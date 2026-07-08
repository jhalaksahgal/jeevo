import logging
import os
from typing import Tuple, Optional
from app.services.whatsapp_service import whatsapp_service
from app.ai.whisper_stt import WhisperSTT
from app.models.message import WhatsAppMessage
logger = logging.getLogger(__name__)
class AudioTranscriptionHelper:
    @staticmethod
    async def download_and_transcribe(message: WhatsAppMessage) -> Tuple[Optional[str], Optional[str]]:
        """
        Downloads audio media from a WhatsAppMessage and transcribes it.
        Returns a tuple of (transcribed_text, detected_language).
        """
        if message.message_type != "audio" or not message.media_id:
            return None, None
        try:
            audio_path = await whatsapp_service.download_media(message.media_id, message.message_type)
            stt = WhisperSTT()
            with open(audio_path, "rb") as af:
                stt_result = await stt.detect_language_and_transcribe(af)
            try:
                os.remove(audio_path)
            except Exception as e:
                logger.warning(f"Could not remove temp audio file {audio_path}: {e}")
            if isinstance(stt_result, dict) and stt_result.get("text"):
                return stt_result.get("text"), stt_result.get("language")
            return None, None
        except Exception as e:
            logger.error(f"Error in download_and_transcribe: {e}")
            return None, None
audio_helper = AudioTranscriptionHelper()
