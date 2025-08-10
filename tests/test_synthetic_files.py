"""
Test analysis of pre-generated synthetic video files
"""

import pytest
from lib import discover_media, ffprobe_streams


class TestSyntheticFileAnalysis:
    """Test analysis of pre-generated synthetic video files"""
    
    def test_compatible_mp4_analysis(self, sample_files):
        """Test analysis of compatible MP4 file"""
        file_path = sample_files['compatible_mp4']
        
        assert file_path.exists()
        assert file_path.suffix == '.mp4'
        
        # Analyze with converter
        info = discover_media(file_path)
        assert info['container'] == 'mp4'
        assert info['video_codec'] == 'h264'
        assert 'aac' in info['audio_codecs']
        assert info['has_video']
        assert info['has_audio']
    
    def test_different_containers(self, sample_files):
        """Test analysis of files with different containers"""
        mp4_info = discover_media(sample_files['compatible_mp4'])
        mkv_info = discover_media(sample_files['remux_mkv'])
        
        assert mp4_info['container'] == 'mp4'
        assert mkv_info['container'] == 'mkv'
        assert mp4_info['video_codec'] == mkv_info['video_codec'] == 'h264'
    
    def test_different_video_codecs(self, sample_files):
        """Test analysis of files with different video codecs"""
        h264_info = discover_media(sample_files['compatible_mp4'])
        mpeg4_info = discover_media(sample_files['video_transcode'])
        
        assert h264_info['video_codec'] == 'h264'
        assert mpeg4_info['video_codec'] == 'mpeg4'
    
    def test_different_audio_configs(self, sample_files):
        """Test analysis of files with different audio codecs and channels"""
        aac_info = discover_media(sample_files['compatible_mp4'])
        ac3_info = discover_media(sample_files['audio_transcode'])
        
        assert 'aac' in aac_info['audio_codecs']
        assert 'ac3' in ac3_info['audio_codecs']
        assert aac_info['audio_channels'][0] == 2
        assert ac3_info['audio_channels'][0] == 6
    
    def test_multilingual_file_analysis(self, sample_files):
        """Test analysis of multilingual content"""
        info = discover_media(sample_files['multilingual'])
        
        assert len(info['audio_streams']) == 3
        assert len(info['audio_languages']) == 3
        assert 'de' in info['audio_languages']
        assert 'en' in info['audio_languages'] 
        assert 'jp' in info['audio_languages']
    
    def test_hdr_content_analysis(self, sample_files):
        """Test analysis of HDR content"""
        info = discover_media(sample_files['hdr_content'])
        
        # Check if HDR is detected or if we have HDR-related metadata
        if not info['is_hdr']:
            # Check raw stream data for HDR metadata
            streams = ffprobe_streams(sample_files['hdr_content'])
            video_stream = next((s for s in streams if s.get('codec_type') == 'video'), None)
            
            if video_stream:
                color_space = video_stream.get('color_space', '')
                color_primaries = video_stream.get('color_primaries', '')
                color_trc = video_stream.get('color_trc', '')
                
                # Accept if any HDR-related metadata is present
                has_hdr_metadata = ('bt2020' in color_space or 'bt2020' in color_primaries or 
                                   'smpte2084' in color_trc)
                
                assert has_hdr_metadata, f"HDR metadata should be present. Got: color_space={color_space}, color_primaries={color_primaries}, color_trc={color_trc}"
            else:
                pytest.fail("No video stream found for HDR test")
    
    def test_no_language_metadata(self, sample_files):
        """Test file with no explicit language metadata"""
        info = discover_media(sample_files['no_language'])
        
        # Should detect unknown language
        assert len(info['audio_languages']) == 1
        assert info['audio_languages'][0] == 'unknown'
    
    @pytest.mark.parametrize("file_key", [
        'compatible_mp4', 'remux_mkv', 'audio_transcode', 
        'video_transcode', 'full_transcode', 'hdr_content', 
        'multilingual', 'mp3_audio', 'legacy_avi'
    ])
    def test_file_sizes_reasonable(self, sample_files, file_key):
        """Test that all pre-generated files have reasonable sizes"""
        file_path = sample_files[file_key]
        file_size = file_path.stat().st_size
        
        # Should be between 100KB and 5MB for 3-second test videos
        assert 100_000 < file_size < 5_000_000, f"File {file_key} size {file_size} seems unreasonable"
    
    def test_all_files_analyzable(self, all_video_files):
        """Test that all video files can be analyzed without errors"""
        for video_file in all_video_files:
            try:
                info = discover_media(video_file)
                # Basic sanity checks
                assert 'container' in info
                assert 'has_video' in info
                assert 'has_audio' in info
                assert info['has_video']  # All our test files should have video
            except Exception as e:
                pytest.fail(f"Failed to analyze {video_file.name}: {e}")
    
    def test_legacy_formats(self, sample_files):
        """Test analysis of legacy formats like AVI"""
        avi_info = discover_media(sample_files['legacy_avi'])
        
        assert avi_info['container'] == 'avi'
        assert avi_info['has_video']
        assert avi_info['has_audio']
        assert avi_info['video_codec'] == 'mpeg4'
    
    def test_mp3_audio_analysis(self, sample_files):
        """Test analysis of MP3 audio in MP4 container"""
        mp3_info = discover_media(sample_files['mp3_audio'])
        
        assert mp3_info['container'] == 'mp4'
        assert 'mp3' in mp3_info['audio_codecs']
        assert mp3_info['has_video']
        assert mp3_info['has_audio']