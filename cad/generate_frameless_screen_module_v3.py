#!/usr/bin/env python3
"""Compact frameless EP-0189 + Pi 4B screen module.

No Defender or MUD mounting pattern is included.  The four compact rear pads
are the interface to a separate relay/base box, which will mount to the car.
X=width, Y=height, Z=depth behind the visible screen glass. Units are mm.
"""
from pathlib import Path
import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "3d print/Defender_EP0189_skarmmodul_V3.stl"

SCREEN_W, SCREEN_H = 276.29, 76.50
SCREEN_R = 6.5                  # estimated pending physical radius check
FIT = 0.60
WALL = 2.8
SHALLOW_DEPTH = 10.0
SCREEN_REAR = 15.3
BACK_T = 2.4

# Pi 4B: centred on display, USB/Ethernet to +X/right.
PI_BOARD_W, PI_BOARD_H = 85.0, 56.0
PI_ZONE_W, PI_ZONE_H = 125.0, 80.0
PI_COVER_REAR = 50.0            # 33 mm current stack + cable/cooling margin

# Local display feature requested by user: from Pi lower-left screw outward.
LOCAL_W, LOCAL_H, LOCAL_REAR = 40.0, 20.0, 15.0
PI_LL_SCREW = (-29.0, -24.5)

# Hidden downward cable routes to the future relay/base box. These sizes admit
# moulded connector bodies, not just bare cable.
POWER_PORT = (36.0, 20.0)       # USB power plugs: width x Z-height
SIGNAL_PORT = (46.0, 18.0)      # relay signal plugs/harness

# Compact rear mounting pattern for relay/base box (not Defender pattern).
MOUNT_X, MOUNT_Y = 52.0, 31.0
MOUNT_PAD = (18.0, 12.0, 4.0)
MOUNT_HOLE_D = 4.5


def box(size, centre):
    m = trimesh.creation.box(size)
    m.apply_translation(centre)
    return m


def rounded_prism(w, h, r, depth, z0, sections=48):
    pieces = [box((w-2*r, h, depth), (0, 0, z0+depth/2)),
              box((w, h-2*r, depth), (0, 0, z0+depth/2))]
    for x in (-w/2+r, w/2-r):
        for y in (-h/2+r, h/2-r):
            c = trimesh.creation.cylinder(radius=r, height=depth,
                                           sections=sections)
            c.apply_translation((x, y, z0+depth/2))
            pieces.append(c)
    return trimesh.boolean.union(pieces, engine="manifold")


def rounded_ring(ow, oh, r, iw, ih, ir, depth, z0):
    return trimesh.boolean.difference([
        rounded_prism(ow, oh, r, depth, z0),
        rounded_prism(iw, ih, ir, depth+2, z0-1)
    ], engine="manifold")


def face_component_count(mesh):
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
    for fi, f in enumerate(mesh.faces):
        for a, b in ((f[0],f[1]),(f[1],f[2]),(f[2],f[0])):
            e = (min(int(a),int(b)), max(int(a),int(b)))
            if e in owners: union(fi, owners[e])
            else: owners[e] = fi
    return len({find(i) for i in range(len(mesh.faces))})


