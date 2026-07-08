import logging
from typing import Dict, Optional
from datetime import datetime
logger = logging.getLogger(__name__)
class LocationHealthContext:
    DISEASE_BY_REGION = {
        "delhi": {
            "monsoon": ["dengue", "typhoid", "malaria", "cholera"],
            "summer": ["heat_stroke", "dehydration", "respiratory_issues"],
            "winter": ["flu", "pneumonia", "asthma"],
            "water_quality": "high",
            "aqi_average": 350,
        },
        "mumbai": {
            "monsoon": ["dengue", "malaria", "typhoid", "asthma"],
            "summer": ["heat_stroke", "cholera"],
            "winter": ["flu", "pneumonia"],
            "water_quality": "moderate",
            "aqi_average": 100,
        },
        "bangalore": {
            "monsoon": ["dengue", "infections"],
            "summer": ["heat_stroke"],
            "winter": ["flu"],
            "water_quality": "high",
            "aqi_average": 60,
        },
        "hyderabad": {
            "monsoon": ["dengue", "malaria"],
            "summer": ["heat_stroke"],
            "winter": ["respiratory"],
            "water_quality": "moderate",
            "aqi_average": 80,
        },
        "kolkata": {
            "monsoon": ["dengue", "malaria", "cholera"],
            "summer": ["heat_stroke"],
            "winter": ["pneumonia"],
            "water_quality": "low",
            "aqi_average": 100,
        },
    }
    ALLERGY_BY_SEASON = {
        "monsoon": ["mold_allergy", "fungal_infection", "respiratory_allergy"],
        "summer": ["pollen_allergy", "heat_rash"],
        "winter": ["dry_skin_allergy"],
    }
    @staticmethod
    def get_current_season() -> str:
        month = datetime.now().month
        if 6 <= month <= 9:
            return "monsoon"
        elif 3 <= month <= 5:
            return "summer"
        else:
            return "winter"
    @staticmethod
    def get_city_from_location(location_dict: Dict) -> Optional[str]:
        if not location_dict:
            return None
        city = location_dict.get("city", "")
        if isinstance(city, str):
            return city.lower().strip()
        return None
    @staticmethod
    def get_location_health_context(location_dict: Dict) -> str:
        if not location_dict:
            return ""
        city = LocationHealthContext.get_city_from_location(location_dict)
        season = LocationHealthContext.get_current_season()
        region_data = LocationHealthContext.DISEASE_BY_REGION.get(city)
        if not region_data:
            return ""
        context_parts = []
        diseases = region_data.get(season, [])
        if diseases:
            disease_str = ", ".join(disease.replace("_", " ").title() for disease in diseases)
            context_parts.append(f"Prevalent diseases in {city.title()} during {season}: {disease_str}")
        allergies = LocationHealthContext.ALLERGY_BY_SEASON.get(season, [])
        if allergies:
            allergy_str = ", ".join(allergy.replace("_", " ").title() for allergy in allergies)
            context_parts.append(f"Common allergies during {season}: {allergy_str}")
        aqi = region_data.get("aqi_average")
        if aqi:
            if aqi > 200:
                aqi_warning = "Very Unhealthy (avoid outdoor activities)"
            elif aqi > 150:
                aqi_warning = "Unhealthy (limit outdoor activities)"
            elif aqi > 100:
                aqi_warning = "Moderate (sensitive groups should limit activity)"
            else:
                aqi_warning = "Good air quality"
            context_parts.append(f"AQI in {city.title()}: {aqi_warning}")
        water_quality = region_data.get("water_quality")
        if water_quality == "low":
            context_parts.append(f"⚠️ Water quality in {city.title()} is low - water-borne diseases possible. Drink boiled/filtered water.")
        elif water_quality == "moderate":
            context_parts.append(f"Water quality in {city.title()} is moderate - take precautions.")
        return "\n".join(context_parts)
    @staticmethod
    def get_symptom_severity_for_location(symptom: str, location_dict: Dict) -> str:
        if not location_dict:
            return "unknown"
        city = LocationHealthContext.get_city_from_location(location_dict)
        season = LocationHealthContext.get_current_season()
        region_data = LocationHealthContext.DISEASE_BY_REGION.get(city)
        if not region_data:
            return "unknown"
        diseases = region_data.get(season, [])
        symptom_lower = symptom.lower()
        for disease in diseases:
            if disease in symptom_lower or symptom_lower in disease:
                return "high"
        return "moderate"
location_health_context = LocationHealthContext()
