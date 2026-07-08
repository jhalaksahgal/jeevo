"""
Comprehensive Test Suite for Source-Based Medical Validation System
Tests all features of the new semantic validation engine
"""

import asyncio
import json
import sys
import os
from datetime import datetime
from typing import List, Dict

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.database.models import (
    MedicalSource, MedicalCondition, MedicalFact, 
    ResponseValidation, ExtractedClaim, FactCheckResult,
    User, Conversation
)
from app.database.repositories import (
    MedicalSourceRepository, MedicalConditionRepository,
    MedicalFactRepository
)
from app.services.medical_validation_service import MedicalValidationService
from app.services.medical_knowledge_base_service import medical_knowledge_base
from app.services.medical_source_loader import MedicalSourceLoader
from app.services.semantic_validation_engine import semantic_validator


# ==================== CONFIGURATION ====================
DATABASE_URL = "sqlite+aiosqlite:///./test_db.sqlite"
TEST_RESULTS = []


def print_header(text: str):
    """Print formatted header"""
    print(f"\n{'=' * 80}")
    print(f"  {text}")
    print(f"{'=' * 80}\n")


def print_test(name: str, passed: bool, details: str = ""):
    """Print test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status} | {name}")
    if details:
        print(f"       {details}")
    TEST_RESULTS.append({"name": name, "passed": passed, "details": details})


async def init_database():
    """Initialize test database"""
    import os
    # Clean up old test database
    if os.path.exists("test_db.sqlite"):
        os.remove("test_db.sqlite")
    
    engine = create_async_engine(DATABASE_URL, echo=False, connect_args={"timeout": 30, "check_same_thread": False})
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        await MedicalSourceLoader.load_all(session)
        await session.commit()
    
    return async_session, engine


async def test_sources_loaded(session_factory):
    """Test 1: Verify medical sources are loaded"""
    print_header("TEST 1: Medical Sources Initialization")
    
    async with session_factory() as session:
        sources = await MedicalSourceRepository.get_active_sources(session)
        
        print(f"Loaded {len(sources)} authoritative medical sources:\n")
        for source in sources:
            print(f"  • {source.name}")
            print(f"    Authority Level: {source.authority_level} | URL: {source.url}\n")
        
        passed = len(sources) >= 4  # At least WHO, ICMR, MOH, NIH
        print_test("Medical Sources Loaded", passed, f"Sources: {len(sources)}")
        
        return sources


async def test_conditions_loaded(session_factory):
    """Test 2: Verify medical conditions are loaded"""
    print_header("TEST 2: Medical Conditions Initialization")
    
    async with session_factory() as session:
        # Get sample conditions (use correct capitalization)
        fever = await MedicalConditionRepository.get_by_name(session, "Fever")
        malaria = await MedicalConditionRepository.get_by_name(session, "Malaria")
        diabetes = await MedicalConditionRepository.get_by_name(session, "Diabetes")
        
        print("Sample Conditions Loaded:")
        for cond in [fever, malaria, diabetes]:
            if cond:
                print(f"\n  📋 {cond.name.upper()}")
                print(f"     ICD Code: {cond.icd10_code}")
                print(f"     Symptoms: {len(cond.symptoms or [])} documented")
                print(f"     Treatments: {len(cond.treatments or [])} documented")
                print(f"     Severity: {cond.severity or 'Not specified'}")
        
        passed = fever and malaria and diabetes
        print_test("Medical Conditions Loaded", passed, f"Conditions found: fever={fever is not None}, malaria={malaria is not None}, diabetes={diabetes is not None}")


async def test_symptom_verification(session_factory):
    """Test 3: Verify symptom checking against knowledge base"""
    print_header("TEST 3: Symptom Verification Against Sources")
    
    async with session_factory() as session:
        test_cases = [
            ("high fever", True, "Should be found in fever condition"),
            ("rash", True, "Symptom of dengue fever"),
            ("persistent cough", True, "TB symptom"),
            ("zxcvbnm_not_a_symptom", False, "Nonsense symptom"),
        ]
        
        print("Testing symptom verification:\n")
        results_summary = {"verified": 0, "expected": 0}
        
        for symptom, should_verify, reason in test_cases:
            is_verified, confidence, matches = await medical_knowledge_base.verify_symptom(
                session, symptom
            )
            
            passed = is_verified == should_verify
            status = "✓" if is_verified else "✗"
            print(f"  {status} '{symptom}'")
            print(f"     Expected: {should_verify}, Got: {is_verified}")
            print(f"     Confidence: {confidence:.2f}")
            print(f"     Reason: {reason}\n")
            
            if is_verified == should_verify:
                results_summary["expected"] += 1
            results_summary["verified"] += 1
            
            print_test(f"Symptom Verification: {symptom}", passed, f"Confidence: {confidence:.2f}")
        
        overall_pass = results_summary["expected"] == results_summary["verified"]
        print(f"\nResults: {results_summary['expected']}/{results_summary['verified']} correct")


async def test_claim_extraction(session_factory):
    """Test 4: Extract medical claims from LLM response"""
    print_header("TEST 4: Medical Claim Extraction from Response")
    
    async with session_factory() as session:
        test_responses = [
            {
                "response": "For fever, take paracetamol 500mg and rest for 2 days. If symptoms persist, see a doctor.",
                "expected_claims": 3,  # fever, paracetamol, rest
                "description": "Simple fever advice"
            },
            {
                "response": "Take aspirin instead of paracetamol for pain relief. It works faster and is safer for children.",
                "expected_claims": 2,
                "description": "Potentially problematic advice (aspirin for children)"
            },
            {
                "response": "Dengue is transmitted by mosquitoes. Use nets and repellent. No specific antiviral exists but supportive care helps.",
                "expected_claims": 3,
                "description": "Information-heavy response"
            },
        ]
        
        for test_case in test_responses:
            print(f"\n📝 Response: {test_case['response'][:80]}...")
            print(f"   Type: {test_case['description']}\n")
            
            claims = await semantic_validator.claim_extractor.extract_claims(
                test_case['response']
            )
            
            print(f"   Extracted Claims ({len(claims)}):")
            for i, claim in enumerate(claims, 1):
                print(f"     {i}. [{claim.get('type', 'unknown').upper()}] {claim['text']}")
                print(f"        Testable: {claim.get('testable', False)} | Confidence: {claim.get('confidence', 0):.2f}")
            
            passed = len(claims) >= max(0, test_case['expected_claims'] - 1)
            print_test(
                f"Claim Extraction: {test_case['description']}", 
                passed, 
                f"Found {len(claims)} claims, expected ~{test_case['expected_claims']}"
            )


async def test_comprehensive_validation(session_factory):
    """Test 5: Full semantic validation pipeline"""
    print_header("TEST 5: Comprehensive Semantic Validation")
    
    async with session_factory() as session:
        test_cases = [
            {
                "query": "I have high fever for 3 days",
                "response": "Rest well, drink fluids, and take paracetamol 500mg. Visit doctor if fever persists.",
                "expected_risk": "low",
                "description": "Good, appropriate medical advice"
            },
            {
                "query": "My child has high fever",
                "response": "Give aspirin 500mg to reduce fever. Antibiotics will prevent complications.",
                "expected_risk": "high",
                "description": "Problematic advice (aspirin for child, unnecessary antibiotics)"
            },
            {
                "query": "How do I prevent malaria?",
                "response": "Use mosquito nets, install indoor spraying, and take prophylaxis in endemic areas. Sleep under treated nets.",
                "expected_risk": "low",
                "description": "Good prevention guidance"
            },
            {
                "query": "Chest pain and difficulty breathing",
                "response": "This might be anxiety. Try relaxation techniques.",
                "expected_risk": "high",
                "description": "Dangerous - ignores emergency symptoms"
            },
        ]
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n📊 TEST CASE {i}: {test_case['description']}")
            print(f"   Query: {test_case['query']}")
            print(f"   Response: {test_case['response'][:80]}...\n")
            
            validation_result = await MedicalValidationService.validate_response(
                db=session,
                user_query=test_case['query'],
                bot_response=test_case['response'],
                confidence_score=0.7,
                use_semantic_validation=True,
                llm_model="test"
            )
            
            print(f"   Validation Results:")
            print(f"     Risk Level: {validation_result.risk_level}")
            print(f"     Requires Escalation: {validation_result.requires_escalation}")
            print(f"     Escalation Trigger: {validation_result.escalation_trigger or 'None'}")
            print(f"     Semantic Confidence: {validation_result.semantic_confidence:.2f}")
            print(f"     Accuracy Score: {validation_result.accuracy_score:.2f}")
            print(f"     Appropriateness Score: {validation_result.appropriateness_score:.2f}")
            print()
            print(f"   Claim Analysis:")
            print(f"     Verified: {len(validation_result.verified_claims)} claims")
            print(f"     Contradicted: {len(validation_result.contradicted_claims)} claims")
            print()
            print(f"   Sources Used: {len(validation_result.sources_used)}")
            
            # Check if risk level matches expectation
            passed = validation_result.risk_level == test_case['expected_risk']
            print_test(
                f"Full Validation: {test_case['description']}", 
                passed,
                f"Risk: {validation_result.risk_level} (expected {test_case['expected_risk']})"
            )


async def test_keyword_detection(session_factory):
    """Test 6: Legacy keyword detection still works"""
    print_header("TEST 6: Legacy Keyword Detection (Hybrid Mode)")
    
    async with session_factory() as session:
        test_cases = [
            {
                "query": "I have chest pain and heart attack symptoms",
                "response": "Rest at home",
                "should_escalate": True,
                "description": "Emergency keywords detected"
            },
            {
                "query": "Fever",
                "response": "Take paracetamol",
                "should_escalate": False,
                "description": "Normal medical query"
            },
            {
                "query": "My infant has convulsions",
                "response": "It's normal",
                "should_escalate": True,
                "description": "High-risk condition (infant + emergency)"
            },
        ]
        
        print("Testing keyword-based emergency detection:\n")
        
        for test_case in test_cases:
            result = await MedicalValidationService.validate_response(
                db=session,
                user_query=test_case['query'],
                bot_response=test_case['response'],
                confidence_score=0.5,
                use_semantic_validation=False,  # Test keyword-only
                llm_model="test"
            )
            
            print(f"  Query: {test_case['query']}")
            print(f"  Emergency Keywords: {result.emergency_keywords_detected}")
            print(f"  High-Risk Keywords: {result.high_risk_keywords_detected}")
            print(f"  Requires Escalation: {result.requires_escalation}")
            print(f"  Risk Level: {result.risk_level}\n")
            
            passed = result.requires_escalation == test_case['should_escalate']
            print_test(
                f"Keyword Detection: {test_case['description']}", 
                passed,
                f"Escalation: {result.requires_escalation} (expected {test_case['should_escalate']})"
            )


def print_sources_documentation():
    """Print detailed documentation on validation sources"""
    print_header("VALIDATION SOURCES & KNOWLEDGE BASE DOCUMENTATION")
    
    doc = """
