import tracing  # must be first
import json
import os
import sys
import urllib.parse
import urllib.request
from dotenv import load_dotenv, find_dotenv
from anthropic import AnthropicFoundry
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

load_dotenv(find_dotenv(), override=True)

endpoint = os.environ["AZURE_ENDPOINT"]  # put this in .env
deployment_name = os.environ["AZURE_DEPLOYMENT_NAME"]  # put this in .env
api_key = os.environ["AZURE_API_KEY"]  # put this in .env

DEFAULT_PROMPT = "What's the weather in Paris right now?"
prompt = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PROMPT

MAX_STEPS = 5  # safety cap on the agent loop

client = AnthropicFoundry(
    api_key=api_key,
    base_url=endpoint
)
tracer = trace.get_tracer("weather-agent")


# ---------------------------------------------------------------------------
# Tools (Open-Meteo: free, no API key)
# ---------------------------------------------------------------------------
def _get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=10) as resp:
        return json.load(resp)


def geocode(city: str) -> dict:
    url = "https://geocoding-api.open-meteo.com/v1/search?" + urllib.parse.urlencode(
        {"name": city, "count": 1}
    )
    results = _get_json(url).get("results")
    if not results:
        return {"error": f"No location found for '{city}'"}
    r = results[0]
    return {
        "name": r["name"],
        "country": r.get("country"),
        "latitude": r["latitude"],
        "longitude": r["longitude"],
    }


def get_current_weather(latitude: float, longitude: float) -> dict:
    url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(
        {
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,apparent_temperature,relative_humidity_2m,"
                       "precipitation,wind_speed_10m,weather_code",
        }
    )
    data = _get_json(url)
    return {"current": data["current"], "units": data["current_units"]}


TOOL_FUNCTIONS = {"geocode": geocode, "get_current_weather": get_current_weather}

TOOLS = [
    {
        "name": "geocode",
        "description": "Look up the latitude and longitude of a city by name.",
        "input_schema": {
            "type": "object",
            "properties": {"city": {"type": "string", "description": "City name, e.g. Paris"}},
            "required": ["city"],
        },
    },
    {
        "name": "get_current_weather",
        "description": "Get the current weather conditions for a latitude/longitude. "
                       "Call geocode first if you only have a city name.",
        "input_schema": {
            "type": "object",
            "properties": {
                "latitude": {"type": "number"},
                "longitude": {"type": "number"},
            },
            "required": ["latitude", "longitude"],
        },
    },
]


def run_tool(name: str, args: dict) -> str:
    """Execute a tool inside its own TOOL span."""
    with tracer.start_as_current_span(name) as span:
        span.set_attribute("openinference.span.kind", "TOOL")
        span.set_attribute("tool.name", name)
        span.set_attribute("input.value", json.dumps(args))
        try:
            result = json.dumps(TOOL_FUNCTIONS[name](**args))
        except Exception as e:  # report failures back to the model
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
            result = json.dumps({"error": str(e)})
        span.set_attribute("output.value", result)
        return result


# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------
def run_agent(user_prompt: str):
    messages = [{"role": "user", "content": user_prompt}]
    input_tokens = output_tokens = 0

    with tracer.start_as_current_span("weather_agent") as agent_span:
        agent_span.set_attribute("openinference.span.kind", "AGENT")
        agent_span.set_attribute("input.value", user_prompt)

        for step in range(MAX_STEPS):
            message = client.messages.create(
                model=deployment_name,
                messages=messages,
                tools=TOOLS,
                max_tokens=1024,
            )
            input_tokens += message.usage.input_tokens
            output_tokens += message.usage.output_tokens

            if message.stop_reason != "tool_use":
                break

            messages.append({"role": "assistant", "content": message.content})
            tool_results = []
            for block in message.content:
                if block.type == "tool_use":
                    print(f"  step {step + 1}: tool call {block.name}({json.dumps(block.input)})")
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": run_tool(block.name, block.input),
                        }
                    )
            messages.append({"role": "user", "content": tool_results})

        final_text = "".join(b.text for b in message.content if b.type == "text")
        agent_span.set_attribute("output.value", final_text)
        return message, final_text, input_tokens, output_tokens


message, final_text, input_tokens, output_tokens = run_agent(prompt)

# Full input/output detail
print(f"Input:  {prompt}")
print(f"Output: {final_text}")
print(f"Model:  {message.model}")
print(f"Stop reason: {message.stop_reason}")
print(f"Input tokens (total):  {input_tokens}")
print(f"Output tokens (total): {output_tokens}")

# Flush and send spans before exit
trace.get_tracer_provider().shutdown()
print("Traces flushed.")
