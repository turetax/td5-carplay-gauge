#!/usr/bin/env python3
"""Frameless EP-0189 / Raspberry Pi 4B prototype for early Defender Td5.

Coordinate system:
  X = vehicle/dashboard width
  Y = height
  Z = depth into dashboard (screen glass is at Z=0)

The model is deliberately adjustable in Z because the MUD side-hole depth has
not yet been measured.  All values below are millimetres.
"""
from pathlib import Path
import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "3d print/Defender_TD5_EP0189_frameless_prototyp_V2.stl"

# Published/measured display data.
SCREEN_W = 276.29
SCREEN_H = 76.50
SCREEN_R = 6.5              # estimated; verify on physical display
FIT = 0.60
WALL = 2.8

# User measurements from the MUD frame.
MUD_W = 333.0               # A
MUD_H = 137.0               # B
MUD_HOLE_CENTRES_X = 307.0  # C
MUD_LOWER_Y_FROM_BOTTOM = 15.0   # D
MUD_UPPER_Y_FROM_BOTTOM = 125.0  # E

# New shallow screen carrier.
SHALLOW_DEPTH = 10.0
LOCAL_DEPTH = 15.0
LOCAL_W = 40.0
LOCAL_H = 20.0

# Pi 4B is centred; USB/Ethernet face to +X (right).
PI_W = 85.0
PI_H = 56.0
PI_CLEARANCE = 10.0
PI_ZONE_W = 125.0           # extra connector/bend room on the right
PI_ZONE_H = 80.0
PI_TOTAL_DEPTH = 50.0       # 33 mm current stack + 17 mm cable/cooling room

# Rear side brackets. Slots leave 35 mm adjustment in dashboard depth.
BRACKET_Z0 = 12.0
BRACKET_Z1 = 105.0
SLOT_Z_CENTRE = 78.0
SLOT_LENGTH = 35.0
SLOT_DIAMETER = 6.0         # provisional until measured
SIDE_T = (MUD_W - MUD_HOLE_CENTRES_X) / 2 + 3.2


def box(size, centre):
    m = trimesh.creation.box(size)
    m.apply_translation(centre)
    return m


def rounded_prism(w, h, r, depth, z0, sections=48):
    pieces = [box((w - 2*r, h, depth), (0, 0, z0 + depth/2)),
              box((w, h - 2*r, depth), (0, 0, z0 + depth/2))]
    for x in (-w/2+r, w/2-r):
        for y in (-h/2+r, h/2-r):
            c = trimesh.creation.cylinder(radius=r, height=depth,
                                           sections=sections)
            c.apply_translation((x, y, z0 + depth/2))
            pieces.append(c)
    return trimesh.boolean.union(pieces, engine="manifold")


def rounded_ring(ow, oh, r, iw, ih, ir, depth, z0):
    return trimesh.boolean.difference([
        rounded_prism(ow, oh, r, depth, z0),
        rounded_prism(iw, ih, ir, depth + 2, z0 - 1)
    ], engine="manifold")


def slot_along_z(x, y, z, length, diameter):
    """Capsule slot through a side plate; cutter axis is X."""
    r = diameter / 2
    cutter_x = 40.0
    middle = box((cutter_x, diameter, length - diameter), (x, y, z))
    rot = trimesh.transformations.rotation_matrix(np.pi/2, [0, 1, 0])
    ends = []
    for dz in (-(length/2-r), length/2-r):
        c = trimesh.creation.cylinder(radius=r, height=cutter_x, sections=48)
        c.apply_transform(rot)
        c.apply_translation((x, y, z + dz))
        ends.append(c)
    return trimesh.boolean.union([middle, *ends], engine="manifold")


def ventilation_cutters():
    """Hidden upper/lower slots through the Pi hood for natural convection."""
    cuts = []
    for y in (-PI_ZONE_H/2, PI_ZONE_H/2):
        for x in (-38, -19, 0, 19, 38):
            cuts.append(box((12, 8, 3.2), (x, y, 37)))
    return cuts


def face_component_count(mesh):
    """Count connected face groups without optional scipy/networkx packages."""
    parent = list(range(len(mesh.faces)))
    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    def union(a, b):
        a, b = find(a), find(b)
        if a != b:
            parent[b] = a
    owners = {}
    for fi, face in enumerate(mesh.faces):
        for a, b in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0])):
            edge = (min(int(a), int(b)), max(int(a), int(b)))
            if edge in owners:
                union(fi, owners[edge])
            else:
                owners[edge] = fi
    return len({find(i) for i in range(len(mesh.faces))})


