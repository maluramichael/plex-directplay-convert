"""
pytest configuration and fixtures for ffmpeg converter tests

Uses pre-generated video files from tests/video_files/
Run tests/generate_test_files.py first to create the video files.
"""

import pytest
import tempfile
import shutil
import subprocess
from pathlib import Path
import sys

# Add the converter lib to path for importing
sys.path.insert(0, str(Path(__file__).parent.parent))
from lib import discover_media, ffprobe_streams


@pytest.fixture(scope="session")
def check_ffmpeg():
    """Check if ffmpeg is available before running tests"""
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        subprocess.run(['ffprobe', '-version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pytest.skip("ffmpeg and/or ffprobe not available")


@pytest.fixture(scope="session") 
def check_test_files():
    """Check if test video files exist"""
    video_files_dir = Path(__file__).parent / 'video_files'
    
    required_files = [
        'compatible.mp4',
        'remux_mkv.mkv', 
        'audio_transcode.mp4',
        'video_transcode.mp4',
        'full_transcode.mkv',
        'hdr_content.mp4',
        'multilingual.mkv',
        'no_language.mp4'
    ]
    
    missing_files = []
    for filename in required_files:
        if not (video_files_dir / filename).exists():
            missing_files.append(filename)
    
    if missing_files:
        pytest.skip(f"Missing test video files: {missing_files}. Run 'python tests/generate_test_files.py' first.")


@pytest.fixture(scope="session")
def video_files_dir(check_ffmpeg, check_test_files):
    """Get the directory containing pre-generated video files"""
    return Path(__file__).parent / 'video_files'


@pytest.fixture(scope="session")
def temp_dirs():
    """Create temporary directories for testing outputs"""
    temp_dir = Path(tempfile.mkdtemp(prefix='converter_pytest_'))
    
    dirs = {
        'temp': temp_dir,
        'output': temp_dir / 'output',  
        'cache': temp_dir / 'cache'
    }
    
    # Create directories
    for dir_path in dirs.values():
        dir_path.mkdir(exist_ok=True)
    
    yield dirs
    
    # Cleanup
    if temp_dir.exists():
        shutil.rmtree(temp_dir)


@pytest.fixture
def run_converter(temp_dirs):
    """Fixture to run converter commands"""
    def _run_converter(args: list, expect_error: bool = False):
        script_path = Path(__file__).parent.parent / 'main.py'
        cmd = [sys.executable, str(script_path)] + args
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if not expect_error and result.returncode != 0:
            pytest.fail(f"Converter failed: {result.stderr}")
        
        return result
    
    return _run_converter


@pytest.fixture(scope="session")
def sample_files(video_files_dir):
    """Dictionary of all pre-generated sample video files"""
    return {
        # Basic compatibility tests
        'compatible_mp4': video_files_dir / 'compatible.mp4',
        'remux_mkv': video_files_dir / 'remux_mkv.mkv',
        'audio_transcode': video_files_dir / 'audio_transcode.mp4',
        'video_transcode': video_files_dir / 'video_transcode.mp4',
        'full_transcode': video_files_dir / 'full_transcode.mkv',
        
        # Special content types
        'hdr_content': video_files_dir / 'hdr_content.mp4',
        'multilingual': video_files_dir / 'multilingual.mkv',
        'no_language': video_files_dir / 'no_language.mp4',
        
        # Additional formats for comprehensive testing
        'mp3_audio': video_files_dir / 'mp3_audio.mp4',
        'legacy_avi': video_files_dir / 'legacy_avi.avi',
    }


@pytest.fixture
def all_video_files(video_files_dir):
    """List of all video files in the video_files directory"""
    video_extensions = {'.mp4', '.mkv', '.avi', '.mov', '.m4v', '.wmv', '.flv'}
    return [f for f in video_files_dir.iterdir() 
            if f.is_file() and f.suffix.lower() in video_extensions]


# Utility functions that can be used in tests
def get_file_info(file_path: Path) -> dict:
    """Get converter analysis info for a file"""
    return discover_media(file_path)


def get_action_for_file(file_path: Path) -> 'Action':
    """Get the required processing action for a file"""
    from lib import needs_processing
    info = discover_media(file_path)
    return needs_processing(info, 'mp4')


# Test data validation
@pytest.fixture(scope="session", autouse=True)
def validate_test_files(video_files_dir, check_test_files):
    """Validate that all test files are properly created and analyzable"""
    print(f"\nValidating test files in {video_files_dir}...")
    
    validation_results = {}
    
    for video_file in video_files_dir.glob("*"):
        if video_file.suffix.lower() in {'.mp4', '.mkv', '.avi'}:
            try:
                info = discover_media(video_file)
                validation_results[video_file.name] = {
                    'analyzable': True,
                    'has_video': info['has_video'],
                    'has_audio': info['has_audio'],
                    'container': info['container']
                }
            except Exception as e:
                validation_results[video_file.name] = {
                    'analyzable': False,
                    'error': str(e)
                }
    
    # Check if any files failed validation
    failed_files = [name for name, result in validation_results.items() 
                   if not result['analyzable']]
    
    if failed_files:
        pytest.fail(f"Test file validation failed for: {failed_files}")
    
    print(f"✅ All {len(validation_results)} test files validated successfully")