"""Configuration for Hail Province Air Quality Monitor."""

import os

# Geographic boundaries - expanded to include all facilities
CITIES = {
    "Hail": {
        "center": [27.5114, 41.7208],
        "bbox": [40.0, 26.5, 44.0, 28.5],
        "radius_km": 100,
        "region": "Hail Province"
    }
}

HAIL_PROVINCE_BBOX = [40.0, 26.5, 44.0, 28.5]

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

# Industrial facility locations - GIS verified coordinates
FACTORIES = {
    "Hail": [
        # VERIFIED HIGH PRECISION (+/-10m)
        {"name": "Hail Regional Airport (OEHL)", "location": [27.4379, 41.6863], "type": "Airport", "emissions": ["NO2", "CO", "SO2"], "capacity": "500K passengers/year", "source": "ICAO/Flightradar24", "verified": True},
        {"name": "SEC Hail 1-3 Power Plant", "location": [27.4689, 41.7416], "type": "Power Generation", "emissions": ["NO2", "SO2", "CO"], "capacity": "1,061 MW, 15 units", "source": "Global Energy Observatory", "verified": True},
        {"name": "SEC Hail-2 Power Plant", "location": [27.4705, 41.7411], "type": "Power Generation", "emissions": ["NO2", "SO2", "CO"], "capacity": "925+ MW combined cycle", "source": "Global Energy Monitor", "verified": True},
        {"name": "Hail Cement Plant", "location": [28.2704, 43.1963], "type": "Cement Manufacturing", "emissions": ["NO2", "SO2", "CO"], "capacity": "1.5M tons/year", "source": "Wikimapia/CemNet", "verified": True},
        {"name": "Hail Cement Power Plant", "location": [28.2947, 43.3717], "type": "Captive Power", "emissions": ["NO2", "SO2", "CO"], "capacity": "51 MW", "source": "Global Energy Monitor", "verified": True},
        {"name": "Az Zabirah Bauxite Mine", "location": [27.9128, 43.7143], "type": "Mining - Bauxite", "emissions": ["NO2", "SO2"], "capacity": "240M tonnes reserves", "source": "Mining Data Online", "verified": True},
        {"name": "Arabian Mills (MC2) Hail", "location": [27.6462, 41.7192], "type": "Flour Milling", "emissions": ["NO2"], "capacity": "1.3M tons/year", "source": "ReviewSaudi/Mrsool", "verified": True},

        # VERIFIED MEDIUM PRECISION (+/-50-100m)
        {"name": "MODON Hail Industrial City", "location": [27.4700, 41.6400], "type": "Mixed Industrial Zone", "emissions": ["NO2", "SO2", "CO", "HCHO", "CH4"], "capacity": "115+ factories, 3.88M m²", "source": "MODON Official", "verified": True},
        {"name": "Almarai Poultry Processing Plant", "location": [27.5600, 41.7300], "type": "Poultry Processing", "emissions": ["NO2", "CH4"], "capacity": "200M birds/year", "source": "Almarai/AMANA", "verified": True},
        {"name": "Almarai Bakery Plant 7", "location": [27.5594, 41.7271], "type": "Food Processing - Bakery", "emissions": ["NO2", "CO", "HCHO"], "capacity": "24-hour operation", "source": "Almarai/VyMaps", "verified": True},
        {"name": "Almarai Al-Shamli Poultry Farms", "location": [26.8578, 40.3293], "type": "Poultry Farming", "emissions": ["CH4", "NO2"], "capacity": "150M birds/year expansion", "source": "Argaam/Almarai", "verified": True},
        {"name": "AJA Pharmaceutical Industries", "location": [27.4700, 41.6400], "type": "Pharmaceutical", "emissions": ["NO2", "HCHO"], "capacity": "2B units/year, 120K m²", "source": "AJA Pharma/CPHI", "verified": True},
        {"name": "Sahala Pharmaceutical Company", "location": [27.4700, 41.6400], "type": "Pharmaceutical", "emissions": ["NO2", "HCHO"], "capacity": "120K m² GMP facility", "source": "Sahala Pharma", "verified": True},
        {"name": "Al Ghazalah Magnesite Mine", "location": [26.7500, 41.2500], "type": "Mining - Magnesite", "emissions": ["NO2", "SO2"], "capacity": "340K tonnes/year", "source": "USGS/Mindat/Ma'aden", "verified": True},

        # ESTIMATED COORDINATES (based on area descriptions)
        {"name": "HADCO Main Complex", "location": [27.4200, 42.0500], "type": "Agricultural Processing", "emissions": ["NO2", "CH4"], "capacity": "Wheat, olives, dates, fodder", "source": "Bloomberg/SaudiYP", "verified": False},
        {"name": "Hail Water Desalination Plant", "location": [27.5500, 41.7200], "type": "Desalination", "emissions": ["NO2", "CO"], "capacity": "100K m³/day", "source": "EMCO Group", "verified": False},
        {"name": "SAGO Grain Silos Hail", "location": [27.5300, 41.7000], "type": "Grain Storage", "emissions": ["CH4"], "capacity": "600 ton/day mill", "source": "Haif Company/MEWA", "verified": False},
        {"name": "Hail Wastewater Treatment Plant", "location": [27.5400, 41.7800], "type": "Wastewater Treatment", "emissions": ["CH4", "NO2"], "capacity": "Municipal treatment", "source": "NWC/SWA", "verified": False},
        {"name": "Hail Municipal Landfill", "location": [27.6200, 41.8000], "type": "Waste Management", "emissions": ["CH4", "NO2", "CO"], "capacity": "Solid waste disposal", "source": "NCWM", "verified": False},

        # MODON INDUSTRIAL CITY FACILITIES (within industrial zone)
        {"name": "Hail Plastics Manufacturing", "location": [27.4720, 41.6420], "type": "Plastics", "emissions": ["NO2", "HCHO"], "capacity": "Plastic products", "source": "MODON", "verified": False},
        {"name": "Hail Concrete Block Factory", "location": [27.4680, 41.6380], "type": "Construction Materials", "emissions": ["NO2", "SO2"], "capacity": "Concrete blocks", "source": "MODON", "verified": False},
        {"name": "Hail Steel Fabrication", "location": [27.4710, 41.6410], "type": "Metal Fabrication", "emissions": ["NO2", "SO2", "CO"], "capacity": "Steel fabrication", "source": "MODON", "verified": False},
        {"name": "Hail Furniture Manufacturing", "location": [27.4690, 41.6390], "type": "Furniture", "emissions": ["NO2", "HCHO"], "capacity": "Wood/furniture", "source": "MODON", "verified": False},
        {"name": "Hail Textiles Factory", "location": [27.4700, 41.6400], "type": "Textiles", "emissions": ["NO2", "HCHO"], "capacity": "Textile manufacturing", "source": "MODON", "verified": False},

        # QUARRIES AND MINING
        {"name": "North Hail Quarries", "location": [27.6500, 41.7500], "type": "Quarrying", "emissions": ["NO2"], "capacity": "Construction materials", "source": "USGS/Saudipedia", "verified": False},
        {"name": "South Hail Quarries", "location": [27.3800, 41.6800], "type": "Quarrying", "emissions": ["NO2"], "capacity": "Construction materials", "source": "USGS/Saudipedia", "verified": False},

        # TRANSPORTATION AND LOGISTICS
        {"name": "Hail Logistics Hub", "location": [27.5200, 41.7500], "type": "Transportation", "emissions": ["NO2", "CO"], "capacity": "Freight center", "source": "Various", "verified": False},
        {"name": "Hail Central Bus Station", "location": [27.5100, 41.7200], "type": "Transportation", "emissions": ["NO2", "CO"], "capacity": "Public transit", "source": "SAPTCO", "verified": False},

        # FUEL AND GAS
        {"name": "Aramco Fuel Distribution Terminal", "location": [27.5300, 41.7600], "type": "Fuel Distribution", "emissions": ["NO2", "CH4", "HCHO"], "capacity": "Regional fuel", "source": "Aramco", "verified": False},
        {"name": "Gas Distribution Station - North", "location": [27.5800, 41.7400], "type": "Gas Distribution", "emissions": ["CH4", "NO2"], "capacity": "LPG/natural gas", "source": "Gas companies", "verified": False},

        # AGRICULTURE
        {"name": "Hail Date Processing", "location": [27.5300, 41.6700], "type": "Food Processing", "emissions": ["NO2", "CH4"], "capacity": "Date packaging", "source": "Various", "verified": False},
        {"name": "Hail Greenhouse Complex", "location": [27.4800, 41.8300], "type": "Agriculture", "emissions": ["CH4", "NO2"], "capacity": "Vegetable production", "source": "Various", "verified": False},
        {"name": "Hail Agricultural Machinery Depot", "location": [27.5000, 41.6500], "type": "Agricultural Support", "emissions": ["NO2", "CO"], "capacity": "Farm equipment", "source": "Agricultural", "verified": False},
        {"name": "Hail Fertilizer Distribution", "location": [27.5200, 41.6600], "type": "Fertilizer", "emissions": ["NO2", "CH4"], "capacity": "Fertilizer storage", "source": "SABIC/Various", "verified": False},

        # OTHER
        {"name": "Hail Recycling Center", "location": [27.5500, 41.7300], "type": "Recycling", "emissions": ["NO2", "CH4"], "capacity": "Recycling", "source": "Environmental", "verified": False}
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
