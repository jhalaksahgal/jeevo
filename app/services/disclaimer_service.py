import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database.models import Disclaimer, DisclaimerTracking, LanguageEnum
logger = logging.getLogger(__name__)
class DisclaimerService:
    """Service to manage medical disclaimers"""
    DEFAULT_DISCLAIMERS = {
        "low": {
            "en": "✅ This information is for general awareness only.",
            "hi": "✅ यह जानकारी सामान्य जागरूकता के लिए है।",
        },
        "medium": {
            "en": "⚠️ This is AI-generated guidance. Please consult a qualified doctor for proper medical advice.",
            "hi": "⚠️ यह एआई द्वारा उत्पन्न मार्गदर्शन है। सही चिकित्सा सलाह के लिए कृपया योग्य डॉक्टर से संपर्क करें।",
        },
        "high": {
            "en": "🚨 IMPORTANT: This requires immediate medical attention. Please consult a doctor or visit a hospital immediately.",
            "hi": "🚨 महत्वपूर्ण: इसके लिए तुरंत चिकित्सा ध्यान दिया जाना चाहिए। कृपया तुरंत डॉक्टर से परामर्श लें या अस्पताल जाएं।",
        },
        "critical": {
            "en": "🚨 EMERGENCY: This appears to be a life-threatening situation. Please call 911 or your local emergency number immediately!",
            "hi": "🚨 आपातकाल: यह एक जानलेवा स्थिति प्रतीत होती है। कृपया तुरंत 911 को कॉल करें या अपना स्थानीय आपातकालीन नंबर दबाएं!",
        }
    }
    @staticmethod
    async def get_disclaimer_for_risk_level(
        db: AsyncSession,
        risk_level: str,
        language: str = "en"
    ) -> Optional[Disclaimer]:
        """
        Get or create a disclaimer for a given risk level
        Args:
            db: Database session
            risk_level: Risk level (low, medium, high, critical)
            language: Language code (en, hi, etc.)
        Returns:
            Disclaimer object or None
        """
        try:
            result = await db.execute(
                select(Disclaimer).where(
                    (Disclaimer.risk_level == risk_level) &
                    (Disclaimer.language == language) &
                    (Disclaimer.is_active == True)
                ).order_by(Disclaimer.priority.desc())
            )
            disclaimer = result.scalars().first()
            if disclaimer:
                return disclaimer
            logger.info(f"[DISCLAIMER] Creating default disclaimer for {risk_level} in {language}")
            default_content = DisclaimerService.DEFAULT_DISCLAIMERS.get(risk_level, {}).get(
                language,
                DisclaimerService.DEFAULT_DISCLAIMERS[risk_level].get("en")
            )
            disclaimer = Disclaimer(
                risk_level=risk_level,
                language=language,
                content=default_content,
                is_active=True,
                priority=1
            )
            db.add(disclaimer)
            await db.commit()
            await db.refresh(disclaimer)
            return disclaimer
        except Exception as e:
            logger.error(f"[DISCLAIMER] Error getting disclaimer: {e}")
            return None
    @staticmethod
    async def track_disclaimer_shown(
        db: AsyncSession,
        user_id: int,
        disclaimer_id: int,
        context: Optional[dict] = None,
        message_id: Optional[str] = None
    ) -> Optional[DisclaimerTracking]:
        """
        Track that a disclaimer was shown to a user
        Args:
            db: Database session
            user_id: ID of the user
            disclaimer_id: ID of the disclaimer
            context: Optional context information
            message_id: Optional message ID
        Returns:
            DisclaimerTracking object or None
        """
        try:
            tracking = DisclaimerTracking(
                user_id=user_id,
                disclaimer_id=disclaimer_id,
                context=context or {},
                message_id=message_id
            )
            db.add(tracking)
            await db.commit()
            await db.refresh(tracking)
            logger.info(f"[DISCLAIMER] Tracked disclaimer {disclaimer_id} for user {user_id}")
            return tracking
        except Exception as e:
            logger.error(f"[DISCLAIMER] Error tracking disclaimer: {e}")
            return None
    @staticmethod
    async def get_user_disclaimer_history(
        db: AsyncSession,
        user_id: int,
        limit: int = 10
    ) -> list:
        """Get disclaimer history for a user"""
        try:
            result = await db.execute(
                select(DisclaimerTracking).where(
                    DisclaimerTracking.user_id == user_id
                ).order_by(
                    DisclaimerTracking.shown_at.desc()
                ).limit(limit)
            )
            return result.scalars().all()
        except Exception as e:
            logger.error(f"[DISCLAIMER] Error fetching disclaimer history: {e}")
            return []
    @staticmethod
    async def create_custom_disclaimer(
        db: AsyncSession,
        risk_level: str,
        language: str,
        content: str,
        priority: int = 1
    ) -> Optional[Disclaimer]:
        """Create a custom disclaimer"""
        try:
            disclaimer = Disclaimer(
                risk_level=risk_level,
                language=language,
                content=content,
                is_active=True,
                priority=priority
            )
            db.add(disclaimer)
            await db.commit()
            await db.refresh(disclaimer)
            logger.info(f"[DISCLAIMER] Created custom disclaimer for {risk_level}")
            return disclaimer
        except Exception as e:
            logger.error(f"[DISCLAIMER] Error creating custom disclaimer: {e}")
            return None
