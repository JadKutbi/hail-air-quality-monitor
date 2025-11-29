"""Regional scanner for Hail Province pollution monitoring."""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pytz
import time
import ee

import config

logging.basicConfig(level=config.LOG_LEVEL, format=config.LOG_FORMAT)
logger = logging.getLogger(__name__)

HAIL_BBOX = [40.0, 26.5, 44.0, 28.5]


class RegionalScanner:
    """Efficient scanner that fetches Hail Province pollution data."""

    CACHE_COLLECTION = "city_pollution_cache"

    def __init__(self, fetcher=None, db=None, recorder=None):
        self.fetcher = fetcher
        self.db = db
        self.recorder = recorder
        self.cities = list(config.CITIES.keys())
        self.ksa_tz = pytz.timezone(config.TIMEZONE)
        self._ee_initialized = False

    def _ensure_ee(self):
        """Initialize Earth Engine."""
        if self._ee_initialized:
            return True

        if self.fetcher and self.fetcher.ee_initialized:
            self._ee_initialized = True
            return True

        try:
            import streamlit as st
            if hasattr(st, 'secrets') and 'GEE_SERVICE_ACCOUNT' in st.secrets:
                service_account = st.secrets['GEE_SERVICE_ACCOUNT']
                credentials = ee.ServiceAccountCredentials(
                    service_account,
                    key_data=st.secrets['GEE_PRIVATE_KEY']
                )
                ee.Initialize(credentials, project=config.GEE_PROJECT)
            else:
                ee.Initialize(project=config.GEE_PROJECT)
            self._ee_initialized = True
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Earth Engine: {e}")
            return False

    def _ensure_db(self):
        """Lazy-load Firestore client."""
        if self.db is None and self.recorder:
            if hasattr(self.recorder, 'db') and self.recorder.use_firestore:
                self.db = self.recorder.db
        return self.db

    def fetch_regional_gas_data(self, gas: str, days_back: int = 7) -> Optional[ee.Image]:
        """Fetch gas data for Hail Province using mosaic for best coverage."""
        if not self._ensure_ee():
            return None

        gas_config = config.GAS_PRODUCTS.get(gas)
        if not gas_config:
            logger.error(f"Unknown gas: {gas}")
            return None

        aoi = ee.Geometry.Rectangle(HAIL_BBOX)
        end_date = datetime.now(pytz.UTC)
        start_date = end_date - timedelta(days=days_back)

        try:
            collection = ee.ImageCollection(gas_config["dataset"]) \
                .filterBounds(aoi) \
                .filterDate(start_date.strftime('%Y-%m-%d'),
                           end_date.strftime('%Y-%m-%d')) \
                .select(gas_config["band"])

            count = collection.size().getInfo()
            if count == 0:
                start_date = end_date - timedelta(days=days_back * 3)
                collection = ee.ImageCollection(gas_config["dataset"]) \
                    .filterBounds(aoi) \
                    .filterDate(start_date.strftime('%Y-%m-%d'),
                               end_date.strftime('%Y-%m-%d')) \
                    .select(gas_config["band"])
                count = collection.size().getInfo()

            if count == 0:
                logger.warning(f"No {gas} data found for Hail Province")
                return None

            sorted_collection = collection.sort('system:time_start', False)
            mosaic = sorted_collection.mosaic()

            test_stats = mosaic.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=aoi,
                scale=10000,
                maxPixels=1e9,
                bestEffort=True
            ).getInfo()

            if test_stats.get(gas_config["band"]) is not None:
                logger.info(f"Created {gas} mosaic from {count} images")
                return mosaic
            else:
                logger.warning(f"No valid {gas} data in mosaic")
                return None

        except Exception as e:
            logger.error(f"Error fetching regional {gas} data: {e}")
            return None

    def extract_city_stats(self, image: ee.Image, gas: str, city: str) -> Dict:
        """Extract statistics for a city from the regional image."""
        city_config = config.CITIES.get(city)
        if not city_config:
            return {'success': False, 'error': f'Unknown city: {city}'}

        gas_config = config.GAS_PRODUCTS.get(gas)
        bbox = city_config["bbox"]
        city_aoi = ee.Geometry.Rectangle(bbox)

        try:
            stats = image.reduceRegion(
                reducer=ee.Reducer.mean().combine(
                    reducer2=ee.Reducer.max(),
                    sharedInputs=True
                ).combine(
                    reducer2=ee.Reducer.min(),
                    sharedInputs=True
                ),
                geometry=city_aoi,
                scale=1113,
                maxPixels=1e9,
                bestEffort=True
            ).getInfo()

            band = gas_config["band"]
            mean_val = stats.get(f"{band}_mean")
            max_val = stats.get(f"{band}_max")
            min_val = stats.get(f"{band}_min")

            if mean_val is None and max_val is None:
                return {'success': False, 'error': 'No data for city area'}

            mean_val = max(0.0, mean_val) if mean_val else 0
            max_val = max(0.0, max_val) if max_val else 0
            min_val = max(0.0, min_val) if min_val else 0

            threshold = config.GAS_THRESHOLDS.get(gas, {}).get('column_threshold', 0)
            is_violation = max_val >= threshold if threshold > 0 else False
            pct_over = ((max_val - threshold) / threshold * 100) if threshold > 0 and is_violation else 0

            return {
                'success': True,
                'value': max_val,
                'mean': mean_val,
                'min': min_val,
                'threshold': threshold,
                'is_violation': is_violation,
                'percentage_over': round(pct_over, 1),
                'unit': gas_config['unit']
            }

        except Exception as e:
            logger.error(f"Error extracting stats for {city}/{gas}: {e}")
            return {'success': False, 'error': str(e)}

    def scan_all_cities(self, days_back: int = 7, auto_record_violations: bool = True) -> Dict:
        """Scan Hail Province with one GEE call per gas."""
        start_time = time.time()
        logger.info("Starting regional scan of Hail Province...")

        results = {
            'cities': {},
            'violations': [],
            'scan_time': None,
            'gases_scanned': 0,
            'cities_with_data': 0,
            'timestamp': datetime.now(self.ksa_tz).isoformat()
        }

        gas_images = {}
        gas_timestamps = {}

        for gas in config.GAS_PRODUCTS.keys():
            logger.info(f"Fetching {gas} for Hail Province...")
            image = self.fetch_regional_gas_data(gas, days_back)
            if image:
                gas_images[gas] = image
                results['gases_scanned'] += 1
                gas_timestamps[gas] = datetime.now(pytz.UTC)

        if not gas_images:
            logger.warning("No gas data available")
            results['error'] = 'No satellite data available'
            return results

        for city in self.cities:
            city_data = {
                'city': city,
                'region': config.CITIES.get(city, {}).get('region', 'Unknown'),
                'readings': {},
                'violations': [],
                'metrics': {}
            }

            successful_gases = 0
            threshold_percentages = []

            for gas, image in gas_images.items():
                stats = self.extract_city_stats(image, gas, city)

                if stats.get('success'):
                    successful_gases += 1
                    city_data['readings'][gas] = {
                        'value': stats['value'],
                        'mean': stats['mean'],
                        'threshold': stats['threshold'],
                        'is_violation': stats['is_violation'],
                        'percentage_over': stats['percentage_over'],
                        'timestamp': gas_timestamps.get(gas, datetime.now(pytz.UTC)).isoformat(),
                        'days_old': (datetime.now(pytz.UTC) - gas_timestamps.get(gas, datetime.now(pytz.UTC))).days
                    }

                    if stats['threshold'] > 0:
                        pct = (stats['value'] / stats['threshold']) * 100
                        threshold_percentages.append(pct)

                    if stats['is_violation']:
                        violation = {
                            'city': city,
                            'gas': gas,
                            'value': stats['value'],
                            'threshold': stats['threshold'],
                            'percentage_over': stats['percentage_over'],
                            'severity': 'critical' if stats['percentage_over'] >= 100 else 'moderate',
                            'timestamp_ksa': gas_timestamps.get(gas, datetime.now(pytz.UTC)).astimezone(self.ksa_tz).strftime('%Y-%m-%d %H:%M:%S KSA')
                        }
                        city_data['violations'].append(violation)
                        results['violations'].append(violation)

                        if auto_record_violations and self.recorder:
                            self._record_violation(violation, gas)

                else:
                    city_data['readings'][gas] = {
                        'value': None,
                        'error': stats.get('error', 'No data'),
                        'is_violation': False
                    }

            data_completeness = successful_gases / len(config.GAS_PRODUCTS)
            avg_threshold_pct = sum(threshold_percentages) / len(threshold_percentages) if threshold_percentages else 0
            pollution_index = avg_threshold_pct

            city_data['metrics'] = {
                'pollution_index': round(pollution_index, 1),
                'active_violations': len(city_data['violations']),
                'gases_monitored': successful_gases,
                'data_completeness': round(data_completeness, 2),
                'avg_threshold_percentage': round(avg_threshold_pct, 1)
            }

            results['cities'][city] = city_data

            if successful_gases > 0:
                results['cities_with_data'] += 1

        self._save_all_to_cache(results)

        results['scan_time'] = round(time.time() - start_time, 1)
        logger.info(f"Regional scan complete in {results['scan_time']}s - {results['cities_with_data']} cities, {len(results['violations'])} violations")

        return results

    def _record_violation(self, violation: Dict, gas: str):
        """Record a violation to Firestore."""
        if not self.recorder:
            return

        try:
            existing = self.recorder.violation_exists(
                violation['city'],
                gas,
                violation['timestamp_ksa']
            )

            if not existing:
                gas_config = config.GAS_PRODUCTS.get(gas, {})
                violation_info = {
                    'gas': gas,
                    'gas_name': gas_config.get('name', gas),
                    'max_value': violation['value'],
                    'threshold': violation['threshold'],
                    'severity': violation['severity'],
                    'percentage_over': violation['percentage_over'],
                    'city': violation['city'],
                    'timestamp_ksa': violation['timestamp_ksa'],
                    'hotspot': None,
                    'wind': {},
                    'nearby_factories': []
                }

                analysis = f"Auto-detected {gas} violation in {violation['city']} via regional scan. Value {violation['value']:.2e} exceeds threshold by {violation['percentage_over']:.1f}%."

                self.recorder.save_violation(violation_info, analysis)
                logger.info(f"Auto-recorded violation: {gas} in {violation['city']}")

        except Exception as e:
            logger.error(f"Failed to record violation: {e}")

    def _save_all_to_cache(self, results: Dict):
        """Save city data to Firestore cache."""
        db = self._ensure_db()
        if not db:
            logger.warning("Firestore not available - cannot save cache")
            return

        now = datetime.now(pytz.UTC)

        for city, city_data in results['cities'].items():
            if city_data['metrics'].get('data_completeness', 0) == 0:
                continue

            try:
                doc = db.collection(self.CACHE_COLLECTION).document(city).get()
                existing_stats = {}
                if doc.exists:
                    existing_stats = doc.to_dict().get('monitoring_stats', {})

                monitoring_stats = {
                    'total_scans': existing_stats.get('total_scans', 0) + 1,
                    'first_scan_date': existing_stats.get('first_scan_date', now.strftime('%Y-%m-%d')),
                    'background_scans': existing_stats.get('background_scans', 0) + 1,
                    'user_scans': existing_stats.get('user_scans', 0),
                }

                cache_doc = {
                    'city': city,
                    'region': city_data['region'],
                    'last_updated': now.isoformat(),
                    'latest_readings': city_data['readings'],
                    'metrics': city_data['metrics'],
                    'violations': city_data['violations'],
                    'monitoring_stats': monitoring_stats
                }

                db.collection(self.CACHE_COLLECTION).document(city).set(cache_doc)

            except Exception as e:
                logger.error(f"Failed to save cache for {city}: {e}")

    def get_cache_status(self) -> Dict[str, Dict]:
        """Get current cache status."""
        db = self._ensure_db()
        if not db:
            return {}

        try:
            status = {}
            now = datetime.now(pytz.UTC)

            for city in self.cities:
                try:
                    doc = db.collection(self.CACHE_COLLECTION).document(city).get()
                    if doc.exists:
                        data = doc.to_dict()
                        last_updated = data.get('last_updated', '')

                        hours_ago = None
                        if last_updated:
                            try:
                                if isinstance(last_updated, str):
                                    last_dt = datetime.fromisoformat(last_updated.replace('Z', '+00:00'))
                                else:
                                    last_dt = last_updated
                                hours_ago = (now - last_dt).total_seconds() / 3600
                            except (ValueError, TypeError, AttributeError):
                                hours_ago = None

                        status[city] = {
                            'has_cache': True,
                            'last_updated': last_updated,
                            'hours_ago': hours_ago,
                            'metrics': data.get('metrics', {}),
                            'violations': len(data.get('violations', []))
                        }
                    else:
                        status[city] = {'has_cache': False}
                except Exception as e:
                    status[city] = {'has_cache': False, 'error': str(e)}

            return status

        except Exception as e:
            logger.error(f"Error getting cache status: {e}")
            return {}

    def get_stale_cities(self, max_age_hours: int = 24) -> List[str]:
        """Get cities that haven't been scanned recently."""
        status = self.get_cache_status()
        stale = []

        for city, info in status.items():
            if not info.get('has_cache'):
                stale.append(city)
            elif info.get('hours_ago') is not None and info['hours_ago'] > max_age_hours:
                stale.append(city)

        return stale


BackgroundCityScanner = RegionalScanner
