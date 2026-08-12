"""Generate an honest communications-access vulnerability proxy for the demo.

It deliberately does not claim cell-tower outage prediction.  It combines the
hazard class, population exposure, and isolation from the supplied main road.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import tifffile
from scipy.spatial import cKDTree


ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "risk_map_outputs"
REFERENCE = ROOT / "reference_data"


def read_raster(path: Path):
    with tifffile.TiffFile(path) as tif:
        page = tif.pages[0]
        data = tif.asarray()
        scale = page.tags[33550].value
        tie = page.tags[33922].value
    if data.ndim == 3:
        data = data[:, :, 0]
    return data, float(scale[0]), float(scale[1]), float(tie[3]), float(tie[4])


def collect_vertices(value):
    if isinstance(value, (list, tuple)) and len(value) >= 2 and all(isinstance(v, (int, float)) for v in value[:2]):
        return [[float(value[0]), float(value[1])]]
    vertices = []
    for item in value:
        vertices.extend(collect_vertices(item))
    return vertices


def main():
    hazard, h_x, h_y, h_left, h_top = read_raster(OUTPUTS / "combined_hazard_class.tif")
    population, p_x, p_y, p_left, p_top = read_raster(REFERENCE / "population_2020_estimate.tif")
    road_data = json.loads((REFERENCE / "main_corridor.geojson").read_text(encoding="utf-8"))
    road_vertices = np.asarray(
        collect_vertices(road_data["features"][0]["geometry"]["coordinates"]), dtype=np.float32
    )

    lat_scale = 111_320.0
    lon_scale = lat_scale * math.cos(math.radians(h_top - hazard.shape[0] * h_y / 2))
    road_tree = cKDTree(np.column_stack((road_vertices[:, 0] * lon_scale, road_vertices[:, 1] * lat_scale)))

    # About 500 m spacing makes an interactive browser layer fast enough for a demo.
    rows, cols = np.indices(hazard.shape)
    sample = (rows % 4 == 0) & (cols % 4 == 0) & (hazard > 0)
    sample_rows = rows[sample]
    sample_cols = cols[sample]
    lons = h_left + sample_cols * h_x
    lats = h_top - sample_rows * h_y
    p_cols = np.clip(np.rint((lons - p_left) / p_x).astype(int), 0, population.shape[1] - 1)
    p_rows = np.clip(np.rint((p_top - lats) / p_y).astype(int), 0, population.shape[0] - 1)
    population_values = population[p_rows, p_cols].astype(np.float32)
    p95 = float(np.percentile(population_values, 95))
    population_score = np.clip(population_values / max(p95, 1.0), 0, 1)
    road_distance, _ = road_tree.query(np.column_stack((lons * lon_scale, lats * lat_scale)))
    isolation_score = np.clip(road_distance / 5000.0, 0, 1)
    hazard_score = (hazard[sample].astype(np.float32) - 1.0) / 2.0
    comm_score = 0.55 * hazard_score + 0.30 * population_score + 0.15 * isolation_score
    comm_class = np.select([comm_score < 0.35, comm_score < 0.66], [1, 2], default=3).astype(int)

    points = []
    for lon, lat, hazard_class, pop, road_m, score, klass in zip(
        lons, lats, hazard[sample], population_values, road_distance, comm_score, comm_class
    ):
        points.append(
            {
                "position": [round(float(lon), 6), round(float(lat), 6)],
                "hazard_class": int(hazard_class),
                "population_estimate": round(float(pop)),
                "road_distance_m": round(float(road_m)),
                "communications_access_score": round(float(score), 3),
                "communications_access_class": int(klass),
            }
        )

    labels = {1: "Low", 2: "Medium", 3: "High"}
    summary = {
        "title": "Communications-access vulnerability proxy",
        "formula": "0.55 hazard + 0.30 population exposure + 0.15 isolation from supplied main road",
        "interpretation": "A communication-priority proxy for the prototype, not a measurement or prediction of individual mobile-tower failure.",
        "classes": {labels[klass]: int((comm_class == klass).sum()) for klass in (1, 2, 3)},
        "point_spacing_approx_m": 500,
    }
    (OUTPUTS / "communications_access_points.json").write_text(
        json.dumps({"summary": summary, "points": points}, ensure_ascii=False), encoding="utf-8"
    )
    (OUTPUTS / "communications_access_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
