#!/usr/bin/env python3
"""Generate GeoJSON building model for Rutland St development shade assessment."""

import json
import os
import shutil
import pyproj
from shapely.geometry import Polygon, mapping
from shapely.affinity import rotate
from shapely.ops import transform

MIN_DIMENSION = 0.01  # Minimum dimension for non-shading elements (lot boundary, car park); note that google maps ignores these minimums and renders at some arbitrary minimum anyway.

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

STAIR_EAST_SETBACK = 12.408
STAIR_WEST_SETBACK = 18.492  # West edge at 22.008m from lot east (12.408 + 9.6)

STREET_NORTH_EAST_SETBACK = 4.76
STREET_SOUTH_EAST_SETBACK = 2.55
STREET_TRANSITION = 30.56  # N-S position where 9.6m transitions to 6.45m

# Stairwell shafts (cut notches into main tower east face)
SHAFT_EAST_SETBACK = 12.953  # From lot east boundary (same for both)

# North shaft (matches roof north stairwell)
NORTH_SHAFT_WIDTH = 5.0    # E-W
NORTH_SHAFT_LENGTH = 6.01  # N-S
NORTH_SHAFT_SOUTH_OFFSET = 29.17 + ANCHOR_SOUTH_OF_LOT_NORTH  # From lot north

# South shaft (matches roof south stairwell)
SOUTH_SHAFT_WIDTH = 5.59   # E-W
SOUTH_SHAFT_LENGTH = 3.67  # N-S
SOUTH_SHAFT_SOUTH_OFFSET = 47.91 + ANCHOR_SOUTH_OF_LOT_NORTH  # From lot north

# West notch (light well, aligned with north shaft)
WEST_NOTCH_LENGTH = TOWER_NORTH_SETBACK - PODIUM_SOUTH_SETBACK  # N-S extent = gap between podium and tower
WEST_NOTCH_EAST_SETBACK = LOT_WIDTH - STAIR_WEST_SETBACK  # Back of notch aligns with stair core west edge

# South notch (corridor light well, centered in tower)
SOUTH_NOTCH_WIDTH = 1.6  # E-W extent
SOUTH_NOTCH_NORTH_SETBACK = 5.09  # Back of notch from lot south boundary

CARPARK_WEST_SETBACK = 4.384
CARPARK_NORTH_SETBACK = 14.58
CARPARK_SOUTH_SETBACK = 9.035

# Fence dimensions
FENCE_HEIGHT = 1.0  # 1m decorative fence
BRICK_WIDTH = 0.1   # 10cm brick pillars
PICKET_THICKNESS = MIN_DIMENSION  # Thin fence sections

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

CARPARK_WIDTH = STAIR_WEST_SETBACK - CARPARK_WEST_SETBACK  # Extends east to stair core west edge
CARPARK_LENGTH = LOT_LENGTH - CARPARK_NORTH_SETBACK - CARPARK_SOUTH_SETBACK

# Heights (metres above ground)
PODIUM_HEIGHT = 14.3
TOWER_HEIGHT = 26.5

