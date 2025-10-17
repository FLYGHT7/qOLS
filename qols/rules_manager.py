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

        # Approach (width, offsets, divergences, sections)
        app = data.get('approach')
        if isinstance(app, dict):
            for key in ['width_m', 'threshold_offset_m', 'divergence_pct', 'L1_m', 'slope1_pct', 'L2_m', 'slope2_pct', 'LH_m']:
                if key in app:
                    app[key] = normalize_map(app.get(key, {}))

        # Transitional (slope)
        trn = data.get('transitional')
        if isinstance(trn, dict) and 'slope_pct' in trn:
            trn['slope_pct'] = normalize_map(trn.get('slope_pct', {}))

        # OFZ (width and inner side slope toward ZIH)
        ofz = data.get('ofz')
        if isinstance(ofz, dict):
            if 'width_m' in ofz:
                ofz['width_m'] = normalize_map(ofz.get('width_m', {}))
            if 'ih_slope_pct' in ofz:
                ofz['ih_slope_pct'] = normalize_map(ofz.get('ih_slope_pct', {}))

        # Inner Approach
        ia = data.get('inner_approach')
        if isinstance(ia, dict):
            for key in ['width_m', 'distance_from_threshold_m', 'length_m', 'slope_pct']:
                if key in ia:
                    ia[key] = normalize_map(ia.get(key, {}))
		
        # Balked Landing
        bl = data.get('balked_landing')
        if isinstance(bl, dict):
            for key in ['width_m', 'distance_from_threshold_m', 'divergence_pct', 'slope_pct']:
                if key in bl:
                    bl[key] = normalize_map(bl.get(key, {}))

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

    def _class_code_lookup(self, mapping: Dict[str, Any], rwy_classification: str, code: int) -> Optional[float]:
        try:
            class_map = mapping.get(rwy_classification) or {}
            val = class_map.get(str(int(code))) or class_map.get(int(code))
            return float(val) if val is not None else None
        except Exception:
            return None

    def get_approach_defaults(self, rwy_classification: str, code: int) -> Optional[Dict[str, float]]:
        rs = self._get_active()
        if not rs:
            return None
        app = rs.get('approach') or {}
        if not isinstance(app, dict):
            return None
        keys = ['width_m', 'threshold_offset_m', 'divergence_pct', 'L1_m', 'slope1_pct', 'L2_m', 'slope2_pct', 'LH_m']
        out: Dict[str, float] = {}
        for k in keys:
            m = app.get(k)
            if isinstance(m, dict):
                v = self._class_code_lookup(m, rwy_classification, code)
                if v is not None:
                    # Convert percentages to ratio for divergence and slopes where applicable
                    if k in ['divergence_pct', 'slope1_pct', 'slope2_pct']:
                        out[k.replace('_pct', '_ratio')] = v / 100.0
                    else:
                        out[k] = v
        return out if out else None

    def get_transitional_defaults(self, rwy_classification: str, code: int) -> Optional[Dict[str, float]]:
        rs = self._get_active()
        if not rs:
            return None
        trn = rs.get('transitional') or {}
        if not isinstance(trn, dict):
            return None
        slope_pct_map = trn.get('slope_pct') or {}
        slope = self._class_code_lookup(slope_pct_map, rwy_classification, code)
        if slope is None:
            return None
        return {'slope_ratio': slope / 100.0, 'slope_pct': slope}

    def get_ofz_defaults(self, rwy_classification: str, code: int) -> Optional[Dict[str, float]]:
        rs = self._get_active()
        if not rs:
            return None
        ofz = rs.get('ofz') or {}
        if not isinstance(ofz, dict):
            return None
        width = self._class_code_lookup(ofz.get('width_m', {}), rwy_classification, code)
        ihs = self._class_code_lookup(ofz.get('ih_slope_pct', {}), rwy_classification, code)
        out: Dict[str, float] = {}
        if width is not None:
            out['width_m'] = width
        if ihs is not None:
            out['ih_slope_ratio'] = ihs / 100.0
            out['ih_slope_pct'] = ihs
        return out if out else None

    def get_inner_approach_defaults(self, rwy_classification: str, code: int) -> Optional[Dict[str, float]]:
        rs = self._get_active()
        if not rs:
            return None
        ia = rs.get('inner_approach') or {}
        if not isinstance(ia, dict):
            return None
        width = self._class_code_lookup(ia.get('width_m', {}), rwy_classification, code)
        dist = self._class_code_lookup(ia.get('distance_from_threshold_m', {}), rwy_classification, code)
        length = self._class_code_lookup(ia.get('length_m', {}), rwy_classification, code)
        slope = self._class_code_lookup(ia.get('slope_pct', {}), rwy_classification, code)
        out: Dict[str, float] = {}
        if width is not None:
            out['width_m'] = width
        if dist is not None:
            out['distance_from_threshold_m'] = dist
        if length is not None:
            out['length_m'] = length
        if slope is not None:
            out['slope_ratio'] = slope / 100.0
            out['slope_pct'] = slope
        return out if out else None

    def get_balked_landing_defaults(self, rwy_classification: str, code: int) -> Optional[Dict[str, float]]:
        rs = self._get_active()
        if not rs:
            return None
        bl = rs.get('balked_landing') or {}
        if not isinstance(bl, dict):
            return None
        width = self._class_code_lookup(bl.get('width_m', {}), rwy_classification, code)
        dist = self._class_code_lookup(bl.get('distance_from_threshold_m', {}), rwy_classification, code)
        div = self._class_code_lookup(bl.get('divergence_pct', {}), rwy_classification, code)
        slope = self._class_code_lookup(bl.get('slope_pct', {}), rwy_classification, code)
        out: Dict[str, float] = {}
        if width is not None:
            out['width_m'] = width
        if dist is not None:
            out['distance_from_threshold_m'] = dist
        if div is not None:
            out['divergence_ratio'] = div / 100.0
            out['divergence_pct'] = div
        if slope is not None:
            out['slope_ratio'] = slope / 100.0
            out['slope_pct'] = slope
        return out if out else None


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


def get_approach_defaults(rwy_classification: str, code: int) -> Optional[Dict[str, float]]:
    return _RM.get_approach_defaults(rwy_classification, code)


def get_transitional_defaults(rwy_classification: str, code: int) -> Optional[Dict[str, float]]:
    return _RM.get_transitional_defaults(rwy_classification, code)


def get_ofz_defaults(rwy_classification: str, code: int) -> Optional[Dict[str, float]]:
    return _RM.get_ofz_defaults(rwy_classification, code)


def get_inner_approach_defaults(rwy_classification: str, code: int) -> Optional[Dict[str, float]]:
    return _RM.get_inner_approach_defaults(rwy_classification, code)


def get_balked_landing_defaults(rwy_classification: str, code: int) -> Optional[Dict[str, float]]:
    return _RM.get_balked_landing_defaults(rwy_classification, code)
