"""
File handling utilities and path operations
"""

import sys
from pathlib import Path
from .language_utils import Action

# Video file extensions
VIDEO_EXTS = {'.mkv', '.mp4', '.m4v', '.mov', '.avi', '.wmv', '.flv', '.ts', '.m2ts', '.webm'}

def format_file_size(size_bytes):
    """Convert bytes to human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"

def display_file_path(src: Path):
    """Display the file path"""
    print(f"File: {src}")

def display_file_info(src: Path, info: dict, mode: Action, out_path: Path, debug_cmd: list = None, gpu_info: dict = None, use_gpu: bool = False):
    """Display detailed file information"""
    print(f"Size: {format_file_size(src.stat().st_size)}")
    print(f"Container: {info['container'].upper()}")
    
    if info['has_video']:
        hdr_status = " (HDR)" if info.get('is_hdr', False) else " (SDR)"
        print(f"Video Codec: {info['video_codec'] or 'Unbekannt'}{hdr_status}")
    else:
        print("Video: Nicht vorhanden")
    
    if info['has_audio'] and info['audio_codecs']:
        audio_info = []
        for i, (codec, channels) in enumerate(zip(info['audio_codecs'], info['audio_channels'])):
            lang = info.get('audio_languages', ['unknown'] * len(info['audio_codecs']))[i]
            audio_info.append(f"{codec} ({channels}ch, {lang})")
        print(f"Audio: {', '.join(audio_info)}")
    else:
        print("Audio: Nicht vorhanden")
    
    # Action info
    action_msg = {
        Action.SKIP: "Bereits kompatibel - wird übersprungen",
        Action.REMUX_AUDIO: "Audio nach Stereo AAC konvertieren",
        Action.TRANCODE_VIDEO: "Video nach H.264 SDR konvertieren",
        Action.TRANCODE_ALL: "Video und Audio konvertieren",
        Action.CONTAINER_REMUX: "Container nach MP4 konvertieren"
    }
    print(f"Aktion: {action_msg.get(mode, str(mode))}")
    print(f"Output: {out_path}")
    
    if use_gpu and gpu_info and gpu_info.get('available'):
        print(f"GPU Beschleunigung: {gpu_info['platform'].title()} ({gpu_info['encoder']})")
    
    if debug_cmd:
        print(f"Befehl: {' '.join(debug_cmd)}")

def handle_temp_file_cleanup(temp_path: Path, final_path: Path, src_path: Path, delete_original: bool):
    """Handle temporary file renaming and original file deletion"""
    try:
        # Move temporary file to final location
        temp_path.rename(final_path)
        print(f'Datei umbenannt: {temp_path.name} -> {final_path.name}')
        
        # Delete original file if requested
        if delete_original:
            try:
                src_path.unlink()
                print(f'Originaldatei gelöscht: {src_path.name}')
            except Exception as e:
                print(f'Fehler beim Löschen der Originaldatei {src_path.name}: {e}', file=sys.stderr)
                
    except Exception as e:
        print(f'Fehler beim Umbenennen der temporären Datei {temp_path.name}: {e}', file=sys.stderr)
        # Clean up temporary file on error
        try:
            if temp_path.exists():
                temp_path.unlink()
                print(f'Temporäre Datei entfernt: {temp_path.name}')
        except Exception as cleanup_e:
            print(f'Fehler beim Entfernen der temporären Datei: {cleanup_e}', file=sys.stderr)