╔════════════════════════════════════════════════════════════════════════════╗
║           MEDICAL VALIDATION SYSTEM - SOURCES & KNOWLEDGE BASE             ║
╚════════════════════════════════════════════════════════════════════════════╝

█████ 1. AUTHORITATIVE SOURCES
═══════════════════════════════════════════════════════════════════════════

The system validates against the following authoritative medical sources:

┌─ TIER 1 (Highest Authority - Authority Level: 1) ─────────────────────────┐
│                                                                             │
│ • WHO (World Health Organization)                                         │
│   URL: https://www.who.int/                                               │
│   Scope: Global health guidelines, epidemic prevention, disease control   │
│                                                                             │
│ • ICMR (Indian Council of Medical Research)                               │
│   URL: https://www.icmr.gov.in/                                           │
│   Scope: India-specific medical research, treatment protocols             │
│                                                                             │
│ • MOH (Ministry of Health & Family Welfare, India)                        │
│   URL: https://mohfw.gov.in/                                              │
│   Scope: Indian government health guidelines, vaccine schedules           │
│                                                                             │
│ • NACO (National AIDS Control Organization - India)                       │
│   URL: https://naco.gov.in/                                               │
│   Scope: HIV/AIDS prevention, treatment, and management in India         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─ TIER 2 (Secondary Authority - Authority Level: 2) ──────────────────────┐
│                                                                             │
│ • IAP (Indian Academy of Pediatrics)                                      │
│   URL: https://www.iapindia.org/                                          │
│   Scope: Pediatric-specific guidelines, vaccines, child health            │
│                                                                             │
│ • NIH (National Institutes of Health - USA)                               │
│   URL: https://www.nih.gov/                                               │
│   Scope: Medical research, evidence-based guidelines                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘


