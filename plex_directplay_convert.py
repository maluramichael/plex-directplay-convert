#!/usr/bin/env python3
"""
plex_directplay_convert.py

Rekursiv alle Videodateien für Apple TV 4K (3. Gen, 2022) + Plex fit machen:
- Container: MP4
- Video: H.264 SDR (HDR→SDR Tonmapping falls nötig)  
- Audio: Stereo (2.0) AAC, Sprach-Filter/Sortierung möglich
- Fortschrittsanzeige mit ETA während Konvertierung

Nutzung:
  python plex_directplay_convert.py /pfad/zum/ordner [Optionen]
  python plex_directplay_convert.py /pfad/zur/datei.mkv [Optionen]
  python plex_directplay_convert.py /pfad/zum/ordner --gather analyse.csv

Video-Qualität:
  --crf 18          Hohe Qualität (größere Dateien)
  --crf 22          Standard Qualität (empfohlen)  
  --crf 26          Niedrigere Qualität (kleinere Dateien)
  --preset slow     Bessere Kompression (langsamer)
  --preset medium   Standard (empfohlen)
  --preset fast     Schnellere Kodierung (größere Dateien)

Sprachen:
  --keep-languages de,en    Nur Deutsche und Englische Spuren behalten
  --sort-languages de,en    Deutsche Spur zuerst, dann Englische

Modi:
  --interactive     Zeigt Details, fragt vor jeder Datei
  --debug          Zeigt ffmpeg-Befehl (mit --interactive)
  --dry-run        Simulation ohne tatsächliche Konvertierung

Erfordert: ffmpeg, ffprobe im PATH
"""
import argparse
import csv
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path, PurePath
from enum import Enum

VIDEO_EXTS = {'.mkv', '.mp4', '.m4v', '.mov', '.avi', '.wmv', '.flv', '.ts', '.m2ts', '.webm'}

# Global variable to track current ffmpeg process for signal handling
current_ffmpeg_process = None
interrupted = False

# Language code mapping - maps various language codes to standardized 2-letter codes
LANGUAGE_MAP = {
    # German variants
    'de': 'de', 'deu': 'de', 'ger': 'de', 'german': 'de', 'deutsch': 'de',
    # English variants  
    'en': 'en', 'eng': 'en', 'english': 'en',
    # Japanese variants
    'jp': 'jp', 'ja': 'jp', 'jpn': 'jp', 'japanese': 'jp',
    # French variants
    'fr': 'fr', 'fra': 'fr', 'fre': 'fr', 'french': 'fr',
    # Spanish variants
    'es': 'es', 'esp': 'es', 'spa': 'es', 'spanish': 'es',
    # Italian variants
    'it': 'it', 'ita': 'it', 'italian': 'it',
    # Common fallbacks
    'unknown': 'unknown', 'und': 'unknown', '': 'unknown'
}

class Action(Enum):
    SKIP = "skip"
    REMUX_AUDIO = "remux_audio" # converts to stereo aac
    TRANCODE_VIDEO = "transcode_video" # converts to h264 SDR
    TRANCODE_ALL = "transcode_all" # converts to h264 SDR and stereo aac
    CONTAINER_REMUX = "container_remux" # converts to mp4

def normalize_language(lang_code):
    """Normalize language code using mapping"""
    if not lang_code:
        return 'unknown'
    return LANGUAGE_MAP.get(lang_code.lower(), lang_code.lower())

def signal_handler(signum, frame):
    """Handle Ctrl+C and other signals gracefully"""
    global current_ffmpeg_process, interrupted
    
    print(f"\n\n🛑 Unterbrechung erkannt (Signal {signum})")
    interrupted = True
    
    if current_ffmpeg_process and current_ffmpeg_process.poll() is None:
        print("⏹️  Beende ffmpeg-Prozess graceful...")
        try:
            # Send SIGTERM first (graceful termination)
            current_ffmpeg_process.terminate()
            
            # Wait up to 5 seconds for graceful termination
            try:
                current_ffmpeg_process.wait(timeout=5)
                print("✅ FFmpeg-Prozess erfolgreich beendet")
            except subprocess.TimeoutExpired:
                # Force kill if it doesn't terminate gracefully
                print("🔨 FFmpeg antwortet nicht, beende forciert...")
                current_ffmpeg_process.kill()
                current_ffmpeg_process.wait()
                print("✅ FFmpeg-Prozess forciert beendet")
        except Exception as e:
            print(f"⚠️  Fehler beim Beenden des FFmpeg-Prozesses: {e}")
    
    print("👋 Programm beendet")
    sys.exit(1)

