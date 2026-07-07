"""Shared helpers for the SharedProcessors pytest suite.

Importing this module puts `autopkglib` and the `SharedProcessors/` directory on
`sys.path`, the same way `test_processors_load.sh` runs the processors:
`autopkglib` is sourced from a sibling `../autopkg/Code` checkout (local dev), an
in-repo `autopkg/Code` (CI checkout via setup-autopkg), or an already-importable
install. `conftest.py` imports this module so the path setup runs before any test
module imports a processor.
"""

import importlib
import inspect
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROCESSORS_DIR = os.path.join(REPO_ROOT, "SharedProcessors")


def _ensure_autopkglib_importable():
    """Add an autopkglib source dir to sys.path if it is not already importable."""
    try:
        import autopkglib  # noqa: F401

        return
    except ImportError:
        pass
    candidates = [
        os.path.join(REPO_ROOT, "..", "autopkg", "Code"),  # sibling checkout (dev)
        os.path.join(REPO_ROOT, "autopkg", "Code"),  # in-repo checkout (CI)
        "/Library/AutoPkg",
    ]
    for path in candidates:
        if os.path.isdir(os.path.join(path, "autopkglib")):
            sys.path.insert(0, os.path.abspath(path))
            return


_ensure_autopkglib_importable()
if PROCESSORS_DIR not in sys.path:
    sys.path.insert(0, PROCESSORS_DIR)


def all_processor_module_names():
    """Return the module stem of every processor in SharedProcessors/.

    Skips underscore-prefixed files (e.g. the `_template.py` scaffold).
    """
    names = []
    for entry in sorted(os.listdir(PROCESSORS_DIR)):
        if entry.endswith(".py") and not entry.startswith("_"):
            names.append(entry[:-3])
    return names


def import_processor_module(name):
    """Import a SharedProcessors module by its file stem and return the module."""
    return importlib.import_module(name)


def processor_classes(module):
    """Return the classes exported by `module` that subclass autopkglib.Processor."""
    from autopkglib import Processor

    exported = getattr(module, "__all__", None) or [
        n for n in dir(module) if not n.startswith("_")
    ]
    classes = []
    for attr_name in exported:
        obj = getattr(module, attr_name, None)
        if inspect.isclass(obj) and issubclass(obj, Processor) and obj is not Processor:
            classes.append(obj)
    return classes
