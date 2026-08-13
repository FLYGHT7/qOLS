"""qOLS QGIS Plugin entrypoint.

Defines the :class:`QOLS` class that QGIS instantiates via
``classFactory(iface)`` when the plugin is loaded.  Owns the toolbar
action, manages the dock widget lifecycle, and dispatches script
execution requests.
"""
import os
import sys
import math
import traceback
from .compat import DOCK_RIGHT, MSG_INFO, MSG_WARNING, MSG_CRITICAL, MSG_SUCCESS
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.PyQt.QtGui import QIcon, QColor
from qgis.PyQt.QtWidgets import QAction, QInputDialog
from qgis.core import (QgsProject, Qgis, QgsVectorLayer,
                       QgsFeature, QgsGeometry, QgsPoint, QgsField,
                       QgsPolygon, QgsLineString, QgsFillSymbol,
                       QgsVectorFileWriter, QgsCoordinateTransform,
                       QgsCoordinateReferenceSystem)

from .ui.dockwidget import QolsDockWidget
from .ui.new_ols_dockwidget import NewOlsDockWidget
from .ui.settings_dialog import RulesSettingsDialog
from .surface_types import SurfaceType
from .rules import manager as rule_mgr
from . import logger  # CR-01


class QOLS:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.actions = []
        self.menu = self.tr(u'&QOLS')
        self.first_start = True
        self.panel = None
        self.panel_new_ols = None
        try:
            _ = rule_mgr.list_rule_sets()
        except Exception:
            pass

    def tr(self, message):
        return QCoreApplication.translate('QOLS', message)

    def add_action(self, icon_path, text, callback, enabled_flag=True,
                   add_to_menu=True, add_to_toolbar=True,
                   status_tip=None, whats_this=None, parent=None):
        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        try:
            action.triggered.connect(callback)
        except Exception as e:
            logger.error(f"Error connecting action callback: {e}")

        action.setEnabled(enabled_flag)
        if status_tip is not None:
            action.setStatusTip(status_tip)
        if whats_this is not None:
            action.setWhatsThis(whats_this)
        if add_to_toolbar:
            try:
                self.iface.addToolBarIcon(action)
            except Exception as e:
                logger.error(f"Error adding action to toolbar: {e}")
        if add_to_menu:
            try:
                self.iface.addPluginToMenu(self.menu, action)
            except Exception as e:
                logger.error(f"Error adding action to menu: {e}")

        self.actions.append(action)
        return action

    def initGui(self):
        icon_current_path = os.path.join(self.plugin_dir, 'icon_current.png')
        icon_new_path = os.path.join(self.plugin_dir, 'icon_new.png')
        try:
            self.add_action(
                icon_current_path,
                text=self.tr(u'QOLS'),
                callback=self.show_panel,
                parent=self.iface.mainWindow())
            self.add_action(
                icon_new_path,
                text=self.tr(u'New OLS'),
                callback=self.show_new_ols_panel,
                status_tip=self.tr('Open New OLS Panel'),
                parent=self.iface.mainWindow())
            self.first_start = True

            rules_action = QAction(self.tr('Select Rule Set…'), self.iface.mainWindow())
            rules_action.triggered.connect(self.on_select_rule_set)
            self.iface.addPluginToMenu(self.menu, rules_action)
            self.actions.append(rules_action)

            reload_action = QAction(self.tr('Reload Rule Files'), self.iface.mainWindow())
            reload_action.triggered.connect(self.on_reload_rule_files)
            self.iface.addPluginToMenu(self.menu, reload_action)
            self.actions.append(reload_action)

            settings_action = QAction(self.tr('Settings'), self.iface.mainWindow())
            settings_action.triggered.connect(self.on_open_settings)
            self.iface.addPluginToMenu(self.menu, settings_action)
            self.actions.append(settings_action)

        except Exception as e:
            logger.error(f"Error in initGui: {e}\n{traceback.format_exc()}")

    def unload(self):
        for action in self.actions:
            self.iface.removePluginMenu(self.menu, action)
            self.iface.removeToolBarIcon(action)
        if self.panel:
            self.panel.close()
            self.panel = None
        if self.panel_new_ols:
            self.panel_new_ols.close()
            self.panel_new_ols = None

    def show_panel(self):
        """Toggle the QOLS dockwidget panel (show/hide)."""
        try:
            if self.panel and self.panel.isVisible():
                self.panel.hide()
                self.iface.messageBar().pushMessage(
                    "QOLS", "Panel closed!", level=MSG_INFO, duration=2)
                return

            if not self.panel:
                self.panel = QolsDockWidget(self.iface)
                self.iface.addDockWidget(DOCK_RIGHT, self.panel)
                self.panel.closingPlugin.connect(self.on_close_panel)
                self.panel.calculateClicked.connect(self.on_calculate)
                self.panel.closeClicked.connect(self.on_close_panel)

            self.panel.show()
            self.panel.raise_()
            self.iface.messageBar().pushMessage(
                "QOLS", "Panel opened!", level=MSG_INFO, duration=2)

        except Exception as e:
            logger.error(f"Error in show_panel: {e}\n{traceback.format_exc()}")
            self.iface.messageBar().pushMessage(
                "QOLS Error", f"Error showing panel: {str(e)}", level=MSG_CRITICAL)

    def on_close_panel(self):
        """Hide the panel when close is clicked."""
        if self.panel:
            self.panel.hide()

    def show_new_ols_panel(self):
        """Toggle the New OLS dock widget (show/hide)."""
        try:
            if self.panel_new_ols and self.panel_new_ols.isVisible():
                self.panel_new_ols.hide()
                self.iface.messageBar().pushMessage(
                    "New OLS", "Panel closed!", level=MSG_INFO, duration=2)
                return
            if self.panel_new_ols is None:
                self.panel_new_ols = NewOlsDockWidget(self.iface)
                self.iface.addDockWidget(DOCK_RIGHT, self.panel_new_ols)
                self.panel_new_ols.closingPlugin.connect(self.on_close_new_ols_panel)
                self.panel_new_ols.calculateClicked.connect(self.on_calculate_new_ols)
                self.panel_new_ols.closeClicked.connect(self.on_close_new_ols_panel)
            self.panel_new_ols.show()
            self.panel_new_ols.raise_()
            self.iface.messageBar().pushMessage(
                "New OLS", "Panel opened!", level=MSG_INFO, duration=2)
        except Exception as e:
            logger.error(f"Error in show_new_ols_panel: {e}\n{traceback.format_exc()}")
            self.iface.messageBar().pushMessage(
                "New OLS Error", f"Error showing panel: {str(e)}", level=MSG_CRITICAL)

    def on_close_new_ols_panel(self):
        """Hide the New OLS panel when close is clicked."""
        if self.panel_new_ols:
            self.panel_new_ols.hide()

    def on_calculate_new_ols(self):
        """Execute the selected New OLS surface calculation script with parameters."""
        try:
            params = self.panel_new_ols.get_parameters()
            if not params:
                self.iface.messageBar().pushMessage(
                    "New OLS", "Error getting parameters", level=MSG_CRITICAL)
                return

            st = params.get('surface_type')
            if not isinstance(st, SurfaceType):
                self.iface.messageBar().pushMessage(
                    "New OLS", "Please select a surface type", level=MSG_WARNING)
                return

            if st == SurfaceType.NEW_OLS_OFS_APPROACH:
                self.execute_new_ols_ofs_approach(params)
            elif st == SurfaceType.NEW_OLS_OES_HORIZONTAL:
                # #159 — OES surfaces are each calculated individually from
                # their own subtab now, instead of bundled behind one
                # shared Calculate click.
                self.execute_new_ols_oes_horizontal(params)
            elif st == SurfaceType.NEW_OLS_OES_DEPARTURE:
                self.execute_new_ols_oes_departure(params)
            elif st == SurfaceType.NEW_OLS_OES_PRECISION_APPROACH:
                self.execute_new_ols_oes_precision_approach(params)
            elif st == SurfaceType.NEW_OLS_OES_STRAIGHT_IN_APPROACH:
                self.execute_new_ols_oes_straight_in_approach(params)
            else:
                raise ValueError(f"Unhandled New OLS surface type: {st!r}")

            if params.get('_script_success', False):
                self.iface.messageBar().pushMessage(
                    "New OLS Success",
                    f"{st} calculation completed successfully",
                    level=MSG_SUCCESS)
            else:
                logger.warning(f"{st} completed but script did not set _script_success=True")

        except Exception as e:
            logger.error(f"Error in on_calculate_new_ols: {e}\n{traceback.format_exc()}")
            self.iface.messageBar().pushMessage(
                "New OLS Error", f"Error calculating surface: {str(e)}", level=MSG_CRITICAL)

    # CR-07: single method instead of repeated hasattr checks
    def _refresh_panel_defaults(self):
        """Refresh defaults on the open panel after a rule-set change."""
        if self.panel and self.panel.isVisible():
            try:
                self.panel.refresh_defaults()
            except Exception as e:
                logger.warning(f"Error refreshing panel defaults: {e}")

    def on_select_rule_set(self):
        """Show a dialog to select the active rule set and persist the choice."""
        try:
            registry = rule_mgr.list_rule_sets()
            names = sorted(list(registry.keys()))
            if not names:
                self.iface.messageBar().pushMessage(
                    "QOLS", "No rule files found in qols/rules",
                    level=MSG_WARNING, duration=4)
                return
            current = rule_mgr.get_active_rule_set_name() or ''
            name, ok = QInputDialog.getItem(
                self.iface.mainWindow(),
                self.tr('Select Rule Set'),
                self.tr('Active Rule Set:'),
                names,
                max(0, names.index(current)) if current in names else 0,
                False)
            if not ok:
                return
            rule_mgr.set_active_rule_set_name(name)
            self.iface.messageBar().pushMessage(
                "QOLS", f"Active rule set: {name}", level=MSG_INFO, duration=3)
            self._refresh_panel_defaults()
        except Exception as e:
            logger.error(f"Error selecting rule set: {e}")

    def on_reload_rule_files(self):
        """Force reload of rule JSON files and refresh panel defaults."""
        try:
            rule_mgr.reload_rules()
            self.iface.messageBar().pushMessage(
                "QOLS", "Rule files reloaded", level=MSG_INFO, duration=3)
            self._refresh_panel_defaults()
        except Exception as e:
            logger.error(f"Error reloading rule files: {e}")

    def on_open_settings(self):
        """Open the QOLS Settings dialog."""
        try:
            dlg = RulesSettingsDialog(self.iface.mainWindow())
            if dlg.exec() == dlg.Accepted:
                name = dlg.selected_rule_set()
                if name:
                    rule_mgr.set_active_rule_set_name(name)
                    self.iface.messageBar().pushMessage(
                        "QOLS", f"Active rule set: {name}", level=MSG_INFO, duration=3)
                    self._refresh_panel_defaults()
        except Exception as e:
            logger.error(f"Error opening settings dialog: {e}")

    def on_calculate(self):
        """Execute the selected surface calculation script with parameters."""
        try:
            params = self.panel.get_parameters()
            if params is None:
                return

            st = params.get('surface_type')
            if not isinstance(st, SurfaceType):
                self.iface.messageBar().pushMessage(
                    "QOLS", "Please select a surface type", level=MSG_WARNING)
                return

            if st == SurfaceType.APPROACH:
                self.execute_approach_surface(params)
            elif st == SurfaceType.CONICAL:
                self.execute_conical_surface(params)
            elif st == SurfaceType.INNER_HORIZONTAL:
                self.execute_inner_horizontal_surface(params)
            elif st == SurfaceType.INNER_CONICAL:
                self.execute_combined_inner_conical_surface(params)
            elif st == SurfaceType.OFZ:
                self.execute_ofz_surface(params)
            elif st == SurfaceType.OUTER_HORIZONTAL:
                self.execute_outer_horizontal_surface(params)
            elif st == SurfaceType.TAKEOFF:
                self.execute_takeoff_surface(params)
            elif st == SurfaceType.TRANSITIONAL:
                self.execute_transitional_surface(params)
            elif st == SurfaceType.NEW_OLS_OFS_APPROACH:
                self.execute_new_ols_ofs_approach(params)
            elif st == SurfaceType.NEW_OLS_OES_TRANSITIONAL:
                self.execute_new_ols_oes_transitional(params)
            else:
                raise ValueError(f"Unhandled surface type: {st!r}")

            # CR-08: only show success when the script confirmed it
            if params.get('_script_success', False):
                self.iface.messageBar().pushMessage(
                    "QOLS Success",
                    f"{st} calculation completed successfully",
                    level=MSG_SUCCESS)
            else:
                logger.warning(
                    f"{st} completed but script did not set _script_success=True")

        except Exception as e:
            logger.error(f"Error in on_calculate: {e}\n{traceback.format_exc()}")
            self.iface.messageBar().pushMessage(
                "QOLS Error", f"Error calculating surface: {str(e)}", level=MSG_CRITICAL)

    def execute_approach_surface(self, params):
        script_path = os.path.join(self.plugin_dir, 'scripts', 'approach-surface-UTM.py')
        self.execute_script(script_path, params)

    def execute_conical_surface(self, params):
        script_path = os.path.join(self.plugin_dir, 'scripts', 'conical.py')
        self.execute_script(script_path, params)

    def execute_inner_horizontal_surface(self, params):
        script_path = os.path.join(self.plugin_dir, 'scripts', 'inner-horizontal-racetrack.py')
        self.execute_script(script_path, params)

    def execute_ofz_surface(self, params):
        script_path = os.path.join(self.plugin_dir, 'scripts', 'OFZ_UTM.py')
        self.execute_script(script_path, params)

    def execute_outer_horizontal_surface(self, params):
        script_path = os.path.join(self.plugin_dir, 'scripts', 'outer-horizontal.py')
        self.execute_script(script_path, params)

    def execute_takeoff_surface(self, params):
        script_path = os.path.join(self.plugin_dir, 'scripts', 'take-off-surface_UTM.py')
        self.execute_script(script_path, params)

    def execute_transitional_surface(self, params):
        script_path = os.path.join(self.plugin_dir, 'scripts', 'TransitionalSurface_UTM.py')
        self.execute_script(script_path, params)

    def execute_new_ols_ofs_approach(self, params):
        approach_path = os.path.join(self.plugin_dir, 'scripts', 'new-ols-ofs-approach-UTM.py')
        trans_path = os.path.join(self.plugin_dir, 'scripts', 'new-ols-oes-transitional-UTM.py')

        # Run approach from the selected threshold only (one direction per user choice)
        self.execute_script(approach_path, params)
        ofs = params.get('specific_params', {})

        # Run transitional ONCE — approach wings + rectangular strips in a single layer.
        # The script resolves the near/opposite threshold itself from
        # threshold_layer + direction (mirrors the runway centerline endpoint
        # picked by direction, same as the legacy Transitional surface).
        trans_params = params.copy()
        trans_params['specific_params'] = {
            'width_m': ofs.get('inner_edge_m', 175.0),
            'start_elevation_m': ofs.get('start_elevation_m', 0.0),
            'end_elevation_m': ofs.get('end_elevation_m', 0.0),
            # #131: arp_elevation_m is now a top-level shared param, not
            # part of the OFS tab's own specific_params.
            'highest_thr_elev_m': params.get('arp_elevation_m', 0.0),
            'slope_pct': 20.0,
            'cap_height_m': 60.0,
            'approach_slope_pct': ofs.get('slope_pct', 3.33),
            'divergence_ratio': ofs.get('divergence_ratio', 0.10),
            'distance_from_threshold_m': ofs.get('distance_from_threshold_m', 60.0),
            'direction': ofs.get('direction', 0),
            'opp_start_elevation_m': ofs.get('end_elevation_m', 0.0),
        }
        self.execute_script(trans_path, trans_params)

    def execute_new_ols_oes_transitional(self, params):
        script_path = os.path.join(self.plugin_dir, 'scripts', 'new-ols-oes-transitional-UTM.py')
        self.execute_script(script_path, params)

    def execute_new_ols_oes_horizontal(self, params):
        """Horizontal Surface (#134) — its own OES subtab (#159), triggered
        individually; get_parameters() already shapes specific_params as
        adg/aerodrome_elevation_m/direction, no remapping needed."""
        script_path = os.path.join(self.plugin_dir, 'scripts', 'new-ols-oes-horizontal-UTM.py')
        self.execute_script(script_path, params)

    def execute_new_ols_oes_departure(self, params):
        """Instrument Departure Surface (#136) — its own OES subtab (#159),
        triggered individually; get_parameters() already shapes
        specific_params as start_elevation_m/direction, no remapping
        needed (Table 4-13 needs no ADG)."""
        script_path = os.path.join(self.plugin_dir, 'scripts', 'new-ols-oes-departure-UTM.py')
        self.execute_script(script_path, params)

    def execute_new_ols_oes_precision_approach(self, params):
        """Surface for Precision Approaches (#135) — its own OES subtab
        (#159), triggered individually; get_parameters() already shapes
        specific_params as start_elevation_m/direction, no remapping
        needed (Table 4-12 needs no ADG; runway_layer/threshold_layer
        are already shared at the top level of params)."""
        script_path = os.path.join(self.plugin_dir, 'scripts', 'new-ols-oes-precision-approach-UTM.py')
        self.execute_script(script_path, params)

    def execute_new_ols_oes_straight_in_approach(self, params):
        """Surface for Straight-in Instrument Approaches (#137) — its own
        OES subtab, triggered individually; get_parameters() already
        shapes specific_params as aerodrome_elevation_m/direction/lower_*/
        upper_*, no remapping needed (Table 4-11 needs no ADG)."""
        script_path = os.path.join(self.plugin_dir, 'scripts', 'new-ols-oes-straight-in-approach-UTM.py')
        self.execute_script(script_path, params)

    def execute_combined_inner_conical_surface(self, params):
        """Execute Inner Horizontal then Conical using per-surface parameters,
        then trim Conical's footprint down to the ring beyond Inner
        Horizontal (#124) — both are concentric racetracks (same runway
        spine/azimuth, Conical's radius >= Inner Horizontal's by
        construction), so Conical would otherwise fully cover it."""
        try:
            specific_params = params.get('specific_params', {})

            if specific_params.get('combined_execution', False):
                inner_params = specific_params.get('inner_horizontal', {})
                conical_params = specific_params.get('conical', {})
            else:
                inner_params = specific_params
                conical_params = specific_params

            inner_full_params = params.copy()
            inner_full_params['specific_params'] = inner_params
            inner_script_path = os.path.join(self.plugin_dir, 'scripts', 'inner-horizontal-racetrack.py')
            self.execute_script(inner_script_path, inner_full_params)

            conical_full_params = params.copy()
            conical_full_params['specific_params'] = conical_params
            conical_script_path = os.path.join(self.plugin_dir, 'scripts', 'conical.py')
            self.execute_script(conical_script_path, conical_full_params)

            self._trim_conical_to_ring(inner_params, conical_params)

        except Exception as e:
            logger.error(f"Error in combined Inner Horizontal & Conical execution: {e}\n{traceback.format_exc()}")
            raise

    def _trim_conical_to_ring(self, inner_params, conical_params):
        """#124: subtract Inner Horizontal's footprint from Conical's so the
        two surfaces don't visually overlap — Conical should only cover
        the ring beyond Inner Horizontal's edge, per ICAO Annex 14.

        Both scripts delete every global they introduced (including their
        own ``v_layer``) as their very last action — a pre-existing
        exec()-namespace cleanup pattern shared by every script in
        qols/scripts/ — so ``execute_script()``'s returned namespace never
        actually contains ``v_layer`` by the time control returns here.
        The layers are instead found by the same deterministic name each
        script itself builds (``f"InnerHorizontal_{classification}_Code{code}"``
        / ``f"Conical_{classification}_Code{code}"``), mirroring the
        name-based lookup convention #121 already established for the
        "Merged Transitional Surface" layer.

        Defensive: leaves Conical's original geometry untouched (per
        feature) if either layer can't be found unambiguously or a
        difference fails — a failed trim must not delete the surface the
        user just calculated.

        #125: the trimmed ring's two edges sit at different absolute
        elevations above the shared datum — the inner edge (touching
        Inner Horizontal) at ``datum + inner_height``, the outer edge at
        ``datum + inner_height + conical_height``. ``bottom_z`` uses the
        exact same formula Inner Horizontal itself computes its own flat
        Z with, guaranteeing the two surfaces meet at the same elevation
        by construction.
        """
        from .geometry_difference import difference_flat

        def _first_vertex_z(geom):
            """Diagnostic-only: exterior ring's first vertex Z, or None."""
            try:
                parts = geom.asGeometryCollection() if geom.isMultipart() else [geom]
                ring = parts[0].constGet().exteriorRing()
                return ring.pointN(0).z() if ring.numPoints() else None
            except Exception:
                return None

        def _first_interior_vertex_z(geom):
            """Diagnostic-only: first interior/hole ring's first vertex Z, or None
            (None also means "no hole yet" if the trim didn't produce one)."""
            try:
                parts = geom.asGeometryCollection() if geom.isMultipart() else [geom]
                abstract = parts[0].constGet()
                if abstract.numInteriorRings() == 0:
                    return None
                ring = abstract.interiorRing(0)
                return ring.pointN(0).z() if ring.numPoints() else None
            except Exception:
                return None

        datum_elevation = conical_params.get('datum_elevation', 0.0)
        inner_height = conical_params.get('inner_height', 0.0)
        conical_height = conical_params.get('height', 0.0)
        bottom_z = datum_elevation + inner_height
        top_z = datum_elevation + inner_height + conical_height
        logger.info(
            f"_trim_conical_to_ring: datum_elevation={datum_elevation}, inner_height={inner_height}, "
            f"conical_height={conical_height} -> bottom_z={bottom_z} (must match Inner Horizontal's own "
            f"Z, so the two surfaces meet as a single line), top_z={top_z}"
        )

        inner_name = (
            f"InnerHorizontal_{inner_params.get('rwyClassification', 'Precision Approach CAT I')}"
            f"_Code{inner_params.get('code', 4)}"
        )
        conical_name = (
            f"Conical_{conical_params.get('rwyClassification', 'Precision Approach CAT I')}"
            f"_Code{conical_params.get('code', 4)}"
        )
        inner_matches = QgsProject.instance().mapLayersByName(inner_name)
        conical_matches = QgsProject.instance().mapLayersByName(conical_name)
        logger.info(
            f"_trim_conical_to_ring: '{inner_name}' -> {len(inner_matches)} match(es), "
            f"'{conical_name}' -> {len(conical_matches)} match(es)"
        )
        if len(inner_matches) != 1 or len(conical_matches) != 1:
            logger.warning(
                "Could not trim Conical to a ring — expected exactly one Inner Horizontal and one "
                "Conical layer by name; delete older same-named layers and recalculate if this persists."
            )
            return
        inner_layer = inner_matches[0]
        conical_layer = conical_matches[0]

        inner_geoms = [f.geometry() for f in inner_layer.getFeatures() if not f.geometry().isEmpty()]
        logger.info(f"_trim_conical_to_ring: {len(inner_geoms)} Inner Horizontal geometrie(s) found")
        if not inner_geoms:
            logger.warning("_trim_conical_to_ring: no Inner Horizontal geometries, skipping trim")
            return
        logger.info(
            f"_trim_conical_to_ring: Inner Horizontal's own vertex Z (read from layer, "
            f"should equal bottom_z={bottom_z}) = {_first_vertex_z(inner_geoms[0])}"
        )
        inner_union = QgsGeometry.unaryUnion(inner_geoms)
        logger.info(
            f"_trim_conical_to_ring: inner_union area={inner_union.area() if inner_union else None}, "
            f"isEmpty={inner_union.isEmpty() if inner_union else None}"
        )

        pr = conical_layer.dataProvider()
        geometry_changes = {}
        conical_feature_count = 0
        for feat in conical_layer.getFeatures():
            conical_feature_count += 1
            trimmed = difference_flat(feat.geometry(), inner_union, exterior_z=top_z, interior_z=bottom_z)
            if trimmed is not None and not trimmed.isEmpty():
                geometry_changes[feat.id()] = trimmed
                logger.info(
                    f"_trim_conical_to_ring: feature {feat.id()} trimmed — exterior vertex Z="
                    f"{_first_vertex_z(trimmed)} (expected top_z={top_z}), interior/hole vertex Z="
                    f"{_first_interior_vertex_z(trimmed)} (expected bottom_z={bottom_z} — this is the "
                    f"single shared line/edge where Conical meets Inner Horizontal)"
                )
        logger.info(
            f"_trim_conical_to_ring: {conical_feature_count} Conical feature(s) processed, "
            f"{len(geometry_changes)} geometry change(s) prepared"
        )

        if geometry_changes:
            changed_ok = pr.changeGeometryValues(geometry_changes)
            logger.info(f"_trim_conical_to_ring: changeGeometryValues returned {changed_ok}")
            conical_layer.updateExtents()
            conical_layer.triggerRepaint()

    # ------------------------------------------------------------------
    # BUG-04 — Centralised layer validation
    # ------------------------------------------------------------------

    def _validate_layers_for_execution(self, params: dict) -> None:
        """Raise a descriptive exception if *params* contains invalid layers.

        Args:
            params: The parameter dict returned by
                    :meth:`~ui.dockwidget.QolsDockWidget.get_parameters`.

        Raises:
            ValueError: With a human-readable message on the first failing check.
        """
        runway_layer = params.get('runway_layer')
        threshold_layer = params.get('threshold_layer')

        if runway_layer is None:
            raise ValueError("No Runway Layer Centerline in parameters. Execution aborted.")
        if threshold_layer is None:
            raise ValueError("No threshold layer in parameters. Execution aborted.")

        if not isinstance(runway_layer, QgsVectorLayer):
            raise ValueError(f"Runway Layer Centerline is not a valid QgsVectorLayer: {type(runway_layer)}")
        if not isinstance(threshold_layer, QgsVectorLayer):
            raise ValueError(f"Threshold layer is not a valid QgsVectorLayer: {type(threshold_layer)}")

        project_layers = list(QgsProject.instance().mapLayers().values())
        if runway_layer not in project_layers:
            raise ValueError(f"Runway Layer Centerline '{runway_layer.name()}' not found in current project.")
        if threshold_layer not in project_layers:
            raise ValueError(f"Threshold layer '{threshold_layer.name()}' not found in current project.")

        if not runway_layer.isValid():
            raise ValueError(f"Runway Layer Centerline '{runway_layer.name()}' is invalid or corrupted.")
        if not threshold_layer.isValid():
            raise ValueError(f"Threshold layer '{threshold_layer.name()}' is invalid or corrupted.")

        if runway_layer.featureCount() == 0:
            raise ValueError(f"Runway Layer Centerline '{runway_layer.name()}' contains no features.")
        if threshold_layer.featureCount() == 0:
            raise ValueError(f"Threshold layer '{threshold_layer.name()}' contains no features.")

        use_runway_selected = params.get('use_runway_selected', False)
        use_threshold_selected = params.get('use_threshold_selected', False)
        if use_runway_selected and len(runway_layer.selectedFeatures()) == 0:
            raise ValueError("use_runway_selected=True but no runway features selected.")
        if use_threshold_selected and len(threshold_layer.selectedFeatures()) == 0:
            raise ValueError("use_threshold_selected=True but no threshold features selected.")

    def execute_script(self, script_path, params=None):
        """Execute a script with dynamic parameters and robust validation."""
        try:
            if params is None:
                raise ValueError("No parameters provided to script execution.")

            self._validate_layers_for_execution(params)

            runway_layer = params['runway_layer']
            threshold_layer = params['threshold_layer']
            logger.info(
                f"Executing {os.path.basename(script_path)} — "
                f"runway='{runway_layer.name()}' threshold='{threshold_layer.name()}'"
            )

            if not os.path.exists(script_path):
                raise ValueError(f"Script file not found: {script_path}")

            with open(script_path, 'r', encoding='utf-8') as f:
                script_content = f.read()

            specific_params = params.get('specific_params', {})

            # BUG-02: explicit priority order (low → high): QGIS stubs < params < specific_params
            # CR-10: inject compat constants so scripts don't re-implement the shim
            exec_namespace: dict = {
                '__file__': script_path,
                'iface': self.iface,
                'QgsProject': QgsProject,
                'QgsVectorLayer': QgsVectorLayer,
                'QgsFeature': QgsFeature,
                'QgsGeometry': QgsGeometry,
                'QgsPoint': QgsPoint,
                'QgsField': QgsField,
                'QgsPolygon': QgsPolygon,
                'QgsLineString': QgsLineString,
                'Qgis': Qgis,
                'QgsFillSymbol': QgsFillSymbol,
                'QgsVectorFileWriter': QgsVectorFileWriter,
                'QgsCoordinateTransform': QgsCoordinateTransform,
                'QgsCoordinateReferenceSystem': QgsCoordinateReferenceSystem,
                'QVariant': QVariant,
                'QColor': QColor,
                'os': os,
                'sys': sys,
                'math': math,
                # CR-10: compat constants — scripts reference these instead of re-implementing
                'MSG_INFO': MSG_INFO,
                'MSG_WARNING': MSG_WARNING,
                'MSG_CRITICAL': MSG_CRITICAL,
                'MSG_SUCCESS': MSG_SUCCESS,
                # Convenience aliases
                'active_rule_set': rule_mgr.get_active_rule_set_name(),
            }
            exec_namespace.update(params)
            exec_namespace.update(specific_params)
            # BUG-01: success sentinel
            exec_namespace['_script_success'] = False

            exec(script_content, exec_namespace)  # nosec B102 - bundled assets, not user input

            # CR-08: propagate success flag back into params so on_calculate can read it
            params['_script_success'] = exec_namespace.get('_script_success', False)
            if not params['_script_success']:
                logger.warning(f"Script did not set _script_success=True: {script_path}")
            else:
                logger.info(f"Script completed successfully: {os.path.basename(script_path)}")

        except Exception as e:
            logger.error(f"Error executing script {os.path.basename(script_path)}: {e}\n{traceback.format_exc()}")
            raise
