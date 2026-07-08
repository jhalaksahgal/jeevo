import logging
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.message import WhatsAppMessage
from app.services.whatsapp_service import whatsapp_service
from app.services.heatmap_update_service import HeatmapUpdateService
from app.services.risk_aggregation_service import RiskAggregationService
logger = logging.getLogger(__name__)
class CommandRouter:
    """Handles explicit text commands sent by the user."""
    @staticmethod
    async def route_command(text_lower: str, message: WhatsAppMessage, user: any, db: AsyncSession) -> bool:
        """
        Routes the command to the appropriate handler.
        Returns True if a command was handled, False otherwise.
        """
        if text_lower in ["heatmap", "हीटमैप", "risk", "जोखिम", "map", "नक्शा", "health risk"]:
            await CommandRouter.handle_heatmap(message, user, db)
            return True
        if text_lower in ["reset", "restart", "शुरू करें", "start"]:
            await CommandRouter.handle_reset(message, user, db)
            return True
        if text_lower in ["briefing", "brief", "सारांश", "daily", "दैनिक"]:
            await CommandRouter.handle_briefing(message, user, db)
            return True
        if text_lower in ["vaccine", "vaccines", "vaccination", "टीकाकरण", "टीके", "immunization", "వ్యాధిబాధ్యతా", "टीका"]:
            await CommandRouter.handle_vaccine(message, user, db)
            return True
        return False
    @staticmethod
    async def handle_heatmap(message: WhatsAppMessage, user: any, db: AsyncSession):
        if not user or not user.city:
            await whatsapp_service.send_text_message(
                message.from_number, 
                "Please update your location first to see the heatmap."
            )
            return
        try:
            heatmap_data = await HeatmapUpdateService.get_city_heatmap(db, user.city)
            if heatmap_data.get("risk_level") != "unknown":
                heatmap_msg = RiskAggregationService.format_heatmap_display(
                    {"risk_level": heatmap_data.get("risk_level"), "score": 5.0, "components": {}},
                    user.city,
                    "en"  
                )
                await whatsapp_service.send_text_message(message.from_number, heatmap_msg)
                logger.info(f"[HEATMAP] Sent heatmap for {user.city} to {message.from_number}")
            else:
                await whatsapp_service.send_text_message(
                    message.from_number,
                    f"Not enough data to generate a heatmap for {user.city} right now."
                )
        except Exception as e:
            logger.error(f"[HEATMAP] Error generating heatmap: {e}")
            await whatsapp_service.send_text_message(
                message.from_number,
                "Error generating heatmap. Please try again later."
            )
    @staticmethod
    async def handle_reset(message: WhatsAppMessage, user: any, db: AsyncSession):
        from app.services.cache_service import cache_service
        try:
            await cache_service.delete(f"onboarding_stage:{message.from_number}")
            await cache_service.delete(f"onboarding_lang:{message.from_number}")
            await whatsapp_service.send_text_message(
                message.from_number,
                "Your session has been reset. Say 'Hi' to start over."
            )
            logger.info(f"[RESET] Reset session for {message.from_number}")
        except Exception as e:
            logger.error(f"[RESET] Error resetting session: {e}")
    @staticmethod
    async def handle_briefing(message: WhatsAppMessage, user: any, db: AsyncSession):
        from app.services.risk_alert_service import RiskAlertService
        user_language = user.language.value if user.language else "en"
        if user.city:
            briefing = await RiskAlertService.send_periodic_health_briefing(
                db, user.city, user_language
            )
            await whatsapp_service.send_text_message(
                message.from_number, briefing
            )
            logger.info(f"[BRIEFING] Sent health briefing to {message.from_number}")
            return
        await whatsapp_service.send_text_message(
            message.from_number,
            "📍 Please update your location first to receive health briefing."
        )
    @staticmethod
    async def handle_vaccine(message: WhatsAppMessage, user: any, db: AsyncSession):
        from app.database.repositories import FamilyMemberRepository
        from app.services.vaccine_service import VaccineReminderService
        from app.services.anganwadi_finder_service import AnganwadiFinderService
        user_language = user.language.value if user.language else "en"
        user_family = await FamilyMemberRepository(db).get_user_family_members(user.id)
        if not user_family:
            await whatsapp_service.send_text_message(
                message.from_number,
                "👨‍👩‍👧 No family members found. Please add family members first to track vaccinations."
            )
            return
        vaccine_status = await VaccineReminderService.send_family_vaccine_status(
            family_id=user.phone_number,
            user_phone=message.from_number,
            user_language=user_language,
            location=user.city,
            session=db
        )
        await whatsapp_service.send_text_message(
            message.from_number, vaccine_status
        )
        if user.city:
            anganwadi_data = await AnganwadiFinderService.find_nearest_anganwadi(user.city)
            if anganwadi_data.get("found"):
                anganwadi_msg = AnganwadiFinderService.format_anganwadi_message(anganwadi_data, user_language)
                await whatsapp_service.send_text_message(
                    message.from_number, anganwadi_msg
                )
                logger.info(f"[VACCINE] Sent vaccine status and Aanganwadi info to {message.from_number}")
            else:
                logger.warning(f"[VACCINE] Aanganwadi data not available for {user.city}")
        else:
            logger.info(f"[VACCINE] Sent vaccine status (no location) to {message.from_number}")
