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
STREET_SOUTH_EAST_SETBACK = 3.45  # East face of southern street mass from lot east boundary (porch protrudes to 2.55m but is not modelled)
STREET_TRANSITION = 30.56  # N-S position where 9.6m transitions to 6.45m
STREET_SHAFT_INFILL_EAST_SETBACK = 2.85 + 4.758  # 7.608m from lot east boundary

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

CARPARK_ENTRANCE_WIDTH = 6.4          # E-W width of vehicle access driveway
CARPARK_ENTRANCE_WEST_SETBACK = 9.284  # Western edge from lot west boundary
CARPARK_ENTRANCE_LOT_OVERHANG = 3.0   # How far past lot boundary entrance extends to reach street
# Anchor-relative east setback of entrance NE corner (eastern edge of entrance)
CARPARK_ENTRANCE_EAST_SETBACK = (LOT_WIDTH - CARPARK_ENTRANCE_WEST_SETBACK - CARPARK_ENTRANCE_WIDTH) - ANCHOR_WEST_OF_LOT_EAST

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
# Southern mass runs from tower south end northward to southern edge of northern stairwell notch
STREET_SOUTH_NORTH_EDGE = NORTH_SHAFT_SOUTH_OFFSET + NORTH_SHAFT_LENGTH  # Where it ends (from lot north)
STREET_SOUTH_LENGTH = (LOT_LENGTH - TOWER_SOUTH_SETBACK) - STREET_SOUTH_NORTH_EDGE

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
        "carpark_access": "south",
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
        "id": "six-floors-tier1",
        "label": "6 storeys (Tier 1)",
        "height_reduction": 6.4,
        "west_shift": 0.0,
        "tower_east_setback": TOWER_EAST_SETBACK,
        "include_street_masses": True,
        "carpark_access": "south",
        "fence_east_offset": 0.5,
        "street_south_east_setback": 4.0,  # Complies with 4.0m minimum (proposal has 3.45m)
        "description": (
            "<strong>Height reduced to 6 storeys, Tier 1</strong> &mdash; "
            "Proposal form retained: same tower position, street-facing step-backs, car park, "
            "and fence. Height reduced from 26.5m to 20.1m. Southern street-facing mass pulled "
            "back 0.55m to comply with the 4.0m minimum setback from Rutland Street "
            "(proposal has 3.45m). No westward shift; no AS5100 assessment required."
        ),
    },
    {
        "id": "six-floors-tier2-moderate",
        "label": "6 storeys (Tier 2, Mod 3 Option B)",
        "height_reduction": 6.4,
        "west_shift": CARPARK_WEST_SETBACK,
        "tower_east_setback": TOWER_EAST_SETBACK,
        "include_street_masses": False,
        "carpark_access": "south",
        "fence_east_offset": 4.0,
        "description": (
            "<strong>Height reduced to 6 storeys with moderate westward adjustment</strong> &mdash; "
            "Building shifted 4.4m west (Modification 3 Option B), increasing Rutland Street setback "
            "to approximately 6m for front gardens and canopy trees. Tower widens from 21.9m "
            "to 26.3m, partially recovering dwellings lost from height reduction. Maximum westward "
            "shift achievable without reconfiguring the external car park."
            "<br><br>"
            "<strong>Planning benefits:</strong> Height override drops to 2.2&times; the GRZ2 9m limit "
            "(within Clause 52.20 precedent range). Landscaping zone enables deep soil "
            "planting, indigenous canopy trees per Yarra Nature Strategy, and verifiable on-site "
            "canopy coverage (addressing current reliance on offsite council trees). Better "
            "heritage interface with buffer to contributory Victorian terraces."
            "<br><br>"
            "<strong>Key features:</strong> Vehicle access from Alexandra Parade East retained with "
            "external overflow car park. Simpler vertical form without street-facing step-backs. "
            "Pervious surface area partially addressing Clause 52.20-6.3 permeability shortfall. "
            "Subject to AS5100 railway clearance risk assessment (building 15-16m from stabling "
            "siding centreline)."
            "<br><br>"
            "<strong>Estimated yield:</strong> Approximately 95-100 dwellings (vs 114 proposed), "
            "maintaining a 3.2-3.3&times; multiplier over existing 30 units with superior planning outcomes."
        ),
    },
    {
        "id": "six-floors-tier2-maximum",
        "label": "6 storeys (Tier 2, Mod 3 Option C)",
        "height_reduction": 6.4,
        "west_shift": TOWER_WEST_SETBACK,
        "tower_east_setback": TOWER_EAST_SETBACK,
        "include_street_masses": False,
        "include_carpark": False,
        "carpark_access": "north",
        "carpark_entrance_west_setback": 1.5,
        "fence_east_offset": 4.0,
        "description": (
            "<strong>Height reduced to 6 storeys with maximum westward adjustment</strong> &mdash; "
            "Building shifted 8.1m west (Modification 3 Option C) to the western lot boundary, "
            "creating 8-12m Rutland Street setback for a generous garden precinct. Tower widens "
            "from 21.9m to 30.0m, maximising floor plate efficiency to recover dwellings."
            "<br><br>"
            "<strong>Planning benefits:</strong> Maximum landscaping and green space of all "
            "scenarios. Deep setback enables substantial canopy tree planting, front gardens for "
            "all ground-floor dwellings, and enhanced streetscape quality consistent with Clifton "
            "Hill's garden suburb character. Height override at 2.2&times; the GRZ2 limit matches "
            "strongest compliance position. Reduced afternoon overshadowing of heritage houses."
            "<br><br>"
            "<strong>Key features:</strong> Superior heritage interface with maximum buffer zone. "
            "Substantial pervious surface area and verified on-site canopy coverage. Vehicle access "
            "from Noone Street with optimal circulation geometry. Parking fully accommodated under "
            "building. Simpler vertical massing. Subject to AS5100 railway clearance risk assessment "
            "(building 12-14m from stabling siding centreline, deeper into 10-20m zone but still "
            "well clear of 10m threshold)."
            "<br><br>"
            "<strong>Estimated yield:</strong> Approximately 95-105 dwellings (vs 114 proposed), "
            "maintaining a 3.2-3.5&times; multiplier over existing 30 units. Represents optimal balance "
            "between housing delivery and planning policy compliance with maximum amenity outcomes "
            "for residents and streetscape."
        ),
    },
    {
        "id": "proposal-6m-south",
        "label": "Proposal with 6m south setback",
        "height_reduction": 0.0,
        "west_shift": 0.0,
        "tower_east_setback": TOWER_EAST_SETBACK,
        "include_street_masses": True,
        "carpark_access": "south",
        "fence_east_offset": 0.5,
        "tower_south_setback": 6.0,
        "description": (
            "<strong>Original proposal with 6m southern setback</strong> &mdash; "
            "identical to the submitted proposal but with the building pulled back "
            "6m from the southern lot boundary (vs 0.5m in the original)."
            "<br><br>"
            "<strong>Key changes:</strong> Tower length reduced from 65.7m to 60.2m "
            "to accommodate the larger southern setback. Street-facing southern mass "
            "shortened correspondingly. All other dimensions and positions unchanged."
            "<br><br>"
            "<strong>Estimated yield:</strong> Slightly reduced from the 114-dwelling "
            "proposal due to shortened floor plate. Improved southern boundary clearance "
            "for deep-soil planting and neighbour amenity."
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


def make_tower_vertices(tower_east_setback, west_shift=0, tower_south_setback=None):
    """Compute main tower polygon vertices with shaft notches.

    Args:
        tower_east_setback: lot-relative east face position (metres from lot east boundary)
        west_shift: additional westward shift for west face and west notch only
        tower_south_setback: optional override for south setback (metres from lot south boundary)
    Returns:
        list of anchor-relative (east_setback, south_offset) tuples
    """
    if tower_south_setback is None:
        tower_south_setback = TOWER_SOUTH_SETBACK

    tower_length = LOT_LENGTH - TOWER_NORTH_SETBACK - tower_south_setback

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
    south_notch_south = ne_south + tower_length
    # Notch depth from tower south edge (constant depth from original design)
    # Original: 5.09m from lot - 0.492m tower setback = 4.598m from tower edge
    NOTCH_DEPTH_FROM_TOWER_EDGE = SOUTH_NOTCH_NORTH_SETBACK - TOWER_SOUTH_SETBACK
    south_notch_north = south_notch_south - NOTCH_DEPTH_FROM_TOWER_EDGE

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
    ("Podium-street infill",
        STREET_NORTH_EAST_SETBACK - ANCHOR_WEST_OF_LOT_EAST,
        PODIUM_SOUTH_SETBACK - ANCHOR_SOUTH_OF_LOT_NORTH,
        STAIR_EAST_SETBACK - STREET_NORTH_EAST_SETBACK,
        STAIR_LENGTH, 6.45, "street", True),
    ("Street-facing north",
        STREET_NORTH_EAST_SETBACK - ANCHOR_WEST_OF_LOT_EAST,
        TOWER_NORTH_SETBACK - ANCHOR_SOUTH_OF_LOT_NORTH,
        STREET_NORTH_WIDTH, STREET_NORTH_LENGTH, 9.675, "street", True),
    ("Street-facing shaft infill",
        STREET_SHAFT_INFILL_EAST_SETBACK - ANCHOR_WEST_OF_LOT_EAST,
        STREET_TRANSITION - ANCHOR_SOUTH_OF_LOT_NORTH,  # North edge aligns with northern mass south edge
        SHAFT_EAST_SETBACK - STREET_SHAFT_INFILL_EAST_SETBACK,
        (NORTH_SHAFT_SOUTH_OFFSET + NORTH_SHAFT_LENGTH) - STREET_TRANSITION,  # Extends to south edge of shaft notch
        6.45, "street", True),
    ("Street-facing south",
        STREET_SOUTH_EAST_SETBACK - ANCHOR_WEST_OF_LOT_EAST,
        STREET_SOUTH_NORTH_EDGE - ANCHOR_SOUTH_OF_LOT_NORTH,  # NE corner at north end of mass
        STREET_SOUTH_WIDTH, STREET_SOUTH_LENGTH, 6.45, "street", True),
    ("Street-facing south shaft infill",
        TOWER_EAST_SETBACK - ANCHOR_WEST_OF_LOT_EAST,
        SOUTH_SHAFT_SOUTH_OFFSET - ANCHOR_SOUTH_OF_LOT_NORTH,
        SHAFT_EAST_SETBACK - TOWER_EAST_SETBACK,  # Notch depth
        SOUTH_SHAFT_LENGTH,
        6.45, "street", True),
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
    ("North fence brick E", _nfence_east, _nfence_north,
     BRICK_WIDTH, _nfence_span, FENCE_HEIGHT, "podium", False),
    ("North fence brick W", _nfence_east + _nfence_width - BRICK_WIDTH, _nfence_north,
     BRICK_WIDTH, _nfence_span, FENCE_HEIGHT, "podium", False),
    ("North fence picket", _nfence_east + BRICK_WIDTH, _nfence_north,
     _nfence_width - 2 * BRICK_WIDTH, PICKET_THICKNESS, FENCE_HEIGHT, "fence", False),
]

# Colours from architectural material samples
COLORS = {
    "tower":   ("rgba(210, 160, 140, 1.0)", "rgba(190, 140, 120, 1.0)"),  # Light salmon/peachy brick (main tower)
    "podium":  ("rgba(180, 100, 80, 1.0)",  "rgba(160, 80, 60, 1.0)"),    # Red-orange brick (podium/street)
    "street":  ("rgba(180, 100, 80, 1.0)",  "rgba(160, 80, 60, 1.0)"),    # Red-orange brick (podium/street)
    "roof":    ("rgba(220, 210, 195, 1.0)", "rgba(200, 190, 175, 1.0)"),  # Light cream/beige (stair cores)
    "carpark": ("rgba(80, 80, 80, 1.0)",    "rgba(60, 60, 60, 1.0)"),     # Dark grey
    "lot":     ("rgba(0, 120, 255, 1.0)",   "rgba(0, 80, 200, 1.0)"),     # Bright blue
    "fence":   ("rgba(0, 0, 0, 0.7)",       "rgba(0, 0, 0, 0.9)"),        # Black picket fence
    "terrace": ("rgba(100, 48, 32, 1.0)",   "rgba(80, 35, 22, 1.0)"),     # Dark Victorian red brick
}

# Victorian terrace house on east side of Rutland St (context building, all scenarios)
# Coordinate is front centre of veranda (westernmost point, N-S midpoint)
TERRACE_VERANDA_FRONT_LAT = -37.794248
TERRACE_VERANDA_FRONT_LON = 144.996166
TERRACE_WEST_OFFSET = -0.20     # Fine-tune shift west from reference coordinate (metres)
TERRACE_SOUTH_OFFSET = 0.30     # Fine-tune shift south from reference coordinate (metres)
TERRACE_HOUSE_WIDTH = 5.0       # N-S outer dimension
TERRACE_NORTH_WALL = 0.25       # North parapet wall thickness (double brick)
TERRACE_SOUTH_WALL = 0.15       # South parapet wall thickness (party wall side)
TERRACE_LOT_WIDTH = 19 * 0.3048 + 3 * 0.0254  # 19'3" = 5.867m N-S (for future fence)
TERRACE_TOTAL_DEPTH = 13.65     # E-W total depth including veranda
TERRACE_VERANDA_DEPTH = 1.5     # E-W veranda depth (west of front wall)
TERRACE_VERANDA_HEIGHT = 3.0    # Ground to top of veranda at front posts (west)
TERRACE_VERANDA_DROP = 0.30     # Descent from building wall to front posts
TERRACE_WALL_HEIGHT = 4.4       # Ground to top of brick parapet walls (front/rear)
TERRACE_EAVE_HEIGHT = 3.8       # Ground to eave at north/south side walls
TERRACE_RIDGE_HEIGHT = 5.4      # Ground to pitched roof ridge
TERRACE_HIP_LENGTH = 2.5        # E-W length of hip at rear (east) end
TERRACE_PAIR_GAP = 0.8          # Free space on each side of a semi-detached pair (metres)
TERRACE_PAIR_PITCH = 2 * TERRACE_HOUSE_WIDTH + 2 * TERRACE_PAIR_GAP  # 11.6m

# All pairs in the block, north-to-south
# (index_from_ref, (north_house, south_house), south_fine_tune_metres)
# index 0 = reference pair; positive index = south; negative = north
# Adjust south_fine_tune to nudge individual pairs
TERRACE_PAIRS = [
    ( 2, ("28", "26"), 0.0),
    ( 1, ("24", "22"), 0.0),
    ( 0, ("20", "18"), 0.0),
    (-1, ("16", "14"), 0.1),
    (-2, ("12", "10"), 0.4),
    (-3, ( "8",  "6"), 0.7),
    (-4, ( "4",  "2"), 1.0),
]


def _make_context_buildings():
    """Compute context building data (terrace houses).

    Returns dict with js_buildings (HTML viewer), wgs84_features, and utm_features (GeoJSON).
    Buildings extend east from the given veranda front coordinate, rotated to street alignment.
    """
    tx, ty = _to_utm(TERRACE_VERANDA_FRONT_LON, TERRACE_VERANDA_FRONT_LAT)
    tx -= TERRACE_WEST_OFFSET
    ty -= TERRACE_SOUTH_OFFSET
    half_w = TERRACE_HOUSE_WIDTH / 2
    fill, stroke = COLORS["terrace"]

    js_buildings = []
    wgs84_features = []
    utm_features = []

    def _add(poly, name, height):
        rotated = rotate(poly, ROTATION_DEG, origin=(tx, ty))
        wgs84 = transform(_to_wgs84, rotated)
        js_buildings.append({"coords": list(wgs84.exterior.coords[:-1]), "height": height, "fill": fill, "stroke": stroke})
        props = {"name": name, "height": height}
        wgs84_features.append({"type": "Feature", "properties": props, "geometry": mapping(wgs84)})
        utm_features.append({"type": "Feature", "properties": props, "geometry": mapping(rotated)})

    def add_house(ty_centre, north_t, south_t, label):
        """Add one terrace house centred at ty_centre with given wall thicknesses."""
        half_w = TERRACE_HOUSE_WIDTH / 2
        roof_x1 = tx + TERRACE_VERANDA_DEPTH
        roof_x2 = tx + TERRACE_TOTAL_DEPTH

        # Veranda: stepped strips sloping from building wall (high) to front posts (low)
        n_vsteps = 4
        vstep_w = TERRACE_VERANDA_DEPTH / n_vsteps
        veranda_strip_data = []
        for i in range(n_vsteps):
            t = i / (n_vsteps - 1)
            strip_h = TERRACE_VERANDA_HEIGHT + t * TERRACE_VERANDA_DROP
            sx_west = tx + i * vstep_w
            sx_east = tx + (i + 1) * vstep_w
            veranda_strip_data.append((
                Polygon([(sx_west, ty_centre + half_w), (sx_east, ty_centre + half_w),
                         (sx_east, ty_centre - half_w), (sx_west, ty_centre - half_w)]),
                f"{label} veranda strip {i + 1}", strip_h,
            ))
        for poly, name, h in reversed(veranda_strip_data):
            _add(poly, name, h)

        # Main body
        _add(Polygon([(roof_x1, ty_centre + half_w), (roof_x2, ty_centre + half_w),
                      (roof_x2, ty_centre - half_w), (roof_x1, ty_centre - half_w)]),
             f"{label} main body", TERRACE_EAVE_HEIGHT)

        # Side parapet walls (north_t / south_t swapped between the two houses)
        _add(Polygon([(roof_x1, ty_centre + half_w), (roof_x2, ty_centre + half_w),
                      (roof_x2, ty_centre + half_w - north_t), (roof_x1, ty_centre + half_w - north_t)]),
             f"{label} north wall", TERRACE_WALL_HEIGHT)
        _add(Polygon([(roof_x1, ty_centre - half_w + south_t), (roof_x2, ty_centre - half_w + south_t),
                      (roof_x2, ty_centre - half_w), (roof_x1, ty_centre - half_w)]),
             f"{label} south wall", TERRACE_WALL_HEIGHT)

        # Pitched roof
        hip_start = roof_x2 - TERRACE_HIP_LENGTH
        n_steps = 8

        def add_roof_strips(x_west, x_east, apex_height, rlabel):
            for i in range(1, n_steps + 1):
                t = i / n_steps
                strip_half_w = max(half_w * (1 - t), 0.05)
                strip_height = TERRACE_EAVE_HEIGHT + t * (apex_height - TERRACE_EAVE_HEIGHT)
                strip = Polygon([
                    (x_west, ty_centre + strip_half_w), (x_east, ty_centre + strip_half_w),
                    (x_east, ty_centre - strip_half_w), (x_west, ty_centre - strip_half_w),
                ])
                _add(strip, f"{rlabel} {i}", strip_height)

        add_roof_strips(roof_x1, hip_start, TERRACE_RIDGE_HEIGHT, f"{label} gable strip")

        n_hip = 5
        hip_slice_w = TERRACE_HIP_LENGTH / n_hip
        for j in range(n_hip):
            t_hip = (j + 0.5) / n_hip
            h_apex = TERRACE_EAVE_HEIGHT + (1 - t_hip) * (TERRACE_RIDGE_HEIGHT - TERRACE_EAVE_HEIGHT)
            x_west = hip_start + j * hip_slice_w
            x_east = hip_start + (j + 1) * hip_slice_w
            add_roof_strips(x_west, x_east, h_apex, f"{label} hip {j + 1} strip")

    ref_wgs84_features = []
    ref_utm_features = []

    for pair_idx, (house_n, house_s), south_tune in TERRACE_PAIRS:
        ty_n = ty + pair_idx * TERRACE_PAIR_PITCH - south_tune
        if pair_idx == 0:
            before = len(wgs84_features)
        add_house(ty_n, TERRACE_NORTH_WALL, TERRACE_SOUTH_WALL, f"House {house_n}")
        add_house(ty_n - TERRACE_HOUSE_WIDTH, TERRACE_SOUTH_WALL, TERRACE_NORTH_WALL, f"House {house_s}")
        if pair_idx == 0:
            ref_wgs84_features = wgs84_features[before:]
            ref_utm_features = utm_features[before:]

    return {
        "js_buildings": js_buildings,
        "wgs84_features": wgs84_features,
        "utm_features": utm_features,
        "ref_wgs84_features": ref_wgs84_features,
        "ref_utm_features": ref_utm_features,
    }


_CONTEXT = _make_context_buildings()
CONTEXT_BUILDINGS = _CONTEXT["js_buildings"]
CONTEXT_WGS84_FEATURES = _CONTEXT["ref_wgs84_features"]
CONTEXT_UTM_FEATURES = _CONTEXT["ref_utm_features"]


def build_legend(tower_height, include_street_masses, include_carpark=True):
    """Build legend HTML for a scenario."""
    items = [
        f'<div class="legend-item"><span class="legend-swatch" style="background:rgb(210,160,140)"></span>Main tower ({tower_height}m)</div>',
    ]
    if include_street_masses:
        items.append('<div class="legend-item"><span class="legend-swatch" style="background:rgb(180,100,80)"></span>Podium (14.3m) / Street (9.675m, 6.45m)</div>')
    else:
        items.append('<div class="legend-item"><span class="legend-swatch" style="background:rgb(180,100,80)"></span>Podium (14.3m)</div>')
    items.append('<div class="legend-item"><span class="legend-swatch" style="background:rgb(220,210,195)"></span>Roof plant &amp; stairs</div>')
    if include_carpark:
        items.append('<div class="legend-item"><span class="legend-swatch" style="background:rgb(80,80,80)"></span>Car park (external overflow)</div>')
    items.append('<div class="legend-item"><span class="legend-swatch" style="background:rgb(0,120,255)"></span>Lot boundary</div>')
    items.append('<div class="legend-item"><span class="legend-swatch" style="background:rgb(100,48,32)"></span>Existing terrace (context)</div>')
    return '\n      '.join(items)


def generate_scenario(scenario):
    """Generate building model for a single scenario.

    Returns (features, js_buildings, legend_html).
    """
    features = []
    utm_features = []
    js_buildings = []

    west_shift = scenario["west_shift"]
    height_reduction = scenario["height_reduction"]
    tower_east_setback = scenario["tower_east_setback"]
    include_street_masses = scenario["include_street_masses"]
    fence_east_offset = scenario["fence_east_offset"]
    tower_south_setback = scenario.get("tower_south_setback", TOWER_SOUTH_SETBACK)
    street_south_east_setback = scenario.get("street_south_east_setback", STREET_SOUTH_EAST_SETBACK)

    # Recalculate dependent dimensions if south setback changed
    tower_length = LOT_LENGTH - TOWER_NORTH_SETBACK - tower_south_setback
    street_south_length = (LOT_LENGTH - tower_south_setback) - STREET_SOUTH_NORTH_EDGE

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
            utm_features.append({
                "type": "Feature",
                "properties": {"name": name, "height": height},
                "geometry": mapping(rotated),
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
        sfence_west = (street_south_east_setback - ANCHOR_WEST_OF_LOT_EAST) + west_shift
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
    sfence_south = LOT_LENGTH - tower_south_setback - ANCHOR_SOUTH_OF_LOT_NORTH
    sfence_span = sfence_south - sfence_north

    street_fence = [
        ("Street fence brick N", sfence_east, sfence_north,
         sfence_width, BRICK_WIDTH, FENCE_HEIGHT, "podium", False),
        ("Street fence brick S", sfence_east, sfence_south - BRICK_WIDTH,
         sfence_width, BRICK_WIDTH, FENCE_HEIGHT, "podium", False),
        ("Street fence picket", sfence_east, sfence_north + BRICK_WIDTH,
         PICKET_THICKNESS, sfence_span - 2 * BRICK_WIDTH, FENCE_HEIGHT, "fence", False),
    ]

    # Filter buildings per scenario config
    include_carpark = scenario.get("include_carpark", True)
    buildings = [b for b in BUILDINGS
                 if (include_street_masses or b[6] != "street")
                 and (include_carpark or b[6] != "carpark")]

    all_boxes = buildings + LOT_BOUNDARY + NORTH_FENCE + street_fence

    for name, east, south, width, length, height, color_group, shade_relevant in all_boxes:
        is_east_face_item = name in ("Roof south stairwell", "Roof north stairwell")

        # Override length for street-facing south mass if tower south setback changed
        if name == "Street-facing south" and tower_south_setback != TOWER_SOUTH_SETBACK:
            length = street_south_length
        # Override east face and width for street-facing south mass if setback changed
        if name == "Street-facing south" and street_south_east_setback != STREET_SOUTH_EAST_SETBACK:
            east = street_south_east_setback - ANCHOR_WEST_OF_LOT_EAST
            width = tower_east_setback - street_south_east_setback

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

    # Car park entrance driveway (where applicable)
    carpark_access = scenario.get("carpark_access")
    if carpark_access:
        ce_west_setback = scenario.get("carpark_entrance_west_setback", CARPARK_ENTRANCE_WEST_SETBACK)
        ce_east = (LOT_WIDTH - ce_west_setback - CARPARK_ENTRANCE_WIDTH) - ANCHOR_WEST_OF_LOT_EAST
        if carpark_access == "south":
            # Access from Alexandra Parade East: shifts west with the car park
            entrance_east = ce_east + west_shift
            entrance_south = LOT_LENGTH - CARPARK_SOUTH_SETBACK - ANCHOR_SOUTH_OF_LOT_NORTH
            entrance_length = CARPARK_SOUTH_SETBACK + CARPARK_ENTRANCE_LOT_OVERHANG
        else:
            # Access from Noone Street: fixed position west of podium, does not shift
            entrance_east = ce_east
            entrance_south = LOT_NE_SOUTH_OFFSET - CARPARK_ENTRANCE_LOT_OVERHANG
            entrance_length = CARPARK_NORTH_SETBACK + CARPARK_ENTRANCE_LOT_OVERHANG
        poly = box(entrance_east, entrance_south, CARPARK_ENTRANCE_WIDTH, entrance_length)
        add_building(poly, "Car park entrance", MIN_DIMENSION, "carpark", False)

    # Process main tower (complex polygon with shaft notches)
    tower_height = TOWER_HEIGHT - height_reduction
    if east_face_shift == 0:
        # Scenarios with original east setback: compute base vertices, apply uniform shift
        tower_verts = make_tower_vertices(TOWER_EAST_SETBACK, tower_south_setback=tower_south_setback)
        tower_verts = [(e + west_shift, s) for e, s in tower_verts]
    else:
        # Different east setback: west_shift applied only to west face inside function
        tower_verts = make_tower_vertices(tower_east_setback, west_shift=west_shift, tower_south_setback=tower_south_setback)

    poly = polygon(tower_verts)
    add_building(poly, "Main tower", tower_height, "tower", True)

    js_buildings.extend(CONTEXT_BUILDINGS)

    legend = build_legend(tower_height, include_street_masses, include_carpark)

    return features, utm_features, js_buildings, legend


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
    .legend {{ margin-top: 0; padding-top: 0; }}
    .legend-item {{ display: flex; align-items: center; gap: 8px; margin: 4px 0; font-size: 11px; }}
    .legend-swatch {{ width: 14px; height: 14px; border-radius: 2px; flex-shrink: 0; }}
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
    .viewpoint-btn {{ padding: 6px; font-size: 11px; cursor: pointer; border: 1px solid #ccc; border-radius: 4px; background: white; }}
    .viewpoint-btn:hover {{ background: #f8f8f8; }}
    /* Hide Google Maps alpha channel warning */
    [role="region"][aria-label*="alpha channel"] {{ display: none !important; }}
    #fullscreen-btn {{ position: absolute; top: 10px; right: 10px; z-index: 1; width: 36px; height: 36px; background: white; border: none; border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.3); cursor: pointer; display: flex; align-items: center; justify-content: center; padding: 0; }}
    #fullscreen-btn:hover {{ background: #f8f8f8; }}
    #fullscreen-btn svg {{ width: 18px; height: 18px; }}
  </style>
  <script src="https://maps.googleapis.com/maps/api/js?key={api_key}&v=alpha&libraries=maps3d" async></script>
  {deckgl_script}
</head>
<body>
  <div id="map3d" class="map-container"></div>
  <div id="mapFlat" class="map-container hidden"></div>
  <button id="fullscreen-btn" title="Toggle fullscreen" aria-label="Toggle fullscreen">
    <svg id="fs-enter" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <polyline points="15 3 21 3 21 9"/><polyline points="9 21 3 21 3 15"/>
      <line x1="21" y1="3" x2="14" y2="10"/><line x1="3" y1="21" x2="10" y2="14"/>
    </svg>
    <svg id="fs-exit" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display:none">
      <polyline points="4 14 10 14 10 20"/><polyline points="20 10 14 10 14 4"/>
      <line x1="10" y1="14" x2="3" y2="21"/><line x1="21" y1="3" x2="14" y2="10"/>
    </svg>
  </button>
  <div id="info-panels">
    <div class="info-panel">
      <h3>Noone St / Rutland St Community Housing</h3>
      <p class="note">Shift+drag or Ctrl+drag to change viewing angle.</p>
      <!--
      <div class="scenario-mode">
        <label>Scenario</label>
        <select id="scenarioSelect">
          {scenario_options}
        </select>
      </div>
      -->
      <div id="legend" class="legend">
      </div>
      <div class="view-mode">
        <label>View mode</label>
        <select id="viewMode">{view_options}
        </select>
      </div>
      <details>
        <summary>Extended options</summary>
        <p>Load <a id="geojsonLink" href="proposal.geojson" download>building model</a> into
           <a href="https://shademap.app" target="_blank">shademap.app</a> for shade analysis.</p>
        <div style="margin: 8px 0;">
          <label style="font-size: 11px; font-weight: 500; display: block; margin-bottom: 4px;">Viewpoints</label>
          <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 4px; margin-bottom: 8px;">
            <button data-view="nw" class="viewpoint-btn">NW</button>
            <button data-view="n" class="viewpoint-btn">N</button>
            <button data-view="ne" class="viewpoint-btn">NE</button>
            <button data-view="w" class="viewpoint-btn">W</button>
            <button data-view="center" class="viewpoint-btn" style="background: #f0f0f0;">Centre</button>
            <button data-view="e" class="viewpoint-btn">E</button>
            <button data-view="sw" class="viewpoint-btn">SW</button>
            <button data-view="s" class="viewpoint-btn">S</button>
            <button data-view="se" class="viewpoint-btn">SE</button>
          </div>
          <div style="margin-top: 8px;">
            <label style="font-size: 11px; display: flex; justify-content: space-between; margin-bottom: 2px;">
              <span>Elevation</span>
              <span id="elevationValue">40m</span>
            </label>
            <input type="range" id="elevationSlider" min="1" max="90" value="40" style="width: 100%;">
          </div>
          <div style="margin-top: 8px;">
            <label style="font-size: 11px; display: flex; justify-content: space-between; margin-bottom: 2px;">
              <span>Tilt</span>
              <span id="tiltValue">68°</span>
            </label>
            <input type="range" id="tiltSlider" min="0" max="90" value="68" style="width: 100%;">
          </div>
        </div>
      </details>
    </div>
    <!--
    <div class="info-panel">
      <details open>
        <summary>Scenario details</summary>
        <div id="scenarioDesc" class="scenario-desc"></div>
      </details>
    </div>
    -->
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
        range: 200, tilt: 60, heading: 0, mode: MapMode.HYBRID,
        minAltitude: 0.1,
        maxAltitude: 1000,
        minTilt: 0,
        maxTilt: 90
      }});
      map3d.style.width = map3d.style.height = "100%";
      document.getElementById("map3d").appendChild(map3d);

      let polygons3d = [];
      let overlay = null;

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
        for (const b of scenario.buildings) {{
          const poly = new Polygon3DElement({{
            altitudeMode: AltitudeMode.ABSOLUTE,
            extruded: true,
            fillColor: b.fill,
            strokeColor: b.stroke,
            strokeWidth: 2
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
        // document.getElementById("scenarioDesc").innerHTML = scenario.description;
      }}

      // Initial load
      loadScenario("proposal");

      // Scenario switching
      document.getElementById("scenarioSelect")?.addEventListener("change", (e) => {{
        loadScenario(e.target.value);
      }});

      // View mode switching
      document.getElementById("viewMode").addEventListener("change", (e) => {{
        const is3d = e.target.value === "3d";
        document.getElementById("map3d").classList.toggle("hidden", !is3d);
        document.getElementById("mapFlat").classList.toggle("hidden", is3d);
        // Sync camera to the current viewpoint whenever switching modes
        if (currentViewpoint) updateCamera();
      }});


      // Viewpoint buttons - calculate positions around lot centrepoint
      // Lot dimensions: 40.5m (E-W) × 80.9m (N-S)
      // Anchor is 1.4m south of lot north boundary, 2.55m west of lot east boundary
      // Lot centre from anchor: (2.55 - 20.25)m east, (1.4 - 40.45)m north = (-17.7, -39.05)m

      // Helper: offset lat/lng by metres (north positive, east positive)
      function offsetLatLng(lat, lng, northM, eastM) {{
        const latOffset = northM / 111320; // metres per degree latitude
        const lngOffset = eastM / (111320 * Math.cos(lat * Math.PI / 180)); // metres per degree longitude
        return {{ lat: lat + latOffset, lng: lng + lngOffset }};
      }}

      // Calculate lot centrepoint (accounting for -5.8° rotation)
      const rotRad = -5.8 * Math.PI / 180;
      const eastOffset = -17.7, northOffset = -39.05; // from anchor in unrotated coords
      const eastRot = eastOffset * Math.cos(rotRad) - northOffset * Math.sin(rotRad);
      const northRot = eastOffset * Math.sin(rotRad) + northOffset * Math.cos(rotRad);
      const lotCentre = offsetLatLng({ANCHOR_LAT}, {ANCHOR_LON}, northRot, eastRot);

      // Viewpoint configuration
      const viewDistance = 100;
      const targetHeight = 0; // Ground level target — gives tilt ~68° at default elevation/distance, matching flat map max
      const defaultElevation = 40; // Default camera elevation (metres)
      let currentViewpoint = null;

      const viewpoints = {{
        n:      {{ heading: 180, offsetNorth: viewDistance, offsetEast: 0 }},
        ne:     {{ heading: 225, offsetNorth: viewDistance/Math.sqrt(2), offsetEast: viewDistance/Math.sqrt(2) }},
        e:      {{ heading: 270, offsetNorth: 0, offsetEast: viewDistance }},
        se:     {{ heading: 315, offsetNorth: -viewDistance/Math.sqrt(2), offsetEast: viewDistance/Math.sqrt(2) }},
        s:      {{ heading: 0, offsetNorth: -viewDistance, offsetEast: 0 }},
        sw:     {{ heading: 45, offsetNorth: -viewDistance/Math.sqrt(2), offsetEast: -viewDistance/Math.sqrt(2) }},
        w:      {{ heading: 90, offsetNorth: 0, offsetEast: -viewDistance }},
        nw:     {{ heading: 135, offsetNorth: viewDistance/Math.sqrt(2), offsetEast: -viewDistance/Math.sqrt(2) }},
        center: {{ heading: 0, offsetNorth: 0, offsetEast: 0, tilt: 60, range: 150, elevation: 80 }}
      }};

      const elevationSlider = document.getElementById("elevationSlider");
      const tiltSlider = document.getElementById("tiltSlider");
      const elevationValue = document.getElementById("elevationValue");
      const tiltValue = document.getElementById("tiltValue");

      // Calculate tilt to point at targetHeight above ground from given elevation and distance
      // Tilt is angle from vertical: atan(horizontal_distance / vertical_difference)
      function calculateTilt(elevation, distance, target) {{
        const verticalDiff = elevation - target;
        return Math.round(Math.atan(distance / verticalDiff) * 180 / Math.PI);
      }}

      function isFlat() {{
        return document.getElementById("viewMode").value === "flat";
      }}

      // Update camera from current viewpoint and slider values
      function updateCamera() {{
        if (!currentViewpoint) return;
        const view = viewpoints[currentViewpoint];
        const elevation = parseInt(elevationSlider.value);
        const tilt = parseInt(tiltSlider.value);
        const viewPos = offsetLatLng(lotCentre.lat, lotCentre.lng, view.offsetNorth, view.offsetEast);

        if (isFlat() && mapFlat) {{
          // Flat map: center is the look-at ground point, not the camera position
          mapFlat.setCenter(lotCentre);
          mapFlat.setHeading(view.heading);
          mapFlat.setTilt(tilt);  // API caps at its own maximum (~67.5°)
          // Logarithmic zoom: calibrated so elevation 40m → zoom 19 (building scale, Melbourne)
          mapFlat.setZoom(19.50 - Math.log2(elevation / 40));
        }} else {{
          map3d.center = {{
            lat: viewPos.lat,
            lng: viewPos.lng,
            altitude: GROUND + elevation
          }};
          map3d.heading = view.heading;
          map3d.tilt = tilt;
          map3d.range = view.range || viewDistance;
        }}
      }}

      // Viewpoint button clicks
      document.querySelectorAll(".viewpoint-btn").forEach(btn => {{
        btn.addEventListener("click", () => {{
          currentViewpoint = btn.dataset.view;
          const view = viewpoints[currentViewpoint];

          // Set elevation slider (use view-specific elevation if available)
          const elevation = view.elevation || defaultElevation;
          elevationSlider.value = elevation;
          elevationValue.textContent = elevation + "m";

          // Calculate and set tilt (use view-specific tilt if available)
          const tilt = view.tilt || calculateTilt(elevation, view.range || viewDistance, targetHeight);
          tiltSlider.value = tilt;
          tiltValue.textContent = tilt + "°";

          updateCamera();
        }});
      }});

      // Slider change events - update camera properties directly to retain current position
      elevationSlider.addEventListener("input", () => {{
        const elevation = parseInt(elevationSlider.value);
        elevationValue.textContent = elevation + "m";

        if (isFlat() && mapFlat) {{
          mapFlat.setZoom(19.50 - Math.log2(elevation / 40));
        }} else {{
          const currentCenter = map3d.center;
          map3d.center = {{
            lat: currentCenter.lat,
            lng: currentCenter.lng,
            altitude: GROUND + elevation
          }};
        }}
      }});

      tiltSlider.addEventListener("input", () => {{
        const tilt = parseInt(tiltSlider.value);
        tiltValue.textContent = tilt + "°";

        if (isFlat() && mapFlat) {{
          mapFlat.setTilt(tilt);  // API caps at its own maximum (~67.5°)
        }} else {{
          map3d.tilt = tilt;
        }}
      }});
    }}

    // Fullscreen button
    const fsBtn = document.getElementById("fullscreen-btn");
    const fsEnter = document.getElementById("fs-enter");
    const fsExit = document.getElementById("fs-exit");

    fsBtn.addEventListener("click", () => {{
      if (!document.fullscreenElement) {{
        document.documentElement.requestFullscreen();
      }} else {{
        document.exitFullscreen();
      }}
    }});

    document.addEventListener("fullscreenchange", () => {{
      const isFs = !!document.fullscreenElement;
      fsEnter.style.display = isFs ? "none" : "";
      fsExit.style.display = isFs ? "" : "none";
    }});

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
        features, utm_features, js_buildings, legend = generate_scenario(scenario)

        geojson = {"type": "FeatureCollection", "features": features}
        filename = f'{scenario["id"]}.geojson'
        with open(filename, "w") as f:
            json.dump(geojson, f, indent=2)
        print(f"Wrote {filename}")

        utm_geojson = {"type": "FeatureCollection", "features": utm_features}
        utm_filename = f'{scenario["id"]}_utm.geojson'
        with open(utm_filename, "w") as f:
            json.dump(utm_geojson, f, indent=2)
        print(f"Wrote {utm_filename}")

        all_scenarios.append({
            "id": scenario["id"],
            "label": scenario["label"],
            "js_buildings": js_buildings,
            "legend": legend,
            "description": scenario["description"],
        })

    with open("terrace.geojson", "w") as f:
        json.dump({"type": "FeatureCollection", "features": CONTEXT_WGS84_FEATURES}, f, indent=2)
    print("Wrote terrace.geojson")

    with open("terrace_utm.geojson", "w") as f:
        json.dump({"type": "FeatureCollection", "features": CONTEXT_UTM_FEATURES}, f, indent=2)
    print("Wrote terrace_utm.geojson")

    # Backward compat: index.geojson is a copy of proposal.geojson
    shutil.copy("proposal.geojson", "index.geojson")
    print("Wrote index.geojson")

    write_html(api_key, flat_map_id, all_scenarios)


if __name__ == "__main__":
    main()
