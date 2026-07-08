"""
Medical Source Loader
Loads and initializes authoritative medical data into the knowledge base
"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from typing import Dict, List, Any
from app.database.repositories import (
    MedicalSourceRepository,
    MedicalConditionRepository,
    MedicalFactRepository,
)
logger = logging.getLogger(__name__)
class MedicalSourceLoader:
    """
    Load medical data from authoritative sources and populate the knowledge base.
    Includes WHO, Indian Ministry of Health, and other verified sources.
    """
    SOURCES = {
        "WHO": {
            "name": "World Health Organization",
            "type": "who",
            "authority_level": 1,
            "url": "https://www.who.int/",
            "description": "Global health authority guidelines",
        },
        "ICMR": {
            "name": "Indian Council of Medical Research",
            "type": "indian_health",
            "authority_level": 1,
            "url": "https://www.icmr.gov.in/",
            "description": "Indian medical research authority",
        },
        "MOH_INDIA": {
            "name": "Ministry of Health & Family Welfare, India",
            "type": "indian_health",
            "authority_level": 1,
            "url": "https://mohfw.gov.in/",
            "description": "Indian government health ministry",
        },
        "IAP": {
            "name": "Indian Academy of Pediatrics",
            "type": "professional_org",
            "authority_level": 2,
            "url": "https://www.iapindia.org/",
            "description": "Pediatric guidelines for India",
        },
        "NACO": {
            "name": "National AIDS Control Organization",
            "type": "disease_specific",
            "authority_level": 1,
            "url": "https://naco.gov.in/",
            "description": "HIV/AIDS guidelines India",
        },
        "NIH": {
            "name": "National Institutes of Health",
            "type": "research_org",
            "authority_level": 2,
            "url": "https://www.nih.gov/",
            "description": "US medical research",
        },
    }
    CONDITIONS = [
        {
            "name": "Fever",
            "icd_code": "R50",
            "symptoms": ["high body temperature", "chills", "sweating", "body ache"],
            "treatments": ["rest", "hydration", "paracetamol 500mg", "ibuprofen 400mg"],
            "contraindications": ["aspirin in children under 16"],
            "prevention": ["hygiene", "vaccination", "avoid close contact with sick people"],
            "sources": ["WHO", "MOH_INDIA"],
        },
        {
            "name": "Cough",
            "icd_code": "R05",
            "symptoms": ["throat irritation", "phlegm", "chest discomfort"],
            "treatments": ["rest", "cough syrup", "honey", "fluids"],
            "contraindications": ["NSAIDs in severe asthma"],
            "prevention": ["avoid irritants", "humidity", "ventilation"],
            "sources": ["WHO", "MOH_INDIA"],
        },
        {
            "name": "Diarrhea",
            "icd_code": "A19",
            "symptoms": [
                "loose stools",
                "frequency increased",
                "abdominal pain",
                "dehydration",
            ],
            "treatments": ["oral rehydration", "zinc supplementation", "rest"],
            "contraindications": ["antibiotics without bacterial confirmation"],
            "prevention": ["clean water", "hand hygiene", "safe food handling"],
            "sources": ["WHO", "MOH_INDIA"],
            "age_specific": {"children": ["ORS", "zinc"], "adults": ["ORS", "rest"]},
        },
        {
            "name": "Headache",
            "icd_code": "R51",
            "symptoms": ["head pain", "sensitivity to light", "nausea"],
            "treatments": ["paracetamol", "ibuprofen", "rest", "hydration"],
            "contraindications": ["excessive medication use"],
            "prevention": ["stress management", "hydration", "sleep"],
            "sources": ["WHO", "NIH"],
        },
        {
            "name": "Malaria",
            "icd_code": "B54",
            "symptoms": ["fever", "chills", "sweating", "muscle pain", "headache"],
            "treatments": ["antimalarial drugs", "ACT therapy", "supportive care"],
            "warning_signs": ["severe fever", "confusion", "convulsions"],
            "contraindications": ["certain drugs with G6PD deficiency"],
            "prevention": ["mosquito nets", "indoor spraying", "prophylaxis in endemic areas"],
            "sources": ["WHO", "MOH_INDIA", "NACO"],
        },
        {
            "name": "Dengue Fever",
            "icd_code": "A90",
            "symptoms": [
                "fever",
                "rash",
                "joint pain",
                "eye pain",
                "bleeding symptoms",
            ],
            "treatments": ["supportive care", "no specific antiviral"],
            "warning_signs": ["bleeding", "shock", "organ failure"],
            "prevention": ["mosquito control", "nets", "avoid travel to endemic areas"],
            "sources": ["WHO", "MOH_INDIA"],
        },
        {
            "name": "Typhoid Fever",
            "icd_code": "A01",
            "symptoms": ["sustained high fever", "rose spots", "delirium", "diarrhea"],
            "treatments": ["antibiotics", "supportive care", "fluids"],
            "warning_signs": ["perforation", "encephalopathy"],
            "prevention": ["vaccination", "clean water", "food safety"],
            "sources": ["WHO", "MOH_INDIA"],
        },
        {
            "name": "Tuberculosis",
            "icd_code": "A15",
            "symptoms": [
                "persistent cough",
                "fever",
                "night sweats",
                "weight loss",
                "hemoptysis",
            ],
            "treatments": ["DOTS therapy", "isoniazid", "rifampicin", "pyrazinamide"],
            "warning_signs": ["drug-resistant TB", "immunosuppression"],
            "prevention": ["BCG vaccination", "contact tracing", "ventilation"],
            "sources": ["WHO", "MOH_INDIA"],
        },
        {
            "name": "Hypertension",
            "icd_code": "I10",
            "symptoms": ["often asymptomatic", "headache", "chest pain"],
            "treatments": ["lifestyle changes", "antihypertensives", "diet"],
            "prevention": ["weight management", "exercise", "low salt intake"],
            "sources": ["WHO", "MOH_INDIA"],
        },
        {
            "name": "Diabetes",
            "icd_code": "E11",
            "symptoms": ["polyuria", "polydipsia", "weight loss", "fatigue"],
            "treatments": ["diet control", "metformin", "insulin", "exercise"],
            "prevention": ["weight management", "healthy diet", "exercise"],
            "sources": ["WHO", "MOH_INDIA"],
        },
    ]
    @staticmethod
    async def initialize_sources(db: AsyncSession) -> bool:
        """Load medical sources into database"""
        try:
            logger.info("Initializing medical sources...")
            for source_code, source_info in MedicalSourceLoader.SOURCES.items():
                source_repo = MedicalSourceRepository(db)
                existing = await source_repo.get_source_by_name(
                    name=source_info["name"]
                )
                if existing:
                    logger.info(f"Source already exists: {source_info['name']}")
                    continue
                source = await source_repo.create_source(
                    name=source_info["name"],
                    url=source_info.get("url"),
                    description=source_info.get("description"),
                    authority_level=source_info.get("authority_level", 1),
                )
                logger.info(f"Created source: {source.name}")
            logger.info("✅ Medical sources initialized")
            return True
        except Exception as e:
            logger.error(f"Error initializing sources: {e}")
            return False
    @staticmethod
    async def initialize_conditions(db: AsyncSession) -> bool:
        """Load medical conditions into database"""
        try:
            logger.info("Initializing medical conditions...")
            for condition_data in MedicalSourceLoader.CONDITIONS:
                try:
                    condition_name = condition_data.get("name", "Unknown")
                    cond_repo = MedicalConditionRepository(db)
                    existing = await cond_repo.get_by_name(
                        name=condition_name
                    )
                    if existing:
                        logger.info(f"Condition already exists: {condition_name}")
                        continue
                    condition = await cond_repo.create_condition(
                        name=condition_name,
                        icd10_code=condition_data.get("icd_code", ""),
                        description=condition_data.get("description", ""),
                        symptoms=condition_data.get("symptoms", []),
                        treatments=condition_data.get("treatments", []),
                        contraindications=condition_data.get("contraindications"),
                    )
                    logger.info(f"Created condition: {condition.name}")
                    for source_name in condition_data.get("sources", []):
                        try:
                            source_repo = MedicalSourceRepository(db)
                            source = await source_repo.get_source_by_name(
                                name=MedicalSourceLoader.SOURCES[source_name]["name"]
                            )
                            if not source:
                                logger.warning(f"Source {source_name} not found")
                                continue
                            for symptom in condition_data.get("symptoms", []):
                                try:
                                    fact_repo = MedicalFactRepository(db)
                                    await fact_repo.create_fact(
                                        condition_id=condition.id,
                                        source_id=source.id,
                                        fact_type="symptom",
                                        fact_text=symptom,
                                    )
                                except Exception as e:
                                    logger.debug(f"Error adding symptom: {e}")
                            for treatment in condition_data.get("treatments", []):
                                try:
                                    fact_repo = MedicalFactRepository(db)
                                    await fact_repo.create_fact(
                                        condition_id=condition.id,
                                        source_id=source.id,
                                        fact_type="treatment",
                                        fact_text=treatment,
                                    )
                                except Exception as e:
                                    logger.debug(f"Error adding treatment: {e}")
                            for prevention in condition_data.get("prevention", []):
                                try:
                                    fact_repo = MedicalFactRepository(db)
                                    await fact_repo.create_fact(
                                        condition_id=condition.id,
                                        source_id=source.id,
                                        fact_type="prevention",
                                        fact_text=prevention,
                                    )
                                except Exception as e:
                                    logger.debug(f"Error adding prevention: {e}")
                        except Exception as e:
                            logger.warning(f"Error loading facts for {source_name}: {e}")
                except Exception as e:
                    logger.error(f"Error creating condition {condition_data.get('name')}: {e}")
                    continue
            logger.info("✅ Medical conditions initialized")
            return True
        except Exception as e:
            logger.error(f"Error initializing conditions: {e}")
            return False
    @staticmethod
    async def load_all(db: AsyncSession) -> bool:
        """Load all medical data"""
        try:
            await MedicalSourceLoader.initialize_sources(db)
            await MedicalSourceLoader.initialize_conditions(db)
            logger.info("✅ All medical data loaded successfully")
            return True
        except Exception as e:
            logger.error(f"Error loading medical data: {e}")
            return False
async def init_medical_data(db: AsyncSession):
    """Call this during app startup to initialize medical data"""
    await MedicalSourceLoader.load_all(db)
