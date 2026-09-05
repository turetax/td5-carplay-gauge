#!/usr/bin/env python3
"""Generate dependency-free ASCII STL prototypes for the Defender screen mount.

All dimensions are millimetres.  Edit the constants below after the first
physical test fit, then run this file with Python 3 again.
"""

from pathlib import Path
from math import sqrt, cos, sin, pi
import struct


OUT = Path(__file__).resolve().parent / "stl"
REFERENCE = Path(__file__).resolve().parent / "reference_thingiverse_5856588"

# Provisional EP-0189 envelope. Published dimensions are approximate.
# Official 52Pi wiki dimensions (±0.1 mm).
SCREEN_W = 276.29
SCREEN_H = 76.50
SCREEN_D = 15.0
CLEARANCE = 0.6
VIEW_W = 252.69
VIEW_H = 57.90
# Not published. Estimated by scaling the manufacturer's straight-on image.
SCREEN_CORNER_R = 6.5

# Prototype housing.
BEZEL_BORDER = 4.0
BEZEL_T = 3.0
VIEW_MARGIN = 1.0
POCKET_D = SCREEN_D + 1.2
WALL = 2.4

# Approximate useful face of the MUD-0039/AWR2277 mounting region.
NECK_W = 198.0
NECK_H = 70.0
ELECTRONICS_D = 62.0

# Deliberately broad trial slots for the unknown Defender rear fixing centres.
# Each M4 slot spans X=65..105 mm from centre, covering 130..210 mm symmetric
# screw spacing. The rail is a test interface, not final fixing geometry.
MOUNT_RAIL_W = 220.0
MOUNT_RAIL_H = 22.0
MOUNT_RAIL_T = 3.0
MOUNT_SLOT_INNER_X = 65.0
MOUNT_SLOT_OUTER_X = 105.0
MOUNT_SLOT_H = 5.2


def normal(a, b, c):
    ux, uy, uz = (b[i] - a[i] for i in range(3))
    vx, vy, vz = (c[i] - a[i] for i in range(3))
    n = (uy*vz-uz*vy, uz*vx-ux*vz, ux*vy-uy*vx)
    length = sqrt(sum(v*v for v in n)) or 1.0
    return tuple(v/length for v in n)


def box(x0, x1, y0, y1, z0, z1):
    v = [(x0,y0,z0),(x1,y0,z0),(x1,y1,z0),(x0,y1,z0),
         (x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1)]
    f = [(0,2,1),(0,3,2),(4,5,6),(4,6,7),
         (0,1,5),(0,5,4),(1,2,6),(1,6,5),
         (2,3,7),(2,7,6),(3,0,4),(3,4,7)]
    return [(v[a],v[b],v[c]) for a,b,c in f]


def ring(ow, oh, iw, ih, z0, z1):
    """Rectangular ring centred on X/Y, made from four printable bars."""
    ox, oy, ix, iy = ow/2, oh/2, iw/2, ih/2
    tris = []
    tris += box(-ox, ox, iy, oy, z0, z1)
    tris += box(-ox, ox, -oy, -iy, z0, z1)
    tris += box(-ox, -ix, -iy, iy, z0, z1)
    tris += box(ix, ox, -iy, iy, z0, z1)
    return tris


def rounded_rect_points(w, h, r, arc_steps=8):
    """CCW points for a centred rounded rectangle."""
    r = max(0.01, min(r, w/2, h/2))
    pts = []
    for cx,cy,start in [(w/2-r,h/2-r,0),(-w/2+r,h/2-r,pi/2),
                        (-w/2+r,-h/2+r,pi),(w/2-r,-h/2+r,3*pi/2)]:
        for i in range(arc_steps+1):
            a = start + i*(pi/2)/arc_steps
            pts.append((cx+r*cos(a), cy+r*sin(a)))
    return pts


