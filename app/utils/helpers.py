import logging
from typing import Dict, Any, Optional
import re
logger = logging.getLogger(__name__)
def is_valid_pincode(pincode: str) -> bool:
    if not pincode or not pincode.strip():
        return False
    pincode = pincode.strip()
    return bool(re.match(r'^\d{6}$', pincode))
def is_valid_phone_number(phone_number: str) -> bool:
    if not phone_number or len(phone_number) < 5:
        return False
    return phone_number.isdigit() or (phone_number.startswith('+') and phone_number[1:].isdigit())
def validate_user_location(city: Optional[str], state: Optional[str], pincode: Optional[str] = None) -> Dict[str, Any]:
    errors = []
    if not city or not city.strip():
        errors.append("City is required")
    elif len(city.strip()) < 2:
        errors.append("City name too short")
    if not state or not state.strip():
        errors.append("State is required")
    elif len(state.strip()) < 2:
        errors.append("State name too short")
    if pincode and not is_valid_pincode(pincode):
        errors.append("Invalid PIN code format (should be 6 digits)")
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "city": city.strip() if city else None,
        "state": state.strip() if state else None,
        "pincode": pincode.strip() if pincode else None
    }
def sanitize_user_input(text: str, max_length: int = 2000) -> str:
    if not text:
        return ""
    text = text.strip()
    if len(text) > max_length:
        logger.warning(f"Input truncated from {len(text)} to {max_length} characters")
        text = text[:max_length]
    return text
def generate_welcome_message(user_name: str = None) -> str:
    if user_name:
        return f"🙏 Namaste {user_name}! Welcome to Jeevo - your personal health assistant.\n\n"               f"I can help you with:\n"               f"✅ Health queries (text, voice, or images)\n"               f"✅ Medical reminders\n"               f"✅ Local health alerts\n\n"               f"How can I assist you today?"
    else:
        return "🙏 Namaste! Welcome to Jeevo - your personal health assistant.\n\n"               "I can help you with:\n"               "✅ Health queries (text, voice, or images)\n"               "✅ Medical reminders\n"               "✅ Local health alerts\n\n"               "How can I assist you today?"
def generate_echo_response(message_type: str, content: str = None) -> str:
    responses = {
        "text": f"📝 I received your text message: '{content}'\n\n⚠️ AI features coming soon!",
        "audio": "🎤 I received your voice message!\n\n⚠️ Voice processing coming soon!",
        "image": "📸 I received your image!\n\n⚠️ Image analysis coming soon!",
        "video": "🎥 I received your video!\n\n⚠️ Video processing coming soon!",
        "document": "📄 I received your document!\n\n⚠️ Document processing coming soon!"
    }
    return responses.get(message_type, "✅ Message received!")
def add_medical_disclaimer(response: str) -> str:
    disclaimer = "⚠️ This is AI-generated guidance. Please consult a qualified doctor for serious health issues."
    return f"{response}\n\n{disclaimer}"
def is_webhook_valid(webhook_data: Dict[str, Any]) -> bool:
    try:
        required_keys = ["entry"]
        if not all(key in webhook_data for key in required_keys):
            return False
        entry = webhook_data["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]
        if "messages" in value:
            return True
        if "statuses" in value:
            return True
        return False
    except (KeyError, IndexError, TypeError):
        return False
def log_incoming_message(message: 'WhatsAppMessage') -> None:
    logger.info(f"[INCOMING] Type: {message.message_type} | From: {message.from_number} | ID: {message.message_id}")
    if message.text_content:
        logger.info(f"[CONTENT] {message.text_content}")
