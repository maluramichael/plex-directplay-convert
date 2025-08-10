"""
Language normalization and filtering utilities
"""

from enum import Enum

# Language code mapping - maps various language codes to standardized 2-letter codes
LANGUAGE_MAP = {
    # German variants
    'de': 'de', 'deu': 'de', 'ger': 'de', 'german': 'de', 'deutsch': 'de',
    # English variants  
    'en': 'en', 'eng': 'en', 'english': 'en',
    # Japanese variants
    'jp': 'jp', 'ja': 'jp', 'jpn': 'jp', 'japanese': 'jp',
    # French variants
    'fr': 'fr', 'fra': 'fr', 'fre': 'fr', 'french': 'fr',
    # Spanish variants
    'es': 'es', 'esp': 'es', 'spa': 'es', 'spanish': 'es',
    # Italian variants
    'it': 'it', 'ita': 'it', 'italian': 'it',
    # Common fallbacks
    'unknown': 'unknown', 'und': 'unknown', '': 'unknown'
}

class Action(Enum):
    SKIP = "skip"
    REMUX_AUDIO = "remux_audio" # converts to stereo aac
    TRANCODE_VIDEO = "transcode_video" # converts to h264 SDR
    TRANCODE_ALL = "transcode_all" # converts to h264 SDR and stereo aac
    CONTAINER_REMUX = "container_remux" # converts to mp4

def normalize_language(lang_code):
    """Normalize language code using mapping"""
    if not lang_code:
        return 'unknown'
    return LANGUAGE_MAP.get(lang_code.lower(), lang_code.lower())

def filter_and_sort_streams(streams, languages, keep_languages=None, sort_languages=None):
    """Filter and sort streams based on language preferences"""
    if not streams:
        return []
    
    # Always keep 'unknown' language streams
    keep_langs = set(keep_languages or [])
    keep_langs.add('unknown')
    
    # Filter streams
    if keep_languages:
        filtered_streams = []
        for i, stream in enumerate(streams):
            tags = stream.get('tags', {})
            lang = normalize_language(tags.get('language', ''))
            if lang in keep_langs:
                filtered_streams.append((i, stream, lang))
    else:
        filtered_streams = [(i, stream, normalize_language(stream.get('tags', {}).get('language', ''))) 
                           for i, stream in enumerate(streams)]
    
    # Sort by language preference if specified
    if sort_languages:
        def sort_key(item):
            _, stream, lang = item
            try:
                return sort_languages.index(lang)
            except ValueError:
                return len(sort_languages)  # Put unknown languages at end
        filtered_streams.sort(key=sort_key)
    
    return filtered_streams