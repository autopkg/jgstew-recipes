"""Contract tests covering every processor in SharedProcessors/.

For each processor module this verifies the AutoPkg processor "contract" that
every concrete SharedProcessor is expected to satisfy: the module imports,
exports a Processor subclass, and that class has a description, well-formed
input_variables / output_variables, is instantiable, and defines main().

This is the broad coverage for all processors. Processors whose only logic lives
in main() (network / filesystem / external-tool side effects) are covered here at
the contract level and integration-tested by the AutoPkg test recipes in
Test-Recipes/. Processors with unit-testable pure functions/methods get dedicated
tests in the other test_*.py files.

A module that fails to import because an optional dependency is not installed in
the current environment (a missing native library such as libcairo, or an
optional pip package) is skipped rather than failed -- strict cross-platform
import coverage is provided by test_processors_load.sh in CI. A genuine code
error (SyntaxError, NameError, ...) is not an ImportError/OSError and still fails.
"""

# pre-commit-skip: processor-conventions
import pytest
from processor_utils import (
    all_processor_module_names,
    import_processor_module,
    processor_classes,
)

PROCESSOR_MODULE_NAMES = all_processor_module_names()

_import_cache = {}


def _import_or_skip(module_name):
    """Import a processor module, or skip if an optional dependency is missing."""
    if module_name not in _import_cache:
        try:
            _import_cache[module_name] = (import_processor_module(module_name), None)
        except (ImportError, OSError) as err:
            _import_cache[module_name] = (None, err)
    module, err = _import_cache[module_name]
    if module is None:
        pytest.skip(f"{module_name}: optional dependency unavailable: {err}")
    return module


def _is_concrete_processor(cls):
    """A concrete processor sets its own `description`; bases/mixins do not."""
    return "description" in vars(cls)


def test_there_are_processors_to_test():
    """Guard against a path/discovery mistake silently testing nothing."""
    assert len(PROCESSOR_MODULE_NAMES) > 50


@pytest.mark.parametrize("module_name", PROCESSOR_MODULE_NAMES)
def test_module_imports(module_name):
    """Every processor module imports (or is skipped for a missing optional dep)."""
    assert _import_or_skip(module_name) is not None


@pytest.mark.parametrize("module_name", PROCESSOR_MODULE_NAMES)
def test_module_exports_processor_subclass(module_name):
    """Every processor module must export at least one Processor subclass."""
    module = _import_or_skip(module_name)
    assert processor_classes(
        module
    ), f"{module_name} exports no autopkglib.Processor subclass"


@pytest.mark.parametrize("module_name", PROCESSOR_MODULE_NAMES)
def test_exported_class_named_in_all(module_name):
    """Exported Processor classes should be listed in __all__ (naming convention)."""
    module = _import_or_skip(module_name)
    exported = getattr(module, "__all__", None)
    if exported is None:
        pytest.skip(f"{module_name} defines no __all__")
    for cls in processor_classes(module):
        assert cls.__name__ in exported


@pytest.mark.parametrize("module_name", PROCESSOR_MODULE_NAMES)
def test_processor_class_contract(module_name):
    """Each exported Processor subclass satisfies the expected shape."""
    module = _import_or_skip(module_name)
    for cls in processor_classes(module):
        # concrete processors must document themselves; base/mixin utilities
        # (e.g. SharedUtilityMethods) are exempt from the description/vars shape
        if _is_concrete_processor(cls):
            assert (
                isinstance(cls.description, str) and cls.description.strip()
            ), f"{cls.__name__}: missing/empty description"
            for attr in ("input_variables", "output_variables"):
                variables = getattr(cls, attr)
                assert isinstance(
                    variables, dict
                ), f"{cls.__name__}.{attr} is not a dict"
                for var_name, spec in variables.items():
                    assert isinstance(
                        spec, dict
                    ), f"{cls.__name__}.{attr}['{var_name}'] is not a dict"

        # applies to every Processor subclass, concrete or base:
        instance = cls({})
        assert instance.env == {}
        assert callable(
            getattr(instance, "main", None)
        ), f"{cls.__name__}: main() is not callable"


@pytest.mark.parametrize("module_name", PROCESSOR_MODULE_NAMES)
def test_static_and_class_methods_are_callable(module_name):
    """Any @staticmethod / @classmethod on a processor resolves and is callable.

    Light coverage of the non-main class methods across all processors (deeper
    behavior is asserted in the dedicated per-processor tests).
    """
    module = _import_or_skip(module_name)
    for cls in processor_classes(module):
        for attr_name, kind in _static_and_class_methods(cls):
            member = getattr(cls, attr_name)
            assert callable(member), f"{cls.__name__}.{attr_name} ({kind}) not callable"


def _static_and_class_methods(cls):
    """Yield (name, kind) for static/class methods defined on cls (not inherited)."""
    for attr_name, raw in vars(cls).items():
        if isinstance(raw, staticmethod):
            yield attr_name, "staticmethod"
        elif isinstance(raw, classmethod):
            yield attr_name, "classmethod"
