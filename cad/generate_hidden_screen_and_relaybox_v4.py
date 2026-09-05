#!/usr/bin/env python3
"""Hidden EP-0189 screen carrier + matching relay/electrical box.

Everything printed stays inside the 276.29 x 76.50 mm glass silhouette.
The screen carrier is glued to the rear corners of the display.  It bolts to
the electrical box using M4 heat-set inserts in the box.  The box lid uses M3
heat-set inserts.  No MUD or Defender hole pattern is assumed.
"""
from pathlib import Path
import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parents[1]
OUTDIR = ROOT / "3d print"
SCREEN_OUT = OUTDIR / "Defender_EP0189_utan_armfasten_kabeloppningar_V21.stl"
BOX_OUT = OUTDIR / "Defender_relabox_rela_vanster_V15.stl"
LID_OUT = OUTDIR / "Defender_relabox_lock_utan_armar_V24.stl"
ANGLE_OUT = OUTDIR / "Defender_relabox_lutningsadapter_42deg_V5.stl"

SCREEN_W, SCREEN_H = 276.29, 76.50
PRINT_W, PRINT_H = 273.8, 73.8       # hidden by glass from straight ahead
CORNER_R = 5.4
WALL = 2.8
GLUE_Z0 = 3.2                        # thin screen corners are about 3 mm
SCREEN_BODY_REAR = 15.3
SCREEN_COVER_REAR = 50.0             # includes Pi + cable/cooling margin
SLIM_REAR = 15.3                     # all non-Pi regions stop here
PI_HOOD_W, PI_HOOD_H = 125.0, 70.0

# Matching screen-to-box interface. Four M4 clearance holes in carrier;
# corresponding heat-set pockets are in the electrical box.
MOUNT_X, MOUNT_Y = 52.0, 27.0
M4_CLEAR = 4.5
M4_INSERT_PILOT = 5.2                # test against the actual insert batch

# Connector-sized hidden pass-throughs between carrier and electrical box.
POWER_C = (-31.0, 0.0)
POWER_WH = (34.0, 18.0)
SIGNAL_C = (31.0, 0.0)
SIGNAL_WH = (42.0, 16.0)

# Electrical box stays inside screen silhouette.
BOX_W, BOX_H, BOX_D = 250.0, 73.0, 70.0
BOX_WALL, BOX_FRONT = 2.8, 3.2
LID_T = 3.0

# Known components.
RELAY_W, RELAY_H, RELAY_D = 73.0, 50.0, 18.5
RELAY_CX = -61.0
RELAY_HOLE_PITCH = (65.0, 42.0)      # adjustable/provisional board pattern
M3_INSERT_PILOT = 4.0
M3_CLEAR = 3.4
USB_PANEL_HOLE = 30.4                # nominal product cut-out is 30 mm
USB_FACE_D = 37.0
USB_BODY_LENGTH = 57.0

# Measured Defender dash side profile (reference/collision envelope).
DASH_FRONT_LIP_H = 50.0
DASH_FRONT_LIP_D = 120.0
DASH_SLOPE_START_H = 50.0


def box(size, centre):
    m = trimesh.creation.box(size)
    m.apply_translation(centre)
    return m


def cyl_z(radius, height, centre, sections=48):
    m = trimesh.creation.cylinder(radius=radius, height=height,
                                   sections=sections)
    m.apply_translation(centre)
    return m


def cyl_x(radius, height, centre, sections=64):
    m = trimesh.creation.cylinder(radius=radius, height=height,
                                   sections=sections)
    m.apply_transform(trimesh.transformations.rotation_matrix(np.pi/2,
                                                               [0, 1, 0]))
    m.apply_translation(centre)
    return m


def cyl_y(radius, height, centre, sections=48):
    m = trimesh.creation.cylinder(radius=radius, height=height,
                                   sections=sections)
    m.apply_transform(trimesh.transformations.rotation_matrix(np.pi/2,
                                                               [1, 0, 0]))
    m.apply_translation(centre)
    return m


def beam_between(p0,p1,width,thickness):
    """Rectangular structural beam whose long axis connects p0 to p1."""
    p0=np.array(p0,float); p1=np.array(p1,float); direction=p1-p0
    length=float(np.linalg.norm(direction))
    m=box((width,thickness,length),(0,0,0))
    align=trimesh.geometry.align_vectors([0,0,1],direction/length)
    m.apply_transform(align); m.apply_translation((p0+p1)/2)
    return m


