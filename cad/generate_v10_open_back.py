#!/usr/bin/env python3
"""V10: open the rear service area for Raspberry Pi and electronics."""
from pathlib import Path
import trimesh

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "3d print/Defender_EP0189_V9_tunn_flush_front.stl"
OUT = ROOT / "3d print/Defender_EP0189_V10_oppen_baksida_for_Pi.stl"

# The tunnel inside is about 192.4 x 64.4 mm. Keep material around it and
# remove the centre of the reference rail from Z=77.5 through the rear.
OPEN_W, OPEN_H = 188.0, 60.0
OPEN_Z0, OPEN_Z1 = 77.5, 92.0


def main():
    body = trimesh.load_mesh(SRC, process=True)
    cutter = trimesh.creation.box((OPEN_W, OPEN_H, OPEN_Z1-OPEN_Z0))
    cutter.apply_translation((0, 0, (OPEN_Z0+OPEN_Z1)/2))
    result = trimesh.boolean.difference([body, cutter], engine="manifold",
                                        check_volume=False)
    result.remove_unreferenced_vertices(); result.merge_vertices(); result.export(OUT)
    print(f"file={OUT}")
    print(f"rear_service_opening_mm={OPEN_W} x {OPEN_H}")
    print(f"extents_mm={result.extents.tolist()}")
    print(f"watertight_before_export={result.is_watertight}")

if __name__ == '__main__': main()
