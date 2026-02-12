# Noone Street and Rutland Street Community Housing - Shade Impact Assessment

## Project Overview

A tool for visualising a proposed development via

* index.html, a static google maps 3d visualisation to see the building in context
* shademap.app to assess shade impacts from proposed development, via produced GeoJSON

## Location
- **Address**: Noone Street and Rutland Street Community Housing, Clifton Hill VIC 3068
- **NE building corner**: -37.79402072126052, 144.9959728611442
- **Street orientation**: Rutland St runs 5.8° west of true north
- **Building side**: West side of Rutland St (odd numbers)

## Building Dimensions

Note that sizes are generally calculated based on offsets from lot boundaries; prefer computing values from these measurements, which can be directly drawn from the plans, over hard coded values for positions or sizes (where possible).

| Parameter | Value | Source |
|-----------|-------|--------|
| Lot width (E-W) | 40.5m | Site plan |
| Lot length (N-S) | 80.9m | Site plan |
| Podium width (E-W) | 26.107m | 40.5 - 4.765 - 9.628 |
| Podium length (N-S) | 9.525m | 11.775 - 2.25 (south - north setbacks) |
| Tower width (E-W) | 21.866m | 40.5 - 10.548 - 8.086 |
| Tower length (N-S) | 65.683m | 80.9 - 14.725 - 0.492 |

## Building Masses

| Mass | Description | Height | Roof RL | E-W depth | N-S length |
|------|-------------|--------|---------|-----------|------------|
| 1 | Northern podium | 14.3m | 36.030 | 26.107m | 9.525m |
| 2 | Main tower | 26.5m | 48.230 | 21.866m | 65.683m |
| 3 | Street-facing north | 9.675m | 31.405 | 5.788m | 15.835m |
| 4 | Street-facing south | 6.45m | 28.180 | 7.998m | 43.828m |
| 5 | Street-facing shaft infill | 6.45m | 28.180 | 5.345m | 6.02m |
| 6 | Stair core north | 26.5m | 48.230 | 9.5m | 2.95m |
| 7 | Roof south stairwell | 28.65m | 50.380 | 5.59m | 3.67m |
| 8 | Roof HW heat pump | 28.4m | 50.130 | 7.66m | 5.16m |
| 9 | Roof north stairwell | 27.5m | 49.230 | 5.0m | 6.01m |
| 10 | Car park west | 0.11m | 21.840 | 14.108m | 57.285m |

Ground level: RL 21.730 AHD

### Street-facing masses
The eastern (Rutland St) frontage has three lower masses between the street and the main tower:
- **Northern portion**: 9.675m high, 5.788m deep, runs from tower north edge (14.725m from north) to 30.56m from north boundary
- **Shaft infill**: 6.45m high, 5.345m deep, fills the northern stairwell notch space from street side (east edge 7.608m from lot east boundary, spans from 30.56m to 36.58m from north, meeting the northern mass and extending to southern edge of stairwell notch)
- **Southern portion**: 6.45m high, 7.998m deep, runs from tower south edge (80.408m from north / 0.492m from south) northward to 36.58m from north (southern edge of northern stairwell notch, 44.32m from south boundary)

### Roof protrusions
Three overruns above the main tower roof (RL 48.23):
- **South stairwell**: RL 50.38, 5.59m × 3.67m, NE corner at 31.59m from south
- **HW heat pump**: RL 50.13, 7.66m × 5.16m, SW corner at 22.1m from south
- **North stairwell**: RL 49.23, from 44.32m to 50.33m from south boundary

### Other masses
- **Stair core north**: Full tower height (26.5m), bridges between podium and main tower
- **Car park west**: Ground-level external overflow parking (0.11m height marker)

## Scenarios

The tool supports multiple building scenarios reflecting the proposal analysis variations:

