import os
from pathlib import Path
import logging
import base64

logger = logging.getLogger(__name__)

AUDIO_DIR = Path("static/audio")
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

def text_to_speech(text: str, doc_id: str) -> str:
    """
    Generate audio file or return text for browser TTS.
    This version doesn't require gTTS and uses browser-based TTS.
    """
    try:
        # Create a text file that the frontend can use with browser TTS
        output_path = AUDIO_DIR / f"{doc_id}_podcast.txt"
        
        # Limit text length for reasonable files
        if len(text) > 1000:
            text = text[:1000] + "... (content truncated for audio)"
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(text)
        
        return str(output_path)
        
    except Exception as e:
        logger.error(f"Audio generation failed: {e}")
        # Return a fallback path
        return f"/static/audio/{doc_id}_podcast.txt"

def generate_audio_placeholder() -> str:
    """Generate a simple placeholder audio message"""
    placeholder_text = "Audio generation requires browser text-to-speech support. Please use the play button in the interface."
    
    try:
        # Create placeholder file
        output_path = AUDIO_DIR / "placeholder_audio.txt"
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(placeholder_text)
        return str(output_path)
    except Exception as e:
        logger.error(f"Placeholder audio failed: {e}")
        return ""

def get_audio_file_base64(audio_path: str) -> str:
    """Get base64 encoded audio file content for frontend"""
    try:
        if os.path.exists(audio_path):
            with open(audio_path, 'rb') as f:
                audio_data = f.read()
            return base64.b64encode(audio_data).decode('utf-8')
    except Exception as e:
        logger.error(f"Base64 encoding failed: {e}")
    return ""

def cleanup_old_audio_files(max_files: int = 50):
    """Clean up old audio files to prevent storage issues"""
    try:
        audio_files = list(AUDIO_DIR.glob("*.txt"))
        audio_files.sort(key=os.path.getmtime, reverse=True)
        
        if len(audio_files) > max_files:
            for old_file in audio_files[max_files:]:
                try:
                    os.remove(old_file)
                    logger.info(f"Removed old audio file: {old_file}")
                except Exception as e:
                    logger.error(f"Failed to remove {old_file}: {e}")
    except Exception as e:
        logger.error(f"Audio cleanup failed: {e}")