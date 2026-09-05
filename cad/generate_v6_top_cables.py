#!/usr/bin/env python3
"""Cut two rounded top cable exits into the complete V5 prototype."""

from pathlib import Path
import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "3d print" / "Defender_EP0189_V5_prototyp_fasthål.stl"
OUT = ROOT / "3d print" / "Defender_EP0189_V7_kabelhal_fram.stl"

SLOT_W = 50.0
SLOT_H = 16.0
SLOT_X = 48.0
SLOT_Z = 22.0
CUT_Y = 24.0


def top_capsule(x_center):
    """Rounded 50 x 16 mm slot extruded through the top wall along Y."""
    r = SLOT_H / 2
    middle = trimesh.creation.box((SLOT_W-2*r, CUT_Y, SLOT_H))
    middle.apply_translation((x_center, 37.0, SLOT_Z))
    parts = [middle]
    rotation = trimesh.transformations.rotation_matrix(np.pi/2, [1, 0, 0])
    for dx in (-(SLOT_W/2-r), SLOT_W/2-r):
        c = trimesh.creation.cylinder(radius=r, height=CUT_Y, sections=48)
        c.apply_transform(rotation)
        c.apply_translation((x_center+dx, 37.0, SLOT_Z))
        parts.append(c)
    return trimesh.boolean.union(parts, engine="manifold")


def main():
    base = trimesh.load_mesh(SRC, process=True)
    cutters = [top_capsule(-SLOT_X), top_capsule(SLOT_X)]
    result = trimesh.boolean.difference([base, *cutters], engine="manifold",
                                        check_volume=False)
    result.remove_unreferenced_vertices()
    result.export(OUT)
    print(f"file={OUT}")
    print(f"watertight_before_export={result.is_watertight}")
    print(f"extents_mm={result.extents.tolist()}")


if __name__ == "__main__":
    main()
