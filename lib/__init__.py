"""
FFmpeg Converter library modules

Modular components for video file conversion and analysis.
"""

# Import all public interfaces for easy access
from .media_analyzer import discover_media, needs_processing, is_direct_play_compatible
from .language_utils import Action, normalize_language, filter_and_sort_streams
from .ffmpeg_runner import run, run_simple, ffprobe_streams, get_duration
from .ffmpeg_builder import build_ffmpeg_cmd
from .gpu_utils import detect_gpu_acceleration, get_gpu_encoder_params
from .cache_manager import read_cache_csv, update_cache_entry, gather_files_to_cache
from .processor import process_file
from .file_utils import VIDEO_EXTS, format_file_size, display_file_info

__all__ = [
    'discover_media', 'needs_processing', 'is_direct_play_compatible',
    'Action', 'normalize_language', 'filter_and_sort_streams',
    'run', 'run_simple', 'ffprobe_streams', 'get_duration',
    'build_ffmpeg_cmd',
    'detect_gpu_acceleration', 'get_gpu_encoder_params',
    'read_cache_csv', 'update_cache_entry', 'gather_files_to_cache',
    'process_file',
    'VIDEO_EXTS', 'format_file_size', 'display_file_info'
]