█████ 2. KNOWLEDGE BASE STRUCTURE
═══════════════════════════════════════════════════════════════════════════

The knowledge base stores medical information in a hierarchical structure:

┌─ DATABASE TABLES ────────────────────────────────────────────────────────┐
│                                                                            │
│ MedicalSource
│ ├─ id: Unique identifier
│ ├─ name: Source name (WHO, ICMR, etc.)
│ ├─ source_type: Type classification
│ ├─ authority_level: 1-5 (1=highest, 5=lowest)
│ └─ url: Official source URL
│
│ MedicalCondition
│ ├─ id: Condition ID
│ ├─ condition_name: Disease/condition name (e.g., "Fever", "Malaria")
│ ├─ icd_code: WHO ICD-10 classification code
│ ├─ primary_symptoms: Array of documented symptoms
│ ├─ warning_signs: Serious symptoms requiring urgent care
│ ├─ causes: Documented causes
│ ├─ risk_factors: Risk factors
│ ├─ first_line_treatment: WHO/validated first-line treatments
│ ├─ second_line_treatment: Alternative treatments
│ ├─ contraindications: Treatments/drugs to AVOID
│ ├─ prevention_measures: Prevention methods
│ ├─ affected_age_groups: Which ages are affected
│ ├─ source_ids: List of authoritative sources
│ ├─ confidence_level: 1=highly verified, 5=experimental
│ └─ last_verified: When this data was last verified
│
│ MedicalFact
│ ├─ id: Individual fact ID
│ ├─ fact_text: The factual statement (e.g., "high fever is a symptom")
│ ├─ fact_type: symptom|treatment|prevention|drug|warning|etc.
│ ├─ condition_id: Which condition(s) this relates to
│ ├─ source_ids: Which authoritative sources confirm this
│ ├─ is_verified: Boolean - verified against sources
│ ├─ verification_level: 1=certain, 5=uncertain
│ └─ conflicting_facts: Related contradicting facts
│
│ ExtractedClaim
│ ├─ response_validation_id: Which response this came from
│ ├─ claim_text: The statement from the LLM response
│ ├─ claim_type: Type of claim (symptom, treatment, warning, etc.)
│ └─ testable: Whether this can be verified against sources
│
│ FactCheckResult
│ ├─ extracted_claim_id: Which claim was checked
│ ├─ check_status: verified|contradicted|concerning|unverifiable
│ ├─ confidence_score: 0.0-1.0 confidence in the check
│ ├─ matched_medical_fact_ids: Which facts matched/contradicted
│ ├─ source_ids: Which sources support the fact-check
│ ├─ concern_level: minor|moderate|serious
│ └─ contradiction_details: Why there's a contradiction
│
└─────────────────────────────────────────────────────────────────────────┘