# Scenario definitions
SCENARIOS = [
    {
        "id": "proposal",
        "label": "Proposal (8 storeys)",
        "height_reduction": 0.0,
        "west_shift": 0.0,
        "tower_east_setback": TOWER_EAST_SETBACK,
        "include_street_masses": True,
        "fence_east_offset": 0.5,
        "description": (
            "<strong>Homes Victoria proposal as submitted</strong> &mdash; "
            "114 dwellings across 8 storeys in a podium-and-tower form with "
            "street-facing step-backs on Rutland Street."
            "<br><br>"
            "<strong>Planning context:</strong> The GRZ2 zone height limit is 9m. "
            "At 26.5m this would be the largest GRZ height override (~2.9&times;) "
            "on the Clause 52.20 register. The Municipal Planning Strategy and "
            "local building heights policy both direct mid-rise away from this "
            "location. The heritage-graded houses across Rutland Street are "
            "single-storey."
        ),
    },
    {
        "id": "six-floors",
        "label": "6 storeys",
        "height_reduction": 6.9,
        "west_shift": CARPARK_WEST_SETBACK,
        "tower_east_setback": TOWER_EAST_SETBACK,
        "include_street_masses": True,
        "fence_east_offset": 4.0,
        "description": (
            "<strong>Height reduced to 6 storeys</strong> &mdash; matching the "
            "tallest existing buildings in the suburb (210 Alexandra Parade East "
            "and 122 Roseneath Street, both 6 storeys and cited by the applicant "
            "as neighbourhood character precedent)."
            "<br><br>"
            "<strong>Key changes:</strong> Building shifted 4.4m west so external "
            "car park reaches the west lot boundary. Street-facing step-backs "
            "retained. Street fence moved to the 4.0m statutory setback line."
            "<br><br>"
            "<strong>Estimated yield:</strong> ~86&ndash;94 dwellings (vs 114 proposed). "
            "The GRZ height override drops to ~2.2&times;, within existing "
            "Clause 52.20 precedent."
        ),
    },
    {
        "id": "six-floors-no-setback",
        "label": "6 storeys, wider footprint",
        "height_reduction": 6.9,
        "west_shift": TOWER_WEST_SETBACK,  # Abut west lot boundary
        "tower_east_setback": 6.05,
        "include_street_masses": False,
        "include_carpark": False,  # Parking under wider building
        "fence_east_offset": 4.0,
        "description": (
            "<strong>Tower shifted west and widened</strong> &mdash; tower abuts "
            "the western lot boundary, east setback reduced from 10.5m to 6.1m. "
            "The wider floor plate recovers dwellings lost from the height reduction."
            "<br><br>"
            "<strong>Key changes:</strong> Street-facing step-backs eliminated for "
            "a simpler vertical form. No external car park (parking accommodated "
            "within the wider ground floor). Straight vehicle entry possible from "
            "Noone Street."
            "<br><br>"
            "<strong>Estimated yield:</strong> ~111&ndash;122 dwellings, potentially "
            "matching or exceeding the 8-storey proposal while improving compliance "
            "with the MPS, heritage adjacency, and building heights policies."
        ),
    },
    {
        "id": "six-floors-more-setback",
        "label": "6 storeys, larger setback",
        "height_reduction": 6.9,
        "west_shift": TOWER_WEST_SETBACK,  # Abut west lot boundary
        "tower_east_setback": TOWER_EAST_SETBACK,  # Original east position (shifts with west_shift)
        "include_street_masses": False,
        "include_carpark": False,
        "fence_east_offset": 4.0,
        "description": (
            "<strong>Tower shifted west with generous setback</strong> &mdash; "
            "tower abuts the western lot boundary but keeps the original east "
            "setback, creating a ~12m Rutland Street frontage."
            "<br><br>"
            "<strong>Key changes:</strong> Deep-soil planting zone, canopy trees, "
            "and front gardens along the full Rutland Street frontage. Reduced "
            "afternoon overshadowing of heritage houses across the street. No "
            "external car park. Straight vehicle entry from Noone Street."
            "<br><br>"
            "<strong>Estimated yield:</strong> ~92&ndash;94 dwellings. Maximises "
            "green space and amenity for residents and the streetscape, with the "
            "strongest planning policy compliance of all scenarios."
        ),
    },
]

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


def polygon(vertices):
    """Create polygon in UTM from list of (east_setback, south_offset) tuples relative to anchor."""
    coords = [(ANCHOR_X - e, ANCHOR_Y - s) for e, s in vertices]
    coords.append(coords[0])  # Close the polygon
    return Polygon(coords)


