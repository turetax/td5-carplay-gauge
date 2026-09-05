#!/usr/bin/env python3
"""V9: thin front flange and countersunk Defender reference holes."""

from pathlib import Path
import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "cad/reference_thingiverse_5856588/Binnacle_Vent_Rail_v1.1.stl"
OUT = ROOT / "3d print/Defender_EP0189_V9_tunn_flush_front.stl"

SCREEN_W, SCREEN_H, SCREEN_D = 276.29, 76.50, 15.0
FIT_XY, FIT_Z, SCREEN_R = 0.60, 0.30, 6.5
FRONT_W, FRONT_H, FRONT_R, FRONT_T = 286.0, 120.0, 10.0, 3.0
POCKET_BORDER, STOP_T = 4.0, 2.4
HOLE_X, HOLE_Y, HOLE_D = 111.0, 52.0, 4.5
HEAD_D, COUNTERSINK_D = 8.6, 2.0
NECK_W, NECK_H, WALL, ELECTRONICS_D = 198.0, 70.0, 2.8, 62.0
CABLE_W, CABLE_H, CABLE_X, CABLE_Z = 50.0, 16.0, 48.0, 22.0


def rounded_prism(w, h, r, depth, z0, sections=64):
    parts = [trimesh.creation.box((w-2*r, h, depth)),
             trimesh.creation.box((w, h-2*r, depth))]
    for x in (-w/2+r, w/2-r):
        for y in (-h/2+r, h/2-r):
            c = trimesh.creation.cylinder(radius=r, height=depth, sections=sections)
            c.apply_translation((x, y, 0)); parts.append(c)
    m = trimesh.boolean.union(parts, engine="manifold")
    m.apply_translation((0, 0, z0+depth/2))
    return m


def rounded_ring(ow, oh, r, iw, ih, ir, depth, z0):
    outer = rounded_prism(ow, oh, r, depth, z0)
    inner = rounded_prism(iw, ih, ir, depth+2, z0-1)
    return trimesh.boolean.difference([outer, inner], engine="manifold")


def capsule_x(w, h, depth_y, x, y, z):
    r = h/2
    parts = [trimesh.creation.box((w-2*r, depth_y, h))]
    rot = trimesh.transformations.rotation_matrix(np.pi/2, [1, 0, 0])
    for dx in (-(w/2-r), w/2-r):
        c = trimesh.creation.cylinder(radius=r, height=depth_y, sections=64)
        c.apply_transform(rot); c.apply_translation((dx, 0, 0)); parts.append(c)
    m = trimesh.boolean.union(parts, engine="manifold")
    m.apply_translation((x, y, z)); return m


def main():
    cw, ch = SCREEN_W+FIT_XY, SCREEN_H+FIT_XY
    pocket_end = SCREEN_D+FIT_Z
    shell_end = pocket_end+STOP_T
    back_z = shell_end+ELECTRONICS_D
    pw, ph = cw+2*POCKET_BORDER, ch+2*POCKET_BORDER

    # Only 3 mm thick across the screw-hole flange.
    flange = rounded_ring(FRONT_W, FRONT_H, FRONT_R, cw, ch,
                          SCREEN_R+FIT_XY/2, FRONT_T, 0)

    # A narrow guide ring follows the screen, rather than thickening the full face.
    guide = rounded_ring(pw, ph, SCREEN_R+FIT_XY/2+POCKET_BORDER,
                         cw, ch, SCREEN_R+FIT_XY/2,
                         pocket_end-FRONT_T+0.6, FRONT_T-0.3)
    stop = rounded_ring(pw, ph, SCREEN_R+FIT_XY/2+POCKET_BORDER,
                        SCREEN_W-2.4, SCREEN_H-2.4,
                        max(1.0, SCREEN_R-1.2), STOP_T+0.6, pocket_end-0.3)

    outer = trimesh.creation.box((NECK_W, NECK_H, ELECTRONICS_D+1))
    outer.apply_translation((0, 0, shell_end+(ELECTRONICS_D-1)/2))
    inner = trimesh.creation.box((NECK_W-2*WALL, NECK_H-2*WALL,
                                  ELECTRONICS_D+2))
    inner.apply_translation((0, 0, shell_end+1+ELECTRONICS_D/2))
    tunnel = trimesh.boolean.difference([outer, inner], engine="manifold")
    rail = trimesh.load_mesh(REF, process=True)
    rail.apply_translation((0, 0, back_z-1))
    result = trimesh.boolean.union([flange, guide, stop, tunnel, rail],
                                   engine="manifold", check_volume=False)

    cutters = []
    for x in (-HOLE_X, HOLE_X):
        for y in (-HOLE_Y, HOLE_Y):
            bore = trimesh.creation.cylinder(radius=HOLE_D/2,
                                              height=FRONT_T+2, sections=64)
            bore.apply_translation((x, y, FRONT_T/2))
            # Conical M4 countersink: 8.6 mm at face, 4.5 mm at 2 mm depth.
            sink = trimesh.creation.cone(radius=HEAD_D/2,
                                         height=HEAD_D/2,
                                         sections=64)
            sink.apply_translation((x, y, -0.01))
            cutters.extend((bore, sink))
    cutters += [capsule_x(CABLE_W, CABLE_H, 32, x, 42, CABLE_Z)
                for x in (-CABLE_X, CABLE_X)]
    result = trimesh.boolean.difference([result, *cutters], engine="manifold",
                                        check_volume=False)
    result.remove_unreferenced_vertices(); result.merge_vertices(); result.export(OUT)
    print(f"file={OUT}")
    print(f"front_flange_thickness_mm={FRONT_T}")
    print(f"screen_pocket_mm={cw:.2f} x {ch:.2f} x {pocket_end:.2f}")
    print(f"countersunk_holes=4x M4 clearance {HOLE_D}, head {HEAD_D} x {COUNTERSINK_D}")
    print(f"extents_mm={result.extents.tolist()}")
    print(f"watertight_before_export={result.is_watertight}")


if __name__ == "__main__":
    main()