█████ 3. CURRENTLY LOADED CONDITIONS (Knowledge Base)
═══════════════════════════════════════════════════════════════════════════

The system includes ~10 common conditions with full documentation:

 1. FEVER (ICD-10: R50)
    • Symptoms: high body temperature, chills, sweating, body ache
    • Treatments: rest, hydration, paracetamol 500mg, ibuprofen 400mg
    • ⚠️ Contraindications: aspirin in children under 16
    • Prevention: hygiene, vaccination
    • Sources: WHO, MOH India

 2. COUGH (ICD-10: R05)
    • Symptoms: throat irritation, phlegm, chest discomfort
    • Treatments: rest, cough syrup, honey, fluids
    • ⚠️ Contraindications: NSAIDs in severe asthma
    • Prevention: avoid irritants, humidity
    • Sources: WHO, MOH India

 3. DIARRHEA (ICD-10: A19)
    • Symptoms: loose stools, frequency, abdominal pain, dehydration
    • Treatments: oral rehydration (ORS), zinc supplementation, rest
    • ⚠️ Contraindications: antibiotics without bacterial confirmation
    • Prevention: clean water, hand hygiene
    • Sources: WHO, MOH India

 4. HEADACHE (ICD-10: R51)
    • Symptoms: head pain, sensitivity to light, nausea
    • Treatments: paracetamol, ibuprofen, rest, hydration
    • Prevention: stress management, hydration
    • Sources: WHO, NIH

 5. MALARIA (ICD-10: B54)
    • Symptoms: fever, chills, sweating, muscle pain, headache
    • ⚠️ Warning Signs: severe fever, confusion, convulsions
    • Treatments: antimalarial drugs, ACT therapy, supportive care
    • ⚠️ Contraindications: certain drugs with G6PD deficiency
    • Prevention: mosquito nets, indoor spraying
    • Sources: WHO, MOH India, NACO

 6. DENGUE FEVER (ICD-10: A90)
    • Symptoms: fever, rash, joint pain, eye pain, bleeding symptoms
    • ⚠️ Warning Signs: bleeding, shock, organ failure
    • Treatments: supportive care (NO antiviral exists)
    • Prevention: mosquito control, nets
    • Sources: WHO, MOH India

 7. TYPHOID FEVER (ICD-10: A01)
    • Symptoms: sustained high fever, delirium, diarrhea
    • ⚠️ Warning Signs: perforation, encephalopathy
    • Treatments: antibiotics, supportive care
    • Prevention: vaccination, clean water
    • Sources: WHO, MOH India

 8. TUBERCULOSIS (ICD-10: A15)
    • Symptoms: persistent cough, fever, night sweats, weight loss
    • Treatments: DOTS therapy (isoniazid, rifampicin, pyrazinamide)
    • Prevention: BCG vaccination, contact tracing
    • Sources: WHO, MOH India

 9. HYPERTENSION (ICD-10: I10)
    • Symptoms: often asymptomatic, headache, chest pain
    • Treatments: lifestyle, antihypertensives, low-salt diet
    • Prevention: weight management, exercise
    • Sources: WHO, MOH India

