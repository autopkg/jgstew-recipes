"""Pytest configuration for the SharedProcessors suite.

Importing processor_utils sets up sys.path (autopkglib + SharedProcessors) before
any test module imports a processor.
"""

import processor_utils  # noqa: F401  (import side effect: sets up sys.path)
import pytest


@pytest.fixture
def make_processor():
    """Return a factory that instantiates a Processor class with an env dict.

    Usage:
        proc = make_processor(SomeProcessor, {"input_var": "value"})
    """

    def _make(processor_class, env=None):
        return processor_class(env if env is not None else {})

    return _make
