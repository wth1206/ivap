"""Register the vendored ECE-YOLO modules under Ultralytics' namespace.

The checkpoint pickle refers to:

    ultralytics.nn.Addmodules.ESPMStem.ESPMStem
    ultralytics.nn.Addmodules.RepNCSPELAN4.RepNCSPELAN4_low
    ultralytics.nn.Addmodules.DynamicHead.DynamicHead

Only these three modules are loaded; the upstream ``Addmodules/__init__.py``
imports dozens of unrelated modules and would pull in missing dependencies.
"""

import sys
import types
from pathlib import Path
from typing import Dict, Optional, Type

from app.algorithms.ece_yolo.mmcv_shim import install_mmcv_shim

VENDOR_DIR = Path(__file__).resolve().parent / "vendor"
_PACKAGE = "ultralytics.nn.Addmodules"
_MODULE_FILES = ("ESPMStem", "RepNCSPELAN4", "DynamicHead")


def _load_module(name: str, path: Path) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__file__ = str(path)
    module.__package__ = _PACKAGE
    sys.modules[name] = module
    source = path.read_text(encoding="utf-8")
    exec(compile(source, str(path), "exec"), module.__dict__)  # noqa: S102
    return module


def register_ece_modules(vendor_dir: Optional[Path] = None) -> Dict[str, Type]:
    """Load the three custom modules and patch ``ultralytics.nn.tasks``.

    Must be called after :func:`install_mmcv_shim`.
    """
    install_mmcv_shim()

    import ultralytics.nn as ultralytics_nn
    import ultralytics.nn.tasks as tasks

    root = Path(vendor_dir) if vendor_dir else VENDOR_DIR
    package = sys.modules.get(_PACKAGE)
    if package is None:
        package = types.ModuleType(_PACKAGE)
        package.__path__ = [str(root)]
        sys.modules[_PACKAGE] = package
        ultralytics_nn.Addmodules = package

    classes: Dict[str, Type] = {}
    for stem in _MODULE_FILES:
        module = sys.modules.get(f"{_PACKAGE}.{stem}")
        if module is None:
            module = _load_module(f"{_PACKAGE}.{stem}", root / f"{stem}.py")
            setattr(package, stem, module)

        if stem == "ESPMStem":
            classes["ESPMStem"] = module.ESPMStem
        elif stem == "RepNCSPELAN4":
            classes["RepNCSPELAN4_low"] = module.RepNCSPELAN4_low
            classes["RepNCSPELAN4_high"] = module.RepNCSPELAN4_high
        elif stem == "DynamicHead":
            classes["DynamicHead"] = module.DynamicHead

    # parse_model() resolves class names from the tasks module globals.
    for name, cls in classes.items():
        setattr(tasks, name, cls)

    return classes