10. DIABETES (ICD-10: E11)
    • Symptoms: polyuria, polydipsia, weight loss, fatigue
    • Treatments: diet control, metformin, insulin, exercise
    • Prevention: weight management, healthy diet
    • Sources: WHO, MOH India


█████ 4. VALIDATION PROCESS - STEP BY STEP
═══════════════════════════════════════════════════════════════════════════

When an LLM responds to a medical query, the validation flow is:

┌─ STEP 1: EMERGENCY KEYWORD DETECTION (Fast Path) ────────────────────────┐
│ Time: ~1ms                                                                 │
│ If detected → IMMEDIATE ESCALATION ⚠️                                    │
│                                                                            │
│ Emergency Keywords:                                                        │
│ "emergency", "urgent", "hospital", "ambulance", "cardiac", "heart attack" │
│ "stroke", "seizure", "unconscious", "bleeding", "poisoning", "overdose"  │
│ "suicide", "death", "trauma"                                              │
│                                                                            │
│ Action: If found → Risk = CRITICAL, Escalate immediately                 │
└──────────────────────────────────────────────────────────────────────────┘

┌─ STEP 2: HIGH-RISK + LOW-CONFIDENCE DETECTION ───────────────────────────┐
│ Time: ~1ms                                                                 │
│ If found + confidence < 0.7 → ESCALATE                                    │
│                                                                            │
│ High-Risk Keywords:                                                        │
│ "pregnant", "infant", "cancer", "diabetes", "kidney disease"              │
│ "mental health", "addiction", "medication", "prescription"                │
│                                                                            │
│ Action: Risk = HIGH, Check confidence                                     │
└──────────────────────────────────────────────────────────────────────────┘

