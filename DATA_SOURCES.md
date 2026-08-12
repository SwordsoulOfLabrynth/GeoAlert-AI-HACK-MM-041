# GeoAlert AI data and prototype limits

## Data layers

- Study-area boundary: MIMU Myanmar Township Boundaries.
- Elevation and slope: NASA SRTM 30 m DEM, clipped to Mawlamyine–Paung.
- Rainfall scenario: CHIRPS v2.0 monthly precipitation, August 2025.
- Population exposure: WorldPop/HDX Myanmar 2020 gridded population estimate.
- Buildings, main corridor and waterways: OpenStreetMap-derived data.

## Output interpretation

- Flood risk = 45% rainfall + 35% inverse elevation + 20% waterway proximity.
- Landslide risk = 60% slope + 40% rainfall.
- Communications-access vulnerability = 55% combined hazard + 30% population exposure + 15% isolation from the supplied main corridor.

The communications layer is a prioritisation proxy. It does **not** measure mobile coverage, identify an individual tower, or predict a tower outage. The route panel uses downloaded OpenStreetMap road geometry and Dijkstra routing. Road distance receives a risk multiplier of low=1, medium=2, high=5, so the route optimiser avoids high-hazard road segments where an OSM alternative exists. It does not include live closures, traffic, one-way restrictions, verified shelters, or official evacuation instructions.

## Attribution links

- MIMU: https://data.humdata.org/dataset/mimu-geonode-myanmar-township-boundaries-mimu
- CHIRPS: https://data.chc.ucsb.edu/products/CHIRPS-2.0/global_monthly/tifs/
- WorldPop: https://hub.worldpop.org/doi/10.5258/SOTON/WP00181
- OpenStreetMap: https://www.openstreetmap.org/copyright

Road-network data was downloaded from the OpenStreetMap API on 2026-08-11. © OpenStreetMap contributors, available under the Open Database License (ODbL).
