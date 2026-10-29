"""Keep the bundled Qt DLL directories ahead of system installations."""
import os
import sys

_qt_dll_handles = []
if getattr(sys, "frozen", False) and hasattr(os, "add_dll_directory"):
    for package in ("PySide6", "shiboken6"):
        directory = os.path.join(sys._MEIPASS, package)
        if os.path.isdir(directory):
            _qt_dll_handles.append(os.add_dll_directory(directory))

if "--verify-build" in sys.argv:
    from pathlib import Path
    import traceback
    report = Path(sys.executable).with_suffix(".verify.log")
    try:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PySide6.QtWidgets import QApplication, QDoubleSpinBox
        from PySide6.QtNetwork import QLocalServer
        from PySide6.QtGui import QIcon, QImage, QFontDatabase
        from core.app_identity import APP_NAME, APP_ICON_PATH
        from core.app_state import get_external_path
        from core.resource_cache import seed_runtime_resources, valid_metadata
        import tempfile
        assert Path(sys.executable).stem == APP_NAME, "Executable and bundled identity differ"
        app = QApplication([])
        app.setApplicationName(APP_NAME)
        assert not QIcon(str(Path(sys._MEIPASS) / APP_ICON_PATH)).isNull(), "Bundled icon missing"
        for name in ("Random", "Duelist", "Initiator", "Controller", "Sentinel"):
            icon_path = Path(sys._MEIPASS) / "assets" / "agents" / f"{name}.png"
            assert not QIcon(str(icon_path)).isNull(), f"Bundled agent option icon missing: {name}"
        assert Path(get_external_path("loadouts")) == Path(sys.executable).parent / "loadouts"
        bundle = Path(sys._MEIPASS)
        images = list((bundle / "assets").rglob("*.png"))
        for path in images:
            assert not QImage(str(path)).isNull(), f"Invalid bundled image: {path.name}"
        for path in (bundle / "assets" / "fonts").iterdir():
            if path.suffix.lower() in (".ttf", ".otf"):
                assert QFontDatabase.addApplicationFont(str(path)) >= 0, f"Invalid font: {path.name}"
        import qtawesome as qta
        assert not qta.icon("fa6s.xmark").isNull(), "Font Awesome assets missing"
        with tempfile.TemporaryDirectory(prefix=".verify-", dir=Path(sys.executable).parent) as seed_dir:
            assert Path(seed_dir).resolve().parent == Path(sys.executable).resolve().parent
            copied = seed_runtime_resources(base_path=seed_dir)
            assert copied > 0, "Startup cache was not seeded"
            for name in ("agent", "season", "skin", "map", "buddy"):
                assert valid_metadata(Path(seed_dir) / "core" / f"{name}_uuids.json"), f"Missing {name} metadata"
            assert list((Path(seed_dir) / "assets" / "maps").glob("*.png")), "Map images missing"
            assert list((Path(seed_dir) / "assets" / "ranks").glob("*.png")), "Rank images missing"
            assert seed_runtime_resources(base_path=seed_dir) == 0, "Valid caches were replaced"
        field = QDoubleSpinBox()
        field.setDecimals(2)
        field.setValue(6.66)
        assert field.value() == 6.66
        report.write_text(f"PASS: {APP_NAME}: {len(images)} bundled images, fonts, five metadata files, first-run cache seeding, persistent loadout path, identity and Qt load.\n", encoding="utf-8")
    except Exception:
        report.write_text(traceback.format_exc(), encoding="utf-8")
        raise SystemExit(1)
    raise SystemExit(0)
