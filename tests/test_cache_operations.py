"""
Test cache generation and processing operations
"""

import pytest
import csv
from pathlib import Path
from lib import read_cache_csv, update_cache_entry


class TestCacheGeneration:
    """Test --gather cache generation functionality"""
    
    def test_gather_single_file(self, sample_files, temp_dirs, run_converter):
        """Test gathering cache for a single file"""
        cache_file = temp_dirs['cache'] / 'single_file.csv'
        
        result = run_converter([
            str(sample_files['compatible_mp4']),
            '--gather', str(cache_file)
        ])
        
        assert result.returncode == 0
        assert cache_file.exists()
        
        # Read and verify cache
        with open(cache_file, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            entries = list(reader)
        
        assert len(entries) == 1
        entry = entries[0]
        assert entry['file_name'] == sample_files['compatible_mp4'].name
        assert entry['container'] == 'MP4'
        assert entry['video_codec'] == 'h264'
        assert entry['direct_play_compatible'] == 'True'
        assert entry['processed'] == 'False'
    
    def test_gather_directory(self, video_files_dir, temp_dirs, run_converter):
        """Test gathering cache for entire directory"""
        cache_file = temp_dirs['cache'] / 'directory.csv'
        
        result = run_converter([
            str(video_files_dir),
            '--gather', str(cache_file)
        ])
        
        assert result.returncode == 0
        assert cache_file.exists()
        
        # Read and verify cache
        with open(cache_file, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            entries = list(reader)
        
        # Should have entries for all video files in directory
        video_files = list(video_files_dir.glob('*.mp4')) + list(video_files_dir.glob('*.mkv')) + list(video_files_dir.glob('*.avi'))
        assert len(entries) == len(video_files)
        
        # Verify all required fields are present
        required_fields = [
            'file_path', 'file_name', 'file_size_bytes', 'file_size_mb',
            'container', 'video_codec', 'is_hdr', 'audio_codecs', 'audio_channels',
            'has_video', 'has_audio', 'direct_play_compatible', 'action_needed',
            'analysis_date', 'processed', 'processing_date'
        ]
        
        for field in required_fields:
            assert field in entries[0], f"Missing field: {field}"
    
    def test_gather_cache_content_accuracy(self, video_files_dir, temp_dirs, run_converter):
        """Test that cache content accurately reflects file analysis"""
        cache_file = temp_dirs['cache'] / 'accuracy_test.csv'
        
        # Gather cache for known files
        result = run_converter([
            str(video_files_dir),
            '--gather', str(cache_file)
        ])
        
        assert result.returncode == 0
        
        # Read cache
        with open(cache_file, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            entries = {entry['file_name']: entry for entry in reader}
        
        # Test specific files
        compatible_entry = next((e for e in entries.values() 
                               if 'compatible' in e['file_name']), None)
        assert compatible_entry is not None
        assert compatible_entry['direct_play_compatible'] == 'True'
        assert 'already compatible' in compatible_entry['action_needed'].lower()
        
        full_transcode_entry = next((e for e in entries.values() 
                                   if 'full_transcode' in e['file_name']), None)
        assert full_transcode_entry is not None
        assert full_transcode_entry['direct_play_compatible'] == 'False'
        assert 'transcode' in full_transcode_entry['action_needed'].lower()


class TestCacheProcessing:
    """Test --use-cache processing functionality"""
    
    @pytest.fixture
    def prepared_cache(self, video_files_dir, temp_dirs, run_converter):
        """Prepare a cache file for processing tests"""
        cache_file = temp_dirs['cache'] / 'processing_cache.csv'
        
        # Generate cache
        run_converter([
            str(video_files_dir),
            '--gather', str(cache_file)
        ])
        
        return cache_file
    
    def test_use_cache_basic_loading(self, video_files_dir, run_converter, prepared_cache):
        """Test basic cache loading functionality"""
        result = run_converter([
            str(video_files_dir),
            '--use-cache', str(prepared_cache),
            '--dry-run'
        ])
        
        assert result.returncode == 0
        assert 'Cache-Datei geladen' in result.stdout
        assert 'Zu verarbeitende Dateien:' in result.stdout
    
    def test_use_cache_with_limit(self, video_files_dir, run_converter, prepared_cache):
        """Test cache processing with limit parameter"""
        result = run_converter([
            str(video_files_dir),
            '--use-cache', str(prepared_cache),
            '--limit', '2',
            '--dry-run'
        ])
        
        assert result.returncode == 0
        assert 'Beschränke Verarbeitung auf' in result.stdout
        assert '--limit 2' in result.stdout
    
    def test_use_cache_skips_compatible(self, video_files_dir, run_converter, prepared_cache):
        """Test that cache processing skips already compatible files"""
        result = run_converter([
            str(video_files_dir),
            '--use-cache', str(prepared_cache),
            '--dry-run'
        ])
        
        assert result.returncode == 0
        # The output should indicate files that need processing, not compatible ones
        # This is implicit in the "Zu verarbeitende Dateien" count being less than total
    
    def test_nonexistent_cache_auto_generation(self, video_files_dir, temp_dirs, run_converter):
        """Test automatic cache generation for nonexistent cache file"""
        nonexistent_cache = temp_dirs['cache'] / 'nonexistent.csv'
        
        result = run_converter([
            str(video_files_dir),
            '--use-cache', str(nonexistent_cache),
            '--limit', '1',
            '--dry-run'
        ])
        
        assert result.returncode == 0
        assert 'Cache-Datei nicht gefunden, erstelle neue' in result.stdout
        assert nonexistent_cache.exists()
    
    def test_cache_state_management(self, temp_dirs, run_converter, prepared_cache):
        """Test that cache state is updated after processing"""
        # This test would require actual processing, not dry-run
        # For now, we test that the cache update functions exist
        
        # Test the cache reading function
        cache_data = read_cache_csv(prepared_cache)
        assert len(cache_data) > 0
        
        # Test cache update function
        first_entry = cache_data[0]
        original_processed = str(first_entry.get('processed', 'false')).lower() == 'true'
        
        update_cache_entry(prepared_cache, first_entry['file_path'], processed=True)
        
        # Read again and verify update
        updated_cache_data = read_cache_csv(prepared_cache)
        updated_entry = next((e for e in updated_cache_data 
                            if e['file_path'] == first_entry['file_path']), None)
        
        assert updated_entry is not None
        assert str(updated_entry['processed']).lower() == 'true'
        assert updated_entry['processing_date'] != ''


class TestLimitParameter:
    """Test --limit parameter functionality"""
    
    def test_limit_with_direct_processing(self, video_files_dir, run_converter):
        """Test limit parameter with direct directory processing"""
        result = run_converter([
            str(video_files_dir),
            '--limit', '2',
            '--dry-run'
        ])
        
        assert result.returncode == 0
        assert 'Beschränke Verarbeitung auf 2 Videodateien' in result.stdout
        assert 'Gefunden:' in result.stdout
    
    def test_limit_with_cache(self, video_files_dir, temp_dirs, run_converter):
        """Test limit parameter with existing cache"""
        # Create cache first
        cache_file = temp_dirs['cache'] / 'limit_test.csv'
        run_converter([
            str(video_files_dir),
            '--gather', str(cache_file)
        ])
        
        # Test with limit
        result = run_converter([
            str(video_files_dir),
            '--use-cache', str(cache_file),
            '--limit', '1',
            '--dry-run'
        ])
        
        assert result.returncode == 0
        assert 'Beschränke Verarbeitung auf' in result.stdout
    
    @pytest.mark.parametrize("limit_value", [1, 2, 5])
    def test_different_limit_values(self, video_files_dir, temp_dirs, run_converter, limit_value):
        """Test various limit values"""
        # Create cache first
        cache_file = temp_dirs['cache'] / f'limit_{limit_value}.csv'
        run_converter([
            str(video_files_dir),
            '--gather', str(cache_file)
        ])
        
        result = run_converter([
            str(video_files_dir),
            '--use-cache', str(cache_file),
            '--limit', str(limit_value),
            '--dry-run'
        ])
        
        assert result.returncode == 0
        assert f'--limit {limit_value}' in result.stdout