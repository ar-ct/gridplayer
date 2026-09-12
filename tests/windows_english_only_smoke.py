"""Windows-only checks for the pruned English-only portable tree."""

import sys
from pathlib import Path


def main() -> int:
    if sys.platform != "win32":
        raise RuntimeError("This smoke test must run on Windows")
    if len(sys.argv) != 2:
        raise RuntimeError("Usage: windows_english_only_smoke.py <GridPlayer directory>")

    app_dir = Path(sys.argv[1]).resolve()
    if not (app_dir / "GridPlayer.exe").is_file():
        raise FileNotFoundError(app_dir / "GridPlayer.exe")

    qt_translations = app_dir / "_internal" / "PyQt5" / "Qt5" / "translations"
    if qt_translations.exists():
        raise AssertionError(f"Qt translation directory was not pruned: {qt_translations}")

    pycountry_dir = app_dir / "_internal" / "pycountry"
    locales_dir = pycountry_dir / "locales"
    if locales_dir.exists():
        raise AssertionError(f"pycountry locale directory was not pruned: {locales_dir}")

    required_databases = {
        "iso3166-1.json",
        "iso639-3.json",
    }
    database_dir = pycountry_dir / "databases"
    missing_databases = [
        name for name in required_databases if not (database_dir / name).is_file()
    ]
    if missing_databases:
        raise AssertionError(
            f"Required pycountry core databases are missing: {missing_databases}"
        )

    qm_files = list(app_dir.rglob("*.qm"))
    if qm_files:
        raise AssertionError(f"Unexpected Qt translation files remain: {qm_files[:5]}")

    print("English-only package contains no standalone Qt/pycountry locale translations")
    print("Required pycountry core databases remain present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
