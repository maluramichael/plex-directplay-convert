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

    out_name = src.stem + '.mp4.convert'
    out_path = (dst_dir / out_name).resolve()
    final_path = (dst_dir / (src.stem + '.mp4')).resolve()
    
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

    # Check if final output file already exists
    if final_path.exists():
        print(f"Output-Datei existiert bereits: {final_path}")
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
        # Clean up partial .convert file
        try:
            if out_path.exists():
                out_path.unlink()
                print(f"Partielle .convert Datei entfernt: {out_path.name}")
        except Exception as cleanup_e:
            print(f"Warnung: Konnte partielle .convert Datei nicht entfernen: {cleanup_e}")
        return 'interrupted', auto_yes
    elif ret != 0:
        print(f"Fehler bei FFmpeg (Exit-Code: {ret})")
        if err:
            print(f"Fehlerdetails: {err}")
        # Clean up failed .convert file
        try:
            if out_path.exists():
                out_path.unlink()
                print(f"Fehlgeschlagene .convert Datei entfernt: {out_path.name}")
        except Exception as cleanup_e:
            print(f"Warnung: Konnte fehlgeschlagene .convert Datei nicht entfernen: {cleanup_e}")
        return 'error', auto_yes

    print("Verarbeitung abgeschlossen!")

    # Handle file renaming: remove original and rename .convert file
    try:
        # Remove original file
        src.unlink()
        print(f'Originaldatei gelöscht: {src.name}')
        
        # Rename .convert file to final name
        out_path.rename(final_path)
        print(f'Datei umbenannt: {out_path.name} -> {final_path.name}')
    except Exception as e:
        print(f'Fehler beim Umbenennen der Dateien: {e}')
        # If rename failed, try to restore original state
        if not src.exists() and out_path.exists():
            try:
                out_path.unlink()
                print(f'Temporäre Datei entfernt: {out_path.name}')
            except:
                pass
        return 'error', auto_yes

    # Update cache if provided
    if cache_path:
        update_cache_entry(cache_path, str(src))

    return 'processed', auto_yes