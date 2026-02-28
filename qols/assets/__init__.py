"""Assets sub-package: icon management and generation utilities."""

__all__ = ["IconManager", "apply_custom_icons_to_combos", "generate_icons"]


def __getattr__(name):  # PEP 562 lazy package-level import
    if name in ("IconManager", "apply_custom_icons_to_combos"):
        from .icon_manager import QolsIconManager as IconManager, apply_custom_icons_to_combos
        globals()[name] = locals()[name]
        return globals()[name]
    if name == "generate_icons":
        from .generate_icons import generate_icons
        globals()["generate_icons"] = generate_icons
        return generate_icons
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