| ID | Label | Tower Height | West Shift | Street Masses | Tower East Setback | Fence East | Notes |
|----|-------|-------------|------------|---------------|-------------------|------------|-------|
| `proposal` | Proposal (8 storeys) | 26.5m | 0m | Yes | 10.548m | 0.5m | As submitted |
| `seven-floors-tier2-moderate` | 7 storeys (Tier 2, Mod 3 Option B) | 23.3m | 5.0m | No | 10.548m | 4.0m | Westward shift, parking under building |
| `six-floors-tier1` | 6 storeys (Tier 1) | 20.1m | 0m | No | 4.0m | 4.0m | No shift, external car park |
| `six-floors-tier2-moderate` | 6 storeys (Tier 2, Mod 3 Option B) | 20.1m | 5.0m | No | 10.548m | 4.0m | 4-6m shift, parking under building |
| `six-floors-tier2-maximum` | 6 storeys (Tier 2, Mod 3 Option C) | 20.1m | 7.5m | No | 10.548m | 4.0m | 6-9m shift, maximum landscaping |

- **West Shift**: moves all masses except podium/fences westward and widens tower by consuming western railway buffer
- **Street Masses**: the two lower street-facing step-backs between tower and Rutland St (removed in all modified scenarios for simpler vertical form)
- **Tower East Setback**: distance from lot east boundary to tower east face (Tier 1 uses 4.0m statutory setback; Tier 2 keeps original 10.548m)
- **Fence East**: street fence east edge distance from lot east boundary (0.5m original, 4.0m statutory)
- **Tier 1**: Achievable without westward shift, no AS5100 assessment required
- **Tier 2**: Conditional on AS5100 railway clearance risk assessment (building enters 10-20m zone from stabling siding centreline)

Key changes from previous scenarios:
- All new scenarios use 4.0m statutory setback fence (was 0.5m for proposal)
- Tier 2 scenarios shift building west and widen tower by consuming western railway buffer
- Street-facing masses removed from all modified scenarios for simplified vertical form
- Tier 1 achieves 4.0m setback by adjusting tower east face position (no westward shift)
- All modifications conditional on final design development; Tier 2 requires AS5100 assessment

## Files

**IMPORTANT**: All files except `generate_geojson.py` are generated outputs. To modify the HTML viewer or building models, edit `generate_geojson.py` and run `mise build`. Do NOT edit generated files directly.

- `generate_geojson.py` - **Source file** - Python script that generates all output files
- `index.html` - Interactive 3D viewer with scenario switching (**GENERATED - edit generate_geojson.py instead**)
- `proposal.geojson` - Original 8-storey proposal (generated)
- `seven-floors-tier2-moderate.geojson` - 7 storeys with moderate westward shift (generated)
- `six-floors-tier1.geojson` - 6 storeys Tier 1, no shift (generated)
- `six-floors-tier2-moderate.geojson` - 6 storeys Tier 2 Option B (generated)
- `six-floors-tier2-maximum.geojson` - 6 storeys Tier 2 Option C (generated)
- `index.geojson` - Copy of proposal.geojson for backward compatibility (generated)

## Dependencies
- Python >=3.12
- pyproj>=3.7.2
- shapely>=2.1.2

## Environment Variables
- `GOOGLE_MAPS_API_KEY` - Required for building HTML viewer (set in mise.toml via .env file)
- `GOOGLE_MAPS_FLAT_MAP_ID` - Optional Map ID with flattened/hidden buildings for clearer model visibility
  - Create in [Google Cloud Console](https://console.cloud.google.com/google/maps-apis/studio/styles) using "3D Hybrid" template
  - Set Buildings > Building Style to "Footprints" or hide entirely
  - Associate the style with a Map ID and set this variable

## Usage
```bash
mise build          # Generate index.geojson and index.html
mise deploy         # Build and deploy to gh-pages branch
```

## Technical Notes
- Coordinates use WGS84 (EPSG:4326)
- Building rotated -5.8° (clockwise) around NE anchor to align with street
- Rotation performed in UTM (EPSG:32755) via pyproj for accuracy

## Verification
1. Load `index.geojson` into geojson.io or shademap.app
2. Confirm building on west side of Rutland St
3. Confirm alignment parallel to street
4. Test shadow simulation at various times

## Deployment
The `mise deploy` task:
1. Builds `index.html` with API key inlined
2. Pushes only `index.html` to the `gh-pages` branch
3. GitHub Pages serves from gh-pages branch

Live at: https://elyobo.github.io/rutland-noone-social-housing/
