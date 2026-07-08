import logging
from typing import Dict, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.base import get_async_db
from app.database.repositories import RiskLevelRepository, UserRepository
from app.services.epidemic_data_service import epidemic_data_service
from app.services.environmental_service import environmental_service
from app.services.risk_aggregation_service import RiskAggregationService, RiskLevel
from app.services.risk_alert_service import RiskAlertService
from app.services.location_health_context import LocationHealthContext
logger = logging.getLogger(__name__)
class HeatmapUpdateService:
    """
    Periodically updates LocalRiskLevel table with aggregated health data.
    Runs as background task every 2-4 hours.
    """
    MAJOR_CITIES = {
        "Delhi": {"lat": 28.7041, "lon": 77.1025, "state": "Delhi"},
        "Mumbai": {"lat": 19.0760, "lon": 72.8777, "state": "Maharashtra"},
        "Bangalore": {"lat": 12.9716, "lon": 77.5946, "state": "Karnataka"},
        "Kolkata": {"lat": 22.5726, "lon": 88.3639, "state": "West Bengal"},
        "Hyderabad": {"lat": 17.3850, "lon": 78.4867, "state": "Telangana"},
        "Chennai": {"lat": 13.0827, "lon": 80.2707, "state": "Tamil Nadu"},
        "Pune": {"lat": 18.5204, "lon": 73.8567, "state": "Maharashtra"},
        "Ahmedabad": {"lat": 23.0225, "lon": 72.5714, "state": "Gujarat"},
        "Lucknow": {"lat": 26.8467, "lon": 80.9462, "state": "Uttar Pradesh"},
        "Jaipur": {"lat": 26.9124, "lon": 75.7873, "state": "Rajasthan"},
    }
    @staticmethod
    async def update_all_regions() -> Dict:
        """
        Main task: Update risk levels for all major cities.
        Called periodically by scheduler.
        """
        logger.info("🌍 Starting heatmap update for all regions...")
        updated_count = 0
        failed_count = 0
        results = {}
        async for db in get_async_db():
            for city, location_info in HeatmapUpdateService.MAJOR_CITIES.items():
                try:
                    result = await HeatmapUpdateService.update_city_risk(
                        db, city, location_info
                    )
                    results[city] = result
                    updated_count += 1
                    logger.info(f"✅ Updated {city}: Risk={result['risk_level']}")
                except Exception as e:
                    failed_count += 1
                    logger.error(f"❌ Failed to update {city}: {e}")
                    results[city] = {"error": str(e), "risk_level": "unknown"}
        logger.info(
            f"🏁 Heatmap update complete: {updated_count} updated, {failed_count} failed"
        )
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "updated": updated_count,
            "failed": failed_count,
            "results": results
        }
    @staticmethod
    async def update_city_risk(
        db: AsyncSession, city: str, location_info: Dict
    ) -> Dict:
        """
        Update risk level for a single city.
        Aggregates AQI, weather, disease, and historical data.
        """
        lat = location_info["lat"]
        lon = location_info["lon"]
        state = location_info["state"]
        pincode_prefix = city.lower()
        aqi_data = await environmental_service.get_aqi_health_risks(
            lat, lon, city
        )
        weather_data = await environmental_service.get_weather_health_risks(
            lat, lon
        )
        disease_data = await epidemic_data_service.get_disease_prevalence(
            city, state
        )
        historical_data = await HeatmapUpdateService._get_historical_trend(
            db, city
        )
        aggregated_risk = RiskAggregationService.calculate_overall_risk(
            aqi_data=aqi_data,
            weather_data=weather_data,
            disease_data=disease_data,
            historical_data=historical_data
        )
        risk_factors = {
            "aqi": aqi_data.get("aqi"),
            "weather": aqi_data.get("weather"),
            "temp": weather_data.get("temp"),
            "humidity": weather_data.get("humidity"),
            "component_scores": aggregated_risk.get("components", {})
        }
        active_diseases = {}
        if disease_data.get("active_diseases"):
            active_diseases = {
                name: {
                    "severity": data.get("severity", "unknown"),
                    "cases": data.get("cases", 0),
                    "trend": data.get("change", "stable")
                }
                for name, data in disease_data["active_diseases"].items()
            }
        weather_alerts = weather_data.get("alerts", [])
        try:
            await RiskAlertService.check_and_alert_risk_changes(db, city, aggregated_risk["risk_level"])
        except Exception as alert_err:
            logger.warning(f"Risk alert check failed for {city}: {alert_err}")
        risk_repo = RiskLevelRepository(db)
        updated_level = await risk_repo.update_risk_level(
            pincode=pincode_prefix,
            city=city,
            state=state,
            risk_level=aggregated_risk["risk_level"],
            risk_factors=risk_factors,
            active_diseases=active_diseases,
            pollution_level=f"AQI: {aqi_data.get('aqi', 'N/A')}",
            weather_alerts=weather_alerts,
            last_updated=datetime.utcnow(),
            data_source="heatmap_aggregation"
        )
        return {
            "city": city,
            "risk_level": aggregated_risk["risk_level"],
            "score": aggregated_risk["score"],
            "active_diseases": list(active_diseases.keys()),
            "alerts_count": len(aggregated_risk.get("alerts", [])),
            "updated_at": updated_level.last_updated.isoformat()
        }
    @staticmethod
    async def _get_historical_trend(db: AsyncSession, city: str) -> Dict:
        """Get historical trend for city"""
        try:
            risk_repo = RiskLevelRepository(db)
            current_risk = await risk_repo.get_risk_level(city.lower())
            if not current_risk:
                return {
                    "current_level": 5.0,
                    "trending": "stable",
                    "days_in_period": 0
                }
            return {
                "current_level": (
                    7.5 if current_risk.risk_level == "red"
                    else 5.5 if current_risk.risk_level == "yellow"
                    else 3.0
                ),
                "trending": "stable",
                "previous_update": current_risk.last_updated.isoformat()
            }
        except Exception as e:
            logger.warning(f"Could not fetch historical trend for {city}: {e}")
            return {"current_level": 5.0, "trending": "unknown"}
    @staticmethod
    async def get_city_heatmap(db: AsyncSession, city: str) -> Dict:
        """Get current heatmap data for a city"""
        try:
            risk_repo = RiskLevelRepository(db)
            risk_level = await risk_repo.get_risk_level(city.lower())
            if not risk_level:
                return {
                    "city": city,
                    "risk_level": "unknown",
                    "message": "No data available yet"
                }
            return {
                "city": risk_level.city or city,
                "state": risk_level.state,
                "risk_level": risk_level.risk_level,
                "risk_factors": risk_level.risk_factors,
                "active_diseases": risk_level.active_diseases,
                "pollution_level": risk_level.pollution_level,
                "weather_alerts": risk_level.weather_alerts,
                "last_updated": risk_level.last_updated.isoformat() if risk_level.last_updated else None
            }
        except Exception as e:
            logger.error(f"Error fetching heatmap for {city}: {e}")
            return {"city": city, "error": str(e)}
    @staticmethod
    async def get_regional_heatmap(db: AsyncSession, state: str) -> List[Dict]:
        """Get heatmap data for all cities in a state"""
        state_cities = [
            (city, location_info)
            for city, location_info in HeatmapUpdateService.MAJOR_CITIES.items()
            if location_info["state"] == state
        ]
        heatmap_data = []
        for city, _ in state_cities:
            city_data = await HeatmapUpdateService.get_city_heatmap(db, city)
            heatmap_data.append(city_data)
        return heatmap_data