def make_tower_vertices(tower_east_setback, west_shift=0):
    """Compute main tower polygon vertices with shaft notches.

    Args:
        tower_east_setback: lot-relative east face position (metres from lot east boundary)
        west_shift: additional westward shift for west face and west notch only
    Returns:
        list of anchor-relative (east_setback, south_offset) tuples
    """
    ne_east = tower_east_setback - ANCHOR_WEST_OF_LOT_EAST
    ne_south = TOWER_NORTH_SETBACK - ANCHOR_SOUTH_OF_LOT_NORTH

    tower_width = LOT_WIDTH - tower_east_setback - TOWER_WEST_SETBACK
    tower_west = ne_east + tower_width + west_shift

    # East face shaft notches - constant depth from east face
    shaft_depth = SHAFT_EAST_SETBACK - TOWER_EAST_SETBACK
    shaft_east = ne_east + shaft_depth

    north_shaft_north = NORTH_SHAFT_SOUTH_OFFSET - ANCHOR_SOUTH_OF_LOT_NORTH
    north_shaft_south = north_shaft_north + NORTH_SHAFT_LENGTH
    south_shaft_north = SOUTH_SHAFT_SOUTH_OFFSET - ANCHOR_SOUTH_OF_LOT_NORTH
    south_shaft_south = south_shaft_north + SOUTH_SHAFT_LENGTH

    # West face light well notch
    west_notch_back = WEST_NOTCH_EAST_SETBACK - ANCHOR_WEST_OF_LOT_EAST + west_shift
    west_notch_south = north_shaft_south
    west_notch_north = west_notch_south - WEST_NOTCH_LENGTH

    # South face corridor notch (re-centred based on actual tower width)
    actual_width = tower_west - ne_east
    south_notch_east = ne_east + (actual_width - SOUTH_NOTCH_WIDTH) / 2
    south_notch_west = south_notch_east + SOUTH_NOTCH_WIDTH
    south_notch_south = ne_south + TOWER_LENGTH
    south_notch_north = LOT_LENGTH - SOUTH_NOTCH_NORTH_SETBACK - ANCHOR_SOUTH_OF_LOT_NORTH

    return [
        (ne_east, ne_south),                               # NE corner
        (ne_east, north_shaft_north),                      # East face to north shaft
        (shaft_east, north_shaft_north),                   # Into north shaft (west)
        (shaft_east, north_shaft_south),                   # Down north shaft back
        (ne_east, north_shaft_south),                      # Out of north shaft (east)
        (ne_east, south_shaft_north),                      # East face to south shaft
        (shaft_east, south_shaft_north),                   # Into south shaft (west)
        (shaft_east, south_shaft_south),                   # Down south shaft back
        (ne_east, south_shaft_south),                      # Out of south shaft (east)
        (ne_east, south_notch_south),                      # SE corner
        (south_notch_east, south_notch_south),             # South face to notch
        (south_notch_east, south_notch_north),             # Into south notch (north)
        (south_notch_west, south_notch_north),             # Across south notch back
        (south_notch_west, south_notch_south),             # Out of south notch (south)
        (tower_west, south_notch_south),                   # SW corner
        (tower_west, west_notch_south),                    # West face to notch
        (west_notch_back, west_notch_south),               # Into west notch (east)
        (west_notch_back, west_notch_north),               # Up west notch back
        (tower_west, west_notch_north),                    # Out of west notch (west)
        (tower_west, ne_south),                            # NW corner
    ]


# Building definitions: (name, east_setback, south_offset, width, length, height, color_group, shade_relevant)
# east_setback and south_offset are relative to anchor point
# shade_relevant: whether to include in GeoJSON for shade mapping (all included in HTML viewer)
BUILDINGS = [
    ("Northern podium",
        PODIUM_EAST_SETBACK - ANCHOR_WEST_OF_LOT_EAST,
        PODIUM_NORTH_SETBACK - ANCHOR_SOUTH_OF_LOT_NORTH,
        PODIUM_WIDTH, PODIUM_LENGTH, PODIUM_HEIGHT, "podium", True),
    ("Stair core north",
        STAIR_EAST_SETBACK - ANCHOR_WEST_OF_LOT_EAST,
        PODIUM_SOUTH_SETBACK - ANCHOR_SOUTH_OF_LOT_NORTH,
        STAIR_WIDTH, STAIR_LENGTH, TOWER_HEIGHT, "roof", True),
    ("Street-facing north",
        STREET_NORTH_EAST_SETBACK - ANCHOR_WEST_OF_LOT_EAST,
        TOWER_NORTH_SETBACK - ANCHOR_SOUTH_OF_LOT_NORTH,
        STREET_NORTH_WIDTH, STREET_NORTH_LENGTH, 9.675, "street", True),
    ("Street-facing south",
        STREET_SOUTH_EAST_SETBACK - ANCHOR_WEST_OF_LOT_EAST,
        STREET_TRANSITION - ANCHOR_SOUTH_OF_LOT_NORTH,
        STREET_SOUTH_WIDTH, STREET_SOUTH_LENGTH, 6.45, "street", True),
    ("Roof south stairwell",      9.403, 47.91,   5.59,    3.67,  28.65, "roof", True),
    ("Roof HW heat pump",        14.75,  52.24,   7.66,    5.16,  28.4, "roof", True),
    ("Roof north stairwell",      8.858, 29.17,   5.0,     6.01,  27.5,  "roof", True),
    ("Car park west",
        LOT_WIDTH - STAIR_WEST_SETBACK - ANCHOR_WEST_OF_LOT_EAST,  # East edge at stair core west edge
        CARPARK_NORTH_SETBACK - ANCHOR_SOUTH_OF_LOT_NORTH,
        CARPARK_WIDTH, CARPARK_LENGTH, MIN_DIMENSION, "carpark", False),
]

