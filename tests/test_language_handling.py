"""
Test language filtering and sorting functionality
"""

import pytest
from lib import normalize_language, discover_media, filter_and_sort_streams


class TestLanguageHandling:
    """Test language filtering and sorting functionality"""
    
    def test_language_normalization(self):
        """Test language code normalization"""
        test_cases = [
            ('de', 'de'),
            ('deu', 'de'),
            ('german', 'de'),
            ('deutsch', 'de'),
            ('en', 'en'),
            ('eng', 'en'),
            ('english', 'en'),
            ('jp', 'jp'),
            ('ja', 'jp'),
            ('jpn', 'jp'),
            ('japanese', 'jp'),
            ('unknown', 'unknown'),
            ('und', 'unknown'),
            ('', 'unknown'),
            (None, 'unknown'),
        ]
        
        for input_code, expected in test_cases:
            result = normalize_language(input_code)
            assert result == expected, f"normalize_language({input_code!r}) should be {expected!r}, got {result!r}"
    
    def test_multilingual_file_detection(self, sample_files):
        """Test detection of multiple languages in file"""
        info = discover_media(sample_files['multilingual'])
        
        # Should detect multiple audio streams
        assert len(info['audio_streams']) == 3
        assert len(info['audio_languages']) == 3
        
        # Should contain the expected languages
        expected_languages = {'de', 'en', 'jp'}
        detected_languages = set(info['audio_languages'])
        
        assert expected_languages.issubset(detected_languages), \
            f"Expected {expected_languages}, got {detected_languages}"
    
    def test_filter_streams_keep_languages(self, sample_files):
        """Test stream filtering by language"""
        info = discover_media(sample_files['multilingual'])
        streams = info['audio_streams']
        languages = info['audio_languages']
        
        # Filter to keep only German and English
        filtered = filter_and_sort_streams(
            streams, languages, keep_languages=['de', 'en']
        )
        
        # Should have 2 streams (German and English)
        assert len(filtered) == 2
        
        # Extract languages from filtered streams
        filtered_languages = [lang for _, _, lang in filtered]
        assert 'de' in filtered_languages
        assert 'en' in filtered_languages
        assert 'jp' not in filtered_languages
    
    def test_sort_streams_by_language(self, sample_files):
        """Test stream sorting by language preference"""
        info = discover_media(sample_files['multilingual'])
        streams = info['audio_streams']
        languages = info['audio_languages']
        
        # Sort with Japanese first, then English, then German
        sorted_streams = filter_and_sort_streams(
            streams, languages, sort_languages=['jp', 'en', 'de']
        )
        
        # Extract languages in sorted order
        sorted_languages = [lang for _, _, lang in sorted_streams]
        
        # Japanese should come first if present
        if 'jp' in sorted_languages:
            assert sorted_languages[0] == 'jp'
        
        # Languages should be in preference order
        jp_index = sorted_languages.index('jp') if 'jp' in sorted_languages else float('inf')
        en_index = sorted_languages.index('en') if 'en' in sorted_languages else float('inf')
        de_index = sorted_languages.index('de') if 'de' in sorted_languages else float('inf')
        
        assert jp_index < en_index < de_index
    
    def test_keep_and_sort_languages_combined(self, sample_files):
        """Test combining language filtering and sorting"""
        info = discover_media(sample_files['multilingual'])
        streams = info['audio_streams']
        languages = info['audio_languages']
        
        # Keep only German and English, with English first
        filtered_sorted = filter_and_sort_streams(
            streams, languages, 
            keep_languages=['de', 'en'],
            sort_languages=['en', 'de']
        )
        
        assert len(filtered_sorted) == 2
        languages_order = [lang for _, _, lang in filtered_sorted]
        
        # English should come before German
        if 'en' in languages_order and 'de' in languages_order:
            en_index = languages_order.index('en')
            de_index = languages_order.index('de')
            assert en_index < de_index
    
    def test_language_filter_with_unknown(self, sample_files):
        """Test that unknown languages are preserved"""
        # Use the no_language file which has no explicit language metadata
        info = discover_media(sample_files['no_language'])
        streams = info['audio_streams']  
        languages = info['audio_languages']
        
        # Filter to keep only German - should still include unknown
        filtered = filter_and_sort_streams(
            streams, languages, keep_languages=['de']
        )
        
        # Should have the unknown language stream
        assert len(filtered) > 0
        filtered_languages = [lang for _, _, lang in filtered]
        assert 'unknown' in filtered_languages
    
    def test_language_commands_dry_run(self, sample_files, temp_dirs, run_converter):
        """Test language filtering commands in dry-run mode"""
        # Test keep-languages
        result_keep = run_converter([
            str(sample_files['multilingual']),
            '--keep-languages', 'de,en',
            '--out', str(temp_dirs['output']),
            '--dry-run'
        ])
        
        assert result_keep.returncode == 0
        
        # Test sort-languages
        result_sort = run_converter([
            str(sample_files['multilingual']),
            '--sort-languages', 'en,de,jp',
            '--out', str(temp_dirs['output']),
            '--dry-run'
        ])
        
        assert result_sort.returncode == 0
        
        # Test both combined
        result_both = run_converter([
            str(sample_files['multilingual']),
            '--keep-languages', 'de,en',
            '--sort-languages', 'en,de',
            '--out', str(temp_dirs['output']),
            '--dry-run'
        ])
        
        assert result_both.returncode == 0
    
    @pytest.mark.parametrize("lang_input,expected_normalized", [
        ('de,en,jp', ['de', 'en', 'jp']),
        ('german,english,japanese', ['de', 'en', 'jp']),
        ('deu,eng,jpn', ['de', 'en', 'jp']),
    ])
    def test_language_argument_parsing(self, lang_input, expected_normalized):
        """Test that language arguments are correctly normalized"""
        # Simulate the argument parsing logic from main()
        parsed_languages = [normalize_language(lang.strip()) 
                           for lang in lang_input.split(',')]
        
        assert parsed_languages == expected_normalized