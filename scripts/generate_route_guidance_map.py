"""Create a transparent, illustrative hazard-avoidance guidance map.

This deliberately does not claim to be a road-navigation route: the supplied
OpenStreetMap input only contains a main-corridor reference, not a complete
routable road network.
"""

from __future__ import annotations

import heapq
import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import numpy as np
import tifffile


ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "risk_map_outputs"
HAZARD_FILE = OUTPUTS / "combined_hazard_class.tif"
CORRIDOR_FILE = ROOT / "reference_data" / "main_corridor.geojson"
MAP_FILE = OUTPUTS / "evacuation_guidance_map.png"
METADATA_FILE = OUTPUTS / "route_guidance_metadata.json"


def pixel_to_lonlat(row: int, col: int, lon_min: float, lat_max: float, pixel_size: float) -> tuple[float, float]:
    return lon_min + (col + 0.5) * pixel_size, lat_max - (row + 0.5) * pixel_size


def a_star(cost: np.ndarray, start: tuple[int, int], goal: tuple[int, int]) -> list[tuple[int, int]]:
    """Four-neighbour least-cost path across a small hazard grid."""
    rows, cols = cost.shape
    queue = [(0.0, start)]
    came_from: dict[tuple[int, int], tuple[int, int]] = {}
    g_score = {start: 0.0}

    while queue:
        _, current = heapq.heappop(queue)
        if current == goal:
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            return path[::-1]
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            neighbor = current[0] + dr, current[1] + dc
            if not (0 <= neighbor[0] < rows and 0 <= neighbor[1] < cols):
                continue
            tentative = g_score[current] + float(cost[neighbor])
            if tentative < g_score.get(neighbor, float("inf")):
                came_from[neighbor] = current
                g_score[neighbor] = tentative
                distance = abs(neighbor[0] - goal[0]) + abs(neighbor[1] - goal[1])
                heapq.heappush(queue, (tentative + distance, neighbor))
    raise RuntimeError("No illustrative least-cost path could be created.")


def lonlat_to_pixel(lon: float, lat: float, lon_min: float, lat_max: float, pixel_size: float) -> tuple[int, int]:
    return round((lat_max - lat) / pixel_size), round((lon - lon_min) / pixel_size)


def main() -> None:
    with tifffile.TiffFile(HAZARD_FILE) as tif:
        hazard = tif.pages[0].asarray()
        scale = tif.pages[0].tags[33550].value[0]
        tiepoint = tif.pages[0].tags[33922].value
        lon_min, lat_max = float(tiepoint[3]), float(tiepoint[4])

    rows, cols = hazard.shape
    lon_max = lon_min + cols * scale
    lat_min = lat_max - rows * scale
    # Chosen endpoints demonstrate the prototype from a high-risk northern area
    # to a lower-risk southern area; they are deliberately not named as real sites.
    start = lonlat_to_pixel(97.40, 16.70, lon_min, lat_max, scale)
    goal = lonlat_to_pixel(97.63, 16.49, lon_min, lat_max, scale)
    start = (int(np.clip(start[0], 0, rows - 1)), int(np.clip(start[1], 0, cols - 1)))
    goal = (int(np.clip(goal[0], 0, rows - 1)), int(np.clip(goal[1], 0, cols - 1)))

    # A high-risk cell has 30 times the traversal cost of a low-risk cell.
    # This produces a transparent *hazard-avoidance corridor concept*, not a road route.
    risk_cost = np.choose(np.clip(hazard, 1, 3) - 1, [1.0, 6.0, 30.0])
    # Keep the illustration within a plausible local corridor rather than letting
    # the mathematical path make a very long detour around the whole study area.
    margin = 45  # about 5 km at this output resolution
    row_min, row_max = max(0, min(start[0], goal[0]) - margin), min(rows, max(start[0], goal[0]) + margin + 1)
    col_min, col_max = max(0, min(start[1], goal[1]) - margin), min(cols, max(start[1], goal[1]) + margin + 1)
    risk_cost[:row_min, :] = 500.0
    risk_cost[row_max:, :] = 500.0
    risk_cost[:, :col_min] = 500.0
    risk_cost[:, col_max:] = 500.0
    path = a_star(risk_cost, start, goal)
    path_lonlat = [pixel_to_lonlat(r, c, lon_min, lat_max, scale) for r, c in path]

    corridor = json.loads(CORRIDOR_FILE.read_text(encoding="utf-8"))
    fig, ax = plt.subplots(figsize=(11, 8.5), dpi=170)
    cmap = ListedColormap(["#58a66a", "#f2bd4a", "#d74f4f"])
    ax.imshow(hazard, cmap=cmap, vmin=1, vmax=3, alpha=0.67, extent=[lon_min, lon_max, lat_min, lat_max], origin="upper")

    for feature in corridor["features"]:
        geometry = feature.get("geometry", {})
        for line in geometry.get("coordinates", []):
            xs, ys = zip(*line)
            ax.plot(xs, ys, color="#b2182b", linewidth=2.6, alpha=0.9, label="Supplied main-corridor reference")

    path_x, path_y = zip(*path_lonlat)
    ax.plot(path_x, path_y, color="#075a30", linewidth=2.8, linestyle="--", label="Illustrative hazard-avoidance corridor")
    start_lon, start_lat = pixel_to_lonlat(*start, lon_min, lat_max, scale)
    goal_lon, goal_lat = pixel_to_lonlat(*goal, lon_min, lat_max, scale)
    ax.scatter(start_lon, start_lat, s=130, marker="o", color="#8b0000", edgecolor="white", linewidth=1.3, zorder=5)
    ax.scatter(goal_lon, goal_lat, s=180, marker="*", color="#075a30", edgecolor="white", linewidth=1.3, zorder=5)
    ax.annotate("Illustrative\nstart area", (start_lon, start_lat), xytext=(8, 8), textcoords="offset points", fontsize=9, weight="bold")
    ax.annotate("Illustrative lower-risk\ndestination", (goal_lon, goal_lat), xytext=(8, 8), textcoords="offset points", fontsize=9, weight="bold")
    ax.set_title("Evacuation guidance prototype — Mawlamyine–Paung corridor", fontsize=15, weight="bold", pad=12)
    ax.text(
        0.5,
        -0.13,
        "Green / amber / red = low / medium / high combined hazard. Dashed green line avoids high-hazard cells,\n"
        "but is not a verified road route or an official evacuation instruction.",
        ha="center",
        va="top",
        transform=ax.transAxes,
        fontsize=9,
    )
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.grid(alpha=0.18)
    handles, labels = ax.get_legend_handles_labels()
    unique = dict(zip(labels, handles))
    ax.legend(unique.values(), unique.keys(), loc="upper right", framealpha=0.95)
    fig.tight_layout()
    fig.savefig(MAP_FILE, bbox_inches="tight")
    plt.close(fig)

    METADATA_FILE.write_text(
        json.dumps(
            {
                "title": "Illustrative hazard-avoidance corridor",
                "method": "A* least-cost path on the combined hazard grid (low=1, medium=6, high=30).",
                "endpoints": "Illustrative map points, not verified shelters or communities.",
                "limitation": "The supplied data has no complete routable road network; this is not turn-by-turn navigation or an official evacuation route.",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(MAP_FILE)


if __name__ == "__main__":
    main()
