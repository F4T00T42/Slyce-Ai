"""Small shared helpers for the DB layer."""

def to_float(value, default=None):
    # Inputs: value (any DB value, possibly None/Decimal/str), default (fallback).
    # Returns float(value), or default when value is None or not convertible.
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