def rounded_ring(ow, oh, outer_r, iw, ih, inner_r, z0, z1):
    """Closed rounded-rectangle annulus with matching point counts."""
    outer = rounded_rect_points(ow, oh, outer_r)
    inner = rounded_rect_points(iw, ih, inner_r)
    n = len(outer); t = []
    for i in range(n):
        j = (i+1) % n
        o0,o1 = outer[i],outer[j]; q0,q1 = inner[i],inner[j]
        # front annulus, back annulus, outer wall and inner wall
        t += [((o0[0],o0[1],z0),(q1[0],q1[1],z0),(o1[0],o1[1],z0)),
              ((o0[0],o0[1],z0),(q0[0],q0[1],z0),(q1[0],q1[1],z0)),
              ((o0[0],o0[1],z1),(o1[0],o1[1],z1),(q1[0],q1[1],z1)),
              ((o0[0],o0[1],z1),(q1[0],q1[1],z1),(q0[0],q0[1],z1)),
              ((o0[0],o0[1],z0),(o1[0],o1[1],z0),(o1[0],o1[1],z1)),
              ((o0[0],o0[1],z0),(o1[0],o1[1],z1),(o0[0],o0[1],z1)),
              ((q0[0],q0[1],z0),(q1[0],q1[1],z1),(q1[0],q1[1],z0)),
              ((q0[0],q0[1],z0),(q0[0],q0[1],z1),(q1[0],q1[1],z1))]
    return t


def write_stl(path, name, tris):
    with path.open("w", encoding="ascii") as f:
        f.write(f"solid {name}\n")
        for a,b,c in tris:
            nx,ny,nz = normal(a,b,c)
            f.write(f" facet normal {nx:.7g} {ny:.7g} {nz:.7g}\n  outer loop\n")
            for x,y,z in (a,b,c):
                f.write(f"   vertex {x:.7g} {y:.7g} {z:.7g}\n")
            f.write("  endloop\n endfacet\n")
        f.write(f"endsolid {name}\n")


def read_binary_stl(path):
    """Read triangles from the binary STL format used by the reference."""
    data = path.read_bytes()
    count = struct.unpack("<I", data[80:84])[0]
    if 84 + count*50 != len(data):
        raise ValueError(f"Unexpected STL format: {path}")
    tris = []
    for i in range(count):
        values = struct.unpack("<12fH", data[84+i*50:84+(i+1)*50])
        tris.append((values[3:6], values[6:9], values[9:12]))
    return tris


def translated(tris, dx=0.0, dy=0.0, dz=0.0):
    return [tuple((x+dx, y+dy, z+dz) for x,y,z in tri) for tri in tris]


def slotted_mount_rail(z0=0.0):
    """Rail with two true through-slots, made without boolean operations."""
    hw, hh = MOUNT_RAIL_W/2, MOUNT_RAIL_H/2
    sh = MOUNT_SLOT_H/2
    xi, xo = MOUNT_SLOT_INNER_X, MOUNT_SLOT_OUTER_X
    z1 = z0 + MOUNT_RAIL_T
    t = []
    # Continuous material above and below both slots.
    t += box(-hw, hw, sh, hh, z0, z1)
    t += box(-hw, hw, -hh, -sh, z0, z1)
    # Solid islands: outer ends and centre between slots.
    t += box(-hw, -xo, -sh, sh, z0, z1)
    t += box(-xi, xi, -sh, sh, z0, z1)
    t += box(xo, hw, -sh, sh, z0, z1)
    return t


