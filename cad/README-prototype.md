# Defender EP-0189 prototype

This is a provisional fit prototype, not a final road-ready mount.

Assumptions:

- GeeekPi EP-0189 body: 276.29 x 76.50 mm (official, ±0.1 mm).
- Official viewing area: 252.69 x 57.90 mm (±0.1 mm).
- Depth remains provisional at 15 mm.
- Outer corner radius is not published; V2 uses an image-scaled estimate of
  R6.5 mm. Confirm this on the physical unit before a final print.
- Screen clearance: 0.6 mm total.
- Central rear tunnel: 198 x 70 x 62 mm, based on the published usable
  MUD-0039 face size. This is not a verified copy of its fixing geometry.
- Screen is loaded from the rear. The front lip overlaps the assumed screen
  envelope by 1 mm on every edge.
- Rear tunnel is deliberately open for cable routing and test fitting.
- The rear fixing rail has two 5.2 mm high horizontal M4 trial slots. Together
  they cover symmetric screw centre spacings from 130 to 210 mm. This is an
  intentionally adjustable test pattern, not a claimed factory dimension.

Print `ep0189_fit_coupon.stl` first. It checks the assumed screen width,
height and depth with much less material. Do not force the screen into it.

Print `defender_mount_slot_template.stl` to test the dashboard fixing centres
without printing the full housing. The template is 220 x 22 x 3 mm. Hold it
against the rear fixing points, centre it, and note the distance between the
two screw centres and their vertical offset relative to the radio opening.

The full concept housing is 284.6 x 84.6 x 81.2 mm. It may need to be split
in the slicer for printers with a bed smaller than 285 mm. Print the front
face on the bed. Use a draft profile for the first vehicle test.

The model does not yet include verified Defender screw holes, Pi standoffs,
connector cut-outs, ventilation, relay/fuse mounts or a rear service cover.
Those should be added after checking the physical screen and dashboard fit.

`defender_ep0189_one_piece_reference_fit.stl` is the preferred combined test.
It replaces the guessed slotted rail with the actual `Binnacle_Vent_Rail_v1.1`
mesh from Thingiverse design 5856588, centred and overlapped with the housing
by 0.8 mm so a slicer treats it as one part. The reference was designed and
test-fitted by mbrooker for a pre-Td5 Defender and is licensed CC BY 4.0:
https://www.thingiverse.com/thing:5856588

This reuse improves the dashboard-facing geometry, but does not prove fit in
every 1998 vehicle. The GeeekPi portion is still based on approximate published
dimensions and requires a physical fit check.

`defender_ep0189_v4_flush_one_piece.stl` places the screen's own front surface
in the same plane as the housing front. No printed bezel overlaps the screen.
The screen loads from the front and stops against a 1.2 mm rear perimeter lip.
This lip position assumes a 15 mm screen depth and must be checked physically.

To regenerate after editing the constants:

```sh
python3 cad/generate_defender_screen_prototype.py
```
