# GeoAlert AI

**Telecom Network Resilience for Flood & Landslide Early Warning**

GeoAlert AI is an explainable GeoAI decision-support dashboard for the Mawlamyine–Paung corridor, Mon State, Myanmar. It combines terrain, historical rainfall, roads, buildings and population data to map flood and landslide risk, estimate exposure, prioritize communications-access vulnerability, and provide a risk-aware road-route illustration.

## What the prototype provides

- Flood and landslide risk maps for a CHIRPS August 2025 historical rainfall scenario
- Estimated high-risk population and building exposure
- Communications-priority cells based on a transparent access-vulnerability proxy
- Risk-weighted OpenStreetMap road routing using NetworkX Dijkstra routing
- Streamlit dashboard with optional local Telegram test alert

## Technology

QGIS and QuickOSM; Python, Pandas and NumPy; Streamlit and PyDeck; OpenStreetMap road geometry; NetworkX Dijkstra routing.

## Run locally

```powershell
pip install -r requirements.txt
streamlit run app.py
```

## Optional Telegram demo

Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`, then add a newly generated bot token and your chat ID. Never commit or submit `secrets.toml`.

## Important limitations

This is a scenario-based decision-support prototype, not a live forecast, certified evacuation instruction, mobile coverage measurement, or individual tower-outage prediction. The communications layer is an access-vulnerability prioritization proxy. See [DATA_SOURCES.md](DATA_SOURCES.md) for sources and limitations.

## Team

**Sky Strikers** — HACK-MM-041, Myanmar

- Kyaw Zay Ya Hein — Project Lead & Presenter
- Phyo Myat Htoo Sint — Data & GIS
- Win Pa Pa Phyo — Prototype & UI
