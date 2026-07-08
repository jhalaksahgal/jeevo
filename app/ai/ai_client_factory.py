import os
import logging
from typing import Optional
from openai import AsyncOpenAI
from elevenlabs.client import ElevenLabs
logger = logging.getLogger(__name__)
class AIClientFactory:
    _instance = None
    _async_openai_client: Optional[AsyncOpenAI] = None
    _elevenlabs_client: Optional[ElevenLabs] = None
    _groq_client: Optional[AsyncOpenAI] = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    @classmethod
    def get_openai_client(cls) -> AsyncOpenAI:
        if cls._async_openai_client is None:
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                cls._async_openai_client = AsyncOpenAI(api_key=api_key)
            else:
                logger.warning("OPENAI_API_KEY not found.")
        return cls._async_openai_client
    @classmethod
    def get_groq_client(cls) -> AsyncOpenAI:
        if cls._groq_client is None:
            api_key = os.getenv("GROQ_API_KEY")
            if api_key:
                cls._groq_client = AsyncOpenAI(
                    api_key=api_key,
                    base_url="https://api.groq.com/openai/v1"
                )
            else:
                logger.warning("GROQ_API_KEY not found.")
        return cls._groq_client
    @classmethod
    def get_elevenlabs_client(cls) -> ElevenLabs:
        if cls._elevenlabs_client is None:
            api_key = os.getenv("ELEVENLABS_API_KEY")
            if api_key:
                cls._elevenlabs_client = ElevenLabs(api_key=api_key)
            else:
                logger.warning("ELEVENLABS_API_KEY not found.")
        return cls._elevenlabs_client
ai_client_factory = AIClientFactory()
