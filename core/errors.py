"""Error handling hierarchy for MCP reliability testing framework."""

from typing import Optional, Dict, Any
import traceback


class MCPError(Exception):
    """Base exception for all MCP-related errors."""
    
    def __init__(
        self, 
        message: str, 
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        self.cause = cause
        self.traceback = traceback.format_exc() if cause else None

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for serialization."""
        return {
            "error_type": self.__class__.__name__,
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
            "traceback": self.traceback
        }


class MCPConnectionError(MCPError):
    """Connection-related errors."""
    pass


class MCPTimeoutError(MCPError):
    """Timeout-related errors."""
    pass


class MCPTransportError(MCPError):
    """Transport-layer errors."""
    pass


class MCPProtocolError(MCPError):
    """Protocol-level errors."""
    pass


class MCPServerError(MCPError):
    """Server-side errors."""
    pass


class MCPClientError(MCPError):
    """Client-side errors."""
    pass


class MCPRetryExhaustedError(MCPError):
    """All retry attempts have been exhausted."""
    
    def __init__(self, attempts: int, last_error: Exception):
        super().__init__(
            f"Retry exhausted after {attempts} attempts",
            details={"attempts": attempts, "last_error": str(last_error)}
        )
        self.attempts = attempts
        self.last_error = last_error


class MCPConfigurationError(MCPError):
    """Configuration-related errors."""
    pass