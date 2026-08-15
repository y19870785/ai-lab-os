
"""Deprecated empty compatibility namespace; use :mod:`core.workflow`."""

import warnings

warnings.warn(
    "The 'workflows' namespace is deprecated; use 'core.workflow'. It is retained "
    "through at least v0.36 and will not be removed before v0.37.0.",
    DeprecationWarning,
    stacklevel=2,
)
