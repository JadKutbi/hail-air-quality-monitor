"""Configuration for Hail Province Air Quality Monitor."""

import os

# Geographic boundaries
CITIES = {
    "Hail": {
        "center": [27.5114, 41.7208],
        "bbox": [40.8, 26.8, 42.5, 28.2],
        "radius_km": 50,
        "region": "Hail Province"
    }
}

HAIL_PROVINCE_BBOX = [40.8, 26.8, 42.5, 28.2]

# Sentinel-5P product definitions
GAS_PRODUCTS = {
    "NO2": {
        "name": "Nitrogen Dioxide",
        "dataset": "COPERNICUS/S5P/NRTI/L3_NO2",
        "band": "NO2_column_number_density",
        "unit": "mol/m²",
        "conversion_factor": 1e6,
        "display_unit": "µmol/m²",
        "typical_range": [0, 0.0003],
        "source_unit": "MOL_M2"
    },
    "SO2": {
        "name": "Sulfur Dioxide",
        "dataset": "COPERNICUS/S5P/NRTI/L3_SO2",
        "band": "SO2_column_number_density",
        "unit": "mol/m²",
        "conversion_factor": 1e6,
        "display_unit": "µmol/m²",
        "typical_range": [0, 0.01],
        "source_unit": "MOL_M2"
    },
    "CO": {
        "name": "Carbon Monoxide",
        "dataset": "COPERNICUS/S5P/NRTI/L3_CO",
        "band": "CO_column_number_density",
        "unit": "mol/m²",
        "conversion_factor": 1e3,
        "display_unit": "mmol/m²",
        "typical_range": [0, 0.1],
        "source_unit": "MOL_M2"
    },
    "HCHO": {
        "name": "Formaldehyde",
        "dataset": "COPERNICUS/S5P/NRTI/L3_HCHO",
        "band": "tropospheric_HCHO_column_number_density",
        "unit": "mol/m²",
        "conversion_factor": 1e6,
        "display_unit": "µmol/m²",
        "typical_range": [0, 0.001],
        "source_unit": "MOL_M2"
    },
    "CH4": {
        "name": "Methane",
        "dataset": "COPERNICUS/S5P/OFFL/L3_CH4",
        "band": "CH4_column_volume_mixing_ratio_dry_air",
        "unit": "ppb",
        "conversion_factor": 1,
        "display_unit": "ppb",
        "typical_range": [1600, 2000],
        "source_unit": "PPB"
    }
}

# Pollution thresholds
GAS_THRESHOLDS = {
    "NO2": {
        "column_threshold": 0.000075,
        "critical_threshold": 0.00015,
        "extreme_threshold": 0.000225,
        "unit": "mol/m²",
        "display_unit": "µmol/m²",
        "source": "Sentinel-5P TROPOMI"
    },
    "SO2": {
        "column_threshold": 0.0025,
        "critical_threshold": 0.005,
        "extreme_threshold": 0.0075,
        "unit": "mol/m²",
        "display_unit": "µmol/m²",
        "source": "Sentinel-5P TROPOMI"
    },
    "CO": {
        "column_threshold": 0.025,
        "critical_threshold": 0.05,
        "extreme_threshold": 0.075,
        "unit": "mol/m²",
        "display_unit": "mmol/m²",
        "source": "Sentinel-5P TROPOMI"
    },
    "HCHO": {
        "column_threshold": 0.00025,
        "critical_threshold": 0.0005,
        "extreme_threshold": 0.00075,
        "unit": "mol/m²",
        "display_unit": "µmol/m²",
        "source": "Sentinel-5P TROPOMI"
    },
    "CH4": {
        "column_threshold": 1920,
        "critical_threshold": 1950,
        "extreme_threshold": 2000,
        "unit": "ppb",
        "display_unit": "ppb",
        "source": "Sentinel-5P TROPOMI"
    }
}

