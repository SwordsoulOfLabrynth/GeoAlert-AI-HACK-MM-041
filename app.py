"""GeoAlert AI — Mawlamyine–Paung hackathon demonstration dashboard."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pydeck as pdk
import requests
import streamlit as st

ROOT = Path(__file__).resolve().parent
OUTPUTS = ROOT / "risk_map_outputs"

st.set_page_config(page_title="GeoAlert AI", page_icon="🌧️", layout="wide")


@st.cache_data
def load_json(filename: str):
    with open(OUTPUTS / filename, encoding="utf-8") as file:
        return json.load(file)


def telegram_is_configured() -> bool:
    try:
        return bool(st.secrets["TELEGRAM_BOT_TOKEN"]) and bool(st.secrets["TELEGRAM_CHAT_ID"])
    except Exception:
        return False


def send_telegram_alert(message: str):
    if not telegram_is_configured():
        return False, "Telegram is not configured."
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{st.secrets['TELEGRAM_BOT_TOKEN']}/sendMessage",
            data={"chat_id": st.secrets["TELEGRAM_CHAT_ID"], "text": message},
            timeout=15,
        )
        return response.ok, "Alert sent." if response.ok else "Telegram rejected the request."
    except requests.RequestException:
        return False, "Could not connect to Telegram."


required = [
    "impact_assessment_summary.json",
    "risk_model_metadata.json",
    "communications_access_points.json",
    "communications_access_summary.json",
    "road_based_route.json",
    "road_based_evacuation_route_map.png",
]
for filename in required:
    if not (OUTPUTS / filename).is_file():
        st.error(f"Missing required dashboard data: {filename}")
        st.stop()

impact = load_json("impact_assessment_summary.json")
meta = load_json("risk_model_metadata.json")
communications = load_json("communications_access_points.json")
communications_summary = load_json("communications_access_summary.json")
road_route = load_json("road_based_route.json")

st.markdown(
    """
    <style>
    .block-container {padding-top: 1.25rem; padding-bottom: 2.4rem; max-width: 1450px;}
    [data-testid="stMetric"] {background:#f8fbff;border:1px solid #dbe7f3;border-radius:15px;padding:14px;box-shadow:0 4px 14px rgba(23,65,104,.07);}
    [data-testid="stMetric"] * {color:#111827 !important;}
    .hero {padding:1.3rem 1.55rem;border-radius:20px;background:linear-gradient(110deg,#081f3a,#125a77 62%,#16726c);color:white;margin-bottom:1rem;box-shadow:0 9px 24px rgba(7,36,63,.20);}
    .hero h1 {margin:0;color:white;} .hero p {margin:.35rem 0 0;color:#dcecff;}
    .tag {display:inline-block;margin-top:.65rem;margin-right:.35rem;padding:.27rem .65rem;border-radius:999px;background:#dcecff;color:#0b2447;font-weight:700;font-size:.78rem;}
    .section-kicker {color:#14746f;font-weight:800;font-size:.78rem;letter-spacing:.08em;text-transform:uppercase;margin-bottom:.2rem;}
    .decision-card {background:linear-gradient(135deg,#f4fbff,#effaf6);border:1px solid #cde9e0;border-radius:16px;padding:1rem 1.1rem;margin:.35rem 0 .8rem;}
    .decision-card, .decision-card * {color:#12364a !important;}
    .decision-card h3 {margin:.1rem 0 .45rem;color:#0b4c6a !important;}
    .mini-label {color:#52616d;font-size:.82rem;font-weight:700;letter-spacing:.03em;text-transform:uppercase;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="hero">
      <h1>🌧️ GeoAlert AI</h1>
      <p>Flood, landslide and communications-access risk dashboard for the Mawlamyine–Paung corridor, Mon State.</p>
      <span class="tag">Explainable GeoAI</span><span class="tag">OSM road routing</span><span class="tag">Historical rainfall scenario</span>
    </div>
    """,
    unsafe_allow_html=True,
)

high_pop = impact["estimated_exposed_population"]["high"]
medium_pop = impact["estimated_exposed_population"]["medium"]
high_buildings = impact["estimated_buildings"]["high"]
high_comms_cells = communications_summary["classes"]["High"]

metrics = st.columns(4)
metrics[0].metric("High-risk population", f"{high_pop:,}", help="Estimated scenario exposure")
metrics[1].metric("High-risk buildings", f"{high_buildings:,}")
metrics[2].metric("High communications-priority cells", f"{high_comms_cells:,}")
metrics[3].metric("Risk-map resolution", f"~{meta['output_resolution_approx_m']} m")

overview_tab, risk_tab, comms_tab, route_tab, alert_tab, methods_tab = st.tabs(
    ["Overview", "Risk explorer", "Communications access", "Safer route", "Alert", "Methods & sources"]
)

with overview_tab:
    st.markdown('<div class="section-kicker">Situation summary</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="decision-card"><h3>What GeoAlert AI helps a response team decide</h3>'
        '<b>1. Where is risk highest?</b> Use flood and landslide layers to focus assessment and alerts.<br>'
        '<b>2. Where should communications readiness be prioritised?</b> Combine hazard, population exposure and corridor isolation.<br>'
        '<b>3. Which road route should be reviewed?</b> Use OSM road routing with a higher cost for high-hazard segments.</div>',
        unsafe_allow_html=True,
    )
    left, right = st.columns([1.25, 1])
    with left:
        st.subheader("Combined hazard decision view")
        st.image(OUTPUTS / "combined_hazard_map.png", width="stretch")
    with right:
        st.subheader("What the prototype answers")
        st.markdown(
            """
            1. **Where** are flood and landslide risk zones?
            2. **Who and what** may be exposed—population and buildings?
            3. **Where should communications readiness be prioritised** when hazard and access risk rise?
            """
        )
        st.warning("Scenario prototype only. It is not a validated real-time forecast, official evacuation order, or cell-tower failure prediction.")
        st.subheader("Estimated exposure")
        exposure = pd.DataFrame(
            {
                "Risk class": ["Low", "Medium", "High"],
                "Population estimate": [
                    impact["estimated_exposed_population"]["low"],
                    medium_pop,
                    high_pop,
                ],
                "Buildings": [
                    impact["estimated_buildings"]["low"],
                    impact["estimated_buildings"]["medium"],
                    high_buildings,
                ],
            }
        )
        st.dataframe(exposure, hide_index=True, width="stretch")

with risk_tab:
    st.subheader("Flood and landslide risk explorer")
    selected = st.radio(
        "Choose a risk layer",
        ["Combined hazard", "Flood risk", "Landslide risk"],
        horizontal=True,
    )
    map_files = {
        "Combined hazard": "combined_hazard_map.png",
        "Flood risk": "flood_risk_map.png",
        "Landslide risk": "landslide_risk_map.png",
    }
    st.image(
        OUTPUTS / map_files[selected],
        caption=f"{selected} — {meta['rainfall_scenario']}",
        width="stretch",
    )
    class_focus = st.selectbox(
        "What should the response team do?",
        ["High risk — assess and alert", "Medium risk — monitor and prepare", "Low risk — maintain awareness"],
    )
    response_guidance = {
        "High risk — assess and alert": "Prioritise field verification, warning communication and contingency planning in red zones.",
        "Medium risk — monitor and prepare": "Prepare response assets and monitor rainfall and local reports in amber zones.",
        "Low risk — maintain awareness": "Maintain situational awareness; low risk in this scenario does not mean zero risk.",
    }
    st.info(response_guidance[class_focus])
    st.caption("Green = low, amber = medium, red = high. Classes are relative to the defined historical scenario.")

with comms_tab:
    st.subheader("Communications-access vulnerability")
    st.write("This interactive layer identifies places where communications readiness should be prioritised when high hazard, exposed population and isolation from the supplied main corridor occur together.")
    st.info(communications_summary["interpretation"])
    filter_left, filter_right = st.columns(2)
    with filter_left:
        selected_priority = st.multiselect(
            "Show priority classes",
            ["High", "Medium", "Low"],
            default=["High", "Medium", "Low"],
        )
    with filter_right:
        population_floor = st.slider(
            "Minimum estimated population per map cell",
            min_value=0,
            max_value=1000,
            value=0,
            step=50,
        )
    colors = {1: [82, 168, 104, 145], 2: [240, 173, 78, 165], 3: [217, 83, 79, 195]}
    point_data = []
    for point in communications["points"]:
        record = dict(point)
        record["color"] = colors[record["communications_access_class"]]
        record["priority"] = {1: "Low", 2: "Medium", 3: "High"}[record["communications_access_class"]]
        if record["priority"] in selected_priority and record["population_estimate"] >= population_floor:
            point_data.append(record)
    st.caption(f"Showing {len(point_data):,} of {len(communications['points']):,} communications-priority map cells.")
    deck = pdk.Deck(
        layers=[
            pdk.Layer(
                "ScatterplotLayer",
                data=point_data,
                get_position="position",
                get_fill_color="color",
                get_radius=240,
                radius_min_pixels=3,
                radius_max_pixels=8,
                pickable=True,
                opacity=0.78,
            )
        ],
        initial_view_state=pdk.ViewState(latitude=16.64, longitude=97.50, zoom=9.6, pitch=0),
        map_style=None,
        tooltip={
            "text": "Communications priority: {priority}\nHazard class: {hazard_class}\nPopulation estimate: {population_estimate}\nDistance to main corridor: {road_distance_m} m"
        },
    )
    st.pydeck_chart(deck, width="stretch")
    st.caption("Green = low, amber = medium, red = high communications-access priority. Hover over a point to inspect the proxy inputs.")
    comms_table = pd.DataFrame(
        [{"Priority": key, "Map cells": value} for key, value in communications_summary["classes"].items()]
    )
    st.bar_chart(comms_table.set_index("Priority"))

with route_tab:
    st.subheader("Road-based evacuation-route prototype")
    route_left, route_right = st.columns([1.25, 1])
    with route_left:
        st.image(
            OUTPUTS / "road_based_evacuation_route_map.png",
            caption="Risk-weighted route follows downloaded OpenStreetMap road geometry",
            width="stretch",
        )
    with route_right:
        selected_route = road_route["selected_route"]
        st.markdown("**Route risk summary**")
        route_metrics = st.columns(2)
        route_metrics[0].metric("Route length", f"{selected_route['distance_km']} km")
        route_metrics[1].metric("High-hazard road", f"{selected_route['high_hazard_km']} km")
        st.markdown(
            f"- **Medium-hazard road:** {selected_route['medium_hazard_km']} km\n"
            "- **Green line:** risk-weighted route on OSM road geometry\n"
            "- **Circle / star:** illustrative origin and destination"
        )
        st.info(road_route["interpretation"])
        st.caption(f"Method: {road_route['method']}")
        with st.expander("Why is this route useful?"):
            st.write("A normal map shows the shortest road. GeoAlert adds a hazard penalty to every road segment, so a lower-risk road can be selected whenever the OSM road network provides one.")
        st.warning("This is road-network routing, but it is still a prototype. Verify road closures, official advice and local conditions before travel.")

with alert_tab:
    st.subheader("GeoAlert notification")
    message = f"""🚨 GEOALERT AI — HIGH-RISK SCENARIO

📍 Mawlamyine–Paung corridor, Mon State
⚠️ Estimated high-risk population: {high_pop:,}
🏠 Estimated high-risk buildings: {high_buildings:,}

🌧️ Heavy rainfall may increase flood and landslide risk.
Recommended action: monitor official local warnings and avoid hazardous areas.

⚠️ Prototype scenario alert — not a live emergency notification."""
    st.error(message)
    st.image(ROOT / "telegram_alert_mockup.png", caption="Telegram notification mock-up", width=420)
    configured = telegram_is_configured()
    if not configured:
        st.caption("Telegram sending is disabled in this safe submission package. Add a newly generated token locally only if you want a live demo.")
    if st.button("Send Telegram test alert", type="primary", disabled=not configured):
        sent, result = send_telegram_alert(message)
        (st.success if sent else st.error)(result)

with methods_tab:
    st.subheader("Model method")
    st.markdown(
        """
        - **Flood risk:** 45% rainfall + 35% inverse elevation + 20% waterway proximity
        - **Landslide risk:** 60% slope + 40% rainfall
        - **Communications-access proxy:** 55% combined hazard + 30% population exposure + 15% isolation from the supplied main corridor
        - **Road-route prototype:** OSM road geometry + Dijkstra routing; high-hazard road segments receive a higher routing cost
        """
    )
    st.write(f"**Scenario:** {meta['rainfall_scenario']}")
    st.write(f"**Risk-map resolution:** approximately {meta['output_resolution_approx_m']} m")
    st.caption("Data and attribution details are in DATA_SOURCES.md. This prototype supports situational awareness; it does not replace emergency authorities or field validation.")
    with st.expander("Technical metadata"):
        st.json(meta)
