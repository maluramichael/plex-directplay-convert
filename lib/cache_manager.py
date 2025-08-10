"""
CSV cache management for video file processing
"""

import csv
from datetime import datetime
from pathlib import Path
from .file_utils import VIDEO_EXTS
from .media_analyzer import analyze_file_for_csv

def read_cache_csv(csv_path: Path):
    """Read cache CSV file and return list of file data"""
    if not csv_path.exists():
        raise FileNotFoundError(f"Cache-Datei nicht gefunden: {csv_path}")
    
    file_data_list = []
    with open(csv_path, 'r', newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            # Convert string bools and numbers back to proper types
            row['file_size_bytes'] = int(row['file_size_bytes']) if row['file_size_bytes'] else 0
            row['file_size_mb'] = float(row['file_size_mb']) if row['file_size_mb'] else 0.0
            row['is_hdr'] = row['is_hdr'].lower() == 'true'
            row['has_video'] = row['has_video'].lower() == 'true'
            row['has_audio'] = row['has_audio'].lower() == 'true'
            row['direct_play_compatible'] = row['direct_play_compatible'].lower() == 'true'
            row['processed'] = row.get('processed', 'false').lower() == 'true'
            file_data_list.append(row)
    
    return file_data_list

def update_cache_entry(csv_path: Path, file_path: str, processed: bool = True, processing_date: str = None):
    """Update a single entry in the cache file to mark it as processed"""
    if not csv_path.exists():
        return
    
    # Read all entries
    file_data_list = read_cache_csv(csv_path)
    
    # Update the specific entry
    updated = False
    for entry in file_data_list:
        if entry['file_path'] == file_path:
            entry['processed'] = processed
            entry['processing_date'] = processing_date or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            updated = True
            break
    
    if updated:
        # Write back to file
        write_analysis_csv(file_data_list, csv_path)

def gather_files_to_cache(root: Path, cache_path: Path):
    """Gather all video files from root directory and create/update cache file"""
    print(f"Sammele Dateien und erstelle Cache: {cache_path}")
    
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
        # Directory - collect all video files with better glob filtering
        video_files = []
        for ext in VIDEO_EXTS:
            video_files.extend(root.rglob(f'*{ext}'))
            video_files.extend(root.rglob(f'*{ext.upper()}'))
        
        # Remove duplicates and filter for actual files
        video_files = list(set([p for p in video_files if p.is_file()]))
        total_files = len(video_files)
        print(f"Gefunden: {total_files} Videodateien")
        
        for i, p in enumerate(video_files, 1):
            print(f"Analysiere ({i}/{total_files}): {p.name}")
            file_data = analyze_file_for_csv(p)
            file_data_list.append(file_data)
    
    # Write cache file
    write_analysis_csv(file_data_list, cache_path)
    return file_data_list

def write_analysis_csv(file_data_list, csv_path: Path):
    """Write analysis results to CSV file"""
    if not file_data_list:
        print("Keine Dateien zu analysieren gefunden.")
        return
    
    fieldnames = [
        'file_path', 'file_name', 'file_size_bytes', 'file_size_mb',
        'container', 'video_codec', 'is_hdr', 'audio_codecs', 'audio_channels',
        'audio_languages', 'has_video', 'has_audio', 'direct_play_compatible', 'action_needed',
        'analysis_date', 'processed', 'processing_date'
    ]
    
    with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(file_data_list)
    
    print(f"Analyse gespeichert in: {csv_path}")
    print(f"Analysierte Dateien: {len(file_data_list)}")
    compatible_count = sum(1 for data in file_data_list if data.get('direct_play_compatible') == 'True')
    print(f"Direct Play kompatibel: {compatible_count}/{len(file_data_list)} ({compatible_count/len(file_data_list)*100:.1f}%)")