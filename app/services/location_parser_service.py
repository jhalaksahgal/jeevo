import logging
from typing import Dict, Any, Optional
from app.ai.llm import MedicalLLM
logger = logging.getLogger(__name__)
class LocationParserService:
    """
    Service to parse natural language location input using LLM.
    Handles cases like "Dharavi, Mumbai" or "Village near Pune" and extracts
    city, state, and pincode information.
    """
    def __init__(self):
        self.llm = MedicalLLM()
    async def parse_location_from_text(self, raw_location_text: str, language: str = "en") -> Dict[str, Any]:
        """
        Parse raw location text using LLM to extract city, state, and pincode.
        Args:
            raw_location_text: User's natural language location input (e.g., "Dharavi, Mumbai")
            language: User's language code
        Returns:
            Dict with keys: success, city, state, pincode, confidence, raw_input
        """
        if not raw_location_text or not raw_location_text.strip():
            return {
                "success": False,
                "error": "Location text is empty",
                "city": None,
                "state": None,
                "pincode": None,
                "confidence": 0,
                "raw_input": raw_location_text
            }
        raw_location_text = raw_location_text.strip()
        parse_prompt = f"""You are a location parser for rural India. Extract location information from the following raw text.
User Input: "{raw_location_text}"
Your task is to:
1. Identify the CITY/VILLAGE/TOWN name (required)
2. Identify the STATE (required - must be a valid Indian state)
3. Try to infer PINCODE if not directly mentioned (optional)
Return ONLY a JSON object with this exact format (no markdown, no extra text):
{{
  "city": "extracted_city_name",
  "state": "extracted_state_name",
  "pincode": "extracted_or_inferred_pincode_or_null",
  "confidence": 0.95,
  "interpretation": "Brief explanation of what you understood"
}}
Rules:
- City/Village names should be properly capitalized
- State names must be official Indian state names (e.g., 'Maharashtra', 'Karnataka')
- If pincode is not mentioned, set to null
- Confidence should be between 0.0 and 1.0 based on how clearly the location was expressed
- Handle abbreviations (e.g., "UP" -> "Uttar Pradesh", "MH" -> "Maharashtra")
- Handle village names with nearby city context (e.g., "Village near Pune" -> city: "Pune")
User Language: {language}
If the input is in a non-English language, still output the JSON in English with proper state/city names."""
        try:
            logger.info(f"[LOCATION] Parsing: {raw_location_text}")
            response = self.llm.client.chat.completions.create(
                model=self.llm.model,
                messages=[
                    {"role": "user", "content": parse_prompt}
                ],
                temperature=0.3,  
                max_tokens=300
            )
            llm_response = response.choices[0].message.content.strip()
            logger.info(f"[LOCATION] LLM response: {llm_response}")
            import json
            try:
                parsed = json.loads(llm_response)
            except json.JSONDecodeError:
                import re
                json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
                if json_match:
                    parsed = json.loads(json_match.group())
                else:
                    logger.warning(f"[LOCATION] Could not extract JSON from LLM response: {llm_response}")
                    return {
                        "success": False,
                        "error": "Could not parse location from LLM response",
                        "city": None,
                        "state": None,
                        "pincode": None,
                        "confidence": 0,
                        "raw_input": raw_location_text
                    }
            city = parsed.get("city", "").strip()
            state = parsed.get("state", "").strip()
            pincode = parsed.get("pincode", "")
            confidence = float(parsed.get("confidence", 0))
            interpretation = parsed.get("interpretation", "")
            if not city or not state:
                logger.warning(f"[LOCATION] Missing city or state from LLM: city={city}, state={state}")
                return {
                    "success": False,
                    "error": f"Could not clearly identify location. Please provide: City/Village name and State",
                    "city": city if city else None,
                    "state": state if state else None,
                    "pincode": pincode if pincode else None,
                    "confidence": confidence,
                    "raw_input": raw_location_text,
                    "interpretation": interpretation
                }
            if pincode and pincode.lower() != "null":
                import re as regex_module
                if not regex_module.match(r'^\d{6}$', str(pincode)):
                    pincode = None  
            logger.info(f"[LOCATION] Successfully parsed: city={city}, state={state}, pincode={pincode}, confidence={confidence}")
            return {
                "success": True,
                "city": city,
                "state": state,
                "pincode": pincode if pincode and pincode.lower() != "null" else None,
                "confidence": confidence,
                "raw_input": raw_location_text,
                "interpretation": interpretation,
                "error": None
            }
        except json.JSONDecodeError as e:
            logger.error(f"[LOCATION] JSON parsing error: {e}")
            return {
                "success": False,
                "error": "Location parsing error. Please provide city and state separately.",
                "city": None,
                "state": None,
                "pincode": None,
                "confidence": 0,
                "raw_input": raw_location_text
            }
        except Exception as e:
            logger.error(f"[LOCATION] Error parsing location: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Location parsing failed: {str(e)}",
                "city": None,
                "state": None,
                "pincode": None,
                "confidence": 0,
                "raw_input": raw_location_text
            }
    async def parse_and_validate_location(
        self, raw_location_text: str, language: str = "en", min_confidence: float = 0.7
    ) -> Dict[str, Any]:
        """
        Parse location and validate it. Returns the parsed location if confidence is high enough.
        Args:
            raw_location_text: User's raw location input
            language: User's language code
            min_confidence: Minimum confidence threshold (0-1)
        Returns:
            Dict with success status and location details
        """
        parse_result = await self.parse_location_from_text(raw_location_text, language)
        if not parse_result["success"]:
            return parse_result
        confidence = parse_result.get("confidence", 0)
        if confidence < min_confidence:
            return {
                "success": False,
                "error": f"Could not clearly identify your location (confidence: {confidence:.0%}). Please provide: City/Village name and State",
                "city": parse_result.get("city"),
                "state": parse_result.get("state"),
                "pincode": parse_result.get("pincode"),
                "confidence": confidence,
                "raw_input": raw_location_text,
                "interpretation": parse_result.get("interpretation")
            }
        from app.utils.helpers import validate_user_location
        validation_result = validate_user_location(
            city=parse_result["city"],
            state=parse_result["state"],
            pincode=parse_result["pincode"]
        )
        if not validation_result["valid"]:
            return {
                "success": False,
                "error": "Location validation failed: " + "; ".join(validation_result["errors"]),
                "city": parse_result["city"],
                "state": parse_result["state"],
                "pincode": parse_result["pincode"],
                "confidence": confidence,
                "raw_input": raw_location_text,
                "interpretation": parse_result.get("interpretation")
            }
        return {
            "success": True,
            "city": validation_result["city"],
            "state": validation_result["state"],
            "pincode": validation_result["pincode"],
            "confidence": confidence,
            "raw_input": raw_location_text,
            "interpretation": parse_result.get("interpretation"),
            "error": None
        }
location_parser_service = LocationParserService()
