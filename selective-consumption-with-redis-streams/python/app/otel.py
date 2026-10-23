from opentelemetry import trace
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider


def setup(service_name):
    # No exporter is needed: the instrumentation alone propagates the W3C
    # trace context and baggage headers between services.
    trace.set_tracer_provider(
        TracerProvider(resource=Resource.create({"service.name": service_name})))
    RequestsInstrumentor().instrument()


def instrument(app):
    FlaskInstrumentor().instrument_app(app)
