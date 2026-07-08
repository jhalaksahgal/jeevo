from elevenlabs import VoiceSettings
from app.ai.ai_client_factory import ai_client_factory
from typing import Optional
import os
import logging
import asyncio
logger = logging.getLogger(__name__)
class ElevenLabsTTS:
    def __init__(self, api_key: str = None):
        self.client = ai_client_factory.get_elevenlabs_client()
        self.voices = {
            "en_female": "21m00Tcm4TlvDq8ikWAM",
            "en_male": "ErXwobaYiN019PkySvjV",
        }
        self.default_indian_voice = "pNInz6obpgDQGcFmaJgB"
        self.speech_speed_multiplier = 0.85
        self.voice_stability = 0.5
        self.voice_similarity = 0.75
        logger.info("Initialized ElevenLabs TTS")
    def _sync_tts_call(self, text: str, voice_id: str) -> bytes:
        audio = self.client.text_to_speech.convert(
            text=text,
            voice_id=voice_id,
            model_id="eleven_multilingual_v2",
            voice_settings=VoiceSettings(
                stability=self.voice_stability,
                similarity_boost=self.voice_similarity,
                style=0.0,
                use_speaker_boost=True
            )
        )
        return b"".join(audio)
    async def text_to_speech(self, text: str, language: str = "en", gender: str = "female") -> bytes:
        if not self.client:
            raise Exception("ElevenLabs client not initialized. Check API key.")
        voice_key = f"{language}_{gender}"
        voice_id = self.voices.get(voice_key, self.default_indian_voice)
        try:
            audio_bytes = await asyncio.to_thread(self._sync_tts_call, text, voice_id)
            logger.info(f"Generated TTS audio: {len(audio_bytes)} bytes")
            return audio_bytes
        except Exception as e:
            logger.error(f"TTS error: {e}")
            raise Exception(f"TTS error: {str(e)}")
    async def save_audio(self, audio_bytes: bytes, filepath: str):
        try:
            def _write_file():
                with open(filepath, "wb") as f:
                    f.write(audio_bytes)
            await asyncio.to_thread(_write_file)
            logger.info(f"Saved audio to {filepath}")
        except Exception as e:
            logger.error(f"Error saving audio: {e}")
            raise
