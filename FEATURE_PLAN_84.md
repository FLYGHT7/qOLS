# Feature Plan — #84 Stepped Surface Contours

> **Issue:** [Enhancement stepped surface #84](https://github.com/FLYGHT7/qOLS/issues/84)  
> **Branch:** `feature/84-stepped-surface-contours`  
> **Scope (Phase 1):** Approach Surface + Take-Off Surface  
> **Scope (Phase 2):** All remaining surfaces

---

## Non-Technical Summary

When working with obstacle charts, analysts need to see **elevation bands** ("steps") on each surface — e.g., "here the surface is 10 m, here it is 20 m, here it is 30 m".  
This feature adds a **Contour Interval** input to each surface tab. When set (e.g., to 10 m), the plugin generates a second QGIS layer of **line features** after each surface calculation. Each line marks where the surface reaches a specific height, labeled directly in the map for easy obstacle assessment.

**Output:** layer `RWY_<SurfaceName>_Contours` — `LineStringZ`, field `surface_elevation` (Double).

Reference image = horizontal red lines spaced at equal elevation intervals across the approach surface trapezoid.

---

## Constraints & Guidelines

| Constraint       | Detail                                                                                                                                          |
| ---------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| Qt compatibility | `qgis.PyQt` only — never `PyQt5`/`PyQt6` directly                                                                                               |
| QGIS API         | `qgis.core`, `qgis.PyQt.QtCore` — all versions ≥ 3.4                                                                                            |
| Calculation code | Scripts in `scripts/` are **PROTECTED** — geometry math is unchanged; only the new contour block is added _after_ the existing polygon creation |
| Python           | Type-annotated, dataclasses for data structures (python-best-practices skill)                                                                   |
| Qt patterns      | `@Slot()` decorators, no inline signal connections, `qgis.PyQt.QtCore.QVariant` for QgsField types (pyside6-reviewer skill)                     |
| Whole numbers    | Contour elevations snap to integer multiples of the interval                                                                                    |
| Zero = disabled  | `contour_interval_m = 0` (or empty) → no contour layer generated                                                                                |

---

## Algorithm Design

### Contour elevation levels

Given a sloped section from `z_start` to `z_end` with positive slope, find contour levels:

```
z_levels = [c for c in range(ceil(z_start / interval) * interval,
                               floor(z_end / interval) * interval + 1,
                               interval)]
```

Example: z_start = 21.7 m, z_end = 81.7 m, interval = 10 m → levels = [30, 40, 50, 60, 70, 80]

### Approach Surface — contour geometry

The surface center line starts at **pt_01** (threshold + `threshold_offset_m`), elevation `start_elevation_m`, going along `azimuth`.

| Section    | Distance range from pt_01 | Elevation                      | Half-width at d                  |
| ---------- | ------------------------- | ------------------------------ | -------------------------------- |
| Section 1  | `[0, L1]`                 | `z_start + d * slope1`         | `width/2 + d * divergence_ratio` |
| Section 2  | `[L1, L1+L2]`             | `z_sec1_end + (d-L1) * slope2` | same formula continues           |
| Horizontal | `[L1+L2, L1+L2+LH]`       | constant = `z_sec2_end`        | same formula continues           |

For contour at elevation `z_c` in section 1:

$$d_c = \frac{z_c - z_{start}}{\text{slope1}}$$

For contour at elevation `z_c` in section 2:

$$d_c = L_1 + \frac{z_c - z_{sec1end}}{\text{slope2}}$$

Contour line = two points:

- `center = pt_01.project(d_c, azimuth)`
- `left  = center.project(half_w(d_c), azimuth + 90)`
- `right = center.project(half_w(d_c), azimuth - 90)`
- Line: `QgsLineString([left, right])` with Z set to `z_c`

> **No contours in the Horizontal section** — constant elevation means infinite density.

### Take-Off Surface — contour geometry

Center line starts at **pt_01D** (threshold + `startDistance`), elevation `ZE`, going along `bazimuth`.

| Distance range from pt_01D               | Half-width                          |
| ---------------------------------------- | ----------------------------------- |
| `[0, distance_to_max_width]`             | `widthDep/2 + d * divergence_ratio` |
| `[distance_to_max_width, surfaceLength]` | `maxWidthDep / 2` (constant)        |

Elevation: `z(d) = ZE + d * slope_ratio` where `slope_ratio = slopePct / 100`

For contour at `z_c`:

$$d_c = \frac{z_c - ZE}{\text{slope\_ratio}}$$

Must be within `[0, surfaceLength]`.

---

## Architecture

```
qols/
├── scripts/
│   ├── _contour_utils.py          ← NEW: pure-Python contour helpers (no QGIS)
│   ├── approach-surface-UTM.py    ← MODIFIED: add contour block after polygon
│   └── take-off-surface_UTM.py   ← MODIFIED: add contour block after polygon
└── qols_dockwidget.py             ← MODIFIED: contour_interval_m parameter
qols_panel_base.ui                 ← MODIFIED: spin_contour_interval fields
```

### `_contour_utils.py` design (python-best-practices skill)

```python
from dataclasses import dataclass
from math import ceil, floor
from typing import Iterator

@dataclass(frozen=True)
class ContourSpec:
    """Geometry-agnostic spec for a single contour line."""
    elevation: float              # elevation label in metres
    distance_from_origin: float   # distance along surface center axis
    half_width: float             # half-width of contour line

def contour_elevations(z_start: float, z_end: float, interval: int) -> list[float]:
    """Return whole-number elevation levels at `interval` spacing within [z_start, z_end]."""
    if interval <= 0 or z_end <= z_start:
        return []
    first = int(ceil(z_start / interval)) * interval
    last  = int(floor(z_end  / interval)) * interval
    return [float(v) for v in range(first, last + 1, interval)]

def contour_specs_for_linear_section(
    z_section_start: float,
    z_section_end: float,
    slope: float,
    d_offset: float,
    near_half_width: float,
    divergence_ratio: float,
    elevations: list[float],
) -> list[ContourSpec]:
    """Compute ContourSpecs for a linearly sloped section."""
    specs = []
    for z_c in elevations:
        if not (z_section_start < z_c <= z_section_end):
            continue
        if slope <= 0:
            continue
        d_c = d_offset + (z_c - z_section_start) / slope
        half_w = near_half_width + d_c * divergence_ratio
        specs.append(ContourSpec(elevation=z_c, distance_from_origin=d_c, half_width=half_w))
    return specs
```

> This module is **imported inside the scripts** using a relative path import via `importlib` (since scripts run under `exec()`):
>
> ```python
> import importlib.util, os as _os
> _spec = importlib.util.spec_from_file_location(
>     '_contour_utils',
>     _os.path.join(_os.path.dirname(__file__), '_contour_utils.py')
> )
> _cu = importlib.util.module_from_spec(_spec)
> _spec.loader.exec_module(_cu)
> ```

---

## Task Table

### Phase 1 — Algorithm module

| ID    | Task                                                                                                                     | Risk | Status |
| ----- | ------------------------------------------------------------------------------------------------------------------------ | ---- | ------ |
| CT-01 | Create `qols/scripts/_contour_utils.py` with `ContourSpec`, `contour_elevations()`, `contour_specs_for_linear_section()` | None | ✅     |
| CT-02 | Unit tests for `_contour_utils.py` (no QGIS required)                                                                    | None | ✅     |

### Phase 2 — UI Parameters

| ID    | Task                                                                                              | Risk | Status |
| ----- | ------------------------------------------------------------------------------------------------- | ---- | ------ |
| CT-03 | Add `spin_contour_interval` QLineEdit row to Approach Surface tab in `qols_panel_base.ui`         | Low  | ✅     |
| CT-04 | Add `spin_contour_interval_takeoff` QLineEdit row to Take-Off Surface tab in `qols_panel_base.ui` | Low  | ✅     |
| CT-05 | Add validation for both fields in `setup_numeric_lineedit_validation()` (integer ≥ 0, default 10) | Low  | ✅     |
| CT-06 | Expose `contour_interval_m` in `get_parameters()` for `"Approach Surface"` branch                 | Low  | ✅     |
| CT-07 | Expose `contour_interval_m` in `get_parameters()` for `"Take-Off Surface"` branch                 | Low  | ✅     |

### Phase 3 — Approach Surface contours

| ID    | Task                                                                                                              | Risk | Status |
| ----- | ----------------------------------------------------------------------------------------------------------------- | ---- | ------ |
| CT-08 | Import `_contour_utils` inside `approach-surface-UTM.py` via `importlib`                                          | Low  | ⏳     |
| CT-09 | Read `contour_interval_m` from globals (default 0 = disabled)                                                     | None | ⏳     |
| CT-10 | Compute contour specs for Section 1 (if slope1 > 0 and L1 > 0)                                                    | None | ⏳     |
| CT-11 | Compute contour specs for Section 2 (if slope2 > 0 and L2 > 0)                                                    | None | ⏳     |
| CT-12 | Create `LineStringZ` layer `RWY_ApproachSurface_Contours` with fields `ID` (String), `surface_elevation` (Double) | Low  | ⏳     |
| CT-13 | Add `QgsFeature` per contour spec to the layer                                                                    | None | ⏳     |
| CT-14 | Apply red line style (width 0.5)                                                                                  | None | ⏳     |
| CT-15 | Enable QGIS labeling on `surface_elevation` field                                                                 | None | ⏳     |
| CT-16 | Add layer to project                                                                                              | None | ⏳     |

### Phase 4 — Take-Off Surface contours

| ID    | Task                                                                         | Risk | Status |
| ----- | ---------------------------------------------------------------------------- | ---- | ------ |
| CT-17 | Import `_contour_utils` inside `take-off-surface_UTM.py` via `importlib`     | Low  | ⏳     |
| CT-18 | Read `contour_interval_m` from globals (default 0 = disabled)                | None | ⏳     |
| CT-19 | Compute contour specs along slope for width-expanding + constant-width zones | None | ⏳     |
| CT-20 | Create `LineStringZ` layer `RWY_TakeOffSurface_Contours` with same schema    | Low  | ⏳     |
| CT-21 | Add features, style, labeling, add to project                                | None | ⏳     |

### Phase 5 — Integration tests

| ID    | Task                                                                                       | Risk | Status |
| ----- | ------------------------------------------------------------------------------------------ | ---- | ------ |
| CT-22 | Integration tests for approach contour output (line count, elevations, geometry positions) | None | ⏳     |
| CT-23 | Integration tests for take-off contour output                                              | None | ⏳     |

### Phase 6 — Remaining surfaces (future)

| Surface          | Notes                                                                                                                                       |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| Conical          | Radial surface — contour = concentric arcs at intervals. Elevation increases with radius: `z(r) = z_inner + (r - r_inner) * slope_pct/100`. |
| Inner Horizontal | Flat surface — no contours (constant elevation).                                                                                            |
| OFZ              | Similar linear slope to approach.                                                                                                           |
| Transitional     | Complex lateral slope — contours run parallel to the runway.                                                                                |
| Outer Horizontal | Flat — no contours.                                                                                                                         |

---

## Qt / QGIS Compatibility Notes

```python
# ✅ All QgsField type declarations use qgis.PyQt.QtCore.QVariant (Qt5 + Qt6 safe)
from qgis.PyQt.QtCore import QVariant
id_field  = QgsField('ID', QVariant.String)
elev_field = QgsField('surface_elevation', QVariant.Double)

# ✅ LineStringZ layer type string — supported in QGIS 3.4+
contour_layer = QgsVectorLayer("LineStringZ?crs=" + map_srid, layer_name, "memory")

# ✅ QgsGeometry from QgsLineString — Z coords set via QgsPoint(x, y, z)
left  = QgsPoint(lx, ly, z_c)
right = QgsPoint(rx, ry, z_c)
geom  = QgsGeometry(QgsLineString([left, right]))

# ✅ Labeling — QGIS 3.4+ API
from qgis.core import QgsPalLayerSettings, QgsVectorLayerSimpleLabeling, QgsTextFormat
pal = QgsPalLayerSettings()
pal.fieldName = 'surface_elevation'
pal.enabled = True
contour_layer.setLabeling(QgsVectorLayerSimpleLabeling(pal))
contour_layer.setLabelsEnabled(True)
```

---

## Acceptance Criteria

1. `contour_interval_m = 0` → no contour layer created, existing behavior unchanged
2. `contour_interval_m = 10` → contour lines at 10 m, 20 m, 30 m, ... up to max surface elevation
3. All contour elevations are **integer multiples** of `contour_interval_m`
4. Each line feature has `surface_elevation` attribute matching its elevation label
5. Lines are styled **red** and labeled with their elevation value
6. Works for both Start→End and End→Start directions
7. Zero regression on existing test suite (362 / 362 ✅)
8. Compatible with QGIS 3.4+ and both Qt5 / Qt6 bindings

---

## Changelog

| Date       | Entry                                                                                   |
| ---------- | --------------------------------------------------------------------------------------- |
| 2026-03-30 | Feature plan created. Branch `feature/84-stepped-surface-contours` created from `main`. |
| 2026-03-30 | Phase 1 complete — `_contour_utils.py` (CT-01) and `test_contour_utils.py` (CT-02) committed. 26/26 tests pass. |
| 2026-03-30 | Phase 2 complete — `spin_contour_interval` / `spin_contour_interval_takeoff` added to UI, validation and `get_parameters()` wired (CT-03–CT-07). |
