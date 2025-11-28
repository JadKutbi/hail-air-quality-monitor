"""Dashboard components for air quality monitoring UI."""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from typing import Dict, List
import pytz
from datetime import datetime
import config
from translations import get_text
from benchmark_analyzer import CityBenchmarkAnalyzer


def t(key: str) -> str:
    """Get translated text for current language."""
    return get_text(key, st.session_state.get('language', 'en'))


def get_aqi_category_translated(category: str) -> str:
    """Translate AQI category name."""
    category_map = {
        'Good': 'aqi_good',
        'Moderate': 'aqi_moderate',
        'Unhealthy for Sensitive': 'aqi_unhealthy_sensitive',
        'Unhealthy': 'aqi_unhealthy',
        'Very Unhealthy': 'aqi_very_unhealthy',
        'Hazardous': 'aqi_hazardous'
    }
    key = category_map.get(category, 'unknown')
    return t(key)


def create_aqi_dashboard(pollution_data: Dict, validator) -> None:
    """Create AQI dashboard with gauge and breakdown charts."""
    st.subheader(f"🌡️ {t('aqi_dashboard')}")

    aqi_data = []
    for gas, data in pollution_data.items():
        if data.get('success'):
            aqi_info = validator.calculate_aqi(gas, data['statistics']['max'])
            if aqi_info['aqi']:
                aqi_data.append({
                    'Gas': gas,
                    'AQI': aqi_info['aqi'],
                    'Category': aqi_info['category'],
                    'CategoryTranslated': get_aqi_category_translated(aqi_info['category']),
                    'Color': aqi_info['color']
                })

    if aqi_data:
        max_aqi = max(aqi_data, key=lambda x: x['AQI'])

        col1, col2, col3 = st.columns([2, 3, 2])
        with col1:
            fig = go.Figure(go.Indicator(
                mode="gauge+number",
                value=max_aqi['AQI'],
                domain={'x': [0, 1], 'y': [0, 1]},
                title={'text': t('overall_aqi')},
                gauge={
                    'axis': {'range': [None, 500]},
                    'bar': {'color': max_aqi['Color']},
                    'steps': [
                        {'range': [0, 50], 'color': "#E8F5E9"},
                        {'range': [50, 100], 'color': "#FFF9C4"},
                        {'range': [100, 150], 'color': "#FFE0B2"},
                        {'range': [150, 200], 'color': "#FFCCBC"},
                        {'range': [200, 300], 'color': "#E1BEE7"},
                        {'range': [300, 500], 'color': "#FFCDD2"}
                    ],
                    'threshold': {
                        'line': {'color': "red", 'width': 4},
                        'thickness': 0.75,
                        'value': 150
                    }
                }
            ))
            fig.update_layout(height=250, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.metric(t('air_quality_status'), max_aqi['CategoryTranslated'])
            st.markdown(f"**{t('dominant_pollutant')}:** {max_aqi['Gas']}")

            df_aqi = pd.DataFrame(aqi_data)
            fig_bar = px.bar(df_aqi, x='Gas', y='AQI', color='CategoryTranslated',
                            color_discrete_map={
                                t('aqi_good'): '#00E400',
                                t('aqi_moderate'): '#FFFF00',
                                t('aqi_unhealthy_sensitive'): '#FF7E00',
                                t('aqi_unhealthy'): '#FF0000',
                                t('aqi_very_unhealthy'): '#8F3F97',
                                t('aqi_hazardous'): '#7E0023',
                                # Fallback for English categories
                                'Good': '#00E400',
                                'Moderate': '#FFFF00',
                                'Unhealthy for Sensitive': '#FF7E00',
                                'Unhealthy': '#FF0000',
                                'Very Unhealthy': '#8F3F97',
                                'Hazardous': '#7E0023'
                            },
                            title=t('aqi_by_pollutant'))
            fig_bar.update_layout(height=200, showlegend=False)
            st.plotly_chart(fig_bar, use_container_width=True)

        with col3:
            st.info(f"**{t('health_advice')}:**")
            aqi_info = validator.calculate_aqi(max_aqi['Gas'],
                                              pollution_data[max_aqi['Gas']]['statistics']['max'])
            st.write(aqi_info['health_implications'])

def create_health_risk_panel(pollution_data: Dict, validator) -> None:
    """Create health risk panel with risk scores and recommendations."""
    st.subheader(f"🏥 {t('health_risk_assessment')}")

    risk_info = validator.calculate_health_risk_index(pollution_data)

    col1, col2, col3 = st.columns([1, 2, 2])

    with col1:
        # Risk level indicator
        st.markdown(f"""
        <div style="text-align: center; padding: 20px; background-color: {risk_info['color']}20;
                    border: 2px solid {risk_info['color']}; border-radius: 10px;">
            <h2 style="color: {risk_info['color']}; margin: 0;">{risk_info['risk_level']}</h2>
            <p style="margin: 5px 0;">{t('risk_score')}: {risk_info['overall_risk']:.0f}/100</p>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        if risk_info['gas_risks']:
            risk_df = pd.DataFrame([
                {t('pollutant'): gas, t('risk_score'): score}
                for gas, score in risk_info['gas_risks'].items()
            ])
            fig = px.bar(risk_df, x=t('risk_score'), y=t('pollutant'), orientation='h',
                        color=t('risk_score'), color_continuous_scale='RdYlGn_r',
                        title=t('risk_by_pollutant'))
            fig.update_layout(height=200, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

    with col3:
        st.markdown(f"**📋 {t('recommendations')}:**")
        for rec in risk_info['recommendations']:
            st.write(f"• {rec}")

def create_data_quality_panel(pollution_data: Dict, validator) -> None:
    """Create data quality heatmap and metrics."""
    st.subheader(f"📊 {t('data_quality')}")

    quality_scores = {}
    for gas, data in pollution_data.items():
        if data.get('success'):
            quality_scores[gas] = validator.calculate_data_quality_score(data)

    if quality_scores:
        quality_df = pd.DataFrame([
            {
                'Gas': gas,
                'Overall': scores['overall'],
                'Spatial': scores['spatial_coverage'],
                'Temporal': scores['temporal_accuracy'],
                'Validity': scores['measurement_validity'],
                'Wind Sync': scores['wind_sync_quality'],
                'Status': scores['label']
            }
            for gas, scores in quality_scores.items()
        ])

        # Display quality heatmap
        fig = go.Figure(data=go.Heatmap(
            z=quality_df[['Spatial', 'Temporal', 'Validity', 'Wind Sync']].values,
            x=[t('spatial_coverage'), t('temporal_accuracy'), t('measurement_validity'), t('wind_sync')],
            y=quality_df['Gas'].values,
            colorscale='RdYlGn',
            text=quality_df[['Spatial', 'Temporal', 'Validity', 'Wind Sync']].values,
            texttemplate='%{text:.0f}',
            textfont={"size": 10},
            colorbar=dict(title=t('quality_score'))
        ))

        fig.update_layout(
            title=t('data_quality_matrix'),
            height=200 + len(quality_scores) * 30,
            xaxis_title=t('quality_metric'),
            yaxis_title=t('pollutant')
        )

        st.plotly_chart(fig, use_container_width=True)

        avg_quality = quality_df['Overall'].mean()
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(t('average_quality'), f"{avg_quality:.0f}%")
        with col2:
            best_quality = quality_df.loc[quality_df['Overall'].idxmax()]
            st.metric(t('best_quality'), f"{best_quality['Gas']}: {best_quality['Overall']:.0f}%")
        with col3:
            worst_quality = quality_df.loc[quality_df['Overall'].idxmin()]
            st.metric(t('needs_attention'), f"{worst_quality['Gas']}: {worst_quality['Overall']:.0f}%")
        with col4:
            high_quality_count = len(quality_df[quality_df['Overall'] >= 80])
            st.metric(t('high_quality'), f"{high_quality_count}/{len(quality_df)} {t('gases')}")

def create_insights_panel(pollution_data: Dict, city: str, validator) -> None:
    """Create insights panel with patterns and correlations."""
    st.subheader(f"💡 {t('intelligent_insights')}")

    insights = validator.generate_data_insights(pollution_data, city)

    if insights:
        cols = st.columns(2)
        for i, insight in enumerate(insights):
            with cols[i % 2]:
                st.info(insight)
    else:
        st.info(t('no_patterns_detected'))

    with st.expander(f"📈 {t('detailed_trend_analysis')}"):
        st.write(f"**{t('pollutant_correlations')}:**")

        correlation_data = []
        gases = list(pollution_data.keys())
        for i, gas1 in enumerate(gases):
            for gas2 in gases[i+1:]:
                if pollution_data[gas1].get('success') and pollution_data[gas2].get('success'):
                    # Simple correlation based on violation status
                    thresh1 = config.GAS_THRESHOLDS.get(gas1, {}).get('column_threshold', float('inf'))
                    thresh2 = config.GAS_THRESHOLDS.get(gas2, {}).get('column_threshold', float('inf'))

                    viol1 = pollution_data[gas1]['statistics']['max'] > thresh1
                    viol2 = pollution_data[gas2]['statistics']['max'] > thresh2

                    if viol1 and viol2:
                        correlation_data.append(f"• {gas1} & {gas2} {t('both_elevated')}")

        if correlation_data:
            for corr in correlation_data:
                st.write(corr)
        else:
            st.write(t('no_correlations_detected'))

def create_historical_comparison(pollution_data: Dict) -> None:
    """Create WHO standards comparison chart."""
    st.subheader(f"📊 {t('who_compliance')}")

    comparison_data = []
    for gas, data in pollution_data.items():
        if data.get('success'):
            threshold = config.GAS_THRESHOLDS.get(gas, {}).get('column_threshold', 100)
            max_val = data['statistics']['max']
            mean_val = data['statistics']['mean']

            # Calculate compliance percentage
            max_compliance = (max_val / threshold * 100) if threshold > 0 else 0
            mean_compliance = (mean_val / threshold * 100) if threshold > 0 else 0

            comparison_data.append({
                'Gas': gas,
                t('peak_level'): max_val,
                t('average_level'): mean_val,
                t('who_guideline'): threshold,
                t('peak_percent_limit'): max_compliance,
                t('status'): f"🔴 {t('violation')}" if max_val > threshold else f"🟢 {t('compliant')}"
            })

    if comparison_data:
        df = pd.DataFrame(comparison_data)

        fig = go.Figure()

        fig.add_trace(go.Bar(
            name=t('peak_concentration'),
            x=df['Gas'],
            y=df[t('peak_level')],
            marker_color='#ef4444',
            text=df[t('peak_percent_limit')].round(0),
            texttemplate='%{text}%',
            textposition='outside'
        ))
        fig.add_trace(go.Bar(
            name=t('spatial_average'),
            x=df['Gas'],
            y=df[t('average_level')],
            marker_color='#3b82f6'
        ))
        fig.add_trace(go.Scatter(
            name=t('who_guideline'),
            x=df['Gas'],
            y=df[t('who_guideline')],
            mode='lines+markers',
            marker=dict(color='#22c55e', size=12, symbol='line-ew'),
            line=dict(color='#22c55e', width=3, dash='dash')
        ))

        fig.update_layout(
            title=t('current_vs_who'),
            barmode='group',
            height=350,
            xaxis_title=t('pollutant_gas'),
            yaxis_title=t('concentration'),
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )

        st.plotly_chart(fig, use_container_width=True)

        violations = df[df[t('status')].str.contains(t('violation'))]
        if len(violations) > 0:
            st.warning(f"⚠️ **{len(violations)} {t('pollutants_exceeding')}**: {', '.join(violations['Gas'].tolist())}")
        else:
            st.success(f"✅ {t('all_within_guidelines')}")


def get_category_translation(category: str, lang: str = 'en') -> str:
    """Translate pollution category name."""
    category_map = {
        'cleanest': 'category_cleanest',
        'clean': 'category_clean',
        'moderate': 'category_moderate',
        'polluted': 'category_polluted',
        'heavily_polluted': 'category_heavily_polluted',
        'unknown': 'category_unknown'
    }
    key = category_map.get(category, 'category_unknown')
    return get_text(key, lang)


def create_benchmark_summary(summary_stats: Dict, lang: str = 'en') -> None:
    """Create benchmark summary metrics."""
    st.subheader(f"📊 {get_text('benchmark_summary', lang)}")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            get_text('cities_monitored', lang),
            f"{summary_stats['cities_with_data']}/{summary_stats['total_cities']}"
        )

    with col2:
        cleanest = summary_stats.get('cleanest_city')
        if cleanest:
            st.metric(
                get_text('cleanest_city', lang),
                get_text(cleanest['city'], lang),
                f"{cleanest['pollution_index']:.1f}%"
            )
        else:
            st.metric(get_text('cleanest_city', lang), "—")

    with col3:
        most_polluted = summary_stats.get('most_polluted_city')
        if most_polluted:
            st.metric(
                get_text('most_polluted_city', lang),
                get_text(most_polluted['city'], lang),
                f"{most_polluted['pollution_index']:.1f}%",
                delta_color="inverse"
            )
        else:
            st.metric(get_text('most_polluted_city', lang), "—")

    with col4:
        st.metric(
            get_text('cities_with_violations', lang),
            summary_stats.get('cities_with_violations', 0),
            f"{summary_stats.get('total_violations', 0)} {get_text('violations', lang)}"
        )


def create_city_rankings_table(rankings: List[Dict], lang: str = 'en') -> None:
    """Create city rankings table with styling."""
    st.subheader(f"🏆 {get_text('city_rankings_table', lang)}")

    table_data = []
    for city_data in rankings:
        if city_data['has_data']:
            # Show historical violations only (current scan violations are auto-recorded to history)
            historical = city_data.get('violation_count', 0)
            row = {
                get_text('rank', lang): city_data['rank'],
                get_text('city', lang): get_text(city_data['city'], lang),
                get_text('region', lang): get_text(city_data['region'], lang),
                get_text('pollution_index', lang): f"{city_data['live_score']:.1f}%",  # Show raw satellite %
                get_text('category', lang): get_category_translation(city_data['category'], lang),
                get_text('violations_count', lang): historical,
            }
            table_data.append(row)

    if table_data:
        df = pd.DataFrame(table_data)

        def color_pollution_index(val):
            try:
                num = float(val.replace('%', ''))
                if num < 25:
                    return 'background-color: #d1fae5; color: #065f46'
                elif num < 50:
                    return 'background-color: #dcfce7; color: #166534'
                elif num < 75:
                    return 'background-color: #fef3c7; color: #92400e'
                elif num < 100:
                    return 'background-color: #fee2e2; color: #991b1b'
                else:
                    return 'background-color: #fecaca; color: #7f1d1d'
            except (ValueError, AttributeError, TypeError):
                return ''

        styled_df = df.style.map(
            color_pollution_index,
            subset=[get_text('pollution_index', lang)]
        )

        st.dataframe(styled_df, use_container_width=True, hide_index=True)
    else:
        st.info(get_text('no_benchmark_data', lang))


def create_city_rankings_chart(rankings: List[Dict], lang: str = 'en') -> None:
    """Create horizontal bar chart of city rankings."""
    cities_with_data = [c for c in rankings if c['has_data']]

    if not cities_with_data:
        return

    cities = [get_text(c['city'], lang) for c in cities_with_data]
    indices = [c['pollution_index'] for c in cities_with_data]
    colors = [c['category_info'].get('color', '#6b7280') for c in cities_with_data]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        y=cities,
        x=indices,
        orientation='h',
        marker_color=colors,
        text=[f"{idx:.1f}%" for idx in indices],
        textposition='outside',
        hovertemplate='<b>%{y}</b><br>' +
                     f'{get_text("pollution_index", lang)}: %{{x:.1f}}%<extra></extra>'
    ))

    fig.add_vline(x=100, line_dash="dash", line_color="red",
                  annotation_text=get_text('threshold', lang))

    fig.update_layout(
        title=get_text('city_rankings_table', lang),
        xaxis_title=get_text('pollution_index', lang) + " (% " + get_text('of_threshold', lang) + ")",
        yaxis_title=get_text('city', lang),
        height=max(400, len(cities_with_data) * 35),
        showlegend=False,
        yaxis={'categoryorder': 'total ascending'}
    )

    st.plotly_chart(fig, use_container_width=True)


def create_regional_comparison(regional_stats: Dict[str, Dict], lang: str = 'en') -> None:
    """Create regional pollution and violation charts."""
    st.subheader(f"🗺️ {get_text('regional_comparison', lang)}")

    col1, col2 = st.columns(2)

    regions_with_data = {k: v for k, v in regional_stats.items()
                        if v.get('avg_pollution_index') is not None}

    if not regions_with_data:
        st.info(get_text('no_benchmark_data', lang))
        return

    with col1:
        regions = [get_text(r, lang) for r in regions_with_data.keys()]
        avg_indices = [v['avg_pollution_index'] for v in regions_with_data.values()]

        colors = []
        for idx in avg_indices:
            if idx < 25:
                colors.append('#10b981')
            elif idx < 50:
                colors.append('#22c55e')
            elif idx < 75:
                colors.append('#f59e0b')
            elif idx < 100:
                colors.append('#ef4444')
            else:
                colors.append('#dc2626')

        fig_avg = go.Figure(go.Bar(
            x=regions,
            y=avg_indices,
            marker_color=colors,
            text=[f"{idx:.1f}%" for idx in avg_indices],
            textposition='outside'
        ))

        fig_avg.add_hline(y=100, line_dash="dash", line_color="red")

        fig_avg.update_layout(
            title=get_text('regional_avg_pollution', lang),
            xaxis_title=get_text('region', lang),
            yaxis_title=get_text('pollution_index', lang),
            height=350
        )

        st.plotly_chart(fig_avg, use_container_width=True)

    with col2:
        violations = [v['total_violations'] for v in regions_with_data.values()]

        fig_viol = go.Figure(go.Bar(
            x=regions,
            y=violations,
            marker_color='#ef4444',
            text=violations,
            textposition='outside'
        ))

        fig_viol.update_layout(
            title=get_text('regional_violations', lang),
            xaxis_title=get_text('region', lang),
            yaxis_title=get_text('violations_count', lang),
            height=350
        )

        st.plotly_chart(fig_viol, use_container_width=True)


def create_category_distribution(rankings: List[Dict], lang: str = 'en') -> None:
    """Create pollution category distribution pie chart."""
    cities_with_data = [c for c in rankings if c['has_data']]

    if not cities_with_data:
        return

    category_counts = {}
    category_colors = {}
    for city in cities_with_data:
        cat = city['category']
        cat_label = get_category_translation(cat, lang)
        category_counts[cat_label] = category_counts.get(cat_label, 0) + 1
        category_colors[cat_label] = city['category_info'].get('color', '#6b7280')

    labels = list(category_counts.keys())
    values = list(category_counts.values())
    colors = [category_colors.get(l, '#6b7280') for l in labels]

    fig = go.Figure(go.Pie(
        labels=labels,
        values=values,
        marker_colors=colors,
        textinfo='label+value',
        texttemplate='%{label}<br>%{value} ' + get_text('cities_in_category', lang).split()[0],
        hole=0.4
    ))

    fig.update_layout(
        title=get_text('pollution_distribution', lang),
        height=350,
        showlegend=True
    )

    st.plotly_chart(fig, use_container_width=True)


def create_gas_specific_ranking(gas_rankings: List[Dict], gas: str, lang: str = 'en') -> None:
    """Create ranking chart for specific gas type."""
    cities_with_data = [c for c in gas_rankings if c['has_data']]

    if not cities_with_data:
        st.info(get_text('no_benchmark_data', lang))
        return

    cities = [get_text(c['city'], lang) for c in cities_with_data]
    threshold_percents = [c['threshold_percent'] for c in cities_with_data]

    colors = ['#ef4444' if c['is_violation'] else '#22c55e' for c in cities_with_data]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        y=cities,
        x=threshold_percents,
        orientation='h',
        marker_color=colors,
        text=[f"{p:.1f}%" for p in threshold_percents],
        textposition='outside'
    ))

    fig.add_vline(x=100, line_dash="dash", line_color="red",
                  annotation_text=get_text('threshold', lang))

    fig.update_layout(
        title=get_text('gas_ranking_for', lang).format(gas=get_text(gas, lang)),
        xaxis_title=get_text('threshold_percent', lang),
        yaxis_title=get_text('city', lang),
        height=max(400, len(cities_with_data) * 35),
        showlegend=False,
        yaxis={'categoryorder': 'total ascending'}
    )

    st.plotly_chart(fig, use_container_width=True)


def create_city_comparison(comparison_result: Dict, lang: str = 'en') -> None:
    """Create side-by-side city comparison view."""
    city1 = comparison_result['city1']
    city2 = comparison_result['city2']

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"### {get_text(city1['name'], lang)}")
        st.metric(
            get_text('pollution_index', lang),
            f"{city1['pollution_index']:.1f}%" if city1['pollution_index'] else "—"
        )
        st.metric(
            get_text('category', lang),
            get_category_translation(city1['category'], lang)
        )
        st.metric(
            get_text('violations_count', lang),
            city1['violations']
        )

    with col2:
        st.markdown(f"### {get_text(city2['name'], lang)}")
        st.metric(
            get_text('pollution_index', lang),
            f"{city2['pollution_index']:.1f}%" if city2['pollution_index'] else "—"
        )
        st.metric(
            get_text('category', lang),
            get_category_translation(city2['category'], lang)
        )
        st.metric(
            get_text('violations_count', lang),
            city2['violations']
        )

    st.divider()
    if comparison_result['overall_cleaner'] not in ['equal', 'insufficient_data']:
        cleaner_city = comparison_result['overall_cleaner']
        diff = comparison_result['difference_percent']
        st.success(f"🏆 **{get_text(cleaner_city, lang)}** {get_text('cleaner_by', lang)} **{diff:.1f}%**")
    elif comparison_result['overall_cleaner'] == 'equal':
        st.info(f"⚖️ {get_text('comparison_result', lang)}: {get_text('equal_pollution', lang)}")
    else:
        st.warning(f"⚠️ {get_text('insufficient_data_comparison', lang)}")

    if comparison_result.get('gas_comparisons'):
        st.subheader(get_text('gas_breakdown', lang))

        comparison_data = []
        for gas, comp in comparison_result['gas_comparisons'].items():
            comparison_data.append({
                'Gas': get_text(gas, lang),
                get_text(city1['name'], lang): f"{comp['city1_percent']:.1f}%",
                get_text(city2['name'], lang): f"{comp['city2_percent']:.1f}%",
                get_text('cleanest_city', lang): get_text(comp['cleaner_city'], lang) if comp['cleaner_city'] != 'equal' else '='
            })

        if comparison_data:
            df = pd.DataFrame(comparison_data)
            st.dataframe(df, use_container_width=True, hide_index=True)