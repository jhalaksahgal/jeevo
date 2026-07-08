import httpx
import logging
import os
import asyncio
from typing import Dict, Any, List
from app.config.settings import settings
from app.models.message import WhatsAppMessage, WhatsAppResponse
logger = logging.getLogger(__name__)
class WhatsAppService:
    def __init__(self):
        self.api_url = settings.WHATSAPP_API_URL
        self.phone_number_id = settings.WHATSAPP_PHONE_NUMBER_ID
        self.access_token = settings.WHATSAPP_ACCESS_TOKEN
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
    def parse_incoming_message(self, webhook_data: Dict[str, Any]) -> WhatsAppMessage:
        try:
            entry = webhook_data["entry"][0]
            changes = entry["changes"][0]
            value = changes["value"]
            message_data = value["messages"][0]
            message_id = message_data["id"]
            from_number = message_data["from"]
            timestamp = message_data["timestamp"]
            message_type = message_data["type"]
            text_content = None
            media_url = None
            media_id = None
            mime_type = None
            if message_type == "text":
                text_content = message_data["text"]["body"]
            elif message_type == "interactive":
                interactive = message_data.get("interactive", {})
                interaction_type = interactive.get("type")
                text_content = ""
                if interaction_type == "button_reply":
                    btn_reply = interactive.get("button_reply", {})
                    btn_id = btn_reply.get("id", "")
                    if btn_id.startswith("btn_"):
                        try:
                            idx = int(btn_id.replace("btn_", ""))
                            text_content = str(idx + 1)  
                        except (ValueError, IndexError):
                            text_content = btn_reply.get("title", "")
                    else:
                        text_content = btn_reply.get("title", "")
                elif interaction_type == "list_reply":
                    list_reply = interactive.get("list_reply", {})
                    list_id = list_reply.get("id", "")
                    if list_id.startswith("option_"):
                        try:
                            idx = int(list_id.replace("option_", ""))
                            text_content = str(idx + 1)  
                        except (ValueError, IndexError):
                            text_content = list_reply.get("title", "")
                    else:
                        text_content = list_reply.get("title", "")
                else:
                    text_content = interactive.get("body", {}).get("text", "")
                message_type = "text"
            elif message_type == "audio":
                media_id = message_data["audio"]["id"]
                mime_type = message_data["audio"]["mime_type"]
            elif message_type == "image":
                media_id = message_data["image"]["id"]
                mime_type = message_data["image"]["mime_type"]
                text_content = message_data["image"].get("caption")
            elif message_type == "location":
                loc = message_data.get("location", {})
                lat = loc.get("latitude")
                lon = loc.get("longitude")
                name = loc.get("name")
                address = loc.get("address")
                parts = []
                if name:
                    parts.append(name)
                if address:
                    parts.append(address)
                if lat and lon:
                    parts.append(f"{lat},{lon}")
                text_content = " - ".join(parts) if parts else ""
                message_type = "text"
            elif message_type == "video":
                media_id = message_data["video"]["id"]
                mime_type = message_data["video"]["mime_type"]
            elif message_type == "document":
                media_id = message_data["document"]["id"]
                mime_type = message_data["document"]["mime_type"]
            return WhatsAppMessage(
                message_id=message_id,
                from_number=from_number,
                timestamp=timestamp,
                message_type=message_type,
                text_content=text_content,
                media_url=media_url,
                media_id=media_id,
                mime_type=mime_type
            )
        except (KeyError, IndexError) as e:
            logger.error(f"Error parsing webhook data: {e}")
            raise ValueError(f"Invalid webhook data structure: {e}")
    async def send_text_message(self, to_number: str, text: str) -> Dict[str, Any]:
        url = f"{self.api_url}/{self.phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_number,
            "type": "text",
            "text": {
                "preview_url": False,
                "body": text
            }
        }
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url,
                    headers=self.headers,
                    json=payload,
                    timeout=30.0
                )
                response.raise_for_status()
                logger.info(f"Message sent to {to_number}")
                return response.json()
            except httpx.HTTPError as e:
                logger.error(f"Error sending message: {e}")
                raise
    async def send_audio_message(self, to_number: str, audio_path: str = None, audio_url: str = None) -> Dict[str, Any]:
        url = f"{self.api_url}/{self.phone_number_id}/messages"
        uploaded_media_id = None
        if audio_path and not audio_url:
            try:
                logger.info(f"[AUDIO] Uploading audio file: {audio_path}")
                if not os.path.exists(audio_path):
                    raise FileNotFoundError(f"Audio file not found: {audio_path}")
                file_size = os.path.getsize(audio_path)
                logger.info(f"[AUDIO] File size: {file_size} bytes")
                if file_size < 100:
                    logger.error(f"[AUDIO] Audio file too small ({file_size} bytes) - likely corrupted")
                    raise ValueError(f"Audio file too small ({file_size} bytes)")
                if file_size > 16000000:  
                    logger.error(f"[AUDIO] Audio file too large ({file_size} bytes) - exceeds 16MB limit")
                    raise ValueError(f"Audio file too large ({file_size} bytes) - max 16MB")
                file_ext = os.path.splitext(audio_path)[1].lower()
                mime_type = "audio/ogg" if file_ext == ".ogg" else "audio/mpeg"
                logger.info(f"[AUDIO] File type: {file_ext}, MIME: {mime_type}")
                with open(audio_path, "rb") as audio_file:
                    audio_content = audio_file.read()
                    upload_url = f"{self.api_url}/{self.phone_number_id}/media"
                    logger.debug(f"[AUDIO] Uploading to: {upload_url}")
                    files = {
                        "file": (os.path.basename(audio_path), audio_content, mime_type)
                    }
                    async with httpx.AsyncClient() as client:
                        upload_response = await client.post(
                            upload_url,
                            headers={
                                "Authorization": self.headers["Authorization"],
                            },
                            data={"messaging_product": "whatsapp"},
                            files=files,
                            timeout=120.0
                        )
                        logger.info(f"[AUDIO] Upload response status: {upload_response.status_code}")
                        if upload_response.status_code not in [200, 201]:
                            error_detail = upload_response.text
                            logger.error(f"[AUDIO] Upload failed with status {upload_response.status_code}")
                            logger.error(f"[AUDIO] Response: {error_detail}")
                            try:
                                error_json = upload_response.json()
                                whatsapp_error = error_json.get("error", {})
                                logger.error(f"[AUDIO] WhatsApp error: {whatsapp_error}")
                            except:
                                pass
                            raise ValueError(f"Media upload failed with status {upload_response.status_code}: {error_detail}")
                        upload_data = upload_response.json()
                        logger.debug(f"[AUDIO] Upload response: {upload_data}")
                        media_id = upload_data.get("id") or upload_data.get("h")
                        if not media_id:
                            logger.error(f"[AUDIO] No media ID in response: {upload_data}")
                            raise ValueError(f"Failed to get media ID from upload response")
                        logger.info(f"[AUDIO] ✅ Audio uploaded successfully with ID: {media_id}")
                        uploaded_media_id = media_id
            except FileNotFoundError as e:
                logger.error(f"[AUDIO] File error: {e}")
                raise ValueError(f"Audio file not found: {str(e)}")
            except Exception as e:
                logger.error(f"[AUDIO] Error uploading audio file: {e}", exc_info=True)
                raise ValueError(f"Could not upload audio file: {str(e)}")
        if not uploaded_media_id and not audio_url:
            raise ValueError("Must provide either audio_path or audio_url")
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_number,
            "type": "audio",
        }
        is_voice_native = False
        try:
            if audio_path and isinstance(audio_path, str) and audio_path.lower().endswith('.ogg'):
                is_voice_native = True
            elif audio_url and isinstance(audio_url, str) and audio_url.lower().endswith('.ogg'):
                is_voice_native = True
        except Exception:
            is_voice_native = False
        if uploaded_media_id:
            logger.info(f"[AUDIO] Using uploaded media ID: {uploaded_media_id}")
            audio_obj = {"id": uploaded_media_id}
            if is_voice_native:
                audio_obj["voice"] = True
            payload["audio"] = audio_obj
        elif audio_url:
            logger.info(f"[AUDIO] Using media URL")
            audio_obj = {"link": audio_url}
            if is_voice_native:
                audio_obj["voice"] = True
            payload["audio"] = audio_obj
        else:
            raise ValueError("[AUDIO] No media ID or URL available for sending")
        async with httpx.AsyncClient() as client:
            try:
                logger.info(f"[AUDIO] Sending audio message to {to_number}")
                logger.debug(f"[AUDIO] Payload: {payload}")
                response = await client.post(
                    url,
                    headers=self.headers,
                    json=payload,
                    timeout=30.0
                )
                response.raise_for_status()
                logger.info(f"[AUDIO] ✅ Audio message sent successfully to {to_number}")
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"[AUDIO] Error sending audio message: {e}")
                logger.error(f"[AUDIO] Response status: {e.response.status_code}")
                logger.error(f"[AUDIO] Response text: {e.response.text}")
                raise
            except httpx.HTTPError as e:
                logger.error(f"[AUDIO] Error sending audio message: {e}", exc_info=True)
                raise
    async def download_media(self, media_id: str, media_type: str) -> str:
        try:
            media_url_endpoint = f"{self.api_url}/{media_id}"
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    media_url_endpoint,
                    headers=self.headers,
                    timeout=30.0
                )
                response.raise_for_status()
                media_info = response.json()
                media_url = media_info.get("url")
                if not media_url:
                    raise ValueError("Media URL not found in response")
                media_response = await client.get(
                    media_url,
                    headers=self.headers,
                    timeout=60.0
                )
                media_response.raise_for_status()
                extension_map = {
                    "audio": "ogg",
                    "image": "jpg",
                    "video": "mp4",
                    "document": "pdf"
                }
                extension = extension_map.get(media_type, "bin")
                os.makedirs("temp", exist_ok=True)
                filepath = f"temp/media_{media_id}.{extension}"
                with open(filepath, "wb") as f:
                    f.write(media_response.content)
                logger.info(f"Downloaded {media_type} to {filepath}")
                return filepath
        except Exception as e:
            logger.error(f"Error downloading media {media_id}: {e}")
            raise
    async def mark_message_as_read(self, message_id: str) -> Dict[str, Any]:
        url = f"{self.api_url}/{self.phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id
        }
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url,
                    headers=self.headers,
                    json=payload,
                    timeout=30.0
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                logger.error(f"Error marking message as read: {e}")
                raise
    async def send_message_with_suggestions(
        self, 
        to_number: str, 
        text: str,
        suggestions: List[str] = None
    ) -> Dict[str, Any]:
        url = f"{self.api_url}/{self.phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_number,
            "type": "text",
            "text": {
                "preview_url": False,
                "body": text
            }
        }
        if suggestions:
            payload["type"] = "interactive"
            payload["interactive"] = {
                "type": "button",
                "body": {"text": text},
                "action": {
                    "buttons": [
                        {
                            "type": "reply",
                            "reply": {
                                "id": f"btn_{i}",
                                "title": suggestion[:20]
                            }
                        }
                        for i, suggestion in enumerate(suggestions[:3])
                    ]
                }
            }
            payload.pop("text")
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url,
                    headers=self.headers,
                    json=payload,
                    timeout=30.0
                )
                response.raise_for_status()
                logger.info(f"Interactive message sent to {to_number}")
                return response.json()
            except httpx.HTTPError as e:
                logger.error(f"Error sending interactive message: {e}")
                raise
whatsapp_service = WhatsAppService()
