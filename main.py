#!/usr/bin/env python3
"""
FFmpeg Converter for Plex Direct Play compatibility

Refactored main entry point for the video converter.
Optimizes videos for Apple TV 4K (3. Gen, 2022) + Plex Direct Play:
- Container: MP4
- Video: H.264 SDR (HDR→SDR Tonmapping if needed)  
- Audio: Stereo (2.0) AAC, with language filtering/sorting support
- Progress monitoring with ETA during conversion

Usage:
  python main.py /path/to/folder [options]
  python main.py /path/to/file.mkv [options]
  python main.py /path/to/folder --gather analysis.csv
  python main.py /path/to/folder --use-cache analysis.csv --limit 10

Requires: ffmpeg, ffprobe in PATH
"""

import argparse
import shutil
import sys
from pathlib import Path

# Import our modular components
from lib.ffmpeg_runner import setup_signal_handlers, interrupted
from lib.language_utils import normalize_language, Action
from lib.gpu_utils import detect_gpu_acceleration
from lib.cache_manager import read_cache_csv, gather_files_to_cache
from lib.processor import process_file
from lib.file_utils import VIDEO_EXTS

def parse_arguments():
    """Parse and validate command line arguments"""
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
    ap.add_argument('--delete-original', action='store_true', help='Originaldatei nach erfolgreicher Konvertierung löschen')
    
    # Language handling
    ap.add_argument('--keep-languages', type=str, help='Sprachen beibehalten (Komma-getrennt, z.B. de,en,jp)')
    ap.add_argument('--sort-languages', type=str, help='Sprachen-Reihenfolge (Komma-getrennt, z.B. de,en)')
    
    # Action filtering
    ap.add_argument('--action-filter', type=str, help='Nur Dateien verarbeiten, die diese Aktion benötigen (container_remux, remux_audio, transcode_video, transcode_all)')
    ap.add_argument('--limit', type=int, help='Nur die nächsten N Dateien verarbeiten (überspringt bereits kompatible)')
    ap.add_argument('--use-cache', type=Path, help='Verwende existierende Cache-Datei für Verarbeitung statt neue Analyse')
    
    args = ap.parse_args()
    
    # Validate arguments
    if not 0 <= args.crf <= 51:
        print('Fehler: CRF muss zwischen 0 und 51 liegen', file=sys.stderr)
        sys.exit(2)
    
    return args

def parse_language_arguments(args):
    """Parse and normalize language arguments"""
    keep_languages = []
    if args.keep_languages:
        keep_languages = [normalize_language(lang.strip()) for lang in args.keep_languages.split(',')]
    
    sort_languages = []
    if args.sort_languages:
        sort_languages = [normalize_language(lang.strip()) for lang in args.sort_languages.split(',')]
    
    return keep_languages, sort_languages

def parse_action_filter(action_filter_arg):
    """Parse and validate action filter argument"""
    if not action_filter_arg:
        return None
        
    valid_actions = {
        'container_remux': Action.CONTAINER_REMUX,
        'remux_audio': Action.REMUX_AUDIO,
        'transcode_video': Action.TRANCODE_VIDEO,
        'transcode_all': Action.TRANCODE_ALL
    }
    if action_filter_arg not in valid_actions:
        print(f'Fehler: Ungültiger action-filter. Gültige Werte: {", ".join(valid_actions.keys())}', file=sys.stderr)
        sys.exit(2)
    return valid_actions[action_filter_arg]

def setup_gpu_acceleration(use_gpu):
    """Setup and detect GPU acceleration if requested"""
    if not use_gpu:
        return None
        
    gpu_info = detect_gpu_acceleration()
    if gpu_info['available']:
        platform_icons = {'metal': 'METAL', 'nvidia': 'NVIDIA', 'intel': 'INTEL'}
        icon = platform_icons.get(gpu_info['platform'], 'GPU')
        print(f"{icon} GPU-Beschleunigung erkannt: {gpu_info['platform'].title()} ({gpu_info['encoder']})")
    else:
        print("GPU-Beschleunigung angefordert, aber nicht verfügbar - verwende CPU-Kodierung")
    
    return gpu_info

