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
from qgis.core import (QgsProject, QgsMessageLog, Qgis, QgsVectorLayer, 
                      QgsFeature, QgsGeometry, QgsPoint, QgsField, 
                      QgsPolygon, QgsLineString, QgsFillSymbol,
                      QgsVectorFileWriter, QgsCoordinateTransform,
                      QgsCoordinateReferenceSystem)

from .ui.dockwidget import QolsDockWidget
from .ui.settings_dialog import RulesSettingsDialog
from .surface_types import SurfaceType
from .rules import manager as rule_mgr

class QOLS:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.actions = []
        self.menu = self.tr(u'&QOLS')
        self.first_start = True
        self.panel = None
        # Ensure rule sets are discoverable on startup
        try:
            _ = rule_mgr.list_rule_sets()
        except Exception:
            pass

    def tr(self, message):
        return QCoreApplication.translate('QOLS', message)

    def add_action(self, icon_path, text, callback, enabled_flag=True, add_to_menu=True, add_to_toolbar=True, status_tip=None, whats_this=None, parent=None):
        print(f"QOLS: add_action called with callback: {callback}")
        print(f"QOLS: add_to_toolbar: {add_to_toolbar}")
        print(f"QOLS: add_to_menu: {add_to_menu}")
        
        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        print(f"QOLS: Action created: {action}")
        
        try:
            action.triggered.connect(callback)
            print("QOLS: Action connected to callback")
        except Exception as e:
            print(f"QOLS: Error connecting callback: {e}")
            
        action.setEnabled(enabled_flag)
        
        if status_tip is not None:
            action.setStatusTip(status_tip)
        
        if whats_this is not None:
            action.setWhatsThis(whats_this)
        
        if add_to_toolbar:
            try:
                self.iface.addToolBarIcon(action)
                print("QOLS: Action added to toolbar")
            except Exception as e:
                print(f"QOLS: Error adding to toolbar: {e}")
        
        if add_to_menu:
            try:
                self.iface.addPluginToMenu(self.menu, action)
                print("QOLS: Action added to menu")
            except Exception as e:
                print(f"QOLS: Error adding to menu: {e}")
        
        self.actions.append(action)
        print(f"QOLS: Total actions: {len(self.actions)}")
        return action

    def initGui(self):
        print("QOLS: initGui called")
        icon_path = os.path.join(self.plugin_dir, 'icon.png')
        print(f"QOLS: Icon path: {icon_path}")
        print(f"QOLS: Icon exists: {os.path.exists(icon_path)}")
        
        try:
            self.add_action(
                icon_path,
                text=self.tr(u'QOLS'),
                callback=self.show_panel,
                parent=self.iface.mainWindow())
            print("QOLS: Action added successfully")
            self.first_start = True

            # Add menu entry for Rule Set selection (Issue #65)
            try:
                rules_action = QAction(self.tr('Select Rule Setâ€¦'), self.iface.mainWindow())
                rules_action.triggered.connect(self.on_select_rule_set)
                self.iface.addPluginToMenu(self.menu, rules_action)
                self.actions.append(rules_action)
                print("QOLS: Added 'Select Rule Setâ€¦' menu action")
            except Exception as e:
                print(f"QOLS: Error adding 'Select Rule Setâ€¦' action: {e}")

            # Optional: Reload rule files action
            try:
                reload_action = QAction(self.tr('Reload Rule Files'), self.iface.mainWindow())
                reload_action.triggered.connect(self.on_reload_rule_files)
                self.iface.addPluginToMenu(self.menu, reload_action)
                self.actions.append(reload_action)
                print("QOLS: Added 'Reload Rule Files' menu action")
            except Exception as e:
                print(f"QOLS: Error adding 'Reload Rule Files' action: {e}")

            # Settings dialog action (like QPANSOPY style)
            try:
                settings_action = QAction(self.tr('Settings'), self.iface.mainWindow())
                settings_action.triggered.connect(self.on_open_settings)
                self.iface.addPluginToMenu(self.menu, settings_action)
                self.actions.append(settings_action)
                print("QOLS: Added 'Settings' menu action")
            except Exception as e:
                print(f"QOLS: Error adding 'Settings' action: {e}")
        except Exception as e:
            print(f"QOLS: Error in initGui: {e}")
            traceback.print_exc()

    def unload(self):
        for action in self.actions:
            self.iface.removePluginMenu(self.menu, action)
            self.iface.removeToolBarIcon(action)
        if self.panel:
            self.panel.close()
            self.panel = None

    def show_panel(self):
        """Toggle the QOLS dockwidget panel (show/hide)"""
        print("QOLS: show_panel called - BUTTON CLICKED!")
        
        try:
            # If panel exists and is visible, hide it
            if self.panel and self.panel.isVisible():
                print("QOLS: Hiding existing panel")
                self.panel.hide()
                self.iface.messageBar().pushMessage(
                    "QOLS", 
                    "Panel closed!", 
                    level=MSG_INFO,
                    duration=2
                )
                return
            
            # If panel doesn't exist, create it
            if not self.panel:
                print("QOLS: Creating new panel")
                self.panel = QolsDockWidget(self.iface)
                # Add panel to RIGHT SIDE instead of left
                self.iface.addDockWidget(DOCK_RIGHT, self.panel)
                self.panel.closingPlugin.connect(self.on_close_panel)
                self.panel.calculateClicked.connect(self.on_calculate)
                self.panel.closeClicked.connect(self.on_close_panel)
                print("QOLS: Panel created successfully")
            else:
                print("QOLS: Panel already exists, showing it")
            
            # Show and raise the panel
            self.panel.show()
            self.panel.raise_()
            print("QOLS: Panel shown and raised")
            
            # Show success message
            self.iface.messageBar().pushMessage(
                "QOLS", 
                "Panel opened!", 
                level=MSG_INFO,
                duration=2
            )
            
        except Exception as e:
            print(f"QOLS Error in show_panel: {e}")
            traceback.print_exc()
            self.iface.messageBar().pushMessage(
                "QOLS Error", 
                f"Error showing panel: {str(e)}", 
                level=MSG_CRITICAL
            )

    def on_close_panel(self):
        """Hide the panel when close is clicked"""
        if self.panel:
            self.panel.hide()
            # Don't set to None to keep the panel for reuse

    def on_select_rule_set(self):
        """Show a simple input dialog to select the active rule set and persist the choice."""
        try:
            registry = rule_mgr.list_rule_sets()
            names = sorted(list(registry.keys()))
            if not names:
                self.iface.messageBar().pushMessage("QOLS", "No rule files found in qols/rules", level=MSG_WARNING, duration=4)
                return
            current = rule_mgr.get_active_rule_set_name() or ''
            # Display selection dialog
            name, ok = QInputDialog.getItem(self.iface.mainWindow(), self.tr('Select Rule Set'), self.tr('Active Rule Set:'), names, max(0, names.index(current)) if current in names else 0, False)
            if not ok:
                return
            rule_mgr.set_active_rule_set_name(name)
            # Notify user
            self.iface.messageBar().pushMessage("QOLS", f"Active rule set: {name}", level=MSG_INFO, duration=3)
            # Refresh defaults in panel if open
            if self.panel and self.panel.isVisible():
                try:
                    # Re-apply defaults on combined tab if widgets exist
                    if hasattr(self.panel, 'apply_combined_inner_conical_defaults_from_selection'):
                        self.panel.apply_combined_inner_conical_defaults_from_selection()
                except Exception as e:
                    print(f"QOLS: Error refreshing panel defaults after rule change: {e}")
        except Exception as e:
            print(f"QOLS: Error selecting rule set: {e}")

    def on_reload_rule_files(self):
        """Force reload of rule JSON files and refresh panel defaults."""
        try:
            rule_mgr.reload_rules()
            self.iface.messageBar().pushMessage("QOLS", "Rule files reloaded", level=MSG_INFO, duration=3)
            # Refresh defaults if panel open
            if self.panel and self.panel.isVisible():
                try:
                    if hasattr(self.panel, 'apply_combined_inner_conical_defaults_from_selection'):
                        self.panel.apply_combined_inner_conical_defaults_from_selection()
                except Exception as e:
                    print(f"QOLS: Error refreshing panel after rule reload: {e}")
        except Exception as e:
            print(f"QOLS: Error reloading rule files: {e}")

    def on_open_settings(self):
        """Open the QOLS Settings dialog (QPANSOPY-like minimal settings)."""
        try:
            dlg = RulesSettingsDialog(self.iface.mainWindow())
            if dlg.exec() == dlg.Accepted:
                name = dlg.selected_rule_set()
                if name:
                    rule_mgr.set_active_rule_set_name(name)
                    self.iface.messageBar().pushMessage("QOLS", f"Active rule set: {name}", level=MSG_INFO, duration=3)
                    # Refresh defaults if panel is open
                    if self.panel and self.panel.isVisible():
                        try:
                            if hasattr(self.panel, 'apply_combined_inner_conical_defaults_from_selection'):
                                self.panel.apply_combined_inner_conical_defaults_from_selection()
                        except Exception as e:
                            print(f"QOLS: Error refreshing panel after settings update: {e}")
        except Exception as e:
            print(f"QOLS: Error opening settings dialog: {e}")

    def on_calculate(self):
        """Execute the selected surface calculation script with parameters"""
        try:
            params = self.panel.get_parameters()
            if not params:
                self.iface.messageBar().pushMessage("QOLS", "Error getting parameters", level=MSG_CRITICAL)
                return
                
            surface_type = params.get('surface_type')
            specific_params = params.get('specific_params', {})
            
            print(f"QOLS: Executing {surface_type} with params: {specific_params}")
            print(f"QOLS DEBUG: Full params dict: {params}")
            print(f"QOLS DEBUG: specific_params content: {specific_params}")
            print(f"QOLS DEBUG: specific_params type: {type(specific_params)}")
            print(f"QOLS DEBUG: specific_params keys: {list(specific_params.keys())}")
            
            # Normalise to SurfaceType enum to catch typos early (R-03)
            try:
                st = SurfaceType.from_tab_text(surface_type)
            except ValueError:
                self.iface.messageBar().pushMessage("QOLS", "Please select a surface type", level=MSG_WARNING)
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
            
            # Show success message
            self.iface.messageBar().pushMessage(
                "QOLS Success", 
                f"{surface_type} calculation completed successfully", 
                level=MSG_SUCCESS
            )
                
        except Exception as e:
            print(f"QOLS: Error in on_calculate: {e}")
            traceback.print_exc()
            self.iface.messageBar().pushMessage("QOLS Error", f"Error calculating surface: {str(e)}", level=MSG_CRITICAL)

    def execute_approach_surface(self, params):
        """Execute the approach surface calculation script with parameters"""
        script_path = os.path.join(self.plugin_dir, 'scripts', 'approach-surface-UTM.py')
        self.execute_script(script_path, params)

    def execute_conical_surface(self, params):
        """Execute the conical surface calculation script with parameters"""
        script_path = os.path.join(self.plugin_dir, 'scripts', 'conical.py')
        self.execute_script(script_path, params)

    def execute_inner_horizontal_surface(self, params):
        """Execute the inner horizontal surface calculation script with parameters"""
        script_path = os.path.join(self.plugin_dir, 'scripts', 'inner-horizontal-racetrack.py')
        self.execute_script(script_path, params)

    def execute_ofz_surface(self, params):
        """Execute the OFZ surface calculation script with parameters"""
        script_path = os.path.join(self.plugin_dir, 'scripts', 'OFZ_UTM.py')
        self.execute_script(script_path, params)

    def execute_outer_horizontal_surface(self, params):
        """Execute the outer horizontal surface calculation script with parameters"""
        script_path = os.path.join(self.plugin_dir, 'scripts', 'outer-horizontal.py')
        self.execute_script(script_path, params)

    def execute_takeoff_surface(self, params):
        """Execute the takeoff surface calculation script with parameters"""
        script_path = os.path.join(self.plugin_dir, 'scripts', 'take-off-surface_UTM.py')
        self.execute_script(script_path, params)

    def execute_transitional_surface(self, params):
        """Execute the transitional surface calculation script with parameters"""
        script_path = os.path.join(self.plugin_dir, 'scripts', 'TransitionalSurface_UTM.py')
        self.execute_script(script_path, params)

    def execute_combined_inner_conical_surface(self, params):
        """Execute both Inner Horizontal and Conical surfaces sequentially using specific parameters for each"""
        try:
            print("QOLS: Executing combined Inner Horizontal & Conical surfaces")
            
            # Extraer parÃ¡metros especÃ­ficos de cada superficie
            specific_params = params.get('specific_params', {})
            
            if specific_params.get('combined_execution', False):
                # Usar parÃ¡metros especÃ­ficos separados
                inner_params = specific_params.get('inner_horizontal', {})
                conical_params = specific_params.get('conical', {})
                print(f"QOLS DEBUG: Using separate parameters - Inner: {inner_params.keys()}, Conical: {conical_params.keys()}")
            else:
                # Fallback: usar los mismos parÃ¡metros para ambos (compatibilidad)
                inner_params = specific_params
                conical_params = specific_params
                print("QOLS DEBUG: Using shared parameters for both surfaces (fallback mode)")
            
            # Preparar parÃ¡metros completos para Inner Horizontal
            inner_full_params = params.copy()
            inner_full_params['specific_params'] = inner_params
            
            # Execute Inner Horizontal surface first (workflow requirement)
            print(f"QOLS: Step 1/2 - Executing Inner Horizontal surface with radius={inner_params.get('radius')}m, height={inner_params.get('height')}m")
            inner_script_path = os.path.join(self.plugin_dir, 'scripts', 'inner-horizontal-racetrack.py')
            self.execute_script(inner_script_path, inner_full_params)
            
            # Preparar parÃ¡metros completos para Conical
            conical_full_params = params.copy()
            conical_full_params['specific_params'] = conical_params
            
            # Execute Conical surface second (depends on Inner Horizontal)
            print(f"QOLS: Step 2/2 - Executing Conical surface with radius={conical_params.get('radius')}m, height={conical_params.get('height')}m, slope={conical_params.get('slope', 5.0)}%")
            conical_script_path = os.path.join(self.plugin_dir, 'scripts', 'conical.py')
            self.execute_script(conical_script_path, conical_full_params)
            
            print("QOLS: Combined Inner Horizontal & Conical surfaces execution completed successfully")
            
        except Exception as e:
            print(f"QOLS: Error in combined Inner Horizontal & Conical execution: {e}")
            traceback.print_exc()
            self.iface.messageBar().pushMessage(
                "QOLS Error", 
                f"Combined surface execution error: {str(e)}", 
                level=MSG_CRITICAL
            )
            raise

    # ------------------------------------------------------------------
    # BUG-04 â€” Centralised layer validation (called from execute_script)
    # ------------------------------------------------------------------

    def _validate_layers_for_execution(self, params: dict) -> None:
        """Raise a descriptive exception if *params* contains invalid layers.

        This consolidates the eight layer checks that were previously scattered
        across :meth:`execute_script` so that the validation logic lives in a
        single place (BUG-04).

        Args:
            params: The parameter dict returned by
                    :meth:`~qols_dockwidget.QolsDockWidget.get_parameters`.

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

            # BUG-04: single validation call replaces the 8 inline checks
            self._validate_layers_for_execution(params)

            runway_layer = params['runway_layer']
            threshold_layer = params['threshold_layer']
            use_runway_selected = params.get('use_runway_selected', False)
            use_threshold_selected = params.get('use_threshold_selected', False)

            print(f"QOLS: EXECUTING SCRIPT WITH VALIDATED PARAMETERS:")
            print(f"  Script: {script_path}")
            print(f"  Runway Layer Centerline: '{runway_layer.name()}' ({runway_layer.featureCount()} features)")
            print(f"  Threshold Layer: '{threshold_layer.name()}' ({threshold_layer.featureCount()} features)")
            print(f"  Use Runway Selected: {use_runway_selected}")
            print(f"  Use Threshold Selected: {use_threshold_selected}")

            if not os.path.exists(script_path):
                raise ValueError(f"Script file not found: {script_path}")

            with open(script_path, 'r', encoding='utf-8') as f:
                script_content = f.read()

            print(f"QOLS: Executing script: {script_path}")

            specific_params = params.get('specific_params', {})

            print(f"QOLS DEBUG: About to create exec_namespace")
            print(f"QOLS DEBUG: specific_params before namespace: {specific_params}")

            # BUG-02: Build namespace explicitly with visible priority order.
            # Priority (low â†’ high): QGIS API stubs < params < specific_params.
            # Using .update() instead of double **-unpack makes key collisions
            # visible and prevents silent overwrites.
            exec_namespace: dict = {
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
                # Convenience aliases
                'use_selected_feature': params.get('use_threshold_selected', False),
                'active_rule_set': rule_mgr.get_active_rule_set_name(),
            }
            # params overrides QGIS stubs (runway_layer, threshold_layer, surface_type â€¦)
            exec_namespace.update(params)
            # specific_params overrides params (Z0, ZE, code, widthDep â€¦)
            exec_namespace.update(specific_params)
            # BUG-01: success sentinel â€” scripts should set _script_success = True when
            # they finish successfully.  Existing scripts don't yet set it, so we emit
            # a warning rather than raising to keep backward compatibility.
            exec_namespace['_script_success'] = False

            print(f"QOLS DEBUG: exec_namespace keys related to params: {[k for k in exec_namespace.keys() if k in ['code', 'typeAPP', 'widthDep', 'maxWidthDep', 'Z0', 'ZE', 'ARPH', 'specific_params', 'runway_layer', 'threshold_layer']]}")
            print(f"QOLS DEBUG: exec_namespace['code'] = {exec_namespace.get('code', 'NOT_FOUND')}")
            print(f"QOLS DEBUG: exec_namespace['widthDep'] = {exec_namespace.get('widthDep', 'NOT_FOUND')}")

            # Execute the script
            exec(script_content, exec_namespace)

            # BUG-01: warn if script did not signal successful completion
            if not exec_namespace.get('_script_success', False):
                print(f"QOLS: Warning â€” script did not set _script_success=True: {script_path}")

            print(f"QOLS: Script executed successfully: {script_path}")

        except Exception as e:
            print(f"QOLS: Error executing script {script_path}: {e}")
            traceback.print_exc()
            self.iface.messageBar().pushMessage("QOLS Error", f"Script execution error: {str(e)}", level=MSG_CRITICAL)
            raise