def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown"""
    signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # Termination request
    
    # On Unix systems, also handle SIGHUP
    if hasattr(signal, 'SIGHUP'):
        signal.signal(signal.SIGHUP, signal_handler)

def detect_gpu_acceleration():
    """Detect available GPU acceleration options"""
    gpu_info = {
        'available': False,
        'encoder': None,
        'decoder': None,
        'platform': None
    }
    
    try:
        # Check ffmpeg encoders
        code, out, err = run_simple(['ffmpeg', '-encoders'])
        if code != 0:
            return gpu_info
            
        encoders_output = out.lower()
        
        # Check for Metal (macOS)
        if 'videotoolbox' in encoders_output and sys.platform == 'darwin':
            gpu_info.update({
                'available': True,
                'encoder': 'h264_videotoolbox',
                'decoder': 'h264',  # Use software decoder, hardware encoder
                'platform': 'metal'
            })
            return gpu_info
        
        # Check for NVIDIA (Windows/Linux)
        if 'h264_nvenc' in encoders_output:
            gpu_info.update({
                'available': True,
                'encoder': 'h264_nvenc',
                'decoder': 'h264_cuvid',  # Hardware decoder if available
                'platform': 'nvidia'
            })
            return gpu_info
            
        # Check for Intel QuickSync (Windows/Linux)
        if 'h264_qsv' in encoders_output:
            gpu_info.update({
                'available': True,
                'encoder': 'h264_qsv',
                'decoder': 'h264_qsv',
                'platform': 'intel'
            })
            return gpu_info
            
    except Exception as e:
        print(f"⚠️  GPU-Erkennung fehlgeschlagen: {e}")
    
    return gpu_info

def get_gpu_encoder_params(gpu_info, crf, preset):
    """Get GPU-specific encoding parameters"""
    if not gpu_info['available']:
        return []
    
    params = []
    
    if gpu_info['platform'] == 'metal':
        # VideoToolbox (Mac Metal)
        # Convert CRF to quality (0-100, higher = better)
        quality = max(0, min(100, 100 - (crf * 2)))
        params.extend([
            '-c:v', 'h264_videotoolbox',
            '-q:v', str(quality),
            '-realtime', '0'  # Allow slower encoding for better quality
        ])
        
    elif gpu_info['platform'] == 'nvidia':
        # NVIDIA NVENC
        # Convert preset to NVENC preset
        nvenc_presets = {
            'ultrafast': 'p1', 'superfast': 'p2', 'veryfast': 'p3',
            'faster': 'p4', 'fast': 'p5', 'medium': 'p6',
            'slow': 'p7', 'slower': 'p7', 'veryslow': 'p7'
        }
        nvenc_preset = nvenc_presets.get(preset, 'p6')
        
        params.extend([
            '-c:v', 'h264_nvenc',
            '-preset', nvenc_preset,
            '-cq', str(crf),
            '-rc', 'constqp'
        ])
        
    elif gpu_info['platform'] == 'intel':
        # Intel QuickSync
        params.extend([
            '-c:v', 'h264_qsv',
            '-preset', preset,
            '-global_quality', str(crf)
        ])
    
    return params

def filter_and_sort_streams(streams, languages, keep_languages=None, sort_languages=None):
    """Filter and sort streams based on language preferences"""
    if not streams:
        return []
    
    # Always keep 'unknown' language streams
    keep_langs = set(keep_languages or [])
    keep_langs.add('unknown')
    
    # Filter streams
    if keep_languages:
        filtered_streams = []
        for i, stream in enumerate(streams):
            tags = stream.get('tags', {})
            lang = normalize_language(tags.get('language', ''))
            if lang in keep_langs:
                filtered_streams.append((i, stream, lang))
    else:
        filtered_streams = [(i, stream, normalize_language(stream.get('tags', {}).get('language', ''))) 
                           for i, stream in enumerate(streams)]
    
    # Sort by language preference if specified
    if sort_languages:
        def sort_key(item):
            _, stream, lang = item
            try:
                return sort_languages.index(lang)
            except ValueError:
                return len(sort_languages)  # Put unknown languages at end
        filtered_streams.sort(key=sort_key)
    
    return filtered_streams

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

def run(cmd, show_progress=False, duration=None):
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
                print(f"\n🛑 Prozess wurde unterbrochen")
                break
                
            stderr_line = p.stderr.readline()
            if stderr_line == '' and p.poll() is not None:
                break
            
            if stderr_line:
                stderr_lines.append(stderr_line)
                
                # Parse progress and update display
                if progress.parse_progress_line(stderr_line):
                    progress.update_display()
        
        # Get remaining output
        stdout, stderr_remaining = p.communicate()
        if stdout:
            stdout_lines.append(stdout)
        if stderr_remaining:
            stderr_lines.append(stderr_remaining)
        
    except KeyboardInterrupt:
        # This shouldn't happen as we handle it globally, but just in case
        print(f"\n🛑 KeyboardInterrupt im Prozess")
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

def is_hdr_content(video_stream):
    """Detect HDR content based on color characteristics and side data"""
    if not video_stream:
        return False
    
    # Check color transfer characteristics
    color_transfer = video_stream.get('color_transfer', '').lower()
    color_primaries = video_stream.get('color_primaries', '').lower()
    
    # Common HDR indicators
    hdr_transfers = {'smpte2084', 'arib-std-b67', 'smpte428', 'iec61966-2-1'}
    hdr_primaries = {'bt2020', 'smpte431', 'smpte432'}
    
    if color_transfer in hdr_transfers or color_primaries in hdr_primaries:
        return True
    
    # Check side data for HDR metadata
    side_data_list = video_stream.get('side_data_list', [])
    for side_data in side_data_list:
        side_data_type = side_data.get('side_data_type', '').lower()
        if 'hdr' in side_data_type or 'mastering' in side_data_type or 'content_light' in side_data_type:
            return True
    
    return False

def discover_media(path: Path):
    streams = ffprobe_streams(path)
    v = next((s for s in streams if s.get('codec_type') == 'video'), None)
    a = [s for s in streams if s.get('codec_type') == 'audio']
    s = [s for s in streams if s.get('codec_type') == 'subtitle']

    video_codec = (v or {}).get('codec_name')
    audio_codecs = [s.get('codec_name') for s in a]
    audio_channels = [int(s.get('channels') or 0) for s in a]
    audio_languages = []
    subtitle_languages = []
    is_hdr = is_hdr_content(v)

    # Extract audio languages
    for stream in a:
        tags = stream.get('tags', {})
        lang = tags.get('language', '')
        normalized_lang = normalize_language(lang)
        audio_languages.append(normalized_lang)

    # Extract subtitle languages  
    for stream in s:
        tags = stream.get('tags', {})
        lang = tags.get('language', '')
        normalized_lang = normalize_language(lang)
        subtitle_languages.append(normalized_lang)

    return {
        'video_codec': video_codec,
        'audio_codecs': audio_codecs,
        'audio_channels': audio_channels,
        'audio_languages': audio_languages,
        'subtitle_languages': subtitle_languages,
        'audio_streams': a,
        'subtitle_streams': s,
        'container': path.suffix.lower().lstrip('.'),
        'has_audio': len(a) > 0,
        'has_video': v is not None,
        'is_hdr': is_hdr,
    }

def needs_processing(info, out_ext: str):
    """Decide whether we must transcode or can remux, or skip entirely.
       Direct-Play-Ziel: MP4 + H.264 SDR + AAC Stereo (Apple TV compatibility)
    """
    container_ok = info['container'] == 'mp4'
    video_ok = (info['video_codec'] or '').lower() in {'h264'} and not info.get('is_hdr', False)
    audio_ok = info['has_audio'] and info['audio_codecs'] and all(c in {'aac'} for c in info['audio_codecs']) and all(ch == 2 for ch in info['audio_channels'])

    if container_ok and video_ok and audio_ok:
        return Action.SKIP  # vollständig kompatibel
    elif not container_ok and video_ok and audio_ok:
        # Nur Container muss zu MP4 geändert werden
        return Action.CONTAINER_REMUX
    elif container_ok and video_ok and not audio_ok:
        # Video ist bereits H.264 SDR, nur Audio zu AAC Stereo
        return Action.REMUX_AUDIO
    elif container_ok and audio_ok and not video_ok:
        # Audio ist bereits AAC Stereo, nur Video transkodieren
        return Action.TRANCODE_VIDEO
    else:
        # Beide müssen transkodiert werden
        return Action.TRANCODE_ALL

def build_ffmpeg_cmd(inp: Path, out: Path, mode: Action, crf: int, preset: str, is_hdr: bool = False, 
                     info: dict = None, keep_languages: list = None, sort_languages: list = None, 
                     gpu_info: dict = None, use_gpu: bool = False):
    base = ['ffmpeg', '-y', '-hide_banner', '-loglevel', 'warning', '-progress', 'pipe:2', '-i', str(inp)]
    
    if mode == Action.SKIP:
        return None

    # Build stream mapping based on language preferences
    map_args = ['-map', '0:v:0']  # Always map first video stream
    
    # Handle audio stream mapping
    if info and 'audio_streams' in info:
        audio_filtered = filter_and_sort_streams(info['audio_streams'], info.get('audio_languages', []), 
                                                keep_languages, sort_languages)
        if audio_filtered:
            # Map filtered audio streams in preference order
            for i, (orig_idx, stream, lang) in enumerate(audio_filtered):
                map_args.extend(['-map', f'0:a:{orig_idx}'])
        else:
            map_args.extend(['-map', '0:a:0?'])  # Fallback to first audio if no matches
    else:
        map_args.extend(['-map', '0:a:0?'])  # Fallback when no language filtering

    if mode == Action.CONTAINER_REMUX:
        # Nur Container zu MP4 ändern, alles andere kopieren
        return base + map_args + [
            '-c:v', 'copy',
            '-c:a', 'copy',
            '-movflags', '+faststart',
            str(out)
        ]
    elif mode == Action.REMUX_AUDIO:
        # Video kopieren, Audio nach AAC Stereo; MP4 optimieren
        return base + map_args + [
            '-c:v', 'copy',
            '-c:a', 'aac', '-ac', '2', '-b:a', '192k',
            '-movflags', '+faststart',
            str(out)
        ]
    elif mode == Action.TRANCODE_VIDEO:
        # Video transkodieren, Audio kopieren
        cmd = base + map_args + ['-c:a', 'copy']
        
        # Choose video encoder (GPU vs CPU)
        if use_gpu and gpu_info and gpu_info['available']:
            # GPU encoding
            gpu_params = get_gpu_encoder_params(gpu_info, crf, preset)
            cmd.extend(gpu_params)
        else:
            # CPU encoding
            cmd.extend(['-c:v', 'libx264', '-preset', preset, '-crf', str(crf)])
        
        # HDR to SDR tone mapping for Apple TV compatibility
        if is_hdr:
            # Note: GPU tone mapping may have different filter syntax
            if use_gpu and gpu_info and gpu_info['platform'] == 'metal':
                # VideoToolbox tone mapping (simplified)
                cmd.extend([
                    '-color_primaries', 'bt709',
                    '-color_trc', 'bt709',
                    '-colorspace', 'bt709'
                ])
            else:
                # Software tone mapping
                cmd.extend([
                    '-vf', 'zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p',
                    '-color_primaries', 'bt709',
                    '-color_trc', 'bt709',
                    '-colorspace', 'bt709'
                ])
        
        cmd.extend(['-movflags', '+faststart', str(out)])
        return cmd
    else:
        # Action.TRANCODE_ALL: Video -> H.264 SDR, Audio -> AAC Stereo
        cmd = base + map_args + ['-c:a', 'aac', '-ac', '2', '-b:a', '192k']
        
        # Choose video encoder (GPU vs CPU)
        if use_gpu and gpu_info and gpu_info['available']:
            # GPU encoding
            gpu_params = get_gpu_encoder_params(gpu_info, crf, preset)
            cmd.extend(gpu_params)
        else:
            # CPU encoding
            cmd.extend(['-c:v', 'libx264', '-preset', preset, '-crf', str(crf)])
        
        # HDR to SDR tone mapping for Apple TV compatibility
        if is_hdr:
            # Note: GPU tone mapping may have different filter syntax
            if use_gpu and gpu_info and gpu_info['platform'] == 'metal':
                # VideoToolbox tone mapping (simplified)
                cmd.extend([
                    '-color_primaries', 'bt709',
                    '-color_trc', 'bt709',
                    '-colorspace', 'bt709'
                ])
            else:
                # Software tone mapping
                cmd.extend([
                    '-vf', 'zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p',
                    '-color_primaries', 'bt709',
                    '-color_trc', 'bt709',
                    '-colorspace', 'bt709'
                ])
        
        cmd.extend(['-movflags', '+faststart', str(out)])
        return cmd

def format_file_size(size_bytes):
    """Convert bytes to human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"

