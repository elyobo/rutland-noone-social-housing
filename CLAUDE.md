# Noone Street and Rutland Street Community Housing - Shade Impact Assessment

## Project Overview
GeoJSON building model for use with shademap.app to assess shade impacts from proposed development.

## Location
- **Address**: Noone Street and Rutland Street Community Housing, Clifton Hill VIC 3068
- **NE building corner**: -37.79402072126052, 144.9959728611442
- **Street orientation**: Rutland St runs 5.8° west of true north
- **Building side**: West side of Rutland St (odd numbers)

## Building Dimensions

| Parameter | Value | Source |
|-----------|-------|--------|
| Lot width (E-W) | 40.5m | Site plan |
| Lot length (N-S) | 80.9m | Site plan |
| Podium width (E-W) | 26.157m | 40.5 - 4.765 - 9.578 |
| Podium length (N-S) | 12.475m | 14.725 - 2.25 setback |
| Tower width (E-W) | 21.866m | 40.5 - 10.548 - 8.086 |
| Tower length (N-S) | 65.683m | 80.9 - 14.725 - 0.492 |

## Building Masses

| Mass | Description | Height | Roof RL | E-W depth | N-S length |
|------|-------------|--------|---------|-----------|------------|
| 1 | Northern podium | 14.3m | 36.030 | 26.157m | 12.475m |
| 2 | Main tower | 26.5m | 48.230 | 21.866m | 65.683m |
| 3 | Street-facing north | 9.6m | 31.330 | 10.548m | 15.835m |
| 4 | Street-facing south | 6.45m | 28.180 | 10.548m | 49.848m |
| 5 | Roof south stairwell | 28.65m | 50.380 | 5.59m | 3.67m |
| 6 | Roof HW heat pump | 28.65m | 50.380 | 7.66m | 5.16m |
| 7 | Roof north stairwell | 27.5m | 49.230 | 5.0m | 6.01m |

Ground level: RL 21.730 AHD

### Street-facing masses
The eastern (Rutland St) frontage has two lower masses at the property boundary:
- **Northern portion**: 9.6m high, runs from podium edge to 30.56m from north boundary
- **Southern portion**: 6.45m high, runs from 30.56m to south end of tower
- Transition at 62.22% of lot length (50.34m from south boundary)

### Roof protrusions
Three overruns above the main tower roof (RL 48.23):
- **South stairwell**: RL 50.38, 5.59m × 3.67m, NE corner at 31.59m from south
- **HW heat pump**: RL 50.38, 7.66m × 5.16m, SW corner at 22.1m from south
- **North stairwell**: RL 49.23, from 44.32m to 50.33m from south boundary

## Files
- `generate_geojson.py` - Python script to generate building model
- `index.geojson` - Output GeoJSON for shademap.app
- `index.html` - Interactive 3D viewer using Google Maps API (API key inlined at build)

## Dependencies
- Python >=3.12
- pyproj>=3.7.2
- shapely>=2.1.2

## Environment Variables
- `GOOGLE_MAPS_API_KEY` - Required for building HTML viewer (set in mise.toml via .env file)

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
