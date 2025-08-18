"""
Rich console output and progress tracking
"""

import time
from typing import Optional, Dict, Any
from pathlib import Path
from rich.console import Console
from rich.progress import (
    Progress, SpinnerColumn, TextColumn, BarColumn, 
    TaskProgressColumn, TimeElapsedColumn, TimeRemainingColumn
)
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.layout import Layout
from rich.live import Live
from rich import box

from .models import MediaInfo, ProcessingConfig, BatchProcessingStats
from .language_utils import Action

# Global console instance
console = Console()

class RichOutput:
    """Rich console output manager"""
    
    def __init__(self):
        self.console = console
        self.current_progress: Optional[Progress] = None
    
    def print_header(self, title: str):
        """Print application header"""
        self.console.print(Panel.fit(
            f"[bold blue]{title}[/bold blue]",
            box=box.DOUBLE,
            border_style="blue"
        ))
    
    def print_file_path(self, path: Path):
        """Print file path being processed"""
        self.console.print(f"\n[bold cyan]Processing:[/bold cyan] {path}")
    
    def print_file_info(self, media_info: MediaInfo, action: Action, 
                       output_path: Optional[Path] = None, debug_cmd: Optional[str] = None,
                       gpu_info: Optional[Dict] = None):
        """Print detailed file information in a formatted table"""
        table = Table(show_header=True, header_style="bold magenta", box=box.ROUNDED)
        table.add_column("Property", style="cyan", width=20)
        table.add_column("Value", style="white")
        
        # File info
        table.add_row("File Path", str(media_info.file_path))
        table.add_row("Container", media_info.container.upper())
        
        # Video info
        if media_info.has_video:
            video_info = f"{media_info.video_codec}"
            if media_info.is_hdr:
                video_info += " [red](HDR)[/red]"
            table.add_row("Video Codec", video_info)
        else:
            table.add_row("Video Codec", "[red]None[/red]")
        
        # Audio info
        if media_info.has_audio:
            audio_info = f"{', '.join(media_info.audio_codecs)}"
            channels_info = f"({', '.join(map(str, media_info.audio_channels))} ch)"
            table.add_row("Audio Codecs", f"{audio_info} {channels_info}")
            
            lang_info = ', '.join(media_info.audio_languages)
            table.add_row("Audio Languages", lang_info or "unknown")
        else:
            table.add_row("Audio Codecs", "[red]None[/red]")
        
        # Action needed
        action_descriptions = {
            Action.SKIP: "[green]✓ Already compatible[/green]",
            Action.CONTAINER_REMUX: "[yellow]Container remux to MP4[/yellow]",
            Action.REMUX_AUDIO: "[yellow]Audio remux to stereo AAC[/yellow]",
            Action.TRANCODE_VIDEO: "[orange3]Video transcode to H.264 SDR[/orange3]",
            Action.TRANCODE_ALL: "[red]Full transcode (video + audio)[/red]"
        }
        table.add_row("Action Needed", action_descriptions.get(action, str(action)))
        
        # Output path
        if output_path:
            table.add_row("Output Path", str(output_path))
        
        # GPU info
        if gpu_info and gpu_info.get('available'):
            gpu_text = f"{gpu_info['platform'].title()} ({gpu_info['encoder']})"
            table.add_row("GPU Acceleration", f"[green]{gpu_text}[/green]")
        
        self.console.print(table)
        
        # Debug command if available
        if debug_cmd:
            self.console.print(Panel(
                debug_cmd,
                title="[bold yellow]FFmpeg Command[/bold yellow]",
                border_style="yellow"
            ))
    
    def print_processing_start(self, output_name: str):
        """Print processing start message"""
        self.console.print(f"\n[bold green]Creating:[/bold green] {output_name}")
        self.console.print("[bold yellow]Processing started...[/bold yellow]")
    
    def create_progress_bar(self, total_duration: Optional[float] = None) -> Progress:
        """Create and return a progress bar for FFmpeg processing"""
        if total_duration:
            # Time-based progress for FFmpeg
            progress = Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                TimeElapsedColumn(),
                TimeRemainingColumn(),
                console=self.console
            )
        else:
            # Indeterminate progress
            progress = Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                TimeElapsedColumn(),
                console=self.console
            )
        
        self.current_progress = progress
        return progress
    
    def create_batch_progress(self) -> Progress:
        """Create progress bar for batch processing"""
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=self.console
        )
        return progress
    
    def print_success(self, message: str = "Processing completed!"):
        """Print success message"""
        self.console.print(f"[bold green]✓ {message}[/bold green]")
    
    def print_error(self, message: str, details: Optional[str] = None):
        """Print error message"""
        self.console.print(f"[bold red]✗ {message}[/bold red]")
        if details:
            self.console.print(f"[red]Details: {details}[/red]")
    
    def print_warning(self, message: str):
        """Print warning message"""
        self.console.print(f"[bold yellow]⚠ {message}[/bold yellow]")
    
    def print_info(self, message: str):
        """Print info message"""
        self.console.print(f"[bold cyan]ℹ {message}[/bold cyan]")
    
    def print_skipped(self, reason: str = "Skipped"):
        """Print skip message"""
        self.console.print(f"[bold yellow]⏭ {reason}[/bold yellow]")
    
    def print_interrupted(self, message: str = "Processing interrupted"):
        """Print interruption message"""
        self.console.print(f"\n[bold red]⏹ {message}[/bold red]")
    
    def print_gpu_info(self, gpu_info: Dict):
        """Print GPU acceleration info"""
        if gpu_info.get('available'):
            platform_icons = {'metal': '🔥', 'nvidia': '🟢', 'intel': '🔵'}
            icon = platform_icons.get(gpu_info['platform'], '⚡')
            self.console.print(f"{icon} [bold green]GPU acceleration detected:[/bold green] "
                             f"{gpu_info['platform'].title()} ({gpu_info['encoder']})")
        else:
            self.console.print("[bold yellow]GPU acceleration requested but not available - using CPU encoding[/bold yellow]")
    
    def print_cache_info(self, cache_path: Path, total_files: int, 
                        processed: int, compatible: int, need_processing: int):
        """Print cache file information"""
        table = Table(show_header=True, header_style="bold magenta", box=box.ROUNDED)
        table.add_column("Category", style="cyan")
        table.add_column("Count", style="white", justify="right")
        
        table.add_row("Total Files", str(total_files))
        table.add_row("Already Processed", f"[green]{processed}[/green]")
        table.add_row("Compatible Files", f"[blue]{compatible}[/blue]")
        table.add_row("Need Processing", f"[yellow]{need_processing}[/yellow]")
        
        self.console.print(Panel(
            table,
            title=f"[bold blue]Cache loaded: {cache_path.name}[/bold blue]",
            border_style="blue"
        ))
    
    def print_final_summary(self, stats: BatchProcessingStats):
        """Print final processing summary"""
        status_icon = "✓" if stats.interrupted_files == 0 else "⏹"
        status_color = "green" if stats.interrupted_files == 0 else "yellow"
        title = "Processing Complete" if stats.interrupted_files == 0 else "Processing Interrupted"
        
        table = Table(show_header=True, header_style="bold magenta", box=box.ROUNDED)
        table.add_column("Metric", style="cyan")
        table.add_column("Count", style="white", justify="right")
        
        table.add_row("Total Files", str(stats.total_files))
        table.add_row("Converted", f"[green]{stats.converted_files}[/green]")
        table.add_row("Remuxed", f"[blue]{stats.remuxed_files}[/blue]")
        table.add_row("Skipped", f"[yellow]{stats.skipped_files}[/yellow]")
        
        if stats.interrupted_files > 0:
            table.add_row("Interrupted", f"[red]{stats.interrupted_files}[/red]")
        
        if stats.error_files > 0:
            table.add_row("Errors", f"[red]{stats.error_files}[/red]")
        
        if stats.processing_duration:
            duration_str = f"{stats.processing_duration:.1f}s"
            table.add_row("Duration", duration_str)
        
        self.console.print(Panel(
            table,
            title=f"[bold {status_color}]{status_icon} {title}[/bold {status_color}]",
            border_style=status_color
        ))
    
    def ask_confirmation(self, prompt: str = "Continue?") -> str:
        """Ask user for confirmation with Rich styling"""
        options_text = "[dim]([/dim][bold green]y[/bold green][dim]es / [/dim][bold red]n[/bold red][dim]o / [/dim][bold blue]a[/bold blue][dim]ll / [/dim][bold yellow]q[/bold yellow][dim]uit)[/dim]"
        self.console.print(f"{prompt} {options_text}")
        
        while True:
            choice = input().lower().strip()
            if choice in ['j', 'ja', 'y', 'yes']:
                return 'yes'
            elif choice in ['n', 'nein', 'no']:
                return 'no'
            elif choice in ['a', 'alle', 'all']:
                return 'all'
            elif choice in ['q', 'quit', 'exit']:
                return 'quit'
            else:
                self.console.print("[red]Please enter: y/n/a/q[/red]")

# Global rich output instance
rich_output = RichOutput()