def main():
    cw, ch = SCREEN_W+FIT, SCREEN_H+FIT
    ow, oh = cw+2*WALL, ch+2*WALL

    # No printed bezel in front of the glass: only a hidden 10 mm perimeter.
    # Continuous perimeter all the way to the rear cover.  Earlier V3 stopped
    # at Z=10 and left a visible/open gap before the rear cover at Z=15.3.
    guide = rounded_ring(ow, oh, SCREEN_R+WALL, cw, ch,
                         SCREEN_R+FIT/2, SCREEN_REAR+BACK_T, 0)

    # Thin rear screen cover, open only inside the protected Pi zone.
    rear = rounded_prism(ow, oh, SCREEN_R+WALL, BACK_T, SCREEN_REAR)
    pi_open = box((PI_ZONE_W-2*WALL, PI_ZONE_H-2*WALL, BACK_T+2),
                  (10.0, 0, SCREEN_REAR+BACK_T/2))
    rear = trimesh.boolean.difference([rear, pi_open], engine="manifold")

    # Small hidden retainers secure the thin outer edge of the display.
    retainers = []
    for x in (-118, 118):
        for y in (-38.0, 38.0):
            retainers.append(box((22, 5.0, 2.6), (x, y, 9.2)))

    # Local 40 x 20 region extending left/outward from Pi lower-left screw.
    local = box((LOCAL_W, LOCAL_H, LOCAL_REAR-SHALLOW_DEPTH),
                (PI_LL_SCREW[0]-LOCAL_W/2, PI_LL_SCREW[1],
                 SHALLOW_DEPTH+(LOCAL_REAR-SHALLOW_DEPTH)/2))

    # Closed Pi hood. Its front overlaps the guide/rear cover; rear is capped.
    hood_z0 = 9.2
    hood_outer = box((PI_ZONE_W, PI_ZONE_H, PI_COVER_REAR-hood_z0),
                     (10.0, 0, (hood_z0+PI_COVER_REAR)/2))
    hood_inner = box((PI_ZONE_W-2*WALL, PI_ZONE_H-2*WALL,
                      PI_COVER_REAR-hood_z0-2*WALL),
                     (10.0, 0, hood_z0+WALL+
                      (PI_COVER_REAR-hood_z0-2*WALL)/2))
    hood = trimesh.boolean.difference([hood_outer, hood_inner],
                                      engine="manifold")

    # Connector-sized passages face downward into the relay box. They are
    # recessed from both side edges, so no wiring is visible side-on.
    power_cut = box((POWER_PORT[0], 9.0, POWER_PORT[1]),
                    (-25.0, -PI_ZONE_H/2, 28.0))
    signal_cut = box((SIGNAL_PORT[0], 9.0, SIGNAL_PORT[1]),
                     (27.0, -PI_ZONE_H/2, 28.0))

    # Matching rear-facing connector passages into the relay box. Placement
    # stays between the four mounting pads and inside the outer silhouette.
    rear_power_cut = box((34.0, 18.0, 8.0),
                         (-31.0, 0, PI_COVER_REAR))
    rear_signal_cut = box((42.0, 16.0, 8.0),
                          (31.0, 0, PI_COVER_REAR))

    # Discreet rear ventilation slots, protected from direct side view.
    vent_cuts = []
    for y in (-22, -11, 0, 11, 22):
        for x in (-36, -18, 0, 18, 36, 54):
            vent_cuts.append(box((12.0, 2.4, 6.0),
                                 (x, y, PI_COVER_REAR-1.0)))
    # Additional narrow vents in the rear wings outside the Pi cover.
    for x in (-118, -96, 96, 118):
        for y in (-20, 0, 20):
            vent_cuts.append(box((14.0, 2.2, BACK_T+2),
                                 (x, y, SCREEN_REAR+BACK_T/2)))

    hood = trimesh.boolean.difference([hood, power_cut, signal_cut,
                                       rear_power_cut, rear_signal_cut,
                                       *vent_cuts[:30]],
                                      engine="manifold", check_volume=False)
    rear = trimesh.boolean.difference([rear, *vent_cuts[30:]],
                                      engine="manifold", check_volume=False)

    # Four compact pads on the rear face mate only with the future relay box.
    pads = []
    holes = []
    for x in (-MOUNT_X, MOUNT_X):
        for y in (-MOUNT_Y, MOUNT_Y):
            pads.append(box(MOUNT_PAD,
                            (x, y, PI_COVER_REAR+MOUNT_PAD[2]/2-0.4)))
            c = trimesh.creation.cylinder(radius=MOUNT_HOLE_D/2,
                                           height=MOUNT_PAD[2]+4,
                                           sections=48)
            c.apply_translation((x, y, PI_COVER_REAR+MOUNT_PAD[2]/2))
            holes.append(c)

    solid = trimesh.boolean.union([guide, rear, hood, local,
                                   *retainers, *pads],
                                  engine="manifold", check_volume=False)
    result = trimesh.boolean.difference([solid, *holes],
                                        engine="manifold", check_volume=False)
    result.remove_unreferenced_vertices()
    result.merge_vertices()
    result.export(OUT)

    print(f"file={OUT}")
    print(f"screen_pocket={cw:.2f} x {ch:.2f} R{SCREEN_R+FIT/2:.2f}")
    print(f"outer={ow:.2f} x {oh:.2f} x {PI_COVER_REAR+MOUNT_PAD[2]-0.4:.1f}")
    print(f"power_port={POWER_PORT[0]} x {POWER_PORT[1]}")
    print(f"signal_port={SIGNAL_PORT[0]} x {SIGNAL_PORT[1]}")
    print(f"relay_box_mount=4 x diameter {MOUNT_HOLE_D} at +-{MOUNT_X}, +-{MOUNT_Y}")
    print(f"watertight={result.is_watertight}")
    print(f"winding_consistent={result.is_winding_consistent}")
    print(f"body_count={face_component_count(result)}")
    print(f"extents={result.extents.tolist()}")
    print(f"triangles={len(result.faces)}")


if __name__ == "__main__":
    main()
