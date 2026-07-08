from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.database.models import (
    User, Conversation, Reminder, LocalRiskLevel, HealthAlert, FamilyMember, 
    VaccinationRecord, ResponseMetric, ResponseValidation, EscalatedCase, 
    Expert, Disclaimer, DisclaimerTracking
)
import logging
logger = logging.getLogger(__name__)
class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
    async def create_user(self, phone_number: str, **kwargs) -> User:
        try:
            user = User(phone_number=phone_number, **kwargs)
            self.db.add(user)
            await self.db.commit()
            await self.db.refresh(user)
            logger.info(f"Created user: {phone_number}")
            return user
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating user: {e}")
            raise
    async def get_user_by_phone(self, phone_number: str) -> Optional[User]:
        result = await self.db.execute(
            select(User).where(User.phone_number == phone_number)
        )
        return result.scalar_one_or_none()
    async def get_by_phone_number(self, phone_number: str) -> Optional[User]:
        return await self.get_user_by_phone(phone_number)
    async def get_or_create_user(self, phone_number: str, **kwargs) -> tuple[User, bool]:
        user = await self.get_user_by_phone(phone_number)
        if user:
            try:
                user.last_active = datetime.utcnow()
                await self.db.commit()
                return user, False
            except Exception as e:
                await self.db.rollback()
                logger.error(f"Error updating user last_active: {e}")
                raise
        else:
            user = await self.create_user(phone_number, **kwargs)
            return user, True
    async def update_user(self, phone_number: str, **kwargs) -> Optional[User]:
        from app.database.models import LanguageEnum
        user = await self.get_user_by_phone(phone_number)
        if user:
            try:
                for key, value in kwargs.items():
                    if key == "language" and isinstance(value, str):
                        try:
                            value = LanguageEnum(value)
                        except ValueError:
                            logger.warning(f"Invalid language code: {value}, defaulting to English")
                            value = LanguageEnum.ENGLISH
                    setattr(user, key, value)
                await self.db.commit()
                await self.db.refresh(user)
                logger.info(f"Updated user: {phone_number}")
            except Exception as e:
                await self.db.rollback()
                logger.error(f"Error updating user: {e}")
                raise
        return user
    async def get_all_users(self, skip: int = 0, limit: int = 100) -> List[User]:
        result = await self.db.execute(
            select(User).offset(skip).limit(limit)
        )
        return result.scalars().all()
class ConversationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
    async def create_conversation(
        self,
        user_id: int,
        message_id: str,
        **kwargs
    ) -> Conversation:
        try:
            conversation = Conversation(
                user_id=user_id,
                message_id=message_id,
                **kwargs
            )
            self.db.add(conversation)
            await self.db.commit()
            await self.db.refresh(conversation)
            return conversation
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating conversation: {e}")
            raise
    async def get_user_conversations(
        self,
        user_id: int,
        limit: int = 50
    ) -> List[Conversation]:
        result = await self.db.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()
    async def get_recent_conversations(
        self,
        user_id: int,
        limit: int = 10
    ) -> List[Conversation]:
        result = await self.db.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.created_at.asc())
            .limit(limit)
        )
        conversations = result.scalars().all()
        return list(reversed(conversations))
    async def get_conversation_context(
        self,
        user_id: int,
        limit: int = 10
    ) -> str:
        conversations = await self.get_recent_conversations(user_id, limit)
        context_lines = []
        for conv in conversations:
            if conv.user_message:
                context_lines.append(f"User: {conv.user_message}")
            if conv.bot_response:
                context_lines.append(f"Assistant: {conv.bot_response}")
        return "\n".join(context_lines)
class ReminderRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
    async def create_reminder(
        self,
        user_id: int,
        **kwargs
    ) -> Reminder:
        try:
            reminder = Reminder(user_id=user_id, **kwargs)
            self.db.add(reminder)
            await self.db.commit()
            await self.db.refresh(reminder)
            logger.info(f"Created reminder for user {user_id}: {reminder.title}")
            return reminder
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating reminder: {e}")
            raise
    async def get_user_reminders(
        self,
        user_id: int,
        active_only: bool = True
    ) -> List[Reminder]:
        query = select(Reminder).where(Reminder.user_id == user_id)
        if active_only:
            query = query.where(
                Reminder.is_sent == False,
                Reminder.is_completed == False
            )
        result = await self.db.execute(query.order_by(Reminder.scheduled_time))
        return result.scalars().all()
    async def get_pending_reminders(self) -> List[Reminder]:
        now = datetime.utcnow()
        result = await self.db.execute(
            select(Reminder)
            .where(
                Reminder.is_sent == False,
                Reminder.scheduled_time <= now
            )
            .order_by(Reminder.scheduled_time)
        )
        return result.scalars().all()
    async def mark_reminder_sent(self, reminder_id: int) -> Optional[Reminder]:
        try:
            result = await self.db.execute(
                select(Reminder).where(Reminder.id == reminder_id)
            )
            reminder = result.scalar_one_or_none()
            if reminder:
                reminder.is_sent = True
                reminder.sent_at = datetime.utcnow()
                await self.db.commit()
                await self.db.refresh(reminder)
            return reminder
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error marking reminder sent: {e}")
            raise
class RiskLevelRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
    async def get_risk_level(self, pincode: str) -> Optional[LocalRiskLevel]:
        result = await self.db.execute(
            select(LocalRiskLevel).where(LocalRiskLevel.pincode == pincode)
        )
        return result.scalar_one_or_none()
    async def update_risk_level(
        self,
        pincode: str,
        **kwargs
    ) -> LocalRiskLevel:
        try:
            risk_level = await self.get_risk_level(pincode)
            if risk_level:
                for key, value in kwargs.items():
                    setattr(risk_level, key, value)
                risk_level.last_updated = datetime.utcnow()
            else:
                risk_level = LocalRiskLevel(pincode=pincode, **kwargs)
                self.db.add(risk_level)
            await self.db.commit()
            await self.db.refresh(risk_level)
            return risk_level
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error updating risk level: {e}")
            raise
class HealthAlertRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
    async def create_alert(self, **kwargs) -> HealthAlert:
        try:
            alert = HealthAlert(**kwargs)
            self.db.add(alert)
            await self.db.commit()
            await self.db.refresh(alert)
            logger.info(f"Created health alert: {alert.title}")
            return alert
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating health alert: {e}")
            raise
    async def get_active_alerts(
        self,
        pincode: Optional[str] = None
    ) -> List[HealthAlert]:
        now = datetime.utcnow()
        query = select(HealthAlert).where(
            HealthAlert.is_active == True,
            (HealthAlert.expires_at == None) | (HealthAlert.expires_at > now)
        )
        result = await self.db.execute(query.order_by(HealthAlert.priority.desc()))
        alerts = result.scalars().all()
        if pincode:
            filtered_alerts = []
            for alert in alerts:
                if alert.target_pincodes and pincode in alert.target_pincodes:
                    filtered_alerts.append(alert)
                elif not alert.target_pincodes:
                    filtered_alerts.append(alert)
            return filtered_alerts
        return alerts
class FamilyMemberRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
    async def create_family_member(
        self,
        user_id: int,
        **kwargs
    ) -> FamilyMember:
        try:
            member = FamilyMember(user_id=user_id, **kwargs)
            self.db.add(member)
            await self.db.commit()
            await self.db.refresh(member)
            logger.info(f"Created family member {member.name} for user {user_id}")
            return member
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating family member: {e}")
            raise
    async def get_user_family_members(
        self,
        user_id: int
    ) -> List[FamilyMember]:
        result = await self.db.execute(
            select(FamilyMember)
            .where(FamilyMember.user_id == user_id)
            .order_by(FamilyMember.created_at.desc())
        )
        return result.scalars().all()
    async def get_family_member(
        self,
        member_id: int
    ) -> Optional[FamilyMember]:
        result = await self.db.execute(
            select(FamilyMember).where(FamilyMember.id == member_id)
        )
        return result.scalar_one_or_none()
    async def update_family_member(
        self,
        member_id: int,
        **kwargs
    ) -> Optional[FamilyMember]:
        member = await self.get_family_member(member_id)
        if member:
            try:
                for key, value in kwargs.items():
                    setattr(member, key, value)
                member.updated_at = datetime.utcnow()
                await self.db.commit()
                await self.db.refresh(member)
            except Exception as e:
                await self.db.rollback()
                logger.error(f"Error updating family member: {e}")
                raise
        return member
    async def delete_family_member(
        self,
        member_id: int
    ) -> bool:
        try:
            result = await self.db.execute(
                delete(FamilyMember).where(FamilyMember.id == member_id)
            )
            await self.db.commit()
            return result.rowcount > 0
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error deleting family member: {e}")
            raise
class VaccinationRecordRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
    async def create_vaccination_record(
        self,
        family_member_id: int,
        **kwargs
    ) -> VaccinationRecord:
        try:
            record = VaccinationRecord(family_member_id=family_member_id, **kwargs)
            self.db.add(record)
            await self.db.commit()
            await self.db.refresh(record)
            logger.info(f"Created vaccination record for family member {family_member_id}")
            return record
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating vaccination record: {e}")
            raise
    async def get_member_vaccinations(
        self,
        family_member_id: int,
        completed_only: bool = False
    ) -> List[VaccinationRecord]:
        query = select(VaccinationRecord).where(
            VaccinationRecord.family_member_id == family_member_id
        )
        if completed_only:
            query = query.where(VaccinationRecord.is_completed == True)
        result = await self.db.execute(query.order_by(VaccinationRecord.scheduled_date))
        return result.scalars().all()
    async def get_pending_vaccinations(
        self,
        family_member_id: int
    ) -> List[VaccinationRecord]:
        result = await self.db.execute(
            select(VaccinationRecord).where(
                VaccinationRecord.family_member_id == family_member_id,
                VaccinationRecord.is_completed == False,
                VaccinationRecord.scheduled_date <= datetime.utcnow()
            ).order_by(VaccinationRecord.scheduled_date)
        )
        return result.scalars().all()
    async def mark_vaccination_complete(
        self,
        record_id: int,
        actual_date: Optional[datetime] = None
    ) -> Optional[VaccinationRecord]:
        try:
            result = await self.db.execute(
                select(VaccinationRecord).where(VaccinationRecord.id == record_id)
            )
            record = result.scalar_one_or_none()
            if record:
                record.is_completed = True
                record.actual_date = actual_date or datetime.utcnow()
                await self.db.commit()
                await self.db.refresh(record)
                logger.info(f"Marked vaccination {record.vaccine_name} as complete")
            return record
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error marking vaccination complete: {e}")
            raise
class ResponseMetricRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
    async def create_metric(
        self,
        user_id: int,
        message_id: str,
        response_type: str,
        **kwargs
    ) -> ResponseMetric:
        try:
            metric = ResponseMetric(
                user_id=user_id,
                message_id=message_id,
                response_type=response_type,
                **kwargs
            )
            self.db.add(metric)
            await self.db.commit()
            await self.db.refresh(metric)
            logger.info(f"Created response metric for user {user_id}")
            return metric
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating response metric: {e}")
            raise
    async def get_user_metrics(
        self,
        user_id: int,
        limit: int = 100
    ) -> List[ResponseMetric]:
        result = await self.db.execute(
            select(ResponseMetric)
            .where(ResponseMetric.user_id == user_id)
            .order_by(ResponseMetric.timestamp.desc())
            .limit(limit)
        )
        return result.scalars().all()
    async def mark_response_helpful(
        self,
        metric_id: int,
        was_helpful: bool,
        feedback: str = None
    ) -> Optional[ResponseMetric]:
        try:
            result = await self.db.execute(
                select(ResponseMetric).where(ResponseMetric.id == metric_id)
            )
            metric = result.scalar_one_or_none()
            if metric:
                metric.was_helpful = was_helpful
                metric.feedback = feedback
                await self.db.commit()
                await self.db.refresh(metric)
                logger.info(f"Updated feedback for metric {metric_id}")
            return metric
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error marking response helpful: {e}")
            raise
    async def get_quality_stats(
        self,
        user_id: int = None,
        days: int = 7
    ) -> Dict:
        from datetime import timedelta
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        query = select(ResponseMetric).where(
            ResponseMetric.timestamp >= cutoff_date
        )
        if user_id:
            query = query.where(ResponseMetric.user_id == user_id)
        result = await self.db.execute(query)
        metrics = result.scalars().all()
        total = len(metrics)
        helpful = len([m for m in metrics if m.was_helpful == True])
        not_helpful = len([m for m in metrics if m.was_helpful == False])
        helpful_rate = (helpful / total * 100) if total > 0 else 0
        return {
            "total_responses": total,
            "helpful": helpful,
            "not_helpful": not_helpful,
            "accuracy_rate": round(helpful_rate, 2),
            "period_days": days,
        }
