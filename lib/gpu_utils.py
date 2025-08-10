"""
GPU acceleration detection and utilities
"""

import sys
import subprocess

def detect_gpu_acceleration():
    """Detect available GPU acceleration options"""
    gpu_info = {
        'available': False,
        'encoder': None,
        'decoder': None,
        'platform': None
    }
    
    try:
        # Check ffmpeg encoders
        p = subprocess.run(['ffmpeg', '-encoders'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if p.returncode != 0:
            return gpu_info
        out = p.stdout
            
        encoders_output = out.lower()
        
        # Check for Metal (macOS)
        if 'videotoolbox' in encoders_output and sys.platform == 'darwin':
            gpu_info.update({
                'available': True,
                'encoder': 'h264_videotoolbox',
                'decoder': 'h264',  # Use software decoder, hardware encoder
                'platform': 'metal'
            })
            return gpu_info
        
        # Check for NVIDIA (Windows/Linux)
        if 'h264_nvenc' in encoders_output:
            gpu_info.update({
                'available': True,
                'encoder': 'h264_nvenc',
                'decoder': 'h264_cuvid',  # Hardware decoder if available
                'platform': 'nvidia'
            })
            return gpu_info
            
        # Check for Intel QuickSync (Windows/Linux)
        if 'h264_qsv' in encoders_output:
            gpu_info.update({
                'available': True,
                'encoder': 'h264_qsv',
                'decoder': 'h264_qsv',
                'platform': 'intel'
            })
            return gpu_info
            
    except Exception as e:
        print(f"GPU-Erkennung fehlgeschlagen: {e}")
    
    return gpu_info

def get_gpu_encoder_params(gpu_info, crf, preset):
    """Get GPU-specific encoding parameters"""
    if not gpu_info['available']:
        return []
    
    params = []
    
    if gpu_info['platform'] == 'metal':
        # VideoToolbox (Mac Metal)
        # Convert CRF to quality (0-100, higher = better)
        quality = max(0, min(100, 100 - (crf * 2)))
        params.extend([
            '-c:v', 'h264_videotoolbox',
            '-q:v', str(quality),
            '-realtime', '0'  # Allow slower encoding for better quality
        ])
        
    elif gpu_info['platform'] == 'nvidia':
        # NVIDIA NVENC
        # Convert preset to NVENC preset
        nvenc_presets = {
            'ultrafast': 'p1', 'superfast': 'p2', 'veryfast': 'p3',
            'faster': 'p4', 'fast': 'p5', 'medium': 'p6',
            'slow': 'p7', 'slower': 'p7', 'veryslow': 'p7'
        }
        nvenc_preset = nvenc_presets.get(preset, 'p6')
        
        params.extend([
            '-c:v', 'h264_nvenc',
            '-preset', nvenc_preset,
            '-cq', str(crf),
            '-rc', 'constqp'
        ])
        
    elif gpu_info['platform'] == 'intel':
        # Intel QuickSync
        params.extend([
            '-c:v', 'h264_qsv',
            '-preset', preset,
            '-global_quality', str(crf)
        ])
    
    return params