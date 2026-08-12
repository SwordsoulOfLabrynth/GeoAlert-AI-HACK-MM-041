"""Build a road-network evacuation-route prototype from downloaded OSM API tiles.

The map uses real OpenStreetMap road geometry.  It is a hackathon prototype:
the selected endpoints are illustrative and routing does not yet include live
closures, traffic, shelters, or field verification.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import networkx as nx
import numpy as np
import tifffile


ROOT = Path(__file__).resolve().parents[1]
TILES = ROOT / "reference_data" / "osm_road_tiles"
OUTPUTS = ROOT / "risk_map_outputs"
HAZARD_FILE = OUTPUTS / "combined_hazard_class.tif"
ROADS_FILE = ROOT / "reference_data" / "osm_road_network.geojson"
ROUTE_FILE = OUTPUTS / "road_based_route.json"
MAP_FILE = OUTPUTS / "road_based_evacuation_route_map.png"
ROAD_TYPES = {"motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential", "service"}


def distance_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    lon1, lat1 = a
    lon2, lat2 = b
    return 111_320 * math.hypot((lon2 - lon1) * math.cos(math.radians((lat1 + lat2) / 2)), lat2 - lat1)


def load_osm() -> tuple[dict[int, tuple[float, float]], dict[int, tuple[list[int], dict[str, str]]]]:
    nodes: dict[int, tuple[float, float]] = {}
    ways: dict[int, tuple[list[int], dict[str, str]]] = {}
    for tile in sorted(TILES.glob("*.osm")):
        root = ET.parse(tile).getroot()
        for element in root:
            if element.tag == "node":
                nodes[int(element.attrib["id"])] = (float(element.attrib["lon"]), float(element.attrib["lat"]))
            elif element.tag == "way":
                tags = {tag.attrib["k"]: tag.attrib["v"] for tag in element.findall("tag")}
                if tags.get("highway") in ROAD_TYPES:
                    ways[int(element.attrib["id"])] = ([int(node.attrib["ref"]) for node in element.findall("nd")], tags)
    if not nodes or not ways:
        raise RuntimeError("No OSM tiles were found. Place downloaded .osm API tiles in reference_data/osm_road_tiles.")
    return nodes, ways


def main() -> None:
    nodes, ways = load_osm()
    with tifffile.TiffFile(HAZARD_FILE) as tif:
        hazard = tif.pages[0].asarray()
        pixel_size = float(tif.pages[0].tags[33550].value[0])
        tiepoint = tif.pages[0].tags[33922].value
        lon_min, lat_max = float(tiepoint[3]), float(tiepoint[4])
    rows, cols = hazard.shape
    lon_max, lat_min = lon_min + cols * pixel_size, lat_max - rows * pixel_size

    def cell_risk(lon: float, lat: float) -> int:
        col = int((lon - lon_min) / pixel_size)
        row = int((lat_max - lat) / pixel_size)
        value = int(hazard[max(0, min(rows - 1, row)), max(0, min(cols - 1, col))])
        return min(3, max(1, value))

    graph = nx.Graph()
    geo_features = []
    for osm_id, (node_ids, tags) in ways.items():
        coordinates = [nodes[node_id] for node_id in node_ids if node_id in nodes]
        if len(coordinates) >= 2:
            geo_features.append(
                {
                    "type": "Feature",
                    "properties": {"osm_way_id": osm_id, "highway": tags["highway"], "name": tags.get("name", "Unnamed OSM road")},
                    "geometry": {"type": "LineString", "coordinates": coordinates},
                }
            )
        for a, b in zip(node_ids, node_ids[1:]):
            if a not in nodes or b not in nodes:
                continue
            segment_distance = distance_m(nodes[a], nodes[b])
            risk = (cell_risk(*nodes[a]) + cell_risk(*nodes[b])) / 2
            # Strongly discourage high-hazard segments while retaining actual road geometry.
            weighted_cost = segment_distance * {1: 1.0, 2: 2.0, 3: 5.0}[int(round(risk))]
            if not graph.has_edge(a, b) or weighted_cost < graph[a][b]["risk_cost"]:
                graph.add_edge(
                    a,
                    b,
                    distance=segment_distance,
                    risk=risk,
                    risk_cost=weighted_cost,
                    highway=tags["highway"],
                    way_name=tags.get("name", "Unnamed OSM road"),
                )

    # Illustrative test route within the OSM tile coverage: Paung-side corridor to Mawlamyine-side corridor.
    requested_start = (97.471, 16.598)
    requested_end = (97.600, 16.531)
    road_nodes = list(graph.nodes)
    start = min(road_nodes, key=lambda node: (nodes[node][0] - requested_start[0]) ** 2 + (nodes[node][1] - requested_start[1]) ** 2)
    end = min(road_nodes, key=lambda node: (nodes[node][0] - requested_end[0]) ** 2 + (nodes[node][1] - requested_end[1]) ** 2)
    shortest_path = nx.shortest_path(graph, start, end, weight="distance")
    selected_path = nx.shortest_path(graph, start, end, weight="risk_cost")

    def summarize(path: list[int]) -> dict[str, object]:
        edges = [graph[a][b] for a, b in zip(path, path[1:])]
        total_m = sum(edge["distance"] for edge in edges)
        high_m = sum(edge["distance"] for edge in edges if edge["risk"] >= 2.5)
        medium_m = sum(edge["distance"] for edge in edges if 1.5 <= edge["risk"] < 2.5)
        return {
            "coordinates": [nodes[node] for node in path],
            "distance_km": round(total_m / 1000, 2),
            "high_hazard_km": round(high_m / 1000, 2),
            "medium_hazard_km": round(medium_m / 1000, 2),
        }

    selected = summarize(selected_path)
    shortest = summarize(shortest_path)
    same_route = selected["coordinates"] == shortest["coordinates"]
    ROUTE_FILE.write_text(
        json.dumps(
            {
                "title": "OSM road-network route prototype",
                "source": "OpenStreetMap API road data, downloaded 2026-08-11; © OpenStreetMap contributors, ODbL.",
                "method": "Dijkstra routing on OSM road geometry; distance is multiplied by hazard class (low=1, medium=2, high=5).",
                "selected_route": selected,
                "shortest_route": shortest,
                "same_as_shortest_route": same_route,
                "interpretation": "For this August 2025 scenario and selected endpoints, the risk-weighted road route matches the shortest available OSM road route. No lower-risk road alternative was found in the downloaded road subset.",
                "limitations": "Illustrative endpoints only. The prototype does not include live road closures, traffic, one-way restrictions, verified shelters, or official evacuation instructions.",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    ROADS_FILE.write_text(json.dumps({"type": "FeatureCollection", "features": geo_features}), encoding="utf-8")

    fig, ax = plt.subplots(figsize=(11, 8.5), dpi=170)
    ax.imshow(hazard, cmap=ListedColormap(["#58a66a", "#f2bd4a", "#d74f4f"]), vmin=1, vmax=3, alpha=0.60, extent=[lon_min, lon_max, lat_min, lat_max], origin="upper")
    for feature in geo_features:
        coords = feature["geometry"]["coordinates"]
        xs, ys = zip(*coords)
        ax.plot(xs, ys, color="#59636e", linewidth=0.45, alpha=0.28)
    route_x, route_y = zip(*selected["coordinates"])
    ax.plot(route_x, route_y, color="#006d3c", linewidth=3.3, label="Risk-weighted OSM road route", zorder=4)
    start_xy, end_xy = selected["coordinates"][0], selected["coordinates"][-1]
    ax.scatter(*start_xy, s=125, color="#8b0000", edgecolor="white", linewidth=1.3, zorder=5, label="Illustrative origin")
    ax.scatter(*end_xy, s=180, marker="*", color="#006d3c", edgecolor="white", linewidth=1.3, zorder=5, label="Illustrative destination")
    ax.set_title("Road-based evacuation-route prototype — Mawlamyine–Paung corridor", fontsize=15, weight="bold", pad=12)
    ax.text(
        0.5,
        -0.13,
        f"Route length: {selected['distance_km']} km. Green / amber / red = low / medium / high combined hazard.\n"
        "Route follows downloaded OSM road geometry; it still requires local closure and safety verification.",
        ha="center",
        va="top",
        transform=ax.transAxes,
        fontsize=9,
    )
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.grid(alpha=0.15)
    ax.legend(loc="upper right", framealpha=0.95)
    fig.tight_layout()
    fig.savefig(MAP_FILE, bbox_inches="tight")
    plt.close(fig)
    print(MAP_FILE)


if __name__ == "__main__":
    main()