class ResponseValidationRepository:
    """Repository for ResponseValidation operations"""
    def __init__(self, db: AsyncSession):
        self.db = db
    async def create_validation(
        self,
        response_text: str,
        **kwargs
    ) -> ResponseValidation:
        """Create a validation record"""
        try:
            validation = ResponseValidation(response_text=response_text, **kwargs)
            self.db.add(validation)
            await self.db.commit()
            await self.db.refresh(validation)
            logger.info(f"Created validation record {validation.id}")
            return validation
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating validation record: {e}")
            raise
    async def get_validation(
        self,
        validation_id: int
    ) -> Optional[ResponseValidation]:
        """Get a validation record by ID"""
        result = await self.db.execute(
            select(ResponseValidation).where(ResponseValidation.id == validation_id)
        )
        return result.scalar_one_or_none()
    async def get_user_validations(
        self,
        user_id: int,
        limit: int = 50
    ) -> List[ResponseValidation]:
        """Get user's validation records"""
        result = await self.db.execute(
            select(ResponseValidation)
            .where(ResponseValidation.user_id == user_id)
            .order_by(ResponseValidation.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()
    async def get_escalation_candidates(
        self,
        limit: int = 50
    ) -> List[ResponseValidation]:
        """Get validations that require escalation"""
        result = await self.db.execute(
            select(ResponseValidation)
            .where(ResponseValidation.requires_escalation == True)
            .order_by(ResponseValidation.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()
class EscalatedCaseRepository:
    """Repository for EscalatedCase operations"""
    def __init__(self, db: AsyncSession):
        self.db = db
    async def get_case(
        self,
        case_id: int
    ) -> Optional[EscalatedCase]:
        """Get a case by ID"""
        result = await self.db.execute(
            select(EscalatedCase).where(EscalatedCase.id == case_id)
        )
        return result.scalar_one_or_none()
    async def get_user_cases(
        self,
        user_id: int,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[EscalatedCase]:
        """Get cases for a user"""
        query = select(EscalatedCase).where(EscalatedCase.user_id == user_id)
        if status:
            query = query.where(EscalatedCase.status == status)
        result = await self.db.execute(
            query.order_by(EscalatedCase.created_at.desc()).limit(limit)
        )
        return result.scalars().all()
    async def get_expert_cases(
        self,
        expert_id: int,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[EscalatedCase]:
        """Get cases assigned to an expert"""
        query = select(EscalatedCase).where(
            EscalatedCase.assigned_expert_id == expert_id
        )
        if status:
            query = query.where(EscalatedCase.status == status)
        result = await self.db.execute(
            query.order_by(EscalatedCase.created_at.asc()).limit(limit)
        )
        return result.scalars().all()
    async def update_case_status(
        self,
        case_id: int,
        status: str,
        resolution_notes: Optional[str] = None
    ) -> Optional[EscalatedCase]:
        """Update case status"""
        try:
            case = await self.get_case(case_id)
            if case:
                case.status = status
                if resolution_notes:
                    case.resolution_notes = resolution_notes
                if status == "resolved":
                    case.resolved_at = datetime.utcnow()
                await self.db.commit()
                await self.db.refresh(case)
                logger.info(f"Updated case {case_id} status to {status}")
            return case
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error updating case status: {e}")
            raise
class ExpertRepository:
    """Repository for Expert operations"""
    def __init__(self, db: AsyncSession):
        self.db = db
    async def create_expert(
        self,
        phone_number: str,
        name: str,
        **kwargs
    ) -> Expert:
        """Create an expert"""
        try:
            expert = Expert(phone_number=phone_number, name=name, **kwargs)
            self.db.add(expert)
            await self.db.commit()
            await self.db.refresh(expert)
            logger.info(f"Created expert: {name}")
            return expert
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating expert: {e}")
            raise
    async def get_expert(
        self,
        expert_id: int
    ) -> Optional[Expert]:
        """Get expert by ID"""
        result = await self.db.execute(
            select(Expert).where(Expert.id == expert_id)
        )
        return result.scalar_one_or_none()
    async def get_available_experts(self) -> List[Expert]:
        """Get all available experts"""
        result = await self.db.execute(
            select(Expert).where(
                (Expert.is_active == True) &
                (Expert.is_available == True)
            )
        )
        return result.scalars().all()
    async def get_all_experts(self, active_only: bool = True) -> List[Expert]:
        """Get all experts"""
        query = select(Expert)
        if active_only:
            query = query.where(Expert.is_active == True)
        result = await self.db.execute(query.order_by(Expert.name))
        return result.scalars().all()
    async def update_expert_availability(
        self,
        expert_id: int,
        is_available: bool
    ) -> Optional[Expert]:
        """Update expert availability"""
        try:
            expert = await self.get_expert(expert_id)
            if expert:
                expert.is_available = is_available
                await self.db.commit()
                await self.db.refresh(expert)
            return expert
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error updating expert availability: {e}")
            raise
class DisclaimerRepository:
    """Repository for Disclaimer operations"""
    def __init__(self, db: AsyncSession):
        self.db = db
    async def create_disclaimer(
        self,
        risk_level: str,
        language: str,
        content: str,
        **kwargs
    ) -> Disclaimer:
        """Create a disclaimer"""
        try:
            disclaimer = Disclaimer(
                risk_level=risk_level,
                language=language,
                content=content,
                **kwargs
            )
            self.db.add(disclaimer)
            await self.db.commit()
            await self.db.refresh(disclaimer)
            logger.info(f"Created disclaimer for {risk_level} in {language}")
            return disclaimer
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating disclaimer: {e}")
            raise
    async def get_disclaimer(
        self,
        disclaimer_id: int
    ) -> Optional[Disclaimer]:
        """Get disclaimer by ID"""
        result = await self.db.execute(
            select(Disclaimer).where(Disclaimer.id == disclaimer_id)
        )
        return result.scalar_one_or_none()
    async def get_active_disclaimers(
        self,
        risk_level: str,
        language: str
    ) -> List[Disclaimer]:
        """Get active disclaimers for risk level and language"""
        result = await self.db.execute(
            select(Disclaimer).where(
                (Disclaimer.risk_level == risk_level) &
                (Disclaimer.language == language) &
                (Disclaimer.is_active == True)
            ).order_by(Disclaimer.priority.desc())
        )
        return result.scalars().all()
class DisclaimerTrackingRepository:
    """Repository for DisclaimerTracking operations"""
    def __init__(self, db: AsyncSession):
        self.db = db
    async def create_tracking(
        self,
        user_id: int,
        disclaimer_id: int,
        **kwargs
    ) -> DisclaimerTracking:
        """Track disclaimer shown to user"""
        try:
            tracking = DisclaimerTracking(
                user_id=user_id,
                disclaimer_id=disclaimer_id,
                **kwargs
            )
            self.db.add(tracking)
            await self.db.commit()
            await self.db.refresh(tracking)
            logger.info(f"Tracked disclaimer {disclaimer_id} for user {user_id}")
            return tracking
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating disclaimer tracking: {e}")
            raise
    async def get_user_disclaimer_history(
        self,
        user_id: int,
        limit: int = 50
    ) -> List[DisclaimerTracking]:
        """Get disclaimer history for user"""
        result = await self.db.execute(
            select(DisclaimerTracking)
            .where(DisclaimerTracking.user_id == user_id)
            .order_by(DisclaimerTracking.shown_at.desc())
            .limit(limit)
        )
        return result.scalars().all()
class MedicalSourceRepository:
    """Repository for MedicalSource operations"""
    def __init__(self, db: AsyncSession):
        self.db = db
    async def create_source(
        self,
        name: str,
        url: str,
        description: str,
        authority_level: int = 1
    ):
        """Create a medical source"""
        from app.database.models import MedicalSource
        try:
            source = MedicalSource(
                name=name,
                url=url,
                description=description,
                authority_level=authority_level
            )
            self.db.add(source)
            await self.db.commit()
            await self.db.refresh(source)
            logger.info(f"Created medical source: {name}")
            return source
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating medical source: {e}")
            raise
    async def get_source(self, source_id: int):
        """Get source by ID"""
        from app.database.models import MedicalSource
        result = await self.db.execute(
            select(MedicalSource).where(MedicalSource.id == source_id)
        )
        return result.scalar_one_or_none()
    async def get_source_by_name(self, name: str):
        """Get source by name"""
        from app.database.models import MedicalSource
        result = await self.db.execute(
            select(MedicalSource).where(MedicalSource.name == name)
        )
        return result.scalar_one_or_none()
    async def get_active_sources(self):
        """Get all active sources"""
        from app.database.models import MedicalSource
        result = await self.db.execute(
            select(MedicalSource)
            .where(MedicalSource.is_active == True)
            .order_by(MedicalSource.authority_level.desc())
        )
        return result.scalars().all()
class MedicalConditionRepository:
    """Repository for MedicalCondition operations"""
    def __init__(self, db: AsyncSession):
        self.db = db
    async def create_condition(
        self,
        name: str,
        icd10_code: str,
        **kwargs
    ):
        """Create a medical condition"""
        from app.database.models import MedicalCondition
        try:
            condition = MedicalCondition(
                name=name,
                icd10_code=icd10_code,
                **kwargs
            )
            self.db.add(condition)
            await self.db.commit()
            await self.db.refresh(condition)
            logger.info(f"Created condition: {name}")
            return condition
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating condition: {e}")
            raise
    async def get_condition(self, condition_id: int):
        """Get condition by ID"""
        from app.database.models import MedicalCondition
        result = await self.db.execute(
            select(MedicalCondition).where(MedicalCondition.id == condition_id)
        )
        return result.scalar_one_or_none()
    async def get_by_name(self, name: str):
        """Get condition by name"""
        from app.database.models import MedicalCondition
        result = await self.db.execute(
            select(MedicalCondition).where(MedicalCondition.name == name)
        )
        return result.scalar_one_or_none()
    async def search_conditions(self, name: str):
        """Search conditions by name"""
        from app.database.models import MedicalCondition
        result = await self.db.execute(
            select(MedicalCondition)
            .where(MedicalCondition.name.ilike(f"%{name}%"))
            .where(MedicalCondition.is_active == True)
        )
        return result.scalars().all()
class MedicalFactRepository:
    """Repository for MedicalFact operations"""
    def __init__(self, db: AsyncSession):
        self.db = db
    async def create_fact(
        self,
        condition_id: int,
        source_id: int,
        fact_type: str,
        fact_text: str,
        **kwargs
    ):
        """Create a medical fact"""
        from app.database.models import MedicalFact
        try:
            fact = MedicalFact(
                condition_id=condition_id,
                source_id=source_id,
                fact_type=fact_type,
                fact_text=fact_text,
                **kwargs
            )
            self.db.add(fact)
            await self.db.commit()
            await self.db.refresh(fact)
            return fact
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating medical fact: {e}")
            raise
    async def get_verified_facts(
        self,
        condition_id: int,
        fact_type: Optional[str] = None
    ):
        """Get verified facts for a condition"""
        from app.database.models import MedicalFact
        query = select(MedicalFact).where(
            (MedicalFact.condition_id == condition_id) &
            (MedicalFact.is_active == True)
        )
        if fact_type:
            query = query.where(MedicalFact.fact_type == fact_type)
        result = await self.db.execute(query)
        return result.scalars().all()
class ExtractedClaimRepository:
    """Repository for ExtractedClaim operations"""
    def __init__(self, db: AsyncSession):
        self.db = db
    async def create_claim(
        self,
        claim_text: str,
        claim_type: str,
        **kwargs
    ):
        """Create an extracted claim"""
        from app.database.models import ExtractedClaim
        try:
            claim = ExtractedClaim(
                claim_text=claim_text,
                claim_type=claim_type,
                **kwargs
            )
            self.db.add(claim)
            await self.db.commit()
            await self.db.refresh(claim)
            return claim
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating claim: {e}")
            raise
    async def get_claims_for_response(
        self,
        response_id: str
    ):
        """Get claims for a specific response"""
        from app.database.models import ExtractedClaim
        result = await self.db.execute(
            select(ExtractedClaim).where(ExtractedClaim.response_id == response_id)
        )
        return result.scalars().all()
class FactCheckResultRepository:
    """Repository for FactCheckResult operations"""
    def __init__(self, db: AsyncSession):
        self.db = db
    async def create_result(
        self,
        verification_status: str,
        **kwargs
    ):
        """Create a fact check result"""
        from app.database.models import FactCheckResult
        try:
            result_obj = FactCheckResult(
                verification_status=verification_status,
                **kwargs
            )
            self.db.add(result_obj)
            await self.db.commit()
            await self.db.refresh(result_obj)
            return result_obj
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating fact check result: {e}")
            raise
    async def get_results_for_response(
        self,
        response_validation_id: int
    ):
        """Get all check results for a response"""
        from app.database.models import FactCheckResult
        result = await self.db.execute(
            select(FactCheckResult).where(
                FactCheckResult.response_validation_id == response_validation_id
            )
        )
        return result.scalars().all()
class ValidationRuleRepository:
    """Repository for ValidationRule operations"""
    def __init__(self, db: AsyncSession):
        self.db = db
    async def create_rule(
        self,
        rule_type: str,
        rule_pattern: str,
        **kwargs
    ):
        """Create a validation rule"""
        from app.database.models import ValidationRule
        try:
            rule = ValidationRule(
                rule_type=rule_type,
                rule_pattern=rule_pattern,
                **kwargs
            )
            self.db.add(rule)
            await self.db.commit()
            await self.db.refresh(rule)
            return rule
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating validation rule: {e}")
            raise
    async def get_active_rules(
        self,
        rule_type: Optional[str] = None
    ):
        """Get active validation rules"""
        from app.database.models import ValidationRule
        query = select(ValidationRule).where(ValidationRule.is_active == True)
        if rule_type:
            query = query.where(ValidationRule.rule_type == rule_type)
        result = await self.db.execute(
            query.order_by(ValidationRule.priority.desc())
        )
        return result.scalars().all()
class SourceValidationCacheRepository:
    """Repository for SourceValidationCache operations"""
    def __init__(self, db: AsyncSession):
        self.db = db
    async def create_cache(
        self,
        query_hash: str,
        cache_key: str,
        result_data: Dict[str, Any],
        **kwargs
    ):
        """Create a validation cache entry"""
        from app.database.models import SourceValidationCache
        try:
            cache_entry = SourceValidationCache(
                query_hash=query_hash,
                cache_key=cache_key,
                result_data=result_data,
                **kwargs
            )
            self.db.add(cache_entry)
            await self.db.commit()
            await self.db.refresh(cache_entry)
            return cache_entry
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating validation cache: {e}")
            raise
    async def get_by_hash(
        self,
        query_hash: str
    ):
        """Get cache entry by hash"""
        from app.database.models import SourceValidationCache
        result = await self.db.execute(
            select(SourceValidationCache).where(
                SourceValidationCache.query_hash == query_hash
            )
        )
        return result.scalar_one_or_none()
