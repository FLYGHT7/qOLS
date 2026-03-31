"""Rules sub-package: rule set loading and parameter lookup.

This package exposes the full public API of *manager* at the package
level so that existing `from qols.rules.manager import ...` call-sites
continue to work, and ``from .rules import manager as rule_mgr`` gives
callers transparent access to the module-level helper functions.
"""

from .manager import (
    RuleManager,
    list_rule_sets,
    get_active_rule_set_name,
    set_active_rule_set_name,
    get_inner_horizontal_defaults,
    get_conical_defaults,
    reload_rules,
    get_approach_defaults,
    get_transitional_defaults,
    get_ofz_defaults,
    get_inner_approach_defaults,
    get_balked_landing_defaults,
)

__all__ = [
    "RuleManager",
    "list_rule_sets",
    "get_active_rule_set_name",
    "set_active_rule_set_name",
    "get_inner_horizontal_defaults",
    "get_conical_defaults",
    "reload_rules",
    "get_approach_defaults",
    "get_transitional_defaults",
    "get_ofz_defaults",
    "get_inner_approach_defaults",
    "get_balked_landing_defaults",
]