# Industrial facility locations
FACTORIES = {
    "Hail": [
        {"name": "MODON Hail Industrial City", "location": [27.48, 41.69], "type": "Mixed Industrial Zone", "emissions": ["NO2", "SO2", "CO", "HCHO", "CH4"], "capacity": "115+ factories", "source": "MODON", "verified": False},
        {"name": "Hail Cement Company", "location": [27.70, 42.00], "type": "Cement Manufacturing", "emissions": ["NO2", "SO2", "CO"], "capacity": "5M tons/year", "source": "Hail Cement Co.", "verified": False},
        {"name": "Hail Combined Cycle Power Plant", "location": [27.52, 41.73], "type": "Power Generation", "emissions": ["NO2", "SO2", "CO"], "capacity": "Combined cycle", "source": "SEC", "verified": False},
        {"name": "Hail Gas Turbine Power Station", "location": [27.50, 41.70], "type": "Power Generation", "emissions": ["NO2", "SO2", "CO"], "capacity": "Peak load", "source": "SEC", "verified": False},
        {"name": "Almarai Poultry Processing Plant", "location": [27.45, 41.85], "type": "Poultry Processing", "emissions": ["NO2", "CH4"], "capacity": "Large-scale", "source": "Almarai", "verified": False},
        {"name": "Almarai Poultry Farm Complex", "location": [27.42, 41.88], "type": "Poultry Farming", "emissions": ["CH4", "NO2"], "capacity": "Industrial-scale", "source": "Almarai", "verified": False},
        {"name": "Almarai Bakery Facility", "location": [27.47, 41.80], "type": "Food Processing", "emissions": ["NO2", "CO", "HCHO"], "capacity": "Industrial bakery", "source": "Almarai", "verified": False},
        {"name": "Almarai Dairy Processing Plant", "location": [27.44, 41.82], "type": "Dairy Processing", "emissions": ["NO2", "CH4", "CO"], "capacity": "Dairy/juice", "source": "Almarai", "verified": False},
        {"name": "HADCO Wheat Processing Plant", "location": [27.55, 41.65], "type": "Agricultural Processing", "emissions": ["NO2", "CH4"], "capacity": "Grain processing", "source": "HADCO", "verified": False},
        {"name": "HADCO Olive Processing Facility", "location": [27.58, 41.62], "type": "Agricultural Processing", "emissions": ["NO2", "CH4", "HCHO"], "capacity": "Olive oil", "source": "HADCO", "verified": False},
        {"name": "HADCO Dairy Farm Complex", "location": [27.52, 41.68], "type": "Dairy Farming", "emissions": ["CH4", "NO2"], "capacity": "Large-scale", "source": "HADCO", "verified": False},
        {"name": "HADCO Potato Processing Plant", "location": [27.56, 41.60], "type": "Agricultural Processing", "emissions": ["NO2", "CH4"], "capacity": "Potato storage", "source": "HADCO", "verified": False},
        {"name": "AJA Pharmaceutical Industries", "location": [27.49, 41.71], "type": "Pharmaceutical", "emissions": ["NO2", "HCHO"], "capacity": "Generic drugs", "source": "AJA Pharma", "verified": False},
        {"name": "Sahala Pharmaceutical Company", "location": [27.50, 41.72], "type": "Pharmaceutical", "emissions": ["NO2", "HCHO"], "capacity": "Pharma production", "source": "Sahala Pharma", "verified": False},
        {"name": "Al Ghazalah Magnesite Mine", "location": [27.30, 42.20], "type": "Mining - Magnesite", "emissions": ["NO2", "SO2"], "capacity": "Magnesite extraction", "source": "Mining Ops", "verified": False},
        {"name": "Az Zabirah Bauxite Mine", "location": [26.90, 41.50], "type": "Mining - Bauxite", "emissions": ["NO2", "SO2"], "capacity": "4M tons/year", "source": "Ma'aden", "verified": False},
        {"name": "Ma'aden Phosphate Exploration", "location": [27.20, 41.80], "type": "Mining - Phosphate", "emissions": ["NO2", "SO2"], "capacity": "Phosphate extraction", "source": "Ma'aden", "verified": False},
        {"name": "Hail Gold Mining Operations", "location": [27.35, 41.45], "type": "Mining - Gold", "emissions": ["NO2", "SO2"], "capacity": "Gold extraction", "source": "Various", "verified": False},
        {"name": "North Hail Quarries", "location": [27.65, 41.75], "type": "Quarrying", "emissions": ["NO2"], "capacity": "Construction materials", "source": "Various", "verified": False},
        {"name": "South Hail Quarries", "location": [27.38, 41.68], "type": "Quarrying", "emissions": ["NO2"], "capacity": "Construction materials", "source": "Various", "verified": False},
        {"name": "SAGO Grain Silos Hail", "location": [27.51, 41.74], "type": "Grain Storage", "emissions": ["CH4"], "capacity": "Strategic storage", "source": "SAGO", "verified": False},
        {"name": "Hail Date Processing Factory", "location": [27.53, 41.67], "type": "Food Processing", "emissions": ["NO2", "CH4"], "capacity": "Date packaging", "source": "Various", "verified": False},
        {"name": "Al Watania Poultry - Hail", "location": [27.46, 41.76], "type": "Poultry Processing", "emissions": ["NO2", "CH4"], "capacity": "Poultry processing", "source": "Al Watania", "verified": False},
        {"name": "Hail Flour Mills", "location": [27.48, 41.70], "type": "Food Processing", "emissions": ["NO2"], "capacity": "Flour milling", "source": "Local mills", "verified": False},
        {"name": "Hail Wastewater Treatment Plant", "location": [27.54, 41.78], "type": "Wastewater Treatment", "emissions": ["CH4", "NO2"], "capacity": "Municipal", "source": "NWC", "verified": False},
        {"name": "Hail Water Desalination Plant", "location": [27.60, 41.72], "type": "Desalination", "emissions": ["NO2", "CO"], "capacity": "Desalination", "source": "SWCC/NWC", "verified": False},
        {"name": "Hail Industrial Wastewater Treatment", "location": [27.47, 41.68], "type": "Industrial Wastewater", "emissions": ["CH4", "NO2"], "capacity": "Industrial zone", "source": "MODON", "verified": False},
        {"name": "Hail Plastics Manufacturing", "location": [27.49, 41.69], "type": "Plastics", "emissions": ["NO2", "HCHO"], "capacity": "Plastic products", "source": "MODON", "verified": False},
        {"name": "Hail Concrete Block Factory", "location": [27.51, 41.71], "type": "Construction Materials", "emissions": ["NO2", "SO2"], "capacity": "Concrete blocks", "source": "Local", "verified": False},
        {"name": "Hail Steel Fabrication", "location": [27.50, 41.70], "type": "Metal Fabrication", "emissions": ["NO2", "SO2", "CO"], "capacity": "Steel fabrication", "source": "MODON", "verified": False},
        {"name": "Hail Furniture Manufacturing", "location": [27.48, 41.72], "type": "Furniture", "emissions": ["NO2", "HCHO"], "capacity": "Wood/furniture", "source": "MODON", "verified": False},
        {"name": "Hail Textiles Factory", "location": [27.47, 41.70], "type": "Textiles", "emissions": ["NO2", "HCHO"], "capacity": "Textile manufacturing", "source": "MODON", "verified": False},
        {"name": "Hail Regional Airport", "location": [27.4372, 41.6861], "type": "Airport", "emissions": ["NO2", "CO", "SO2"], "capacity": "Regional airport", "source": "GACA", "verified": True},
        {"name": "Hail Logistics Hub", "location": [27.52, 41.75], "type": "Transportation", "emissions": ["NO2", "CO"], "capacity": "Freight center", "source": "Various", "verified": False},
        {"name": "Hail Central Bus Station", "location": [27.51, 41.72], "type": "Transportation", "emissions": ["NO2", "CO"], "capacity": "Public transit", "source": "SAPTCO", "verified": False},
        {"name": "Aramco Fuel Distribution Terminal", "location": [27.53, 41.76], "type": "Fuel Distribution", "emissions": ["NO2", "CH4", "HCHO"], "capacity": "Regional fuel", "source": "Aramco", "verified": False},
        {"name": "Gas Distribution Station - North", "location": [27.58, 41.74], "type": "Gas Distribution", "emissions": ["CH4", "NO2"], "capacity": "LPG/natural gas", "source": "Gas companies", "verified": False},
        {"name": "Hail Municipal Landfill", "location": [27.62, 41.80], "type": "Waste Management", "emissions": ["CH4", "NO2", "CO"], "capacity": "Solid waste", "source": "Municipality", "verified": False},
        {"name": "Hail Recycling Center", "location": [27.55, 41.73], "type": "Recycling", "emissions": ["NO2", "CH4"], "capacity": "Recycling", "source": "Environmental", "verified": False},
        {"name": "Hail Agricultural Machinery Depot", "location": [27.50, 41.65], "type": "Agricultural Support", "emissions": ["NO2", "CO"], "capacity": "Farm equipment", "source": "Agricultural", "verified": False},
        {"name": "Hail Fertilizer Distribution", "location": [27.52, 41.66], "type": "Fertilizer", "emissions": ["NO2", "CH4"], "capacity": "Fertilizer storage", "source": "SABIC/Various", "verified": False},
        {"name": "Hail Greenhouse Complex", "location": [27.48, 41.83], "type": "Agriculture", "emissions": ["CH4", "NO2"], "capacity": "Vegetable production", "source": "Various", "verified": False}
    ]
}