def full_housing(include_trial_rail=True):
    cavity_w = SCREEN_W + CLEARANCE
    cavity_h = SCREEN_H + CLEARANCE
    outer_w = cavity_w + 2*BEZEL_BORDER
    outer_h = cavity_h + 2*BEZEL_BORDER
    # Expose the official viewing area plus 1 mm margin on every side.
    opening_w = VIEW_W + 2*VIEW_MARGIN
    opening_h = VIEW_H + 2*VIEW_MARGIN
    z_pocket = BEZEL_T + POCKET_D
    z_back = z_pocket + ELECTRONICS_D
    t = []
    # Front retaining bezel and screen pocket walls (back-loading screen).
    t += rounded_ring(outer_w, outer_h, SCREEN_CORNER_R+BEZEL_BORDER,
                      opening_w, opening_h, max(1.0, SCREEN_CORNER_R-2.0),
                      0, BEZEL_T)
    t += box(-outer_w/2, outer_w/2, cavity_h/2, outer_h/2, BEZEL_T, z_pocket)
    t += box(-outer_w/2, outer_w/2, -outer_h/2, -cavity_h/2, BEZEL_T, z_pocket)
    t += box(-outer_w/2, -cavity_w/2, -cavity_h/2, cavity_h/2, BEZEL_T, z_pocket)
    t += box(cavity_w/2, outer_w/2, -cavity_h/2, cavity_h/2, BEZEL_T, z_pocket)
    # Low central electronics tunnel. Open at the rear for wiring/service.
    nw, nh = NECK_W, NECK_H
    t += box(-nw/2, nw/2, nh/2-WALL, nh/2, z_pocket, z_back)
    t += box(-nw/2, nw/2, -nh/2, -nh/2+WALL, z_pocket, z_back)
    t += box(-nw/2, -nw/2+WALL, -nh/2+WALL, nh/2-WALL, z_pocket, z_back)
    t += box(nw/2-WALL, nw/2, -nh/2+WALL, nh/2-WALL, z_pocket, z_back)
    # Shoulder plate ties the wide screen pocket to the 198 x 70 mm tunnel.
    t += ring(outer_w, outer_h, nw-2*WALL, nh-2*WALL,
              z_pocket, z_pocket+WALL)
    # Provisional Defender rear fixing rail at the open end of the tunnel.
    if include_trial_rail:
        t += slotted_mount_rail(z_back)
    return t


def reference_fit_housing():
    """One-piece concept using mbrooker's tested pre-Td5 vent rail geometry."""
    t = full_housing(include_trial_rail=False)
    ref = REFERENCE / "Binnacle_Vent_Rail_v1.1.stl"
    if not ref.exists():
        raise FileNotFoundError(f"Missing Thingiverse reference: {ref}")
    z_pocket = BEZEL_T + POCKET_D
    z_back = z_pocket + ELECTRONICS_D
    # The reference rail is already centred in XY. Sink it 0.8 mm into the
    # tunnel end so common slicers merge both closed shells into one part.
    t += translated(read_binary_stl(ref), dz=z_back-0.8)
    return t


