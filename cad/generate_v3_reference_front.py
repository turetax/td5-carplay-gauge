#!/usr/bin/env python3
"""Generate a V3 EP-0189 front for Thingiverse 5856588 support parts.

Requires trimesh and manifold3d.  Dimensions are millimetres.
The design preserves the four original corner fastener centres.  The two
original mid-height holes are omitted because the wider EP-0189 occupies them.
"""

from pathlib import Path
import trimesh

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "3d print" / "V3_reference_based"

BODY_W, BODY_H, BODY_D = 276.29, 76.50, 15.0
BODY_CLEARANCE = 0.60
VIEW_W, VIEW_H = 252.69, 57.90
VIEW_MARGIN = 1.0
BODY_R = 6.5                  # image-derived; manufacturer does not specify
OUTER_W, OUTER_H = 286.0, 120.0
OUTER_R, PLATE_T = 8.0, 10.0
FACE_T = 3.0
HOLE_D = 4.5
HOLE_X, HOLE_Y = 111.0, 52.0 # measured from original front STL


def rounded_prism(w, h, r, depth, z_center):
    """Rounded rectangle made as a robust union of boxes and cylinders."""
    parts = [
        trimesh.creation.box((w-2*r, h, depth)),
        trimesh.creation.box((w, h-2*r, depth)),
    ]
    for x in (-w/2+r, w/2-r):
        for y in (-h/2+r, h/2-r):
            c = trimesh.creation.cylinder(radius=r, height=depth, sections=48)
            c.apply_translation((x, y, 0))
            parts.append(c)
    result = trimesh.boolean.union(parts, engine="manifold")
    result.apply_translation((0, 0, z_center))
    return result


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    plate = rounded_prism(OUTER_W, OUTER_H, OUTER_R, PLATE_T, PLATE_T/2)

    # Visible opening passes through the complete front plate.
    opening = rounded_prism(VIEW_W+2*VIEW_MARGIN, VIEW_H+2*VIEW_MARGIN,
                            max(1.0, BODY_R-2.0), PLATE_T+2, PLATE_T/2)

    # Rear pocket stops at the 3 mm front face and locates the screen body.
    pocket_depth = PLATE_T-FACE_T+1
    pocket = rounded_prism(BODY_W+BODY_CLEARANCE, BODY_H+BODY_CLEARANCE,
                           BODY_R+BODY_CLEARANCE/2, pocket_depth,
                           FACE_T+(pocket_depth/2))

    cutters = [opening, pocket]
    for x in (-HOLE_X, HOLE_X):
        for y in (-HOLE_Y, HOLE_Y):
            hole = trimesh.creation.cylinder(radius=HOLE_D/2,
                                             height=PLATE_T+2, sections=40)
            hole.apply_translation((x, y, PLATE_T/2))
            cutters.append(hole)

    front = trimesh.boolean.difference([plate, *cutters], engine="manifold")
    front.remove_unreferenced_vertices()
    front.export(OUT / "EP0189_V3_front_4xM4.stl")

    report = (
        f"watertight={front.is_watertight}\n"
        f"vertices={len(front.vertices)} faces={len(front.faces)}\n"
        f"bounds_mm={front.extents.tolist()}\n"
        f"volume_mm3={front.volume:.2f}\n"
    )
    (OUT / "mesh_check.txt").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