# Lot boundary frame
FRAME_THICK = MIN_DIMENSION
LOT_BOUNDARY = [
    ("Lot boundary N", LOT_NE_EAST_SETBACK, LOT_NE_SOUTH_OFFSET, LOT_WIDTH, FRAME_THICK, FRAME_THICK, "lot", False),
    ("Lot boundary S", LOT_NE_EAST_SETBACK, LOT_NE_SOUTH_OFFSET + LOT_LENGTH - FRAME_THICK, LOT_WIDTH, FRAME_THICK, FRAME_THICK, "lot", False),
    ("Lot boundary E", LOT_NE_EAST_SETBACK, LOT_NE_SOUTH_OFFSET + FRAME_THICK, FRAME_THICK, LOT_LENGTH - 2 * FRAME_THICK, FRAME_THICK, "lot", False),
    ("Lot boundary W", LOT_NE_EAST_SETBACK + LOT_WIDTH - FRAME_THICK, LOT_NE_SOUTH_OFFSET + FRAME_THICK, FRAME_THICK, LOT_LENGTH - 2 * FRAME_THICK, FRAME_THICK, "lot", False),
]

# North fence (extends north from podium toward lot north boundary)
_nfence_south = PODIUM_NORTH_SETBACK - ANCHOR_SOUTH_OF_LOT_NORTH
_nfence_north = LOT_NE_SOUTH_OFFSET + 0.5
_nfence_span = _nfence_south - _nfence_north
_nfence_east = PODIUM_EAST_SETBACK - ANCHOR_WEST_OF_LOT_EAST
_nfence_width = PODIUM_WIDTH

NORTH_FENCE = [
    ("North fence brick S", _nfence_east, _nfence_south - BRICK_WIDTH,
     _nfence_width, BRICK_WIDTH, FENCE_HEIGHT, "podium", False),
    ("North fence brick N", _nfence_east, _nfence_north,
     _nfence_width, BRICK_WIDTH, FENCE_HEIGHT, "podium", False),
    ("North fence picket", _nfence_east, _nfence_north + BRICK_WIDTH,
     _nfence_width, _nfence_span - 2 * BRICK_WIDTH, FENCE_HEIGHT, "fence", False),
]

# Brick colours from architectural drawings
COLORS = {
    "tower":   ("rgba(176, 128, 112, 1.0)", "rgba(140, 100, 88, 1.0)"),   # Lighter pinkish-red brick
    "podium":  ("rgba(140, 68, 68, 1.0)",   "rgba(100, 48, 48, 1.0)"),    # Deeper red-brown brick
    "street":  ("rgba(140, 68, 68, 1.0)",   "rgba(100, 48, 48, 1.0)"),    # Deeper red-brown brick
    "roof":    ("rgba(128, 128, 128, 1.0)", "rgba(96, 96, 96, 1.0)"),     # Grey
    "carpark": ("rgba(80, 80, 80, 1.0)",    "rgba(60, 60, 60, 1.0)"),     # Dark grey
    "lot":     ("rgba(0, 120, 255, 1.0)",   "rgba(0, 80, 200, 1.0)"),     # Bright blue
    "fence":   ("rgba(0, 0, 0, 0.7)",       "rgba(0, 0, 0, 0.9)"),        # Black picket fence
}