┌─ STEP 3: SEMANTIC VALIDATION (Accurate Path) ────────────────────────────┐
│ Time: ~500-2000ms (calls LLM for claim extraction)                        │
│ Uses AI + Knowledge Base for fact-checking                                │
│                                                                            │
│ Step 3a: CLAIM EXTRACTION                                                 │
│          ├─ LLM analyzes response text                                    │
│          ├─ Extracts structured claims: [claim_text, type, confidence]   │
│          ├─ Types: symptom|treatment|prevention|warning|diagnosis        │
│          └─ Only testable claims are extracted                            │
│                                                                            │
│ Step 3b: CLAIM VERIFICATION                                               │
│          For each extracted claim:                                         │
│          ├─ Search medical knowledge base                                  │
│          ├─ Find matching MedicalFact entries                              │
│          ├─ Check against authoritative sources                            │
│          └─ Classify as: verified|contradicted|concerning|unverifiable   │
│                                                                            │
│ Step 3c: RISK CALCULATION                                                 │
│          ├─ Count verified claims                                          │
│          ├─ Count contradicted claims                                      │
│          ├─ Identify dangerous treatments/advice                           │
│          ├─ Check contraindications (e.g., aspirin for children)          │
│          └─ Score appropriateness & accuracy                               │
│                                                                            │
│ Result: Detailed validation report with all fact-checks                   │
└──────────────────────────────────────────────────────────────────────────┘


█████ 5. VALIDATION OUTPUT - WHAT YOU GET
═══════════════════════════════════════════════════════════════════════════

ValidationResult contains:

LEGACY FIELDS (Keyword-based):
├─ risk_level: "low", "medium", "high", "critical"
├─ requires_escalation: boolean
├─ emergency_keywords_detected: ["heart attack", "bleeding", ...]
├─ high_risk_keywords_detected: ["pregnant", "cancer", ...]
└─ validation_message: human-readable reason

NEW FIELDS (Semantic-based):
├─ validation_method: "keyword_only", "source_based", or "hybrid"
├─ total_claims: number of claims extracted
├─ verified_claims: claims that match authoritative sources
├─ contradicted_claims: claims that conflict with sources
├─ unverifiable_claims: claims that can't be verified
├─ concerning_claims: medically concerning even if not wrong
├─ semantic_confidence: 0.0-1.0 (confidence in fact-checking)
├─ accuracy_score: 0.0-1.0 (% of verified claims)
├─ appropriateness_score: 0.0-1.0 (is advice suitable?)
├─ completeness_score: 0.0-1.0 (response completeness)
├─ sources_used: ["WHO", "ICMR", ...]
├─ extracted_claims: detailed list of all claims extracted
├─ fact_checks: detailed results for each claim
├─ escalation_trigger: specific reason for escalation
└─ validation_duration_ms: performance timing