def tube_between(p0,p1,width,height,wall=2.4):
    """Open-ended rectangular tube for a complete moulded connector harness."""
    p0=np.array(p0,float); p1=np.array(p1,float); direction=p1-p0
    length=float(np.linalg.norm(direction)); mid=(p0+p1)/2
    align=trimesh.geometry.align_vectors([0,0,1],direction/length)
    outer=box((width,height,length),(0,0,0)); outer.apply_transform(align); outer.apply_translation(mid)
    inner=box((width-2*wall,height-2*wall,length+3),(0,0,0)); inner.apply_transform(align); inner.apply_translation(mid)
    return trimesh.boolean.difference([outer,inner],engine="manifold")


def rect_between_yz(p0,p1,width,height):
    """Rectangular solid along a YZ line, with X orientation locked.

    Unlike a generic vector alignment this cannot roll/twist the cross-section,
    so its broad X face stays flat against a constant-X support arm.
    """
    p0=np.array(p0,float); p1=np.array(p1,float); direction=p1-p0
    if abs(direction[0]) > 1e-8:
        raise ValueError("rect_between_yz requires equal X coordinates")
    length=float(np.linalg.norm(direction))
    angle=-np.arctan2(direction[1],direction[2])
    m=box((width,height,length),(0,0,0))
    m.apply_transform(trimesh.transformations.rotation_matrix(angle,[1,0,0]))
    m.apply_translation((p0+p1)/2)
    return m


def rect_tube_between_yz(p0,p1,width,height,wall=2.4):
    """Open-ended rectangular YZ duct with zero cross-section roll."""
    p0=np.array(p0,float); p1=np.array(p1,float); direction=p1-p0
    unit=direction/np.linalg.norm(direction)
    outer=rect_between_yz(p0,p1,width,height)
    inner=rect_between_yz(p0-unit*1.5,p1+unit*1.5,
                          width-2*wall,height-2*wall)
    return trimesh.boolean.difference([outer,inner],engine="manifold")


def slot_z_through_y(x,y,z,length,diameter,cut_height):
    """Capsule slot along Z with its cutting axis through Y."""
    r=diameter/2
    pieces=[box((diameter,cut_height,length-diameter),(x,y,z))]
    for dz in (-(length/2-r),length/2-r):
        pieces.append(cyl_y(r,cut_height,(x,y,z+dz)))
    return trimesh.boolean.union(pieces,engine="manifold")


def arc_capsules_x(cx,cy,cz,radius,a0,a1,tube_radius,length_x,steps=18):
    """Union of overlapping X-axis cylinders following an arc in YZ."""
    pieces=[]
    for a in np.linspace(np.radians(a0),np.radians(a1),steps):
        y=cy+radius*np.sin(a); z=cz+radius*np.cos(a)
        pieces.append(cyl_x(tube_radius,length_x,(cx,y,z),sections=32))
    return trimesh.boolean.union(pieces,engine="manifold",check_volume=False)


def yz_plate(xcentre,thickness,points):
    """Closed prism with constant X thickness and a polygonal YZ profile."""
    n=len(points); x0=xcentre-thickness/2; x1=xcentre+thickness/2
    cy=sum(p[0] for p in points)/n; cz=sum(p[1] for p in points)/n
    vertices=[(x0,y,z) for y,z in points]+[(x1,y,z) for y,z in points]
    vertices += [(x0,cy,cz),(x1,cy,cz)]
    faces=[]; c0=2*n; c1=2*n+1
    for i in range(n):
        j=(i+1)%n
        faces += [(c0,j,i),(c1,n+i,n+j),(i,j,n+j),(i,n+j,n+i)]
    m=trimesh.Trimesh(vertices=np.array(vertices),faces=np.array(faces),process=True)
    if m.volume<0: m.invert()
    return m


def rounded_prism(w, h, r, depth, z0, sections=48):
    pieces = [box((w-2*r, h, depth), (0, 0, z0+depth/2)),
              box((w, h-2*r, depth), (0, 0, z0+depth/2))]
    for x in (-w/2+r, w/2-r):
        for y in (-h/2+r, h/2-r):
            pieces.append(cyl_z(r, depth, (x, y, z0+depth/2), sections))
    return trimesh.boolean.union(pieces, engine="manifold")


def rounded_ring(ow,oh,orr,iw,ih,irr,depth,z0):
    return trimesh.boolean.difference([
        rounded_prism(ow,oh,orr,depth,z0),
        rounded_prism(iw,ih,irr,depth+2,z0-1)
    ],engine="manifold")


def face_component_count(mesh):
    parent = list(range(len(mesh.faces)))
    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]; a = parent[a]
        return a
    def union(a,b):
        a,b=find(a),find(b)
        if a != b: parent[b]=a
    owner={}
    for fi,f in enumerate(mesh.faces):
        for a,b in ((f[0],f[1]),(f[1],f[2]),(f[2],f[0])):
            e=(min(int(a),int(b)),max(int(a),int(b)))
            if e in owner: union(fi,owner[e])
            else: owner[e]=fi
    return len({find(i) for i in range(len(mesh.faces))})


