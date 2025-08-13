"""Retry policy management for MCP operations."""

import asyncio
import random
import logging
from typing import Callable, Any, Optional
from datetime import datetime, timedelta, timezone

from .config import MCPRetryConfig, RetryStrategy
from .errors import MCPRetryExhaustedError


class RetryPolicyManager:
    """Manages retry policies for MCP operations."""
    
    def __init__(self, config: MCPRetryConfig):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)

    def should_retry(self, error: Exception, attempt: int) -> bool:
        """Determine if an operation should be retried."""
        if attempt >= self.config.max_attempts:
            return False

        error_type = type(error).__name__.lower()
        return any(
            retry_error in error_type 
            for retry_error in self.config.retry_on_errors
        )

    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay before next retry attempt."""
        if self.config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = self.config.initial_delay * (
                self.config.backoff_multiplier ** (attempt - 1)
            )
        elif self.config.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = self.config.initial_delay * attempt
        else:  # FIXED_DELAY
            delay = self.config.initial_delay

        # Add jitter to prevent thundering herd
        jitter = random.uniform(0.0, 0.1) * delay
        delay += jitter

        return min(delay, self.config.max_delay)

    async def execute_with_retry(
        self,
        operation: Callable[[], Any],
        operation_name: str = "operation"
    ) -> Any:
        """Execute an operation with retry logic."""
        last_error = None
        
        for attempt in range(1, self.config.max_attempts + 1):
            try:
                self.logger.debug(
                    f"Executing {operation_name}, attempt {attempt}/{self.config.max_attempts}"
                )
                return await operation()
                
            except Exception as error:
                last_error = error
                self.logger.warning(
                    f"Attempt {attempt} of {operation_name} failed: {error}"
                )
                
                if not self.should_retry(error, attempt):
                    self.logger.error(
                        f"Not retrying {operation_name} after attempt {attempt}: {error}"
                    )
                    raise
                
                if attempt < self.config.max_attempts:
                    delay = self.calculate_delay(attempt)
                    self.logger.info(
                        f"Retrying {operation_name} in {delay:.2f} seconds"
                    )
                    await asyncio.sleep(delay)

        # All retries exhausted
        raise MCPRetryExhaustedError(self.config.max_attempts, last_error)


class CircuitBreaker:
    """Circuit breaker pattern implementation for MCP operations."""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: type = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self.logger = logging.getLogger(self.__class__.__name__)

    def _should_attempt_reset(self) -> bool:
        """Check if circuit breaker should attempt to reset."""
        return (
            self.state == "OPEN" and
            self.last_failure_time and
            datetime.now(timezone.utc) - self.last_failure_time > timedelta(
                seconds=self.recovery_timeout
            )
        )

    async def call(self, operation: Callable[[], Any]) -> Any:
        """Execute operation through circuit breaker."""
        if self.state == "OPEN":
            if self._should_attempt_reset():
                self.state = "HALF_OPEN"
                self.logger.info("Circuit breaker moving to HALF_OPEN state")
            else:
                from .errors import MCPError
                raise MCPError("Circuit breaker is OPEN")

        try:
            result = await operation()
            
            # Success - reset circuit breaker if it was half-open
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failure_count = 0
                self.logger.info("Circuit breaker reset to CLOSED state")
                
            return result
            
        except self.expected_exception as e:
            self.failure_count += 1
            self.last_failure_time = datetime.now(timezone.utc)
            
            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
                self.logger.warning(
                    f"Circuit breaker opened after {self.failure_count} failures"
                )
            
            raise