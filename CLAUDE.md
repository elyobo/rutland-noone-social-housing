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
| 4 | Street-facing south | 6.45m | 28.180 | 7.998m | 49.848m |
| 5 | Stair core north | 26.5m | 48.230 | 9.5m | 2.95m |
| 6 | Roof south stairwell | 28.65m | 50.380 | 5.59m | 3.67m |
| 7 | Roof HW heat pump | 28.4m | 50.130 | 7.66m | 5.16m |
| 8 | Roof north stairwell | 27.5m | 49.230 | 5.0m | 6.01m |
| 9 | Car park west | 0.11m | 21.840 | 14.108m | 57.285m |

Ground level: RL 21.730 AHD

### Street-facing masses
The eastern (Rutland St) frontage has two lower masses between the street and the main tower:
- **Northern portion**: 9.675m high, 5.788m deep, runs from tower north edge to 30.56m from north boundary
- **Southern portion**: 6.45m high, 7.998m deep, runs from 30.56m to south end of tower
- Transition at 37.8% of lot length from north (50.34m from south boundary)

### Roof protrusions
Three overruns above the main tower roof (RL 48.23):
- **South stairwell**: RL 50.38, 5.59m × 3.67m, NE corner at 31.59m from south
- **HW heat pump**: RL 50.13, 7.66m × 5.16m, SW corner at 22.1m from south
- **North stairwell**: RL 49.23, from 44.32m to 50.33m from south boundary

### Other masses
- **Stair core north**: Full tower height (26.5m), bridges between podium and main tower
- **Car park west**: Ground-level external overflow parking (0.11m height marker)

## Scenarios

The tool supports multiple building scenarios for comparison:

| ID | Label | Tower Height | West Shift | Street Masses | Tower East Setback | Fence East |
|----|-------|-------------|------------|---------------|-------------------|------------|
| `proposal` | Proposal (8 storeys) | 26.5m | 0m | Yes | 10.548m | 0.5m |
| `six-floors` | 6 storeys | 19.6m | 4.384m | Yes | 10.548m | 4.0m |
| `six-floors-no-setback` | 6 storeys, wider footprint | 19.6m | 8.086m | No | 6.05m | 4.0m |
| `six-floors-more-setback` | 6 storeys, larger setback | 19.6m | 8.086m | No | 10.548m | 4.0m |

- **West Shift**: moves all masses except podium/fences westward
  - Scenario 2: car park touches west lot boundary
  - Scenarios 3 & 4: tower abuts west lot boundary; car park removed (parking under building)
- **Street Masses**: the two lower street-facing step-backs between tower and Rutland St
- **Tower East Setback**: distance from lot east boundary to tower east face (base value; effective position includes west shift for scenarios with uniform shift)
- **Fence East**: street fence east edge distance from lot east boundary (0.5m original, 4.0m statutory)

## Files
- `generate_geojson.py` - Python script to generate building models (generates all output files)
- `proposal.geojson` - Original 8-storey proposal (generated, do not edit directly)
- `six-floors.geojson` - 6 storeys scenario (generated, do not edit directly)
- `six-floors-no-setback.geojson` - 6 storeys, wider footprint (generated, do not edit directly)
- `six-floors-more-setback.geojson` - 6 storeys, larger setback (generated, do not edit directly)
- `index.geojson` - Copy of proposal.geojson for backward compatibility (generated, do not edit directly)
- `index.html` - Interactive 3D viewer with scenario switching (generated, do not edit directly)

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
