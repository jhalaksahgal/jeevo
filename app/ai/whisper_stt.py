import openai
from typing import BinaryIO, Dict
import os
import logging
logger = logging.getLogger(__name__)
from app.ai.ai_client_factory import ai_client_factory
class WhisperSTT:
    def __init__(self, api_key: str = None):
        self.use_groq = os.getenv("USE_GROQ", "false").lower() == "true"
        if self.use_groq:
            self.client = ai_client_factory.get_groq_client()
            self.whisper_model = "whisper-large-v3-turbo"
            logger.info("Initialized Whisper STT with Groq")
        else:
            self.client = ai_client_factory.get_openai_client()
            self.whisper_model = "whisper-1"
            logger.info("Initialized Whisper STT with OpenAI")
    async def transcribe_audio(self, audio_file: BinaryIO, language: str = "hi") -> str:
        try:
            transcript = await self.client.audio.transcriptions.create(
                model=self.whisper_model,
                file=audio_file,
                language=language,
                response_format="text"
            )
            logger.info(f"Successfully transcribed audio in {language}")
            return transcript
        except Exception as e:
            logger.error(f"Error transcribing audio: {e}")
            return f"Error transcribing audio: {str(e)}"
    async def detect_language_and_transcribe(self, audio_file: BinaryIO) -> Dict:
        try:
            transcript = await self.client.audio.transcriptions.create(
                model=self.whisper_model,
                file=audio_file,
                response_format="verbose_json"
            )
            result = {
                "text": getattr(transcript, 'text', ''),
                "language": getattr(transcript, 'language', 'en')
            }
            if not isinstance(transcript, dict):
                try:
                    result["text"] = transcript.text
                    result["language"] = transcript.language
                except:
                    pass
            logger.info(f"Transcribed audio: detected language={result['language']}")
            return result
        except Exception as e:
            logger.error(f"Error in detect_language_and_transcribe: {e}")
            return {"text": "", "language": "en"}
