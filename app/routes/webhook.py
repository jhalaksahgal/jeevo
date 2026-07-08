from fastapi import APIRouter, Request, HTTPException, Query, Depends
from fastapi.responses import PlainTextResponse
from typing import Dict, Any
import logging
import os
import time
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.settings import settings
from app.models.message import WhatsAppMessage
from app.services.whatsapp_service import whatsapp_service
from app.services.cache_service import cache_service
from app.database.base import get_db
from app.database.repositories import UserRepository, ConversationRepository, FamilyMemberRepository
from app.logic.multimodal_router import MultimodalRouter
from app.logic.language_manager import LanguageManager
from app.services.jeevo_onboarding import jeevo_onboarding
from app.services.service_handlers import (
    HealthSupportService,
    FamilyCareService,
    VaccinationService,
    HospitalFinderService,
    EnvironmentalAlertService
)
from app.services.heatmap_update_service import HeatmapUpdateService
from app.services.risk_alert_service import RiskAlertService
from app.services.risk_aggregation_service import RiskAggregationService
from app.services.vaccine_reminder_service import VaccineReminderService
from app.services.anganwadi_finder_service import AnganwadiFinderService
from app.services.location_parser_service import location_parser_service
from app.ai.whisper_stt import WhisperSTT
from app.utils.audio_helper import audio_helper
from app.routes.command_router import CommandRouter
from app.utils.helpers import (
    is_webhook_valid,
    log_incoming_message,
    validate_user_location,
    sanitize_user_input
)
logger = logging.getLogger(__name__)
router = APIRouter()
multimodal_router = MultimodalRouter()
language_manager = LanguageManager()
async def complete_onboarding(phone_number: str, db: AsyncSession):
    """Mark user as onboarded and clean up all cache keys to prevent state inconsistency"""
    try:
        await UserRepository(db).update_user(phone_number, is_onboarded=True)
        keys_to_delete = [
            f"onboarding_stage:{phone_number}",
            f"onboarding_lang:{phone_number}",
            f"onboarding_name:{phone_number}",
        ]
        for key in keys_to_delete:
            try:
                await cache_service.delete(key)
            except:
                pass
        logger.info(f"[ONBOARDING] ✅ Completed for {phone_number} - marked onboarded and cache cleared")
    except Exception as e:
        logger.error(f"[ONBOARDING] Error completing onboarding: {e}")
@router.get("/webhook", response_class=PlainTextResponse)
async def verify_webhook(
    request: Request,
    mode: str = Query(alias="hub.mode"),
    token: str = Query(alias="hub.verify_token"),
    challenge: str = Query(alias="hub.challenge")
):
    logger.info(f"[WEBHOOK VERIFICATION] Mode: {mode}, Token received: {token[:10]}...")
    if mode == "subscribe" and token == settings.WEBHOOK_VERIFY_TOKEN:
        logger.info("[WEBHOOK VERIFICATION] ✅ Success - Returning challenge")
        return challenge
    else:
        logger.warning("[WEBHOOK VERIFICATION] ❌ Failed - Invalid token")
        raise HTTPException(status_code=403, detail="Verification token mismatch")
