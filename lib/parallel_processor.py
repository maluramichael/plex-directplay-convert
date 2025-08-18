"""
Dask-based parallel file processing
"""

import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from concurrent.futures import ProcessPoolExecutor, as_completed
import dask
from dask import delayed
from dask.distributed import Client, as_completed as dask_as_completed
from dask.diagnostics import ProgressBar

from .models import MediaInfo, ProcessingConfig, ProcessingResult, BatchProcessingStats
from .media_analyzer import discover_media
from .processor import process_file
from .rich_console import rich_output


class ParallelProcessor:
    """Dask-based parallel processor for media files"""
    
    def __init__(self, max_workers: Optional[int] = None, use_distributed: bool = False):
        self.max_workers = max_workers or min(os.cpu_count() or 1, 4)  # Limit to 4 for FFmpeg
        self.use_distributed = use_distributed
        self.client: Optional[Client] = None
        
        if use_distributed:
            try:
                self.client = Client(processes=True, n_workers=self.max_workers, 
                                   threads_per_worker=1, memory_limit='2GB')
                rich_output.print_info(f"Dask distributed client started with {self.max_workers} workers")
            except Exception as e:
                rich_output.print_warning(f"Failed to start distributed client: {e}")
                rich_output.print_info("Falling back to synchronous processing")
                self.use_distributed = False
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            self.client.close()
    
    def analyze_files_parallel(self, file_paths: List[Path]) -> List[MediaInfo]:
        """Analyze multiple files in parallel"""
        if not file_paths:
            return []
        
        rich_output.print_info(f"Analyzing {len(file_paths)} files in parallel...")
        
        if self.use_distributed and self.client:
            return self._analyze_files_distributed(file_paths)
        else:
            return self._analyze_files_concurrent(file_paths)
    
    def _analyze_files_distributed(self, file_paths: List[Path]) -> List[MediaInfo]:
        """Analyze files using Dask distributed"""
        delayed_tasks = [delayed(self._analyze_single_file)(path) for path in file_paths]
        
        with ProgressBar():
            results = dask.compute(*delayed_tasks)
        
        return [result for result in results if result is not None]
    
    def _analyze_files_concurrent(self, file_paths: List[Path]) -> List[MediaInfo]:
        """Analyze files using concurrent futures"""
        results = []
        
        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            # Create progress bar
            progress = rich_output.create_batch_progress()
            
            with progress:
                task_id = progress.add_task("Analyzing files...", total=len(file_paths))
                
                # Submit all tasks
                future_to_path = {
                    executor.submit(self._analyze_single_file, path): path 
                    for path in file_paths
                }
                
                # Process completed tasks
                for future in as_completed(future_to_path):
                    path = future_to_path[future]
                    try:
                        result = future.result()
                        if result:
                            results.append(result)
                    except Exception as e:
                        rich_output.print_error(f"Analysis failed for {path}: {e}")
                    
                    progress.update(task_id, advance=1)
        
        return results
    
    @staticmethod
    def _analyze_single_file(path: Path) -> Optional[MediaInfo]:
        """Analyze a single file (static method for multiprocessing)"""
        try:
            from .media_analyzer import discover_media
            info_dict = discover_media(path)
            
            # Convert to Pydantic model
            media_info = MediaInfo(
                file_path=path,
                container=info_dict['container'],
                video_stream=None,
                audio_streams=[],
                subtitle_streams=[]
            )
            
            # Add video stream if present
            if info_dict['has_video']:
                from .models import VideoStreamInfo
                video_stream = VideoStreamInfo(
                    codec_name=info_dict['video_codec'] or 'unknown'
                )
                media_info.video_stream = video_stream
            
            # Add audio streams
            if info_dict['has_audio']:
                from .models import AudioStreamInfo
                for i, codec in enumerate(info_dict['audio_codecs']):
                    channels = info_dict['audio_channels'][i] if i < len(info_dict['audio_channels']) else 0
                    language = info_dict['audio_languages'][i] if i < len(info_dict['audio_languages']) else 'unknown'
                    
                    audio_stream = AudioStreamInfo(
                        codec_name=codec,
                        channels=channels,
                        language=language
                    )
                    media_info.audio_streams.append(audio_stream)
            
            return media_info
            
        except Exception as e:
            return None
    
    def process_batch_parallel(self, file_paths: List[Path], config: ProcessingConfig,
                             output_dir: Optional[Path] = None,
                             cache_path: Optional[Path] = None) -> BatchProcessingStats:
        """Process multiple files in parallel with controlled concurrency"""
        if not file_paths:
            return BatchProcessingStats()
        
        rich_output.print_info(f"Processing {len(file_paths)} files with {self.max_workers} workers...")
        
        stats = BatchProcessingStats(total_files=len(file_paths))
        stats.start_time = None  # Will be set when processing starts
        
        # For FFmpeg processing, we want to limit concurrency to avoid resource conflicts
        # Use a smaller number of workers for actual processing
        processing_workers = min(self.max_workers, 2)  # Max 2 concurrent FFmpeg processes
        
        results = []
        with ProcessPoolExecutor(max_workers=processing_workers) as executor:
            progress = rich_output.create_batch_progress()
            
            with progress:
                task_id = progress.add_task("Processing files...", total=len(file_paths))
                
                # Submit all tasks
                future_to_path = {
                    executor.submit(
                        self._process_single_file_wrapper,
                        path, output_dir, config, cache_path
                    ): path 
                    for path in file_paths
                }
                
                # Process completed tasks
                for future in as_completed(future_to_path):
                    path = future_to_path[future]
                    try:
                        result = future.result()
                        results.append(result)
                        stats.add_result(result)
                    except Exception as e:
                        rich_output.print_error(f"Processing failed for {path}: {e}")
                        stats.add_result('error')
                    
                    progress.update(task_id, advance=1)
        
        return stats
    
    @staticmethod
    def _process_single_file_wrapper(file_path: Path, output_dir: Optional[Path], 
                                   config: ProcessingConfig, cache_path: Optional[Path]) -> str:
        """Wrapper for process_file to work with multiprocessing"""
        try:
            target_dir = output_dir if output_dir else file_path.parent
            
            result, _ = process_file(
                file_path, target_dir, config.crf, config.preset, 
                False,  # dry_run = False
                False,  # interactive = False 
                True,   # auto_yes = True (no user interaction in parallel mode)
                False,  # debug = False
                config.keep_languages, config.sort_languages,
                None,   # gpu_info - will be detected in subprocess
                config.use_gpu, config.action_filter, config.delete_original,
                cache_path
            )
            return result
        except Exception as e:
            return 'error'
    
    def create_analysis_tasks(self, root_path: Path) -> List[Path]:
        """Create list of files to analyze from root path"""
        from .file_utils import VIDEO_EXTS
        
        if root_path.is_file():
            if root_path.suffix.lower() in VIDEO_EXTS:
                return [root_path]
            else:
                return []
        
        # Collect video files from directory
        video_files = []
        for ext in VIDEO_EXTS:
            video_files.extend(root_path.rglob(f'*{ext}'))
            video_files.extend(root_path.rglob(f'*{ext.upper()}'))
        
        # Remove duplicates and filter for actual files
        return list(set([p for p in video_files if p.is_file()]))
    
    def get_optimal_worker_count(self, task_type: str = 'analysis') -> int:
        """Get optimal worker count based on task type"""
        cpu_count = os.cpu_count() or 1
        
        if task_type == 'analysis':
            # Analysis can be more parallel
            return min(cpu_count, 8)
        elif task_type == 'processing':
            # FFmpeg processing should be limited to avoid conflicts
            return min(cpu_count, 2)
        else:
            return min(cpu_count, 4)


def create_parallel_processor(max_workers: Optional[int] = None, 
                            use_distributed: bool = False) -> ParallelProcessor:
    """Factory function to create a parallel processor"""
    return ParallelProcessor(max_workers=max_workers, use_distributed=use_distributed)