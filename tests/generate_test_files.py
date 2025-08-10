#!/usr/bin/env python3
"""
Generate all synthetic test video files once using native FFmpeg commands.

This script creates all the video files needed for testing in tests/video_files/
Run this once before running tests.
"""

import subprocess
import sys
from pathlib import Path

def run_ffmpeg(cmd, description):
    """Run an ffmpeg command with error handling"""
    print(f"Creating: {description}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(f"  ✅ Success")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  ❌ Failed: {e.stderr}")
        return False

def check_ffmpeg_available():
    """Check if ffmpeg and ffprobe are available"""
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        subprocess.run(['ffprobe', '-version'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ ffmpeg and/or ffprobe not found in PATH")
        return False

def generate_test_files():
    """Generate all synthetic test video files"""
    
    if not check_ffmpeg_available():
        return False
    
    # Get the video files directory
    video_dir = Path(__file__).parent / 'video_files'
    video_dir.mkdir(exist_ok=True)
    
    print(f"Generating test files in: {video_dir}")
    print("=" * 50)
    
    # Common settings
    duration = 3  # seconds
    video_size = "640x360"  # smaller for faster generation
    
    test_files = [
        # 1. Compatible MP4 - H.264 + AAC Stereo
        {
            'name': 'compatible.mp4',
            'description': 'Compatible MP4 (H.264 + AAC Stereo)',
            'cmd': [
                'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
                '-f', 'lavfi', '-i', f'testsrc2=size={video_size}:duration={duration}:rate=24',
                '-f', 'lavfi', '-i', f'sine=frequency=440:duration={duration}',
                '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '28',
                '-c:a', 'aac', '-ac', '2', '-b:a', '128k',
                '-movflags', '+faststart',
                str(video_dir / 'compatible.mp4')
            ]
        },
        
        # 2. MKV Container Remux - H.264 + AAC but in MKV
        {
            'name': 'remux_mkv.mkv', 
            'description': 'MKV needing container remux (H.264 + AAC)',
            'cmd': [
                'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
                '-f', 'lavfi', '-i', f'testsrc2=size={video_size}:duration={duration}:rate=24',
                '-f', 'lavfi', '-i', f'sine=frequency=440:duration={duration}',
                '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '28',
                '-c:a', 'aac', '-ac', '2', '-b:a', '128k',
                str(video_dir / 'remux_mkv.mkv')
            ]
        },
        
        # 3. Audio Transcode - H.264 + AC3 6-channel
        {
            'name': 'audio_transcode.mp4',
            'description': 'Audio transcode needed (H.264 + AC3 6ch)',
            'cmd': [
                'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
                '-f', 'lavfi', '-i', f'testsrc2=size={video_size}:duration={duration}:rate=24',
                '-f', 'lavfi', '-i', f'sine=frequency=440:duration={duration}',
                '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '28',
                '-c:a', 'ac3', '-ac', '6', '-b:a', '384k',
                '-movflags', '+faststart',
                str(video_dir / 'audio_transcode.mp4')
            ]
        },
        
        # 4. Video Transcode - MPEG-4 + AAC
        {
            'name': 'video_transcode.mp4',
            'description': 'Video transcode needed (MPEG-4 + AAC)',
            'cmd': [
                'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
                '-f', 'lavfi', '-i', f'testsrc2=size={video_size}:duration={duration}:rate=24',
                '-f', 'lavfi', '-i', f'sine=frequency=440:duration={duration}',
                '-c:v', 'mpeg4', '-qscale:v', '8',
                '-c:a', 'aac', '-ac', '2', '-b:a', '128k',
                '-movflags', '+faststart',
                str(video_dir / 'video_transcode.mp4')
            ]
        },
        
        # 5. Full Transcode - MPEG-4 + AC3 in MKV
        {
            'name': 'full_transcode.mkv',
            'description': 'Full transcode needed (MPEG-4 + AC3 6ch in MKV)',
            'cmd': [
                'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
                '-f', 'lavfi', '-i', f'testsrc2=size={video_size}:duration={duration}:rate=24',
                '-f', 'lavfi', '-i', f'sine=frequency=440:duration={duration}',
                '-f', 'lavfi', '-i', f'sine=frequency=550:duration={duration}',
                '-map', '0:v', '-map', '1:a', '-map', '2:a',
                '-metadata:s:a:0', 'language=de',
                '-metadata:s:a:1', 'language=en', 
                '-c:v', 'mpeg4', '-qscale:v', '8',
                '-c:a', 'ac3', '-ac', '6', '-b:a', '384k',
                str(video_dir / 'full_transcode.mkv')
            ]
        },
        
        # 6. HDR Content - H.264 with HDR metadata
        {
            'name': 'hdr_content.mp4',
            'description': 'HDR content (H.264 + HDR color metadata)',
            'cmd': [
                'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
                '-f', 'lavfi', '-i', f'testsrc2=size={video_size}:duration={duration}:rate=24',
                '-f', 'lavfi', '-i', f'sine=frequency=440:duration={duration}',
                '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '28',
                '-color_primaries', 'bt2020',
                '-color_trc', 'smpte2084', 
                '-colorspace', 'bt2020nc',
                '-c:a', 'aac', '-ac', '2', '-b:a', '128k',
                '-movflags', '+faststart',
                str(video_dir / 'hdr_content.mp4')
            ]
        },
        
        # 7. Multilingual - H.264 + AAC with multiple languages (MKV for metadata)
        {
            'name': 'multilingual.mkv',
            'description': 'Multilingual content (German, English, Japanese)',
            'cmd': [
                'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
                '-f', 'lavfi', '-i', f'testsrc2=size={video_size}:duration={duration}:rate=24',
                '-f', 'lavfi', '-i', f'sine=frequency=440:duration={duration}',  # German
                '-f', 'lavfi', '-i', f'sine=frequency=550:duration={duration}',  # English
                '-f', 'lavfi', '-i', f'sine=frequency=660:duration={duration}',  # Japanese
                '-map', '0:v', '-map', '1:a', '-map', '2:a', '-map', '3:a',
                '-metadata:s:a:0', 'language=de',
                '-metadata:s:a:1', 'language=en',
                '-metadata:s:a:2', 'language=jp',
                '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '28',
                '-c:a', 'aac', '-ac', '2', '-b:a', '128k',
                str(video_dir / 'multilingual.mkv')
            ]
        },
        
        # 8. MP3 Audio Test - H.264 + MP3 (less common)
        {
            'name': 'mp3_audio.mp4',
            'description': 'MP3 audio test (H.264 + MP3)',
            'cmd': [
                'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
                '-f', 'lavfi', '-i', f'testsrc2=size={video_size}:duration={duration}:rate=24',
                '-f', 'lavfi', '-i', f'sine=frequency=440:duration={duration}',
                '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '28',
                '-c:a', 'mp3', '-b:a', '192k',
                '-movflags', '+faststart',
                str(video_dir / 'mp3_audio.mp4')
            ]
        },
        
        # 9. AVI Container - MPEG-4 + MP3 (old format)
        {
            'name': 'legacy_avi.avi',
            'description': 'Legacy AVI format (MPEG-4 + MP3)',
            'cmd': [
                'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
                '-f', 'lavfi', '-i', f'testsrc2=size={video_size}:duration={duration}:rate=24',
                '-f', 'lavfi', '-i', f'sine=frequency=440:duration={duration}',
                '-c:v', 'mpeg4', '-qscale:v', '8',
                '-c:a', 'mp3', '-b:a', '192k',
                str(video_dir / 'legacy_avi.avi')
            ]
        },
        
        # 10. No Language Metadata - for testing unknown language handling
        {
            'name': 'no_language.mp4',
            'description': 'No language metadata (should be detected as unknown)',
            'cmd': [
                'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
                '-f', 'lavfi', '-i', f'testsrc2=size={video_size}:duration={duration}:rate=24',
                '-f', 'lavfi', '-i', f'sine=frequency=440:duration={duration}',
                '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '28',
                '-c:a', 'aac', '-ac', '2', '-b:a', '128k',
                '-movflags', '+faststart',
                str(video_dir / 'no_language.mp4')
            ]
        }
    ]
    
    # Generate all files
    success_count = 0
    for file_spec in test_files:
        if run_ffmpeg(file_spec['cmd'], file_spec['description']):
            success_count += 1
    
    print("=" * 50)
    print(f"Generated {success_count}/{len(test_files)} test files successfully")
    
    # List generated files with sizes
    print(f"\nGenerated files in {video_dir}:")
    total_size = 0
    for file_path in video_dir.glob("*"):
        if file_path.is_file():
            size = file_path.stat().st_size
            size_mb = size / (1024 * 1024)
            total_size += size
            print(f"  {file_path.name}: {size_mb:.2f} MB")
    
    print(f"\nTotal size: {total_size / (1024 * 1024):.2f} MB")
    
    return success_count == len(test_files)

if __name__ == '__main__':
    print("🎬 FFmpeg Converter Test File Generator")
    print("=" * 50)
    
    success = generate_test_files()
    
    if success:
        print("\n✅ All test files generated successfully!")
        print("You can now run the test suite with: pytest")
    else:
        print("\n❌ Some files failed to generate")
        sys.exit(1)