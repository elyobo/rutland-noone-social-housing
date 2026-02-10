#!/usr/bin/env python3
"""
Generate GeoJSON for Noone Street and Rutland Street Community Housing shade impact assessment.

Creates building masses aligned with Rutland Street (~12° west of true north),
using shapely for proper geometric transformations.
"""

import json
import os
from shapely.geometry import Polygon, mapping
from shapely.affinity import rotate
import pyproj
from functools import partial
from shapely.ops import transform

# === Configuration ===

# Anchor point: NE corner of building (at street boundary)
ANCHOR_LAT = -37.79402072126052
ANCHOR_LON = 144.9959728611442

# Building rotation: Rutland St runs ~6° west of true north
# For building on WEST side of street, eastern face must align with street
# Clockwise = negative angle in shapely
ROTATION_DEG = -5.8

# Site dimensions (from planning documents)
LOT_LENGTH = 80.9   # N-S dimension
LOT_WIDTH = 40.5    # E-W dimension

# Podium setbacks
PODIUM_NORTH_SETBACK = 2.25
PODIUM_EAST_SETBACK = 4.765
PODIUM_WEST_SETBACK = 9.578
PODIUM_SOUTH_EDGE = 14.725  # Distance from north boundary to podium's south edge

# Tower setbacks
TOWER_SOUTH_SETBACK = 0.492
TOWER_EAST_SETBACK = 10.548
TOWER_WEST_SETBACK = 8.086

# Calculated building dimensions
MASS1_WIDTH = LOT_WIDTH - PODIUM_EAST_SETBACK - PODIUM_WEST_SETBACK   # 26.157m
MASS1_LENGTH = PODIUM_SOUTH_EDGE - PODIUM_NORTH_SETBACK               # 12.475m

MASS2_WIDTH = LOT_WIDTH - TOWER_EAST_SETBACK - TOWER_WEST_SETBACK     # 21.866m
MASS2_LENGTH = LOT_LENGTH - PODIUM_SOUTH_EDGE - TOWER_SOUTH_SETBACK   # 65.683m

# Heights
MASS1_HEIGHT = 14.3
MASS2_HEIGHT = 26.5  # Main tower bulk to RL 48.23

# Roof protrusions (stairwell/plant room overruns) - all at RL 50.38
ROOF_SOUTH_HEIGHT = 28.65  # RL 50.38 - 21.73

# South stairwell: NE corner aligned with original position
# From 31.59m to (31.59 - 3.67) = 27.92m from south boundary
ROOF_STAIR_SOUTH_LENGTH = 3.67
ROOF_STAIR_SOUTH_WIDTH = 5.59
ROOF_STAIR_SOUTH_START_FROM_NORTH = LOT_LENGTH - 31.59  # 49.31m from north
ROOF_STAIR_SOUTH_EAST_SETBACK = TOWER_EAST_SETBACK + 1.405  # 11.953m from east boundary

# HW Heat Pump: SW corner aligned with original position
# From 22.1m to (22.1 + 5.16) = 27.26m from south boundary
ROOF_HW_LENGTH = 5.16
ROOF_HW_WIDTH = 7.66
ROOF_HW_START_FROM_NORTH = LOT_LENGTH - (22.1 + ROOF_HW_LENGTH)  # 53.64m from north
ROOF_HW_WEST_FROM_BOUNDARY = 15.54
ROOF_HW_EAST_SETBACK = LOT_WIDTH - ROOF_HW_WEST_FROM_BOUNDARY - ROOF_HW_WIDTH  # 17.3m from east

