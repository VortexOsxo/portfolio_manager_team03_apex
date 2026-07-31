from decimal import Decimal, InvalidOperation


def parse_positive_amount(raw_value):
    """Parse `raw_value` into a positive, finite Decimal.

    Returns (amount, None) on success, (None, error_message) on failure.
    """
    try:
        amount = Decimal(str(raw_value))
    except InvalidOperation:
        return None, "amount must be a number"

    if amount.is_nan():
        return None, "amount must be a number"

    if amount <= 0:
        return None, "amount must be greater than zero"

    return amount, None