def keep_largest_face_component(mesh):
    """Discard microscopic boolean slivers without optional graph packages."""
    parent=list(range(len(mesh.faces)))
    def find(a):
        while parent[a]!=a:
            parent[a]=parent[parent[a]]; a=parent[a]
        return a
    def union(a,b):
        a,b=find(a),find(b)
        if a!=b: parent[b]=a
    owner={}
    for fi,f in enumerate(mesh.faces):
        for a,b in ((f[0],f[1]),(f[1],f[2]),(f[2],f[0])):
            e=(min(int(a),int(b)),max(int(a),int(b)))
            if e in owner: union(fi,owner[e])
            else: owner[e]=fi
    groups={}
    for i in range(len(mesh.faces)): groups.setdefault(find(i),[]).append(i)
    if len(groups)>1:
        keep=max(groups.values(),key=len)
        mesh.update_faces(np.array(keep,dtype=int)); mesh.remove_unreferenced_vertices()
    return mesh


def convex_wing(x0,x1,outer_side,y0=-35.0,y1=35.0,nx=28,ny=16):
    """Wing with 0->15 mm clearance over the first 15 mm from screen edges."""
    screen_edge_rear=GLUE_Z0
    plate_t=2.4
    verts=[]
    for zside in (0,1):
        for iy in range(ny+1):
            y=y0+(y1-y0)*iy/ny
            for ix in range(nx+1):
                x=x0+(x1-x0)*ix/nx
                dx=(x-x0) if outer_side=="left" else (x1-x)
                edge_distance=max(0.0,min(dx,y-y0,y1-y))
                t=min(1.0,edge_distance/15.0)
                # Raised cosine: tangent at both 0 and 15 mm endpoints.
                clearance=15.0*(1.0-np.cos(np.pi*t))/2.0
                front_z=screen_edge_rear+clearance
                verts.append((x,y,front_z if zside==0 else front_z+plate_t))
    layer=(nx+1)*(ny+1); faces=[]
    def idx(layer_i,iy,ix): return layer_i*layer+iy*(nx+1)+ix
    for iy in range(ny):
        for ix in range(nx):
            a,b=idx(0,iy,ix),idx(0,iy,ix+1)
            c,d=idx(0,iy+1,ix+1),idx(0,iy+1,ix)
            faces += [(a,c,b),(a,d,c)]
            a,b=idx(1,iy,ix),idx(1,iy,ix+1)
            c,d=idx(1,iy+1,ix+1),idx(1,iy+1,ix)
            faces += [(a,b,c),(a,c,d)]
    # Close all four perimeter edges.
    loops=[]
    loops.append([idx(0,0,i) for i in range(nx+1)])
    loops.append([idx(0,ny,i) for i in range(nx,-1,-1)])
    loops.append([idx(0,i,0) for i in range(ny,-1,-1)])
    loops.append([idx(0,i,nx) for i in range(ny+1)])
    for loop in loops:
        for a,b in zip(loop,loop[1:]):
            ar=a+layer; br=b+layer
            faces += [(a,b,br),(a,br,ar)]
    m=trimesh.Trimesh(vertices=np.array(verts),faces=np.array(faces),process=True)
    if m.volume < 0: m.invert()
    return m


def finish(mesh, path):
    # Manifold output already shares topological vertices. A later tolerance-
    # based merge can incorrectly join very close vertices around angled holes.
    mesh=keep_largest_face_component(mesh)
    mesh.remove_unreferenced_vertices(); mesh.export(path)
    print(f"file={path}")
    print(f"  watertight={mesh.is_watertight} winding={mesh.is_winding_consistent} "
          f"bodies={face_component_count(mesh)} triangles={len(mesh.faces)}")
    print(f"  extents={mesh.extents.tolist()}")


