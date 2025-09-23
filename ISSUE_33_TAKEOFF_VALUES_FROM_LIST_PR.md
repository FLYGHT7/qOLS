# Take-Off Surface: Values From Table Applied + Parameters Exposed (Issue #33)

## Summary

Implements the client’s table-based specifications for the Take-Off Climb surface and exposes previously hardcoded values in the UI. Adds per-code defaults (Codes 1–4) for inner edge, start distance, divergence, final width, length, and slope; introduces an IMC/VMC checkbox for the 1200 m vs 1800 m final width rule; and rewires the backend and script to use these values instead of hardcoded constants.

## Background / Source

Based on the provided table (ICAO-conformant) for “RUNWAYS MEANT FOR TAKE-OFF – TAKE-OFF CLIMB”:

- Code 1: inner edge 60 m, start 30 m, divergence 10% (each side), final width 380 m, length 1600 m, slope 5%
- Code 2: inner edge 80 m, start 60 m, divergence 10% (each side), final width 580 m, length 2500 m, slope 4%
- Code 3 or 4: inner edge 180 m, start 60 m, divergence 12.5% (each side), final width 1800 m or 1200 m (see note), length 15000 m, slope 2%
- Final width note: 1800 m when intended track includes changes of heading > 15° for operations conducted in IMC, VMC by night; otherwise 1200 m.
- Start distance note: surface starts at end of clearway if clearway length exceeds the specified distance. We implemented this as start = max(CWYLength, Start Distance).

## What Changed

### UI (Take-Off tab)

- New fields (editable by user):
  - `Divergence (%)` (`spin_divergence_takeoff`)
  - `Start Distance (m)` (`spin_startDistance_takeoff`)
  - `Surface Length (m)` (`spin_surfaceLength_takeoff`)
  - `Slope (%)` (`spin_slope_takeoff`)
- New option: `IMC/Night VMC > 15° option` (`check_imc_heading_takeoff`, checked by default)
  - Shown only for Code 3 or 4
  - When checked: final width defaults to 1800 m; unchecked: 1200 m
- Existing fields continued: `Width Dep (m)`, `Max Width Dep (m)`, `CWY Length (m)`, `Start Elevation (m)`

### Auto Defaults From Table

- On Take-Off `Code` change, the following fields are populated from the table:
  - `Width Dep (m)` (inner edge)
  - `Start Distance (m)`
  - `Divergence (%)`
  - `Surface Length (m)`
  - `Slope (%)`
  - `Max Width Dep (m)` (final width, honoring IMC checkbox for code 3/4)
- On IMC checkbox toggle (code 3/4), only `Max Width Dep (m)` switches between 1800 and 1200; other fields remain unchanged.
- Users can still override any value after defaults are applied.

### Backend (DockWidget)

- Collects new parameters and passes them to the script:
  - `divergencePct`, `startDistance`, `surfaceLength`, `slopePct`, `maxWidthDep`
- Applies final width logic for Code 3/4 + IMC checkbox
- Applies start offset as `max(CWYLength, startDistance)` (implemented in script)
- Shows/hides IMC checkbox for codes 3/4; applies defaults on code change and final-width-only update on IMC toggle

### Script (`scripts/take-off-surface_UTM.py`)

- Replaced hardcoded constants with injected parameters (with safe defaults if run in console):
  - `divergencePct`, `startDistance`, `surfaceLength`, `slopePct`, plus previously used `widthDep`, `maxWidthDep`, `CWYLength`, `Z0`, `ZE`, etc.
- Geometry calculations updated:
  - Start station: `dD = max(CWYLength, startDistance)` per table note
  - Divergence distance to reach final width uses `divergencePct/100.0`
  - Elevation increase uses `slopePct/100.0`
  - End of surface uses `surfaceLength`

## Files Modified

- `qols/qols_panel_base.ui` — Added new Take-Off fields and IMC checkbox
- `qols/qols_dockwidget.py` — Parameter collection, per-code defaults, IMC toggle behavior, UI signal wiring
- `scripts/take-off-surface_UTM.py` — Consume injected params; remove hardcoded values

## How It Maps to the Table

- Inner edge → `Width Dep (m)`
- Distance from runway end → `Start Distance (m)` (min start, overridden by CWY when CWY > start)
- Divergence (each side) → `Divergence (%)`
- Final width → `Max Width Dep (m)` (1200/1800 for code 3/4 per IMC checkbox)
- Length → `Surface Length (m)`
- Slope → `Slope (%)`

## Testing

1. Open the plugin → Take-Off Surface tab
2. Select Code 1, 2, 3, 4 and confirm the fields update to:
   - Code 1: 60 / 30 / 10% / 380 / 1600 / 5%
   - Code 2: 80 / 60 / 10% / 580 / 2500 / 4%
   - Code 3/4: 180 / 60 / 12.5% / 1800 / 15000 / 2%
3. For Code 3 or 4, uncheck the IMC checkbox and confirm `Max Width Dep (m)` switches to 1200; recheck to return to 1800
4. Enter a non-empty `CWY Length (m)`, greater than `Start Distance (m)`; run calculation and verify start offset matches CWY length
5. Run calculations and verify geometry reflects:
   - Start offset = max(CWY, Start Distance)
   - Distance to full width varies with divergence and max width
   - End elevation reflects slope × surface length

## Acceptance Criteria

- All table values apply automatically on code change
- IMC checkbox visible only for Code 3/4 and toggles final width between 1200/1800
- Users can still manually override any field after defaults are applied
- Calculations use these values (no hidden hardcoded constants remain)
- Start offset logic respects table note (CWY override)

## Non-Goals

- No changes to the algorithm’s broader geometry other than parameterization
- No locking of fields; user retains full control after defaults apply

## Risk & Compatibility

- Low risk: UI-only additions and parameterized script. Defaults applied deterministically from the table.
- Backwards compatible: Script retains defaults when executed from console; plugin injects values in normal use.

## Related

- Issue: #33 (Takeoff Values from List)
- See also: #41 (label consistency), #26 (RWY Classification groundwork)
