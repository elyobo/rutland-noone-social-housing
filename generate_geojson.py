#!/usr/bin/env python3
"""Generate GeoJSON building model for Rutland St development shade assessment."""

import json
import os
import pyproj
from shapely.geometry import Polygon, mapping
from shapely.affinity import rotate
from shapely.ops import transform

# Configuration: Adjustments for modelling alternatives
MAIN_HEIGHT_REDUCTION = 0.0  # Metres to reduce main tower and roof items
WEST_SHIFT = 0.0  # Metres to shift all except podium westward

# Anchor: NE corner of existing building
ANCHOR_LAT, ANCHOR_LON = -37.794009, 144.995949
ROTATION_DEG = -5.8  # Rutland St alignment (clockwise from north)
GROUND_RL = 21.73

# Lot dimensions and anchor position relative to lot NE corner
LOT_WIDTH = 40.5   # E-W extent
LOT_LENGTH = 80.9  # N-S extent
ANCHOR_SOUTH_OF_LOT_NORTH = 1.4   # Anchor is 1.4m south of north lot boundary
ANCHOR_WEST_OF_LOT_EAST = 2.55    # Anchor is 2.55m west of east lot boundary

# Derived: lot NE corner relative to anchor (negative = north/east of anchor)
LOT_NE_EAST_SETBACK = -ANCHOR_WEST_OF_LOT_EAST
LOT_NE_SOUTH_OFFSET = -ANCHOR_SOUTH_OF_LOT_NORTH

# Building setbacks from lot boundaries (metres)
# Plans show setbacks/offsets from boundaries, not area dimensions directly,
# so we derive widths and lengths from these known offsets.
TOWER_EAST_SETBACK = 10.548
TOWER_WEST_SETBACK = 8.086
TOWER_NORTH_SETBACK = 14.725
TOWER_SOUTH_SETBACK = 0.492

PODIUM_EAST_SETBACK = 4.765
PODIUM_WEST_SETBACK = 9.628
PODIUM_NORTH_SETBACK = 2.25
PODIUM_SOUTH_SETBACK = 11.775  # South edge of podium

STAIR_EAST_SETBACK = 13.0
STAIR_WEST_SETBACK = 18.0

STREET_NORTH_EAST_SETBACK = 4.76
STREET_SOUTH_EAST_SETBACK = 2.55
STREET_TRANSITION = 30.56  # N-S position where 9.6m transitions to 6.45m

CARPARK_WEST_SETBACK = 4.384
CARPARK_NORTH_SETBACK = 14.58
CARPARK_SOUTH_SETBACK = 9.035

# Computed dimensions
TOWER_WIDTH = LOT_WIDTH - TOWER_EAST_SETBACK - TOWER_WEST_SETBACK
TOWER_LENGTH = LOT_LENGTH - TOWER_NORTH_SETBACK - TOWER_SOUTH_SETBACK

PODIUM_WIDTH = LOT_WIDTH - PODIUM_EAST_SETBACK - PODIUM_WEST_SETBACK
PODIUM_LENGTH = PODIUM_SOUTH_SETBACK - PODIUM_NORTH_SETBACK

STAIR_WIDTH = LOT_WIDTH - STAIR_EAST_SETBACK - STAIR_WEST_SETBACK
STAIR_LENGTH = TOWER_NORTH_SETBACK - PODIUM_SOUTH_SETBACK

STREET_NORTH_WIDTH = TOWER_EAST_SETBACK - STREET_NORTH_EAST_SETBACK
STREET_SOUTH_WIDTH = TOWER_EAST_SETBACK - STREET_SOUTH_EAST_SETBACK
STREET_NORTH_LENGTH = STREET_TRANSITION - TOWER_NORTH_SETBACK
STREET_SOUTH_LENGTH = (LOT_LENGTH - TOWER_SOUTH_SETBACK) - STREET_TRANSITION

