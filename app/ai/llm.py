import openai
from typing import Optional
import os
import logging
logger = logging.getLogger(__name__)
MEDICAL_SYSTEM_PROMPT = """You are Jeevo, a qualified medical health assistant for rural India. Your role is to:
1. PROVIDE HEALTH GUIDANCE
   - Offer symptom assessment and preliminary health advice
   - Connect local health issues to prevention and treatment
   - Always recommend professional medical consultation for serious conditions
2. COMMUNICATION STYLE
   - Be empathetic, clear, and use simple language
   - Respond in the user's language
   - Use emojis to make responses friendly and accessible
   - Break information into digestible chunks
3. SAFETY GUIDELINES
   - Always include medical disclaimers
   - Recommend visiting a doctor for persistent symptoms
   - Never replace professional medical advice
   - Escalate emergency cases (chest pain, difficulty breathing, severe bleeding) to call 108
4. CONTEXT AWARENESS
   - Consider local health issues (malaria in monsoon, heatstroke in summer)
   - Know about immunization schedules in India
   - Provide information suitable for resource-limited settings
5. MULTILINGUAL
   - Support 10 Indian languages (English, Hindi, Tamil, Telugu, Bengali, Marathi, Gujarati, Kannada, Malayalam, Punjabi)
   - Translate medical terms accurately
   - Respect cultural health practices
6. RESPONSE FORMAT
   - Keep responses under 600 characters
   - Use structured text with bullet points
   - End with clear next steps
   - Include relevant emojis
Remember: You are a health assistant, not a doctor. Always encourage professional consultation."""
from app.ai.ai_client_factory import ai_client_factory
class MedicalLLM:
    def __init__(self, api_key: str = None):
        self.use_groq = os.getenv("USE_GROQ", "false").lower() == "true"
        if self.use_groq:
            self.client = ai_client_factory.get_groq_client()
            self.model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
            logger.info(f"Initialized Medical LLM with Groq: {self.model}")
        else:
            self.client = ai_client_factory.get_openai_client()
            self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            logger.info(f"Initialized Medical LLM with OpenAI: {self.model}")
    async def get_medical_response(self, user_message: str, language: str = "en") -> str:
        if not self.client:
            return "⚠️ Sorry, AI client is not configured properly."
        language_names = {
            "en": "English",
            "hi": "Hindi (हिंदी)",
            "bn": "Bengali (বাংলা)",
            "te": "Telugu (తెలుగు)",
            "mr": "Marathi (मराठी)",
            "ta": "Tamil (தமிழ்)",
            "gu": "Gujarati (ગુજરાતી)",
            "kn": "Kannada (ಕನ್ನಡ)",
            "ml": "Malayalam (മലയാളം)",
            "pa": "Punjabi (ਪੰਜਾਬੀ)",
        }
        lang_name = language_names.get(language, "English")
        language_instruction = f"Please respond in {lang_name}. If you cannot, reply in English and mark that translation was necessary."
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": MEDICAL_SYSTEM_PROMPT},
                    {"role": "system", "content": language_instruction},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.7,
                max_tokens=600
            )
            try:
                return response.choices[0].message.content
            except Exception:
                return getattr(response.choices[0].message, 'content', str(response))
        except Exception as e:
            logger.error(f"Error generating LLM response: {e}")
            return "⚠️ Sorry, I encountered an error processing your request. Please try again."
    async def get_medical_reply(self, user_message: str, language: str = "en") -> str:
        return await self.get_medical_response(user_message, language)
