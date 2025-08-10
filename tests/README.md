# FFmpeg Converter Test Suite

This comprehensive test suite validates all functionality of the plex_directplay_convert.py script using pytest and pre-generated synthetic video files.

## 🚀 Quick Start

### 1. Generate Test Files (One-time setup)
```bash
python tests/generate_test_files.py
```

### 2. Run Tests
```bash
# Run all tests
venv/bin/python -m pytest tests/

# Run specific test module
venv/bin/python -m pytest tests/test_synthetic_files.py -v

# Run with coverage
venv/bin/python -m pytest tests/ --cov=plex_directplay_convert --cov-report=html
```

## 📁 Test Structure

### Pre-Generated Video Files

All test files are generated once and stored in `tests/video_files/`:

**Total size**: ~3.3 MB (10 files)

#### Core Test Files
- **`compatible.mp4`** - H.264 + AAC Stereo (already compatible)
- **`remux_mkv.mkv`** - H.264 + AAC in MKV (needs container remux)
- **`audio_transcode.mp4`** - H.264 + AC3 6ch (needs audio transcoding)
- **`video_transcode.mp4`** - MPEG-4 + AAC (needs video transcoding)
- **`full_transcode.mkv`** - MPEG-4 + AC3 6ch in MKV (needs full transcoding)

#### Special Content
- **`hdr_content.mp4`** - HDR content with color metadata
- **`multilingual.mkv`** - German/English/Japanese audio tracks
- **`no_language.mp4`** - No language metadata (unknown)
- **`mp3_audio.mp4`** - H.264 + MP3 audio
- **`legacy_avi.avi`** - MPEG-4 + MP3 in AVI container

### Test Modules

#### `test_synthetic_files.py` (19 tests)
- File analysis and codec detection
- Container format validation
- HDR metadata detection
- Language track analysis
- File size validation

#### `test_action_detection.py` (12 tests)
- Action detection for different file types
- Direct Play compatibility checking
- Parametrized action validation
- HDR processing requirements

#### `test_cache_operations.py` (14 tests)
- Cache generation (`--gather`)
- Cache loading (`--use-cache`)
- Limit parameter functionality
- State management and updates
- Error handling

#### `test_language_handling.py` (10 tests)
- Language normalization
- Stream filtering (`--keep-languages`)
- Stream sorting (`--sort-languages`)
- Unknown language handling
- Command-line argument processing

#### `test_integration.py` (8 tests)
- Complete two-step workflows
- Incremental processing
- Action filtering workflows
- Language processing workflows
- Error handling scenarios

## 🛠️ Test Features

### Static Video Files (No Dynamic Generation)
- **Fast execution**: No ffmpeg calls during test runs
- **Consistent results**: Same files every time
- **Reliable CI/CD**: No dependency on ffmpeg during testing
- **Small footprint**: Only 3.3 MB total

### Comprehensive Coverage
- All converter functions tested
- All new cache-based features validated
- Error conditions and edge cases covered
- Integration workflows tested end-to-end

### pytest Best Practices
- **Fixtures**: Reusable test data and utilities
- **Parametrized tests**: Comprehensive scenario coverage
- **Session-scoped setup**: Efficient resource usage
- **Automatic validation**: Test files validated on startup

## 🎯 New Features Tested

### 1. Processing Limit (`--limit N`)
✅ Limits processing to next N files needing conversion  
✅ Skips already compatible files in count  
✅ Works with direct and cache-based processing  

### 2. Two-Step Cache Processing
✅ **Step 1**: `--gather cache.csv` creates comprehensive analysis  
✅ **Step 2**: `--use-cache cache.csv --limit 10` processes from cache  
✅ Cache state updated after each file processed  
✅ Incremental processing support  

### 3. Enhanced Directory Processing
✅ Auto-generates temporary cache for directories  
✅ Better glob filtering by video extensions  
✅ Persistent state tracking in cache files  

## 📊 Test Results

**63 tests passing** in ~27 seconds

- **File Analysis**: 19 tests ✅
- **Action Detection**: 12 tests ✅
- **Cache Operations**: 14 tests ✅
- **Language Handling**: 10 tests ✅
- **Integration Workflows**: 8 tests ✅

## 🔧 Maintenance

### Regenerating Test Files
If you need to recreate the test files (e.g., for different settings):

```bash
# Remove existing files
rm -rf tests/video_files/*

# Regenerate with new settings
python tests/generate_test_files.py
```

### Adding New Tests
1. Add test functions to appropriate test module
2. Use `sample_files` fixture for pre-generated files
3. Use `video_files_dir` fixture for the files directory
4. Follow pytest naming conventions (`test_*.py`, `test_*()`)

## 🎬 Video File Specifications

All synthetic files created with:
- **Duration**: 3 seconds
- **Video**: 640x360 resolution, 24fps
- **Audio**: Various codecs/channels as specified
- **Size**: Optimized for fast testing (200KB - 700KB each)

The files comprehensively test all converter functionality while remaining small and fast to work with.