@router.post("/webhook")
async def receive_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    try:
        webhook_data: Dict[str, Any] = await request.json()
        logger.info("[WEBHOOK] Received data")
        if not is_webhook_valid(webhook_data):
            logger.warning("[WEBHOOK] Invalid webhook structure")
            return {"status": "ignored", "reason": "invalid_structure"}
        entry = webhook_data["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]
        if "statuses" in value:
            logger.info("[WEBHOOK] Status update received - ignoring")
            return {"status": "ok", "type": "status_update"}
        try:
            message = whatsapp_service.parse_incoming_message(webhook_data)
            log_incoming_message(message)
        except ValueError as e:
            logger.error(f"[WEBHOOK] Error parsing message: {e}")
            return {"status": "error", "message": str(e)}
        try:
            await whatsapp_service.mark_message_as_read(message.message_id)
        except Exception as e:
            logger.warning(f"[WEBHOOK] Could not mark message as read: {e}")
        await process_message(message, db)
        return {"status": "ok", "message_id": message.message_id}
    except Exception as e:
        logger.error(f"[WEBHOOK] Unexpected error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}
async def process_message(message: WhatsAppMessage, db: AsyncSession) -> None:
    start_time = time.time()
    try:
        user = await UserRepository(db).get_by_phone_number(message.from_number)
        is_new = False
        if not user:
            is_new = True
            user = await UserRepository(db).create_user(phone_number=message.from_number)
            logger.info(f"[USER] New user created: {message.from_number}")
            await whatsapp_service.send_text_message(
                to_number=message.from_number,
                text=jeevo_onboarding.welcome_message()
            )
            await cache_service.set(f"onboarding_stage:{message.from_number}", "language_selection", 600)
            return
        else:
            logger.info(f"[USER] Existing user: {message.from_number}")
        onboarding_stage = await cache_service.get(f"onboarding_stage:{message.from_number}")
        if onboarding_stage:
            text = message.text_content.strip() if (message.message_type == "text" and message.text_content) else ""
            if onboarding_stage == "language_selection":
                lang_code = jeevo_onboarding.get_language_from_number(text)
                if lang_code:
                    await UserRepository(db).update_user(message.from_number, language=lang_code)
                    await cache_service.set(f"onboarding_lang:{message.from_number}", lang_code, 600)
                    await cache_service.set(f"onboarding_stage:{message.from_number}", "name_collection", 600)
                    await whatsapp_service.send_text_message(
                        to_number=message.from_number,
                        text=jeevo_onboarding.get_name_request(lang_code)
                    )
                    return
                else:
                    await whatsapp_service.send_text_message(
                        to_number=message.from_number,
                        text="❌ Invalid. Reply with number 1-10"
                    )
                    return
            elif onboarding_stage == "name_collection":
                if message.message_type == "audio" and message.media_id:
                    try:
                        transcript, detected_lang = await audio_helper.download_and_transcribe(message)
                        if not detected_lang:
                            detected_lang = (await cache_service.get(f"onboarding_lang:{message.from_number}")) or "en"
                        if transcript:
                            name = None
                            lower = transcript.lower()
                            if "my name is" in lower:
                                name = transcript.partition("my name is")[-1].strip().split("\n")[0]
                            elif "मेरा नाम" in transcript:
                                name = transcript.partition("मेरा नाम")[-1].strip().split("\n")[0]
                            if not name:
                                first_line = transcript.strip().split("\n")[0]
                                if 1 < len(first_line) <= 60:
                                    name = first_line
                            if name:
                                await UserRepository(db).update_user(message.from_number, name=name)
                                await cache_service.set(f"onboarding_name:{message.from_number}", name, 600)
                                await cache_service.set(f"onboarding_stage:{message.from_number}", "location_collection", 600)
                                lang = await cache_service.get(f"onboarding_lang:{message.from_number}") or detected_lang or "en"
                                await whatsapp_service.send_text_message(
                                    to_number=message.from_number,
                                    text=jeevo_onboarding.get_location_request(lang)
                                )
                                return
                            await whatsapp_service.send_text_message(
                                to_number=message.from_number,
                                text="❌ Could not detect your name from the voice note. Please type your name or try again."
                            )
                            return
                        else:
                            await whatsapp_service.send_text_message(
                                to_number=message.from_number,
                                text="⚠️ Couldn't transcribe your audio. Please type your name."
                            )
                            return
                    except Exception as e:
                        logger.error(f"[ONBOARDING][VOICE] Error processing voice for name collection: {e}")
                        await whatsapp_service.send_text_message(
                            to_number=message.from_number,
                            text="⚠️ Error processing your voice message. Please type your name."
                        )
                        return
                name = text
                await UserRepository(db).update_user(message.from_number, name=name)
                await cache_service.set(f"onboarding_name:{message.from_number}", name, 600)
                await cache_service.set(f"onboarding_stage:{message.from_number}", "location_collection", 600)
                lang = await cache_service.get(f"onboarding_lang:{message.from_number}") or "en"
                await whatsapp_service.send_text_message(
                    to_number=message.from_number,
                    text=jeevo_onboarding.get_location_request(lang)
                )
                return
            elif onboarding_stage == "location_collection":
                user_lang = await cache_service.get(f"onboarding_lang:{message.from_number}") or "en"
                location_text = text
                if message.message_type == "audio" and message.media_id:
                    try:
                        location_text, det_lang = await audio_helper.download_and_transcribe(message)
                        if location_text:
                            user_lang = det_lang or user_lang
                        else:
                            await whatsapp_service.send_text_message(
                                to_number=message.from_number,
                                text=jeevo_onboarding.get_location_request(user_lang)
                            )
                            return
                    except Exception as e:
                        logger.error(f"[ONBOARDING][VOICE] Error processing voice for location: {e}")
                        await whatsapp_service.send_text_message(
                            to_number=message.from_number,
                            text=jeevo_onboarding.get_location_request(user_lang)
                        )
                        return
                logger.info(f"[LOCATION] Parsing user input: {location_text}")
                parse_result = await location_parser_service.parse_and_validate_location(location_text, language=user_lang)
                if not parse_result["success"]:
                    error_message = parse_result.get("error", "Could not understand your location.")
                    logger.warning(f"[LOCATION] Parse failed: {error_message}")
                    await whatsapp_service.send_text_message(
                        to_number=message.from_number,
                        text=f"❌ {error_message}"
                    )
                    hint_message = {
                        "en": "💡 Try again with format like: 'Dharavi, Mumbai' or 'Village XYZ, Maharashtra'",
                        "hi": "💡 इस तरह कोशिश करें: 'धारावी, मुंबई' या 'गांव XYZ, महाराष्ट्र'"
                    }
                    await whatsapp_service.send_text_message(
                        to_number=message.from_number,
                        text=hint_message.get(user_lang, hint_message["en"])
                    )
                    return
                logger.info(f"[LOCATION] ✅ Parsed: city={parse_result['city']}, state={parse_result['state']}, pincode={parse_result['pincode']}")
                await UserRepository(db).update_user(
                    message.from_number,
                    city=parse_result["city"],
                    state=parse_result["state"],
                    pincode=parse_result["pincode"]
                )
                confirm_message = f"✅ Got it! You're in {parse_result['city']}, {parse_result['state']}"
                if parse_result.get("interpretation"):
                    confirm_message += f"\n({parse_result['interpretation']})"
                await whatsapp_service.send_text_message(
                    to_number=message.from_number,
                    text=confirm_message
                )
                location = {"city": parse_result["city"], "state": parse_result["state"]}
                hospitals = await HospitalFinderService.find_hospitals(location)
                name = await cache_service.get(f"onboarding_name:{message.from_number}") or "User"
                await cache_service.set(f"onboarding_stage:{message.from_number}", "service_selection", 600)
                await whatsapp_service.send_text_message(
                    to_number=message.from_number,
                    text=jeevo_onboarding.get_service_selection(user_lang, name)
                )
                return
            elif onboarding_stage == "profile_update_selection":
                profile_option = text.strip()
                lang = await cache_service.get(f"onboarding_lang:{message.from_number}") or "en"
                if profile_option == "1":
                    await cache_service.set(f"onboarding_stage:{message.from_number}", "updating_location", 600)
                    await whatsapp_service.send_text_message(
                        message.from_number,
                        jeevo_onboarding.get_location_request(lang)
                    )
                    return
                elif profile_option == "2":
                    await cache_service.set(f"onboarding_stage:{message.from_number}", "updating_name", 600)
                    await whatsapp_service.send_text_message(
                        message.from_number,
                        jeevo_onboarding.get_name_request(lang)
                    )
                    return
                elif profile_option == "3":
                    await cache_service.set(f"onboarding_stage:{message.from_number}", "language_selection", 600)
                    await whatsapp_service.send_text_message(
                        message.from_number,
                        jeevo_onboarding.welcome_message()
                    )
                    return
                else:
                    await whatsapp_service.send_text_message(
                        message.from_number,
                        "❌ Invalid. Reply with number 1-3"
                    )
                    return
            elif onboarding_stage == "updating_location":
                lang = await cache_service.get(f"onboarding_lang:{message.from_number}") or "en"
                location_text = text
                if message.message_type == "audio" and message.media_id:
                    try:
                        location_text, det_lang = await audio_helper.download_and_transcribe(message)
                        if location_text:
                            lang = det_lang or lang
                        else:
                            await whatsapp_service.send_text_message(
                                to_number=message.from_number,
                                text=jeevo_onboarding.get_location_request(lang)
                            )
                            return
                    except Exception as e:
                        logger.error(f"[ONBOARDING][VOICE] Error processing voice for updating location: {e}")
                        await whatsapp_service.send_text_message(
                            to_number=message.from_number,
                            text=jeevo_onboarding.get_location_request(lang)
                        )
                        return
                logger.info(f"[LOCATION] Parsing user input for update: {location_text}")
                parse_result = await location_parser_service.parse_and_validate_location(location_text, language=lang)
                if not parse_result["success"]:
                    error_message = parse_result.get("error", "Could not understand your location.")
                    logger.warning(f"[LOCATION] Parse failed: {error_message}")
                    await whatsapp_service.send_text_message(
                        to_number=message.from_number,
                        text=f"❌ {error_message}"
                    )
                    hint_message = {
                        "en": "💡 Try again with format like: 'Dharavi, Mumbai' or 'Village XYZ, Maharashtra'",
                        "hi": "💡 इस तरह कोशिश करें: 'धारावी, मुंबई' या 'गांव XYZ, महाराष्ट्र'"
                    }
                    await whatsapp_service.send_text_message(
                        to_number=message.from_number,
                        text=hint_message.get(lang, hint_message["en"])
                    )
                    return
                logger.info(f"[LOCATION] ✅ Updated: city={parse_result['city']}, state={parse_result['state']}")
                await UserRepository(db).update_user(
                    message.from_number,
                    city=parse_result['city'],
                    state=parse_result['state'],
                    pincode=parse_result['pincode']
                )
                confirm_message = f"✅ Location updated! You're now in {parse_result['city']}, {parse_result['state']}"
                if parse_result.get("interpretation"):
                    confirm_message += f"\n({parse_result['interpretation']})"
                await whatsapp_service.send_text_message(
                    to_number=message.from_number,
                    text=confirm_message
                )
                await cache_service.delete(f"onboarding_stage:{message.from_number}")
                return_msg = {
                    "en": "✅ Profile updated successfully! Type *MENU* to access services.",
                    "hi": "✅ प्रोफाइल सफलतापूर्वक अपडेट हो गया! सेवाओं के लिए *MENU* टाइप करें।"
                }
                await whatsapp_service.send_text_message(
                    message.from_number,
                    return_msg.get(lang, return_msg["en"])
                )
                return
            elif onboarding_stage == "updating_name":
                new_name = text.strip()
                await UserRepository(db).update_user(message.from_number, name=new_name)
                lang = await cache_service.get(f"onboarding_lang:{message.from_number}") or "en"
                await cache_service.delete(f"onboarding_stage:{message.from_number}")
                confirm_msgs = {
                    "en": f"✅ Name updated to '{new_name}'! Type *MENU* to access services.",
                    "hi": f"✅ नाम '{new_name}' में बदल दिया गया! सेवाओं के लिए *MENU* टाइप करें।"
                }
                await whatsapp_service.send_text_message(
                    message.from_number,
                    confirm_msgs.get(lang, confirm_msgs["en"])
                )
                return
            elif onboarding_stage == "service_selection":
                service_num = text.strip()
                lang = await cache_service.get(f"onboarding_lang:{message.from_number}") or "en"
                name = await cache_service.get(f"onboarding_name:{message.from_number}") or "User"
                if service_num == "1":
                    await complete_onboarding(message.from_number, db)
                    msg = "अपनी समस्या विस्तार से बताएं" if lang == "hi" else "Describe your health problem"
                    await whatsapp_service.send_text_message(message.from_number, msg)
                    return
                elif service_num == "2":
                    await cache_service.set(f"onboarding_stage:{message.from_number}", "adding_family", 600)
                    await whatsapp_service.send_text_message(
                        message.from_number,
                        jeevo_onboarding.get_family_member_request(lang)
                    )
                    return
                elif service_num == "3":
                    await cache_service.set(f"onboarding_stage:{message.from_number}", "vaccination_setup", 600)
                    await whatsapp_service.send_text_message(
                        message.from_number,
                        jeevo_onboarding.get_vaccination_setup(lang)
                    )
                    return
                elif service_num == "4":
                    user_data = await UserRepository(db).get_by_phone_number(message.from_number)
                    location = {"city": user_data.city, "state": user_data.state}
                    hospitals = await HospitalFinderService.find_hospitals(location)
                    response = HospitalFinderService.format_hospitals(hospitals, lang)
                    await complete_onboarding(message.from_number, db)
                    await whatsapp_service.send_text_message(message.from_number, response)
                    services_enabled = ["🏥 Hospital Finder"]
                    completion = jeevo_onboarding.get_completion_message(lang, name, services_enabled)
                    await whatsapp_service.send_text_message(message.from_number, completion)
                    return
                elif service_num == "5":
                    user_data = await UserRepository(db).get_by_phone_number(message.from_number)
                    location = {"city": user_data.city, "state": user_data.state}
                    alerts = await EnvironmentalAlertService.get_alerts(location)
                    response = EnvironmentalAlertService.format_alerts(alerts, lang)
                    await complete_onboarding(message.from_number, db)
                    await whatsapp_service.send_text_message(message.from_number, response)
                    services_enabled = ["🌡️ Environmental Alerts"]
                    completion = jeevo_onboarding.get_completion_message(lang, name, services_enabled)
                    await whatsapp_service.send_text_message(message.from_number, completion)
                    return
                elif service_num == "6":
                    await complete_onboarding(message.from_number, db)
                    msg = "दवा का नाम बताएं" if lang == "hi" else "Tell me medicine name"
                    await whatsapp_service.send_text_message(message.from_number, msg)
                    return
                elif service_num == "7":
                    await cache_service.set(f"onboarding_stage:{message.from_number}", "profile_update_selection", 600)
                    await whatsapp_service.send_text_message(
                        message.from_number,
                        jeevo_onboarding.get_profile_update_menu(lang)
                    )
                    return
                else:
                    await whatsapp_service.send_text_message(
                        message.from_number,
                        "❌ Invalid. Reply with number 1-7"
                    )
                    return
            elif onboarding_stage == "adding_family":
                if text.upper() == "DONE":
                    lang = await cache_service.get(f"onboarding_lang:{message.from_number}") or "en"
                    name = await cache_service.get(f"onboarding_name:{message.from_number}") or "User"
                    await complete_onboarding(message.from_number, db)
                    services_enabled = ["👨‍👩‍👧 Family Care"]
                    completion = jeevo_onboarding.get_completion_message(lang, name, services_enabled)
                    await whatsapp_service.send_text_message(message.from_number, completion)
                    return
                else:
                    parts = [p.strip() for p in text.split(",")]
                    if len(parts) >= 3:
                        try:
                            await FamilyMemberRepository(db).create_family_member(
                                user_id=user.id,
                                name=parts[0],
                                relation=parts[1],
                                age=int(parts[2]) if parts[2].isdigit() else None
                            )
                            await whatsapp_service.send_text_message(
                                message.from_number,
                                f"✅ Added {parts[0]}!\n\nAdd more or reply *DONE*"
                            )
                        except Exception as e:
                            logger.error(f"Error saving family member: {e}")
                            await whatsapp_service.send_text_message(
                                message.from_number,
                                "❌ Error saving family member. Please try again."
                            )
                        return
                    else:
                        lang = await cache_service.get(f"onboarding_lang:{message.from_number}") or "en"
                        await whatsapp_service.send_text_message(
                            message.from_number,
                            jeevo_onboarding.get_family_member_request(lang)
                        )
                        return
            elif onboarding_stage == "vaccination_setup":
                parts = [p.strip() for p in text.split(",")]
                if len(parts) >= 2:
                    lang = await cache_service.get(f"onboarding_lang:{message.from_number}") or "en"
                    name = await cache_service.get(f"onboarding_name:{message.from_number}") or "User"
                    await complete_onboarding(message.from_number, db)
                    msg = f"✅ Vaccination tracking setup for {parts[0]}!\n\nI'll send automatic reminders."
                    await whatsapp_service.send_text_message(message.from_number, msg)
                    services_enabled = ["💉 Vaccination Tracking"]
                    completion = jeevo_onboarding.get_completion_message(lang, name, services_enabled)
                    await whatsapp_service.send_text_message(message.from_number, completion)
                    return
                else:
                    lang = await cache_service.get(f"onboarding_lang:{message.from_number}") or "en"
                    await whatsapp_service.send_text_message(
                        message.from_number,
                        jeevo_onboarding.get_vaccination_setup(lang)
                    )
                    return
        user_language = user.language.value if user.language else "en"
        if message.message_type == "text" and message.text_content:
            text_lower = message.text_content.lower().strip()
            if text_lower in ["menu", "मेनू", "services", "सेवाएं", "help", "मदद", "options", "विकल्प", "0"]:
                name = user.name or "User"
                await cache_service.set(f"onboarding_stage:{message.from_number}", "service_selection", 600)
                await cache_service.set(f"onboarding_lang:{message.from_number}", user_language, 600)
                await cache_service.set(f"onboarding_name:{message.from_number}", name, 600)
                try:
                    menu_text = jeevo_onboarding.get_service_selection(user_language, name)
                    menu_buttons_map = {
                        "en": ["💊 Health Problem", "💉 Vaccination", "🏥 Hospital"],
                        "hi": ["💊 स्वास्थ्य समस्या", "💉 टीकाकरण", "🏥 अस्पताल"],
                        "mr": ["💊 आरोग्य समस्या", "💉 लसीकरण", "🏥 रुग्णालय"],
                        "gu": ["💊 આરોગ્ય સમસ્યા", "💉 રસીકરણ", "🏥 હોસ્પિટલ"],
                        "bn": ["💊 স্বাস্থ্য সমস্যা", "💉 টিকা", "🏥 হাসপাতাল"],
                        "ta": ["💊 சுகாதार சிக்கல்", "💉 தடுப்பூசி", "🏥 மருத்துவமனை"],
                        "te": ["💊 ఆరోగ్య సమస్య", "💉 టీకా", "🏥 ఆసుపత్రి"],
                        "kn": ["💊 ಆರೋಗ್ಯ ಸಮಸ್ಯೆ", "💉 ಲಸಿಕ", "🏥 ಆಸ್ಪತ್ರೆ"],
                        "ml": ["💊 ആരോഗ്യ പ്രശ്നം", "💉 വാക്സിൻ", "🏥 ആശുപത്രി"],
                        "pa": ["💊 ਸਿਹਤ ਸਮੱਸਿਆ", "💉 ਵੈਕਸੀਨ", "🏥 ਹਸਪਤਾਲ"]
                    }
                    buttons = menu_buttons_map.get(user_language, menu_buttons_map["en"])
                    await whatsapp_service.send_message_with_suggestions(
                        to_number=message.from_number,
                        text=menu_text,
                        suggestions=buttons
                    )
                except Exception as e:
                    logger.warning(f"Interactive menu failed, falling back to text: {e}")
                    menu_text = jeevo_onboarding.get_service_selection(user_language, name)
                    await whatsapp_service.send_text_message(
                        to_number=message.from_number,
                        text=menu_text
                    )
                return
            if text_lower in ["language", "lang", "भाषा", "change language", "भाषा बदलें"]:
                await cache_service.set(f"onboarding_stage:{message.from_number}", "language_selection", 600)
                await whatsapp_service.send_text_message(
                    to_number=message.from_number,
                    text=jeevo_onboarding.welcome_message()
                )
                return
            if await CommandRouter.route_command(text_lower, message, user, db):
                return
            if text_lower in ["hi", "hello", "start", "namaste", "hey", "नमस्ते", "வணக்கம்", "నమస్కారం"] or is_new:
                welcome_msg = language_manager.get_system_message("welcome", user_language)
                menu_hint = "\n\n💡 Type *MENU* anytime for services" if user_language == "en" else "\n\n💡 सेवाओं के लिए *MENU* टाइप करें"
                welcome_msg += menu_hint
                await whatsapp_service.send_text_message(
                    to_number=message.from_number,
                    text=welcome_msg
                )
                await ConversationRepository(db).create_conversation(
                    user_id=user.id,
                    message_id=message.message_id,
                    message_type=message.message_type,
                    user_message=message.text_content,
                    bot_response=welcome_msg,
                    media_id=message.media_id,
                    response_time_ms=int((time.time() - start_time) * 1000)
                )
                logger.info(f"[RESPONSE] Sent welcome message to {message.from_number}")
                return
        content = message.text_content
        caption = ""
        if message.media_id:
            try:
                media_path = await whatsapp_service.download_media(message.media_id, message.message_type)
                content = media_path
                if message.message_type == "image" and message.text_content:
                    caption = message.text_content
                logger.info(f"[MEDIA] Downloaded {message.message_type} to {media_path}")
            except Exception as e:
                logger.error(f"[MEDIA] Failed to download media: {e}")
                error_msg = language_manager.get_system_message("error", user_language)
                await whatsapp_service.send_text_message(
                    to_number=message.from_number,
                    text=error_msg
                )
                return
        if message.message_type == "text" and message.text_content:
            candidate = message.text_content.strip()
            if candidate.isdigit() and candidate in {"0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"}:
                lang = user_language
                name = user.name or await cache_service.get(f"onboarding_name:{message.from_number}") or "User"
                if candidate == "0":
                    await cache_service.set(f"onboarding_stage:{message.from_number}", "service_selection", 600)
                    await whatsapp_service.send_text_message(
                        to_number=message.from_number,
                        text=jeevo_onboarding.get_service_selection(lang, name)
                    )
                    return
                lang_code = jeevo_onboarding.get_language_from_number(candidate)
                if lang_code:
                    await UserRepository(db).update_user(message.from_number, language=lang_code)
                    await cache_service.set(f"onboarding_lang:{message.from_number}", lang_code, 600)
                    onboarding_stage = await cache_service.get(f"onboarding_stage:{message.from_number}")
                    if onboarding_stage == "language_selection":
                        await cache_service.set(f"onboarding_stage:{message.from_number}", "name_collection", 600)
                        await whatsapp_service.send_text_message(
                            to_number=message.from_number,
                            text=jeevo_onboarding.get_name_request(lang_code)
                        )
                        return
                    else:
                        await whatsapp_service.send_text_message(
                            message.from_number,
                            f"✅ Language changed"
                        )
                        return
                service_num = candidate
                if service_num == "1":
                    await complete_onboarding(message.from_number, db)
                    msg = "अपनी समस्या विस्तार से बताएं" if lang == "hi" else "Describe your health problem"
                    await whatsapp_service.send_text_message(message.from_number, msg)
                    return
                if service_num == "2":
                    await cache_service.set(f"onboarding_stage:{message.from_number}", "adding_family", 600)
                    await whatsapp_service.send_text_message(
                        message.from_number,
                        jeevo_onboarding.get_family_member_request(lang)
                    )
                    return
                if service_num == "3":
                    await cache_service.set(f"onboarding_stage:{message.from_number}", "vaccination_setup", 600)
                    await whatsapp_service.send_text_message(
                        message.from_number,
                        jeevo_onboarding.get_vaccination_setup(lang)
                    )
                    return
                if service_num == "4":
                    user_data = await UserRepository(db).get_by_phone_number(message.from_number)
                    location = {"city": user_data.city, "state": user_data.state}
                    hospitals = await HospitalFinderService.find_hospitals(location)
                    response = HospitalFinderService.format_hospitals(hospitals, lang)
                    await complete_onboarding(message.from_number, db)
                    await whatsapp_service.send_text_message(message.from_number, response)
                    services_enabled = ["🏥 Hospital Finder"]
                    completion = jeevo_onboarding.get_completion_message(lang, name, services_enabled)
                    await whatsapp_service.send_text_message(message.from_number, completion)
                    return
                if service_num == "5":
                    user_data = await UserRepository(db).get_by_phone_number(message.from_number)
                    location = {"city": user_data.city, "state": user_data.state}
                    alerts = await EnvironmentalAlertService.get_alerts(location)
                    response = EnvironmentalAlertService.format_alerts(alerts, lang)
                    await complete_onboarding(message.from_number, db)
                    await whatsapp_service.send_text_message(message.from_number, response)
                    services_enabled = ["🌡️ Environmental Alerts"]
                    completion = jeevo_onboarding.get_completion_message(lang, name, services_enabled)
                    await whatsapp_service.send_text_message(message.from_number, completion)
                    return
                if service_num == "6":
                    await complete_onboarding(message.from_number, db)
                    msg = "दवा का नाम बताएं" if lang == "hi" else "Tell me medicine name"
                    await whatsapp_service.send_text_message(message.from_number, msg)
                    return
                if service_num == "7":
                    await cache_service.set(f"onboarding_stage:{message.from_number}", "profile_update_selection", 600)
                    await whatsapp_service.send_text_message(
                        message.from_number,
                        jeevo_onboarding.get_profile_update_menu(lang)
                    )
                    return
        logger.info(f"[ROUTER] Processing {message.message_type} message in {user_language}")
        user_location = {
            "city": user.city,
            "state": user.state,
            "latitude": user.latitude,
            "longitude": user.longitude
        }
        if not user.city or not user.state:
            location_msg = {
                "en": "⚠️ Please update your location first for better assistance. Use command: MENU → Location",
                "hi": "⚠️ बेहतर सहायता के लिए कृपया अपना स्थान अपडेट करें। कमांड उपयोग करें: MENU → Location"
            }
            await whatsapp_service.send_text_message(
                to_number=message.from_number,
                text=location_msg.get(user_language, location_msg["en"])
            )
            return
        response = await multimodal_router.route_message(
            message_type=message.message_type,
            content=content,
            caption=caption,
            language=user_language,
            user_location=user_location
        )
        response_language = response.get("language", user_language)
        if response.get("type") == "text" and user.voice_enabled and message.message_type == "audio":
            detected_symptom = response.get("detected_symptom")
            is_medical_related = detected_symptom or (message.text_content and any(
                keyword in message.text_content.lower() 
                for keyword in ["fever", "pain", "disease", "medicine", "doctor", "hospital", 
                              "बीमारी", "दर्द", "दवा", "डॉक्टर", "अस्पताल", "बुखार"]
            ))
            if is_medical_related:
                try:
                    logger.info(f"[AUTO-VOICE] Generating audio for medical response in {response_language} (audio input)")
                    logger.info(f"[AUTO-VOICE] Response text length: {len(response['content'])} characters")
                    from app.services.tts_fallback_service import tts_fallback_service
                    audio_bytes, provider = await tts_fallback_service.text_to_speech_with_fallback(
                        text=response["content"],
                        language=response_language,
                        gender="female"
                    )
                    if audio_bytes:
                        output_path = f"temp/auto_voice_{os.urandom(8).hex()}.ogg"
                        os.makedirs("temp", exist_ok=True)
                        with open(output_path, "wb") as f:
                            f.write(audio_bytes)
                        if os.path.exists(output_path):
                            file_size = os.path.getsize(output_path)
                            logger.info(f"[AUTO-VOICE] ✅ Audio file created: {output_path} ({file_size} bytes)")
                            response["audio_path"] = output_path
                            response["audio_provider"] = provider
                            logger.info(f"[AUTO-VOICE] ✅ Generated audio via {provider}")
                        else:
                            logger.error(f"[AUTO-VOICE] ❌ Audio file not created: {output_path}")
                    else:
                        logger.warning("[AUTO-VOICE] ❌ No audio generated, falling back to text")
                except Exception as e:
                    logger.warning(f"[AUTO-VOICE] ❌ Failed to auto-generate audio: {e}, using text fallback")
                    import traceback
                    logger.warning(f"[AUTO-VOICE] Traceback: {traceback.format_exc()}")
        if response["type"] == "text":
            await whatsapp_service.send_text_message(
                to_number=message.from_number,
                text=response["content"]
            )
            bot_response = response["content"]
            if response.get("audio_path") and message.message_type == "audio":
                try:
                    logger.info(f"[VOICE] Sending audio message to {message.from_number} (audio input)")
                    await whatsapp_service.send_audio_message(
                        to_number=message.from_number,
                        audio_path=response["audio_path"]
                    )
                    bot_response = f"[Voice Response] {response['content']}"
                    logger.info(f"[VOICE] ✅ Audio message sent successfully")
                    try:
                        await asyncio.sleep(2.0)
                        if os.path.exists(response["audio_path"]):
                            os.remove(response["audio_path"])
                            logger.debug(f"[VOICE] Cleaned up temp file: {response['audio_path']}")
                    except Exception as cleanup_error:
                        logger.warning(f"[VOICE] Failed to clean up temp file: {cleanup_error}")
                except Exception as e:
                    logger.error(f"[VOICE] ❌ Failed to send voice message: {e}", exc_info=True)
                    bot_response = f"[Voice Failed→Text] {response['content']}"
        elif response["type"] == "voice":
            if message.message_type != "audio":
                logger.info("[VOICE] Incoming message not audio; skipping outgoing audio and sending text instead")
                await whatsapp_service.send_text_message(
                    to_number=message.from_number,
                    text=response.get("content")
                )
                bot_response = response.get("content")
            elif response.get("audio_path"):
                try:
                    await whatsapp_service.send_text_message(
                        to_number=message.from_number,
                        text=response.get("content")
                    )
                    bot_response = response.get("content")
                    logger.info(f"[VOICE] Sending audio message to {message.from_number}")
                    await whatsapp_service.send_audio_message(
                        to_number=message.from_number,
                        audio_path=response["audio_path"]
                    )
                    bot_response = f"[Voice Response] {response['content']}"
                    logger.info(f"[VOICE] ✅ Audio message sent successfully")
                    try:
                        await asyncio.sleep(2.0)
                        if os.path.exists(response["audio_path"]):
                            os.remove(response["audio_path"])
                            logger.debug(f"[VOICE] Cleaned up temp file: {response['audio_path']}")
                    except Exception as cleanup_error:
                        logger.warning(f"[VOICE] Failed to clean up temp file: {cleanup_error}")
                except Exception as e:
                    logger.error(f"[VOICE] ❌ Failed to send voice message: {e}", exc_info=True)
                    fallback_text = f"Audio response unavailable. {response['content']}"
                    await whatsapp_service.send_text_message(
                        to_number=message.from_number,
                        text=fallback_text
                    )
                    bot_response = f"[Voice Failed→Text] {response['content']}"
            else:
                logger.warning(f"[VOICE] No audio_path in response, falling back to text")
                await whatsapp_service.send_text_message(
                    to_number=message.from_number,
                    text=response["content"]
                )
                bot_response = response["content"]
        else:
            error_msg = language_manager.get_system_message("error", user_language)
            await whatsapp_service.send_text_message(
                to_number=message.from_number,
                text=error_msg
            )
            bot_response = error_msg
        response_time_ms = int((time.time() - start_time) * 1000)
        try:
            await ConversationRepository(db).create_conversation(
                user_id=user.id,
                message_id=message.message_id,
                message_type=message.message_type,
                user_message=message.text_content or f"[{message.message_type}]",
                bot_response=bot_response,
                media_id=message.media_id,
                response_time_ms=response_time_ms
            )
        except Exception as e:
            logger.error(f"[DB] Failed to log conversation: {e}")
        new_context = {
            "last_message_type": message.message_type,
            "last_message_time": message.timestamp,
            "conversation_state": "active",
            "language": user_language
        }
        await cache_service.set_user_context(message.from_number, new_context)
        logger.info(f"[RESPONSE] Sent to {message.from_number} (took {response_time_ms}ms)")
    except Exception as e:
        logger.error(f"[PROCESS] Error processing message: {e}", exc_info=True)
        try:
            error_message = "⚠️ Sorry, I encountered an error. Please try again in a moment."
            await whatsapp_service.send_text_message(
                to_number=message.from_number,
                text=error_message
            )
        except Exception as send_error:
            logger.error(f"[PROCESS] Could not send error message: {send_error}")
