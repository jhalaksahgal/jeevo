import logging
from typing import Optional, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database.models import EscalatedCase, Expert, User
logger = logging.getLogger(__name__)
class EscalationService:
    """Service to manage case escalation to experts"""
    @staticmethod
    async def escalate_case(
        db: AsyncSession,
        user_id: int,
        original_query: str,
        bot_response: str,
        severity: str,
        reason: str,
        keywords_triggered: List[str],
        validation_id: Optional[int] = None
    ) -> Optional[EscalatedCase]:
        """
        Create an escalated case and assign to an available expert
        Args:
            db: Database session
            user_id: ID of the user
            original_query: Original query from user
            bot_response: Bot's response that triggered escalation
            severity: Severity level (low, medium, high, critical)
            reason: Reason for escalation
            keywords_triggered: Keywords that triggered escalation
            validation_id: ID of the validation record
        Returns:
            Created EscalatedCase or None if creation fails
        """
        try:
            available_expert = await EscalationService._find_available_expert(db)
            case = EscalatedCase(
                user_id=user_id,
                validation_id=validation_id,
                assigned_expert_id=available_expert.id if available_expert else None,
                original_query=original_query,
                bot_response=bot_response,
                severity=severity,
                escalation_reason=reason,
                keywords_triggered=keywords_triggered,
                status="open"
            )
            db.add(case)
            await db.commit()
            await db.refresh(case)
            logger.info(
                f"[ESCALATION] Case {case.id} created | "
                f"User: {user_id} | Severity: {severity} | "
                f"Assigned to: {available_expert.name if available_expert else 'Unassigned'}"
            )
            return case
        except Exception as e:
            logger.error(f"[ESCALATION] Error creating escalated case: {e}")
            return None
    @staticmethod
    async def _find_available_expert(db: AsyncSession) -> Optional[Expert]:
        """Find an available expert to assign the case"""
        try:
            result = await db.execute(
                select(Expert).where(
                    (Expert.is_active == True) &
                    (Expert.is_available == True)
                )
            )
            expert = result.scalars().first()
            return expert
        except Exception as e:
            logger.warning(f"[ESCALATION] Could not find available expert: {e}")
            return None
    @staticmethod
    async def resolve_case(
        db: AsyncSession,
        case_id: int,
        resolution_notes: str
    ) -> Optional[EscalatedCase]:
        """
        Resolve an escalated case
        Args:
            db: Database session
            case_id: ID of the case
            resolution_notes: Notes on resolution
        Returns:
            Updated EscalatedCase or None
        """
        try:
            result = await db.execute(
                select(EscalatedCase).where(EscalatedCase.id == case_id)
            )
            case = result.scalar_one_or_none()
            if not case:
                logger.warning(f"[ESCALATION] Case {case_id} not found")
                return None
            case.status = "resolved"
            case.resolution_notes = resolution_notes
            case.resolved_at = datetime.utcnow()
            await db.commit()
            await db.refresh(case)
            logger.info(f"[ESCALATION] Case {case_id} resolved")
            return case
        except Exception as e:
            logger.error(f"[ESCALATION] Error resolving case: {e}")
            return None
    @staticmethod
    async def get_pending_cases(db: AsyncSession, expert_id: int) -> List[EscalatedCase]:
        """Get all pending cases for an expert"""
        try:
            result = await db.execute(
                select(EscalatedCase).where(
                    (EscalatedCase.assigned_expert_id == expert_id) &
                    (EscalatedCase.status.in_(["open", "in_progress"]))
                )
            )
            return result.scalars().all()
        except Exception as e:
            logger.error(f"[ESCALATION] Error fetching pending cases: {e}")
            return []
    @staticmethod
    async def get_case_by_id(db: AsyncSession, case_id: int) -> Optional[EscalatedCase]:
        """Get a specific escalated case"""
        try:
            result = await db.execute(
                select(EscalatedCase).where(EscalatedCase.id == case_id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"[ESCALATION] Error fetching case: {e}")
            return None
