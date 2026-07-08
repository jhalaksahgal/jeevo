import logging
import os
from typing import Optional, Tuple
from app.ai.elevenlabs_tts import ElevenLabsTTS
logger = logging.getLogger(__name__)
class TTSFallbackService:
    def __init__(self):
        self.elevenlabs = ElevenLabsTTS()
        self.fallback_providers = []
        if self._can_use_gtts():
            self.fallback_providers.append("gtts")
        self.fallback_providers.append("silencio")
    def _can_use_gtts(self) -> bool:
        try:
            import gtts
            return True
        except ImportError:
            return False
    async def text_to_speech_with_fallback(
        self, 
        text: str, 
        language: str = "en",
        gender: str = "female"
    ) -> Tuple[Optional[bytes], str]:
        logger.info(f"[TTS] Attempting TTS with fallback chain for language: {language}")
        logger.info(f"[TTS] Text length: {len(text)} characters")
        try:
            logger.debug("[TTS] Trying ElevenLabs TTS...")
            audio_bytes = await self.elevenlabs.text_to_speech(text, language, gender)
            if not audio_bytes:
                logger.warning("[TTS] ElevenLabs returned empty audio bytes")
                raise Exception("Empty audio bytes from ElevenLabs")
            logger.info(f"[TTS] ✅ ElevenLabs TTS succeeded - Generated {len(audio_bytes)} bytes")
            return audio_bytes, "elevenlabs"
        except Exception as e:
            logger.warning(f"[TTS] ElevenLabs TTS failed: {e}")
        for provider in self.fallback_providers:
            try:
                if provider == "gtts":
                    logger.debug("[TTS] Trying Google TTS fallback...")
                    audio_bytes = self._gtts_generate(text, language)
                    if not audio_bytes:
                        logger.warning("[TTS] gTTS returned empty audio bytes")
                        continue
                    logger.info(f"[TTS] ✅ Google TTS succeeded - Generated {len(audio_bytes)} bytes")
                    return audio_bytes, "gtts"
            except Exception as e:
                logger.warning(f"[TTS] {provider} TTS failed: {e}")
                continue
        logger.error("[TTS] ❌ All TTS providers failed. No audio generated.")
        return None, "none"
    def _gtts_generate(self, text: str, language: str = "en") -> bytes:
        try:
            from gtts import gTTS
            from io import BytesIO
            lang_map = {
                "en": "en",
                "hi": "hi",
                "ta": "ta",
                "te": "te",
                "bn": "bn",
                "mr": "mr",
            }
            gtts_lang = lang_map.get(language, "en")
            tts = gTTS(text=text, lang=gtts_lang, slow=True)
            audio_buffer = BytesIO()
            tts.write_to_fp(audio_buffer)
            audio_buffer.seek(0)
            return audio_buffer.read()
        except Exception as e:
            logger.error(f"Google TTS error: {e}")
            raise
    async def save_audio_with_format(
        self,
        audio_bytes: bytes,
        filepath: str,
        format: str = "ogg"
    ) -> bool:
        try:
            if not audio_bytes:
                logger.warning("No audio bytes to save")
                return False
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "wb") as f:
                f.write(audio_bytes)
            logger.info(f"Saved audio ({format}) to {filepath}")
            return True
        except Exception as e:
            logger.error(f"Error saving audio: {e}")
            return False
tts_fallback_service = TTSFallbackService()
