"""Finance data error types."""


class FinanceDataError(ValueError):
    """Raised when finance data is missing or malformed."""


class FinanceRecordNotFoundError(FinanceDataError):
    """Raised when a requested finance record does not exist."""
