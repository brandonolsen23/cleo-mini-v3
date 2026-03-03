"""ARN normalization — canonical 20-digit Ontario assessment roll number.

Ontario ARNs come in two formats:
  - 15-digit (from Realtrack HTML):  190402310006300
  - 20-digit (from MPAC/AgMaps):     19040231000630000000

The 20-digit format is canonical. The last 5 digits are a sub-roll suffix
(usually 00000 for the primary roll entry).

Usage:
    from cleo.parcels.arn import normalize_arn

    normalize_arn("190402310006300")      # → "19040231000630000000"
    normalize_arn("19040231000630000000")  # → "19040231000630000000"  (no-op)
    normalize_arn("")                      # → ""
"""

import re


def normalize_arn(arn: str) -> str:
    """Normalize an ARN to canonical 20-digit format.

    Strips non-digit characters, pads 15-digit ARNs to 20 digits.
    Returns empty string for empty/invalid input.
    """
    if not arn:
        return ""
    digits = re.sub(r"\D", "", arn)
    if not digits:
        return ""
    if len(digits) == 15:
        return digits + "00000"
    if len(digits) == 20:
        return digits
    # Non-standard length — return as-is (don't silently mangle)
    return digits