def screen_carrier():
    # A thin hidden glue/contact rim. The curved wings supply the increasing
    # clearance; the outer edge itself has zero free space behind the display.
    shell = rounded_ring(PRINT_W,PRINT_H,CORNER_R,
                         PRINT_W-2*WALL,PRINT_H-2*WALL,
                         max(1.0,CORNER_R-WALL),
                         WALL,GLUE_Z0)

    # Four broad glue pads sit only at the thin rear corners. The centre stays
    # clear until Z=15.3 for the thicker display body.
    pads=[]
    for x in (-122,122):
        for y in (-29,29):
            pads.append(box((25,11,3.0),(x,y,GLUE_Z0+1.5)))

    # Two smoothly convex covers over the thin left/right display areas. The
    # centre is absent, leaving a fully open path from display rear to Pi space.
    left_wing=convex_wing(-135.5,-51.5,"left")
    right_wing=convex_wing(71.5,135.5,"right")

    # The Pi hood starts only after the full 15.3 mm display installation
    # envelope. No hood wall may enter the space needed to insert the screen.
    hood_z0=SCREEN_BODY_REAR
    hood_outer = box((PI_HOOD_W,PI_HOOD_H,SCREEN_COVER_REAR-hood_z0),
                     (10.0,0,(hood_z0+SCREEN_COVER_REAR)/2))
    # Cutter starts ahead of the hood: no plastic remains between screen and Pi.
    hood_inner_z0=hood_z0-1.0
    hood_inner_z1=SCREEN_COVER_REAR-WALL
    hood_inner = box((PI_HOOD_W-2*WALL,PI_HOOD_H-2*WALL,
                      hood_inner_z1-hood_inner_z0),
                     (10.0,0,(hood_inner_z0+hood_inner_z1)/2))
    pi_hood = trimesh.boolean.difference([hood_outer,hood_inner],engine="manifold")

    # Direct service access to the Raspberry Pi USB side, which is on the
    # vehicle-left side in the installed orientation.  The 60 x 18 mm clear
    # window accepts moulded plugs and sits below the M4 pivot/lock centres at
    # Z=42, retaining material around both structural screw locations.
    # Positive model X is vehicle-left in the installed, rear-facing screen
    # orientation.  (The previous V17 incorrectly used screen-view left.)
    usb_left_service = box((16.0,60.0,18.0),(72.5,0.0,27.0))
    # Pi USB-C power and both micro-HDMI sockets face the display lower edge.
    # Two depthwise windows give moulded plugs and the short screen-to-Pi
    # jumpers room to turn.  A 2 mm web remains between the openings.
    usb_c_lower_service = box((16.0,14.0,38.0),(-36.0,-35.0,31.0))
    micro_hdmi_lower_service = box((32.0,14.0,38.0),(-10.0,-35.0,31.0))
    pi_hood = trimesh.boolean.difference([pi_hood,usb_left_service,
                                          usb_c_lower_service,
                                          micro_hdmi_lower_service],
                                         engine="manifold",
                                         check_volume=False)

    # Discreet rear vents: narrow horizontal slots; none open toward the sides.
    vents=[]
    for y in (-22,-11,0,11,22):
        for x in (-108,-90,-72,-12,6,24,42,60,78,96):
            vents.append(box((12,2.2,5.0),(x,y,SCREEN_COVER_REAR-1.5)))

    # Mating cable windows face directly into the electrical box.
    cuts=[box((POWER_WH[0],POWER_WH[1],7.0),
              (POWER_C[0],POWER_C[1],SCREEN_COVER_REAR-1.5)),
          box((SIGNAL_WH[0],SIGNAL_WH[1],7.0),
              (SIGNAL_C[0],SIGNAL_C[1],SCREEN_COVER_REAR-1.5))]

    # No arm lugs in this measurement prototype.  The user will print the
    # clean screen/Pi enclosure and draw the required arm geometry by hand.
    mount_bosses=[]; mount_holes=[]

    # Small hidden vents through the convex wings.
    wing_vents=[]
    for x in (-110,-90,90,110):
        for y in (-15,0,15):
            wing_vents.append(box((12,2.0,24.0),(x,y,12.0)))

    solid=trimesh.boolean.union([shell,left_wing,right_wing,pi_hood,
                                 *pads,*mount_bosses],
                                engine="manifold",check_volume=False)
    return trimesh.boolean.difference([solid,*vents,*wing_vents,*cuts,*mount_holes],
                                      engine="manifold",check_volume=False)


def slope_adapter():
    """Open two-rail adapter for the measured Defender slope.

    150 mm sloping surface and about 100 mm vertical component gives 41.8 deg
    to horizontal. The adapter is deliberately skeletal instead of a massive
    wedge. It mates with the four generic M5 points under the relay box.
    """
    angle=np.arcsin(100.0/150.0)
    z0,z1=12.0,62.0
    min_t=5.0
    rise=np.tan(angle)*(z1-z0)
    x0,x1=-102.0,102.0
    verts=[(x0,0,z0),(x1,0,z0),(x1,0,z1),(x0,0,z1),
           (x0,-min_t,z0),(x1,-min_t,z0),
           (x1,-min_t-rise,z1),(x0,-min_t-rise,z1)]
    faces=[(0,1,2),(0,2,3),(4,7,6),(4,6,5),
           (0,4,5),(0,5,1),(1,5,6),(1,6,2),
           (2,6,7),(2,7,3),(3,7,4),(3,4,0)]
    solid=trimesh.Trimesh(vertices=np.array(verts),faces=np.array(faces),process=True)
    if solid.volume < 0:
        solid.invert()
    # One central window leaves two side rails and front/rear cross ties, while
    # keeping the adapter a clean single manifold rather than tangent pieces.
    centre_window=box((156,100,28),(0,-25,37))
    solid=trimesh.boolean.difference([solid,centre_window],engine="manifold")
    holes=[]
    for x in (-90,90):
        for z in (22,52):
            holes.append(cyl_y(5.5/2,70,(x,-20,z)))
    return trimesh.boolean.difference([solid,*holes],engine="manifold",
                                      check_volume=False)


