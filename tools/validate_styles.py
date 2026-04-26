"""Validate all photographer style definitions before a QA pass.

Checks each .py file in data/styles/ for:
- Required top-level exports: STYLE_NAME, STYLE_ID, STYLE_DESCRIPTION,
  PROMPT_STUDIO_SYSTEM, TRANSFORM_SYSTEM, INTENSITY_MODIFIERS
- Multi-variant schema: TRANSFORM_VARIANTS (dict), VARIANT_LIST (list derived from it)
- Intensity keys: exactly subtle / moderate / full / extreme
- Em-dash presence in any string (violates Jeremie's writing style rule)
- STYLE_ID matches the filename stem

Run from the pack root:
  python tools/validate_styles.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_HERE = Path(__file__).parent
_STYLES_DIR = _HERE.parent / "data" / "styles"

REQUIRED_SINGLE = [
    "STYLE_NAME", "STYLE_ID", "STYLE_DESCRIPTION",
    "PROMPT_STUDIO_SYSTEM", "TRANSFORM_SYSTEM", "INTENSITY_MODIFIERS",
]
REQUIRED_INTENSITIES = {"subtle", "moderate", "full", "extreme"}
EM_DASH = "—"  # em dash character — violates style rule


def _load_module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _check_em_dashes(mod) -> list[str]:
    """Return list of attribute names that contain em dashes in their string values."""
    hits = []
    for name in dir(mod):
        if name.startswith("_"):
            continue
        val = getattr(mod, name)
        if isinstance(val, str) and EM_DASH in val:
            hits.append(name)
        elif isinstance(val, dict):
            for k, v in val.items():
                if isinstance(v, str) and EM_DASH in v:
                    hits.append(f"{name}[{k!r}]")
                if isinstance(k, str) and EM_DASH in k:
                    hits.append(f"{name} key {k!r}")
    return hits


def validate_one(path: Path) -> dict:
    """Return a report dict for one style file."""
    report = {
        "file": path.name,
        "errors": [],
        "warnings": [],
        "variants": 0,
        "dropdown_entries": 0,
    }

    try:
        mod = _load_module(path)
    except Exception as e:
        report["errors"].append(f"import failed: {e}")
        return report

    # Required single exports
    for key in REQUIRED_SINGLE:
        if not hasattr(mod, key):
            report["errors"].append(f"missing export: {key}")

    # STYLE_ID matches filename
    expected_id = path.stem
    actual_id = getattr(mod, "STYLE_ID", None)
    if actual_id is not None and actual_id != expected_id:
        report["errors"].append(f"STYLE_ID mismatch: file stem is {expected_id!r}, export is {actual_id!r}")

    # Intensity keys exactly match the expected set
    intensity = getattr(mod, "INTENSITY_MODIFIERS", None)
    if isinstance(intensity, dict):
        keys = set(intensity.keys())
        missing = REQUIRED_INTENSITIES - keys
        extra = keys - REQUIRED_INTENSITIES
        if missing:
            report["errors"].append(f"INTENSITY_MODIFIERS missing keys: {sorted(missing)}")
        if extra:
            report["errors"].append(f"INTENSITY_MODIFIERS extra keys: {sorted(extra)}")
        for k, v in intensity.items():
            if not isinstance(v, str) or not v.strip():
                report["errors"].append(f"INTENSITY_MODIFIERS[{k!r}] must be a non-empty string")
    elif intensity is not None:
        report["errors"].append(f"INTENSITY_MODIFIERS must be a dict, got {type(intensity).__name__}")

    # Multi-variant schema
    variants = getattr(mod, "TRANSFORM_VARIANTS", None)
    if variants is not None:
        if not isinstance(variants, dict):
            report["errors"].append(f"TRANSFORM_VARIANTS must be a dict, got {type(variants).__name__}")
        else:
            report["variants"] = len(variants)
            if len(variants) == 0:
                report["errors"].append("TRANSFORM_VARIANTS is empty")
            for vname, vbody in variants.items():
                if not isinstance(vname, str) or not vname.strip():
                    report["errors"].append(f"TRANSFORM_VARIANTS has non-string or empty key: {vname!r}")
                if not isinstance(vbody, str) or not vbody.strip():
                    report["errors"].append(f"TRANSFORM_VARIANTS[{vname!r}] must be a non-empty string")
            # VARIANT_LIST should match
            vlist = getattr(mod, "VARIANT_LIST", None)
            if vlist is not None and list(vlist) != list(variants.keys()):
                report["warnings"].append("VARIANT_LIST does not match TRANSFORM_VARIANTS key order")

    # Count dropdown entries for this style: 4 per variant (intensity tiers applied at runtime),
    # or 1 if single-variant legacy.
    n_variants = max(report["variants"], 1)
    report["dropdown_entries"] = n_variants

    # Em-dash check
    em_hits = _check_em_dashes(mod)
    if em_hits:
        report["warnings"].append(f"em-dash found in: {em_hits}")

    return report


def main() -> int:
    files = sorted(p for p in _STYLES_DIR.glob("*.py") if p.name != "__init__.py")
    if not files:
        print(f"no style files found in {_STYLES_DIR}")
        return 1

    print(f"Validating {len(files)} style files in {_STYLES_DIR}\n")

    total_errors = 0
    total_warnings = 0
    total_entries = 0
    multi_variant = 0
    single_variant = 0

    for path in files:
        r = validate_one(path)
        status = "OK" if not r["errors"] else "FAIL"
        variants_note = f"{r['variants']} variants" if r["variants"] else "single-variant (legacy)"
        print(f"[{status:4}] {r['file']:34} {variants_note}")
        for err in r["errors"]:
            print(f"         ERROR: {err}")
        for warn in r["warnings"]:
            print(f"         WARN:  {warn}")
        total_errors += len(r["errors"])
        total_warnings += len(r["warnings"])
        if r["variants"] >= 2:
            multi_variant += 1
            total_entries += r["variants"]
        else:
            single_variant += 1
            total_entries += 1

    print()
    print(f"Totals: {multi_variant} multi-variant × avg {total_entries/max(1,multi_variant):.1f} + "
          f"{single_variant} single-variant = {total_entries} distinct variant bodies")
    print(f"        {total_errors} errors, {total_warnings} warnings across {len(files)} files")
    return 0 if total_errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
