"""
Main file processing logic
"""

from pathlib import Path
from .media_analyzer import discover_media, needs_processing
from .ffmpeg_runner import get_duration, run
from .ffmpeg_builder import build_ffmpeg_cmd
from .file_utils import display_file_path, display_file_info, handle_temp_file_cleanup
from .language_utils import Action
from .cache_manager import update_cache_entry

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
                gpu_info: dict = None, use_gpu: bool = False, action_filter: Action = None, delete_original: bool = False,
                cache_path: Path = None):
    """Process a single video file"""
    display_file_path(src)
    info = discover_media(src)
    if not info['has_video']:
        print(f'Kein Video: {src}')
        return 'skipped', auto_yes

    out_name = src.stem + '.mp4'
    out_path = (dst_dir / out_name).resolve()
    
    # Use temporary filename if output would overwrite source and delete_original is enabled
    temp_output = False
    if delete_original and src.resolve() == out_path:
        temp_output = True
        out_path = (dst_dir / (src.stem + '.tmp.mp4')).resolve()
    
    # Get duration for progress monitoring
    duration = get_duration(src)
    mode = needs_processing(info, 'mp4')

    # Build command for debug display
    debug_cmd = None
    if debug or (interactive and debug):
        debug_cmd = build_ffmpeg_cmd(src, out_path, mode, crf, preset, info.get('is_hdr', False), 
                                   info, keep_languages, sort_languages, gpu_info, use_gpu)
    
    # Check action filter - skip file if it doesn't match the filter
    if action_filter and mode != action_filter:
        return 'filtered', auto_yes

    display_file_info(src, info, mode, out_path, debug_cmd, gpu_info, use_gpu)

    if mode == Action.SKIP:
        print("Übersprungen")
        return 'skipped', auto_yes

    user_choice = 'yes'
    if interactive and not auto_yes:
        user_choice = ask_user_confirmation()
        if user_choice == 'quit':
            print("Beende Programm.")
            return 'quit', False
        elif user_choice == 'no':
            print("Übersprungen")
            return 'skipped', auto_yes
        elif user_choice == 'all':
            auto_yes = True

    if dry_run:
        print("DRY-RUN: Würde verarbeitet werden")
        return 'processed', auto_yes

    # Create output directory if it doesn't exist
    dst_dir.mkdir(parents=True, exist_ok=True)

    # Check if output file already exists (unless using temporary output)
    if not temp_output and out_path.exists():
        print(f"Output-Datei existiert bereits: {out_path}")
        return 'skipped', auto_yes

    print(f"Erstelle: {out_path.name}")
    cmd = build_ffmpeg_cmd(src, out_path, mode, crf, preset, info.get('is_hdr', False), 
                          info, keep_languages, sort_languages, gpu_info, use_gpu)
    
    if not cmd:
        print("Kein FFmpeg-Befehl erstellt")
        return 'error', auto_yes

    print("Verarbeitung beginnt...")
    ret, out, err = run(cmd, show_progress=True, duration=duration)
    
    if ret == 130:  # Interrupted
        print("\nVerarbeitung unterbrochen")
        # Clean up partial output file
        try:
            if out_path.exists():
                out_path.unlink()
                print(f"Partielle Datei entfernt: {out_path.name}")
        except Exception as cleanup_e:
            print(f"Warnung: Konnte partielle Datei nicht entfernen: {cleanup_e}")
        return 'interrupted', auto_yes
    elif ret != 0:
        print(f"Fehler bei FFmpeg (Exit-Code: {ret})")
        if err:
            print(f"Fehlerdetails: {err}")
        # Clean up failed output file
        try:
            if out_path.exists():
                out_path.unlink()
                print(f"Fehlgeschlagene Datei entfernt: {out_path.name}")
        except Exception as cleanup_e:
            print(f"Warnung: Konnte fehlgeschlagene Datei nicht entfernen: {cleanup_e}")
        return 'error', auto_yes

    print("Verarbeitung abgeschlossen!")

    # Handle temporary file cleanup and renaming
    if temp_output:
        final_path = (dst_dir / (src.stem + '.mp4')).resolve()
        handle_temp_file_cleanup(out_path, final_path, src, delete_original)
    elif delete_original and src.resolve() != out_path:
        # Delete original only if output is different file
        try:
            src.unlink()
            print(f'Originaldatei gelöscht: {src.name}')
        except Exception as e:
            print(f'Fehler beim Löschen der Originaldatei: {e}')

    # Update cache if provided
    if cache_path:
        update_cache_entry(cache_path, str(src))

    return 'processed', auto_yes