def electrical_box():
    # Tray is closed at the screen/front side (Z=0) and open at Z=BOX_D.
    outer=box((BOX_W,BOX_H,BOX_D),(0,0,BOX_D/2))
    inner=box((BOX_W-2*BOX_WALL,BOX_H-2*BOX_WALL,
               BOX_D-BOX_FRONT+2),(0,0,BOX_FRONT+(BOX_D-BOX_FRONT+2)/2))
    tray=trimesh.boolean.difference([outer,inner],engine="manifold")

    # Front M4 bosses for the carrier. Inserts are installed from screen side.
    front_boss=[]; front_pilots=[]
    for x in (-MOUNT_X,MOUNT_X):
        for y in (-MOUNT_Y,MOUNT_Y):
            front_boss.append(cyl_z(8.0,10,(x,y,5.0)))
            front_pilots.append(cyl_z(M4_INSERT_PILOT/2,9,(x,y,3.5)))

    # Matching power/signal windows through the tray front.
    front_ports=[box((POWER_WH[0],POWER_WH[1],BOX_FRONT+4),
                     (POWER_C[0],POWER_C[1],BOX_FRONT/2)),
                 box((SIGNAL_WH[0],SIGNAL_WH[1],BOX_FRONT+4),
                     (SIGNAL_C[0],SIGNAL_C[1],BOX_FRONT/2))]

    # Relay board standoffs. M3 insert pockets allow small printed/metal clamps;
    # 65 x 42 pitch is intentionally marked provisional until board is measured.
    relay_boss=[]; relay_pilots=[]
    for dx in (-RELAY_HOLE_PITCH[0]/2,RELAY_HOLE_PITCH[0]/2):
        for dy in (-RELAY_HOLE_PITCH[1]/2,RELAY_HOLE_PITCH[1]/2):
            x,y=RELAY_CX+dx,dy
            relay_boss.append(cyl_z(5.5,9,(x,y,BOX_FRONT+4.5)))
            relay_pilots.append(cyl_z(M3_INSERT_PILOT/2,8,(x,y,BOX_FRONT+5)))

    # External USB unit: recessed on right side, under the glass silhouette.
    ext_usb_c=(BOX_W/2,17.0,35.0)
    ext_usb_cut=cyl_x(USB_PANEL_HOLE/2,BOX_WALL+6,ext_usb_c)
    ext_shroud_outer=cyl_x(19.0,10,(BOX_W/2-2,17,35))
    ext_shroud_inner=cyl_x(USB_FACE_D/2+0.3,12,(BOX_W/2-2,17,35))
    ext_shroud=trimesh.boolean.difference([ext_shroud_outer,ext_shroud_inner],
                                          engine="manifold")

    # Internal USB unit on a divider. Its USB face is inside the service cavity;
    # the 57 mm body points right and clears the exterior unit vertically.
    divider=box((3.2,36,46),(43,-18,35))
    divider_foot=box((3.2,36,12),(43,-18,8.0))
    int_usb_cut=cyl_x(USB_PANEL_HOLE/2,8,(43,-18,35))
    divider=trimesh.boolean.difference([divider,int_usb_cut],engine="manifold")

    # Universal fuse/accessory insert points; final holder can be screwed here.
    accessory_boss=[]; accessory_pilots=[]
    for y in (-20,20):
        accessory_boss.append(cyl_z(5.5,9,(0,y,BOX_FRONT+4.5)))
        accessory_pilots.append(cyl_z(M3_INSERT_PILOT/2,8,(0,y,BOX_FRONT+5)))

    # Rear lid bosses with M3 inserts installed from the open rear.
    lid_boss=[]; lid_bridges=[]; lid_pilots=[]
    for x in (-110,110):
        for y in (-27,27):
            lid_boss.append(cyl_z(6.5,12,(x,y,BOX_D-6)))
            bridge_x = -119.0 if x < 0 else 119.0
            lid_bridges.append(box((14,7,12),(bridge_x,y,BOX_D-6)))
            lid_pilots.append(cyl_z(M3_INSERT_PILOT/2,9,(x,y,BOX_D-2.5)))

    # Generic M5 insert sockets in the bottom wall for a later Defender adapter;
    # these deliberately encode no vehicle hole pattern.
    adapter_boss=[]; adapter_pilots=[]
    for x in (-90,90):
        for z in (22,52):
            adapter_boss.append(cyl_y(7.5,9,(x,-BOX_H/2+4,z)))
            adapter_pilots.append(cyl_y(6.2/2,8,(x,-BOX_H/2+2.5,z)))

    solid=trimesh.boolean.union([tray,*front_boss,*relay_boss,ext_shroud,
                                 divider,divider_foot,*accessory_boss,*lid_boss,
                                 *lid_bridges,*adapter_boss],
                                engine="manifold",check_volume=False)
    cuts=[*front_pilots,*front_ports,*relay_pilots,ext_usb_cut,
          *accessory_pilots,*lid_pilots,*adapter_pilots]
    return trimesh.boolean.difference([solid,*cuts],engine="manifold",
                                      check_volume=False)