def display_file_info(src: Path, info: dict, mode: Action, out_path: Path, debug_cmd: list = None, gpu_info: dict = None, use_gpu: bool = False):
    """Display detailed file information"""
    print(f"\n{'='*60}")
    print(f"📁 Datei: {src}")
    print(f"📏 Größe: {format_file_size(src.stat().st_size)}")
    print(f"📦 Container: {info['container'].upper()}")
    
    if info['has_video']:
        hdr_status = " (HDR)" if info.get('is_hdr', False) else " (SDR)"
        print(f"🎥 Video Codec: {info['video_codec'] or 'Unbekannt'}{hdr_status}")
    else:
        print("🎥 Video: Nicht vorhanden")
    
    if info['has_audio'] and info['audio_codecs']:
        audio_info = []
        for i, (codec, channels) in enumerate(zip(info['audio_codecs'], info['audio_channels'])):
            lang = info.get('audio_languages', ['unknown'] * len(info['audio_codecs']))[i]
            audio_info.append(f"{codec} ({channels}ch, {lang})")
        print(f"🔊 Audio: {', '.join(audio_info)}")
    else:
        print("🔊 Audio: Nicht vorhanden")
    
    # Show subtitles if any
    if info.get('subtitle_languages'):
        sub_langs = ', '.join(set(info['subtitle_languages']))  # Remove duplicates
        print(f"💬 Subtitles: {sub_langs}")
    
    # Show GPU acceleration status
    if use_gpu:
        if gpu_info and gpu_info['available']:
            platform_icons = {'metal': '🍎', 'nvidia': '🟢', 'intel': '🔵'}
            icon = platform_icons.get(gpu_info['platform'], '⚡')
            print(f"{icon} GPU: {gpu_info['platform'].title()} ({gpu_info['encoder']})")
        else:
            print("⚠️  GPU: Angefordert, aber nicht verfügbar - verwende CPU")
    
    print(f"📤 Ausgabe: {out_path}")
    
    # Show what will be done
    if mode == Action.SKIP:
        print("✅ Aktion: Bereits kompatibel - nichts zu tun")
    elif mode == Action.CONTAINER_REMUX:
        print("🔄 Aktion: Nur Container zu MP4 ändern (remux)")
    elif mode == Action.REMUX_AUDIO:
        print("🔄 Aktion: Video kopieren, Audio zu AAC Stereo konvertieren")
    elif mode == Action.TRANCODE_VIDEO:
        hdr_note = " + HDR→SDR Konvertierung" if info.get('is_hdr', False) else ""
        print(f"🎯 Aktion: Video zu H.264{hdr_note} konvertieren, Audio kopieren")
    else:  # Action.TRANCODE_ALL
        hdr_note = " + HDR→SDR Konvertierung" if info.get('is_hdr', False) else ""
        print(f"🎯 Aktion: Video zu H.264{hdr_note} + Audio zu AAC Stereo konvertieren")
    
    # Show debug command if provided
    if debug_cmd:
        print(f"\n🔧 FFmpeg Befehl:")
        cmd_str = ' '.join(f'"{arg}"' if ' ' in arg else arg for arg in debug_cmd)
        print(f"   {cmd_str}")
    
    print(f"{'='*60}")