# Wind data providers
WIND_SOURCES = [
    {"id": "era5_land_hourly", "label": "ECMWF ERA5-Land Hourly", "dataset": "ECMWF/ERA5_LAND/HOURLY", "u_component": "u_component_of_wind_10m", "v_component": "v_component_of_wind_10m", "scale": 11132, "search_windows_hours": [1, 2, 3, 6, 12, 24, 48, 72], "forward_search_hours": 0, "max_time_offset_hours": 72, "base_reliability": 0.95, "sample_radius_km": 30},
    {"id": "noaa_gfs", "label": "NOAA GFS", "dataset": "NOAA/GFS0P25", "u_component": "u_component_of_wind_10m_above_ground", "v_component": "v_component_of_wind_10m_above_ground", "scale": 27830, "search_windows_hours": [1, 3, 6, 12, 24, 48], "forward_search_hours": 0, "max_time_offset_hours": 48, "base_reliability": 0.92, "sample_radius_km": 40},
    {"id": "era5_daily", "label": "ECMWF ERA5 Daily", "dataset": "ECMWF/ERA5/DAILY", "u_component": "u_component_of_wind_10m", "v_component": "v_component_of_wind_10m", "scale": 27830, "search_windows_hours": [24, 72], "forward_search_hours": 0, "max_time_offset_hours": 72, "base_reliability": 0.90, "sample_radius_km": 50}
]

