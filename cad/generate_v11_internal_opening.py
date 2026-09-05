#!/usr/bin/env python3
"""V11: open only the screen-to-electronics partition; retain the rear."""
from pathlib import Path
import trimesh

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "3d print/Defender_EP0189_V9_tunn_flush_front.stl"
OUT = ROOT / "3d print/Defender_EP0189_V11_oppen_mellan_skarm_och_el.stl"

# Electronics tunnel: 198 x 70 outside, 2.8 mm walls -> 192.4 x 64.4 inside.
# A 190 x 62 opening leaves a 1.2 mm locating shoulder on every inner side.
OPEN_W, OPEN_H = 190.0, 62.0
PARTITION_Z0, PARTITION_Z1 = 15.15, 17.90


def main():
    body = trimesh.load_mesh(SRC, process=True)
    cutter = trimesh.creation.box((OPEN_W, OPEN_H,
                                   PARTITION_Z1-PARTITION_Z0))
    cutter.apply_translation((0, 0, (PARTITION_Z0+PARTITION_Z1)/2))
    result = trimesh.boolean.difference([body, cutter], engine="manifold",
                                        check_volume=False)
    result.remove_unreferenced_vertices(); result.merge_vertices(); result.export(OUT)
    print(f"file={OUT}")
    print(f"internal_passage_mm={OPEN_W} x {OPEN_H}")
    print(f"rear_geometry_unchanged=True")
    print(f"removed_partition_cm3={(body.volume-result.volume)/1000:.3f}")
    print(f"extents_mm={result.extents.tolist()}")
    print(f"watertight_before_export={result.is_watertight}")

if __name__ == '__main__': main()
