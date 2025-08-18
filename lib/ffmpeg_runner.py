"""
FFmpeg command execution with progress monitoring
"""

import json
import re
import signal
import subprocess
import sys
import threading
import time
from datetime import timedelta
from pathlib import Path

# Global variables for signal handling
current_ffmpeg_process = None
interrupted = False

class ProgressMonitor:
    """Real-time ffmpeg progress monitor with progress bar"""
    
    def __init__(self, duration_seconds=None):
        self.duration = duration_seconds
        self.current_time = 0
        self.fps = 0
        self.bitrate = ""
        self.speed = ""
        self.progress_percent = 0
        self.start_time = time.time()
        self.last_update = time.time()
        self.running = False
        
    def parse_progress_line(self, line):
        """Parse ffmpeg progress output line"""
        line = line.strip()
        if not line:
            return False
            
        # Parse out_time_us (microseconds) from progress pipe format
        if line.startswith('out_time_us='):
            try:
                microseconds = int(line.split('=')[1])
                self.current_time = microseconds / 1_000_000  # Convert to seconds
                
                if self.duration and self.duration > 0:
                    self.progress_percent = min(100, (self.current_time / self.duration) * 100)
                return True
            except (ValueError, IndexError):
                pass
        
        # Fallback: Parse time=HH:MM:SS.sss from stderr format
        time_match = re.search(r'time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})', line)
        if time_match:
            hours = int(time_match.group(1))
            minutes = int(time_match.group(2))
            seconds = int(time_match.group(3))
            centiseconds = int(time_match.group(4))
            self.current_time = hours * 3600 + minutes * 60 + seconds + centiseconds / 100
            
            if self.duration and self.duration > 0:
                self.progress_percent = min(100, (self.current_time / self.duration) * 100)
            return True
        
        # Parse fps=XX.X
        fps_match = re.search(r'fps=\s*(\d+\.?\d*)', line)
        if fps_match:
            self.fps = float(fps_match.group(1))
            
        # Parse bitrate=XXXkbits/s
        bitrate_match = re.search(r'bitrate=\s*([0-9.]+[kmg]?bits/s)', line)
        if bitrate_match:
            self.bitrate = bitrate_match.group(1)
            
        # Parse speed=X.XXx
        speed_match = re.search(r'speed=\s*([0-9.]+x)', line)
        if speed_match:
            self.speed = speed_match.group(1)
            
        return False
    
    def get_eta_string(self):
        """Calculate and format estimated time remaining"""
        if not self.duration or self.current_time <= 0:
            return "??:??:??"
            
        elapsed = time.time() - self.start_time
        if elapsed <= 0:
            return "??:??:??"
            
        progress_ratio = self.current_time / self.duration
        if progress_ratio <= 0:
            return "??:??:??"
            
        total_estimated = elapsed / progress_ratio
        remaining = total_estimated - elapsed
        
        if remaining < 0:
            remaining = 0
            
        return str(timedelta(seconds=int(remaining)))
    
    def format_time(self, seconds):
        """Format seconds as HH:MM:SS"""
        return str(timedelta(seconds=int(seconds)))
    
    def draw_progress_bar(self, width=40):
        """Draw a text progress bar"""
        filled = int(width * self.progress_percent / 100)
        bar = '█' * filled + '░' * (width - filled)
        return f"[{bar}]"
    
    def get_progress_line(self):
        """Get formatted progress line"""
        bar = self.draw_progress_bar(30)
        
        if self.duration:
            current_str = self.format_time(self.current_time)
            total_str = self.format_time(self.duration)
            time_info = f"{current_str}/{total_str}"
        else:
            time_info = self.format_time(self.current_time)
        
        eta = self.get_eta_string()
        speed_info = f"{self.speed}" if self.speed else "?.??x"
        fps_info = f"{self.fps:.1f}fps" if self.fps > 0 else "?.?fps"
        
        return f"\r{bar} {self.progress_percent:5.1f}% | {time_info} | ETA: {eta} | {speed_info} | {fps_info}"
    
    def update_display(self):
        """Update progress display"""
        now = time.time()
        if now - self.last_update >= 0.5:  # Update every 500ms
            print(self.get_progress_line(), end='', flush=True)
            self.last_update = now

