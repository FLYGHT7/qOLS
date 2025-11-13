# PR: Rename "Runway Layer" to "Runway Layer Centerline" (#71)

## Summary

This PR standardizes all user-facing occurrences of "Runway Layer" to "Runway Layer Centerline" to eliminate ambiguity and clearly reference the expected LINE geometry representing runway centerlines. The change spans UI labels and tooltips, validation messages, logs, and exceptions. No functional logic or algorithms were changed.

## Rationale

- Clarifies that the input is the centerline layer (LINE geometry), not polygons or other runway-related layers.
- Aligns the terminology across the entire plugin for consistency and better UX.

## Scope of Changes

- Text-only updates across UI and messages. No changes to business logic, data models, or geometry computations.

## Files Updated

- UI
  - `qols/qols_panel_base.ui`: label and tooltip updated to "Runway Layer Centerline".
- Framework and messages
  - `qols/qols_dockwidget.py`: validation messages, prompts, and logs updated.
  - `qols/qols.py`: critical error messages and logs updated.
  - `qols/icon_manager.py`: helper/guide text updated.
- Scripts
  - `qols/scripts/approach-surface-UTM.py`
  - `qols/scripts/OFZ_UTM.py`
  - `qols/scripts/TransitionalSurface_UTM.py`
  - `qols/scripts/take-off-surface_UTM.py`
  - `qols/scripts/conical.py`
  - `qols/scripts/inner-horizontal-racetrack.py`

## User Impact

- UI label now reads "Runway Layer Centerline"; tooltips and message bar errors reflect the same terminology.
- No change to existing project files or layer filtering behavior. Users still select LINE geometry layers (centerlines) as before.

## Testing

1. Reload the plugin in QGIS.
2. Open the dock and verify the label reads "Runway Layer Centerline" and the tooltip mentions "centerlines".
3. Attempt to run without selecting a centerline layer and confirm the error message mentions "Runway Layer Centerline".
4. Run each generator (Approach, OFZ, Transitional, Take-Off, Inner Horizontal/Conical) with a valid centerline layer and confirm normal operation (no behavior change expected).

## Backward Compatibility

- Backward compatible. Only user-facing strings were changed. No API, logic, or data format changes.

## Documentation

- Inline UI texts updated; no external docs required. Release notes should mention the terminology update for clarity.

## Versioning

- Recommended: Patch or minor bump due to UI text changes (no functional changes).

## Related Issues

- Closes #71.