CARPARK_WIDTH = TOWER_WEST_SETBACK - CARPARK_WEST_SETBACK
CARPARK_LENGTH = LOT_LENGTH - CARPARK_NORTH_SETBACK - CARPARK_SOUTH_SETBACK

# Heights (metres above ground)
PODIUM_HEIGHT = 14.3
TOWER_HEIGHT = 26.5

# Coordinate transformers (WGS84 <-> UTM zone 55S for Melbourne)
_wgs84 = pyproj.CRS("EPSG:4326")
_utm = pyproj.CRS("EPSG:32755")
_to_utm = pyproj.Transformer.from_crs(_wgs84, _utm, always_xy=True).transform
_to_wgs84 = pyproj.Transformer.from_crs(_utm, _wgs84, always_xy=True).transform

# Anchor in UTM meters
ANCHOR_X, ANCHOR_Y = _to_utm(ANCHOR_LON, ANCHOR_LAT)


def box(east_setback, south_offset, width, length):
    """Create rectangle in UTM from offsets relative to anchor."""
    ne_x = ANCHOR_X - east_setback
    ne_y = ANCHOR_Y - south_offset
    return Polygon([
        (ne_x, ne_y),
        (ne_x - width, ne_y),
        (ne_x - width, ne_y - length),
        (ne_x, ne_y - length),
        (ne_x, ne_y),
    ])


# Building definitions: (name, east_setback, south_offset, width, length, height, color_group)
# east_setback and south_offset are relative to anchor point
BUILDINGS = [
    ("Northern podium",
        PODIUM_EAST_SETBACK - ANCHOR_WEST_OF_LOT_EAST,
        PODIUM_NORTH_SETBACK - ANCHOR_SOUTH_OF_LOT_NORTH,
        PODIUM_WIDTH, PODIUM_LENGTH, PODIUM_HEIGHT, "podium"),
    ("Stair core north",
        STAIR_EAST_SETBACK - ANCHOR_WEST_OF_LOT_EAST,
        PODIUM_SOUTH_SETBACK - ANCHOR_SOUTH_OF_LOT_NORTH,
        STAIR_WIDTH, STAIR_LENGTH, TOWER_HEIGHT, "roof"),
    ("Main tower",
        TOWER_EAST_SETBACK - ANCHOR_WEST_OF_LOT_EAST,
        TOWER_NORTH_SETBACK - ANCHOR_SOUTH_OF_LOT_NORTH,
        TOWER_WIDTH, TOWER_LENGTH, TOWER_HEIGHT, "tower"),
    ("Street-facing north",
        STREET_NORTH_EAST_SETBACK - ANCHOR_WEST_OF_LOT_EAST,
        TOWER_NORTH_SETBACK - ANCHOR_SOUTH_OF_LOT_NORTH,
        STREET_NORTH_WIDTH, STREET_NORTH_LENGTH, 9.6, "street"),
    ("Street-facing south",
        STREET_SOUTH_EAST_SETBACK - ANCHOR_WEST_OF_LOT_EAST,
        STREET_TRANSITION - ANCHOR_SOUTH_OF_LOT_NORTH,
        STREET_SOUTH_WIDTH, STREET_SOUTH_LENGTH, 6.45, "street"),
    ("Roof south stairwell",      9.403, 47.91,   5.59,    3.67,  28.65, "roof"),
    ("Roof HW heat pump",        14.75,  52.24,   7.66,    5.16,  28.65, "roof"),
    ("Roof north stairwell",      8.858, 29.17,   5.0,     6.01,  27.5,  "roof"),
    ("Car park west",
        LOT_WIDTH - TOWER_WEST_SETBACK - ANCHOR_WEST_OF_LOT_EAST,
        CARPARK_NORTH_SETBACK - ANCHOR_SOUTH_OF_LOT_NORTH,
        CARPARK_WIDTH, CARPARK_LENGTH, 0.11, "carpark"),
]

