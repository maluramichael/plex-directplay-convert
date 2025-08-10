"""
Integration tests for complete workflows
"""

import pytest
import csv
from pathlib import Path


class TestIntegrationWorkflows:
    """Integration tests for complete converter workflows"""
    
    def test_complete_two_step_workflow(self, video_files_dir, temp_dirs, run_converter):
        """Test the complete gather -> process workflow"""
        cache_file = temp_dirs['cache'] / 'workflow_cache.csv'
        
        # Step 1: Gather files into cache
        gather_result = run_converter([
            str(video_files_dir),
            '--gather', str(cache_file)
        ])
        
        assert gather_result.returncode == 0
        assert cache_file.exists()
        assert 'Analyse gespeichert in' in gather_result.stdout
        
        # Verify cache was created with content
        with open(cache_file, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            cache_entries = list(reader)
        
        # Should have entries for all video files
        video_file_count = len(list(video_files_dir.glob('*.mp4'))) + len(list(video_files_dir.glob('*.mkv'))) + len(list(video_files_dir.glob('*.avi')))
        assert len(cache_entries) == video_file_count
        
        # Step 2: Process from cache with limit
        process_result = run_converter([
            str(video_files_dir),
            '--use-cache', str(cache_file),
            '--limit', '2',
            '--out', str(temp_dirs['output']),
            '--dry-run'
        ])
        
        assert process_result.returncode == 0
        assert 'Cache-Datei geladen' in process_result.stdout
        assert 'Beschränke Verarbeitung auf' in process_result.stdout
    
    def test_incremental_processing_simulation(self, video_files_dir, temp_dirs, run_converter):
        """Test incremental processing workflow (simulated)"""
        cache_file = temp_dirs['cache'] / 'incremental_cache.csv'
        
        # Create cache
        run_converter([
            str(video_files_dir),
            '--gather', str(cache_file)
        ])
        
        # First batch - limit 1
        batch1_result = run_converter([
            str(video_files_dir),
            '--use-cache', str(cache_file),
            '--limit', '1',
            '--dry-run'
        ])
        
        assert batch1_result.returncode == 0
        
        # Second batch - different limit
        batch2_result = run_converter([
            str(video_files_dir),
            '--use-cache', str(cache_file),
            '--limit', '2',
            '--dry-run'
        ])
        
        assert batch2_result.returncode == 0
    
    def test_action_filtering_workflow(self, video_files_dir, temp_dirs, run_converter):
        """Test workflow with action filtering"""
        cache_file = temp_dirs['cache'] / 'action_filter_cache.csv'
        
        # Create cache
        run_converter([
            str(video_files_dir),
            '--gather', str(cache_file)
        ])
        
        # Test different action filters
        action_filters = ['container_remux', 'remux_audio', 'transcode_video', 'transcode_all']
        
        for action_filter in action_filters:
            result = run_converter([
                str(video_files_dir),
                '--use-cache', str(cache_file),
                '--action-filter', action_filter,
                '--dry-run'
            ])
            
            # Should succeed even if no files match the filter
            assert result.returncode == 0
    
    def test_language_processing_workflow(self, video_files_dir, temp_dirs, run_converter):
        """Test workflow with language filtering and sorting"""
        cache_file = temp_dirs['cache'] / 'language_cache.csv'
        
        # Create cache
        run_converter([
            str(video_files_dir),
            '--gather', str(cache_file)
        ])
        
        # Process with language options
        result = run_converter([
            str(video_files_dir),
            '--use-cache', str(cache_file),
            '--keep-languages', 'de,en',
            '--sort-languages', 'de,en',
            '--dry-run'
        ])
        
        assert result.returncode == 0
    
    def test_directory_auto_cache_workflow(self, video_files_dir, run_converter):
        """Test automatic cache creation for directory processing"""
        result = run_converter([
            str(video_files_dir),
            '--limit', '3',
            '--dry-run'
        ])
        
        assert result.returncode == 0
        assert 'Erstelle temporären Cache' in result.stdout
        
        # Check that auto-cache was created
        auto_cache = video_files_dir / '.ffmpeg_converter_cache.csv'
        assert auto_cache.exists()
    
    def test_comprehensive_options_workflow(self, video_files_dir, temp_dirs, run_converter):
        """Test workflow with multiple options combined"""
        cache_file = temp_dirs['cache'] / 'comprehensive_cache.csv'
        
        # Create cache
        run_converter([
            str(video_files_dir),
            '--gather', str(cache_file)
        ])
        
        # Process with many options
        result = run_converter([
            str(video_files_dir),
            '--use-cache', str(cache_file),
            '--limit', '2',
            '--keep-languages', 'de,en',
            '--sort-languages', 'en,de',
            '--crf', '24',
            '--preset', 'fast',
            '--out', str(temp_dirs['output']),
            '--dry-run'
        ])
        
        assert result.returncode == 0
    
    def test_error_handling_workflow(self, video_files_dir, temp_dirs, run_converter):
        """Test error handling in workflows"""
        # Test with nonexistent directory
        result1 = run_converter([
            str(temp_dirs['temp'] / 'nonexistent'),
            '--gather', str(temp_dirs['cache'] / 'error_test.csv')
        ], expect_error=True)
        
        assert result1.returncode != 0
        assert 'existiert nicht' in result1.stderr
        
        # Test with invalid action filter
        result2 = run_converter([
            str(video_files_dir),
            '--action-filter', 'invalid_action'
        ], expect_error=True)
        
        assert result2.returncode != 0
        assert 'Ungültiger action-filter' in result2.stderr
        
        # Test with invalid CRF value
        result3 = run_converter([
            str(video_files_dir),
            '--crf', '100',
            '--dry-run'
        ], expect_error=True)
        
        assert result3.returncode != 0
        assert 'CRF muss zwischen 0 und 51 liegen' in result3.stderr
    
    @pytest.mark.parametrize("container_format", ["mp4", "mkv"])
    def test_mixed_container_processing(self, video_files_dir, temp_dirs, run_converter, container_format):
        """Test processing files with different container formats"""
        cache_file = temp_dirs['cache'] / f'mixed_{container_format}_cache.csv'
        
        # Process workflow with existing pre-generated files
        gather_result = run_converter([
            str(video_files_dir),
            '--gather', str(cache_file)
        ])
        
        assert gather_result.returncode == 0
        
        process_result = run_converter([
            str(video_files_dir),
            '--use-cache', str(cache_file),
            '--dry-run'
        ])
        
        assert process_result.returncode == 0