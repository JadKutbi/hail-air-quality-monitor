"""Pollution analysis with threshold detection and AI source attribution."""

import numpy as np
from typing import Dict, List, Tuple, Optional
import logging
from datetime import datetime
import json
import os
import config


def format_value_for_display(value: float, gas: str) -> str:
    """Convert raw gas value to display units."""
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


def get_current_language():
    """Get current UI language from session state."""
    try:
        import streamlit as st
        return st.session_state.get('language', 'en')
    except Exception:
        return 'en'

try:
    import vertexai
    from vertexai.generative_models import GenerativeModel, Part, Image
    VERTEX_AI_AVAILABLE = True
except ImportError:
    VERTEX_AI_AVAILABLE = False
    try:
        import google.generativeai as genai
    except ImportError:
        genai = None

logging.basicConfig(level=config.LOG_LEVEL, format=config.LOG_FORMAT)
logger = logging.getLogger(__name__)

class PollutionAnalyzer:
    """Analyze pollution data and attribute sources to industrial facilities."""

    def __init__(self, gemini_api_key: Optional[str] = None,
                 vertex_project: Optional[str] = None,
                 vertex_location: Optional[str] = None):
        """Initialize with Vertex AI or Gemini API for source attribution."""
        self.model = None
        self.use_vertex = False

        if VERTEX_AI_AVAILABLE and vertex_project and vertex_location:
            try:
                vertexai.init(project=vertex_project, location=vertex_location)
                self.model = GenerativeModel("gemini-3-pro-preview-11-2025")
                self.use_vertex = True
                logger.info(f"Vertex AI initialized (project: {vertex_project})")
            except Exception as e:
                logger.warning(f"Vertex AI initialization failed: {e}")

        if not self.model and gemini_api_key and genai:
            genai.configure(api_key=gemini_api_key)
            self.model = genai.GenerativeModel('gemini-3-pro-preview')
            self.use_vertex = False
            logger.info("Gemini API initialized")
    
    def find_hotspot(self, gas_data: Dict) -> Optional[Dict]:
        """Find pixel with maximum concentration."""
        pixels = gas_data.get('pixels', [])

        if not pixels:
            logger.warning(f"No pixels available for {gas_data['gas']}")
            return None

        max_pixel = max(pixels, key=lambda p: p['value'])

        gas_config = config.GAS_PRODUCTS.get(gas_data['gas'], {})
        conversion = gas_config.get('conversion_factor', 1)
        display_unit = gas_config.get('display_unit', gas_data['unit'])
        display_value = max_pixel['value'] * conversion
        if display_value >= 1000:
            formatted_value = f"{display_value:.0f}"
        elif display_value >= 1:
            formatted_value = f"{display_value:.1f}"
        elif display_value >= 0.01:
            formatted_value = f"{display_value:.2f}"
        else:
            formatted_value = f"{display_value:.4f}"

        logger.info(f"Hotspot found at ({max_pixel['lat']:.4f}, {max_pixel['lon']:.4f}) "
                   f"with value {formatted_value} {display_unit}")
        
        return {
            'lat': max_pixel['lat'],
            'lon': max_pixel['lon'],
            'value': max_pixel['value'],
            'gas': gas_data['gas'],
            'unit': gas_data['unit']
        }
    
    def check_threshold_violation(self, gas: str, value: float) -> Dict:
        """Check if concentration exceeds thresholds."""
        threshold_config = config.GAS_THRESHOLDS.get(gas, {})
        threshold = threshold_config.get('column_threshold')
        critical = threshold_config.get('critical_threshold')
        threshold_unit = threshold_config.get('unit')
        gas_unit = config.GAS_PRODUCTS[gas]['unit']
        unit_mismatch = False

        if threshold_unit and gas_unit != threshold_unit:
            unit_mismatch = True
            logger.warning(
                "Unit mismatch detected for %s: gas data in %s vs threshold in %s",
                gas,
                gas_unit,
                threshold_unit
            )
        
        if threshold is None:
            return {'violated': False, 'severity': 'unknown'}

        if critical is None:
            critical = threshold * 2

        if value is None:
            return {'violated': False, 'severity': 'unknown'}

        if value >= critical:
            severity = 'critical'
            violated = True
        elif value >= threshold:
            severity = 'moderate'
            violated = True
        else:
            severity = 'normal'
            violated = False
        
        return {
            'violated': violated,
            'severity': severity,
            'threshold': threshold,
            'critical_threshold': critical,
            'measured_value': value,
            'percentage_over': ((value - threshold) / threshold * 100) if violated else 0,
            'unit': threshold_unit or gas_unit,
            'unit_mismatch': unit_mismatch,
            'who_source': threshold_config.get('source', 'Unknown')
        }
    
    def find_nearby_factories(self, hotspot: Dict, city: str,
                            max_distance_km: float = 250.0) -> List[Dict]:
        """Find factories within radius of hotspot."""
        factories = config.FACTORIES.get(city, [])
        nearby = []
        
        for factory in factories:
            distance = self._haversine_distance(
                hotspot['lat'], hotspot['lon'],
                factory['location'][0], factory['location'][1]
            )
            
            if distance <= max_distance_km:
                nearby.append({
                    **factory,
                    'distance_km': distance
                })
        
        nearby.sort(key=lambda f: f['distance_km'])
        
        logger.info(f"Found {len(nearby)} factories within {max_distance_km}km of hotspot")
        return nearby
    
    def calculate_wind_vector_to_factories(self, hotspot: Dict,
                                          factories: List[Dict],
                                          wind_data: Dict) -> List[Dict]:
        """Score and rank factories by likelihood of being the pollution source."""
        wind_direction = wind_data.get('direction_deg')
        wind_success = wind_data.get('success', False)
        wind_confidence = wind_data.get('confidence', 0 if not wind_success else wind_data.get('confidence', 100))
        detected_gas = hotspot.get('gas', '')

        for factory in factories:
            bearing = self._calculate_bearing(
                factory['location'][0], factory['location'][1],
                hotspot['lat'], hotspot['lon']
            )

            factory['bearing_to_hotspot'] = bearing
            scores = {}

            if wind_success and wind_direction is not None:
                # Factory is upwind if wind blows FROM factory TO hotspot
                reverse_bearing = (bearing + 180) % 360
                angle_diff = abs((reverse_bearing - wind_direction + 180) % 360 - 180)

                # Wind alignment score (0-100)
                if angle_diff <= 15:
                    scores['wind'] = 100.0 - (angle_diff * 2.0)
                elif angle_diff <= 30:
                    scores['wind'] = 70.0 - ((angle_diff - 15) * 2.0)
                elif angle_diff <= 60:
                    scores['wind'] = 40.0 - ((angle_diff - 30) * 1.0)
                elif angle_diff <= 90:
                    scores['wind'] = max(0.0, 10.0 - ((angle_diff - 60) * 0.33))
                else:
                    scores['wind'] = 0.0

                factory['angle_from_wind'] = angle_diff
                factory['likely_upwind'] = bool(angle_diff < 30)
                logger.info(
                    f"Factory: {factory['name'][:30]:<30} | "
                    f"Factory→Hotspot: {bearing:>3.0f}° | "
                    f"Hotspot→Factory: {reverse_bearing:>3.0f}° | "
                    f"Wind from: {wind_direction:>3.0f}° | "
                    f"Deviation: {angle_diff:>3.0f}° | "
                    f"Upwind: {'YES' if angle_diff < 30 else 'NO':<3} | "
                    f"Wind score: {scores['wind']:>3.0f}"
                )
            else:
                scores['wind'] = 0.0
                factory['angle_from_wind'] = None
                factory['likely_upwind'] = False

            # Distance score - closer factories score higher (exponential decay)
            distance_km = factory.get('distance_km', 100)
            scores['distance'] = 100.0 * np.exp(-distance_km / 5.0)

            # Emission match - factory must produce the detected gas
            factory_emissions = factory.get('emissions', [])
            if detected_gas in factory_emissions:
                scores['emission'] = 100.0
                logger.debug(f"Emission match: {factory['name']} produces {detected_gas}")
            else:
                scores['emission'] = 0.0
                logger.debug(f"No emission match: {factory['name']} doesn't produce {detected_gas}")

            # Composite score with weights: wind 40%, distance 30%, emission 20%
            weights = {'wind': 0.40, 'distance': 0.30, 'emission': 0.20}
            composite_score = sum(scores[k] * weights[k] for k in ['wind', 'distance', 'emission'])

            # Penalize factories that don't emit the detected gas
            if scores['emission'] == 0:
                composite_score *= 0.1

            # Adjust for wind data quality
            if wind_confidence >= 70:
                confidence_multiplier = 1.0
            elif wind_confidence >= 40:
                confidence_multiplier = 0.8
            else:
                confidence_multiplier = 0.5

            final_confidence = composite_score * confidence_multiplier

            factory['scores'] = scores
            factory['composite_score'] = composite_score
            factory['confidence'] = float(max(0.0, min(100.0, final_confidence)))
            factory['confidence_breakdown'] = {
                'wind_score': scores.get('wind', 0),
                'distance_score': scores.get('distance', 0),
                'emission_score': scores.get('emission', 0),
                'wind_confidence_multiplier': confidence_multiplier,
                'final_confidence': final_confidence
            }

        # Fallback: if no factories upwind, rank by distance + emission match
        upwind_list = [f['name'] for f in factories if f.get('likely_upwind', False)]
        has_upwind_factory = len(upwind_list) > 0

        logger.info(f"Upwind check: {len(upwind_list)} upwind factories out of {len(factories)} total")
        if upwind_list:
            logger.info(f"Upwind factories: {', '.join(upwind_list)}")
        else:
            logger.info("No upwind factories detected")

        if not has_upwind_factory:
            logger.info("No upwind factories - using distance-based ranking")

            for factory in factories:
                emission_score = factory['scores'].get('emission', 0)
                distance_score = factory['scores'].get('distance', 0)

                if emission_score > 0:
                    factory['confidence'] = distance_score * 0.9
                    factory['fallback_ranking'] = 'emission_match'
                else:
                    factory['confidence'] = distance_score * 0.1
                    factory['fallback_ranking'] = 'no_emission_match'

                logger.info(
                    f"Fallback ranking: {factory['name'][:30]:<30} | "
                    f"Distance: {factory.get('distance_km', 0):>5.1f} km | "
                    f"Emits {detected_gas}: {'YES' if emission_score > 0 else 'NO':<3} | "
                    f"Confidence: {factory['confidence']:>3.0f}%"
                )

        return sorted(factories, key=lambda f: f['confidence'], reverse=True)
    
    def ai_analysis(self, violation_data: Dict, map_image_path: Optional[str] = None) -> str:
        """Use Gemini AI to identify likely pollution source."""
        factories = violation_data.get('nearby_factories', [])
        MIN_CONFIDENCE_THRESHOLD = 40.0

        has_upwind = any(f.get('likely_upwind', False) for f in factories)
        has_confident = any(f.get('confidence', 0) >= MIN_CONFIDENCE_THRESHOLD for f in factories)

        # Skip AI if no clear source candidates
        if factories and not has_upwind and not has_confident:
            logger.warning("No clear source: All factories have confidence < 40% and none are upwind")
            return self._rule_based_analysis(violation_data)

        if not self.model:
            return self._rule_based_analysis(violation_data)

        try:
            current_lang = get_current_language()
            if current_lang == 'ar':
                language_instruction = "IMPORTANT: You MUST respond ENTIRELY in Arabic (العربية). All text, analysis, recommendations, and conclusions must be written in Arabic. Use formal Arabic suitable for official environmental reports."
            else:
                language_instruction = "Respond in English."

            gas = violation_data['gas']
            measured_formatted = format_value_for_display(violation_data['max_value'], gas)
            threshold_formatted = format_value_for_display(violation_data['threshold'], gas)

            prompt = f"""You are an environmental monitoring AI expert analyzing satellite pollution data.

**Violation Details:**
- Gas: {violation_data['gas']} ({violation_data['gas_name']})
- Measured Value: {measured_formatted}
- Satellite Threshold: {threshold_formatted}
- Exceeded by: {violation_data['percentage_over']:.1f}%
- Severity: {violation_data['severity']}
- Location: {violation_data['city']} at ({violation_data['hotspot']['lat']:.4f}, {violation_data['hotspot']['lon']:.4f})
- Time: {violation_data['timestamp_ksa']}

**Wind Conditions:**
- Direction: {violation_data['wind']['direction_deg']:.0f}° ({violation_data['wind']['direction_cardinal']})
- Speed: {violation_data['wind']['speed_ms']:.1f} m/s
- Wind Data Quality: {violation_data['wind'].get('confidence', 0):.0f}% confidence ({violation_data['wind'].get('source_label', 'unknown source')})
- Wind measurement time: {violation_data['wind'].get('timestamp_ksa', 'N/A')}
- Satellite observation time: {violation_data['timestamp_ksa']}
- Time offset: {violation_data['wind'].get('time_offset_hours', 'N/A'):.1f} hours

**Nearby Factories:**
"""
            
            for i, factory in enumerate(violation_data.get('nearby_factories', [])[:5], 1):
                bearing = factory.get('bearing_to_hotspot', 0)
                wind_dir = violation_data['wind']['direction_deg']
                reverse_bearing = (bearing + 180) % 360
                angle_diff = abs((reverse_bearing - wind_dir + 180) % 360 - 180)

                prompt += f"""
{i}. {factory.get('name', 'Unknown')}
   - Type: {factory.get('type', 'Unknown')}
   - Distance: {factory.get('distance_km', 0):.1f} km
   - Bearing to hotspot: {bearing:.0f}° (Factory is {self._get_direction_relative_to_hotspot(bearing)} of hotspot)
   - Produces: {', '.join(factory.get('emissions', []))}
   - Emission match: {'✓ YES - produces {}'.format(violation_data['gas']) if violation_data['gas'] in factory.get('emissions', []) else '✗ NO - does not produce {}'.format(violation_data['gas'])}
   - Upwind status: {'✓ UPWIND (wind blows from factory to hotspot)' if factory.get('likely_upwind', False) else '✗ NOT UPWIND (wind angle mismatch)'}
   - Wind alignment: {angle_diff:.0f}° deviation from ideal
   - Confidence: {factory.get('confidence', 0):.0f}%
"""
            
            prompt += """
**Task:**
Analyze this data and identify the pollution source. Your analysis MUST include:

**CRITICAL FIRST CHECK:**
Before attributing to any factory, verify:
- Are ANY factories marked as "✓ UPWIND" in the data above?
- Are ANY factories showing confidence >40%?
- If NO factories are upwind AND all confidence scores are <40%, you MUST report: **"NO CLEAR SOURCE IDENTIFIED - No factories aligned with wind direction"**

**CLUSTER POLLUTION CHECK:**
Count how many factories are marked "✓ UPWIND":
- If 3 OR MORE factories are upwind within 10 km, this suggests **CLUSTER POLLUTION** (cumulative emissions from industrial zone)
- In this case, recommend **COORDINATED CLUSTER INVESTIGATION** of the entire industrial area, not just one facility
- Report the top 3 contributors and note this is likely combined emissions

**If a clear single source exists (1-2 upwind factories with >40% confidence):**

1. **Primary Source Identification:**
   - Name the most likely factory
   - JUSTIFY your selection by explaining:
     a) EMISSION MATCH: Does this factory produce the detected gas? (CRITICAL: Only select factories that emit this specific gas)
     b) WIND DIRECTION: Is this factory UPWIND of the hotspot? (Wind should blow FROM factory TO hotspot)
     c) DISTANCE: How close is the factory to the pollution hotspot?

2. **Exclusion Reasoning:**
   - Briefly explain why nearby factories were excluded (e.g., "Factory X excluded: wrong emissions" or "Factory Y excluded: downwind location")

3. **Confidence Assessment:**
   - Rate confidence as High (>70%), Medium (40-70%), or Low (<40%)
   - Consider: wind data quality, emission profile match, distance, upwind position

4. **Recommended Actions:**
   - For single source: "Immediate inspection of [factory name]"
   - For cluster (3+ upwind): "COORDINATED CLUSTER INVESTIGATION of [area] industrial zone - inspect [top 3 facilities]"

5. **Alternative Sources** (if applicable)

**If NO clear source (no upwind factories OR all confidence <40%):**
Report: "⚠️ **NO CLEAR SOURCE IDENTIFIED**"
Explain:
- No factories are aligned with wind direction
- List possible explanations: mobile sources, distant sources, wind uncertainty, source outside monitoring area
- Recommend: Expand monitoring radius, investigate mobile/distant sources

CRITICAL RULES:
- ONLY select factories that produce the detected gas type
- ONLY attribute if confidence ≥40% OR factory is upwind
- If wind points to empty space (no factories), report "No clear source"
- LOW wind confidence (<50%) reduces overall attribution certainty
- ALWAYS explain your reasoning with emission matching + wind direction logic

Keep response concise (max 300 words), professional, and actionable.

**LANGUAGE INSTRUCTION:**
{language_instruction}"""

            content_parts = []
            image_included = False

            if map_image_path and os.path.exists(map_image_path):
                try:
                    logger.info(f"Loading map image from {map_image_path}")
                    if self.use_vertex:
                        image_part = Image.load_from_file(map_image_path)
                        content_parts.append(image_part)
                    else:
                        from PIL import Image as PILImage
                        img = PILImage.open(map_image_path)
                        content_parts.append(img)

                    image_included = True

                    prompt += """

**VISUAL MAP ANALYSIS:**
You are analyzing a pollution map image showing:
- RED/ORANGE HOTSPOT MARKER: Exact location of maximum pollution concentration
- BLUE ARROW: Wind direction (arrow points in direction wind is blowing TO)
- RED FACTORY MARKERS: HIGH PRIORITY - Upwind factories that emit the detected gas
- BLUE FACTORY MARKERS: Lower priority - Other nearby factories
- HEATMAP COLORS (Google Maps AQI Standard):
  * GREEN = Good air quality (low concentration)
  * YELLOW = Moderate pollution
  * ORANGE = Unhealthy for sensitive groups
  * RED = Unhealthy (high concentration)
  * PURPLE = Very unhealthy
  * MAROON = Hazardous (extreme concentration)

CRITICAL VISION TASKS:
1. **Spatial Analysis**: Visually verify which factories are upwind of the hotspot by following the blue wind arrow backwards
2. **Pollution Pattern**: Describe the visual shape/spread of the pollution heatmap - is it a tight plume pointing to a source or dispersed?
3. **Distance Assessment**: Visually assess proximity of red markers to the hotspot
4. **Wind Alignment**: Confirm if any red factory markers align with the wind arrow direction relative to the hotspot
5. **Confidence Check**: Does the visual evidence support the data analysis or raise concerns?

Use the visual map to provide insights beyond the numerical data."""

                    logger.info(f"Map image added for vision analysis")
                except Exception as img_err:
                    logger.error(f"Could not load map image: {img_err}")
            elif map_image_path:
                logger.warning(f"Map image not found: {map_image_path}")

            if self.use_vertex:
                content_parts.insert(0, prompt)
            else:
                content_parts.append(prompt)

            logger.info(f"Sending request to Gemini ({'Vertex AI' if self.use_vertex else 'Standard API'})")

            if self.use_vertex:
                response = self.model.generate_content(
                    content_parts,
                    generation_config={
                        'temperature': 0.3,
                        'max_output_tokens': 800,  # More tokens for vision analysis
                        'top_p': 0.95,
                    }
                )
            else:
                response = self.model.generate_content(
                    content_parts,
                    generation_config={
                        'temperature': 0.3,
                        'max_output_tokens': 800,
                    }
                )

            analysis = response.text
            logger.info("Gemini analysis completed")
            return analysis
            
        except Exception as e:
            logger.error(f"Gemini AI analysis failed: {e}")
            return self._rule_based_analysis(violation_data)
    
    def _rule_based_analysis(self, violation_data: Dict) -> str:
        """Fallback analysis when AI unavailable."""
        try:
            factories = violation_data.get('nearby_factories', [])
            lang = get_current_language()
            is_ar = lang == 'ar'

            if not factories:
                if is_ar:
                    return "لم يتم العثور على مصانع بالقرب من بؤرة التلوث. قد يكون المصدر خارج المنطقة المراقبة أو مصدر متنقل."
                return "No factories found near pollution hotspot. Source may be outside monitored area or mobile source."

            # Find upwind factories that produce this gas
            gas = violation_data.get('gas', '')
            if not gas:
                if is_ar:
                    return "خطأ: لم يتم تحديد نوع الغاز في بيانات المخالفة."
                return "Error: Gas type not specified in violation data."

            gas_name = violation_data.get('gas_name', gas)
            wind_dir = violation_data.get('wind', {}).get('direction_cardinal', 'Unknown')
            wind_deg = violation_data.get('wind', {}).get('direction_deg', 0)

            def has_emission(factory, gas_type):
                emissions = factory.get('emissions', [])
                if emissions is None:
                    return False
                if isinstance(emissions, list):
                    return gas_type in emissions
                return False

            upwind_emitters = [f for f in factories if has_emission(f, gas) and f.get('likely_upwind', False)]
            all_emitters = [f for f in factories if has_emission(f, gas)]
            non_emitters = [f for f in factories[:5] if not has_emission(f, gas)]

            candidates = upwind_emitters if upwind_emitters else all_emitters

            wind_confidence = violation_data.get('wind', {}).get('confidence', 0)
            wind_source = violation_data.get('wind', {}).get('source_label', 'unknown')

            if candidates:
                top = candidates[0]
                top_confidence = top.get('confidence', 0)
                top_is_upwind = top.get('likely_upwind', False)
                MIN_CONFIDENCE_THRESHOLD = 40.0

                # Report uncertainty if no clear source
                if not top_is_upwind and top_confidence < MIN_CONFIDENCE_THRESHOLD:
                    if is_ar:
                        analysis = f"⚠️ لم يتم تحديد مصدر واضح\n"
                        analysis += f"{'='*50}\n\n"
                        analysis += f"السبب: لا توجد مصانع متوافقة مع اتجاه الرياح.\n\n"
                        analysis += f"ظروف الرياح:\n"
                        analysis += f"  - اتجاه الرياح: {wind_deg:.0f}° ({wind_dir})\n"
                        analysis += f"  - سرعة الرياح: {violation_data.get('wind', {}).get('speed_ms', 0):.1f} م/ث\n"
                        analysis += f"  - جودة بيانات الرياح: {wind_confidence:.0f}% ({wind_source})\n"
                        wind_time = violation_data.get('wind', {}).get('timestamp_ksa', 'N/A')
                        sat_time = violation_data.get('timestamp_ksa', 'N/A')
                        time_offset = violation_data.get('wind', {}).get('time_offset_hours', 'N/A')
                        analysis += f"  - وقت قياس الرياح: {wind_time}\n"
                        analysis += f"  - وقت رصد القمر الصناعي: {sat_time}\n"
                        analysis += f"  - الفارق الزمني: {time_offset:.1f} ساعات\n\n" if isinstance(time_offset, (int, float)) else f"  - الفارق الزمني: {time_offset}\n\n"

                        analysis += f"تحليل المصانع القريبة:\n"
                        analysis += f"  - {len(candidates)} مصانع تنتج {gas_name}\n"
                        analysis += f"  - أقرب مُنتِج: {top.get('name', 'Unknown')} ({top.get('distance_km', 0):.1f} كم)\n"
                        analysis += f"  - ومع ذلك، هذا المصنع ليس في اتجاه الرياح (الثقة: {top_confidence:.0f}%)\n"
                        analysis += f"  - الرياح لا تهب من أي مصنع معروف ينتج {gas_name} نحو البؤرة\n\n"

                        analysis += f"التفسيرات المحتملة:\n"
                        analysis += f"  - مصدر خارج المنطقة المراقبة (مثلاً: بعد 20 كم)\n"
                        analysis += f"  - مصادر متنقلة (سفن، مركبات، نقل صناعي)\n"
                        analysis += f"  - عدم يقين اتجاه الرياح (ثقة الرياح: {wind_confidence:.0f}%)\n"
                        analysis += f"  - نقل التلوث بعيد المدى من مصادر بعيدة\n"
                        analysis += f"  - قاعدة بيانات انبعاثات المصانع غير مكتملة\n\n"

                        analysis += f"التوصية: توسيع نطاق المراقبة أو التحقيق في المصادر المتنقلة/البعيدة المحتملة.\n\n"

                        analysis += f"مرجع - المُنتِجون القريبون (ليسوا في اتجاه الرياح):\n"
                        for i, factory in enumerate(candidates[:5], 1):
                            try:
                                if isinstance(factory, dict):
                                    name = factory.get('name', 'Unknown')
                                    dist = factory.get('distance_km', 0)
                                    conf = factory.get('confidence', 0)
                                    analysis += f"  {i}. {name} - {dist:.1f} كم، ثقة {conf:.0f}%\n"
                                else:
                                    analysis += f"  {i}. مصنع غير معروف\n"
                            except Exception:
                                analysis += f"  {i}. خطأ في قراءة بيانات المصنع\n"
                    else:
                        analysis = f"⚠️ NO CLEAR SOURCE IDENTIFIED\n"
                        analysis += f"{'='*50}\n\n"
                        analysis += f"REASON: No factories are aligned with the wind direction.\n\n"
                        analysis += f"WIND CONDITIONS:\n"
                        analysis += f"  - Wind Direction: {wind_deg:.0f}° ({wind_dir})\n"
                        analysis += f"  - Wind Speed: {violation_data.get('wind', {}).get('speed_ms', 0):.1f} m/s\n"
                        analysis += f"  - Wind Data Quality: {wind_confidence:.0f}% ({wind_source})\n"
                        wind_time = violation_data.get('wind', {}).get('timestamp_ksa', 'N/A')
                        sat_time = violation_data.get('timestamp_ksa', 'N/A')
                        time_offset = violation_data.get('wind', {}).get('time_offset_hours', 'N/A')
                        analysis += f"  - Wind measurement time: {wind_time}\n"
                        analysis += f"  - Satellite observation time: {sat_time}\n"
                        analysis += f"  - Time offset: {time_offset:.1f} hours\n\n" if isinstance(time_offset, (int, float)) else f"  - Time offset: {time_offset}\n\n"

                        analysis += f"NEARBY FACTORIES ANALYSIS:\n"
                        analysis += f"  - {len(candidates)} factories produce {gas_name}\n"
                        analysis += f"  - Closest emitter: {top.get('name', 'Unknown')} ({top.get('distance_km', 0):.1f} km)\n"
                        analysis += f"  - However, this factory is NOT upwind (confidence: {top_confidence:.0f}%)\n"
                        analysis += f"  - Wind does not blow from any known {gas_name}-producing factory toward the hotspot\n\n"

                        analysis += f"POSSIBLE EXPLANATIONS:\n"
                        analysis += f"  - Source outside monitored area (e.g., beyond 20km radius)\n"
                        analysis += f"  - Mobile sources (ships, vehicles, industrial transport)\n"
                        analysis += f"  - Wind direction uncertainty (wind confidence: {wind_confidence:.0f}%)\n"
                        analysis += f"  - Long-range pollution transport from distant sources\n"
                        analysis += f"  - Incomplete factory emissions database\n\n"

                        analysis += f"RECOMMENDATION: Expand monitoring radius or investigate potential mobile/distant sources.\n\n"

                        # List all nearby emitters for reference
                        analysis += f"REFERENCE - NEARBY EMITTERS (not upwind):\n"
                        for i, factory in enumerate(candidates[:5], 1):
                            try:
                                if isinstance(factory, dict):
                                    name = factory.get('name', 'Unknown')
                                    dist = factory.get('distance_km', 0)
                                    conf = factory.get('confidence', 0)
                                    analysis += f"  {i}. {name} - {dist:.1f} km, {conf:.0f}% confidence\n"
                                else:
                                    analysis += f"  {i}. Unknown factory\n"
                            except Exception:
                                analysis += f"  {i}. Error reading factory data\n"

                    return analysis

                if is_ar:
                    analysis = f"المصدر الأكثر احتمالاً: {top.get('name', 'Unknown')} ({top.get('type', 'Unknown')})\n"
                    analysis += f"{'='*50}\n\n"

                    analysis += "التبرير:\n"
                    analysis += f"✓ تطابق الانبعاثات: المصنع ينتج {gas_name} (الغاز المكتشف: {gas_name})\n"
                    analysis += f"\nظروف الرياح:\n"
                    analysis += f"  - اتجاه الرياح: {wind_deg:.0f}° ({wind_dir})\n"
                    analysis += f"  - سرعة الرياح: {violation_data.get('wind', {}).get('speed_ms', 0):.1f} م/ث\n"
                    analysis += f"  - جودة بيانات الرياح: {wind_confidence:.0f}% ({wind_source})\n"
                    wind_time = violation_data.get('wind', {}).get('timestamp_ksa', 'N/A')
                    sat_time = violation_data.get('timestamp_ksa', 'N/A')
                    time_offset = violation_data.get('wind', {}).get('time_offset_hours', 'N/A')
                    analysis += f"  - وقت قياس الرياح: {wind_time}\n"
                    analysis += f"  - وقت رصد القمر الصناعي: {sat_time}\n"
                    analysis += f"  - الفارق الزمني: {time_offset:.1f} ساعات\n\n" if isinstance(time_offset, (int, float)) else f"  - الفارق الزمني: {time_offset}\n\n"
                    if top.get('likely_upwind', False):
                        analysis += f"✓ توافق الرياح: المصنع في اتجاه الرياح من البؤرة\n"
                        analysis += f"  - الرياح تهب من المصنع إلى بؤرة التلوث\n"
                        analysis += f"  - الاتجاه من المصنع: {top.get('bearing_to_hotspot', 0):.0f}°\n"
                        analysis += f"  - ثقة التوافق: {top.get('confidence', 0):.0f}%\n"
                    else:
                        analysis += f"⚠️ توافق الرياح: المصنع ليس في اتجاه الرياح المثالي\n"
                        analysis += f"  - الاتجاه من المصنع: {top.get('bearing_to_hotspot', 0):.0f}°\n"
                        analysis += f"  - عدم تطابق اتجاه الرياح (تم اختياره لتطابق الانبعاثات + القرب)\n"
                        analysis += f"  - ثقة التوافق: {top.get('confidence', 0):.0f}%\n"

                    analysis += f"✓ المسافة: {top.get('distance_km', 0):.1f} كم من البؤرة\n\n"
                    if non_emitters:
                        analysis += f"المصانع المستبعدة:\n"
                        for f in non_emitters[:2]:
                            analysis += f"✗ {f.get('name', 'Unknown')}: لا ينتج {gas_name}\n"

                    # Similar distance comparison
                    similar_distance_emitters = [
                        f for f in all_emitters
                        if f.get('name') != top.get('name')
                        and abs(f.get('distance_km', 0) - top.get('distance_km', 0)) < 2.0
                    ]

                    if similar_distance_emitters:
                        analysis += f"\nمقارنة مع مصانع على مسافة مماثلة:\n"
                        for f in similar_distance_emitters[:2]:
                            analysis += f"✗ {f.get('name', 'Unknown')} ({f.get('distance_km', 0):.1f} كم):\n"
                            analysis += f"  - توافق الرياح: {f.get('confidence', 0):.0f}% مقابل {top.get('confidence', 0):.0f}%\n"
                            analysis += f"  - الاتجاه: {f.get('bearing_to_hotspot', 0):.0f}° مقابل {top.get('bearing_to_hotspot', 0):.0f}°\n"
                            if f.get('confidence', 0) < top.get('confidence', 0):
                                analysis += f"  - تم اختيار الأساسي بسبب توافق أفضل مع الرياح\n"
                            else:
                                analysis += f"  - مُدرج كمصدر بديل\n"

                    other_downwind = [f for f in all_emitters
                                    if not f.get('likely_upwind', False)
                                    and f.get('name') != top.get('name')
                                    and f not in similar_distance_emitters]
                    if other_downwind:
                        analysis += f"✗ {len(other_downwind)} مُنتِج(ون) آخر(ون): أبعد أو توافق ضعيف مع الرياح\n"

                    analysis += "\n"
                    if wind_confidence < 50:
                        analysis += f"⚠️ الثقة الإجمالية: متوسطة-منخفضة (عدم يقين بيانات الرياح)\n\n"
                    elif top.get('likely_upwind', False) and top.get('distance_km', 0) < 5:
                        analysis += f"✓ الثقة الإجمالية: عالية (في اتجاه الرياح + قريب + تطابق الانبعاثات)\n\n"
                    else:
                        analysis += f"✓ الثقة الإجمالية: متوسطة (تم تأكيد تطابق الانبعاثات)\n\n"

                    analysis += f"التوصية: فحص فوري لضوابط انبعاثات {top.get('name', 'Unknown')} والتغييرات التشغيلية الأخيرة."

                    if len(candidates) > 1:
                        analysis += f"\n\nالمصادر البديلة: {', '.join([f.get('name', 'Unknown') for f in candidates[1:3]])}"
                else:
                    analysis = f"MOST LIKELY SOURCE: {top.get('name', 'Unknown')} ({top.get('type', 'Unknown')})\n"
                    analysis += f"{'='*50}\n\n"

                    analysis += "JUSTIFICATION:\n"
                    analysis += f"✓ Emission Match: Factory produces {gas_name} (detected gas: {gas_name})\n"
                    analysis += f"\nWIND CONDITIONS:\n"
                    analysis += f"  - Wind Direction: {wind_deg:.0f}° ({wind_dir})\n"
                    analysis += f"  - Wind Speed: {violation_data.get('wind', {}).get('speed_ms', 0):.1f} m/s\n"
                    analysis += f"  - Wind Data Quality: {wind_confidence:.0f}% ({wind_source})\n"
                    wind_time = violation_data.get('wind', {}).get('timestamp_ksa', 'N/A')
                    sat_time = violation_data.get('timestamp_ksa', 'N/A')
                    time_offset = violation_data.get('wind', {}).get('time_offset_hours', 'N/A')
                    analysis += f"  - Wind measurement time: {wind_time}\n"
                    analysis += f"  - Satellite observation time: {sat_time}\n"
                    analysis += f"  - Time offset: {time_offset:.1f} hours\n\n" if isinstance(time_offset, (int, float)) else f"  - Time offset: {time_offset}\n\n"
                    if top.get('likely_upwind', False):
                        analysis += f"✓ Wind Alignment: Factory IS upwind of hotspot\n"
                        analysis += f"  - Wind blows FROM factory TO pollution hotspot\n"
                        analysis += f"  - Bearing from factory: {top.get('bearing_to_hotspot', 0):.0f}°\n"
                        analysis += f"  - Alignment confidence: {top.get('confidence', 0):.0f}%\n"
                    else:
                        analysis += f"⚠️ Wind Alignment: Factory NOT ideally upwind\n"
                        analysis += f"  - Bearing from factory: {top.get('bearing_to_hotspot', 0):.0f}°\n"
                        analysis += f"  - Wind bearing mismatch (selected for emission match + proximity)\n"
                        analysis += f"  - Alignment confidence: {top.get('confidence', 0):.0f}%\n"

                    analysis += f"✓ Distance: {top.get('distance_km', 0):.1f} km from hotspot\n\n"
                    if non_emitters:
                        analysis += f"EXCLUDED FACTORIES:\n"
                        for f in non_emitters[:2]:
                            analysis += f"✗ {f.get('name', 'Unknown')}: Does not produce {gas_name}\n"

                    similar_distance_emitters = [
                        f for f in all_emitters
                        if f.get('name') != top.get('name')
                        and abs(f.get('distance_km', 0) - top.get('distance_km', 0)) < 2.0
                    ]

                    if similar_distance_emitters:
                        analysis += f"\nCOMPARISON WITH SIMILAR-DISTANCE FACTORIES:\n"
                        for f in similar_distance_emitters[:2]:
                            analysis += f"✗ {f.get('name', 'Unknown')} ({f.get('distance_km', 0):.1f} km):\n"
                            analysis += f"  - Wind alignment: {f.get('confidence', 0):.0f}% vs {top.get('confidence', 0):.0f}%\n"
                            analysis += f"  - Bearing: {f.get('bearing_to_hotspot', 0):.0f}° vs {top.get('bearing_to_hotspot', 0):.0f}°\n"
                            if f.get('confidence', 0) < top.get('confidence', 0):
                                analysis += f"  - Selected primary due to better wind alignment\n"
                            else:
                                analysis += f"  - Listed as alternative source\n"

                    other_downwind = [f for f in all_emitters
                                    if not f.get('likely_upwind', False)
                                    and f.get('name') != top.get('name')
                                    and f not in similar_distance_emitters]
                    if other_downwind:
                        analysis += f"✗ {len(other_downwind)} other emitter(s): Farther or poor wind alignment\n"

                    analysis += "\n"
                    if wind_confidence < 50:
                        analysis += f"⚠️ OVERALL CONFIDENCE: MEDIUM-LOW (wind data uncertainty)\n\n"
                    elif top.get('likely_upwind', False) and top.get('distance_km', 0) < 5:
                        analysis += f"✓ OVERALL CONFIDENCE: HIGH (upwind + close + emission match)\n\n"
                    else:
                        analysis += f"✓ OVERALL CONFIDENCE: MEDIUM (emission match confirmed)\n\n"

                    analysis += f"RECOMMENDATION: Immediate inspection of {top.get('name', 'Unknown')} emission controls and recent operational changes."

                    if len(candidates) > 1:
                        analysis += f"\n\nALTERNATIVE SOURCES: {', '.join([f.get('name', 'Unknown') for f in candidates[1:3]])}"

                return analysis

            else:
                if is_ar:
                    analysis = f"لم يتم تحديد مصدر واضح\n"
                    analysis += f"{'='*50}\n\n"
                    analysis += f"السبب: لا يُعرف أن أياً من المصانع القريبة ({len(factories)} مصنع) ينتج {gas_name}.\n\n"
                    analysis += f"الغاز المكتشف: {gas_name}\n"
                    analysis += f"المصانع القريبة: {', '.join([f.get('name', 'Unknown') for f in factories[:3]])}\n"
                    analysis += f"انبعاثاتها: {', '.join([', '.join(f.get('emissions', [])) for f in factories[:3]])}\n\n"
                    analysis += f"التفسيرات المحتملة:\n"
                    analysis += f"- مصدر خارج المنطقة المراقبة\n"
                    analysis += f"- مصادر متنقلة (مركبات، سفن)\n"
                    analysis += f"- قاعدة بيانات انبعاثات المصانع غير مكتملة\n"
                    analysis += f"- نقل بعيد المدى (الرياح: {wind_dir}، الثقة: {wind_confidence:.0f}%)"
                else:
                    analysis = f"NO CLEAR SOURCE IDENTIFIED\n"
                    analysis += f"{'='*50}\n\n"
                    analysis += f"REASON: None of the {len(factories)} nearby factories are known to produce {gas_name}.\n\n"
                    analysis += f"DETECTED GAS: {gas_name}\n"
                    analysis += f"NEARBY FACTORIES: {', '.join([f.get('name', 'Unknown') for f in factories[:3]])}\n"
                    analysis += f"THEIR EMISSIONS: {', '.join([', '.join(f.get('emissions', [])) for f in factories[:3]])}\n\n"
                    analysis += f"POSSIBLE EXPLANATIONS:\n"
                    analysis += f"- Source outside monitored area\n"
                    analysis += f"- Mobile sources (vehicles, ships)\n"
                    analysis += f"- Incomplete factory emission database\n"
                    analysis += f"- Long-range transport (wind: {wind_dir}, confidence: {wind_confidence:.0f}%)"

                return analysis
        except Exception as e:
            logger.error(f"Error in rule-based analysis: {e}")
            lang = get_current_language()
            if lang == 'ar':
                return f"خطأ في التحليل. يرجى المحاولة مرة أخرى."
            return f"Error in analysis. Please try again."

    @staticmethod
    def _haversine_distance(lat1: float, lon1: float,
                           lat2: float, lon2: float) -> float:
        """Calculate distance between two points (km)."""
        R = 6371
        
        lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
        c = 2 * np.arcsin(np.sqrt(a))
        
        return R * c
    
    @staticmethod
    def _calculate_bearing(lat1: float, lon1: float,
                          lat2: float, lon2: float) -> float:
        """Calculate bearing from point 1 to point 2 (degrees)."""
        lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])

        dlon = lon2 - lon1
        x = np.sin(dlon) * np.cos(lat2)
        y = np.cos(lat1) * np.sin(lat2) - np.sin(lat1) * np.cos(lat2) * np.cos(dlon)

        bearing = np.degrees(np.arctan2(x, y))
        return (bearing + 360) % 360

    @staticmethod
    def _get_direction_relative_to_hotspot(bearing: float) -> str:
        """Convert bearing to cardinal direction."""
        directions = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE',
                     'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']
        index = int((bearing + 11.25) / 22.5) % 16
        return directions[index]