# Lot boundary frame (computed from constants, 0.3m thick edges)
FRAME_THICK = 0.3
LOT_BOUNDARY = [
    ("Lot boundary N", LOT_NE_EAST_SETBACK, LOT_NE_SOUTH_OFFSET, LOT_WIDTH, FRAME_THICK, 0.1, "lot"),
    ("Lot boundary S", LOT_NE_EAST_SETBACK, LOT_NE_SOUTH_OFFSET + LOT_LENGTH - FRAME_THICK, LOT_WIDTH, FRAME_THICK, 0.1, "lot"),
    ("Lot boundary E", LOT_NE_EAST_SETBACK, LOT_NE_SOUTH_OFFSET + FRAME_THICK, FRAME_THICK, LOT_LENGTH - 2 * FRAME_THICK, 0.1, "lot"),
    ("Lot boundary W", LOT_NE_EAST_SETBACK + LOT_WIDTH - FRAME_THICK, LOT_NE_SOUTH_OFFSET + FRAME_THICK, FRAME_THICK, LOT_LENGTH - 2 * FRAME_THICK, 0.1, "lot"),
]

# Brick colours from architectural drawings
COLORS = {
    "tower":   ("rgba(176, 128, 112, 1.0)", "rgba(140, 100, 88, 1.0)"),   # Lighter pinkish-red brick
    "podium":  ("rgba(140, 68, 68, 1.0)",   "rgba(100, 48, 48, 1.0)"),    # Deeper red-brown brick
    "street":  ("rgba(140, 68, 68, 1.0)",   "rgba(100, 48, 48, 1.0)"),    # Deeper red-brown brick
    "roof":    ("rgba(128, 128, 128, 1.0)", "rgba(96, 96, 96, 1.0)"),     # Grey
    "carpark": ("rgba(80, 80, 80, 0.6)",    "rgba(60, 60, 60, 1.0)"),     # Dark grey, semi-transparent
    "lot":     ("rgba(0, 120, 255, 1.0)",   "rgba(0, 80, 200, 1.0)"),     # Bright blue
}