def flush_reference_housing():
    """One-piece test housing with the EP-0189 front flush to the outer face."""
    cavity_w = SCREEN_W + CLEARANCE
    cavity_h = SCREEN_H + CLEARANCE
    outer_w = cavity_w + 2*BEZEL_BORDER
    outer_h = cavity_h + 2*BEZEL_BORDER
    screen_stop_z = SCREEN_D + CLEARANCE/2
    stop_t = 2.2
    z_pocket_end = screen_stop_z + stop_t
    z_back = z_pocket_end + ELECTRONICS_D
    t = []

    # Surround only: no material overlaps the screen's front surface.
    t += rounded_ring(outer_w, outer_h, SCREEN_CORNER_R+BEZEL_BORDER,
                      cavity_w, cavity_h, SCREEN_CORNER_R+CLEARANCE/2,
                      0, BEZEL_T)

    # Guide walls behind the flush opening.
    t += box(-outer_w/2, outer_w/2, cavity_h/2, outer_h/2,
             BEZEL_T, z_pocket_end)
    t += box(-outer_w/2, outer_w/2, -outer_h/2, -cavity_h/2,
             BEZEL_T, z_pocket_end)
    t += box(-outer_w/2, -cavity_w/2, -cavity_h/2, cavity_h/2,
             BEZEL_T, z_pocket_end)
    t += box(cavity_w/2, outer_w/2, -cavity_h/2, cavity_h/2,
             BEZEL_T, z_pocket_end)

    # Rear perimeter stop. It overlaps the screen back edge by 1.2 mm and
    # leaves the centre open for the Pi and connectors.
    stop_open_w = SCREEN_W - 2.4
    stop_open_h = SCREEN_H - 2.4
    t += rounded_ring(outer_w, outer_h, SCREEN_CORNER_R+BEZEL_BORDER,
                      stop_open_w, stop_open_h,
                      max(1.0, SCREEN_CORNER_R-1.2),
                      screen_stop_z, z_pocket_end)

    # Electronics tunnel, open at the rear for service and cable routing.
    nw, nh = NECK_W, NECK_H
    t += box(-nw/2, nw/2, nh/2-WALL, nh/2, z_pocket_end, z_back)
    t += box(-nw/2, nw/2, -nh/2, -nh/2+WALL, z_pocket_end, z_back)
    t += box(-nw/2, -nw/2+WALL, -nh/2+WALL, nh/2-WALL,
             z_pocket_end, z_back)
    t += box(nw/2-WALL, nw/2, -nh/2+WALL, nh/2-WALL,
             z_pocket_end, z_back)
    t += rounded_ring(outer_w, outer_h, SCREEN_CORNER_R+BEZEL_BORDER,
                      nw-2*WALL, nh-2*WALL, 2.0,
                      z_pocket_end, z_pocket_end+WALL)

    ref = REFERENCE / "Binnacle_Vent_Rail_v1.1.stl"
    if not ref.exists():
        raise FileNotFoundError(f"Missing Thingiverse reference: {ref}")
    t += translated(read_binary_stl(ref), dz=z_back-0.8)
    return t


def fit_coupon():
    """Two corner gauges joined by a thin bar; quick check of W/H/D."""
    cw, ch, cd = SCREEN_W+CLEARANCE, SCREEN_H+CLEARANCE, SCREEN_D+0.6
    leg, thick = 16.0, 2.2
    t = []
    # Bottom-left and top-right L-shaped corner gauges.
    for sx, sy in [(-1,-1),(1,1)]:
        x_edge = sx*cw/2
        y_edge = sy*ch/2
        xa, xb = (x_edge-thick, x_edge+leg) if sx < 0 else (x_edge-leg, x_edge+thick)
        ya, yb = (y_edge-thick, y_edge+leg) if sy < 0 else (y_edge-leg, y_edge+thick)
        t += box(xa, xb, y_edge-thick if sy < 0 else y_edge, y_edge if sy < 0 else y_edge+thick, 0, cd)
        t += box(x_edge-thick if sx < 0 else x_edge, x_edge if sx < 0 else x_edge+thick, ya, yb, 0, cd)
    # Break-away diagonal reference bar, one layer-ish thick.
    steps = 25
    for i in range(steps):
        x0 = -cw/2 + leg + i*(cw-2*leg)/steps
        x1 = -cw/2 + leg + (i+1)*(cw-2*leg)/steps
        y = -ch/2 + leg + (i+0.5)*(ch-2*leg)/steps
        t += box(x0, x1, y-0.65, y+0.65, 0, 0.7)
    return t


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    write_stl(OUT / "defender_ep0189_concept_housing.stl",
              "defender_ep0189_concept_housing", full_housing())
    write_stl(OUT / "ep0189_fit_coupon.stl",
              "ep0189_fit_coupon", fit_coupon())
    write_stl(OUT / "defender_mount_slot_template.stl",
              "defender_mount_slot_template", slotted_mount_rail())
    write_stl(OUT / "defender_ep0189_one_piece_reference_fit.stl",
              "defender_ep0189_one_piece_reference_fit", reference_fit_housing())
    write_stl(OUT / "defender_ep0189_v4_flush_one_piece.stl",
              "defender_ep0189_v4_flush_one_piece", flush_reference_housing())
    print(f"Wrote STL files to {OUT}")


if __name__ == "__main__":
    main()
