import logging
from typing import Optional, List
from app.services.translation_service import translation_service
logger = logging.getLogger(__name__)
class JeevoOnboarding:
    @staticmethod
    def welcome_message() -> str:
        return translation_service.get("en", "onboarding", "welcome")
    @staticmethod
    def get_language_from_number(num: str) -> Optional[str]:
        lang_map = {
            "1": "hi", "2": "en", "3": "mr",
            "4": "gu", "5": "bn", "6": "ta",
            "7": "te", "8": "kn", "9": "ml", "10": "pa"
        }
        return lang_map.get(num.strip())
    @staticmethod
    def get_name_request(lang: str) -> str:
        return translation_service.get(lang, "onboarding", "name_request")
    @staticmethod
    def get_location_request(lang: str) -> str:
        return translation_service.get(lang, "onboarding", "location_request")
    @staticmethod
    def get_service_selection(lang: str, name: str) -> str:
        return translation_service.get(lang, "onboarding", "service_selection", name=name)
    @staticmethod
    def get_profile_update_menu(lang: str) -> str:
        return translation_service.get(lang, "onboarding", "profile_update")
    @staticmethod
    def get_quick_help(lang: str, name: str = None) -> str:
        return translation_service.get(lang, "onboarding", "quick_help", name=name)
    @staticmethod
    def get_family_setup(lang: str) -> str:
        return translation_service.get(lang, "onboarding", "family_setup")
    @staticmethod
    def get_vaccination_setup(lang: str) -> str:
        return translation_service.get(lang, "onboarding", "vaccination_setup")
    @staticmethod
    def get_completion_message(lang: str, name: str, services_enabled: List[str]) -> str:
        services_text = "\n".join([f"✅ {s}" for s in services_enabled])
        return translation_service.get(lang, "onboarding", "completion_message", name=name, services_text=services_text)
jeevo_onboarding = JeevoOnboarding()
