import openai
import base64
from typing import Union
import os
import logging
logger = logging.getLogger(__name__)
VISION_SYSTEM_PROMPT = """You are a medical image analysis assistant for Jeevo health platform serving rural India. Your role is to:
1. ANALYZE MEDICAL IMAGES
   - Examine skin conditions, wounds, visible symptoms
   - Describe visible abnormalities in simple terms
   - Provide preliminary assessment (NOT a diagnosis)
   - Recommend professional medical consultation
2. COMMUNICATION
   - Use simple, non-technical language
   - Respond in the user's language
   - Be empathetic and reassuring
   - Avoid alarming users unnecessarily
3. SAFETY PROTOCOLS
   - Always disclaim that you're providing preliminary assessment only
   - Strongly recommend professional doctor consultation
   - Flag urgent symptoms (severe redness, pus, swelling, deformity)
   - For unclear images, ask for better photo or recommend in-person visit
4. LIMITATIONS
   - Cannot detect internal diseases from external images
   - Cannot provide definitive diagnosis
   - Cannot be used for legal/insurance purposes
   - Always defer to qualified doctors
5. RESPONSE FORMAT
   - Start with image quality assessment (clear/unclear)
   - Describe visible observations
   - Provide possible causes (not diagnosis)
   - Recommend next steps
   - Include medical disclaimer
   - Keep under 600 characters
Remember: This is preliminary assessment only. Always encourage professional consultation."""
class VisionAnalyzer:
    def __init__(self, api_key: str = None):
        use_groq = os.getenv("USE_GROQ", "false").lower() == "true"
        if use_groq:
            api_key = api_key or os.getenv("GROQ_API_KEY")
            self.client = openai.OpenAI(
                api_key=api_key,
                base_url="https://api.groq.com/openai/v1"
            )
            self.model = os.getenv("GROQ_VISION_MODEL", "llama-3.2-90b-vision-preview")
            logger.info(f"Initialized Vision analyzer with Groq: {self.model}")
        else:
            api_key = api_key or os.getenv("OPENAI_API_KEY")
            self.client = openai.OpenAI(api_key=api_key)
            self.model = os.getenv("OPENAI_VISION_MODEL", "gpt-4o-mini")
            logger.info(f"Initialized Vision analyzer with OpenAI: {self.model}")
    def analyze_image(self, image_path: str, query: str = "Analyze this medical image",
                     language: str = "en") -> str:
        language_names = {
            "en": "English",
            "hi": "Hindi (हिंदी)",
            "ta": "Tamil (தமிழ்)",
            "te": "Telugu (తెలుగు)",
            "bn": "Bengali (বাংলা)"
        }
        lang_name = language_names.get(language, "English")
        try:
            with open(image_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            logger.error(f"Error reading image {image_path}: {e}")
            return f"Error reading image: {str(e)}"
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": VISION_SYSTEM_PROMPT
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": query},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=600
            )
            logger.info("Successfully analyzed image")
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error analyzing image: {e}")
            return f"⚠️ Error analyzing image: {str(e)}"
    def analyze_from_url(self, image_url: str, query: str, language: str = "en") -> str:
        language_names = {
            "en": "English",
            "hi": "Hindi",
            "ta": "Tamil",
            "te": "Telugu"
        }
        lang_name = language_names.get(language, "English")
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": VISION_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": query},
                            {"type": "image_url", "image_url": {"url": image_url}}
                        ]
                    }
                ],
                max_tokens=600
            )
            logger.info("Successfully analyzed image from URL")
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error analyzing image from URL: {e}")
            return f"⚠️ Error: {str(e)}"
