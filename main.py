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
    ap.add_argument('--delete-original', action='store_true', help='Originaldatei nach erfolgreicher Konvertierung löschen')
    
    # Language handling
    ap.add_argument('--keep-languages', type=str, help='Sprachen beibehalten (Komma-getrennt, z.B. de,en,jp)')
    ap.add_argument('--sort-languages', type=str, help='Sprachen-Reihenfolge (Komma-getrennt, z.B. de,en)')
    
    # Action filtering
    ap.add_argument('--action-filter', type=str, help='Nur Dateien verarbeiten, die diese Aktion benötigen (container_remux, remux_audio, transcode_video, transcode_all)')
    ap.add_argument('--limit', type=int, help='Nur die nächsten N Dateien verarbeiten (überspringt bereits kompatible)')
    ap.add_argument('--use-cache', type=Path, help='Verwende existierende Cache-Datei für Verarbeitung statt neue Analyse')
    
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
            platform_icons = {'metal': 'METAL', 'nvidia': 'NVIDIA', 'intel': 'INTEL'}
            icon = platform_icons.get(gpu_info['platform'], 'GPU')
            print(f"{icon} GPU-Beschleunigung erkannt: {gpu_info['platform'].title()} ({gpu_info['encoder']})")
        else:
            print("GPU-Beschleunigung angefordert, aber nicht verfügbar - verwende CPU-Kodierung")

    root: Path = args.root
    if not root.exists():
        print(f'Pfad existiert nicht: {root}', file=sys.stderr); sys.exit(2)

    # Handle gather mode - analyze files and export to CSV
    if args.gather:
        csv_path = args.gather.resolve()
        gather_files_to_cache(root, csv_path)
        return
    
    # Handle cache-based processing
    if args.use_cache:
        cache_path = args.use_cache.resolve()
        try:
            file_data_list = read_cache_csv(cache_path)
            print(f"Cache-Datei geladen: {cache_path}")
            print(f"Gefunden: {len(file_data_list)} Dateien in Cache")
        except FileNotFoundError as e:
            print(f"Fehler: {e}", file=sys.stderr)
            sys.exit(2)
    else:
        # Auto-generate cache when processing directories
        if not root.is_file():
            # Create temporary cache file
            cache_path = root / '.ffmpeg_converter_cache.csv'
            print(f"Erstelle temporären Cache: {cache_path}")
            file_data_list = gather_files_to_cache(root, cache_path)
        else:
            cache_path = None
            file_data_list = None

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
    processed_count = 0
    
    # Process files based on cache or direct processing
    if args.use_cache or file_data_list:
        # Cache-based processing
        files_to_process = []
        
        # Filter files that need processing and exist
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
        
        # Apply limit if specified
        if args.limit and args.limit > 0:
            files_to_process = files_to_process[:args.limit]
            print(f"Beschränke Verarbeitung auf {len(files_to_process)} Dateien (--limit {args.limit})")
        
        total = len(files_to_process)
        print(f"Zu verarbeitende Dateien: {total}")
        
        # Process each file
        for p in files_to_process:
            # Check for global interruption
            if interrupted:
                print(f"\nVerarbeitung unterbrochen")
                break
            
            target_dir = out_dir if out_dir else p.parent
            try:
                res, auto_yes = process_file(p, target_dir, args.crf, args.preset, args.dry_run, args.interactive, 
                                            auto_yes, args.debug, keep_languages, sort_languages, gpu_info, getattr(args, 'use_gpu', False), action_filter, args.delete_original, cache_path)
                processed_count += 1
                
                if res in ('converted', 'processed'):
                    converted += 1
                elif res in ('skipped', 'planned', 'filtered'):
                    skipped += 1
                elif res in ('remuxed',):
                    remuxed += 1
                elif res in ('interrupted',):
                    interrupted_count += 1
                    break  # Exit early on interruption
                elif res == 'quit':
                    break  # User chose to quit
                else:
                    errors += 1
            except Exception as e:
                print(f'Fehler bei {p}: {e}', file=sys.stderr)
                errors += 1
                
    else:
        # Single file processing (legacy mode)
        if not root.is_file():
            print(f'Fehler: Für Verzeichnis-Verarbeitung wird automatisch ein Cache erstellt', file=sys.stderr)
            sys.exit(2)
            
        if root.suffix.lower() not in VIDEO_EXTS:
            print(f'Fehler: {root} ist keine unterstützte Videodatei', file=sys.stderr)
            sys.exit(2)
        
        total = 1
        target_dir = out_dir if out_dir else root.parent
        try:
            res, auto_yes = process_file(root, target_dir, args.crf, args.preset, args.dry_run, args.interactive, 
                                        auto_yes, args.debug, keep_languages, sort_languages, gpu_info, getattr(args, 'use_gpu', False), action_filter, args.delete_original, None)
            if res in ('converted', 'processed'):
                converted += 1
            elif res in ('skipped', 'planned', 'filtered'):
                skipped += 1
            elif res in ('remuxed',):
                remuxed += 1
            elif res in ('interrupted',):
                interrupted_count += 1
            else:
                errors += 1
        except Exception as e:
            print(f'Fehler bei {root}: {e}', file=sys.stderr)
            errors += 1

    # Final summary
    if interrupted_count > 0:
        print(f'\nUnterbrochen. Dateien: {total} | konvertiert: {converted} | remuxt: {remuxed} | übersprungen/geplant: {skipped} | unterbrochen: {interrupted_count} | Fehler: {errors}')
    else:
        print(f'\nFertig. Dateien: {total} | konvertiert: {converted} | remuxt: {remuxed} | übersprungen/geplant: {skipped} | Fehler: {errors}')

if __name__ == '__main__':
    main()