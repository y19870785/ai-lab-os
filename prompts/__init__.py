
"""Deprecated source-only compatibility namespace for the historical stub."""

import warnings

warnings.warn(
    "The source-only 'prompts' namespace is deprecated and has no canonical "
    "runtime registry. It remains source-importable through at least v0.36 and "
    "will not be removed before v0.37.0.",
    DeprecationWarning,
    stacklevel=2,
)
