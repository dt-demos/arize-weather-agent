# arize-quickstart

Sends a prompt to Claude (Azure Foundry) and traces the call to Arize.

## Prerequisites

- Arize Account
- Arize API Key
- Hosted LLM Model - Project has example for one in Azure. See .env-template for where to adjust
- Python 3.11

## Setup

1. Clone this repo

2. Copy the env template and set the values in `.env` (at least `ARIZE_API_KEY` and `AZURE_API_KEY`). 

Project has example for one in Azure. See .env-template for adjustments

```
cp .env-template .env
```

3. Setup Python

```
rm -rf .venv
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

4. Test

```
# with defaulted prompt
python main.py

# Pass your own prompt to override the default:
python main.py "your prompt"
```

## How the agent works

`main.py` runs a small tool-calling loop (max 5 steps):

1. The prompt is sent to Claude along with two tool definitions.
2. If Claude replies with `tool_use`, the script runs the tool and sends the result back. For "weather in Paris" this is typically `geocode("Paris")` for lat/long, then `get_current_weather(lat, lon)`.
3. The loop ends when Claude returns a normal text answer.

**No web search is used.** Both tools call the free [Open-Meteo](https://open-meteo.com) HTTP APIs, which need no API key. The model only decides which tool to call and summarizes the results.

| Tool | API endpoint | Docs |
|------|--------------|------|
| `geocode` | `https://geocoding-api.open-meteo.com/v1/search` | https://open-meteo.com/en/docs/geocoding-api |
| `get_current_weather` | `https://api.open-meteo.com/v1/forecast` | https://open-meteo.com/en/docs |

Tracing (`tracing.py`) sends OpenTelemetry spans to Arize: one `AGENT` span (`weather_agent`) wrapping the run, with a `TOOL` span for each tool call.