def signal_handler(signum, frame):
    """Handle Ctrl+C and other signals gracefully"""
    global current_ffmpeg_process, interrupted
    
    print(f"\n\nUnterbrechung erkannt (Signal {signum})")
    interrupted = True
    
    if current_ffmpeg_process and current_ffmpeg_process.poll() is None:
        print("Beende ffmpeg-Prozess graceful...")
        try:
            # Send SIGTERM first (graceful termination)
            current_ffmpeg_process.terminate()
            
            # Wait up to 5 seconds for graceful termination
            try:
                current_ffmpeg_process.wait(timeout=5)
                print("FFmpeg-Prozess erfolgreich beendet")
            except subprocess.TimeoutExpired:
                # Force kill if it doesn't terminate gracefully
                print("FFmpeg antwortet nicht, beende forciert...")
                current_ffmpeg_process.kill()
                current_ffmpeg_process.wait()
                print("FFmpeg-Prozess forciert beendet")
        except Exception as e:
            print(f"Fehler beim Beenden des FFmpeg-Prozesses: {e}")
    
    print("Programm beendet")
    sys.exit(1)

def setup_signal_handlers():
    """Set up signal handlers for graceful interruption"""
    signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # Termination signal

def run(cmd, show_progress=False, duration=None, progress_callback=None):
    """Execute command with optional progress monitoring"""
    global current_ffmpeg_process, interrupted
    
    # Check if we were interrupted before starting
    if interrupted:
        return 130, "", "Process interrupted"
    
    # Ensure command list contains strings for Windows compatibility
    cmd_str = [str(c) for c in cmd]
    
    if not show_progress:
        # Original behavior for non-ffmpeg commands
        p = subprocess.run(cmd_str, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return p.returncode, p.stdout, p.stderr
    
    # Progress monitoring for ffmpeg
    progress = ProgressMonitor(duration)
    
    # Start ffmpeg process with real-time stderr capture
    p = subprocess.Popen(cmd_str, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                        text=True, universal_newlines=True)
    
    # Track the current ffmpeg process globally for signal handling
    current_ffmpeg_process = p
    
    stdout_lines = []
    stderr_lines = []
    
    try:
        # Read stderr in real-time for progress updates
        while True:
            # Check for interruption
            if interrupted:
                print(f"\nProzess wurde unterbrochen")
                break
                
            stderr_line = p.stderr.readline()
            if stderr_line == '' and p.poll() is not None:
                break
            
            if stderr_line:
                stderr_lines.append(stderr_line)
                
                # Parse progress and update display
                if progress.parse_progress_line(stderr_line):
                    # Call Rich progress callback if provided
                    if progress_callback and duration:
                        progress_callback(progress.current_time)
                    else:
                        # Fallback to traditional progress display
                        progress.update_display()
        
        # Get remaining output
        stdout, stderr_remaining = p.communicate()
        if stdout:
            stdout_lines.append(stdout)
        if stderr_remaining:
            stderr_lines.append(stderr_remaining)
        
    except KeyboardInterrupt:
        # This shouldn't happen as we handle it globally, but just in case
        print(f"\nKeyboardInterrupt im Prozess")
        interrupted = True
    
    finally:
        # Clear the global process reference
        current_ffmpeg_process = None
    
    # Final progress update (only if not interrupted)
    if show_progress and not interrupted:
        progress.progress_percent = 100
        print(progress.get_progress_line())
        print()  # New line after progress bar
    elif interrupted:
        print()  # New line after interruption
    
    # Return appropriate exit code
    if interrupted:
        return 130, '\n'.join(stdout_lines), '\n'.join(stderr_lines)  # 130 = interrupted by Ctrl+C
    
    return p.returncode, '\n'.join(stdout_lines), '\n'.join(stderr_lines)

def run_simple(cmd):
    """Simple run function for non-ffmpeg commands (backward compatibility)"""
    return run(cmd, show_progress=False)

def ffprobe_streams(path: Path):
    """Get stream information from media file"""
    cmd = [
        'ffprobe', '-v', 'error',
        '-show_entries', 'stream=index,codec_type,codec_name,channels,color_space,color_transfer,color_primaries,side_data_list:stream_tags=language,title',
        '-of', 'json',
        str(path)
    ]
    code, out, err = run_simple(cmd)
    if code != 0:
        raise RuntimeError(f'ffprobe failed for {path}: {err}')
    data = json.loads(out or '{}')
    return data.get('streams', [])

def get_duration(path: Path):
    """Get duration of media file in seconds"""
    cmd = [
        'ffprobe', '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'csv=p=0',
        str(path)
    ]
    code, out, err = run_simple(cmd)
    if code != 0:
        return None
    try:
        return float(out.strip())
    except (ValueError, AttributeError):
        return None