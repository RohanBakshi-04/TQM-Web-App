"""Monetary Currency and Integer Paise Conversion Utilities.

Course: BBAT104 - Fundamentals of Total Quality Management (TQM)
Quality Goal: Q05 - Zero Financial Discrepancies and Exact Integer Arithmetic
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional, Union


def to_paise(amount: Any) -> int:
    """Convert rupee value (Decimal, float, int, or numeric str) to integer paise strictly using Decimal."""
    if amount is None:
        return 0
    if isinstance(amount, (int,)):
        return int(amount) * 100
    # Clean string if formatted with commas or symbols
    amt_str = str(amount).strip().replace(",", "").replace("₹", "").replace("Rs.", "").replace("Rs", "").strip()
    if not amt_str:
        return 0
    dec = Decimal(amt_str).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return int(dec * 100)


def from_paise(paise: Optional[Union[int, float]]) -> Decimal:
    """Convert integer paise to Decimal rupee representation with 2 decimal places."""
    if paise is None:
        return Decimal("0.00")
    return (Decimal(int(paise)) / Decimal(100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def paise_to_float(paise: Optional[Union[int, float]]) -> float:
    """Convert integer paise to floating point rupees for backward-compatible API payloads."""
    return float(from_paise(paise))


def format_inr(value: Any, is_paise: bool = False) -> str:
    """Format rupee or paise value as standard INR string (e.g. ₹1,250.00)."""
    if is_paise:
        dec = from_paise(value)
    else:
        dec = Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"₹{dec:,.2f}"
