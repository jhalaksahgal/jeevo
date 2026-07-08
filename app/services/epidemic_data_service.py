import httpx
import logging
import os
from typing import Dict, List, Optional
from datetime import datetime, timedelta
logger = logging.getLogger(__name__)
class EpidemicDataService:
    def __init__(self):
        self.google_api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    async def get_disease_prevalence(self, city: str, state: str) -> Dict:
        """
        Fetch real-time disease prevalence data from available sources.
        Falls back to historical patterns if APIs unavailable.
        """
        prevalence_data = {
            "city": city,
            "state": state,
            "active_diseases": {},
            "severity_level": "low",
            "data_source": "unknown",
            "timestamp": datetime.utcnow().isoformat(),
            "confidence": 0.0
        }
        try:
            covid_data = await self._get_covid_trends(city)
            if covid_data:
                prevalence_data["active_diseases"]["covid_19"] = covid_data
                prevalence_data["data_source"] = "covid_api"
                prevalence_data["confidence"] = 0.7
        except Exception as e:
            logger.warning(f"COVID data fetch failed: {e}")
        try:
            disease_data = await self._get_disease_data(city)
            if disease_data:
                prevalence_data["active_diseases"].update(disease_data)
                prevalence_data["severity_level"] = self._calculate_severity(disease_data)
        except Exception as e:
            logger.warning(f"Disease data fetch failed: {e}")
        if not prevalence_data["active_diseases"]:
            prevalence_data["active_diseases"] = self._get_seasonal_diseases(city)
            prevalence_data["data_source"] = "seasonal_historical"
            prevalence_data["confidence"] = 0.5
        return prevalence_data
    async def _get_covid_trends(self, location: str) -> Optional[Dict]:
        """Fetch COVID-19 trends from disease.sh API"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://disease.sh/v3/covid-19/countries/{location}",
                    timeout=5
                )
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "cases": data.get("cases", 0),
                        "deaths": data.get("deaths", 0),
                        "recovered": data.get("recovered", 0),
                        "cases_per_million": data.get("casesPerMillion", 0),
                        "trend": "increasing" if data.get("cases", 0) > 1000 else "stable"
                    }
        except Exception as e:
            logger.debug(f"COVID API error for {location}: {e}")
            return None
    async def _get_disease_data(self, city: str) -> Optional[Dict]:
        """
        Fetch disease outbreak data from public health APIs.
        Currently uses mock data; can be integrated with ICMR/WHO APIs.
        """
        disease_map = {
            "delhi": {
                "dengue": {"cases": 150, "severity": "moderate", "change": "+5%"},
                "typhoid": {"cases": 45, "severity": "low", "change": "+2%"},
                "respiratory": {"cases": 200, "severity": "moderate", "change": "stable"}
            },
            "mumbai": {
                "dengue": {"cases": 120, "severity": "moderate", "change": "+3%"},
                "malaria": {"cases": 80, "severity": "moderate", "change": "-2%"},
                "asthma": {"cases": 300, "severity": "high", "change": "stable"}
            },
            "bangalore": {
                "dengue": {"cases": 60, "severity": "low", "change": "+1%"},
                "respiratory": {"cases": 100, "severity": "low", "change": "stable"}
            },
            "kolkata": {
                "dengue": {"cases": 200, "severity": "high", "change": "+8%"},
                "cholera": {"cases": 20, "severity": "moderate", "change": "+1%"},
                "respiratory": {"cases": 180, "severity": "moderate", "change": "stable"}
            },
            "hyderabad": {
                "dengue": {"cases": 100, "severity": "moderate", "change": "+2%"},
                "malaria": {"cases": 60, "severity": "low", "change": "-1%"}
            }
        }
        city_lower = city.lower()
        return disease_map.get(city_lower, None)
    def _get_seasonal_diseases(self, city: str) -> Dict:
        """Get diseases likely prevalent based on season"""
        from app.services.location_health_context import LocationHealthContext
        city_lower = city.lower()
        region_data = LocationHealthContext.DISEASE_BY_REGION.get(city_lower, {})
        season = LocationHealthContext.get_current_season()
        seasonal_diseases = region_data.get(season, [])
        return {disease: {"severity": "low", "likelihood": 0.6} for disease in seasonal_diseases}
    def _calculate_severity(self, disease_data: Dict) -> str:
        """Calculate overall severity from disease data"""
        if not disease_data:
            return "low"
        high_severity_count = sum(
            1 for disease in disease_data.values()
            if isinstance(disease, dict) and disease.get("severity") == "high"
        )
        if high_severity_count >= 2:
            return "high"
        elif high_severity_count >= 1:
            return "moderate"
        else:
            return "low"
    async def get_weekly_disease_trend(self, city: str) -> Dict:
        """Get 7-day disease trend"""
        return {
            "city": city,
            "week_trend": [
                {"date": (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d"), "risk": self._get_trend_risk()}
                for i in range(7)
            ],
            "forecast": self._get_trend_forecast()
        }
    def _get_trend_risk(self) -> str:
        """Get random trend risk for demo"""
        import random
        return random.choice(["green", "yellow", "red"])
    def _get_trend_forecast(self) -> str:
        """Get forecast for next 3 days"""
        return "Risk expected to remain moderate. Monitor weather patterns for monsoon impact."
epidemic_data_service = EpidemicDataService()
