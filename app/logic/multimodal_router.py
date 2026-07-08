from app.ai.llm import MedicalLLM
from app.ai.whisper_stt import WhisperSTT
from app.ai.elevenlabs_tts import ElevenLabsTTS
from app.ai.vision import VisionAnalyzer
from app.services.location_health_context import location_health_context
from app.services.symptom_checker_service import symptom_checker
from typing import Dict, Optional, List
import os
import logging
import asyncio
logger = logging.getLogger(__name__)
class MultimodalRouter:
    def __init__(self):
        try:
            self.llm = MedicalLLM()
            logger.info("✅ Medical LLM initialized")
            from app.services.intelligent_orchestrator import get_orchestrator
            self.orchestrator = get_orchestrator(self.llm.client, self.llm.model)
            logger.info("✅ Intelligent Orchestrator initialized")
        except Exception as e:
            logger.error(f"Failed to initialize LLM: {e}")
            self.llm = None
            self.orchestrator = None
        try:
            self.stt = WhisperSTT()
            logger.info("✅ Whisper STT initialized")
        except Exception as e:
            logger.error(f"Failed to initialize STT: {e}")
            self.stt = None
        try:
            self.tts = ElevenLabsTTS()
            if self.tts.client:
                logger.info("✅ ElevenLabs TTS initialized")
            else:
                logger.warning("⚠️ TTS not initialized (API key missing)")
                self.tts = None
        except Exception as e:
            logger.error(f"Failed to initialize TTS: {e}")
            self.tts = None
        try:
            self.vision = VisionAnalyzer()
            logger.info("✅ Vision analyzer initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Vision: {e}")
            self.vision = None
    async def process_text_message(self, text: str, language: str = "en", user_location: Dict = None, 
                                  user_id: int = None, family_members: List[Dict] = None,
                                  conversation_context: str = None) -> Dict:
        if not self.llm:
            return {
                "type": "text",
                "content": "⚠️ AI service temporarily unavailable. Please try again later.",
                "language": language
            }
        try:
            detected_symptom = symptom_checker.detect_symptom(text)
            location_context = ""
            if user_location:
                location_context = location_health_context.get_location_health_context(user_location)
            family_context = ""
            if family_members:
                family_info = ", ".join([f"{member.get('name', 'Unknown')} ({member.get('relation', '')}, Age: {member.get('age', '?')})" 
                                       for member in family_members if member])
                family_context = f"Family members: {family_info}\n"
            base_prompt = text
            if location_context:
                base_prompt = f"User Location Context:\n{location_context}\n\nUser Request:\n{text}"
            if family_context:
                base_prompt = family_context + base_prompt
            if conversation_context:
                base_prompt = f"Recent Conversation History:\n{conversation_context}\n\n{base_prompt}"
            if self.orchestrator and user_location:
                response_text = await self.orchestrator.process_with_tools(
                    base_prompt, 
                    language, 
                    user_location
                )
            else:
                response_text = await self.llm.get_medical_response(base_prompt, language)
            metadata = {
                "type": "text",
                "content": response_text,
                "language": language
            }
            if detected_symptom:
                metadata["detected_symptom"] = detected_symptom
                workflow = symptom_checker.get_assessment_flow(detected_symptom)
                if workflow:
                    metadata["symptom_workflow"] = workflow.get("name")
            return metadata
        except Exception as e:
            logger.error(f"Error processing text message: {e}")
            return {
                "type": "text",
                "content": "⚠️ Sorry, I encountered an error. Please try again.",
                "language": language
            }
    def process_voice_message(self, audio_file_path: str, language: str = "hi") -> Dict:
        if not self.stt or not self.llm:
            return {
                "type": "text",
                "content": "⚠️ Voice processing temporarily unavailable.",
                "language": language
            }
        try:
            with open(audio_file_path, "rb") as audio_file:
                transcription = await self.stt.detect_language_and_transcribe(audio_file)
            if "error" in transcription:
                return {"type": "error", "content": transcription["error"]}
            detected_language = transcription.get("language", language)
            user_text = transcription["text"]
            logger.info(f"Transcribed: '{user_text[:50]}...' in {detected_language}")
            response_text = await self.llm.get_medical_response(user_text, detected_language)
            audio_path = None
            if self.tts and self.tts.client:
                try:
                    audio_bytes = await self.tts.text_to_speech(
                        text=response_text,
                        language=detected_language,
                        gender="female"
                    )
                    output_path = f"temp/response_{os.urandom(8).hex()}.ogg"
                    os.makedirs("temp", exist_ok=True)
                    await self.tts.save_audio(audio_bytes, output_path)
                    audio_path = output_path
                    logger.info(f"Generated voice response at {audio_path}")
                except Exception as e:
                    logger.warning(f"TTS failed, sending text response: {e}")
            return {
                "type": "voice" if audio_path else "text",
                "audio_path": audio_path,
                "content": response_text,
                "transcription": user_text,
                "language": detected_language
            }
        except Exception as e:
            logger.error(f"Error processing voice message: {e}")
            return {
                "type": "text",
                "content": "⚠️ Could not process voice message. Please try again.",
                "language": language
            }
    def process_image_message(self, image_path: str, caption: str = "",
                             language: str = "en") -> Dict:
        if not self.vision:
            return {
                "type": "text",
                "content": "⚠️ Image analysis temporarily unavailable.",
                "language": language
            }
        try:
            query = caption if caption else "What do you see in this medical image? Provide guidance and assessment."
            analysis = self.vision.analyze_image(image_path, query, language)
            return {
                "type": "text",
                "content": analysis,
                "language": language,
                "original_image": image_path
            }
        except Exception as e:
            logger.error(f"Error processing image: {e}")
            return {
                "type": "text",
                "content": "⚠️ Could not analyze image. Please try again.",
                "language": language
            }
    async def route_message(self, message_type: str, content: str, caption: str = "",
                     language: str = "en", user_location: Dict = None,
                     user_id: int = None, family_members: List[Dict] = None,
                     conversation_context: str = None) -> Dict:
        logger.info(f"Routing {message_type} message in {language}")
        if message_type == "text":
            return await self.process_text_message(
                content, 
                language, 
                user_location,
                user_id=user_id,
                family_members=family_members,
                conversation_context=conversation_context
            )
        elif message_type == "audio" or message_type == "voice":
            return self.process_voice_message(content, language)
        elif message_type == "image":
            return self.process_image_message(content, caption, language)
        else:
            return {
                "type": "text",
                "content": f"⚠️ Sorry, {message_type} messages are not yet supported.",
                "language": language
            }
