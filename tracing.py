import os
from dotenv import load_dotenv, find_dotenv
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from openinference.instrumentation.anthropic import AnthropicInstrumentor

load_dotenv(find_dotenv(), override=True)

space_id = os.environ["ARIZE_SPACE_ID"]
api_key = os.environ["ARIZE_API_KEY"]
project_name = os.environ.get("ARIZE_PROJECT_NAME", "arize-quickstart")

exporter = OTLPSpanExporter(
    endpoint=os.environ.get("ARIZE_OTLP_ENDPOINT", "https://otlp.eu-west-1a.arize.com/v1/traces"),
    headers={
        "api_key": api_key,
        "arize-space-id": space_id,
        "arize-interface": "otel",
    },
)

provider = TracerProvider(
    resource=Resource.create(
        {
            "model_id": project_name,
            "openinference.project.name": project_name,
        }
    )
)
provider.add_span_processor(BatchSpanProcessor(exporter))
trace.set_tracer_provider(provider)

AnthropicInstrumentor().instrument()

print(f"Tracing initialized for project: {project_name}")