def build_legend(tower_height, include_street_masses, include_carpark=True):
    """Build legend HTML for a scenario."""
    items = [
        f'<div class="legend-item"><span class="legend-swatch" style="background:rgb(176,128,112)"></span>Main tower ({tower_height}m)</div>',
    ]
    if include_street_masses:
        items.append('<div class="legend-item"><span class="legend-swatch" style="background:rgb(140,68,68)"></span>Podium (14.3m) / Street (9.675m, 6.45m)</div>')
    else:
        items.append('<div class="legend-item"><span class="legend-swatch" style="background:rgb(140,68,68)"></span>Podium (14.3m)</div>')
    items.append('<div class="legend-item"><span class="legend-swatch" style="background:rgb(128,128,128)"></span>Roof plant &amp; stairs</div>')
    if include_carpark:
        items.append('<div class="legend-item"><span class="legend-swatch" style="background:rgb(80,80,80)"></span>Car park (external overflow)</div>')
    items.append('<div class="legend-item"><span class="legend-swatch" style="background:rgb(0,120,255)"></span>Lot boundary</div>')
    return '\n      '.join(items)


def generate_scenario(scenario):
    """Generate building model for a single scenario.

    Returns (features, js_buildings, legend_html).
    """
    features = []
    js_buildings = []

    west_shift = scenario["west_shift"]
    height_reduction = scenario["height_reduction"]
    tower_east_setback = scenario["tower_east_setback"]
    include_street_masses = scenario["include_street_masses"]
    fence_east_offset = scenario["fence_east_offset"]

    east_face_shift = TOWER_EAST_SETBACK - tower_east_setback

    def add_building(poly, name, height, color_group, shade_relevant):
        """Process a building polygon and add to output lists."""
        rotated = rotate(poly, ROTATION_DEG, origin=(ANCHOR_X, ANCHOR_Y))
        wgs84 = transform(_to_wgs84, rotated)

        if shade_relevant:
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

    # Compute street fence for this scenario
    # Fence always ~2.05m wide, positioned at the building's east face
    original_fence_width = ANCHOR_WEST_OF_LOT_EAST - 0.5  # 2.05m
    if include_street_masses:
        sfence_west = (STREET_SOUTH_EAST_SETBACK - ANCHOR_WEST_OF_LOT_EAST) + west_shift
        sfence_east = LOT_NE_EAST_SETBACK + fence_east_offset
    else:
        # Fence abuts the building east face, wherever it ends up
        building_east = tower_east_setback - ANCHOR_WEST_OF_LOT_EAST
        if east_face_shift == 0:
            building_east += west_shift
        sfence_west = building_east
        sfence_east = building_east - original_fence_width
    sfence_width = sfence_west - sfence_east

    sfence_north = NORTH_SHAFT_SOUTH_OFFSET + NORTH_SHAFT_LENGTH - ANCHOR_SOUTH_OF_LOT_NORTH
    sfence_south = LOT_LENGTH - TOWER_SOUTH_SETBACK - ANCHOR_SOUTH_OF_LOT_NORTH
    sfence_span = sfence_south - sfence_north

    street_fence = [
        ("Street fence brick N", sfence_east, sfence_north,
         sfence_width, BRICK_WIDTH, FENCE_HEIGHT, "podium", False),
        ("Street fence brick S", sfence_east, sfence_south - BRICK_WIDTH,
         sfence_width, BRICK_WIDTH, FENCE_HEIGHT, "podium", False),
        ("Street fence picket", sfence_east, sfence_north + BRICK_WIDTH,
         sfence_width, sfence_span - 2 * BRICK_WIDTH, FENCE_HEIGHT, "fence", False),
    ]

    # Filter buildings per scenario config
    include_carpark = scenario.get("include_carpark", True)
    buildings = [b for b in BUILDINGS
                 if (include_street_masses or b[6] != "street")
                 and (include_carpark or b[6] != "carpark")]

    all_boxes = buildings + LOT_BOUNDARY + NORTH_FENCE + street_fence

    for name, east, south, width, length, height, color_group, shade_relevant in all_boxes:
        is_east_face_item = name in ("Roof south stairwell", "Roof north stairwell")

        # Apply positional shift (not to lot boundary, podium, or fences)
        if color_group not in ("lot", "fence") and name != "Northern podium" and "fence" not in name.lower():
            if is_east_face_item and east_face_shift != 0:
                # East-face items move with the east face, not the general west shift
                east -= east_face_shift
            else:
                east += west_shift

        if height > PODIUM_HEIGHT:  # Taller than podium = part of main tower mass
            height -= height_reduction

        poly = box(east, south, width, length)
        add_building(poly, name, height, color_group, shade_relevant)

    # Process main tower (complex polygon with shaft notches)
    tower_height = TOWER_HEIGHT - height_reduction
    if east_face_shift == 0:
        # Scenarios with original east setback: compute base vertices, apply uniform shift
        tower_verts = make_tower_vertices(TOWER_EAST_SETBACK)
        tower_verts = [(e + west_shift, s) for e, s in tower_verts]
    else:
        # Different east setback: west_shift applied only to west face inside function
        tower_verts = make_tower_vertices(tower_east_setback, west_shift=west_shift)

    poly = polygon(tower_verts)
    add_building(poly, "Main tower", tower_height, "tower", True)

    legend = build_legend(tower_height, include_street_masses, include_carpark)

    return features, js_buildings, legend


