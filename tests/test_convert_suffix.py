"""
Tests for .convert suffix functionality
"""

import pytest
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

from lib.processor import process_file
from lib.language_utils import Action


@pytest.fixture
def sample_video_info():
    """Sample video info for testing"""
    return {
        'has_video': True,
        'has_audio': True,
        'container': 'mkv',
        'video_codec': 'hevc',
        'audio_codec': 'aac',
        'audio_channels': [6],
        'audio_codecs': ['aac'],
        'audio_languages': ['de'],
        'is_hdr': False,
        'video_streams': [{'codec_name': 'hevc'}],
        'audio_streams': [{'codec_name': 'aac', 'channels': 6}]
    }


class TestConvertSuffix:
    """Test the .convert suffix functionality during file processing"""
    
    def test_convert_suffix_output_path(self, temp_dirs, sample_video_info):
        """Test that output file uses .convert suffix during processing"""
        src_file = temp_dirs['temp'] / 'test_video.mkv'
        src_file.touch()  # Create empty test file
        dst_dir = temp_dirs['output']
        
        with patch('lib.processor.discover_media') as mock_discover, \
             patch('lib.processor.get_duration') as mock_duration, \
             patch('lib.processor.needs_processing') as mock_needs, \
             patch('lib.processor.build_ffmpeg_cmd') as mock_build_cmd, \
             patch('lib.processor.run') as mock_run:
            
            # Setup mocks
            mock_discover.return_value = sample_video_info
            mock_duration.return_value = 120.0
            mock_needs.return_value = Action.TRANCODE_ALL
            mock_build_cmd.return_value = ['ffmpeg', '-i', 'input.mkv', 'output.mp4.convert']
            mock_run.return_value = (0, '', '')  # Success
            
            # Create the expected convert file that ffmpeg would create
            convert_file = dst_dir / 'convert.test_video.mp4'
            dst_dir.mkdir(parents=True, exist_ok=True)
            convert_file.touch()
            
            result, _ = process_file(src_file, dst_dir, 22, 'medium', False, False)
            
            # Verify ffmpeg was called with convert prefix
            mock_build_cmd.assert_called_once()
            call_args = mock_build_cmd.call_args
            output_path = call_args[0][1]  # Second argument is output path
            assert output_path.name.startswith('convert.')
            
            assert result == 'processed'
    
    def test_successful_conversion_flow(self, temp_dirs, sample_video_info):
        """Test complete successful conversion with file renaming"""
        src_file = temp_dirs['temp'] / 'test_video_success.mkv'
        src_file.write_text('original content')  # Create file with content
        dst_dir = temp_dirs['output']
        dst_dir.mkdir(parents=True, exist_ok=True)
        
        convert_file = dst_dir / 'convert.test_video_success.mp4'
        
        def mock_run_side_effect(*args, **kwargs):
            # Simulate ffmpeg creating the convert file during conversion
            convert_file.write_text('converted content')
            return (0, '', '')  # Success
        
        with patch('lib.processor.discover_media') as mock_discover, \
             patch('lib.processor.get_duration') as mock_duration, \
             patch('lib.processor.needs_processing') as mock_needs, \
             patch('lib.processor.build_ffmpeg_cmd') as mock_build_cmd, \
             patch('lib.processor.run') as mock_run:
            
            # Setup mocks
            mock_discover.return_value = sample_video_info
            mock_duration.return_value = 120.0
            mock_needs.return_value = Action.TRANCODE_ALL
            mock_build_cmd.return_value = ['ffmpeg', '-i', 'input.mkv', 'output.mp4.convert']
            mock_run.side_effect = mock_run_side_effect
            
            result, _ = process_file(src_file, dst_dir, 22, 'medium', False, False)
            
            # Verify results
            assert result == 'processed'
            
            # Original file should be deleted
            assert not src_file.exists()
            
            # convert file should be renamed to final name
            final_file = dst_dir / 'test_video_success.mp4'
            assert final_file.exists()
            assert not convert_file.exists()
            assert final_file.read_text() == 'converted content'
    
    def test_conversion_error_cleanup(self, temp_dirs, sample_video_info):
        """Test that convert file is cleaned up on conversion error"""
        src_file = temp_dirs['temp'] / 'test_video_error.mkv'
        src_file.write_text('original content')
        dst_dir = temp_dirs['output']
        dst_dir.mkdir(parents=True, exist_ok=True)
        
        convert_file = dst_dir / 'convert.test_video_error.mp4'
        
        def mock_run_side_effect(*args, **kwargs):
            # Simulate ffmpeg creating partial file before failing
            convert_file.write_text('partial content')
            return (1, '', 'conversion failed')  # Error
        
        with patch('lib.processor.discover_media') as mock_discover, \
             patch('lib.processor.get_duration') as mock_duration, \
             patch('lib.processor.needs_processing') as mock_needs, \
             patch('lib.processor.build_ffmpeg_cmd') as mock_build_cmd, \
             patch('lib.processor.run') as mock_run:
            
            # Setup mocks
            mock_discover.return_value = sample_video_info
            mock_duration.return_value = 120.0
            mock_needs.return_value = Action.TRANCODE_ALL
            mock_build_cmd.return_value = ['ffmpeg', '-i', 'input.mkv', 'output.mp4.convert']
            mock_run.side_effect = mock_run_side_effect
            
            result, _ = process_file(src_file, dst_dir, 22, 'medium', False, False)
            
            # Verify results
            assert result == 'error'
            
            # Original file should still exist
            assert src_file.exists()
            assert src_file.read_text() == 'original content'
            
            # convert file should be cleaned up
            assert not convert_file.exists()
            
            # Final file should not exist
            final_file = dst_dir / 'test_video_error.mp4'
            assert not final_file.exists()
    
    def test_conversion_interrupted_cleanup(self, temp_dirs, sample_video_info):
        """Test that convert file is cleaned up on interruption"""
        src_file = temp_dirs['temp'] / 'test_video_interrupt.mkv'
        src_file.write_text('original content')
        dst_dir = temp_dirs['output']
        dst_dir.mkdir(parents=True, exist_ok=True)
        
        convert_file = dst_dir / 'convert.test_video_interrupt.mp4'
        
        def mock_run_side_effect(*args, **kwargs):
            # Simulate ffmpeg creating partial file before interruption
            convert_file.write_text('partial content')
            return (130, '', '')  # Interrupted (SIGINT)
        
        with patch('lib.processor.discover_media') as mock_discover, \
             patch('lib.processor.get_duration') as mock_duration, \
             patch('lib.processor.needs_processing') as mock_needs, \
             patch('lib.processor.build_ffmpeg_cmd') as mock_build_cmd, \
             patch('lib.processor.run') as mock_run:
            
            # Setup mocks
            mock_discover.return_value = sample_video_info
            mock_duration.return_value = 120.0
            mock_needs.return_value = Action.TRANCODE_ALL
            mock_build_cmd.return_value = ['ffmpeg', '-i', 'input.mkv', 'output.mp4.convert']
            mock_run.side_effect = mock_run_side_effect
            
            result, _ = process_file(src_file, dst_dir, 22, 'medium', False, False)
            
            # Verify results
            assert result == 'interrupted'
            
            # Original file should still exist
            assert src_file.exists()
            assert src_file.read_text() == 'original content'
            
            # convert file should be cleaned up
            assert not convert_file.exists()
            
            # Final file should not exist
            final_file = dst_dir / 'test_video_interrupt.mp4'
            assert not final_file.exists()
    
    def test_cache_update_functionality(self, temp_dirs, sample_video_info):
        """Test that cache is updated when provided"""
        src_file = temp_dirs['temp'] / 'test_video_cache.mkv'
        src_file.write_text('original content')
        dst_dir = temp_dirs['output']
        dst_dir.mkdir(parents=True, exist_ok=True)
        cache_file = temp_dirs['cache'] / 'test_cache.csv'
        
        convert_file = dst_dir / 'convert.test_video_cache.mp4'
        
        def mock_run_side_effect(*args, **kwargs):
            # Simulate ffmpeg creating the convert file
            convert_file.write_text('converted content')
            return (0, '', '')  # Success
        
        with patch('lib.processor.discover_media') as mock_discover, \
             patch('lib.processor.get_duration') as mock_duration, \
             patch('lib.processor.needs_processing') as mock_needs, \
             patch('lib.processor.build_ffmpeg_cmd') as mock_build_cmd, \
             patch('lib.processor.run') as mock_run, \
             patch('lib.processor.update_cache_entry') as mock_update_cache:
            
            # Setup mocks
            mock_discover.return_value = sample_video_info
            mock_duration.return_value = 120.0
            mock_needs.return_value = Action.TRANCODE_ALL
            mock_build_cmd.return_value = ['ffmpeg', '-i', 'input.mkv', 'output.mp4.convert']
            mock_run.side_effect = mock_run_side_effect
            
            # Test with cache provided
            result, _ = process_file(src_file, dst_dir, 22, 'medium', False, False, 
                                   cache_path=cache_file)
            
            # Verify results
            assert result == 'processed'
            
            # Cache should be updated
            mock_update_cache.assert_called_once_with(cache_file, str(src_file))
    
    def test_existing_final_file_skip(self, temp_dirs, sample_video_info):
        """Test that processing is skipped if final output file already exists"""
        src_file = temp_dirs['temp'] / 'test_video.mkv'
        src_file.write_text('original content')
        dst_dir = temp_dirs['output']
        dst_dir.mkdir(parents=True, exist_ok=True)
        
        # Create existing final file
        final_file = dst_dir / 'test_video.mp4'
        final_file.write_text('existing content')
        
        with patch('lib.processor.discover_media') as mock_discover, \
             patch('lib.processor.get_duration') as mock_duration, \
             patch('lib.processor.needs_processing') as mock_needs:
            
            # Setup mocks
            mock_discover.return_value = sample_video_info
            mock_duration.return_value = 120.0
            mock_needs.return_value = Action.TRANCODE_ALL
            
            result, _ = process_file(src_file, dst_dir, 22, 'medium', False, False)
            
            # Should skip due to existing file
            assert result == 'skipped'
            
            # Original file should still exist
            assert src_file.exists()
            
            # Final file should be unchanged
            assert final_file.exists()
            assert final_file.read_text() == 'existing content'