def compact_tilted_electrical_box():
    """Smaller box rotated down behind the screen by the measured dash angle."""
    bw,bh,bd=190.0,68.0,64.0
    wall,front=2.8,3.2

    # Local tray, open at its rear for service.
    outer=box((bw,bh,bd),(0,0,bd/2))
    inner=box((bw-2*wall,bh-2*wall,bd-front+2),
              (0,0,front+(bd-front+2)/2))
    tray=trimesh.boolean.difference([outer,inner],engine="manifold")

    # Cable entries are high on the local front wall, nearest the screen.
    local_power=(-31.0,20.0)
    local_signal=(31.0,20.0)
    front_ports=[box((POWER_WH[0],POWER_WH[1],front+4),
                     (local_power[0],local_power[1],front/2)),
                 box((SIGNAL_WH[0],SIGNAL_WH[1],front+4),
                     (local_signal[0],local_signal[1],front/2))]

    # Relay board at left; same provisional 65 x 42 pattern but less dead space.
    relay_cx=-49.0; relay_boss=[]; relay_pilot=[]
    for dx in (-RELAY_HOLE_PITCH[0]/2,RELAY_HOLE_PITCH[0]/2):
        for dy in (-RELAY_HOLE_PITCH[1]/2,RELAY_HOLE_PITCH[1]/2):
            x,y=relay_cx+dx,dy
            relay_boss.append(cyl_z(5.5,9,(x,y,front+4.5)))
            relay_pilot.append(cyl_z(M3_INSERT_PILOT/2,8,(x,y,front+5)))

    # Two USB units stacked vertically in local Y. The exterior face is recessed
    # at the right side; the second unit is on an internal divider.
    ext_c=(bw/2,15.0,33.0)
    ext_cut=cyl_x(USB_PANEL_HOLE/2,wall+7,ext_c)
    shroud_o=cyl_x(18.8,9,(bw/2-2,15,33))
    shroud_i=cyl_x(USB_FACE_D/2+0.2,11,(bw/2-2,15,33))
    shroud=trimesh.boolean.difference([shroud_o,shroud_i],engine="manifold")
    divider=box((3.2,34,43),(35,-16,33))
    divider_foot=box((3.2,34,12),(35,-16,8))
    int_cut=cyl_x(USB_PANEL_HOLE/2,8,(35,-16,33))
    divider=trimesh.boolean.difference([divider,int_cut],engine="manifold")

    # Universal fuse-holder insert points in the remaining centre strip.
    accessory=[]; accessory_holes=[]
    for y in (-19,19):
        accessory.append(cyl_z(5.3,8,(2,y,front+4)))
        accessory_holes.append(cyl_z(M3_INSERT_PILOT/2,7,(2,y,front+4.5)))

    # Rear lid bosses connected to side walls.
    lid_boss=[]; lid_bridges=[]; lid_holes=[]
    for x in (-82,82):
        for y in (-25,25):
            lid_boss.append(cyl_z(6.3,11,(x,y,bd-5.5)))
            lid_bridges.append(box((11,7,11),((-89 if x<0 else 89),y,bd-5.5)))
            lid_holes.append(cyl_z(M3_INSERT_PILOT/2,8,(x,y,bd-2.5)))

    # Generic M5 sockets for a later small Defender restraint/strap.
    adapter=[]; adapter_holes=[]
    for x in (-72,72):
        for z in (20,48):
            adapter.append(cyl_y(7.2,8,(x,-bh/2+3.5,z)))
            adapter_holes.append(cyl_y(6.2/2,7,(x,-bh/2+2.0,z)))

    local=trimesh.boolean.union([tray,*relay_boss,shroud,divider,divider_foot,
                                 *accessory,*lid_boss,*lid_bridges,*adapter],
                                engine="manifold",check_volume=False)
    local=trimesh.boolean.difference([local,*front_ports,*relay_pilot,ext_cut,
                                      *accessory_holes,*lid_holes,*adapter_holes],
                                     engine="manifold",check_volume=False)

    # Rotate rearward depth downwards by 41.8 degrees. Translation places the
    # front of the box below the Pi hood, while total depth remains about 150 mm.
    angle=np.arcsin(100.0/150.0)
    rot=trimesh.transformations.rotation_matrix(angle,[1,0,0])
    local.apply_transform(rot)
    # Z=18 keeps the complete assembled depth below 140 mm, leaving roughly
    # 10 mm margin to the measured 150 mm plastic boundary.
    translation=np.array((0.0,-64.0,18.0))
    local.apply_translation(translation)

    def xf(x,y,z):
        p=np.array([x,y,z,1.0]); return (rot@p)[:3]+translation

    # Four load-bearing arms. Boss faces remain parallel to the screen rear so
    # the existing V7 M4 clearance holes still mate correctly.
    bosses=[]; pilots=[]; arms=[]
    for x in (-MOUNT_X,MOUNT_X):
        for sy,local_y in ((MOUNT_Y,25.0),(-MOUNT_Y,-25.0)):
            bosses.append(cyl_z(8.0,10,(x,sy,5.0)))
            pilots.append(cyl_z(M4_INSERT_PILOT/2,9,(x,sy,3.5)))
            arms.append(beam_between((x,sy,8.0),xf(x,local_y,2.0),14.0,8.0))

    # Fully enclosed angled cable ducts; inner clear sizes remain large enough
    # for moulded USB and relay-harness connectors.
    power_end=xf(local_power[0],local_power[1],2.0)
    signal_end=xf(local_signal[0],local_signal[1],2.0)
    ducts=[tube_between((POWER_C[0],POWER_C[1],5.0),power_end,
                        POWER_WH[0]+5,POWER_WH[1]+5),
           tube_between((SIGNAL_C[0],SIGNAL_C[1],5.0),signal_end,
                        SIGNAL_WH[0]+5,SIGNAL_WH[1]+5)]

    solid=trimesh.boolean.union([local,*bosses,*arms,*ducts],engine="manifold",
                                check_volume=False)
    return trimesh.boolean.difference([solid,*pilots],engine="manifold",
                                      check_volume=False)


