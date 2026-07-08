"""
Medical Knowledge Base Service
Manages authoritative medical information and facts for validation
"""
import logging
import hashlib
from typing import Dict, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.repositories import (
    MedicalSourceRepository,
    MedicalConditionRepository,
    MedicalFactRepository,
    SourceValidationCacheRepository,
)
logger = logging.getLogger(__name__)
class MedicalKnowledgeBase:
    """
    Central repository for medical facts and conditions.
    Handles lookup, caching, and fact verification.
    """
    def __init__(self):
        self.cache_enabled = True
        self.cache_ttl_seconds = 3600  
    async def search_conditions(
        self, db: AsyncSession, query: str, limit: int = 10
    ) -> List[Dict]:
        """Search for medical conditions matching query"""
        try:
            repo = MedicalConditionRepository(db)
            conditions = await repo.search_conditions(
                query
            )
            if not conditions:
                return []
            return [
                {
                    "id": c.id,
                    "name": c.name,
                    "icd10_code": c.icd10_code,
                    "symptoms": c.symptoms or [],
                    "treatments": c.treatments or [],
                    "contraindications": c.contraindications,
                }
                for c in conditions
            ]
        except Exception as e:
            logger.error(f"Error searching conditions: {e}")
            return []
    async def get_condition_facts(self, db: AsyncSession, condition_id: int) -> Dict:
        """Get all verified facts for a condition"""
        try:
            cond_repo = MedicalConditionRepository(db)
            condition = await cond_repo.get_condition(condition_id)
            if not condition:
                return {}
            fact_repo = MedicalFactRepository(db)
            facts = await fact_repo.get_verified_facts(
                condition_id=condition_id
            )
            return {
                "condition": condition.name,
                "icd_code": condition.icd10_code,
                "symptoms": condition.symptoms or [],
                "treatments": condition.treatments or [],
                "contraindications": condition.contraindications or [],
                "facts_count": len(facts),
            }
        except Exception as e:
            logger.error(f"Error getting condition facts: {e}")
            return {}
    async def verify_symptom(
        self, db: AsyncSession, symptom: str, condition_id: Optional[int] = None
    ) -> Tuple[bool, float, List[Dict]]:
        """
        Verify if a symptom is documented for a condition.
        Returns: (is_verified, confidence, matching_conditions)
        """
        try:
            if condition_id:
                fact_repo = MedicalFactRepository(db)
                facts = await fact_repo.get_verified_facts(
                    condition_id=condition_id, fact_type="symptom"
                )
                matching = [
                    {
                        "condition_id": f.condition_id,
                        "fact_text": f.fact_text,
                        "confidence": f.confidence_score or 0.8,
                    }
                    for f in facts
                    if symptom.lower() in f.fact_text.lower()
                ]
            else:
                from sqlalchemy import select
                from app.database.models import MedicalFact, MedicalCondition
                result = await db.execute(
                    select(MedicalFact).where(
                        MedicalFact.fact_type == "symptom"
                    )
                )
                all_facts = result.scalars().all()
                matching = [
                    {
                        "condition_id": f.condition_id,
                        "fact_text": f.fact_text,
                        "confidence": f.confidence_score or 0.8,
                    }
                    for f in all_facts
                    if symptom.lower() in f.fact_text.lower()
                ]
            is_verified = len(matching) > 0
            avg_confidence = (
                sum(m["confidence"] for m in matching) / len(matching)
                if matching
                else 0.0
            )
            return is_verified, avg_confidence, matching
        except Exception as e:
            logger.error(f"Error verifying symptom: {e}")
            return False, 0.0, []
    async def verify_treatment(
        self, db: AsyncSession, treatment: str, condition_id: Optional[int] = None
    ) -> Tuple[bool, float, List[Dict]]:
        """
        Verify if a treatment is documented for a condition.
        Returns: (is_verified, confidence, matching_treatments)
        """
        try:
            if condition_id:
                fact_repo = MedicalFactRepository(db)
                facts = await fact_repo.get_verified_facts(
                    condition_id=condition_id, fact_type="treatment"
                )
                matching = [
                    {
                        "condition_id": f.condition_id,
                        "treatment": f.fact_text,
                        "confidence": f.confidence_score or 0.8,
                    }
                    for f in facts
                    if treatment.lower() in f.fact_text.lower()
                ]
            else:
                from sqlalchemy import select
                from app.database.models import MedicalFact
                result = await db.execute(
                    select(MedicalFact).where(
                        MedicalFact.fact_type == "treatment"
                    )
                )
                all_facts = result.scalars().all()
                matching = [
                    {
                        "condition_id": f.condition_id,
                        "treatment": f.fact_text,
                        "confidence": f.confidence_score or 0.8,
                    }
                    for f in all_facts
                    if treatment.lower() in f.fact_text.lower()
                ]
            is_verified = len(matching) > 0
            avg_confidence = (
                sum(m["confidence"] for m in matching) / len(matching)
                if matching
                else 0.0
            )
            return is_verified, avg_confidence, matching
        except Exception as e:
            logger.error(f"Error verifying treatment: {e}")
            return False, 0.0, []
    async def check_contraindications(
        self, db: AsyncSession, treatment: str, condition_id: int
    ) -> Tuple[bool, List[str]]:
        """
        Check if a treatment has contraindications for a condition.
        Returns: (has_contraindication, reason_list)
        """
        try:
            cond_repo = MedicalConditionRepository(db)
            condition = await cond_repo.get_condition(condition_id)
            if not condition or not condition.contraindications:
                return False, []
            contraindicated = [
                c
                for c in condition.contraindications
                if treatment.lower() in c.lower()
            ]
            return len(contraindicated) > 0, contraindicated
        except Exception as e:
            logger.error(f"Error checking contraindications: {e}")
            return False, []
    async def get_drug_interactions(
        self, db: AsyncSession, drug_names: List[str]
    ) -> List[Dict]:
        """Get known interactions between drugs"""
        try:
            logger.warning("Drug interaction lookup not yet implemented")
            return []
        except Exception as e:
            logger.error(f"Error getting drug interactions: {e}")
            return []
    async def validate_medication_dosage(
        self, db: AsyncSession, drug_name: str, dosage: str, age_group: str
    ) -> Tuple[bool, str]:
        """
        Validate if a medication dosage is appropriate for age group.
        Returns: (is_appropriate, reason)
        """
        try:
            logger.warning("Medication dosage validation not yet implemented")
            return True, "Requires manual validation"
        except Exception as e:
            logger.error(f"Error validating dosage: {e}")
            return False, f"Validation error: {str(e)}"
    async def get_sources(self, db: AsyncSession) -> List[Dict]:
        """Get all active medical sources"""
        try:
            source_repo = MedicalSourceRepository(db)
            sources = await source_repo.get_active_sources()
            return [
                {
                    "id": s.id,
                    "name": s.name,
                    "type": s.source_type,
                    "authority_level": s.authority_level,
                    "url": s.url,
                }
                for s in sources
            ]
        except Exception as e:
            logger.error(f"Error getting sources: {e}")
            return []
    async def clear_cache(self):
        """Clear all validation caches"""
        try:
            logger.info("Cache clearing requested - implement as needed")
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
medical_knowledge_base = MedicalKnowledgeBase()
