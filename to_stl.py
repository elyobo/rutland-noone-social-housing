#!/usr/bin/env python3
"""Convert a UTM geojson building model to a single watertight STL for 3D printing."""

import argparse
import json
import sys
import trimesh
from shapely.geometry import Polygon

parser = argparse.ArgumentParser(description="UTM geojson to STL converter")
parser.add_argument("in_file", help="path to UTM geojson (use *_utm.geojson files)")
parser.add_argument("-s", "--scale", type=float, default=2.0,
                    help="scale factor in mm per real-world metre, e.g. 2.0 for 1:500 (default: 2.0 = 1:500)")
args = parser.parse_args()

with open(args.in_file) as f:
    data = json.load(f)

features = data["features"]
if not features:
    sys.exit("No features found")

# Normalise to local origin
all_coords = [c for feat in features for c in feat["geometry"]["coordinates"][0]]
min_x = min(c[0] for c in all_coords)
min_y = min(c[1] for c in all_coords)

meshes = []
for feat in features:
    coords = [(c[0] - min_x, c[1] - min_y) for c in feat["geometry"]["coordinates"][0]]
    height = feat["properties"]["height"]
    poly = Polygon(coords)
    if not poly.is_valid or poly.is_empty:
        print(f"  skipping invalid polygon: {feat['properties'].get('name', '?')}")
        continue
    mesh = trimesh.creation.extrude_polygon(poly, height)
    meshes.append(mesh)
    print(f"  extruded: {feat['properties'].get('name', '?')} h={height}m")

print(f"Unioning {len(meshes)} meshes...")
result = trimesh.boolean.union(meshes, engine="manifold")

if not result.is_volume:
    print("Warning: result is not watertight — may not print cleanly")

result.apply_scale(args.scale)
print(f"Scaled at 1:{round(1000/args.scale)} ({args.scale} mm per metre)")

out_file = args.in_file.replace(".geojson", ".stl")
result.export(out_file)
print(f"Wrote {out_file} ({len(result.faces)} faces)")