def compact_relay_lid():
    bw,bh=190.0,68.0
    plate=box((bw,bh,LID_T),(0,0,LID_T/2))
    holes=[cyl_z(M3_CLEAR/2,LID_T+3,(x,y,LID_T/2))
           for x in (-82,82) for y in (-25,25)]
    vents=[box((12,2.2,LID_T+2),(x,y,LID_T/2))
           for y in (-17,-8.5,0,8.5,17)
           for x in (-65,-48,-31,-14,3,20,37,54,71)]
    return trimesh.boolean.difference([plate,*holes,*vents],engine="manifold",
                                      check_volume=False)


def horizontal_center_tunnel_box():
    """0-degree relay box with a bottom-open vehicle-centre cable tunnel."""
    # Asymmetric about vehicle centre X=0: relay section left, services right.
    xmin,xmax=-104.0,110.0
    bw,bh,bd=xmax-xmin,60.0,65.0
    cx=(xmin+xmax)/2; wall=2.8; bottom=3.2

    # Open-top tray for service from above.
    outer=box((bw,bh,bd),(cx,bh/2,bd/2))
    inner=box((bw-2*wall,bh-bottom+2,bd-2*wall),
              (cx,bottom+(bh-bottom+2)/2,bd/2))
    tray=trimesh.boolean.difference([outer,inner],engine="manifold")

    # Existing vehicle harness passes through this arch without disconnection.
    tunnel=box((40.0,27.0,bd+4),(0,12.5,bd/2))
    tray=trimesh.boolean.difference([tray,tunnel],engine="manifold")

    # Relay board lies flat and entirely left of the centre tunnel.
    relay_c=(-62.0,0.0,35.0); relay_b=[]; relay_h=[]
    for dx in (-RELAY_HOLE_PITCH[0]/2,RELAY_HOLE_PITCH[0]/2):
        for dz in (-RELAY_HOLE_PITCH[1]/2,RELAY_HOLE_PITCH[1]/2):
            x,z=relay_c[0]+dx,relay_c[2]+dz
            relay_b.append(cyl_y(5.5,9,(x,bottom+4.5,z)))
            relay_h.append(cyl_y(M3_INSERT_PILOT/2,8,(x,bottom+5,z)))

    # USB services remain to the right. Their bodies overlap in X but are
    # separated diagonally in the YZ section.
    ext_c=(xmax,40.0,43.0)
    ext_cut=cyl_x(USB_PANEL_HOLE/2,wall+7,ext_c)
    sh_o=cyl_x(18.8,9,(xmax-2,40,43)); sh_i=cyl_x(USB_FACE_D/2+0.2,11,(xmax-2,40,43))
    shroud=trimesh.boolean.difference([sh_o,sh_i],engine="manifold")
    divider=box((3.2,34,36),(28,18,20))
    divider_foot=box((3.2,12,36),(28,6,20))
    int_cut=cyl_x(USB_PANEL_HOLE/2,8,(28,18,20))
    divider=trimesh.boolean.difference([divider,int_cut],engine="manifold")

    # Fuse/accessory insert points live right of the centreline and tunnel.
    fuse_b=[]; fuse_h=[]
    for x in (58,82):
        fuse_b.append(cyl_y(5.3,8,(x,bottom+4,17)))
        fuse_h.append(cyl_y(M3_INSERT_PILOT/2,7,(x,bottom+4.5,17)))

    # Lid bosses near corners, joined to side walls.
    lid_b=[]; lid_links=[]; lid_h=[]
    for x in (-78,10,98):
        for z in (9,56):
            lid_b.append(cyl_y(7.2,12,(x,bh-6,z)))
            # Each boss overlaps the nearby front/rear Z wall.
            wall_z=3.5 if z<bd/2 else bd-3.5
            lid_links.append(box((14,12,7),(x,bh-6,wall_z)))
            lid_h.append(cyl_y(M4_INSERT_PILOT/2,9,(x,bh-3,z)))

    # Bottom slots move the complete screen/box assembly 25 mm fore-aft.
    slide_cuts=[slot_z_through_y(x,2.0,z,25.0,6.5,9.0)
                for x in (-70,75) for z in (19,48)]

    solid=trimesh.boolean.union([tray,*relay_b,shroud,divider,divider_foot,
                                 *fuse_b,*lid_b,*lid_links],
                                engine="manifold",check_volume=False)
    cuts=[*relay_h,ext_cut,*fuse_h,*lid_h,*slide_cuts]
    return trimesh.boolean.difference([solid,*cuts],engine="manifold",
                                      check_volume=False)


