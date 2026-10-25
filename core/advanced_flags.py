"""Pure-Python registry and helper functions for schema-driven opt-in advanced flags.

Definitions now come from flags.toml via flag_registry.py.
Qt-free module.
"""

from typing import Any

from .flag_registry import REGISTRY  # alias for compat
from .flag_registry import FlagDef as AdvancedFlagDef
from .models import CommandPlan, ValidationResult
from .validation import (
    clean_date_range,
    normalize_extensions_csv,
    normalize_list_csv,
)
from .validation import (
    validate_date_range as _validate_date_range,
)

# Backwards-compatible dict: advanced defs only, keyed by tab.
ADVANCED_FLAGS: dict[str, tuple[AdvancedFlagDef, ...]] = {
    tab: REGISTRY.advanced_defs(tab) for tab in REGISTRY.tabs
}


def advanced_flag_args(def_: AdvancedFlagDef, value: Any) -> list[str]:
    """Generates CLI argument list for an enabled advanced flag definition and value."""
    flag = def_.flag

    if def_.kind == "bool":
        if bool(value):
            return [f"--{flag}"]
        return [f"--{flag}=false"]

    if value is None:
        return []

    if def_.kind in ("text", "enum"):
        text = str(value).strip()
        if not text:
            return []
        return [f"--{flag}={text}"]

    if def_.kind == "int":
        return [f"--{flag}={int(value)}"]

    if def_.kind == "duration_minutes":
        return [f"--{flag}={int(value)}m"]

    if def_.kind == "date_range":
        cleaned = clean_date_range(str(value))
        if not cleaned:
            return []
        return [f"--{flag}={cleaned}"]

    if def_.kind == "extensions":
        normalized = normalize_extensions_csv(str(value))
        if not normalized:
            return []
        return [f"--{flag}={normalized}"]

    if def_.kind == "csv_repeat":
        items = normalize_list_csv(str(value))
        return [f"--{flag}={item}" for item in items if item]

    if def_.kind == "lines_repeat":
        args = []
        for line in str(value).splitlines():
            line = line.strip()
            if line:
                args.append(f"--{flag}={line}")
        return args

    return []


def apply_advanced_flags_to_plan(
    plan: CommandPlan,
    emitter: Any,
    tab_key: str,
    advanced_state: dict,
):
    """Applies active (enabled) advanced flags to a CommandPlan and FlagEmitter."""
    from .cli_schema import flag_allowed_for_tab

    if not isinstance(advanced_state, dict):
        return

    for def_ in ADVANCED_FLAGS.get(tab_key, ()):
        entry = advanced_state.get(def_.key)
        if not isinstance(entry, dict) or not entry.get("enabled"):
            continue

        value = entry.get("value", def_.default)

        # from-dry-run is emitted by the dry-run button when plan.dry_run is set
        if def_.key == "from-dry-run" and getattr(plan, "dry_run", False):
            continue

        # Secret advanced flags set env var instead of argv
        if def_.secret_env:
            if value:
                plan.env[def_.secret_env] = str(value).strip()
            continue

        args = advanced_flag_args(def_, value)
        if not args:
            continue

        if not flag_allowed_for_tab(tab_key, def_.flag):
            emitter.errors.append(
                f"Flag '--{def_.flag}' is not allowed for tab '{tab_key}'"
            )
            continue

        for arg in args:
            emitter.add_raw_checked(arg, source="advanced")

        warning = def_.warn_values.get(value)
        if warning:
            plan.warnings.append(warning)


def validate_advanced_state(tab_key: str, advanced_state: dict) -> ValidationResult:
    """Validates enabled advanced flags for a given tab."""
    res = ValidationResult()
    if not isinstance(advanced_state, dict):
        return res

    for def_ in ADVANCED_FLAGS.get(tab_key, ()):
        entry = advanced_state.get(def_.key)
        if not isinstance(entry, dict) or not entry.get("enabled"):
            continue

        value = entry.get("value", def_.default)

        if def_.kind == "date_range":
            text = str(value or "").strip()
            if text:
                ok, err = _validate_date_range(text)
                if not ok:
                    res.errors.append(f"Invalid {def_.label}: {err}")

        elif def_.kind in ("text", "extensions", "csv_repeat", "lines_repeat"):
            text = str(value or "").strip()
            if not text and not def_.allow_empty:
                res.errors.append(f"{def_.label} is enabled but empty.")

        elif def_.kind in ("int", "duration_minutes") and value is not None:
            try:
                n = int(value)
            except (TypeError, ValueError):
                res.errors.append(f"{def_.label} must be a whole number.")
            else:
                if def_.min_val is not None and n < def_.min_val:
                    res.errors.append(f"{def_.label} must be at least {def_.min_val}.")
                if def_.max_val is not None and n > def_.max_val:
                    res.errors.append(f"{def_.label} must be at most {def_.max_val}.")

        if def_.key == "on-errors":
            v = str(value or "").strip().lower()
            if (
                v
                and v not in ("stop", "continue")
                and not (v.isdigit() and int(v) >= 0)
            ):
                res.errors.append(
                    "On errors must be 'stop', 'continue', or a non-negative integer "
                    "(max tolerated errors)."
                )

    return res
