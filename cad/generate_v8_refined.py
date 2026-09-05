#!/usr/bin/env python3
"""Generate a cleaner, dimension-audited Defender/EP-0189 prototype."""

from pathlib import Path
import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "cad" / "reference_thingiverse_5856588" / "Binnacle_Vent_Rail_v1.1.stl"
OUT = ROOT / "3d print" / "Defender_EP0189_V8_snyggad_kontrollmatt.stl"

# Published EP-0189 body dimensions; depth and radius remain provisional.
SCREEN_W, SCREEN_H, SCREEN_D = 276.29, 76.50, 15.0
FIT_XY, FIT_Z, SCREEN_R = 0.60, 0.30, 6.5

# Defender reference envelope and hole pattern measured from Thingiverse 5856588.
FRONT_W, FRONT_H, FRONT_R = 286.0, 120.0, 10.0
HOLE_X, HOLE_Y, HOLE_D = 111.0, 52.0, 4.5

FRONT_T, STOP_T = 3.0, 2.4
NECK_W, NECK_H, WALL, ELECTRONICS_D = 198.0, 70.0, 2.8, 62.0
CABLE_W, CABLE_H, CABLE_X, CABLE_Z = 50.0, 16.0, 48.0, 22.0


def rounded_prism(w, h, r, depth, z0, sections=64):
    parts = [trimesh.creation.box((w - 2*r, h, depth)),
             trimesh.creation.box((w, h - 2*r, depth))]
    for x in (-w/2+r, w/2-r):
        for y in (-h/2+r, h/2-r):
            c = trimesh.creation.cylinder(radius=r, height=depth, sections=sections)
            c.apply_translation((x, y, 0))
            parts.append(c)
    m = trimesh.boolean.union(parts, engine="manifold")
    m.apply_translation((0, 0, z0 + depth/2))
    return m


def capsule_x(w, h, depth_y, x, y, z):
    r = h/2
    parts = [trimesh.creation.box((w - 2*r, depth_y, h))]
    rot = trimesh.transformations.rotation_matrix(np.pi/2, [1, 0, 0])
    for dx in (-(w/2-r), w/2-r):
        c = trimesh.creation.cylinder(radius=r, height=depth_y, sections=64)
        c.apply_transform(rot)
        c.apply_translation((dx, 0, 0))
        parts.append(c)
    m = trimesh.boolean.union(parts, engine="manifold")
    m.apply_translation((x, y, z))
    return m


def main():
    cavity_w, cavity_h = SCREEN_W + FIT_XY, SCREEN_H + FIT_XY
    pocket_end = SCREEN_D + FIT_Z
    shell_end = pocket_end + STOP_T
    back_z = shell_end + ELECTRONICS_D

    # Clean rounded front shell. The screen face is flush at Z=0.
    shell = rounded_prism(FRONT_W, FRONT_H, FRONT_R, shell_end, 0)
    screen_cavity = rounded_prism(cavity_w, cavity_h, SCREEN_R + FIT_XY/2,
                                  pocket_end + 1.0, -0.5)
    rear_open = rounded_prism(SCREEN_W - 2.4, SCREEN_H - 2.4,
                              max(1.0, SCREEN_R - 1.2), STOP_T + 1.0,
                              pocket_end)
    shell = trimesh.boolean.difference([shell, screen_cavity, rear_open],
                                       engine="manifold")

    # Hollow electronics tunnel with 2.8 mm walls and an open service rear.
    outer = trimesh.creation.box((NECK_W, NECK_H, ELECTRONICS_D + 1.0))
    outer.apply_translation((0, 0, shell_end + (ELECTRONICS_D - 1.0)/2))
    inner = trimesh.creation.box((NECK_W - 2*WALL, NECK_H - 2*WALL,
                                  ELECTRONICS_D + 2.0))
    inner.apply_translation((0, 0, shell_end + 1.0 + ELECTRONICS_D/2))
    tunnel = trimesh.boolean.difference([outer, inner], engine="manifold")

    # The tested Defender vent rail overlaps the tunnel by 1 mm.
    rail = trimesh.load_mesh(REF, process=True)
    rail.apply_translation((0, 0, back_z - 1.0))
    result = trimesh.boolean.union([shell, tunnel, rail], engine="manifold",
                                   check_volume=False)

    # Four M4 clearance holes copied from the reference front plate.
    holes = []
    for x in (-HOLE_X, HOLE_X):
        for y in (-HOLE_Y, HOLE_Y):
            h = trimesh.creation.cylinder(radius=HOLE_D/2,
                                          height=shell_end + 2, sections=48)
            h.apply_translation((x, y, shell_end/2))
            holes.append(h)

    # Two rounded top exits immediately behind the 15 mm screen body.
    cables = [capsule_x(CABLE_W, CABLE_H, 32.0, x, 42.0, CABLE_Z)
              for x in (-CABLE_X, CABLE_X)]
    result = trimesh.boolean.difference([result, *holes, *cables],
                                        engine="manifold", check_volume=False)
    result.remove_unreferenced_vertices()
    result.merge_vertices()
    result.export(OUT)

    print(f"file={OUT}")
    print(f"screen_pocket_mm={cavity_w:.2f} x {cavity_h:.2f} x {pocket_end:.2f}")
    print(f"front_mm={FRONT_W:.1f} x {FRONT_H:.1f}")
    print(f"hole_centres_mm=(+-{HOLE_X:.1f}, +-{HOLE_Y:.1f}), diameter={HOLE_D:.1f}")
    print(f"cable_slots_mm={CABLE_W:.1f} x {CABLE_H:.1f}, z={CABLE_Z-CABLE_H/2:.1f}..{CABLE_Z+CABLE_H/2:.1f}")
    print(f"extents_mm={result.extents.tolist()}")
    print(f"watertight_before_export={result.is_watertight}")


if __name__ == "__main__":
    main()
