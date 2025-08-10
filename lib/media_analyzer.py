"""
Media file analysis and compatibility checking
"""

from pathlib import Path
from .ffmpeg_runner import ffprobe_streams
from .language_utils import normalize_language, Action

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
    """Analyze media file and return detailed information"""
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

def is_direct_play_compatible(info):
    """Check if file is already Direct Play compatible for Apple TV 4K"""
    container_ok = info['container'] == 'mp4'
    video_ok = (info['video_codec'] or '').lower() in {'h264'} and not info.get('is_hdr', False)
    audio_ok = info['has_audio'] and info['audio_codecs'] and all(c in {'aac'} for c in info['audio_codecs']) and all(ch == 2 for ch in info['audio_channels'])
    
    return container_ok and video_ok and audio_ok

def analyze_file_for_csv(src: Path):
    """Analyze a single file and return data for CSV export"""
    from datetime import datetime
    from .file_utils import format_file_size
    
    try:
        info = discover_media(src)
        action_needed = needs_processing(info, 'mp4')
        
        # Create action description
        action_descriptions = {
            Action.SKIP: "Already compatible, skip processing",
            Action.CONTAINER_REMUX: "Container remux to MP4",
            Action.REMUX_AUDIO: "Audio remux to stereo AAC",
            Action.TRANCODE_VIDEO: "Video transcode to H.264 SDR", 
            Action.TRANCODE_ALL: "Full transcode (video + audio)"
        }
        
        file_stats = src.stat()
        file_size_bytes = file_stats.st_size
        
        file_data = {
            'file_path': str(src),
            'file_name': src.name,
            'file_size_bytes': file_size_bytes,
            'file_size_mb': round(file_size_bytes / (1024 * 1024), 2),
            'container': info['container'].upper(),
            'video_codec': info['video_codec'] or 'None',
            'is_hdr': 'True' if info.get('is_hdr', False) else 'False',
            'audio_codecs': ', '.join(info['audio_codecs']) if info['audio_codecs'] else 'None',
            'audio_channels': ', '.join(map(str, info['audio_channels'])) if info['audio_channels'] else 'None',
            'audio_languages': ', '.join(info['audio_languages']) if info['audio_languages'] else 'unknown',
            'has_video': 'True' if info['has_video'] else 'False',
            'has_audio': 'True' if info['has_audio'] else 'False',
            'direct_play_compatible': 'True' if is_direct_play_compatible(info) else 'False',
            'action_needed': action_descriptions.get(action_needed, str(action_needed)),
            'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'processed': 'False',
            'processing_date': ''
        }
        
        return file_data
        
    except Exception as e:
        # Return error entry
        file_stats = src.stat()
        return {
            'file_path': str(src),
            'file_name': src.name,
            'file_size_bytes': file_stats.st_size,
            'file_size_mb': round(file_stats.st_size / (1024 * 1024), 2),
            'container': 'ERROR',
            'video_codec': f'Analysis failed: {str(e)}',
            'is_hdr': 'False',
            'audio_codecs': 'ERROR',
            'audio_channels': 'ERROR', 
            'audio_languages': 'unknown',
            'has_video': 'Unknown',
            'has_audio': 'Unknown',
            'direct_play_compatible': 'False',
            'action_needed': 'Analysis failed',
            'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'processed': 'False',
            'processing_date': ''
        }