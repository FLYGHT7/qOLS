import os
import json
from typing import Dict, Optional, Any

from qgis.PyQt.QtCore import QSettings

# Normalized classification keys expected from UI
CLASS_KEYS = [
    'Non-instrument',
    'Non-precision approach',
    'Precision Approach CAT I',
    'Precision Approach CAT II or III',
]


class RuleManager:
    """Loads JSON rule sets from the qols/rules folder and provides lookups.

    Persistence: stores the active rule set name in QSettings under 'QOLS/ActiveRuleSet'.
    """

    def __init__(self):
        self._rules_loaded = False
        self._registry: Dict[str, Dict[str, Any]] = {}
        self._rules_dir = os.path.join(os.path.dirname(__file__), 'rules')

    def load(self):
        if self._rules_loaded:
            return
        self._registry.clear()
        if not os.path.isdir(self._rules_dir):
            self._rules_loaded = True
            return

        for fname in os.listdir(self._rules_dir):
            if not fname.lower().endswith('.json'):
                continue
            fpath = os.path.join(self._rules_dir, fname)
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                name = data.get('name') or os.path.splitext(fname)[0]
                # Normalize classification maps if present
                self._normalize_classification_maps(data)
                self._registry[name] = data
            except Exception:
                # Ignore broken rule files; they will be skipped
                continue

        self._rules_loaded = True

    def reload(self):
        """Force a reload of rule sets from disk."""
        self._rules_loaded = False
        self.load()

    def _normalize_classification_maps(self, data: Dict[str, Any]):
        # Ensure classification keys match UI texts when present
        def normalize_map(m: Dict[str, Any]) -> Dict[str, Any]:
            if not isinstance(m, dict):
                return {}
            result = {}
            for key, value in m.items():
                # Attempt to match by case-insensitive containment
                k_lower = str(key).strip().lower()
                mapped = None
                for ck in CLASS_KEYS:
                    if k_lower == ck.lower():
                        mapped = ck
                        break
                    # simple aliasing
                    if 'non-instrument' in k_lower and ck == 'Non-instrument':
                        mapped = ck
                        break
                    if 'non-precision' in k_lower and ck == 'Non-precision approach':
                        mapped = ck
                        break
                    if 'cat i' in k_lower and ck == 'Precision Approach CAT I':
                        mapped = ck
                        break
                    if ('cat ii' in k_lower or 'cat iii' in k_lower) and ck == 'Precision Approach CAT II or III':
                        mapped = ck
                        break
                result[mapped or key] = value
            return result

        # Inner Horizontal
        ih = data.get('inner_horizontal')
        if isinstance(ih, dict) and 'radius_m' in ih:
            ih['radius_m'] = normalize_map(ih.get('radius_m', {}))

        # Conical
        con = data.get('conical')
        if isinstance(con, dict) and 'height_m' in con:
            con['height_m'] = normalize_map(con.get('height_m', {}))

    def list_rule_sets(self) -> Dict[str, Dict[str, Any]]:
        self.load()
        return dict(self._registry)

    def get_active_rule_set_name(self) -> Optional[str]:
        try:
            settings = QSettings()
            name = settings.value('QOLS/ActiveRuleSet', type=str)
            if name and name in self._registry:
                return name
            # If not set but only one rule set exists, select it implicitly
            if not name and len(self._registry) == 1:
                return next(iter(self._registry.keys()))
            return name
        except Exception:
            return None

    def set_active_rule_set_name(self, name: Optional[str]):
        settings = QSettings()
        if name and name in self._registry:
            settings.setValue('QOLS/ActiveRuleSet', name)
        else:
            settings.remove('QOLS/ActiveRuleSet')

    def _get_active(self) -> Optional[Dict[str, Any]]:
        self.load()
        name = self.get_active_rule_set_name()
        if name:
            return self._registry.get(name)
        return None

    def get_inner_horizontal_defaults(self, rwy_classification: str, code: int) -> Optional[Dict[str, float]]:
        rs = self._get_active()
        if not rs:
            return None
        ih = rs.get('inner_horizontal') or {}
        # Height may be scalar; radius is a classification->code map
        height = ih.get('height_m')
        try:
            height = float(height) if height is not None else None
        except Exception:
            height = None
        radius_map = ih.get('radius_m') or {}
        class_map = radius_map.get(rwy_classification) or {}
        radius = class_map.get(str(int(code))) or class_map.get(int(code))
        try:
            radius = float(radius) if radius is not None else None
        except Exception:
            radius = None
        if height is None and radius is None:
            return None
        result: Dict[str, float] = {}
        if height is not None:
            result['height_m'] = height
        if radius is not None:
            result['radius_m'] = radius
        return result if result else None

    def get_conical_defaults(self, rwy_classification: str, code: int) -> Optional[Dict[str, float]]:
        rs = self._get_active()
        if not rs:
            return None
        con = rs.get('conical') or {}
        # Height may be classification map; slope_pct may be scalar; radius may be default_radius_m
        height_map = con.get('height_m') or {}
        class_map = height_map.get(rwy_classification) or {}
        height = class_map.get(str(int(code))) or class_map.get(int(code))
        try:
            height = float(height) if height is not None else None
        except Exception:
            height = None
        slope_pct = con.get('slope_pct')
        try:
            slope_pct = float(slope_pct) if slope_pct is not None else None
        except Exception:
            slope_pct = None
        # If radius explicitly provided, use it (rare); else leave for UI to compute
        radius = con.get('default_radius_m')
        try:
            radius = float(radius) if radius is not None else None
        except Exception:
            radius = None
        if height is None and slope_pct is None and radius is None:
            return None
        result: Dict[str, float] = {}
        if height is not None:
            result['height_m'] = height
        if slope_pct is not None:
            result['slope_pct'] = slope_pct
        if radius is not None:
            result['radius_m'] = radius
        return result if result else None


# Singleton instance
_RM = RuleManager()


def list_rule_sets() -> Dict[str, Dict[str, Any]]:
    return _RM.list_rule_sets()


def get_active_rule_set_name() -> Optional[str]:
    return _RM.get_active_rule_set_name()


def set_active_rule_set_name(name: Optional[str]):
    _RM.set_active_rule_set_name(name)


def get_inner_horizontal_defaults(rwy_classification: str, code: int) -> Optional[Dict[str, float]]:
    return _RM.get_inner_horizontal_defaults(rwy_classification, code)


def get_conical_defaults(rwy_classification: str, code: int) -> Optional[Dict[str, float]]:
    return _RM.get_conical_defaults(rwy_classification, code)


def reload_rules():
    _RM.reload()