# North protrusion: RL 49.23, from 44.32m to 50.33m from south boundary
ROOF_NORTH_HEIGHT = 27.5  # RL 49.23 - 21.73
ROOF_NORTH_START_FROM_SOUTH = 44.32
ROOF_NORTH_END_FROM_SOUTH = 50.33
ROOF_NORTH_LENGTH = ROOF_NORTH_END_FROM_SOUTH - ROOF_NORTH_START_FROM_SOUTH  # 6.01m
ROOF_NORTH_START_FROM_NORTH = LOT_LENGTH - ROOF_NORTH_END_FROM_SOUTH  # 30.57m
ROOF_NORTH_EAST_SETBACK = TOWER_EAST_SETBACK + 0.86   # 0.86m back from tower's east edge
ROOF_NORTH_WIDTH = 5.0  # Approximately 5m wide

# Street-facing masses (at property boundary, in front of tower)
# Transition point: 62.22% of 80.9m from south = 50.34m from south = 30.56m from north
STREET_TRANSITION_FROM_NORTH = 30.56

# Northern street-facing mass (taller, adjacent to podium)
STREET_NORTH_LENGTH = STREET_TRANSITION_FROM_NORTH - PODIUM_SOUTH_EDGE  # 15.835m
STREET_NORTH_HEIGHT = 9.6
STREET_NORTH_WIDTH = TOWER_EAST_SETBACK  # 10.548m (fills gap to tower)

# Southern street-facing mass (lower)
STREET_SOUTH_LENGTH = (LOT_LENGTH - TOWER_SOUTH_SETBACK) - STREET_TRANSITION_FROM_NORTH  # 49.848m
STREET_SOUTH_HEIGHT = 6.45
STREET_SOUTH_WIDTH = TOWER_EAST_SETBACK  # 10.548m

# Output files
OUTPUT_FILE = "index.geojson"
HTML_FILE = "index.html"


def create_utm_transformers(lon: float, lat: float):
    """Create transformers between WGS84 and appropriate UTM zone."""
    # Determine UTM zone (Melbourne is zone 55S)
    utm_zone = int((lon + 180) / 6) + 1
    utm_crs = pyproj.CRS(f"EPSG:326{utm_zone:02d}" if lat >= 0 else f"EPSG:327{utm_zone:02d}")
    wgs84 = pyproj.CRS("EPSG:4326")

    to_utm = pyproj.Transformer.from_crs(wgs84, utm_crs, always_xy=True).transform
    to_wgs84 = pyproj.Transformer.from_crs(utm_crs, wgs84, always_xy=True).transform

    return to_utm, to_wgs84


def create_building_mass(anchor_x: float, anchor_y: float,
                         width: float, length: float,
                         offset_along: float = 0,
                         east_setback: float = 0) -> Polygon:
    """
    Create a rectangular building mass in UTM coordinates.

    Anchor is at NE corner of lot (street boundary). Building extends:
    - West (negative X) by width, starting from east_setback
    - South (negative Y) by length

    offset_along: distance south from anchor to start this mass
    east_setback: distance west from anchor to start eastern face
    """
    # NE corner of building (set back from lot boundary)
    ne_x = anchor_x - east_setback
    ne_y = anchor_y - offset_along

    nw_x = ne_x - width
    nw_y = ne_y

    sw_x = nw_x
    sw_y = ne_y - length

    se_x = ne_x
    se_y = sw_y

    return Polygon([
        (ne_x, ne_y),
        (nw_x, nw_y),
        (sw_x, sw_y),
        (se_x, se_y),
        (ne_x, ne_y)
    ])