█████ 6. CONTRADICTION DETECTION EXAMPLES
═══════════════════════════════════════════════════════════════════════════

The system catches dangerous advice like:

❌ EXAMPLE 1: "Give aspirin to your 5-year-old for fever"
   Contradiction: ICMR/WHO explicitly contraindicate aspirin < 16 years
   Status: CONTRADICTED
   Action: Risk = HIGH, Escalate, Flag contraindication

❌ EXAMPLE 2: "Dengue has no treatment, so use antibiotics"
   Contradiction: WHO confirms dengue has NO antiviral, antibiotics unhelpful
   Status: CONTRADICTED
   Action: Risk = MEDIUM, Provide correct info first-line: supportive care

❌ EXAMPLE 3: "Don't use mosquito nets, use pesticides instead"
   Contradiction: WHO recommends nets + pesticides, not instead-of
   Status: CONCERNING
   Action: Risk = MEDIUM, Flag incomplete advice

✅ EXAMPLE 4: "Rest, hydrate, take paracetamol 500mg for fever"
   Match: All verified in WHO/ICMR guidelines
   Status: VERIFIED
   Action: Risk = LOW, Send response


█████ 7. PERFORMANCE CHARACTERISTICS
═══════════════════════════════════════════════════════════════════════════

Keyword Detection:      ~1ms    (instant, always runs)
Semantic Validation:    ~500-2000ms (calls LLM, runs if no emergency)
Caching:               ~10ms    (subsequent similar queries)
Database Lookup:        ~20-50ms (fact verification)

Total Validation Time:   ~1-2 seconds per response


█████ 8. EXTENSIBILITY
═══════════════════════════════════════════════════════════════════════════

New conditions can be added:
  1. Add entry to MedicalSourceLoader.CONDITIONS
  2. Run MedicalSourceLoader.load_all(db)
  3. New facts automatically indexed

New sources can be added:
  1. Add to MedicalSourceLoader.SOURCES
  2. Load via MedicalSourceRepository.create_source()
  3. Link conditions to new sources

Custom validation rules:
  1. Create entry in ValidationRule table
  2. Specify rule_logic (JSON)
  3. Associated with conditions/sources
"""
    
    print(doc)


async def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("  MEDICAL RESPONSE VALIDATION SYSTEM - COMPREHENSIVE TEST SUITE")
    print("="*80 + "\n")
    
    # Initialize database
    print("🔧 Initializing test database...")
    session_factory, engine = await init_database()
    print("✅ Database initialized with medical knowledge base\n")
    
    try:
        # Run tests
        await test_sources_loaded(session_factory)
        await test_conditions_loaded(session_factory)
        await test_symptom_verification(session_factory)
        await test_claim_extraction(session_factory)
        await test_comprehensive_validation(session_factory)
        await test_keyword_detection(session_factory)
        
        # Print documentation
        print_sources_documentation()
        
        # Summary
        print_header("TEST SUMMARY")
        passed = sum(1 for result in TEST_RESULTS if result['passed'])
        total = len(TEST_RESULTS)
        
        print(f"Total Tests: {total}")
        print(f"Passed: {passed} ✅")
        print(f"Failed: {total - passed} ❌")
        print(f"Success Rate: {(passed/total*100):.1f}%\n")
        
        if passed == total:
            print("🎉 ALL TESTS PASSED! 🎉\n")
        else:
            print("⚠️  SOME TESTS FAILED\n")
            print("Failed tests:")
            for result in TEST_RESULTS:
                if not result['passed']:
                    print(f"  ❌ {result['name']}")
                    if result['details']:
                        print(f"     {result['details']}")
    
    finally:
        await engine.dispose()


if __name__ == "__main__":
    print("\n🚀 Starting Medical Validation Test Suite...\n")
    asyncio.run(main())
