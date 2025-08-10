"""
FFmpeg command building for video/audio processing
"""

from pathlib import Path
from .language_utils import Action, filter_and_sort_streams
from .gpu_utils import get_gpu_encoder_params

def build_ffmpeg_cmd(inp: Path, out: Path, mode: Action, crf: int, preset: str, is_hdr: bool = False, 
                     info: dict = None, keep_languages: list = None, sort_languages: list = None, 
                     gpu_info: dict = None, use_gpu: bool = False):
    """Build FFmpeg command based on processing mode and options"""
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