"""
Test action detection for different file types
"""

import pytest
from lib import discover_media, needs_processing, is_direct_play_compatible, Action, ffprobe_streams


class TestActionDetection:
    """Test correct action detection for various file configurations"""
    
    def test_skip_action_compatible_file(self, sample_files):
        """Test SKIP action for already compatible files"""
        info = discover_media(sample_files['compatible_mp4'])
        action = needs_processing(info, 'mp4')
        
        assert action == Action.SKIP
    
    def test_container_remux_action(self, sample_files):
        """Test CONTAINER_REMUX action for MKV with compatible codecs"""
        info = discover_media(sample_files['remux_mkv'])
        action = needs_processing(info, 'mp4')
        
        assert action == Action.CONTAINER_REMUX
    
    def test_audio_remux_action(self, sample_files):
        """Test REMUX_AUDIO action for incompatible audio"""
        info = discover_media(sample_files['audio_transcode'])
        action = needs_processing(info, 'mp4')
        
        assert action == Action.REMUX_AUDIO
    
    def test_video_transcode_action(self, sample_files):
        """Test TRANSCODE_VIDEO action for incompatible video"""
        info = discover_media(sample_files['video_transcode'])
        action = needs_processing(info, 'mp4')
        
        assert action == Action.TRANCODE_VIDEO
    
    def test_full_transcode_action(self, sample_files):
        """Test TRANSCODE_ALL action for incompatible video and audio"""
        info = discover_media(sample_files['full_transcode'])
        action = needs_processing(info, 'mp4')
        
        assert action == Action.TRANCODE_ALL
    
    @pytest.mark.parametrize("file_key,expected_action", [
        ('compatible_mp4', Action.SKIP),
        ('remux_mkv', Action.CONTAINER_REMUX),
        ('audio_transcode', Action.REMUX_AUDIO),
        ('video_transcode', Action.TRANCODE_VIDEO),
        ('full_transcode', Action.TRANCODE_ALL),
    ])
    def test_action_detection_parametrized(self, sample_files, file_key, expected_action):
        """Parametrized test for all action types"""
        info = discover_media(sample_files[file_key])
        action = needs_processing(info, 'mp4')
        
        assert action == expected_action
    
    def test_direct_play_compatibility_detection(self, sample_files):
        """Test direct play compatibility detection"""
        # Compatible file
        compatible_info = discover_media(sample_files['compatible_mp4'])
        assert is_direct_play_compatible(compatible_info)
        
        # Incompatible files
        for file_key in ['remux_mkv', 'audio_transcode', 'video_transcode', 'full_transcode']:
            incompatible_info = discover_media(sample_files[file_key])
            assert not is_direct_play_compatible(incompatible_info), f"{file_key} should not be compatible"
    
    def test_hdr_content_metadata_present(self, sample_files):
        """Test that HDR content has HDR-related metadata"""
        info = discover_media(sample_files['hdr_content'])
        
        # Get raw stream data to check for HDR metadata
        streams = ffprobe_streams(sample_files['hdr_content'])
        video_stream = next((s for s in streams if s.get('codec_type') == 'video'), None)
        
        assert video_stream is not None, "Should have video stream"
        
        # Check if we have any HDR-related color metadata
        color_space = video_stream.get('color_space', '')
        color_primaries = video_stream.get('color_primaries', '')
        color_trc = video_stream.get('color_trc', '')
        
        # We should have at least some HDR-related metadata from our synthetic file
        has_hdr_metadata = ('bt2020' in color_space or 'bt2020' in color_primaries or 
                           'smpte2084' in color_trc)
        
        assert has_hdr_metadata, f"Should have HDR metadata. Got: color_space={color_space}, color_primaries={color_primaries}, color_trc={color_trc}"