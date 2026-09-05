#!/usr/bin/env python3
"""Slim the validated V8 flange while preserving its watertight body."""
from pathlib import Path
import trimesh

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "3d print/Defender_EP0189_V8_snyggad_kontrollmatt.stl"
OUT = ROOT / "3d print/Defender_EP0189_V9_tunn_flush_front.stl"

FRONT_W, FRONT_H, FRONT_T = 286.0, 120.0, 3.0
POCKET_W, POCKET_H = 284.89, 85.10
TRIM_END = 18.2
HOLE_X, HOLE_Y, HEAD_D = 111.0, 52.0, 8.6


def box(size, center):
    m = trimesh.creation.box(size)
    m.apply_translation(center)
    return m


def main():
    body = trimesh.load_mesh(SRC, process=True)
    depth = TRIM_END - FRONT_T
    # Remove only the unnecessary thick wings behind the 3 mm front flange.
    trims = [
        box((FRONT_W+2, (FRONT_H-POCKET_H)/2+1, depth),
            (0, (FRONT_H+POCKET_H)/4, FRONT_T+depth/2)),
        box((FRONT_W+2, (FRONT_H-POCKET_H)/2+1, depth),
            (0, -(FRONT_H+POCKET_H)/4, FRONT_T+depth/2)),
        box(((FRONT_W-POCKET_W)/2+1, POCKET_H, depth),
            ((FRONT_W+POCKET_W)/4, 0, FRONT_T+depth/2)),
        box(((FRONT_W-POCKET_W)/2+1, POCKET_H, depth),
            (-(FRONT_W+POCKET_W)/4, 0, FRONT_T+depth/2)),
    ]
    result = trimesh.boolean.difference([body, *trims], engine="manifold",
                                        check_volume=False)
    # 90-degree countersinks; existing V8 Ø4.5 bores form the narrow end.
    sinks=[]
    for x in (-HOLE_X, HOLE_X):
        for y in (-HOLE_Y, HOLE_Y):
            # Revolved 90-degree countersink profile, overlapped with the
            # existing bore to avoid a zero-area cone tip in the STL.
            profile=[[0,-0.2],[HEAD_D/2,-0.2],[2.25,1.85],[0,1.85]]
            c=trimesh.creation.revolve(profile, sections=64)
            c.apply_translation((x,y,0)); sinks.append(c)
    result=trimesh.boolean.difference([result,*sinks],engine="manifold",
                                      check_volume=False)
    result.remove_unreferenced_vertices(); result.merge_vertices(); result.export(OUT)
    print(f"file={OUT}")
    print(f"front_flange_mm={FRONT_T}")
    print(f"extents_mm={result.extents.tolist()}")
    print(f"watertight_before_export={result.is_watertight}")

if __name__ == '__main__': main()