def main():
    # Get API key from environment
    api_key = os.environ.get('GOOGLE_MAPS_API_KEY')
    if not api_key:
        raise SystemExit("Error: GOOGLE_MAPS_API_KEY environment variable not set")

    # Set up coordinate transformers
    to_utm, to_wgs84 = create_utm_transformers(ANCHOR_LON, ANCHOR_LAT)

    # Convert anchor point to UTM
    anchor_x, anchor_y = to_utm(ANCHOR_LON, ANCHOR_LAT)
    print(f"Anchor point in UTM: ({anchor_x:.2f}, {anchor_y:.2f})")

    # Create building masses (aligned N-S initially)
    # Podium: starts at north setback, uses podium east setback
    mass1 = create_building_mass(anchor_x, anchor_y, MASS1_WIDTH, MASS1_LENGTH,
                                 offset_along=PODIUM_NORTH_SETBACK,
                                 east_setback=PODIUM_EAST_SETBACK)
    # Tower: starts at podium south edge, uses tower east setback
    mass2 = create_building_mass(anchor_x, anchor_y, MASS2_WIDTH, MASS2_LENGTH,
                                 offset_along=PODIUM_SOUTH_EDGE,
                                 east_setback=TOWER_EAST_SETBACK)

    # Street-facing masses (at property boundary, no east setback)
    # Northern street mass (taller, adjacent to podium)
    street_north = create_building_mass(anchor_x, anchor_y, STREET_NORTH_WIDTH, STREET_NORTH_LENGTH,
                                        offset_along=PODIUM_SOUTH_EDGE,
                                        east_setback=0)
    # Southern street mass (lower)
    street_south = create_building_mass(anchor_x, anchor_y, STREET_SOUTH_WIDTH, STREET_SOUTH_LENGTH,
                                        offset_along=STREET_TRANSITION_FROM_NORTH,
                                        east_setback=0)

    # Roof protrusions (stairwell/plant room overruns)
    roof_stair_south = create_building_mass(anchor_x, anchor_y, ROOF_STAIR_SOUTH_WIDTH, ROOF_STAIR_SOUTH_LENGTH,
                                            offset_along=ROOF_STAIR_SOUTH_START_FROM_NORTH,
                                            east_setback=ROOF_STAIR_SOUTH_EAST_SETBACK)
    roof_hw = create_building_mass(anchor_x, anchor_y, ROOF_HW_WIDTH, ROOF_HW_LENGTH,
                                   offset_along=ROOF_HW_START_FROM_NORTH,
                                   east_setback=ROOF_HW_EAST_SETBACK)
    roof_north = create_building_mass(anchor_x, anchor_y, ROOF_NORTH_WIDTH, ROOF_NORTH_LENGTH,
                                      offset_along=ROOF_NORTH_START_FROM_NORTH,
                                      east_setback=ROOF_NORTH_EAST_SETBACK)

    print(f"Mass 1 bounds (before rotation): {mass1.bounds}")
    print(f"Mass 2 bounds (before rotation): {mass2.bounds}")
    print(f"Street north bounds (before rotation): {street_north.bounds}")
    print(f"Street south bounds (before rotation): {street_south.bounds}")

    # Rotate all masses around the anchor point (NE corner)
    mass1_rotated = rotate(mass1, ROTATION_DEG, origin=(anchor_x, anchor_y))
    mass2_rotated = rotate(mass2, ROTATION_DEG, origin=(anchor_x, anchor_y))
    street_north_rotated = rotate(street_north, ROTATION_DEG, origin=(anchor_x, anchor_y))
    street_south_rotated = rotate(street_south, ROTATION_DEG, origin=(anchor_x, anchor_y))
    roof_stair_south_rotated = rotate(roof_stair_south, ROTATION_DEG, origin=(anchor_x, anchor_y))
    roof_hw_rotated = rotate(roof_hw, ROTATION_DEG, origin=(anchor_x, anchor_y))
    roof_north_rotated = rotate(roof_north, ROTATION_DEG, origin=(anchor_x, anchor_y))

    print(f"Mass 1 bounds (after rotation): {mass1_rotated.bounds}")
    print(f"Mass 2 bounds (after rotation): {mass2_rotated.bounds}")
    print(f"Street north bounds (after rotation): {street_north_rotated.bounds}")
    print(f"Street south bounds (after rotation): {street_south_rotated.bounds}")

    # Transform back to WGS84
    mass1_wgs84 = transform(to_wgs84, mass1_rotated)
    mass2_wgs84 = transform(to_wgs84, mass2_rotated)
    street_north_wgs84 = transform(to_wgs84, street_north_rotated)
    street_south_wgs84 = transform(to_wgs84, street_south_rotated)
    roof_stair_south_wgs84 = transform(to_wgs84, roof_stair_south_rotated)
    roof_hw_wgs84 = transform(to_wgs84, roof_hw_rotated)
    roof_north_wgs84 = transform(to_wgs84, roof_north_rotated)

    # Build GeoJSON
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "name": "Northern podium",
                    "height": MASS1_HEIGHT
                },
                "geometry": mapping(mass1_wgs84)
            },
            {
                "type": "Feature",
                "properties": {
                    "name": "Main tower",
                    "height": MASS2_HEIGHT
                },
                "geometry": mapping(mass2_wgs84)
            },
            {
                "type": "Feature",
                "properties": {
                    "name": "Street-facing north (taller)",
                    "height": STREET_NORTH_HEIGHT
                },
                "geometry": mapping(street_north_wgs84)
            },
            {
                "type": "Feature",
                "properties": {
                    "name": "Street-facing south (lower)",
                    "height": STREET_SOUTH_HEIGHT
                },
                "geometry": mapping(street_south_wgs84)
            },
            {
                "type": "Feature",
                "properties": {
                    "name": "Roof south stairwell",
                    "height": ROOF_SOUTH_HEIGHT
                },
                "geometry": mapping(roof_stair_south_wgs84)
            },
            {
                "type": "Feature",
                "properties": {
                    "name": "Roof HW heat pump",
                    "height": ROOF_SOUTH_HEIGHT
                },
                "geometry": mapping(roof_hw_wgs84)
            },
            {
                "type": "Feature",
                "properties": {
                    "name": "Roof north stairwell",
                    "height": ROOF_NORTH_HEIGHT
                },
                "geometry": mapping(roof_north_wgs84)
            }
        ]
    }

    # Write GeoJSON output
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(geojson, f, indent=2)

    print(f"\nWrote {OUTPUT_FILE}")

    # Ground level elevation (AHD ~ sea level)
    GROUND_ELEVATION = 21.730

    # Building coordinates for polygon
    mass1_coords = [[c[0], c[1]] for c in mass1_wgs84.exterior.coords[:-1]]
    mass2_coords = [[c[0], c[1]] for c in mass2_wgs84.exterior.coords[:-1]]
    street_north_coords = [[c[0], c[1]] for c in street_north_wgs84.exterior.coords[:-1]]
    street_south_coords = [[c[0], c[1]] for c in street_south_wgs84.exterior.coords[:-1]]
    roof_stair_south_coords = [[c[0], c[1]] for c in roof_stair_south_wgs84.exterior.coords[:-1]]
    roof_hw_coords = [[c[0], c[1]] for c in roof_hw_wgs84.exterior.coords[:-1]]
    roof_north_coords = [[c[0], c[1]] for c in roof_north_wgs84.exterior.coords[:-1]]

    # Write interactive HTML viewer using Google Maps 3D (maps3d library)
    html_content = f'''<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Noone Street and Rutland Street Community Housing - 3D Building Model</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    html, body {{ margin: 0; padding: 0; height: 100%; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
    #map-container {{ width: 100%; height: 100vh; }}
    gmp-map-3d {{ display: block; width: 100%; height: 100%; }}
    #info {{
      position: absolute;
      top: 10px;
      left: 10px;
      background: white;
      padding: 12px 16px;
      border-radius: 8px;
      box-shadow: 0 2px 6px rgba(0,0,0,0.3);
      font-size: 14px;
      z-index: 1;
      max-width: 320px;
    }}
    #info h3 {{ margin: 0 0 8px 0; font-size: 15px; }}
    #info p {{ margin: 0 0 8px 0; color: #666; font-size: 12px; line-height: 1.4; }}
    #info a {{ color: #1a73e8; }}
    .note {{ font-size: 11px; color: #888; margin-top: 8px; }}
    /* Hide Google Maps alpha channel warning */
    [role="region"][aria-label*="alpha channel"] {{ display: none !important; }}
  </style>
  <script src="https://maps.googleapis.com/maps/api/js?key={api_key}&v=alpha&libraries=maps3d" async></script>
</head>
<body>
  <div id="map-container"></div>
  <div id="info">
    <h3>Noone Street and Rutland Street Community Housing</h3>
    <p>Tower: {MASS2_HEIGHT}m &bull; Roof peaks: {ROOF_SOUTH_HEIGHT}m / {ROOF_NORTH_HEIGHT}m<br>
    Podium: {MASS1_HEIGHT}m &bull; Street: {STREET_NORTH_HEIGHT}m / {STREET_SOUTH_HEIGHT}m</p>
    <p>Load <a href="index.geojson">building model</a> into <a href="https://shademap.app" target="_blank">shademap.app</a> to see shade impact at different times of day/year.</p>
    <p class="note">Use shift+drag or control+drag (depends on browser/os) to change viewing angles.</p>
  </div>

  <script>
    const GROUND = {GROUND_ELEVATION};
    const MASS1_COORDS = {json.dumps(mass1_coords)};
    const MASS2_COORDS = {json.dumps(mass2_coords)};
    const STREET_NORTH_COORDS = {json.dumps(street_north_coords)};
    const STREET_SOUTH_COORDS = {json.dumps(street_south_coords)};
    const ROOF_STAIR_SOUTH_COORDS = {json.dumps(roof_stair_south_coords)};
    const ROOF_HW_COORDS = {json.dumps(roof_hw_coords)};
    const ROOF_NORTH_COORDS = {json.dumps(roof_north_coords)};
    const MASS1_HEIGHT = {MASS1_HEIGHT};
    const MASS2_HEIGHT = {MASS2_HEIGHT};
    const STREET_NORTH_HEIGHT = {STREET_NORTH_HEIGHT};
    const STREET_SOUTH_HEIGHT = {STREET_SOUTH_HEIGHT};
    const ROOF_SOUTH_HEIGHT = {ROOF_SOUTH_HEIGHT};
    const ROOF_NORTH_HEIGHT = {ROOF_NORTH_HEIGHT};
    const CENTER_LAT = {ANCHOR_LAT - 0.0015};
    const CENTER_LNG = {ANCHOR_LON};

    async function createMap() {{
      // Import the library
      const {{ Map3DElement, Polygon3DElement, AltitudeMode, MapMode }} = await google.maps.importLibrary("maps3d");

      // Create the 3D map
      const map3D = new Map3DElement({{
        center: {{ lat: CENTER_LAT, lng: CENTER_LNG, altitude: 200 }},
        range: 400,
        tilt: 60,
        heading: 0,
        mode: MapMode.HYBRID
      }});

      map3D.style.width = '100%';
      map3D.style.height = '100%';
      document.getElementById('map-container').appendChild(map3D);

      // Create podium polygon
      const podium = new Polygon3DElement({{
        altitudeMode: AltitudeMode.ABSOLUTE,
        extruded: true,
        fillColor: "rgba(255, 140, 0, 1.0)",
        strokeColor: "rgba(200, 100, 0, 1.0)",
        strokeWidth: 2,
        drawsOccludedSegments: false
      }});
      podium.outerCoordinates = MASS1_COORDS.map(([lng, lat]) => ({{
        lat, lng, altitude: GROUND + MASS1_HEIGHT
      }}));
      map3D.appendChild(podium);

      // Create tower polygon
      const tower = new Polygon3DElement({{
        altitudeMode: AltitudeMode.ABSOLUTE,
        extruded: true,
        fillColor: "rgba(255, 140, 0, 1.0)",
        strokeColor: "rgba(200, 100, 0, 1.0)",
        strokeWidth: 2,
        drawsOccludedSegments: false
      }});
      tower.outerCoordinates = MASS2_COORDS.map(([lng, lat]) => ({{
        lat, lng, altitude: GROUND + MASS2_HEIGHT
      }}));
      map3D.appendChild(tower);

      // Create street-facing north polygon (taller)
      const streetNorth = new Polygon3DElement({{
        altitudeMode: AltitudeMode.ABSOLUTE,
        extruded: true,
        fillColor: "rgba(255, 180, 100, 1.0)",
        strokeColor: "rgba(200, 120, 50, 1.0)",
        strokeWidth: 2,
        drawsOccludedSegments: false
      }});
      streetNorth.outerCoordinates = STREET_NORTH_COORDS.map(([lng, lat]) => ({{
        lat, lng, altitude: GROUND + STREET_NORTH_HEIGHT
      }}));
      map3D.appendChild(streetNorth);

      // Create street-facing south polygon (lower)
      const streetSouth = new Polygon3DElement({{
        altitudeMode: AltitudeMode.ABSOLUTE,
        extruded: true,
        fillColor: "rgba(255, 200, 150, 1.0)",
        strokeColor: "rgba(200, 140, 80, 1.0)",
        strokeWidth: 2,
        drawsOccludedSegments: false
      }});
      streetSouth.outerCoordinates = STREET_SOUTH_COORDS.map(([lng, lat]) => ({{
        lat, lng, altitude: GROUND + STREET_SOUTH_HEIGHT
      }}));
      map3D.appendChild(streetSouth);

      // Create roof south stairwell
      const roofStairSouth = new Polygon3DElement({{
        altitudeMode: AltitudeMode.ABSOLUTE,
        extruded: true,
        fillColor: "rgba(200, 100, 50, 1.0)",
        strokeColor: "rgba(150, 70, 30, 1.0)",
        strokeWidth: 2,
        drawsOccludedSegments: false
      }});
      roofStairSouth.outerCoordinates = ROOF_STAIR_SOUTH_COORDS.map(([lng, lat]) => ({{
        lat, lng, altitude: GROUND + ROOF_SOUTH_HEIGHT
      }}));
      map3D.appendChild(roofStairSouth);

      // Create roof HW heat pump
      const roofHW = new Polygon3DElement({{
        altitudeMode: AltitudeMode.ABSOLUTE,
        extruded: true,
        fillColor: "rgba(200, 100, 50, 1.0)",
        strokeColor: "rgba(150, 70, 30, 1.0)",
        strokeWidth: 2,
        drawsOccludedSegments: false
      }});
      roofHW.outerCoordinates = ROOF_HW_COORDS.map(([lng, lat]) => ({{
        lat, lng, altitude: GROUND + ROOF_SOUTH_HEIGHT
      }}));
      map3D.appendChild(roofHW);

      // Create roof north stairwell
      const roofNorth = new Polygon3DElement({{
        altitudeMode: AltitudeMode.ABSOLUTE,
        extruded: true,
        fillColor: "rgba(200, 100, 50, 1.0)",
        strokeColor: "rgba(150, 70, 30, 1.0)",
        strokeWidth: 2,
        drawsOccludedSegments: false
      }});
      roofNorth.outerCoordinates = ROOF_NORTH_COORDS.map(([lng, lat]) => ({{
        lat, lng, altitude: GROUND + ROOF_NORTH_HEIGHT
      }}));
      map3D.appendChild(roofNorth);

      console.log('Map and polygons created');
    }}

    window.onload = createMap;
  </script>
</body>
</html>'''

    with open(HTML_FILE, 'w') as f:
        f.write(html_content)

    print(f"Wrote {HTML_FILE}")

    # Print coordinates for verification
    print("\nMass 1 coordinates (WGS84):")
    for coord in mass1_wgs84.exterior.coords:
        print(f"  [{coord[0]:.8f}, {coord[1]:.8f}]")

    print("\nMass 2 coordinates (WGS84):")
    for coord in mass2_wgs84.exterior.coords:
        print(f"  [{coord[0]:.8f}, {coord[1]:.8f}]")


if __name__ == "__main__":
    main()
