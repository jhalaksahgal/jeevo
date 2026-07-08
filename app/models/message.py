from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime
class WhatsAppMessage(BaseModel):
    message_id: str
    from_number: str
    timestamp: str
    message_type: Literal["text", "audio", "image", "video", "document", "interactive", "location"]
    text_content: Optional[str] = None
    media_url: Optional[str] = None
    media_id: Optional[str] = None
    mime_type: Optional[str] = None
    class Config:
        json_schema_extra = {
            "example": {
                "message_id": "wamid.abc123",
                "from_number": "919876543210",
                "timestamp": "1234567890",
                "message_type": "text",
                "text_content": "Hello Jeevo"
            }
        }
class WhatsAppResponse(BaseModel):
    to_number: str
    message_type: Literal["text", "audio", "image"]
    content: str
    class Config:
        json_schema_extra = {
            "example": {
                "to_number": "919876543210",
                "message_type": "text",
                "content": "Hello! I'm Jeevo, your health assistant."
            }
        }
class WebhookVerification(BaseModel):
    mode: str = Field(alias="hub.mode")
    token: str = Field(alias="hub.verify_token")
    challenge: str = Field(alias="hub.challenge")
    class Config:
        populate_by_name = True