def is_direct_play_compatible(info):
    """Check if file is already Direct Play compatible for Apple TV 4K"""
    container_ok = info['container'] == 'mp4'
    video_ok = (info['video_codec'] or '').lower() in {'h264'} and not info.get('is_hdr', False)
    audio_ok = info['has_audio'] and info['audio_codecs'] and all(c in {'aac'} for c in info['audio_codecs']) and all(ch == 2 for ch in info['audio_channels'])
    
    return container_ok and video_ok and audio_ok

def analyze_file_for_csv(src: Path):
    """Analyze a single file and return data for CSV export"""
    try:
        info = discover_media(src)
        file_size = src.stat().st_size
        
        # Join audio codecs and channels info
        audio_codecs_str = ', '.join(info['audio_codecs']) if info['audio_codecs'] else 'None'
        audio_channels_str = ', '.join(str(ch) for ch in info['audio_channels']) if info['audio_channels'] else 'None'
        
        # Determine what processing is needed
        mode = needs_processing(info, 'mp4')
        if mode == Action.SKIP:
            action_needed = 'None (already compatible)'
        elif mode == Action.CONTAINER_REMUX:
            action_needed = 'Container remux only'
        elif mode == Action.REMUX_AUDIO:
            action_needed = 'Audio transcode to AAC stereo'
        elif mode == Action.TRANCODE_VIDEO:
            hdr_note = " + HDR→SDR" if info.get('is_hdr', False) else ""
            action_needed = f'Video transcode to H.264{hdr_note}'
        else:  # Action.TRANCODE_ALL
            hdr_note = " + HDR→SDR" if info.get('is_hdr', False) else ""
            action_needed = f'Full transcode (video{hdr_note} + audio)'
        
        return {
            'file_path': str(src),
            'file_name': src.name,
            'file_size_bytes': file_size,
            'file_size_mb': round(file_size / (1024 * 1024), 2),
            'container': info['container'].upper(),
            'video_codec': info['video_codec'] or 'None',
            'is_hdr': info.get('is_hdr', False),
            'audio_codecs': audio_codecs_str,
            'audio_channels': audio_channels_str,
            'has_video': info['has_video'],
            'has_audio': info['has_audio'],
            'direct_play_compatible': is_direct_play_compatible(info),
            'action_needed': action_needed,
            'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    except Exception as e:
        return {
            'file_path': str(src),
            'file_name': src.name,
            'file_size_bytes': 0,
            'file_size_mb': 0,
            'container': 'ERROR',
            'video_codec': 'ERROR',
            'is_hdr': False,
            'audio_codecs': 'ERROR',
            'audio_channels': 'ERROR',
            'has_video': False,
            'has_audio': False,
            'direct_play_compatible': False,
            'action_needed': f'Analysis failed: {str(e)}',
            'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

def write_analysis_csv(file_data_list, csv_path: Path):
    """Write analysis results to CSV file"""
    if not file_data_list:
        print("Keine Dateien zu analysieren gefunden.")
        return
    
    fieldnames = [
        'file_path', 'file_name', 'file_size_bytes', 'file_size_mb',
        'container', 'video_codec', 'is_hdr', 'audio_codecs', 'audio_channels',
        'has_video', 'has_audio', 'direct_play_compatible', 'action_needed',
        'analysis_date'
    ]
    
    with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(file_data_list)
    
    print(f"Analyse gespeichert in: {csv_path}")
    print(f"Analysierte Dateien: {len(file_data_list)}")
    compatible_count = sum(1 for data in file_data_list if data['direct_play_compatible'])
    print(f"Direct Play kompatibel: {compatible_count}/{len(file_data_list)} ({compatible_count/len(file_data_list)*100:.1f}%)")

def ask_user_confirmation():
    """Ask user for confirmation with options"""
    while True:
        choice = input("Fortfahren? (j)a / (n)ein / (a)lle / (q)uit: ").lower().strip()
        if choice in ['j', 'ja', 'y', 'yes']:
            return 'yes'
        elif choice in ['n', 'nein', 'no']:
            return 'no'
        elif choice in ['a', 'alle', 'all']:
            return 'all'
        elif choice in ['q', 'quit', 'exit']:
            return 'quit'
        else:
            print("Bitte eingeben: j/n/a/q")

def process_file(src: Path, dst_dir: Path, crf: int, preset: str, dry_run: bool, interactive: bool = False, 
                auto_yes: bool = False, debug: bool = False, keep_languages: list = None, sort_languages: list = None,
                gpu_info: dict = None, use_gpu: bool = False, action_filter: Action = None):
    info = discover_media(src)
    if not info['has_video']:
        print(f'⏭️  Kein Video: {src}')
        return 'skipped', auto_yes

    out_name = src.stem + '.mp4'
    out_path = (dst_dir / out_name).resolve()
    
    # Get duration for progress monitoring
    duration = get_duration(src)

    mode = needs_processing(info, 'mp4')
    
    # Check action filter - skip file if it doesn't match the filter
    if action_filter and mode != action_filter:
        return 'filtered', auto_yes
    
    # Build command for debug display
    debug_cmd = None
    if debug or (interactive and debug):
        debug_cmd = build_ffmpeg_cmd(src, out_path, mode, crf, preset, info.get('is_hdr', False), 
                                   info, keep_languages, sort_languages, gpu_info, use_gpu)
    
    # Interactive mode: show info and ask for confirmation
    if interactive and not auto_yes:
        display_file_info(src, info, mode, out_path, debug_cmd, gpu_info, use_gpu)
        choice = ask_user_confirmation()
        if choice == 'quit':
            print("Abgebrochen.")
            sys.exit(0)
        elif choice == 'no':
            print("Übersprungen.")
            return 'skipped', auto_yes
        elif choice == 'all':
            # Set flag to skip further confirmations
            auto_yes = True

    if mode == Action.SKIP:
        print(f'✅ Bereits kompatibel: {src}')
        return 'skipped', auto_yes
    elif mode == Action.CONTAINER_REMUX:
        cmd = build_ffmpeg_cmd(src, out_path, mode, crf, preset, info.get('is_hdr', False), 
                              info, keep_languages, sort_languages, gpu_info, use_gpu)
        print(f'🔁 Container Remux: {src.name} -> {out_path.name}')
        if not dry_run:
            code, out, err = run(cmd, show_progress=True, duration=duration)
            if code == 130:  # Interrupted
                return 'interrupted', auto_yes
            elif code != 0:
                print(err, file=sys.stderr)
                return 'error', auto_yes
        return 'remuxed', auto_yes

    cmd = build_ffmpeg_cmd(src, out_path, mode, crf, preset, info.get('is_hdr', False), 
                          info, keep_languages, sort_languages, gpu_info, use_gpu)
    if mode == Action.REMUX_AUDIO:
        action = 'remux+audio'
    elif mode == Action.TRANCODE_VIDEO:
        action = 'video-only'
    else:  # Action.TRANCODE_ALL
        action = 'transcode'
    hdr_status = " HDR→SDR" if info.get('is_hdr', False) else ""
    gpu_status = f" ({gpu_info['platform'].upper()})" if use_gpu and gpu_info and gpu_info['available'] else ""
    print(f'🎯 {action}{hdr_status}{gpu_status}: {src.name} -> {out_path.name} (v:{info["video_codec"]} a:{",".join(info["audio_codecs"] or ["-"])})')
    if dry_run:
        return 'planned', auto_yes
    code, out, err = run(cmd, show_progress=True, duration=duration)
    if code == 130:  # Interrupted
        return 'interrupted', auto_yes
    elif code != 0:
        print(err, file=sys.stderr)
        return 'error', auto_yes
    return 'converted', auto_yes

def main():
    # Setup signal handlers for graceful shutdown
    setup_signal_handlers()
    
    ap = argparse.ArgumentParser(description='Plex Direct Play Konverter für Apple TV 4K (3. Gen)')
    ap.add_argument('root', type=Path, help='Wurzelverzeichnis (rekursiv) oder einzelne Datei')
    ap.add_argument('--out', type=Path, default=None, help='Zielordner (Standard: in-place neben Original)')
    
    # Video encoding parameters
    ap.add_argument('--crf', type=int, default=22, 
                    help='Constant Rate Factor für x264 (0-51, niedriger = besser Qualität, Standard: 22)')
    ap.add_argument('--preset', type=str, default='medium',
                    choices=['ultrafast', 'superfast', 'veryfast', 'faster', 'fast', 'medium', 'slow', 'slower', 'veryslow'],
                    help='x264 Encoding Preset - schneller = größere Datei (Standard: medium)')
    ap.add_argument('--use-gpu', action='store_true',
                    help='GPU-Beschleunigung verwenden (Mac Metal / Windows NVIDIA)')
    
    # Operation modes
    ap.add_argument('--dry-run', action='store_true', help='Nur zeigen, was passieren würde')
    ap.add_argument('--interactive', '-i', action='store_true', help='Interaktiver Modus: Zeigt Details und fragt nach Bestätigung')
    ap.add_argument('--debug', action='store_true', help='Debug-Modus: Zeigt ffmpeg-Befehl in interaktivem Modus')
    ap.add_argument('--gather', '-g', type=Path, help='Sammelmodus: Analysiert alle Dateien und speichert Informationen in CSV-Datei')
    
    # Language handling
    ap.add_argument('--keep-languages', type=str, help='Sprachen beibehalten (Komma-getrennt, z.B. de,en,jp)')
    ap.add_argument('--sort-languages', type=str, help='Sprachen-Reihenfolge (Komma-getrennt, z.B. de,en)')
    
    # Action filtering
    ap.add_argument('--action-filter', type=str, help='Nur Dateien verarbeiten, die diese Aktion benötigen (container_remux, remux_audio, transcode_video, transcode_all)')
    
    args = ap.parse_args()

    # Validate CRF value
    if not 0 <= args.crf <= 51:
        print('Fehler: CRF muss zwischen 0 und 51 liegen', file=sys.stderr)
        sys.exit(2)

    # Parse language arguments
    keep_languages = []
    if args.keep_languages:
        keep_languages = [normalize_language(lang.strip()) for lang in args.keep_languages.split(',')]
    
    sort_languages = []
    if args.sort_languages:
        sort_languages = [normalize_language(lang.strip()) for lang in args.sort_languages.split(',')]

    # Parse action filter
    action_filter = None
    if args.action_filter:
        valid_actions = {
            'container_remux': Action.CONTAINER_REMUX,
            'remux_audio': Action.REMUX_AUDIO,
            'transcode_video': Action.TRANCODE_VIDEO,
            'transcode_all': Action.TRANCODE_ALL
        }
        if args.action_filter not in valid_actions:
            print(f'Fehler: Ungültiger action-filter. Gültige Werte: {", ".join(valid_actions.keys())}', file=sys.stderr)
            sys.exit(2)
        action_filter = valid_actions[args.action_filter]

    if shutil.which('ffmpeg') is None or shutil.which('ffprobe') is None:
        print('Fehler: ffmpeg/ffprobe nicht gefunden. Bitte in PATH verfügbar machen.', file=sys.stderr)
        sys.exit(2)
    
    # GPU acceleration detection
    gpu_info = None
    if getattr(args, 'use_gpu', False):  # Handle potential missing attribute
        gpu_info = detect_gpu_acceleration()
        if gpu_info['available']:
            platform_icons = {'metal': '🍎', 'nvidia': '🟢', 'intel': '🔵'}
            icon = platform_icons.get(gpu_info['platform'], '⚡')
            print(f"{icon} GPU-Beschleunigung erkannt: {gpu_info['platform'].title()} ({gpu_info['encoder']})")
        else:
            print("⚠️  GPU-Beschleunigung angefordert, aber nicht verfügbar - verwende CPU-Kodierung")

    root: Path = args.root
    if not root.exists():
        print(f'Pfad existiert nicht: {root}', file=sys.stderr); sys.exit(2)

    # Handle gather mode - analyze files and export to CSV
    if args.gather:
        csv_path = args.gather.resolve()
        print(f"Sammelmodus: Analysiere Dateien und speichere in {csv_path}")
        
        file_data_list = []
        total_files = 0
        
        if root.is_file():
            # Single file
            if root.suffix.lower() in VIDEO_EXTS:
                total_files = 1
                print(f"Analysiere: {root}")
                file_data = analyze_file_for_csv(root)
                file_data_list.append(file_data)
        else:
            # Directory - collect all video files first to show progress
            video_files = [p for p in root.rglob('*') if p.is_file() and p.suffix.lower() in VIDEO_EXTS]
            total_files = len(video_files)
            print(f"Gefunden: {total_files} Videodateien")
            
            for i, p in enumerate(video_files, 1):
                print(f"Analysiere ({i}/{total_files}): {p.name}")
                file_data = analyze_file_for_csv(p)
                file_data_list.append(file_data)
        
        # Write CSV and exit
        write_analysis_csv(file_data_list, csv_path)
        return

    out_dir = args.out.resolve() if args.out else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)

    total = 0
    converted = 0
    skipped = 0
    errors = 0
    remuxed = 0
    interrupted_count = 0
    auto_yes = False

    # Handle single file or directory
    if root.is_file():
        # Single file processing
        if root.suffix.lower() not in VIDEO_EXTS:
            print(f'Fehler: {root} ist keine unterstützte Videodatei', file=sys.stderr)
            sys.exit(2)
        
        total = 1
        target_dir = out_dir if out_dir else root.parent
        try:
            res, auto_yes = process_file(root, target_dir, args.crf, args.preset, args.dry_run, args.interactive, 
                                        auto_yes, args.debug, keep_languages, sort_languages, gpu_info, getattr(args, 'use_gpu', False), action_filter)
            if res in ('converted',):
                converted += 1
            elif res in ('skipped', 'planned', 'filtered'):
                skipped += 1
            elif res in ('remuxed',):
                remuxed += 1
            elif res in ('interrupted',):
                interrupted_count += 1
                # For single file, just mark as interrupted and continue to summary
            else:
                errors += 1
        except Exception as e:
            print(f'Fehler bei {root}: {e}', file=sys.stderr)
            errors += 1
    else:
        # Directory processing (recursive)
        for p in root.rglob('*'):
            # Check for global interruption
            if interrupted:
                print(f"\n🛑 Verarbeitung unterbrochen")
                break
                
            if not p.is_file():
                continue
            if p.suffix.lower() not in VIDEO_EXTS:
                continue

            total += 1
            target_dir = out_dir if out_dir else p.parent
            try:
                res, auto_yes = process_file(p, target_dir, args.crf, args.preset, args.dry_run, args.interactive, 
                                            auto_yes, args.debug, keep_languages, sort_languages, gpu_info, getattr(args, 'use_gpu', False), action_filter)
                if res in ('converted',):
                    converted += 1
                elif res in ('skipped', 'planned', 'filtered'):
                    skipped += 1
                elif res in ('remuxed',):
                    remuxed += 1
                elif res in ('interrupted',):
                    interrupted_count += 1
                    break  # Exit early on interruption
                else:
                    errors += 1
            except Exception as e:
                print(f'Fehler bei {p}: {e}', file=sys.stderr)
                errors += 1

    # Final summary
    if interrupted_count > 0:
        print(f'\n🛑 Unterbrochen. Dateien: {total} | konvertiert: {converted} | remuxt: {remuxed} | übersprungen/geplant: {skipped} | unterbrochen: {interrupted_count} | Fehler: {errors}')
    else:
        print(f'\nFertig. Dateien: {total} | konvertiert: {converted} | remuxt: {remuxed} | übersprungen/geplant: {skipped} | Fehler: {errors}')

if __name__ == '__main__':
    main()
