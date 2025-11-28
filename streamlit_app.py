"""Saudi Arabia Air Quality Monitoring System using Sentinel-5P satellite data."""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import pytz
import os
from typing import Dict, List, Optional
import json
import logging

logger = logging.getLogger(__name__)

# Import local modules
from satellite_fetcher import SatelliteDataFetcher
from analyzer import PollutionAnalyzer
from visualizer import MapVisualizer
from data_validator import DataValidator
from violation_recorder import ViolationRecorder
from translations import get_text, get_direction, get_font_family, TRANSLATIONS
from dashboard_components import (
    create_aqi_dashboard,
    create_health_risk_panel,
    create_data_quality_panel,
    create_insights_panel,
    create_historical_comparison,
    create_benchmark_summary,
    create_city_rankings_table,
    create_city_rankings_chart,
    create_regional_comparison,
    create_category_distribution,
    create_gas_specific_ranking,
    create_city_comparison
)
from benchmark_analyzer import CityBenchmarkAnalyzer
import config


def format_gas_value(value: float, gas: str) -> str:
    """Format gas value with unit for display."""
    if value is None:
        return "N/A"

    gas_config = config.GAS_PRODUCTS.get(gas, {})
    conversion = gas_config.get('conversion_factor', 1)
    display_unit = gas_config.get('display_unit', 'mol/m²')
    display_value = value * conversion

    if gas == 'CH4':
        return f"{display_value:.0f} {display_unit}"
    elif display_value >= 1000:
        return f"{display_value:.0f} {display_unit}"
    elif display_value >= 100:
        return f"{display_value:.1f} {display_unit}"
    elif display_value >= 1:
        return f"{display_value:.2f} {display_unit}"
    elif display_value >= 0.001:
        return f"{display_value:.3f} {display_unit}"
    elif display_value > 0:
        return f"{display_value:.2e} {display_unit}"
    else:
        return f"0 {display_unit}"


def format_gas_value_short(value: float, gas: str) -> str:
    """Format gas value without unit."""
    if value is None:
        return "N/A"

    gas_config = config.GAS_PRODUCTS.get(gas, {})
    conversion = gas_config.get('conversion_factor', 1)

    display_value = value * conversion

    if gas == 'CH4':
        return f"{display_value:.0f}"
    elif display_value >= 1000:
        return f"{display_value:.0f}"
    elif display_value >= 100:
        return f"{display_value:.1f}"
    elif display_value >= 1:
        return f"{display_value:.2f}"
    elif display_value >= 0.001:
        return f"{display_value:.3f}"
    elif display_value > 0:
        return f"{display_value:.2e}"
    else:
        return "0"


st.set_page_config(
    page_title="Saudi Air Quality Monitor",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'About': "Real-time air quality monitoring using Sentinel-5P satellite data. "
                 "Developed for the Royal Commission for Jubail and Yanbu."
    }
)

