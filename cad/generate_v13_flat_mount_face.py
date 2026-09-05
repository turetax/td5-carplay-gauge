#!/usr/bin/env python3
"""V13: remove rear screw bosses so the mounting flange seats flat."""
from pathlib import Path
import trimesh

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'3d print/Defender_EP0189_V12_printbar_forstarkt.stl'
OUT=ROOT/'3d print/Defender_EP0189_V13_plan_anliggningsyta.stl'
HOLE_X,HOLE_Y=111.0,52.0

def main():
    body=trimesh.load_mesh(SRC,process=True)
    cutters=[]
    # Remove the added Ø14 bosses from immediately behind the 3 mm flange.
    # A slightly larger cutter avoids leaving a printable ridge at the seam.
    for x in (-HOLE_X,HOLE_X):
        for y in (-HOLE_Y,HOLE_Y):
            c=trimesh.creation.cylinder(radius=7.1,height=4.4,sections=64)
            c.apply_translation((x,y,5.2));cutters.append(c)
    result=trimesh.boolean.difference([body,*cutters],engine='manifold',check_volume=False)
    result.remove_unreferenced_vertices();result.merge_vertices();result.export(OUT)
    print(f'file={OUT}')
    print('mounting_face_behind_holes_mm=3.0 flat flange')
    print(f'watertight_before_export={result.is_watertight}')
    print(f'extents_mm={result.extents.tolist()}')

if __name__=='__main__':main()
