# Consistency of Elevation Labels Across Surfaces (Issue #41)

## Summary

Align elevation field labels across surfaces with the previously updated Approach Surface. Replaced technical labels (Z0/ZE) with user-friendly terms:

- "Start Elevation (m)"
- "End Elevation (m)"

This makes the UI consistent and clearer for users while keeping backend logic unchanged.

## Scope of Changes

- Surface tabs updated: OFZ, Take-Off, Transitional
- UI-only change (labels); no changes to widget object names, backend code, or calculations

## Changes (Before → After)

- OFZ:
  - "Initial Elevation Z0 (m)" → "Start Elevation (m)"
  - "End Elevation ZE (m)" → "End Elevation (m)"
- Take-Off Surface:
  - "Initial Elevation Z0 (m)" → "Start Elevation (m)"
- Transitional Surface:
  - "Initial Elevation Z0 (m)" → "Start Elevation (m)"
  - "End Elevation ZE (m)" → "End Elevation (m)"

Note: Approach Surface was already updated in a previous PR (Issue #25) and serves as the reference for this change.

## Files Modified

- `qols/qols_panel_base.ui`

## Implementation Notes

- Only label texts were changed; widget names (e.g., `spin_Z0_*`, `spin_ZE_*`) remain the same
- No parameter passing or calculation logic was modified
- Low risk of regressions; labels are display-only

## How to Test

1. Open the qOLS plugin in QGIS
2. Navigate to each tab and verify labels:
   - OFZ: Start/End Elevation (m)
   - Take-Off Surface: Start Elevation (m)
   - Transitional Surface: Start/End Elevation (m)
3. Run a sample calculation in each tab to confirm no runtime errors and that behavior is unchanged

## Acceptance Criteria

- Labels in OFZ, Take-Off, and Transitional match the Approach Surface style
- No backend errors occur when running calculations
- No changes to widget IDs or parameter keys

## Related Issue

- Closes #41

## Screenshots (Optional)

- N/A (UI text updates only)

## Changelog

- UI: Standardized elevation labels across OFZ, Take-Off, and Transitional to "Start/End Elevation (m)"