def horizontal_box_lid():
    xmin,xmax=-104.0,110.0; bw=xmax-xmin; bd=65.0
    plate=box((bw,LID_T,bd),((xmin+xmax)/2,LID_T/2,bd/2))
    holes=[cyl_y(M4_CLEAR/2,LID_T+3,(x,LID_T/2,z))
           for x in (-78,10,98) for z in (9,56)]
    vents=[box((12,LID_T+2,2.2),(x,LID_T/2,z))
           for z in (12,21,30,39,48,57)
           for x in (-62,-45,-28,45,62,79,96)]

    # Clean measurement lid: no screen arms, tilt slots or cable ducts.  The
    # six relay-box fixing holes and ventilation remain unchanged.
    return trimesh.boolean.difference([plate,*holes,*vents],
                                      engine="manifold",check_volume=False)


def relay_lid():
    plate=box((BOX_W,BOX_H,LID_T),(0,0,LID_T/2))
    holes=[]
    for x in (-110,110):
        for y in (-27,27):
            holes.append(cyl_z(M3_CLEAR/2,LID_T+3,(x,y,LID_T/2)))
    # Recessed ventilation slots on lid, avoiding direct edge openings.
    vents=[]
    for y in (-18,-9,0,9,18):
        for x in (-82,-64,-46,-28,-10,8,26,44,62,80):
            vents.append(box((12,2.2,LID_T+2),(x,y,LID_T/2)))
    return trimesh.boolean.difference([plate,*holes,*vents],engine="manifold",
                                      check_volume=False)


def main():
    sc=screen_carrier(); eb=horizontal_center_tunnel_box(); lid=horizontal_box_lid()
    finish(sc,SCREEN_OUT); finish(eb,BOX_OUT); finish(lid,LID_OUT)
    print(f"glass={SCREEN_W} x {SCREEN_H}")
    print(f"largest printed front silhouette={PRINT_W} x {PRINT_H}")
    print(f"hidden margin per side={(SCREEN_W-PRINT_W)/2:.2f} x "
          f"{(SCREEN_H-PRINT_H)/2:.2f}")
    print("interface prototype=no screen arms/lugs; relay-box lid=6 x M4")
    print("dash reference lip=120 mm deep x 50 mm high; slope begins 50 mm up")
    print("USB holes=30.4 mm; relay pitch 65 x 42 mm PROVISIONAL")
    print("screen profile=0 to 15 mm clearance over 15 mm rounded edge transition")
    print("Pi USB service=vehicle-left side window 60 x 18 mm")
    print("Pi lower connector service=USB-C 16 mm + micro-HDMI 32 mm, 2 mm web")
    print("relay box=214 x 60 x 65 mm, horizontal 0 degrees")
    print("vehicle centre cable tunnel=40 x 25 mm, open through full depth")
    print("relay board=entirely left of vehicle centreline")


if __name__=="__main__": main()
