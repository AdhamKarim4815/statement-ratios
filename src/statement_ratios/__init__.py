"""statement-ratios: financial statement ratio analysis with no dependencies."""

from __future__ import annotations

__version__ = "0.1.0"

from .analysis import Analysis, YearResult, analyze
from .loader import load_company
from .models import Company, FiscalYear, InputError, ValidationError
from .validate import build_company

__all__ = [
    "Analysis",
    "Company",
    "FiscalYear",
    "InputError",
    "ValidationError",
    "YearResult",
    "__version__",
    "analyze",
    "build_company",
    "load_company",
]