def main():
    cavity_w = SCREEN_W + FIT
    cavity_h = SCREEN_H + FIT
    outer_w = cavity_w + 2*WALL
    outer_h = cavity_h + 2*WALL

    # Frameless hidden guide: it starts at the glass plane and has no front lip.
    guide = rounded_ring(outer_w, outer_h, SCREEN_R + WALL,
                         cavity_w, cavity_h, SCREEN_R + FIT/2,
                         SHALLOW_DEPTH, 0)

    # Four small rear retainers contact only the thin outer part of the display.
    retainers = []
    for x in (-118, 118):
        for y in (-38.0, 38.0):
            retainers.append(box((22, 5.0, 2.4), (x, y, 9.0)))

    # User-specified 40 x 20 local 15 mm-deep region, extending outward/left
    # from the Pi's lower-left mounting screw (approx. x=-29, y=-24.5).
    pi_lower_left = (-29.0, -24.5)
    local_x = pi_lower_left[0] - LOCAL_W/2
    local_patch = box((LOCAL_W, LOCAL_H, LOCAL_DEPTH-SHALLOW_DEPTH),
                      (local_x, pi_lower_left[1],
                       SHALLOW_DEPTH + (LOCAL_DEPTH-SHALLOW_DEPTH)/2))

    # Protective open-front Pi hood. It is deep only where needed. The right
    # side has the extra connector space; front remains open toward the display.
    hood_z0 = SHALLOW_DEPTH - 0.8
    hood_outer = box((PI_ZONE_W, PI_ZONE_H, PI_TOTAL_DEPTH-hood_z0),
                     (10.0, 0, (hood_z0+PI_TOTAL_DEPTH)/2))
    hood_inner = box((PI_ZONE_W-2*WALL, PI_ZONE_H-2*WALL,
                      PI_TOTAL_DEPTH-SHALLOW_DEPTH-WALL),
                     (10.0, 0, SHALLOW_DEPTH +
                      (PI_TOTAL_DEPTH-SHALLOW_DEPTH-WALL)/2 - 0.4))
    hood = trimesh.boolean.difference([hood_outer, hood_inner,
                                       *ventilation_cutters()],
                                      engine="manifold", check_volume=False)

    # MUD side plates at measured overall width. They begin behind the display,
    # so no Defender fixings are visible from the front.
    side_x = MUD_W/2 - SIDE_T/2
    side_depth = BRACKET_Z1 - BRACKET_Z0
    sides = [box((SIDE_T, MUD_H, side_depth),
                 (sx, 0, (BRACKET_Z0+BRACKET_Z1)/2))
             for sx in (-side_x, side_x)]

    # Top/bottom triangulation rails connect the screen carrier to side plates.
    # Kept behind Z=12 so they do not create a visible bezel.
    span = MUD_W
    rails = []
    for y in (-outer_h/2 + WALL/2, outer_h/2 - WALL/2):
        rails.append(box((span, WALL, 13.0), (0, y, 15.5)))
    for sx in (-1, 1):
        # vertical gusset near each screen corner
        rails.append(box((18.0, 18.0, 38.0),
                         (sx*(outer_w/2+8.5), 0, 31.0)))

    solid = trimesh.boolean.union([guide, *retainers, local_patch, hood,
                                   *sides, *rails],
                                  engine="manifold", check_volume=False)

    # Two vertical adjustment slots per side at D/E measured Y positions.
    lower_y = -MUD_H/2 + MUD_LOWER_Y_FROM_BOTTOM
    upper_y = -MUD_H/2 + MUD_UPPER_Y_FROM_BOTTOM
    hole_x = MUD_HOLE_CENTRES_X/2
    cutters = [slot_along_z(sx*hole_x, y, SLOT_Z_CENTRE,
                            SLOT_LENGTH, SLOT_DIAMETER)
               for sx in (-1, 1) for y in (lower_y, upper_y)]
    result = trimesh.boolean.difference([solid, *cutters],
                                        engine="manifold", check_volume=False)
    result.remove_unreferenced_vertices()
    result.merge_vertices()
    result.export(OUT)

    print(f"file={OUT}")
    print(f"screen_cavity={cavity_w:.2f} x {cavity_h:.2f} mm, R{SCREEN_R+FIT/2:.2f}")
    print(f"shallow_depth={SHALLOW_DEPTH:.1f} mm")
    print(f"local_patch={LOCAL_W:.1f} x {LOCAL_H:.1f} x {LOCAL_DEPTH:.1f} mm")
    print(f"pi_zone={PI_ZONE_W:.1f} x {PI_ZONE_H:.1f} x {PI_TOTAL_DEPTH:.1f} mm")
    print(f"mud_envelope={MUD_W:.1f} x {MUD_H:.1f} mm")
    print(f"side_slots=4 x {SLOT_LENGTH:.1f} x {SLOT_DIAMETER:.1f} mm (provisional)")
    print(f"watertight={result.is_watertight}")
    print(f"winding_consistent={result.is_winding_consistent}")
    print(f"body_count={face_component_count(result)}")
    print(f"extents={result.extents.tolist()}")
    print(f"triangles={len(result.faces)}")


if __name__ == "__main__":
    main()
