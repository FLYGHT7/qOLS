# Approach Surface Direction Handling Fix (Issue #40)

## Summary

This PR fixes the Approach Surface behavior so that elevation inputs respect the selected runway direction, as intended and as documented in prior changes:

- If "Start to End" is selected, the Start Elevation is used as the starting reference.
- If "End to Start" is selected, the End Elevation is used as the starting reference.

Previously, the merge mentioned this logic but it wasn’t being applied during execution.

## Changes

### Backend: Parameter Mapping (DockWidget)

- File: `qols/qols_dockwidget.py`
- Update parameter collection for "Approach Surface":
  - Compute `s` from the UI direction toggle: `s = 0` for Start→End, `s = -1` for End→Start.
  - Map UI values to calculation parameters:
    - For `s = 0`: `Z0 = Start Elevation`, `ZE = End Elevation`.
    - For `s = -1`: `Z0 = End Elevation`, `ZE = Start Elevation`.
  - Pass `s` inside `specific_params` to the script for consistent geometry orientation.

### Script: Respect Injected Parameters

- File: `scripts/approach-surface-UTM.py`
- Make the script consume injected variables from the plugin when present:
  - Use provided globals for `code`, `rwyClassification`/`typeAPP`, `widthApp`, `Z0`, `ZE`, `ARPH`, `L1`, `L2`, `LH`, `s`.
  - Keep original values as defaults to preserve standalone run behavior inside QGIS Python Console.
  - Continue using `s` to switch geometry orientation (including `s2 = 180` for reversed direction).

## Why This Fix

- The algorithm expects `Z0` to represent the first end along the selected direction and `ZE` the opposite end.
- The UI labels were updated to "Start Elevation" and "End Elevation", but the backend wasn’t remapping these values based on direction.
- This PR ensures correctness without changing the user inputs or script core geometry logic.

## Scope / Non-Goals

- No UI changes required (labels already standardized in Issue #25 and Issue #41).
- No changes to approach geometry math; only parameter wiring and defaults.
- No impact on other surfaces (Transitional has its own dedicated `s` handling which remains unchanged).

## How to Test

1. Open qOLS and select "Approach Surface".
2. Input distinct values for Start/End Elevation (e.g., Start = 2548.0, End = 2546.5).
3. Test both directions using the direction button:
   - Direction: Start to End
     - Expect the surface to start at Start Elevation.
   - Direction: End to Start
     - Expect the surface to start at End Elevation (i.e., values swapped internally).
4. Verify that the geometry orientation flips correctly and surface elevations reflect the chosen direction.

## Acceptance Criteria

- Elevation reference matches the selected direction for Approach Surface.
- No runtime errors; calculations succeed for both directions.
- Reversing direction changes the starting elevation and orientation as expected.

## Files Modified

- `qols/qols_dockwidget.py`
- `scripts/approach-surface-UTM.py`

## Risk & Compatibility

- Low risk: UI unchanged; parameter mapping is localized to Approach Surface.
- Backward compatible: scripts still run in isolation due to default fallbacks; plugin injects values when invoked via the UI.

## Related Issues

- Closes #40
- Related: #25 (label rename), #41 (label consistency)
