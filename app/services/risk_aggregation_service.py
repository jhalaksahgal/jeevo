import logging
from typing import Dict, List, Optional
from datetime import datetime
from enum import Enum
from app.services.translation_service import translation_service
logger = logging.getLogger(__name__)
class RiskLevel(str, Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"
class RiskAggregationService:
    """Aggregates data from multiple sources to calculate overall risk level"""
    RISK_WEIGHTS = {
        "aqi": 0.35,
        "weather": 0.25,
        "disease": 0.30,
        "historical": 0.10
    }
    @staticmethod
    def calculate_overall_risk(
        aqi_data: Optional[Dict] = None,
        weather_data: Optional[Dict] = None,
        disease_data: Optional[Dict] = None,
        historical_data: Optional[Dict] = None
    ) -> Dict:
        """
        Calculate overall risk by weighing multiple data sources.
        Returns: {risk_level, score, components, alerts, recommendations}
        """
        scores = {}
        if aqi_data:
            scores["aqi"] = RiskAggregationService._score_aqi(aqi_data)
        if weather_data:
            scores["weather"] = RiskAggregationService._score_weather(weather_data)
        if disease_data:
            scores["disease"] = RiskAggregationService._score_disease(disease_data)
        if historical_data:
            scores["historical"] = RiskAggregationService._score_historical(historical_data)
        weighted_score = sum(
            scores.get(key, 0) * weight
            for key, weight in RiskAggregationService.RISK_WEIGHTS.items()
        )
        risk_level = RiskAggregationService._score_to_risk_level(weighted_score)
        alerts = RiskAggregationService._generate_alerts(
            aqi_data, weather_data, disease_data, risk_level
        )
        recommendations = RiskAggregationService._generate_recommendations(
            risk_level
        )
        return {
            "risk_level": risk_level,
            "score": round(weighted_score, 2),
            "components": scores,
            "alerts": alerts,
            "recommendations": recommendations,
            "timestamp": datetime.utcnow().isoformat(),
            "last_updated": datetime.utcnow().isoformat()
        }
    @staticmethod
    def _score_aqi(aqi_data: Dict) -> float:
        """Score AQI data (0-10)"""
        if "aqi" not in aqi_data:
            return 5.0
        aqi_value = aqi_data["aqi"]
        if aqi_value > 300:
            return 10.0
        elif aqi_value > 200:
            return 8.5
        elif aqi_value > 150:
            return 7.0
        elif aqi_value > 100:
            return 5.5
        else:
            return 2.0
    @staticmethod
    def _score_weather(weather_data: Dict) -> float:
        """Score weather data (0-10)"""
        score = 3.0
        if weather_data.get("risk_level") == "red":
            score += 7.0
        elif weather_data.get("risk_level") == "yellow":
            score += 4.0
        temp = weather_data.get("temp", 20)
        if temp > 40 or temp < 5:
            score += 1.5
        humidity = weather_data.get("humidity", 50)
        if humidity > 85:
            score += 0.5
        return min(score, 10.0)
    @staticmethod
    def _score_disease(disease_data: Dict) -> float:
        """Score disease prevalence data (0-10)"""
        if not disease_data or not disease_data.get("active_diseases"):
            return 3.0
        severity = disease_data.get("severity_level", "low")
        if severity == "high":
            return 8.0
        elif severity == "moderate":
            return 5.5
        else:
            return 2.5
    @staticmethod
    def _score_historical(historical_data: Dict) -> float:
        """Score historical trend data (0-10)"""
        if not historical_data:
            return 5.0
        trending_up = historical_data.get("trending", "stable") == "increasing"
        current_level = historical_data.get("current_level", 5.0)
        if trending_up:
            current_level += 1.5
        return min(current_level, 10.0)
    @staticmethod
    def _score_to_risk_level(score: float) -> RiskLevel:
        """Convert numeric score to risk level"""
        if score >= 7.0:
            return RiskLevel.RED
        elif score >= 4.5:
            return RiskLevel.YELLOW
        else:
            return RiskLevel.GREEN
    @staticmethod
    def _generate_alerts(
        aqi_data: Optional[Dict],
        weather_data: Optional[Dict],
        disease_data: Optional[Dict],
        risk_level: RiskLevel
    ) -> List[str]:
        """Generate alerts based on data sources"""
        alerts = []
        t = translation_service.get_domain("en", "risk_aggregation")
        alerts_text = t.get("alerts_text", {})
        if aqi_data and aqi_data.get("risk_level") == "red":
            alerts.append(alerts_text.get("severe_air_pollution", "🚨 SEVERE Air Pollution Alert"))
        if weather_data and weather_data.get("risk_level") == "red":
            alerts.extend(weather_data.get("alerts", []))
        if disease_data and disease_data.get("severity_level") == "high":
            diseases = list(disease_data.get("active_diseases", {}).keys())
            if diseases:
                alert_tmpl = alerts_text.get("high_disease_prevalence", "⚠️ High disease prevalence detected: {diseases}")
                alerts.append(alert_tmpl.replace("{diseases}", ", ".join(diseases)))
        if risk_level == RiskLevel.RED:
            alerts.append(alerts_text.get("overall_red", "🔴 OVERALL RISK LEVEL: RED - Essential outings only"))
        elif risk_level == RiskLevel.YELLOW:
            alerts.append(alerts_text.get("overall_yellow", "🟡 OVERALL RISK LEVEL: YELLOW - Caution advised"))
        return alerts
    @staticmethod
    def _generate_recommendations(risk_level: RiskLevel, lang: str = "en") -> List[str]:
        """Generate health recommendations based on risk level"""
        t = translation_service.get_domain(lang, "risk_aggregation")
        if risk_level == RiskLevel.RED:
            return t.get("recs_red", [])
        elif risk_level == RiskLevel.YELLOW:
            return t.get("recs_yellow", [])
        else:
            return t.get("recs_green", [])
    @staticmethod
    def format_heatmap_display(aggregated_risk: Dict, city: str, lang: str = "en") -> str:
        """Format aggregated risk data for WhatsApp display in user's language"""
        score = aggregated_risk.get("score", 0)
        risk_level = aggregated_risk.get("risk_level", "unknown")
        components = aggregated_risk.get("components", {})
        alerts = aggregated_risk.get("alerts", [])
        try:
            enum_risk = RiskLevel(risk_level)
        except ValueError:
            enum_risk = RiskLevel.GREEN
        recommendations = RiskAggregationService._generate_recommendations(enum_risk, lang)
        t = translation_service.get_domain(lang, "risk_aggregation")
        msg = f"{t['title']} - {city}\n\n"
        risk_emoji = {"red": "🔴", "yellow": "🟡", "green": "🟢"}.get(risk_level, "⚪")
        msg += f"{risk_emoji} {t['overall_risk']}: {risk_level.upper()}\n"
        msg += f"   {t['risk_score']}: {score}/10\n\n"
        msg += f"{t['components']}\n"
        if components.get("aqi"):
            msg += f"  • {t['air_quality']}: {components['aqi']:.1f}/10\n"
        if components.get("weather"):
            msg += f"  • {t['weather']}: {components['weather']:.1f}/10\n"
        if components.get("disease"):
            msg += f"  • {t['disease_prev']}: {components['disease']:.1f}/10\n"
        if components.get("historical"):
            msg += f"  • {t['historical']}: {components['historical']:.1f}/10\n"
        msg += f"\n{t['alerts']}\n"
        for alert in alerts[:3]:
            msg += f"{alert}\n"
        msg += f"\n{t['recommendations']}\n"
        for rec in recommendations[:4]:
            msg += f"{rec}\n"
        return msg