def update_processing_counters(result, counters):
    """Update processing result counters based on file processing result"""
    if result in ('converted', 'processed'):
        counters['converted'] += 1
    elif result in ('skipped', 'planned', 'filtered'):
        counters['skipped'] += 1
    elif result in ('remuxed',):
        counters['remuxed'] += 1
    elif result in ('interrupted',):
        counters['interrupted'] += 1
        return True  # Signal to break processing loop
    elif result == 'quit':
        return True  # Signal to break processing loop
    else:
        counters['errors'] += 1
    return False  # Continue processing

def collect_video_files(root_path):
    """Collect all video files from a directory"""
    video_files = []
    for ext in VIDEO_EXTS:
        video_files.extend(root_path.rglob(f'*{ext}'))
        video_files.extend(root_path.rglob(f'*{ext.upper()}'))
    
    # Remove duplicates and filter for actual files
    return list(set([p for p in video_files if p.is_file()]))

def filter_cache_files(file_data_list, action_filter):
    """Filter cache files that need processing"""
    files_to_process = []
    
    for entry in file_data_list:
        file_path = Path(entry['file_path'])
        
        # Skip if file doesn't exist
        if not file_path.exists():
            continue
            
        # Skip if already processed
        if entry.get('processed', False):
            continue
        
        # Skip if already compatible (unless action filter requires it)
        if entry.get('direct_play_compatible', False) and not action_filter:
            continue
            
        # Apply action filter if specified
        if action_filter:
            action_needed = entry.get('action_needed', '')
            filter_map = {
                Action.CONTAINER_REMUX: 'Container remux to MP4',
                Action.REMUX_AUDIO: 'Audio remux to stereo AAC', 
                Action.TRANCODE_VIDEO: 'Video transcode to H.264 SDR',
                Action.TRANCODE_ALL: 'Full transcode'
            }
            if not any(filter_text in action_needed for filter_text in filter_map.get(action_filter, [])):
                continue
        
        files_to_process.append(file_path)
    
    return files_to_process

def apply_limit_and_print(files_list, limit, description="Dateien"):
    """Apply limit to files list and print information"""
    if limit and limit > 0:
        files_list = files_list[:limit]
        print(f"Beschränke Verarbeitung auf {len(files_list)} {description} (--limit {limit})")
    return files_list

def process_files_batch(files, out_dir, cache_path, args, keep_languages, sort_languages, gpu_info, counters, action_filter=None):
    """Process a batch of files and update counters"""
    auto_yes = False
    
    for file_path in files:
        # Check for global interruption
        if interrupted:
            print(f"\nVerarbeitung unterbrochen")
            break
        
        target_dir = out_dir if out_dir else file_path.parent
        try:
            res, auto_yes = process_file(
                file_path, target_dir, args.crf, args.preset, args.dry_run, args.interactive,
                auto_yes, args.debug, keep_languages, sort_languages, gpu_info,
                getattr(args, 'use_gpu', False), action_filter,
                args.delete_original, cache_path
            )
            counters['processed'] += 1
            
            # Update counters and check for early exit
            should_break = update_processing_counters(res, counters)
            if should_break:
                break
                
        except Exception as e:
            print(f'Fehler bei {file_path}: {e}', file=sys.stderr)
            counters['errors'] += 1
    
    return counters

def print_final_summary(counters):
    """Print final processing summary"""
    if counters['interrupted'] > 0:
        print(f'\nUnterbrochen. Dateien: {counters["total"]} | konvertiert: {counters["converted"]} | remuxt: {counters["remuxed"]} | übersprungen/geplant: {counters["skipped"]} | unterbrochen: {counters["interrupted"]} | Fehler: {counters["errors"]}')
    else:
        print(f'\nFertig. Dateien: {counters["total"]} | konvertiert: {counters["converted"]} | remuxt: {counters["remuxed"]} | übersprungen/geplant: {counters["skipped"]} | Fehler: {counters["errors"]}')

