#!/usr/bin/env python3
"""Add a 120 mm Defender-covering front and four original M4 holes to V4."""

from pathlib import Path
import trimesh

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "3d print" / "Defender_EP0189_V4_flush_en_del.stl"
OUT = ROOT / "3d print" / "Defender_EP0189_V5_prototyp_fasthål.stl"

SCREEN_W, SCREEN_H = 276.29, 76.50
CLEARANCE = 0.60
SCREEN_R = 6.5
FRONT_W, FRONT_H, FRONT_R, FRONT_T = 286.0, 120.0, 8.0, 3.0
HOLE_X, HOLE_Y, HOLE_D = 111.0, 52.0, 4.5


def rounded_prism(w, h, r, depth, z_center):
    parts = [trimesh.creation.box((w-2*r, h, depth)),
             trimesh.creation.box((w, h-2*r, depth))]
    for x in (-w/2+r, w/2-r):
        for y in (-h/2+r, h/2-r):
            c = trimesh.creation.cylinder(radius=r, height=depth, sections=48)
            c.apply_translation((x, y, 0))
            parts.append(c)
    result = trimesh.boolean.union(parts, engine="manifold")
    result.apply_translation((0, 0, z_center))
    return result


def main():
    base = trimesh.load_mesh(SRC, process=True)
    face = rounded_prism(FRONT_W, FRONT_H, FRONT_R, FRONT_T, FRONT_T/2)
    opening = rounded_prism(SCREEN_W+CLEARANCE, SCREEN_H+CLEARANCE,
                            SCREEN_R+CLEARANCE/2, FRONT_T+2, FRONT_T/2)
    face = trimesh.boolean.difference([face, opening], engine="manifold")
    merged = trimesh.boolean.union([base, face], engine="manifold",
                                   check_volume=False)

    holes = []
    for x in (-HOLE_X, HOLE_X):
        for y in (-HOLE_Y, HOLE_Y):
            h = trimesh.creation.cylinder(radius=HOLE_D/2,
                                          height=FRONT_T+2, sections=40)
            h.apply_translation((x, y, FRONT_T/2))
            holes.append(h)
    result = trimesh.boolean.difference([merged, *holes], engine="manifold",
                                        check_volume=False)
    result.remove_unreferenced_vertices()
    result.export(OUT)
    print(f"file={OUT}")
    print(f"watertight={result.is_watertight}")
    print(f"extents_mm={result.extents.tolist()}")
    print(f"faces={len(result.faces)}")


if __name__ == "__main__":
    main()
