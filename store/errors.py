class MemoryLimitError(Exception):
    """Raised when a write cannot fit in the configured maxmemory budget."""

