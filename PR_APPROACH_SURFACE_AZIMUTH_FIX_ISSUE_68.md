# PR: Approach Surface Azimuth Logic (Issue #68)

## Summary
Fixes the azimuth orientation for the Approach Surface so it projects outward from the selected runway threshold in the direction indicated by the UI toggle:
- "Direction: Start to End": project in the runway's start→end direction when the selected threshold matches the start; otherwise flip 180°.
- "Direction: End to Start": flip the above by 180°.

This aligns with the expected workflow: runway centerline is digitized low→high, the user selects a threshold, and the surface extends outwards from that threshold according to the chosen direction.

## Problem
The previous logic treated the azimuth relative to the runway polyline alone, ignoring which runway end was selected as threshold (and the UI direction). This could draw the surface in the opposite direction than intended.

## Approach
1. Compute the base azimuth from the runway polyline first point to last point (start→end).
2. Determine which runway end (start or end) is closer to the selected threshold feature.
3. Set the outward azimuth as:
   - If threshold ≈ start end → `base_azimuth`.
   - If threshold ≈ end end → `base_azimuth + 180`.
4. Apply the UI direction toggle (`direction`): 0 = Start→End, -1 = End→Start → add 180° when -1.
5. Map UI Z0/ZE to calculation Z0/ZE based on the selected UI direction to keep elevation semantics consistent.

## Files Changed
- `qols/scripts/approach-surface-UTM.py`
  - Adds threshold-end detection and outward-azimuth computation.
  - Applies UI direction as a 180° flip.
  - Logs base/outward/final azimuths and selected end for traceability.
- `qols/qols_dockwidget.py`
  - Packs `direction` into `specific_params` (0 when Start→End; -1 when End→Start).
  - Swaps Z0/ZE mapping for calculation to match chosen direction.

## Testing
1. Select one runway centerline feature and one threshold point (the threshold at the end you want to use).
2. Run with "Direction: Start to End": the surface must extend from the selected threshold in the runway's start→end direction.
3. Toggle to "Direction: End to Start": the surface must extend in the opposite direction.
4. Visually confirm the direction matches expectations (see attached screenshots in the issue).
5. Optional: print debug logs to confirm:
   - Base azimuth (start→end)
   - Selected threshold end (start/end)
   - Outward and final azimuth used for projection

## Backward Compatibility
- No breaking changes. Only azimuth orientation logic and elevation mapping based on UI direction were adjusted.

## Notes
- This PR focuses strictly on Issue #68. Geometry construction modernization (POLYGONZ via WKT) is handled in Issue #72 and not included here to keep scope focused.

## Closes
- Closes #68.
