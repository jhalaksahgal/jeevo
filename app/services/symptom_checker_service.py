import logging
from typing import Dict, List, Optional
logger = logging.getLogger(__name__)
class SymptomChecker:
    import json
    import os
    try:
        workflows_path = os.path.join(os.path.dirname(__file__), "..", "resources", "symptom_workflows.json")
        with open(workflows_path, "r", encoding="utf-8") as f:
            SYMPTOM_WORKFLOWS = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load symptom workflows: {e}")
        SYMPTOM_WORKFLOWS = {}
    @staticmethod
    def detect_symptom(text: str) -> Optional[str]:
        text_lower = text.lower()
        for symptom in SymptomChecker.SYMPTOM_WORKFLOWS.keys():
            if symptom in text_lower:
                return symptom
        return None
    @staticmethod
    def get_assessment_flow(symptom: str) -> Optional[Dict]:
        return SymptomChecker.SYMPTOM_WORKFLOWS.get(symptom.lower())
    @staticmethod
    def get_next_question(symptom: str, current_step: int = 0) -> Optional[str]:
        workflow = SymptomChecker.get_assessment_flow(symptom)
        if not workflow:
            return None
        questions = workflow.get("questions", [])
        if current_step < len(questions):
            return questions[current_step]
        return None
    @staticmethod
    def check_red_flags(symptom: str, user_responses: List[str]) -> Dict:
        workflow = SymptomChecker.get_assessment_flow(symptom)
        if not workflow:
            return {"risk_level": "unknown", "message": ""}
        response_text = " ".join(user_responses).lower()
        red_flags = workflow.get("red_flags", [])
        high_risk = workflow.get("high_risk_indicators", [])
        has_red_flags = any(flag.lower() in response_text for flag in red_flags)
        has_high_risk = any(indicator.lower() in response_text for indicator in high_risk)
        if has_red_flags:
            return {
                "risk_level": "critical",
                "message": workflow.get("advice_if_severe", "Seek emergency care immediately."),
            }
        elif has_high_risk:
            return {
                "risk_level": "high",
                "message": workflow.get("advice_if_severe", "Please consult a doctor soon."),
            }
        else:
            return {
                "risk_level": "moderate",
                "message": "Continue monitoring your symptoms and consult if they worsen.",
            }
    @staticmethod
    def get_first_question(symptom: str) -> Optional[str]:
        return SymptomChecker.get_next_question(symptom, 0)
symptom_checker = SymptomChecker()
