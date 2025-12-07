"""Application Insights observability setup for VideoAgent."""

import os
from typing import Optional

from .settings import get_app_insights_settings


def setup_observability() -> None:
    """Setup OpenTelemetry observability with Application Insights.

    Configures tracing and metrics export to Azure Application Insights
    if a connection string is provided in the environment.
    """
    settings = get_app_insights_settings()
    connection_string = settings.applicationinsights_connection_string

    if not connection_string:
        print("Warning: APPLICATIONINSIGHTS_CONNECTION_STRING not set. Observability disabled.")
        return

    try:
        from azure.monitor.opentelemetry.exporter import (
            AzureMonitorTraceExporter,
            AzureMonitorMetricExporter,
        )
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.resources import Resource

        # Create resource with service name
        resource = Resource.create(
            {
                "service.name": "videoagent",
                "service.version": "0.1.0",
            }
        )

        # Setup trace provider
        trace_provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(trace_provider)

        # Add Azure Monitor exporter
        trace_exporter = AzureMonitorTraceExporter(
            connection_string=connection_string
        )
        trace_provider.add_span_processor(
            BatchSpanProcessor(trace_exporter)
        )

        print("Application Insights observability enabled.")

    except ImportError as e:
        print(f"Warning: Could not setup Application Insights: {e}")
        print("Install azure-monitor-opentelemetry-exporter for observability support.")


def get_tracer(name: str = "videoagent"):
    """Get a tracer for creating spans.

    Args:
        name: Tracer name (default: "videoagent")

    Returns:
        OpenTelemetry Tracer instance
    """
    try:
        from opentelemetry import trace
        return trace.get_tracer(name)
    except ImportError:
        # Return a no-op tracer if OpenTelemetry is not installed
        return _NoOpTracer()


class _NoOpTracer:
    """No-op tracer for when OpenTelemetry is not available."""

    def start_as_current_span(self, name: str, **kwargs):
        return _NoOpSpan()


class _NoOpSpan:
    """No-op span context manager."""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def set_attribute(self, key: str, value):
        pass

    def add_event(self, name: str, **kwargs):
        pass