def write_html(api_key, flat_map_id, all_scenarios):
    """Write the HTML viewer with scenario switching support."""
    # Determine view mode options based on whether flat map ID is configured
    if flat_map_id:
        view_options = '''
        <option value="3d" selected>3D Surrounds</option>
        <option value="flat">Flat Surrounds</option>'''
        deckgl_script = '<script src="https://unpkg.com/deck.gl@latest/dist.min.js"></script>'
    else:
        view_options = '''
        <option value="3d" selected>3D Surrounds</option>'''
        deckgl_script = ''

    # Build scenario select options
    scenario_options = '\n        '.join(
        f'<option value="{s["id"]}"{" selected" if s["id"] == "proposal" else ""}>{s["label"]}</option>'
        for s in all_scenarios
    )

    # Build JS scenarios object
    scenarios_js = json.dumps({
        s["id"]: {
            "buildings": s["js_buildings"],
            "legend": s["legend"],
            "geojson": f'{s["id"]}.geojson',
            "label": s["label"],
            "description": s["description"],
        }
        for s in all_scenarios
    })

    html = f'''<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Noone St / Rutland St Community Housing - 3D Model</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    html, body {{ margin: 0; padding: 0; height: 100%; font-family: system-ui, sans-serif; }}
    .map-container {{ position: absolute; top: 0; left: 0; width: 100%; height: 100vh; }}
    .map-container.hidden {{ display: none; }}
    gmp-map-3d {{ display: block; width: 100%; height: 100%; }}
    .note {{ font-size: 11px; color: #888; margin-top: 8px; }}
    .legend {{ margin-top: 10px; padding-top: 10px; border-top: 1px solid #eee; }}
    .legend-item {{ display: flex; align-items: center; gap: 8px; margin: 4px 0; font-size: 11px; }}
    .legend-swatch {{ width: 14px; height: 14px; border-radius: 2px; flex-shrink: 0; }}
    .toggle {{ display: block; margin-top: 10px; font-size: 12px; cursor: pointer; }}
    .view-mode {{ margin-top: 10px; padding-top: 10px; border-top: 1px solid #eee; }}
    .view-mode label {{ font-size: 12px; font-weight: 500; display: block; margin-bottom: 6px; }}
    .view-mode select {{ font-size: 12px; padding: 4px 8px; border-radius: 4px; border: 1px solid #ccc; width: 100%; }}
    .scenario-mode {{ margin-bottom: 10px; padding-bottom: 10px; border-bottom: 1px solid #eee; }}
    .scenario-mode label {{ font-size: 12px; font-weight: 500; display: block; margin-bottom: 6px; }}
    .scenario-mode select {{ font-size: 12px; padding: 4px 8px; border-radius: 4px; border: 1px solid #ccc; width: 100%; }}
    details {{ margin-top: 6px; }}
    details summary {{ cursor: pointer; font-size: 12px; font-weight: 500; color: #333; padding: 4px 0; }}
    details summary::-webkit-details-marker {{ margin-right: 4px; }}
    details[open] summary {{ margin-bottom: 6px; }}
    .scenario-desc {{ font-size: 11px; color: #555; line-height: 1.5; }}
    #info-panels {{ position: absolute; top: 10px; left: 10px; z-index: 1; max-width: 340px; display: flex; flex-direction: column; gap: 8px; max-height: calc(100vh - 20px); }}
    .info-panel {{ background: white; padding: 12px 16px; border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.3); font-size: 14px; overflow-y: auto; }}
    .info-panel h3 {{ margin: 0 0 8px; font-size: 15px; }}
    .info-panel p {{ margin: 0 0 8px; color: #666; font-size: 12px; line-height: 1.4; }}
    .info-panel a {{ color: #1a73e8; }}
    /* Hide Google Maps alpha channel warning */
    [role="region"][aria-label*="alpha channel"] {{ display: none !important; }}
  </style>
  <script src="https://maps.googleapis.com/maps/api/js?key={api_key}&v=alpha&libraries=maps3d" async></script>
  {deckgl_script}
</head>
<body>
  <div id="map3d" class="map-container"></div>
  <div id="mapFlat" class="map-container hidden"></div>
  <div id="info-panels">
    <div class="info-panel">
      <h3>Noone St / Rutland St Community Housing</h3>
      <div class="scenario-mode">
        <label>Scenario</label>
        <select id="scenarioSelect">
          {scenario_options}
        </select>
      </div>
      <details open>
        <summary>Map controls</summary>
        <p>Load <a id="geojsonLink" href="proposal.geojson" download>building model</a> into
           <a href="https://shademap.app" target="_blank">shademap.app</a> for shade analysis.</p>
        <div id="legend" class="legend">
        </div>
        <p class="note">Shift+drag or Ctrl+drag to change viewing angle.</p>
        <div class="view-mode">
          <label>View mode</label>
          <select id="viewMode">{view_options}
          </select>
        </div>
        <label class="toggle"><input type="checkbox" id="occluded"> Show through existing buildings</label>
      </details>
    </div>
    <div class="info-panel">
      <details open>
        <summary>Scenario details</summary>
        <div id="scenarioDesc" class="scenario-desc"></div>
      </details>
    </div>
  </div>
  <script>
    const CENTER = {{ lat: {ANCHOR_LAT - 0.001}, lng: {ANCHOR_LON - 0.0001} }};
    const GROUND = {GROUND_RL};
    const SCENARIOS = {scenarios_js};
    const FLAT_MAP_ID = "{flat_map_id}";

    // Parse rgba string to [r,g,b,a] array for deck.gl
    function parseRgba(rgba) {{
      const match = rgba.match(/rgba?\\((\\d+),\\s*(\\d+),\\s*(\\d+)(?:,\\s*([\\d.]+))?\\)/);
      if (!match) return [128, 128, 128, 200];
      return [
        parseInt(match[1]),
        parseInt(match[2]),
        parseInt(match[3]),
        Math.round((match[4] !== undefined ? parseFloat(match[4]) : 1) * 255)
      ];
    }}

    async function init() {{
      const {{ Map3DElement, Polygon3DElement, AltitudeMode, MapMode }} = await google.maps.importLibrary("maps3d");

      // 3D map (full photorealistic) with Polygon3DElement
      const map3d = new Map3DElement({{
        center: {{ ...CENTER, altitude: 80 }},
        range: 200, tilt: 60, heading: 0, mode: MapMode.HYBRID
      }});
      map3d.style.width = map3d.style.height = "100%";
      document.getElementById("map3d").appendChild(map3d);

      let polygons3d = [];
      let overlay = null;
      const occludedCheckbox = document.getElementById("occluded");

      // Flat map setup (only if Map ID configured)
      let mapFlat = null;
      if (FLAT_MAP_ID && typeof deck !== "undefined") {{
        mapFlat = new google.maps.Map(document.getElementById("mapFlat"), {{
          center: {{ ...CENTER, lat: {ANCHOR_LAT} }},
          zoom: 19,
          tilt: 60,
          heading: 0,
          mapId: FLAT_MAP_ID
        }});
        overlay = new deck.GoogleMapsOverlay({{ layers: [] }});
        overlay.setMap(mapFlat);
      }}

      function loadScenario(id) {{
        const scenario = SCENARIOS[id];
        if (!scenario) return;

        // Remove existing 3D polygons
        for (const p of polygons3d) p.remove();
        polygons3d = [];

        // Create new 3D polygons
        const drawsOccluded = occludedCheckbox.checked;
        for (const b of scenario.buildings) {{
          const poly = new Polygon3DElement({{
            altitudeMode: AltitudeMode.ABSOLUTE,
            extruded: true,
            fillColor: b.fill,
            strokeColor: b.stroke,
            strokeWidth: 2,
            drawsOccludedSegments: drawsOccluded
          }});
          poly.outerCoordinates = b.coords.map(([lng, lat]) => ({{
            lat, lng, altitude: GROUND + b.height
          }}));
          map3d.appendChild(poly);
          polygons3d.push(poly);
        }}

        // Update deck.gl overlay
        if (overlay) {{
          const deckData = scenario.buildings.map(b => ({{
            polygon: b.coords.map(([lng, lat]) => [lng, lat]),
            height: b.height,
            fillColor: parseRgba(b.fill),
            strokeColor: parseRgba(b.stroke)
          }}));
          overlay.setProps({{
            layers: [new deck.PolygonLayer({{
              id: "buildings",
              data: deckData,
              extruded: true,
              wireframe: true,
              getPolygon: d => d.polygon,
              getElevation: d => d.height,
              getFillColor: d => d.fillColor,
              getLineColor: d => d.strokeColor,
              getLineWidth: 2,
              pickable: true
            }})]
          }});
        }}

        // Update legend, download link, and scenario description
        document.getElementById("legend").innerHTML = scenario.legend;
        document.getElementById("geojsonLink").href = scenario.geojson;
        document.getElementById("scenarioDesc").innerHTML = scenario.description;
      }}

      // Initial load
      loadScenario("proposal");

      // Scenario switching
      document.getElementById("scenarioSelect").addEventListener("change", (e) => {{
        loadScenario(e.target.value);
      }});

      // View mode switching
      document.getElementById("viewMode").addEventListener("change", (e) => {{
        const is3d = e.target.value === "3d";
        document.getElementById("map3d").classList.toggle("hidden", !is3d);
        document.getElementById("mapFlat").classList.toggle("hidden", is3d);
      }});

      // Occlusion toggle (3D mode only)
      occludedCheckbox.addEventListener("change", (e) => {{
        for (const p of polygons3d) p.drawsOccludedSegments = e.target.checked;
      }});
    }}

    window.onload = init;
  </script>
</body>
</html>'''

    with open("index.html", "w") as f:
        f.write(html)
    print("Wrote index.html")


def main():
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        raise SystemExit("Error: GOOGLE_MAPS_API_KEY not set")

    flat_map_id = os.environ.get("GOOGLE_MAPS_FLAT_MAP_ID", "")

    all_scenarios = []
    for scenario in SCENARIOS:
        features, js_buildings, legend = generate_scenario(scenario)

        geojson = {"type": "FeatureCollection", "features": features}
        filename = f'{scenario["id"]}.geojson'
        with open(filename, "w") as f:
            json.dump(geojson, f, indent=2)
        print(f"Wrote {filename}")

        all_scenarios.append({
            "id": scenario["id"],
            "label": scenario["label"],
            "js_buildings": js_buildings,
            "legend": legend,
            "description": scenario["description"],
        })

    # Backward compat: index.geojson is a copy of proposal.geojson
    shutil.copy("proposal.geojson", "index.geojson")
    print("Wrote index.geojson")

    write_html(api_key, flat_map_id, all_scenarios)


if __name__ == "__main__":
    main()
