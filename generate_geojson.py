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
BUILDINGS = [
    ("Northern podium",           2.215,  0.85,  26.157,  12.475, 14.3,  "podium"),
    ("Main tower",                7.998, 13.325, 21.866,  65.683, 26.5,  "tower"),
    ("Street-facing north",       0.0,   13.325,  7.998,  15.835,  9.6,  "street"),
    ("Street-facing south",       0.0,   29.16,   7.998,  49.848,  6.45, "street"),
    ("Roof south stairwell",      9.403, 47.91,   5.59,    3.67,  28.65, "roof"),
    ("Roof HW heat pump",        14.75,  52.24,   7.66,    5.16,  28.65, "roof"),
    ("Roof north stairwell",      8.858, 29.17,   5.0,     6.01,  27.5,  "roof"),
]

# Brick colours from architectural drawings
COLORS = {
    "tower":  ("rgba(176, 128, 112, 1.0)", "rgba(140, 100, 88, 1.0)"),   # Lighter pinkish-red brick
    "podium": ("rgba(140, 68, 68, 1.0)",   "rgba(100, 48, 48, 1.0)"),    # Deeper red-brown brick
    "street": ("rgba(140, 68, 68, 1.0)",   "rgba(100, 48, 48, 1.0)"),    # Deeper red-brown brick
    "roof":   ("rgba(128, 128, 128, 1.0)", "rgba(96, 96, 96, 1.0)"),     # Grey
}


def main():
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        raise SystemExit("Error: GOOGLE_MAPS_API_KEY not set")

    features = []
    js_buildings = []

    for name, east, south, width, length, height, color_group in BUILDINGS:
        # Apply adjustments
        is_podium = name == "Northern podium"
        if not is_podium:
            east += WEST_SHIFT
        if color_group in ("tower", "roof"):
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
    /* Hide Google Maps alpha channel warning */
    [role="region"][aria-label*="alpha channel"] {{ display: none !important; }}
  </style>
  <script src="https://maps.googleapis.com/maps/api/js?key={api_key}&v=alpha&libraries=maps3d" async></script>
</head>
<body>
  <div id="map"></div>
  <div id="info">
    <h3>Noone St / Rutland St Community Housing</h3>
    <p>Tower: 26.5m &bull; Podium: 14.3m &bull; Street: 9.6m / 6.45m</p>
    <p>Load <a href="index.geojson" download>building model</a> into
       <a href="https://shademap.app" target="_blank">shademap.app</a> for shade analysis.</p>
    <p class="note">Shift+drag or Ctrl+drag to change viewing angle.</p>
  </div>
  <script>
    const GROUND = {GROUND_RL};
    const BUILDINGS = {json.dumps(js_buildings)};

    async function init() {{
      const {{ Map3DElement, Polygon3DElement, AltitudeMode, MapMode }} = await google.maps.importLibrary("maps3d");

      const map = new Map3DElement({{
        center: {{ lat: {ANCHOR_LAT - 0.0015}, lng: {ANCHOR_LON}, altitude: 200 }},
        range: 400, tilt: 60, heading: 0, mode: MapMode.HYBRID
      }});
      map.style.width = map.style.height = "100%";
      document.getElementById("map").appendChild(map);

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
      }}
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