WIND_DEFAULTS = {"speed_ms": 2.0, "direction_deg": 0.0, "confidence": 0.0, "cardinal": "N"}

# System settings
LIVE_VIOLATION_TTL_HOURS = 12
LIVE_VIOLATIONS_MAX_ENTRIES = 50
SCAN_INTERVAL_HOURS = 12
SCAN_INTERVAL_MINUTES = SCAN_INTERVAL_HOURS * 60
TIMEZONE = "Asia/Riyadh"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
LOG_DIR = os.path.join(BASE_DIR, "logs")
VIOLATION_DIR = os.path.join(BASE_DIR, "violations")
LIVE_VIOLATIONS_FILE = os.path.join(LOG_DIR, "live_violations.json")

for directory in [DATA_DIR, LOG_DIR, VIOLATION_DIR]:
    os.makedirs(directory, exist_ok=True)

def _env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")

def _env_list(name: str, default: list[str]) -> list[str]:
    value = os.getenv(name)
    if not value:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]

NOTIFICATION_CONFIG = {
    "email": {"enabled": _env_bool("EMAIL_NOTIFICATIONS_ENABLED", False), "smtp_server": os.getenv("EMAIL_SMTP_SERVER", "smtp.gmail.com"), "smtp_port": int(os.getenv("EMAIL_SMTP_PORT", "587")), "sender_email": os.getenv("EMAIL_SENDER_ADDRESS", ""), "sender_password": os.getenv("EMAIL_SENDER_PASSWORD", ""), "recipients": _env_list("EMAIL_RECIPIENTS", [])},
    "webhook": {"enabled": _env_bool("WEBHOOK_NOTIFICATIONS_ENABLED", False), "url": os.getenv("WEBHOOK_URL", "")},
    "telegram": {"enabled": _env_bool("TELEGRAM_NOTIFICATIONS_ENABLED", False), "bot_token": os.getenv("TELEGRAM_BOT_TOKEN", ""), "chat_id": os.getenv("TELEGRAM_CHAT_ID", "")}
}

GEE_PROJECT = 'rcjyenviroment'
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