def main():
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        raise SystemExit("Error: GOOGLE_MAPS_API_KEY not set")

    features = []
    js_buildings = []

    for name, east, south, width, length, height, color_group in BUILDINGS + LOT_BOUNDARY:
        # Apply adjustments (not to lot boundary or podium)
        if color_group not in ("lot",) and name != "Northern podium":
            east += WEST_SHIFT
        if height > PODIUM_HEIGHT:  # Taller than podium = part of main tower mass
            height -= MAIN_HEIGHT_REDUCTION

        # Create box in UTM, rotate, convert to WGS84
        poly = box(east, south, width, length)
        rotated = rotate(poly, ROTATION_DEG, origin=(ANCHOR_X, ANCHOR_Y))
        wgs84 = transform(_to_wgs84, rotated)

        features.append({
            "type": "Feature",
            "properties": {"name": name, "height": height},
            "geometry": mapping(wgs84),
        })

        fill, stroke = COLORS[color_group]
        js_buildings.append({
            "coords": list(wgs84.exterior.coords[:-1]),
            "height": height,
            "fill": fill,
            "stroke": stroke,
        })

    # Write GeoJSON
    geojson = {"type": "FeatureCollection", "features": features}
    with open("index.geojson", "w") as f:
        json.dump(geojson, f, indent=2)
    print("Wrote index.geojson")

    # Write HTML viewer
    html = f'''<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Noone St / Rutland St Community Housing - 3D Model</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    html, body {{ margin: 0; padding: 0; height: 100%; font-family: system-ui, sans-serif; }}
    #map {{ width: 100%; height: 100vh; }}
    gmp-map-3d {{ display: block; width: 100%; height: 100%; }}
    #info {{
      position: absolute; top: 10px; left: 10px; background: white;
      padding: 12px 16px; border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.3);
      font-size: 14px; z-index: 1; max-width: 320px;
    }}
    #info h3 {{ margin: 0 0 8px; font-size: 15px; }}
    #info p {{ margin: 0 0 8px; color: #666; font-size: 12px; line-height: 1.4; }}
    #info a {{ color: #1a73e8; }}
    .note {{ font-size: 11px; color: #888; margin-top: 8px; }}
    .legend {{ margin-top: 10px; padding-top: 10px; border-top: 1px solid #eee; }}
    .legend-item {{ display: flex; align-items: center; gap: 8px; margin: 4px 0; font-size: 11px; }}
    .legend-swatch {{ width: 14px; height: 14px; border-radius: 2px; flex-shrink: 0; }}
    .toggle {{ display: block; margin-top: 10px; font-size: 12px; cursor: pointer; }}
    /* Hide Google Maps alpha channel warning */
    [role="region"][aria-label*="alpha channel"] {{ display: none !important; }}
  </style>
  <script src="https://maps.googleapis.com/maps/api/js?key={api_key}&v=alpha&libraries=maps3d" async></script>
</head>
<body>
  <div id="map"></div>
  <div id="info">
    <h3>Noone St / Rutland St Community Housing</h3>
    <p>Load <a href="index.geojson" download>building model</a> into
       <a href="https://shademap.app" target="_blank">shademap.app</a> for shade analysis.</p>
    <div class="legend">
      <div class="legend-item"><span class="legend-swatch" style="background:rgb(176,128,112)"></span>Main tower (26.5m)</div>
      <div class="legend-item"><span class="legend-swatch" style="background:rgb(140,68,68)"></span>Podium (14.3m) / Street (9.6m, 6.45m)</div>
      <div class="legend-item"><span class="legend-swatch" style="background:rgb(128,128,128)"></span>Roof plant &amp; stairs</div>
      <div class="legend-item"><span class="legend-swatch" style="background:rgb(80,80,80)"></span>Car park (external overflow)</div>
      <div class="legend-item"><span class="legend-swatch" style="background:rgb(0,120,255)"></span>Lot boundary</div>
    </div>
    <p class="note">Shift+drag or Ctrl+drag to change viewing angle.</p>
    <label class="toggle"><input type="checkbox" id="occluded"> Show through existing buildings</label>
  </div>
  <script>
    const GROUND = {GROUND_RL};
    const BUILDINGS = {json.dumps(js_buildings)};

    async function init() {{
      const {{ Map3DElement, Polygon3DElement, AltitudeMode, MapMode }} = await google.maps.importLibrary("maps3d");

      const map = new Map3DElement({{
        center: {{ lat: {ANCHOR_LAT - 0.001}, lng: {ANCHOR_LON - 0.0002}, altitude: 120 }},
        range: 200, tilt: 60, heading: 0, mode: MapMode.HYBRID
      }});
      map.style.width = map.style.height = "100%";
      document.getElementById("map").appendChild(map);

      const polygons = [];
      for (const b of BUILDINGS) {{
        const poly = new Polygon3DElement({{
          altitudeMode: AltitudeMode.ABSOLUTE,
          extruded: true,
          fillColor: b.fill,
          strokeColor: b.stroke,
          strokeWidth: 2,
          drawsOccludedSegments: false
        }});
        poly.outerCoordinates = b.coords.map(([lng, lat]) => ({{
          lat, lng, altitude: GROUND + b.height
        }}));
        map.appendChild(poly);
        polygons.push(poly);
      }}

      document.getElementById("occluded").addEventListener("change", (e) => {{
        for (const p of polygons) p.drawsOccludedSegments = e.target.checked;
      }});
    }}

    window.onload = init;
  </script>
</body>
</html>'''

    with open("index.html", "w") as f:
        f.write(html)
    print("Wrote index.html")


if __name__ == "__main__":
    main()
