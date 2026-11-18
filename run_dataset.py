"""Send a batch of prompts through the weather agent to generate traces in Arize.

Usage: python run_dataset.py [--repeat N] [--delay S]
"""
import argparse
import time
import uuid

from main import run_agent
from opentelemetry import trace

# Prompts from the "Weather Assistant Test Suite" dataset
SUITE_PROMPTS = [
    "What is the current temperature in New York City right now?",
    "Is it raining in London at this moment?",
    "What causes a thunderstorm to form?",
    "What is the difference between a hurricane, a typhoon, and a cyclone?",
    "Convert 35 degrees Celsius to Fahrenheit.",
    "I'm traveling to Iceland in January. What clothes should I pack for the weather?",
    "There is a tornado warning in my area. What should I do?",
    "What is the capital of France?",
]

# Extra prompts to vary the traces (tool use, multi-city, error paths)
EXTRA_PROMPTS = [
    "What's the weather in Tokyo right now?",
    "Compare the current weather in Sydney and Toronto.",
    "Do I need an umbrella in Seattle today?",
    "How windy is it in Chicago at the moment?",
    "What's the temperature in Reykjavik, and should I wear a coat?",
    "What's the weather in Xyzzyville?",
    "Is it humid in Singapore right now?",
    "Give me the current conditions in Cairo, Mumbai, and Sao Paulo.",
]

PROMPTS = SUITE_PROMPTS + EXTRA_PROMPTS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeat", type=int, default=1, help="run the full prompt list N times")
    parser.add_argument("--delay", type=float, default=0.0, help="seconds to pause between prompts")
    args = parser.parse_args()

    run_id = f"batch-{uuid.uuid4().hex[:8]}"
    total = args.repeat * len(PROMPTS)
    n = 0
    print(f"Run {run_id}: {total} prompts")

    for rep in range(args.repeat):
        for prompt in PROMPTS:
            n += 1
            print(f"[{n}/{total}] {prompt}")
            try:
                run_agent(prompt, session_id=run_id)
            except Exception as e:  # keep going so one failure doesn't stop the batch
                print(f"  ERROR: {e}")
            if args.delay and n < total:
                time.sleep(args.delay)

    trace.get_tracer_provider().shutdown()
    print(f"Done. Traces flushed (session.id = {run_id}).")


if __name__ == "__main__":
    main()