def inject_custom_css():
    """Inject CSS with RTL support for Arabic."""
    lang = st.session_state.get('language', 'en')
    direction = get_direction(lang)
    font_family = get_font_family(lang)

    rtl_css = """
        .rtl-content {
            direction: rtl;
            text-align: right;
        }
        .rtl-content .stSelectbox, .rtl-content .stTextInput {
            direction: rtl;
        }
    """ if lang == 'ar' else ""

    st.markdown(f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Arabic:wght@400;500;600;700&display=swap');

        .main {{
            padding-top: 2rem;
            direction: {direction};
            font-family: {font_family};
        }}
        .stAlert {{
            border-radius: 10px;
            border: 1px solid;
        }}
        .metric-card {{
            background-color: #f0f2f6;
            border-radius: 10px;
            padding: 1rem;
            margin: 0.5rem;
        }}
        .violation-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 1.5rem;
            border-radius: 10px;
            margin: 1rem 0;
        }}
        h1 {{
            color: #1e3a8a;
        }}
        .stMetric {{
            background-color: #ffffff;
            padding: 1rem;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        {rtl_css}
        </style>
        """, unsafe_allow_html=True)

if 'selected_city' not in st.session_state:
    st.session_state.selected_city = 'Yanbu'
if 'auto_refresh' not in st.session_state:
    st.session_state.auto_refresh = False
if 'refresh_interval' not in st.session_state:
    st.session_state.refresh_interval = 6
if 'last_update' not in st.session_state:
    st.session_state.last_update = None
if 'pollution_data' not in st.session_state:
    st.session_state.pollution_data = {}
if 'alert_thresholds' not in st.session_state:
    st.session_state.alert_thresholds = {}
if 'language' not in st.session_state:
    st.session_state.language = 'en'
if 'confirm_clear' not in st.session_state:
    st.session_state.confirm_clear = False
if 'current_tab' not in st.session_state:
    st.session_state.current_tab = 'overview'
if 'benchmark_data' not in st.session_state:
    st.session_state.benchmark_data = {}
if 'benchmark_last_update' not in st.session_state:
    st.session_state.benchmark_last_update = None


def t(key: str) -> str:
    """Get translated text for current language."""
    return get_text(key, st.session_state.language)

@st.cache_resource
def initialize_services():
    """Initialize monitoring services. Returns tuple, any may be None on failure."""
    services = {}

    vertex_project = st.secrets.get("VERTEX_PROJECT_ID", os.getenv("VERTEX_PROJECT_ID"))
    vertex_location = st.secrets.get("VERTEX_LOCATION", os.getenv("VERTEX_LOCATION", "us-central1"))
    gemini_key = st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY"))

    try:
        services['fetcher'] = SatelliteDataFetcher()
    except Exception as e:
        st.warning(f"{t('satellite_unavailable')}: {str(e)}")
        services['fetcher'] = None

    try:
        services['analyzer'] = PollutionAnalyzer(
            gemini_api_key=gemini_key,
            vertex_project=vertex_project,
            vertex_location=vertex_location
        )
    except Exception as e:
        st.warning(f"{t('ai_unavailable')}: {str(e)}")
        services['analyzer'] = None

    try:
        services['visualizer'] = MapVisualizer()
    except Exception as e:
        st.warning(f"{t('map_unavailable')}: {str(e)}")
        services['visualizer'] = None

    try:
        services['validator'] = DataValidator()
    except Exception as e:
        st.warning(f"{t('validation_unavailable')}: {str(e)}")
        services['validator'] = None

    try:
        services['recorder'] = ViolationRecorder()
    except Exception as e:
        st.warning(f"{t('recorder_unavailable')}: {str(e)}")
        services['recorder'] = None

    return (services.get('fetcher'), services.get('analyzer'),
            services.get('visualizer'), services.get('validator'),
            services.get('recorder'))

def create_header():
    """Display header with title and current time."""
    col1, col2 = st.columns([4, 1])

    with col1:
        st.title(f"🌍 {t('app_title')}")
        st.caption(t('app_subtitle'))

    with col2:
        ksa_tz = pytz.timezone(config.TIMEZONE)
        current_time = datetime.now(ksa_tz).strftime("%H:%M KSA")
        st.metric(t('time_label'), current_time)

def create_sidebar():
    """Configure sidebar with city selection, language, and refresh controls."""
    with st.sidebar:
        st.selectbox(
            "🌐 Language / اللغة",
            options=["en", "ar"],
            index=0 if st.session_state.language == "en" else 1,
            format_func=lambda x: "English" if x == "en" else "العربية",
            key="lang_selector",
            on_change=lambda: setattr(st.session_state, 'language', st.session_state.lang_selector)
        )

        st.divider()
        st.header(f"⚙️ {t('control_panel')}")

        city_keys = list(config.CITIES.keys())
        if st.session_state.selected_city not in city_keys:
            st.session_state.selected_city = city_keys[0] if city_keys else 'Yanbu'
        selected_city = st.selectbox(
            t('select_city'),
            options=city_keys,
            index=city_keys.index(st.session_state.selected_city),
            format_func=lambda x: t(x),
            help=t('choose_city_help')
        )
        st.session_state.selected_city = selected_city

        days_back = 30

        st.subheader(f"🔄 {t('refresh_settings')}")

        refresh_enabled = st.toggle(
            t('auto_refresh'),
            value=st.session_state.get('auto_refresh', False),
        )
        st.session_state.auto_refresh = refresh_enabled

        if refresh_enabled:
            refresh_hours = st.select_slider(
                t('refresh_interval'),
                options=[0.5, 1, 2, 3, 4, 6, 8, 12, 24],
                value=st.session_state.get('refresh_interval', 6),
                format_func=lambda x: f"{x} {t('hours')}" if x >= 1 else f"{int(x*60)} {t('minutes')}",
            )
            st.session_state.refresh_interval = refresh_hours

            if st.session_state.last_update:
                last_update_dt = datetime.strptime(st.session_state.last_update, "%Y-%m-%d %H:%M:%S KSA")
                ksa_tz = pytz.timezone(config.TIMEZONE)
                last_update_ksa = ksa_tz.localize(last_update_dt)
                next_refresh = last_update_ksa + timedelta(hours=refresh_hours)
                st.caption(f"{t('next_refresh')}: {next_refresh.strftime('%H:%M:%S KSA')}")

        if st.button(f"🔄 {t('refresh_now')}", width="stretch", type="primary"):
            st.session_state.pollution_data = {}
            fetch_pollution_data.clear()
            st.rerun()

        st.divider()
        if st.session_state.last_update:
            st.info(f"{t('last_update')}: {st.session_state.last_update}")

        st.divider()
        with st.expander(f"🔧 {t('connection_diagnostics')}"):
            if st.button(t('test_connection'), width="stretch"):
                with st.spinner(t('testing_connection')):
                    try:
                        import ee
                        # Test basic connection
                        test_number = ee.Number(1).getInfo()
                        st.success(f"✅ {t('connection_successful')}")

                        # Test project access
                        try:
                            test_collection = ee.ImageCollection("COPERNICUS/S5P/NRTI/L3_NO2").limit(1).getInfo()
                            st.success(f"✅ {t('can_access_data')}")
                        except Exception as e:
                            st.error(f"❌ {t('cannot_access_data')}: {str(e)}")

                        # Check credentials
                        if st.secrets.get("GEE_SERVICE_ACCOUNT"):
                            st.info(f"{t('using_service_account')}: {st.secrets['GEE_SERVICE_ACCOUNT'][:30]}...")
                        else:
                            st.warning(t('no_service_account'))

                    except Exception as e:
                        st.error(f"❌ {t('connection_failed')}: {str(e)}")

        st.divider()
        st.subheader(f"ℹ️ {t('about')}")
        if st.session_state.language == "ar":
            st.markdown("""
            يراقب هذا النظام جودة الهواء باستخدام:
            - بيانات القمر الصناعي **Sentinel-5P**
            - إرشادات **منظمة الصحة العالمية 2021**
            - بيانات الرياح **الفورية**
            - تحديد المصادر **بالذكاء الاصطناعي**
            """)
        else:
            st.markdown("""
            This system monitors air quality using:
            - **Sentinel-5P** satellite data
            - **Satellite-based** pollution thresholds
            - **Real-time** wind data
            - **AI-powered** source attribution
            """)

        st.subheader(f"🔬 {t('monitored_gases')}")
        for gas, info in config.GAS_PRODUCTS.items():
            st.caption(f"• **{gas}**: {t(gas)}")

        return selected_city, days_back

@st.cache_data(ttl=1800)
def fetch_pollution_data(city: str, days_back: int):
    """Fetch pollution data for all monitored gases."""
    fetcher, analyzer, _, _, _ = initialize_services()

    if not fetcher:
        st.error(t('cannot_connect_satellite'))
        st.info(t('check_earth_engine'))
        return {}

    all_data = {}
    errors = []

    progress = st.progress(0)
    status = st.empty()

    try:
        gases = list(config.GAS_PRODUCTS.keys())
        for i, gas in enumerate(gases):
            status.text(t('retrieving_data').format(gas=gas))
            progress.progress((i + 1) / len(gases))

            try:
                data = fetcher.fetch_gas_data(city, gas, days_back=days_back)
                if data and data.get('success'):
                    all_data[gas] = data
                else:
                    error_msg = data.get('error', 'No data available') if data else 'No data available'
                    errors.append(f"{gas}: {error_msg}")
            except Exception as e:
                errors.append(f"{gas}: {str(e)}")
    finally:
        progress.empty()
        status.empty()

    if errors and len(errors) == len(gases):
        st.error(t('failed_fetch_all'))
        with st.expander(t('error')):
            for error in errors:
                st.write(f"• {error}")
    elif errors:
        with st.expander(t('partial_data').format(count=len(errors))):
            for error in errors:
                st.write(f"• {error}")

    return all_data

def display_metrics(pollution_data: Dict):
    """Display current pollution metrics for all gases."""
    st.subheader(f"📊 {t('current_metrics')}")

    valid_data = {gas: data for gas, data in pollution_data.items() if data.get('success')}

    if not valid_data:
        st.warning(t('no_data_available'))
        return

    cols = st.columns(min(len(valid_data), 6))

    for i, (gas, data) in enumerate(valid_data.items()):
        with cols[i % len(cols)]:
            threshold_info = config.GAS_THRESHOLDS.get(gas, {})
            threshold = threshold_info.get('column_threshold', float('inf'))
            critical = threshold_info.get('critical_threshold', float('inf'))

            max_val = data['statistics']['max']
            if max_val >= critical:
                status = f"🔴 {t('critical')}"
                delta_color = "inverse"
            elif max_val >= threshold:
                status = f"🟡 {t('moderate')}"
                delta_color = "normal"
            else:
                status = f"🟢 {t('normal')}"
                delta_color = "normal"

            st.metric(
                label=f"{gas} ({config.GAS_PRODUCTS[gas]['name']})",
                value=format_gas_value_short(max_val, gas),
                delta=f"{status} | {t('threshold')}: {format_gas_value_short(threshold, gas)}",
                delta_color=delta_color
            )

            with st.expander(t('violation_details')):
                st.write(f"**{t('mean')}:** {format_gas_value(data['statistics']['mean'], gas)}")
                st.write(f"**{t('min')}:** {format_gas_value(data['statistics']['min'], gas)}")
                st.write(f"**{t('type')}:** {config.GAS_PRODUCTS[gas].get('display_unit', data['unit'])}")

                if data.get('data_age_label'):
                    age_emoji = "🕐" if data.get('days_old', 0) > 0 else "✨"
                    st.caption(f"{age_emoji} {t('data_from')}: {data.get('data_age_label')}")

                if max_val >= threshold:
                    exceeded = ((max_val - threshold) / threshold * 100)
                    st.error(f"{t('exceeded_by')} {exceeded:.1f}%")

def display_violations(pollution_data: Dict, city: str):
    """Display violations with AI source attribution."""
    st.subheader(f"⚠️ {t('violation_analysis')}")

    fetcher, analyzer, visualizer, validator, recorder = initialize_services()
    violations = []

    for gas, data in pollution_data.items():
        if not data.get('success'):
            continue

        threshold_check = analyzer.check_threshold_violation(gas, data['statistics']['max'])

        if threshold_check['violated']:
            hotspot = analyzer.find_hotspot(data)
            if hotspot:
                factories = analyzer.find_nearby_factories(hotspot, city)
                wind_data = data.get('wind', {})

                if wind_data.get('success'):
                    factories = analyzer.calculate_wind_vector_to_factories(
                        hotspot, factories, wind_data
                    )

                violation_info = {
                    'gas': gas,
                    'gas_name': config.GAS_PRODUCTS[gas]['name'],
                    'max_value': data['statistics']['max'],
                    'threshold': threshold_check['threshold'],
                    'unit': data['unit'],
                    'severity': threshold_check['severity'],
                    'percentage_over': threshold_check['percentage_over'],
                    'hotspot': hotspot,
                    'city': city,
                    'timestamp_ksa': data.get('timestamp_ksa', 'N/A'),
                    'wind': wind_data,
                    'nearby_factories': factories[:5]
                }

                violations.append(violation_info)

    if violations:
        for violation in violations:
            with st.container():
                col1, col2 = st.columns([2, 1])

                with col1:
                    st.error(f"**{violation['gas']} {t('violation_detected')}**")
                    st.write(f"**{t('severity')}:** {violation['severity'].upper()}")
                    st.write(f"**{t('value')}:** {format_gas_value(violation['max_value'], violation['gas'])}")
                    st.write(f"**{t('threshold')}:** {format_gas_value(violation['threshold'], violation['gas'])}")
                    st.write(f"**{t('exceeded_by')}:** {violation['percentage_over']:.1f}%")

                    if violation['wind'].get('success'):
                        st.write(f"**{t('wind')}:** {violation['wind']['speed_ms']:.1f} m/s {t('wind_from')} {violation['wind']['direction_cardinal']} ({violation['wind']['direction_deg']:.0f}°)")
                        st.write(f"**{t('wind_confidence')}:** {violation['wind']['confidence']:.0f}%")

                    if violation.get('hotspot'):
                        st.write(f"**{t('hotspot_location')}:** ({violation['hotspot']['lat']:.4f}, {violation['hotspot']['lon']:.4f})")

                with col2:
                    st.write(f"**🤖 {t('ai_analysis')}:**")
                    with st.spinner(t('analyzing_source')):
                        import tempfile

                        temp_map = visualizer.create_pollution_map(
                            pollution_data[violation['gas']],
                            violation['wind'],
                            hotspot=violation['hotspot'],
                            factories=violation['nearby_factories'],
                            violation=True
                        )

                        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
                            temp_map.save(f.name)
                            temp_html_path = f.name

                        temp_png_path = temp_html_path.replace('.html', '.png')
                        map_image_created = visualizer.save_map_as_image(temp_html_path, temp_png_path)

                        if map_image_created:
                            analysis = analyzer.ai_analysis(violation, map_image_path=temp_png_path)
                        else:
                            analysis = analyzer.ai_analysis(violation)

                    if len(analysis) > 300:
                        st.info(analysis[:300] + "...")
                        with st.expander(t('view_full_analysis')):
                            st.write(analysis)
                    else:
                        st.info(analysis)

                    if recorder:
                        existing_id = recorder.violation_exists(
                            violation['city'],
                            violation['gas'],
                            violation['timestamp_ksa']
                        )

                        if existing_id:
                            st.caption(f"📁 {t('already_saved')}: {existing_id}")
                        else:
                            with st.spinner(t('saving_violation')):
                                violation_id = recorder.save_violation(violation, analysis, temp_html_path)
                                if violation_id:
                                    st.success(f"{t('saved')}: {violation_id}")
                                else:
                                    st.warning(t('save_failed'))

                    try:
                        if os.path.exists(temp_html_path):
                            os.remove(temp_html_path)
                        if map_image_created and os.path.exists(temp_png_path):
                            os.remove(temp_png_path)
                    except (OSError, IOError) as cleanup_error:
                        logger.debug(f"Failed to clean up temp files: {cleanup_error}")

                if violation.get('nearby_factories'):
                    with st.expander(f"📍 {t('nearby_facilities')} ({len(violation['nearby_factories'])} {t('found')})"):
                        for factory in violation['nearby_factories'][:5]:
                            col1, col2, col3 = st.columns([2, 1, 1])
                            with col1:
                                st.write(f"**{factory.get('name', 'Unknown')}**")
                                st.write(f"{t('type')}: {factory.get('type', 'Unknown')}")
                            with col2:
                                st.write(f"{t('distance')}: {factory.get('distance_km', 0):.1f} {t('km')}")
                                if factory.get('likely_upwind', False):
                                    st.write(f"⚠️ **{t('upwind')}**")
                            with col3:
                                st.write(f"{t('confidence')}: {factory.get('confidence', 0):.0f}%")
                                emissions = factory.get('emissions', [])
                                if emissions:
                                    st.write(f"{t('emissions')}: {', '.join(emissions[:2])}")

                st.divider()
    else:
        st.success(f"✅ {t('no_violations')}")

def display_map(pollution_data: Dict, city: str):
    """Display interactive pollution heatmap."""
    st.subheader(f"🗺️ {t('pollution_heatmap')}")

    from streamlit_folium import st_folium

    fetcher, analyzer, visualizer, validator, _ = initialize_services()

    available_gases = [gas for gas, data in pollution_data.items()
                      if data.get('success')]

    if not available_gases:
        st.warning(t('no_map_data'))
        return

    gases_with_pixels = [gas for gas in available_gases
                        if pollution_data[gas].get('pixels')]

    violation_gases_list = []
    for gas in available_gases:
        stats = pollution_data[gas].get('statistics')
        if stats is None:
            continue
        max_val = stats.get('max')
        if max_val is None:
            continue
        threshold_check = analyzer.check_threshold_violation(gas, max_val)
        if threshold_check.get('violated'):
            violation_gases_list.append(gas)

    default_index = 0
    if violation_gases_list:
        for i, gas in enumerate(available_gases):
            if gas in violation_gases_list:
                default_index = i
                break

    gas_options = []
    gas_labels = {}
    for gas in available_gases:
        base_label = f"{gas} - {config.GAS_PRODUCTS[gas]['name']}"
        if gas in violation_gases_list:
            label = f"{base_label} ⚠️ {t('violation').upper()}"
        else:
            label = base_label
        gas_options.append(gas)
        gas_labels[gas] = label

    if violation_gases_list:
        st.warning(f"⚠️ {len(violation_gases_list)} gases with threshold violations: {', '.join(violation_gases_list)}")

    selected_gas = st.selectbox(
        t('select_gas_display'),
        gas_options,
        index=default_index,
        format_func=lambda x: gas_labels.get(x, x)
    )

    if selected_gas:
        gas_data = pollution_data[selected_gas]

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric(f"{selected_gas} {t('max')}",
                     format_gas_value_short(gas_data['statistics']['max'], selected_gas),
                     config.GAS_PRODUCTS[selected_gas].get('display_unit', gas_data['unit']))
        with col2:
            st.metric(f"{selected_gas} {t('mean')}",
                     format_gas_value_short(gas_data['statistics']['mean'], selected_gas),
                     f"{t('min')}: {format_gas_value_short(gas_data['statistics']['min'], selected_gas)}")
        with col3:
            if gas_data.get('wind', {}).get('success'):
                wind = gas_data['wind']
                st.metric(t('wind'),
                         f"{wind['speed_ms']:.1f} m/s",
                         f"{t('wind_from')} {wind['direction_cardinal']} ({wind['direction_deg']:.0f}°)")
            else:
                st.metric(t('wind'), t('no_data'), "—")
        with col4:
            # Show pixel count if available
            pixel_count = gas_data.get('statistics', {}).get('pixel_count', 0)
            st.metric(t('data_quality'),
                     pixel_count,
                     t('pixels') if pixel_count > 0 else t('no_data'))

        with st.expander(f"🕐 {t('detailed_timing')}", expanded=True):
            col1, col2, col3 = st.columns(3)

            with col1:
                sat_time_ksa = gas_data.get('timestamp_ksa', 'N/A')
                if hasattr(sat_time_ksa, 'strftime'):
                    st.info(f"**🛰️ {t('satellite_pass')}:**\n{sat_time_ksa.strftime('%Y-%m-%d %H:%M:%S KSA')}")
                else:
                    st.info(f"**🛰️ {t('satellite_pass')}:**\n{sat_time_ksa}")

            with col2:
                if gas_data.get('wind', {}).get('timestamp_ksa'):
                    wind_time = gas_data['wind']['timestamp_ksa']
                    if hasattr(wind_time, 'strftime'):
                        st.info(f"**💨 {t('wind_reading')}:**\n{wind_time.strftime('%Y-%m-%d %H:%M:%S KSA')}")
                    else:
                        st.info(f"**💨 {t('wind_reading')}:**\n{wind_time}")
                else:
                    st.info(f"**💨 {t('wind_reading')}:**\n{t('no_wind_data')}")

            with col3:
                if gas_data.get('wind', {}).get('time_difference_minutes') is not None:
                    time_diff = gas_data['wind']['time_difference_minutes']
                    confidence = gas_data['wind'].get('confidence', 0)
                    if time_diff < 30:
                        quality = f"🟢 {t('excellent')}"
                    elif time_diff < 60:
                        quality = f"🟡 {t('good')}"
                    else:
                        quality = f"🔴 {t('poor')}"
                    st.info(f"**⏱️ {t('sync_quality')}:**\n{quality}\nΔt: {time_diff:.0f} min\n{t('confidence')}: {confidence:.0f}%")
                else:
                    st.info(f"**⏱️ {t('sync_quality')}:**\n{t('no_sync_data')}")

        hotspot = analyzer.find_hotspot(gas_data)

        factories = None
        if hotspot:
            factories = analyzer.find_nearby_factories(hotspot, city)
            wind_data = gas_data.get('wind', {})
            if wind_data.get('success'):
                factories = analyzer.calculate_wind_vector_to_factories(
                    hotspot, factories, wind_data
                )

        threshold_check = analyzer.check_threshold_violation(selected_gas, gas_data['statistics']['max'])
        violation = threshold_check['violated']

        gas_data_for_map = {
            'city': city,
            'gas': selected_gas,
            'pixels': gas_data.get('pixels', []),
            'statistics': gas_data.get('statistics', {}),
            'unit': gas_data.get('unit', '')
        }

        wind_data = gas_data.get('wind', {})

        pollution_map = visualizer.create_pollution_map(
            gas_data=gas_data_for_map,
            wind_data=wind_data,
            hotspot=hotspot,
            factories=factories,
            violation=violation
        )

        st_folium(pollution_map, width=None, height=600, returned_objects=[])

def display_trends(pollution_data: Dict):
    """Display pollution analysis charts."""
    st.subheader(f"📈 {t('pollution_trends')}")

    trend_data = []
    for gas, data in pollution_data.items():
        if data.get('success'):
            threshold = config.GAS_THRESHOLDS.get(gas, {}).get('column_threshold', 0)
            critical = config.GAS_THRESHOLDS.get(gas, {}).get('critical_threshold', 0)
            max_val = data['statistics']['max']
            mean_val = data['statistics']['mean']
            min_val = data['statistics']['min']

            gas_config = config.GAS_PRODUCTS.get(gas, {})
            conversion = gas_config.get('conversion_factor', 1)
            display_unit = gas_config.get('display_unit', data['unit'])
            max_pct = (max_val / threshold * 100) if threshold > 0 else 0

            trend_data.append({
                'Gas': gas,
                'Gas Name': config.GAS_PRODUCTS[gas]['name'],
                'Max (% of Threshold)': max_pct,
                'Max Value': max_val * conversion,
                'Mean Value': mean_val * conversion,
                'Min Value': min_val * conversion,
                'Threshold Value': threshold * conversion,
                'Critical Value': critical * conversion,
                'Unit': display_unit
            })

    if trend_data:
        col1, col2 = st.columns(2)

        with col1:
            violation_count = sum(1 for row in trend_data if row['Max (% of Threshold)'] > 100)
            safe_count = len(trend_data) - violation_count

            if violation_count > 0 or safe_count > 0:
                pie_data = pd.DataFrame({
                    'Status': [t('within_limits'), t('violation')],
                    'Count': [safe_count, violation_count]
                })

                fig_pie = px.pie(pie_data, values='Count', names='Status',
                             title=f"🎯 {t('violation_summary')}",
                             color='Status',
                             color_discrete_map={t('within_limits'): '#10b981', t('violation'): '#ef4444'})

                st.plotly_chart(fig_pie, width="stretch")

                if violation_count > 0:
                    violating_gases = [row['Gas'] for row in trend_data if row['Max (% of Threshold)'] > 100]
                    st.warning(f"⚠️ {t('violations_detected_gases')}: {', '.join(violating_gases)}")

        with col2:
            st.markdown(f"### {t('quick_summary')}")
            for row in trend_data:
                pct = row['Max (% of Threshold)']
                if pct > 100:
                    st.markdown(f"🔴 **{row['Gas']}**: {pct:.0f}% {t('of_threshold_label')} ({t('violation').upper()})")
                elif pct > 80:
                    st.markdown(f"🟡 **{row['Gas']}**: {pct:.0f}% {t('of_threshold_label')} ({t('warning_label')})")
                else:
                    st.markdown(f"🟢 **{row['Gas']}**: {pct:.0f}% {t('of_threshold_label')} ({t('normal_label')})")

        st.divider()

        st.subheader(f"📊 {t('individual_gas_analysis')}")

        num_gases = len(trend_data)
        cols_per_row = 2

        for i in range(0, num_gases, cols_per_row):
            cols = st.columns(cols_per_row)

            for j, col in enumerate(cols):
                if i + j < num_gases:
                    row = trend_data[i + j]
                    gas = row['Gas']
                    gas_name = row['Gas Name']
                    max_val = row['Max Value']
                    mean_val = row['Mean Value']
                    min_val = row['Min Value']
                    threshold = row['Threshold Value']
                    critical = row['Critical Value']
                    unit = row['Unit']
                    pct = row['Max (% of Threshold)']

                    with col:
                        if pct > 100:
                            status_color = "#ef4444"  # Red
                            status_text = "VIOLATION"
                        elif pct > 80:
                            status_color = "#f59e0b"  # Yellow/Orange
                            status_text = "WARNING"
                        else:
                            status_color = "#10b981"
                            status_text = "NORMAL"

                        fig = go.Figure()

                        fig.add_trace(go.Bar(
                            x=[t('min_label_chart'), t('mean_label_chart'), t('max_label_chart')],
                            y=[min_val, mean_val, max_val],
                            marker_color=['#3b82f6', '#8b5cf6', status_color],
                            text=[f'{min_val:.2f}', f'{mean_val:.2f}', f'{max_val:.2f}'],
                            textposition='outside',
                            name=gas
                        ))

                        fig.add_hline(
                            y=threshold,
                            line_dash="dash",
                            line_color="orange",
                            annotation_text=f"{t('threshold_label')}: {threshold:.1f}",
                            annotation_position="right"
                        )

                        if critical > threshold:
                            fig.add_hline(
                                y=critical,
                                line_dash="dot",
                                line_color="red",
                                annotation_text=f"{t('critical_label')}: {critical:.1f}",
                                annotation_position="right"
                            )

                        fig.update_layout(
                            title=dict(
                                text=f"{gas} - {gas_name}<br><sub>{status_text} ({pct:.0f}% of threshold)</sub>",
                                font=dict(size=14)
                            ),
                            yaxis_title=unit,
                            showlegend=False,
                            height=350,
                            margin=dict(t=80, b=40, l=60, r=60),
                            plot_bgcolor='white',
                            yaxis=dict(
                                gridcolor='lightgray',
                                zeroline=True,
                                zerolinecolor='lightgray'
                            )
                        )

                        st.plotly_chart(fig, width="stretch")

        st.divider()

        st.subheader(f"📋 {t('detailed_values_table')}")
        df = pd.DataFrame(trend_data)
        display_df = df[['Gas', 'Gas Name', 'Min Value', 'Mean Value', 'Max Value', 'Threshold Value', 'Unit', 'Max (% of Threshold)']].copy()
        display_df['Max (% of Threshold)'] = display_df['Max (% of Threshold)'].round(1)
        display_df = display_df.rename(columns={
            'Min Value': 'Min',
            'Max Value': 'Max',
            'Mean Value': 'Mean',
            'Threshold Value': 'Threshold',
            'Max (% of Threshold)': '% of Threshold'
        })

        def color_violations(val):
            if isinstance(val, (int, float)) and val > 100:
                return 'background-color: #fee2e2; color: #991b1b'
            elif isinstance(val, (int, float)) and val > 80:
                return 'background-color: #fef3c7; color: #92400e'
            return ''

        styled_df = display_df.style.map(color_violations, subset=['% of Threshold'])
        st.dataframe(styled_df, width="stretch", hide_index=True)

def display_historical_trends(violations: List[Dict], stats: Dict):
    """Display historical trend charts."""
    if not violations:
        return

    st.subheader(f"📈 {t('historical_trends')}")

    df_data = []
    for v in violations:
        try:
            # Parse timestamp
            ts_str = v.get('timestamp', v.get('timestamp_ksa', ''))
            if 'T' in ts_str:
                ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
            else:
                ts = datetime.strptime(ts_str.split(' KSA')[0], '%Y-%m-%d %H:%M:%S')

            df_data.append({
                'date': ts.date(),
                'datetime': ts,
                'gas': v.get('gas', 'Unknown'),
                'severity': v.get('severity', 'unknown'),
                'max_value': v.get('max_value', 0),
                'threshold': v.get('threshold', 0),
                'percentage_over': v.get('percentage_over', 0),
                'city': v.get('city', 'Unknown')
            })
        except Exception:
            continue

    if not df_data:
        st.info(t('not_enough_data'))
        return

    df = pd.DataFrame(df_data)

    trend_tab1, trend_tab2, trend_tab3 = st.tabs([
        f"📅 {t('timeline')}", f"🏭 {t('by_gas')}", f"⚠️ {t('by_severity')}"
    ])

    with trend_tab1:
        daily_counts = df.groupby('date').size().reset_index(name='count')
        daily_counts['date'] = pd.to_datetime(daily_counts['date'])

        fig_timeline = px.area(
            daily_counts,
            x='date',
            y='count',
            title=t('violations_over_time'),
            labels={'date': 'Date', 'count': t('tab_violations')}
        )
        fig_timeline.update_layout(height=300)
        fig_timeline.update_traces(fill='tozeroy', line_color='#ef4444')
        st.plotly_chart(fig_timeline, width="stretch")

        col1, col2, col3 = st.columns(3)
        with col1:
            if len(daily_counts) > 0:
                avg_daily = daily_counts['count'].mean()
                st.metric(t('avg_violations_day'), f"{avg_daily:.1f}")
        with col2:
            if len(daily_counts) > 0:
                max_daily = daily_counts['count'].max()
                st.metric(t('peak_day'), f"{max_daily}")
        with col3:
            date_range = (df['date'].max() - df['date'].min()).days + 1
            st.metric(t('monitoring_period'), f"{date_range} {t('days')}")

    with trend_tab2:
        gas_daily = df.groupby(['date', 'gas']).size().reset_index(name='count')
        gas_daily['date'] = pd.to_datetime(gas_daily['date'])

        fig_gas = px.bar(
            gas_daily,
            x='date',
            y='count',
            color='gas',
            title=t('violations_by_gas_time'),
            labels={'date': 'Date', 'count': t('violations'), 'gas': 'Gas'},
            color_discrete_map={
                'NO2': '#ef4444',
                'SO2': '#f59e0b',
                'CO': '#6366f1',
                'HCHO': '#10b981',
                'CH4': '#8b5cf6'
            }
        )
        fig_gas.update_layout(height=300, barmode='stack')
        st.plotly_chart(fig_gas, width="stretch")

        col1, col2 = st.columns(2)
        with col1:
            gas_totals = df['gas'].value_counts().reset_index()
            gas_totals.columns = ['gas', 'count']
            fig_pie = px.pie(
                gas_totals,
                values='count',
                names='gas',
                title=t('total_violations_gas'),
                color='gas',
                color_discrete_map={
                    'NO2': '#ef4444',
                    'SO2': '#f59e0b',
                    'CO': '#6366f1',
                    'HCHO': '#10b981',
                    'CH4': '#8b5cf6'
                }
            )
            fig_pie.update_layout(height=250)
            st.plotly_chart(fig_pie, width="stretch")

        with col2:
            avg_exceed = df.groupby('gas')['percentage_over'].mean().reset_index()
            avg_exceed.columns = ['gas', 'avg_percentage']
            fig_exceed = px.bar(
                avg_exceed,
                x='gas',
                y='avg_percentage',
                title=t('avg_exceedance_gas'),
                labels={'gas': 'Gas', 'avg_percentage': t('avg_percent_threshold')},
                color='avg_percentage',
                color_continuous_scale='Reds'
            )
            fig_exceed.update_layout(height=250, showlegend=False)
            st.plotly_chart(fig_exceed, width="stretch")

    with trend_tab3:
        severity_daily = df.groupby(['date', 'severity']).size().reset_index(name='count')
        severity_daily['date'] = pd.to_datetime(severity_daily['date'])

        fig_severity = px.bar(
            severity_daily,
            x='date',
            y='count',
            color='severity',
            title=t('violations_severity_time'),
            labels={'date': 'Date', 'count': t('violations'), 'severity': t('severity')},
            color_discrete_map={
                'critical': '#dc2626',
                'moderate': '#f59e0b',
                'normal': '#22c55e'
            }
        )
        fig_severity.update_layout(height=300, barmode='stack')
        st.plotly_chart(fig_severity, width="stretch")

        col1, col2 = st.columns(2)
        with col1:
            severity_totals = df['severity'].value_counts().reset_index()
            severity_totals.columns = ['severity', 'count']
            fig_sev_pie = px.pie(
                severity_totals,
                values='count',
                names='severity',
                title=t('violations_by_severity'),
                color='severity',
                color_discrete_map={
                    'critical': '#dc2626',
                    'moderate': '#f59e0b',
                    'normal': '#22c55e'
                }
            )
            fig_sev_pie.update_layout(height=250)
            st.plotly_chart(fig_sev_pie, width="stretch")

        with col2:
            total = len(df)
            critical_count = len(df[df['severity'] == 'critical'])
            moderate_count = len(df[df['severity'] == 'moderate'])
            critical_rate = (critical_count / total * 100) if total > 0 else 0
            moderate_rate = (moderate_count / total * 100) if total > 0 else 0

            st.markdown(f"### {t('severity_breakdown')}")
            st.metric(t('critical_rate'), f"{critical_rate:.1f}%", delta=f"{critical_count} {t('violations')}")
            st.metric(t('moderate_rate'), f"{moderate_rate:.1f}%", delta=f"{moderate_count} {t('violations')}")


def display_violation_history(city: str):
    """Display historical violation records."""
    _, _, visualizer, _, recorder = initialize_services()

    if not recorder:
        st.warning(t('recorder_unavailable_msg'))
        return

    storage_info = recorder.get_storage_info()

    with st.expander(f"ℹ️ {t('storage_info')}", expanded=False):
        if storage_info.get('use_firestore'):
            st.success(f"☁️ **Google Cloud Firestore** - {t('cloud_storage')}")
            st.markdown(f"""
            - **{t('project')}:** `{storage_info.get('project_id')}`
            - **{t('collection')}:** `{storage_info.get('collection_name')}`
            - **{t('status')}:** {'✅ ' + t('connected_writable') if storage_info.get('writable') else '❌ ' + t('not_writable')}
            - **{t('map_storage')}:** ✅ {t('stored_firestore')}

            {t('violations_stored')}
            """)
        else:
            st.warning(f"📁 **{t('local_storage')}**")
            st.markdown(f"""
            **{t('info')}:** {t('local_storage_note')}

            - **{t('path')}:** `{storage_info.get('local_path')}`
            - **{t('status')}:** {'✅ ' + t('connected_writable') if storage_info.get('writable') else '❌ ' + t('not_writable')}
            - **{t('firestore_available')}:** {t('yes') if storage_info.get('firestore_available') else t('no') + ' (' + t('install_firestore') + ')'}
            """)

    stats = recorder.get_statistics(city=city)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(t('total_violations'), stats['total_violations'])
    with col2:
        if stats['by_severity']:
            most_severe = max(stats['by_severity'].keys(), key=lambda x: stats['by_severity'][x])
            st.metric(t('most_common_severity'), most_severe.capitalize())
        else:
            st.metric(t('most_common_severity'), "N/A")
    with col3:
        if stats['by_gas']:
            most_frequent = max(stats['by_gas'].keys(), key=lambda x: stats['by_gas'][x])
            st.metric(t('most_frequent_gas'), most_frequent)
        else:
            st.metric(t('most_frequent_gas'), "N/A")
    with col4:
        if stats.get('date_range'):
            st.metric(t('records_since'), stats['date_range']['oldest'].split()[0])
        else:
            st.metric(t('records_since'), "N/A")

    if stats['total_violations'] == 0:
        st.info(t('no_violations_recorded'))
        st.markdown("---")
        st.markdown(f"**💡 {t('tip')}:** {t('tip_violations')}")
        return

    all_violations = recorder.get_all_violations(city=city, limit=500)

    if len(all_violations) >= 2:
        display_historical_trends(all_violations, stats)
        st.divider()

    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        gas_filter = st.selectbox(
            t('filter_by_gas'),
            [t('all')] + list(stats['by_gas'].keys()),
            key="history_gas_filter"
        )
    with col2:
        limit = st.number_input(t('show_records'), min_value=10, max_value=100, value=20, step=10)
    with col3:
        if st.button(f"🗑️ {t('clear_all')}", type="secondary"):
            if st.session_state.get('confirm_clear'):
                # Actually clear
                records = recorder.get_all_violations(city=city)
                for record in records:
                    recorder.delete_violation(record['id'])
                st.success(t('all_records_cleared'))
                st.session_state.confirm_clear = False
                st.rerun()
            else:
                st.session_state.confirm_clear = True
                st.warning(t('click_to_confirm'))

    violations = recorder.get_all_violations(
        city=city,
        gas=None if gas_filter == t('all') else gas_filter,
        limit=limit
    )

    if violations:
        st.subheader(f"📋 {t('showing_violations').format(count=len(violations))}")

        for record in violations:
            with st.expander(
                f"🚨 {record['gas']} - {record['timestamp_ksa']} - {record['severity'].upper()}",
                expanded=False
            ):
                col1, col2 = st.columns([3, 2])

                with col1:
                    st.markdown(f"**{t('pollutant')}:** {record['gas_name']} ({record['gas']})")
                    st.markdown(f"**{t('time_label')}:** {record['timestamp_ksa']}")
                    st.markdown(f"**{t('select_city')}:** {t(record['city'])}")
                    st.markdown(f"**{t('severity')}:** {t(record['severity']).upper()}")
                    st.markdown(f"**{t('max')}:** {format_gas_value(record['max_value'], record['gas'])}")
                    st.markdown(f"**{t('threshold')}:** {format_gas_value(record['threshold'], record['gas'])}")
                    st.markdown(f"**{t('exceeded_by')}:** {record['percentage_over']:.1f}%")

                    # Hotspot location
                    if record.get('hotspot'):
                        st.markdown(f"**{t('hotspot_location')}:** ({record['hotspot']['lat']:.4f}, {record['hotspot']['lon']:.4f})")

                    # Wind data
                    if record.get('wind', {}).get('success'):
                        wind = record['wind']
                        st.markdown(f"**{t('wind')}:** {wind['speed_ms']:.1f} m/s {t('wind_from')} {wind['direction_cardinal']} ({wind['direction_deg']:.0f}°)")

                with col2:
                    if record.get('hotspot'):
                        hotspot = record['hotspot']
                        st.markdown(f"**📍 {t('hotspot_location')}:** [{hotspot['lat']:.4f}, {hotspot['lon']:.4f}](https://www.google.com/maps?q={hotspot['lat']},{hotspot['lon']})")

                    if record.get('map_html'):
                        if st.button(f"🗺️ {t('view_heatmap')}", key=f"view_map_{record['id']}", type="primary"):
                            st.session_state[f"show_map_{record['id']}"] = not st.session_state.get(f"show_map_{record['id']}", False)

                    if st.button(f"🗑️ {t('delete')}", key=f"delete_{record['id']}", type="secondary"):
                        if recorder.delete_violation(record['id']):
                            st.success(t('record_deleted'))
                            st.rerun()
                        else:
                            st.error(t('failed_to_delete'))

                st.markdown(f"**🤖 {t('ai_analysis')}:**")
                st.info(record['ai_analysis'])

                if record.get('nearby_factories'):
                    st.markdown(f"**📍 {t('nearby_factories')} ({len(record['nearby_factories'])}):**")
                    for factory in record['nearby_factories'][:3]:
                        upwind_marker = f"⚠️ {t('upwind')}" if factory.get('likely_upwind') else ""
                        st.markdown(f"- {factory['name']} ({factory['distance_km']:.1f} {t('km')}) {upwind_marker}")

                if st.session_state.get(f"show_map_{record['id']}", False) and record.get('map_html'):
                    st.divider()
                    st.subheader(f"🗺️ {t('pollution_heatmap')}")
                    import streamlit.components.v1 as components
                    components.html(record['map_html'], height=500, scrolling=True)

                    st.download_button(
                        label=f"📥 {t('download_map')}",
                        data=record['map_html'],
                        file_name=f"{record['id']}_heatmap.html",
                        mime="text/html",
                        key=f"download_{record['id']}"
                    )

    else:
        st.info(t('no_records'))

def main():
    """Main application entry point."""
    inject_custom_css()
    create_header()

    city, days_back = create_sidebar()

    if st.session_state.auto_refresh:
        refresh_interval = st.session_state.get('refresh_interval', 6)
        interval_text = f"{refresh_interval} {t('hours')}" if refresh_interval >= 1 else f"{int(refresh_interval*60)} {t('minutes')}"
        st.info(f"🔄 {t('auto_refresh')} - {interval_text}")

    if st.session_state.get('confirm_clear', False):
        pass  # Confirmation state managed by history tab

    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
        f"📊 {t('tab_overview')}",
        f"🌡️ {t('tab_aqi')}",
        f"🗺️ {t('tab_map')}",
        f"📈 {t('tab_analysis')}",
        f"⚠️ {t('tab_violations')}",
        f"💡 {t('tab_insights')}",
        f"📜 {t('tab_history')}",
        f"🏆 {t('tab_benchmark')}"
    ])

    if not st.session_state.pollution_data:
        with st.spinner(t('fetching_data')):
            st.session_state.pollution_data = fetch_pollution_data(city, days_back)
            ksa_tz = pytz.timezone(config.TIMEZONE)
            st.session_state.last_update = datetime.now(ksa_tz).strftime("%Y-%m-%d %H:%M:%S KSA")

    pollution_data = st.session_state.pollution_data

    if not pollution_data:
        st.error(f"❌ {t('error')}: {t('no_data')}")
        if st.button(t('retry')):
            st.session_state.pollution_data = {}
            st.rerun()
        return

    with tab1:
        st.header(f"{t('tab_overview')} - {t(city)}")

        data_ages = set()
        for gas, data in pollution_data.items():
            if data.get('success') and data.get('days_old') is not None:
                data_ages.add(data.get('days_old'))

        if len(data_ages) > 1:
            max_age = max(data_ages)
            st.info(f"ℹ️ **{t('info')}:** {t('data_note_different_days').format(days=max_age)}")

        display_metrics(pollution_data)

        st.divider()
        col1, col2, col3 = st.columns(3)

        violations_count = sum(1 for gas, data in pollution_data.items()
                             if data.get('success') and
                             data['statistics']['max'] >= config.GAS_THRESHOLDS.get(gas, {}).get('column_threshold', float('inf')))

        with col1:
            st.metric(t('total_gases_monitored'), len(pollution_data))
        with col2:
            st.metric(t('violations_detected'), violations_count)
        with col3:
            if pollution_data:
                st.metric(t('data_quality_label'), t('high') if all(d.get('success') for d in pollution_data.values()) else t('partial'))
            else:
                st.metric(t('data_quality_label'), t('no_data_label'))

    with tab2:
        st.header(f"🌡️ {t('aqi_dashboard_header')}")
        _, _, _, validator, _ = initialize_services()

        create_aqi_dashboard(pollution_data, validator)
        st.divider()
        create_health_risk_panel(pollution_data, validator)

    with tab3:
        st.header(f"🗺️ {t('pollution_map')} - {t(city)}")
        display_map(pollution_data, city)

    with tab4:
        st.header(f"📈 {t('detailed_analysis')}")
        display_trends(pollution_data)

    with tab5:
        st.header(f"⚠️ {t('violation_details')}")
        display_violations(pollution_data, city)

    with tab6:
        st.header(f"💡 {t('intelligent_insights')}")
        _, _, _, validator, _ = initialize_services()

        create_insights_panel(pollution_data, city, validator)

        with st.expander(f"🔬 {t('advanced_analytics')}"):
            st.subheader(t('data_validation_report'))
            for gas, data in pollution_data.items():
                if data.get('success'):
                    validation = validator.validate_measurement(gas, data['statistics']['max'], data['unit'])
                    if validation['warnings'] or validation['errors']:
                        st.write(f"**{gas}:**")
                        for warning in validation['warnings']:
                            st.warning(f"⚠️ {warning}")
                        for error in validation['errors']:
                            st.error(f"❌ {error}")

    with tab7:
        st.header(f"📜 {t('tab_history')}")
        display_violation_history(city)

    with tab8:
        st.header(f"🏆 {t('cities_benchmark')}")
        st.markdown(f"*{t('benchmark_subtitle')}*")

        lang = st.session_state.get('language', 'en')

        # Initialize services
        fetcher, _, _, _, recorder = initialize_services()
        benchmark_analyzer = CityBenchmarkAnalyzer(violation_recorder=recorder)

        from background_scanner import RegionalScanner

        scanner = RegionalScanner(fetcher=fetcher, recorder=recorder)
        stale_cities = scanner.get_stale_cities(max_age_hours=6)

        if len(stale_cities) > 10:
            with st.spinner(t('auto_scanning')):
                scan_results = scanner.scan_all_cities(days_back=7, auto_record_violations=True)
                if scan_results.get('violations'):
                    st.success(t('auto_scan_complete').format(
                        cities=scan_results['cities_with_data'],
                        violations=len(scan_results['violations']),
                        time=scan_results['scan_time']
                    ))

        with st.spinner(t('benchmark_loading')):
            cache_data, historical_data = benchmark_analyzer.load_all_data()

        col1, col2, col3 = st.columns(3)
        with col1:
            cities_with_cache = len([c for c in cache_data if cache_data.get(c, {}).get('metrics')])
            st.metric(t('live_data_cities'), f"{cities_with_cache}/21")
        with col2:
            cities_with_history = len(historical_data)
            st.metric(t('historical_data_cities'), cities_with_history)
        with col3:
            total_violations = sum(len(v) for v in historical_data.values())
            st.metric(t('total_violations'), total_violations)

        with st.expander(f"🔄 {t('refresh_cache')}", expanded=False):
            st.markdown(f"*{t('refresh_cache_desc')}*")
            st.caption(t('efficient_scan_note'))

            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button(f"🔄 {t('scan_all_cities')}", type="primary"):
                    with st.spinner(t('scanning_all_cities')):
                        results = scanner.scan_all_cities(days_back=7, auto_record_violations=True)

                    st.success(t('scan_complete').format(
                        success=results['cities_with_data'],
                        failed=21 - results['cities_with_data'],
                        duration=results['scan_time']
                    ))

                    if results.get('violations'):
                        st.info(t('violations_auto_recorded').format(count=len(results['violations'])))

                    st.rerun()

            with col2:
                stale_count = len(scanner.get_stale_cities(max_age_hours=6))
                if stale_count > 0:
                    st.warning(t('stale_cities').format(count=stale_count))
                else:
                    st.success(t('all_cities_fresh'))

            with col3:
                # Clear all history button with confirmation
                if 'confirm_clear_all' not in st.session_state:
                    st.session_state.confirm_clear_all = False

                if st.button(f"🗑️ {t('clear_all_history')}", type="secondary"):
                    if st.session_state.confirm_clear_all:
                        # Actually clear
                        if recorder and recorder.use_firestore:
                            try:
                                deleted = recorder.clear_all_violations()
                                st.success(t('all_history_cleared').format(count=deleted))
                                st.session_state.confirm_clear_all = False
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error clearing history: {e}")
                                st.session_state.confirm_clear_all = False
                        else:
                            st.error("Database not available")
                            st.session_state.confirm_clear_all = False
                    else:
                        st.session_state.confirm_clear_all = True
                        st.warning(t('click_to_confirm_clear_all'))

        st.divider()

        # Calculate fair rankings
        rankings = benchmark_analyzer.rank_cities(cache_data, historical_data)
        summary_stats = benchmark_analyzer.get_summary_statistics(cache_data, historical_data)
        regional_stats = benchmark_analyzer.get_regional_statistics(cache_data, historical_data)

        create_benchmark_summary(summary_stats, lang)

        st.divider()

        benchmark_tab1, benchmark_tab2, benchmark_tab3, benchmark_tab4 = st.tabs([
            f"📋 {t('city_rankings_table')}",
            f"🗺️ {t('regional_comparison')}",
            f"🧪 {t('gas_breakdown')}",
            f"⚖️ {t('compare_cities')}"
        ])

        with benchmark_tab1:
            create_city_rankings_table(rankings, lang)

            st.divider()

            create_city_rankings_chart(rankings, lang)

            col1, col2 = st.columns(2)
            with col1:
                create_category_distribution(rankings, lang)

        with benchmark_tab2:
            # Regional comparison
            create_regional_comparison(regional_stats, lang)

        with benchmark_tab3:
            # Gas-specific rankings
            st.subheader(f"🧪 {t('gas_breakdown')}")

            selected_gas = st.selectbox(
                t('select_gas_ranking'),
                options=list(config.GAS_PRODUCTS.keys()),
                format_func=lambda x: t(x)
            )

            if selected_gas:
                gas_rankings = benchmark_analyzer.get_gas_leaderboard(cache_data, selected_gas)
                create_gas_specific_ranking(gas_rankings, selected_gas, lang)

        with benchmark_tab4:
            # City comparison
            st.subheader(f"⚖️ {t('compare_cities')}")

            col1, col2 = st.columns(2)
            cities_list = list(config.CITIES.keys())

            with col1:
                city1 = st.selectbox(
                    t('select_city_1'),
                    options=cities_list,
                    format_func=lambda x: t(x),
                    index=0
                )

            with col2:
                city2 = st.selectbox(
                    t('select_city_2'),
                    options=cities_list,
                    format_func=lambda x: t(x),
                    index=min(1, len(cities_list)-1)
                )

            if city1 and city2 and city1 != city2:
                comparison = benchmark_analyzer.compare_cities(city1, city2, cache_data, historical_data)
                create_city_comparison(comparison, lang)
            elif city1 == city2:
                st.warning(f"⚠️ {t('select_different_cities')}")

        # Note about fair benchmark methodology
        st.divider()
        st.info(f"ℹ️ {t('benchmark_note_fair')}")

    # Footer with enhanced information
    st.divider()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.caption(f"**{t('data_source')}:** ESA Sentinel-5P TROPOMI")
    with col2:
        st.caption(f"**{t('standards')}:** Sentinel-5P Typical Ranges")
    with col3:
        ksa_tz = pytz.timezone(config.TIMEZONE)
        current_time = datetime.now(ksa_tz)
        st.caption(f"**{t('system_time')}:** {current_time.strftime('%Y-%m-%d %H:%M:%S KSA')}")

if __name__ == "__main__":
    main()