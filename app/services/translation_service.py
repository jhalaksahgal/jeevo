import json
import logging
from pathlib import Path
from typing import Dict, Any
logger = logging.getLogger(__name__)
class TranslationService:
    def __init__(self, locales_dir: str = "app/locales"):
        self.locales_dir = Path(locales_dir)
        self.translations: Dict[str, Dict[str, Any]] = {}
        self.default_lang = "en"
        self._load_all_locales()
    def _load_all_locales(self):
        """Loads all JSON files from the locales directory into memory."""
        if not self.locales_dir.exists() or not self.locales_dir.is_dir():
            logger.warning(f"Locales directory {self.locales_dir} not found.")
            return
        for filepath in self.locales_dir.glob("*.json"):
            lang = filepath.stem
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    self.translations[lang] = json.load(f)
                logger.info(f"Loaded locale: {lang}")
            except Exception as e:
                logger.error(f"Failed to load locale {lang}: {e}")
    def get(self, lang: str, domain: str, key: str, **kwargs) -> str:
        """
        Get a translated string.
        :param lang: Language code (e.g., 'en', 'hi')
        :param domain: Domain/module (e.g., 'onboarding', 'risk_aggregation')
        :param key: The key inside the domain
        :param kwargs: Format arguments
        """
        if lang not in self.translations:
            lang = self.default_lang
        domain_data = self.translations.get(lang, {}).get(domain)
        if not domain_data and lang != self.default_lang:
            domain_data = self.translations.get(self.default_lang, {}).get(domain)
        if not domain_data:
            return f"[{domain}.{key}]"
        text = domain_data.get(key)
        if text is None and lang != self.default_lang:
            text = self.translations.get(self.default_lang, {}).get(domain, {}).get(key)
        if text is None:
            return f"[{domain}.{key}]"
        if kwargs:
            try:
                return text.format(**kwargs)
            except KeyError as e:
                logger.error(f"Missing format key {e} in {domain}.{key} for language {lang}")
                return text
        return text
    def get_domain(self, lang: str, domain: str) -> Dict[str, Any]:
        """Get all translations for a specific domain and language."""
        if lang not in self.translations:
            lang = self.default_lang
        domain_data = self.translations.get(lang, {}).get(domain)
        if not domain_data and lang != self.default_lang:
            domain_data = self.translations.get(self.default_lang, {}).get(domain)
        return domain_data or {}
translation_service = TranslationService()