def main():
    # Setup signal handlers for graceful shutdown
    setup_signal_handlers()
    
    # Parse and validate arguments
    args = parse_arguments()
    keep_languages, sort_languages = parse_language_arguments(args)
    action_filter = parse_action_filter(args.action_filter)

    # Check for required tools
    if shutil.which('ffmpeg') is None or shutil.which('ffprobe') is None:
        print('Fehler: ffmpeg/ffprobe nicht gefunden. Bitte in PATH verfügbar machen.', file=sys.stderr)
        sys.exit(2)
    
    # Setup GPU acceleration
    gpu_info = setup_gpu_acceleration(getattr(args, 'use_gpu', False))

    root: Path = args.root
    if not root.exists():
        print(f'Pfad existiert nicht: {root}', file=sys.stderr); sys.exit(2)

    # Handle gather mode - analyze files and export to CSV
    if args.gather:
        csv_path = args.gather.resolve()
        gather_files_to_cache(root, csv_path)
        return
    
    # Handle cache-based processing (only when --use-cache is specified)
    cache_path = None
    file_data_list = None
    
    if args.use_cache:
        cache_path = args.use_cache.resolve()
        try:
            file_data_list = read_cache_csv(cache_path)
            print(f"Cache-Datei geladen: {cache_path}")
            
            # Count different file states
            total_files = len(file_data_list)
            already_processed = sum(1 for entry in file_data_list if entry.get('processed', False))
            compatible_files = sum(1 for entry in file_data_list if entry.get('direct_play_compatible', False) and not entry.get('processed', False))
            need_processing = total_files - already_processed - compatible_files
            
            print(f"Gefunden: {total_files} Dateien in Cache, {already_processed} sind bereits konvertiert, {need_processing} müssen transcodiert werden")
        except FileNotFoundError:
            # Generate cache file if it doesn't exist
            print(f"Cache-Datei nicht gefunden, erstelle neue: {cache_path}")
            file_data_list = gather_files_to_cache(root, cache_path)

    out_dir = args.out.resolve() if args.out else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)

    # Initialize counters
    counters = {
        'total': 0,
        'converted': 0,
        'skipped': 0,
        'errors': 0,
        'remuxed': 0,
        'interrupted': 0,
        'processed': 0
    }
    
    # Process files based on cache or direct processing
    if args.use_cache:
        files_to_process = filter_cache_files(file_data_list, action_filter)
        files_to_process = apply_limit_and_print(files_to_process, args.limit)
        
        counters['total'] = len(files_to_process)
        print(f"Zu verarbeitende Dateien: {counters['total']}")
        
        process_files_batch(files_to_process, out_dir, cache_path, args, keep_languages, sort_languages, gpu_info, counters, action_filter)
                
    else:
        # Direct processing without cache
        if root.is_file():
            # Single file processing
            if root.suffix.lower() not in VIDEO_EXTS:
                print(f'Fehler: {root} ist keine unterstützte Videodatei', file=sys.stderr)
                sys.exit(2)
            
            counters['total'] = 1
            process_files_batch([root], out_dir, None, args, keep_languages, sort_languages, gpu_info, counters, action_filter)
        else:
            # Directory processing without cache
            video_files = collect_video_files(root)
            video_files = apply_limit_and_print(video_files, args.limit, "Videodateien")
            
            counters['total'] = len(video_files)
            print(f"Gefunden: {counters['total']} Videodateien")
            
            process_files_batch(video_files, out_dir, None, args, keep_languages, sort_languages, gpu_info, counters, action_filter)

    # Final summary
    print_final_summary(counters)

if __name__ == '__main__':
    main()