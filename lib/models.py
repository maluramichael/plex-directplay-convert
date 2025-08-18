"""
Pydantic models for data validation and serialization
"""

from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator
from enum import Enum

from .language_utils import Action


class AudioStreamInfo(BaseModel):
    """Audio stream information"""
    codec_name: str
    channels: int
    language: Optional[str] = None
    tags: Dict[str, Any] = Field(default_factory=dict)
    
    @validator('channels')
    def validate_channels(cls, v):
        if v < 0:
            raise ValueError('Channels must be non-negative')
        return v


class VideoStreamInfo(BaseModel):
    """Video stream information"""
    codec_name: str
    color_transfer: Optional[str] = None
    color_primaries: Optional[str] = None
    side_data_list: List[Dict[str, Any]] = Field(default_factory=list)
    
    def is_hdr(self) -> bool:
        """Check if this video stream contains HDR content"""
        hdr_transfers = {'smpte2084', 'arib-std-b67', 'smpte428', 'iec61966-2-1'}
        hdr_primaries = {'bt2020', 'smpte431', 'smpte432'}
        
        if (self.color_transfer and self.color_transfer.lower() in hdr_transfers or
            self.color_primaries and self.color_primaries.lower() in hdr_primaries):
            return True
        
        for side_data in self.side_data_list:
            side_data_type = side_data.get('side_data_type', '').lower()
            if 'hdr' in side_data_type or 'mastering' in side_data_type or 'content_light' in side_data_type:
                return True
        
        return False


class SubtitleStreamInfo(BaseModel):
    """Subtitle stream information"""
    codec_name: str
    language: Optional[str] = None
    tags: Dict[str, Any] = Field(default_factory=dict)


class MediaInfo(BaseModel):
    """Complete media file information"""
    file_path: Path
    container: str
    video_stream: Optional[VideoStreamInfo] = None
    audio_streams: List[AudioStreamInfo] = Field(default_factory=list)
    subtitle_streams: List[SubtitleStreamInfo] = Field(default_factory=list)
    
    @property
    def has_video(self) -> bool:
        return self.video_stream is not None
    
    @property
    def has_audio(self) -> bool:
        return len(self.audio_streams) > 0
    
    @property
    def is_hdr(self) -> bool:
        return self.video_stream.is_hdr() if self.video_stream else False
    
    @property
    def video_codec(self) -> Optional[str]:
        return self.video_stream.codec_name if self.video_stream else None
    
    @property
    def audio_codecs(self) -> List[str]:
        return [stream.codec_name for stream in self.audio_streams]
    
    @property
    def audio_channels(self) -> List[int]:
        return [stream.channels for stream in self.audio_streams]
    
    @property
    def audio_languages(self) -> List[str]:
        return [stream.language or 'unknown' for stream in self.audio_streams]
    
    @property
    def subtitle_languages(self) -> List[str]:
        return [stream.language or 'unknown' for stream in self.subtitle_streams]
    
    def is_direct_play_compatible(self) -> bool:
        """Check if file is already Direct Play compatible for Apple TV 4K"""
        container_ok = self.container == 'mp4'
        video_ok = (self.video_codec or '').lower() == 'h264' and not self.is_hdr
        audio_ok = (self.has_audio and 
                   all(codec == 'aac' for codec in self.audio_codecs) and 
                   all(channels == 2 for channels in self.audio_channels))
        
        return container_ok and video_ok and audio_ok
    
    def get_required_action(self) -> Action:
        """Determine what processing action is needed"""
        container_ok = self.container == 'mp4'
        video_ok = (self.video_codec or '').lower() == 'h264' and not self.is_hdr
        audio_ok = (self.has_audio and 
                   all(codec == 'aac' for codec in self.audio_codecs) and 
                   all(channels == 2 for channels in self.audio_channels))

        if container_ok and video_ok and audio_ok:
            return Action.SKIP
        elif not container_ok and video_ok and audio_ok:
            return Action.CONTAINER_REMUX
        elif container_ok and video_ok and not audio_ok:
            return Action.REMUX_AUDIO
        elif container_ok and audio_ok and not video_ok:
            return Action.TRANCODE_VIDEO
        else:
            return Action.TRANCODE_ALL


class ProcessingResult(BaseModel):
    """Result of file processing operation"""
    source_path: Path
    target_path: Optional[Path] = None
    action_taken: Action
    success: bool
    error_message: Optional[str] = None
    processing_time: Optional[float] = None
    file_size_before: Optional[int] = None
    file_size_after: Optional[int] = None
    
    @validator('processing_time')
    def validate_processing_time(cls, v):
        if v is not None and v < 0:
            raise ValueError('Processing time must be non-negative')
        return v


class CacheEntry(BaseModel):
    """Cache entry for analyzed file data"""
    file_path: str
    file_name: str
    file_size_bytes: int
    file_size_mb: float
    container: str
    video_codec: str
    is_hdr: bool
    audio_codecs: str
    audio_channels: str
    audio_languages: str
    has_video: bool
    has_audio: bool
    direct_play_compatible: bool
    action_needed: str
    analysis_date: datetime
    processed: bool = False
    processing_date: Optional[datetime] = None
    
    @validator('file_size_bytes')
    def validate_file_size(cls, v):
        if v < 0:
            raise ValueError('File size must be non-negative')
        return v
    
    @validator('file_size_mb')
    def validate_file_size_mb(cls, v):
        if v < 0:
            raise ValueError('File size in MB must be non-negative')
        return v
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ProcessingConfig(BaseModel):
    """Configuration for file processing"""
    crf: int = Field(default=22, ge=0, le=51)
    preset: str = Field(default='medium')
    use_gpu: bool = False
    delete_original: bool = False
    keep_languages: List[str] = Field(default_factory=list)
    sort_languages: List[str] = Field(default_factory=list)
    action_filter: Optional[Action] = None
    limit: Optional[int] = None
    
    @validator('preset')
    def validate_preset(cls, v):
        valid_presets = ['ultrafast', 'superfast', 'veryfast', 'faster', 'fast', 
                        'medium', 'slow', 'slower', 'veryslow']
        if v not in valid_presets:
            raise ValueError(f'Preset must be one of: {", ".join(valid_presets)}')
        return v
    
    @validator('limit')
    def validate_limit(cls, v):
        if v is not None and v <= 0:
            raise ValueError('Limit must be positive')
        return v


class BatchProcessingStats(BaseModel):
    """Statistics for batch processing operation"""
    total_files: int = 0
    processed_files: int = 0
    converted_files: int = 0
    remuxed_files: int = 0
    skipped_files: int = 0
    error_files: int = 0
    interrupted_files: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    @property
    def processing_duration(self) -> Optional[float]:
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None
    
    def add_result(self, result: str):
        """Add a processing result to the statistics"""
        if result in ('converted', 'processed'):
            self.converted_files += 1
        elif result in ('skipped', 'planned', 'filtered'):
            self.skipped_files += 1
        elif result in ('remuxed',):
            self.remuxed_files += 1
        elif result in ('interrupted',):
            self.interrupted_files += 1
        else:
            self.error_files += 1
        
        self.processed_files += 1