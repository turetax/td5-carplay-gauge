#!/usr/bin/env python3
"""V12: self-supporting internal transition plus local screw bosses."""
from pathlib import Path
import numpy as np
import trimesh

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'3d print/Defender_EP0189_V9_tunn_flush_front.stl'
OUT=ROOT/'3d print/Defender_EP0189_V12_printbar_forstarkt.stl'

Z0,Z1=15.10,61.00
FO,FI=(284.89,85.10),(273.89,74.10) # front outer/inner rings
BO,BI=(198.00,70.00),(190.00,62.00) # rear outer/inner rings
HOLE_X,HOLE_Y,HOLE_D=111.0,52.0,4.5


def loft_ring(outer0,inner0,outer1,inner1,z0,z1):
    """Closed rectangular tapered ring with printable sloping walls."""
    def loop(wh,z):
        w,h=wh; return [(-w/2,-h/2,z),(w/2,-h/2,z),(w/2,h/2,z),(-w/2,h/2,z)]
    v=np.array(loop(outer0,z0)+loop(inner0,z0)+loop(outer1,z1)+loop(inner1,z1),float)
    f=[]
    def quad(a,b,c,d): f.extend([(a,b,c),(a,c,d)])
    for i in range(4):
        j=(i+1)%4
        quad(i,j,8+j,8+i)           # outer slope
        quad(4+i,12+i,12+j,4+j)    # inner slope
        quad(i,4+i,4+j,j)           # front annulus
        quad(8+i,8+j,12+j,12+i)     # rear annulus
    return trimesh.Trimesh(vertices=v,faces=np.array(f),process=True)


def capsule_x(w,h,depth_y,x,y,z):
    r=h/2; parts=[trimesh.creation.box((w-2*r,depth_y,h))]
    rot=trimesh.transformations.rotation_matrix(np.pi/2,[1,0,0])
    for dx in (-(w/2-r),w/2-r):
        c=trimesh.creation.cylinder(radius=r,height=depth_y,sections=64)
        c.apply_transform(rot);c.apply_translation((dx,0,0));parts.append(c)
    m=trimesh.boolean.union(parts,engine='manifold');m.apply_translation((x,y,z));return m


def main():
    body=trimesh.load_mesh(SRC,process=True)
    # Remove the flat partition and the first part of the straight tunnel only.
    cut=trimesh.creation.box((300,130,(Z1-Z0)-0.2))
    cut.apply_translation((0,0,(Z0+Z1)/2))
    body=trimesh.boolean.difference([body,cut],engine='manifold',check_volume=False)
    funnel=loft_ring(FO,FI,BO,BI,Z0-0.2,Z1+0.2)

    # 14 mm bosses reinforce the otherwise 3 mm flange around the four screws.
    bosses=[]; bores=[]
    for x in (-HOLE_X,HOLE_X):
        for y in (-HOLE_Y,HOLE_Y):
            b=trimesh.creation.cylinder(radius=7,height=4.2,sections=64)
            b.apply_translation((x,y,4.9));bosses.append(b)
            h=trimesh.creation.cylinder(radius=HOLE_D/2,height=9,sections=64)
            h.apply_translation((x,y,4.5));bores.append(h)
    result=trimesh.boolean.union([body,funnel,*bosses],engine='manifold',check_volume=False)
    # Restore holes and the two existing cable exits through the new funnel.
    # Begin at Z=16, immediately behind the assumed 15 mm screen body;
    # avoiding the funnel's front seam also keeps the exported mesh manifold.
    cables=[capsule_x(50,16,32,x,42,24) for x in (-48,48)]
    cutter_union=trimesh.boolean.union([*bores,*cables],engine='manifold',check_volume=False)
    result=trimesh.boolean.difference([result,cutter_union],engine='manifold',check_volume=False)
    result.remove_unreferenced_vertices();result.merge_vertices();result.export(OUT)
    side_angle=np.degrees(np.arctan((Z1-Z0)/((FO[0]-BO[0])/2)))
    print(f'file={OUT}')
    print(f'internal_front_opening_mm={FI[0]} x {FI[1]}')
    print(f'internal_rear_opening_mm={BI[0]} x {BI[1]}')
    print(f'shallowest_transition_angle_deg={side_angle:.1f}')
    print('screw_bosses_mm=14 diameter x 7 total depth')
    print(f'watertight_before_export={result.is_watertight}')
    print(f'extents_mm={result.extents.tolist()}')

if __name__=='__main__':main()
