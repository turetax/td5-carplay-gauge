#!/usr/bin/env python3
"""Clean-sheet frameless EP-0189 housing with rear downward mounting feet."""
from pathlib import Path
import numpy as np
import trimesh

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'3d print/Defender_EP0189_FRAMELESS_V1_bakre_faste.stl'

# Retained measured/published screen data.
SCREEN_W,SCREEN_H,SCREEN_D=276.29,76.50,15.0
FIT_XY,FIT_Z,SCREEN_R=0.60,0.30,6.5
WALL=2.8

# New clean-sheet architecture.
GUIDE_Z0,GUIDE_Z1=2.0,15.3       # housing starts behind the visible glass face
TAPER_Z1=52.0
BOX_Z1=84.0
REAR_CAP=3.0
BOX_OUT=(210.0,74.0)
BOX_IN=(204.4,68.4)


def rounded_prism(w,h,r,depth,z0,sections=64):
    parts=[trimesh.creation.box((w-2*r,h,depth)),trimesh.creation.box((w,h-2*r,depth))]
    for x in (-w/2+r,w/2-r):
        for y in (-h/2+r,h/2-r):
            c=trimesh.creation.cylinder(radius=r,height=depth,sections=sections)
            c.apply_translation((x,y,0));parts.append(c)
    m=trimesh.boolean.union(parts,engine='manifold');m.apply_translation((0,0,z0+depth/2));return m


def rounded_ring(ow,oh,r,iw,ih,ir,depth,z0):
    return trimesh.boolean.difference([
        rounded_prism(ow,oh,r,depth,z0),rounded_prism(iw,ih,ir,depth+2,z0-1)
    ],engine='manifold')


def loft_ring(outer0,inner0,outer1,inner1,z0,z1):
    def loop(wh,z):
        w,h=wh;return [(-w/2,-h/2,z),(w/2,-h/2,z),(w/2,h/2,z),(-w/2,h/2,z)]
    v=np.array(loop(outer0,z0)+loop(inner0,z0)+loop(outer1,z1)+loop(inner1,z1),float);f=[]
    def q(a,b,c,d):f.extend([(a,b,c),(a,c,d)])
    for i in range(4):
        j=(i+1)%4;q(i,j,8+j,8+i);q(4+i,12+i,12+j,4+j);q(i,4+i,4+j,j);q(8+i,8+j,12+j,12+i)
    return trimesh.Trimesh(vertices=v,faces=np.array(f),process=True)


def slot_z(length,width,depth_y,x,y,z):
    r=width/2;parts=[trimesh.creation.box((width,depth_y,length-2*r))]
    rot=trimesh.transformations.rotation_matrix(np.pi/2,[1,0,0])
    for dz in (-(length/2-r),length/2-r):
        c=trimesh.creation.cylinder(radius=r,height=depth_y,sections=48)
        c.apply_transform(rot);c.apply_translation((0,0,dz));parts.append(c)
    m=trimesh.boolean.union(parts,engine='manifold');m.apply_translation((x,y,z));return m


def cable_slot(x):
    # 50 x 16 capsule through the upper wall, behind the screen connectors.
    r=8;parts=[trimesh.creation.box((34,28,16))]
    rot=trimesh.transformations.rotation_matrix(np.pi/2,[1,0,0])
    for dx in (-17,17):
        c=trimesh.creation.cylinder(radius=r,height=28,sections=48)
        c.apply_transform(rot);c.apply_translation((dx,0,0));parts.append(c)
    m=trimesh.boolean.union(parts,engine='manifold');m.apply_translation((x,39,24));return m


def main():
    cw,ch=SCREEN_W+FIT_XY,SCREEN_H+FIT_XY
    # No face plate: only a hidden guide beginning 2 mm behind the glass.
    guide=rounded_ring(cw+2*WALL,ch+2*WALL,SCREEN_R+WALL,
                       cw,ch,SCREEN_R+FIT_XY/2,GUIDE_Z1-GUIDE_Z0,GUIDE_Z0)
    # Small rear retaining shoulder, followed by a printable tapered electronics shell.
    taper=loft_ring((cw+2*WALL-1,ch+2*WALL-1),(SCREEN_W-2.4,SCREEN_H-2.4),
                    BOX_OUT,BOX_IN,GUIDE_Z1-0.2,TAPER_Z1+0.2)
    outer=trimesh.creation.box((BOX_OUT[0],BOX_OUT[1],BOX_Z1-TAPER_Z1+0.4))
    outer.apply_translation((0,0,(TAPER_Z1+BOX_Z1)/2))
    inner=trimesh.creation.box((BOX_IN[0],BOX_IN[1],BOX_Z1-TAPER_Z1-REAR_CAP+1))
    inner.apply_translation((0,0,TAPER_Z1+(BOX_Z1-TAPER_Z1-REAR_CAP)/2))
    box=trimesh.boolean.difference([outer,inner],engine='manifold')

    # Two rear feet point down to the console's flat surface; no visible front screws.
    feet=[]
    for x in (-72,72):
        foot=trimesh.creation.box((52,3.2,31));foot.apply_translation((x,-38.4,69.5));feet.append(foot)
    result=trimesh.boolean.union([guide,taper,box,*feet],engine='manifold',check_volume=False)
    slots=[slot_z(18,6,8,x,-38.4,72) for x in (-72,72)]
    cables=[cable_slot(x) for x in (-48,48)]
    result=trimesh.boolean.difference([result,*slots,*cables],engine='manifold',check_volume=False)
    result.remove_unreferenced_vertices();result.merge_vertices();result.export(OUT)
    angle=np.degrees(np.arctan((TAPER_Z1-GUIDE_Z1)/(((cw+2*WALL-1)-BOX_OUT[0])/2)))
    print(f'file={OUT}')
    print(f'visible_front_frame_mm=0')
    print(f'screen_pocket_mm={cw:.2f} x {ch:.2f} x {SCREEN_D+FIT_Z:.2f}')
    print(f'rear_box_outside_mm={BOX_OUT[0]} x {BOX_OUT[1]} x {BOX_Z1-TAPER_Z1}')
    print('rear_downward_mount=2 slots, 18 x 6')
    print(f'taper_angle_deg={angle:.1f}')
    print(f'watertight_before_export={result.is_watertight}')
    print(f'extents_mm={result.extents.tolist()}')

if __name__=='__main__':main()
