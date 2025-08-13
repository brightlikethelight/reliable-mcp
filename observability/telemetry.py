"""OpenTelemetry setup and configuration for MCP reliability testing."""

import logging
from typing import Optional, Dict, Any
import os

try:
    from opentelemetry import trace, metrics
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
    from opentelemetry.instrumentation.redis import RedisInstrumentor
    
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False


logger = logging.getLogger(__name__)

# Global tracer and meter instances
_tracer: Optional[trace.Tracer] = None
_meter: Optional[metrics.Meter] = None


def setup_telemetry(
    service_name: str = "mcp-reliability-lab",
    service_version: str = "0.1.0",
    otlp_endpoint: Optional[str] = None,
    otlp_headers: Optional[Dict[str, str]] = None,
    trace_sampling_rate: float = 1.0,
    enable_instrumentation: bool = True,
    resource_attributes: Optional[Dict[str, str]] = None
) -> bool:
    """
    Set up OpenTelemetry tracing and metrics.
    
    Args:
        service_name: Name of the service for telemetry
        service_version: Version of the service
        otlp_endpoint: OTLP endpoint URL (defaults to localhost:4317)
        otlp_headers: Additional headers for OTLP export
        trace_sampling_rate: Sampling rate for traces (0.0 to 1.0)
        enable_instrumentation: Whether to enable automatic instrumentation
        resource_attributes: Additional resource attributes
        
    Returns:
        True if setup successful, False otherwise
    """
    global _tracer, _meter
    
    if not OTEL_AVAILABLE:
        logger.warning("OpenTelemetry not available, telemetry disabled")
        return False
    
    try:
        # Set up resource
        resource_attrs = {
            "service.name": service_name,
            "service.version": service_version,
            "service.instance.id": os.environ.get("HOSTNAME", "unknown"),
        }
        
        if resource_attributes:
            resource_attrs.update(resource_attributes)
            
        resource = Resource.create(resource_attrs)
        
        # Set up OTLP endpoint
        endpoint = otlp_endpoint or os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
        headers = otlp_headers or {}
        
        # Parse headers from environment if not provided
        if not headers and "OTEL_EXPORTER_OTLP_HEADERS" in os.environ:
            header_str = os.environ["OTEL_EXPORTER_OTLP_HEADERS"]
            headers = dict(h.split("=") for h in header_str.split(","))
        
        # Set up tracing
        tracer_provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(tracer_provider)
        
        otlp_span_exporter = OTLPSpanExporter(
            endpoint=endpoint,
            headers=headers
        )
        
        span_processor = BatchSpanProcessor(otlp_span_exporter)
        tracer_provider.add_span_processor(span_processor)
        
        _tracer = trace.get_tracer(__name__)
        
        # Set up metrics
        otlp_metric_exporter = OTLPMetricExporter(
            endpoint=endpoint,
            headers=headers
        )
        
        metric_reader = PeriodicExportingMetricReader(
            exporter=otlp_metric_exporter,
            export_interval_millis=10000  # 10 seconds
        )
        
        meter_provider = MeterProvider(
            resource=resource,
            metric_readers=[metric_reader]
        )
        metrics.set_meter_provider(meter_provider)
        
        _meter = metrics.get_meter(__name__)
        
        # Enable automatic instrumentation
        if enable_instrumentation:
            try:
                HTTPXClientInstrumentor().instrument()
            except Exception as e:
                logger.warning(f"Failed to instrument HTTPX: {e}")
                
            try:
                AsyncPGInstrumentor().instrument()
            except Exception as e:
                logger.warning(f"Failed to instrument AsyncPG: {e}")
                
            try:
                RedisInstrumentor().instrument()
            except Exception as e:
                logger.warning(f"Failed to instrument Redis: {e}")
        
        logger.info(f"OpenTelemetry initialized for {service_name}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize OpenTelemetry: {e}")
        return False


def get_tracer(name: Optional[str] = None) -> Optional[trace.Tracer]:
    """
    Get a tracer instance.
    
    Args:
        name: Optional tracer name
        
    Returns:
        Tracer instance if available, None otherwise
    """
    if not OTEL_AVAILABLE:
        return None
        
    if name:
        return trace.get_tracer(name)
    return _tracer


def get_meter(name: Optional[str] = None) -> Optional[metrics.Meter]:
    """
    Get a meter instance.
    
    Args:
        name: Optional meter name
        
    Returns:
        Meter instance if available, None otherwise
    """
    if not OTEL_AVAILABLE:
        return None
        
    if name:
        return metrics.get_meter(name)
    return _meter


def shutdown_telemetry() -> None:
    """Shutdown telemetry providers and exporters."""
    if not OTEL_AVAILABLE:
        return
        
    try:
        # Shutdown tracer provider
        tracer_provider = trace.get_tracer_provider()
        if hasattr(tracer_provider, 'shutdown'):
            tracer_provider.shutdown()
            
        # Shutdown meter provider
        meter_provider = metrics.get_meter_provider()
        if hasattr(meter_provider, 'shutdown'):
            meter_provider.shutdown()
            
        logger.info("OpenTelemetry shutdown complete")
        
    except Exception as e:
        logger.error(f"Error during OpenTelemetry shutdown: {e}")


def configure_from_environment() -> Dict[str, Any]:
    """
    Configure telemetry from environment variables.
    
    Returns:
        Configuration dictionary
    """
    config = {
        "service_name": os.environ.get("OTEL_SERVICE_NAME", "mcp-reliability-lab"),
        "service_version": os.environ.get("OTEL_SERVICE_VERSION", "0.1.0"),
        "otlp_endpoint": os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"),
        "trace_sampling_rate": float(os.environ.get("OTEL_TRACES_SAMPLER_ARG", "1.0")),
        "enable_instrumentation": os.environ.get("OTEL_AUTO_INSTRUMENT", "true").lower() == "true"
    }
    
    # Parse resource attributes
    if "OTEL_RESOURCE_ATTRIBUTES" in os.environ:
        attrs_str = os.environ["OTEL_RESOURCE_ATTRIBUTES"]
        config["resource_attributes"] = dict(
            attr.split("=") for attr in attrs_str.split(",")
        )
    
    return config