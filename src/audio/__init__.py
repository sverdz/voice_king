"""
Audio module - STT, TTS та Wake Word Detection
"""
from .stt import SpeechToText
from .tts import TextToSpeech
from .wake_word import WakeWordDetector

__all__ = ['SpeechToText', 'TextToSpeech', 'WakeWordDetector']
