import time
from openai import OpenAI
import cohere
from config import get_config

config = get_config()

# Initialize clients using the validated keys from your config
openai_client = OpenAI(api_key=config.OPENAI_API_KEY)
cohere_client = cohere.Client(api_key=config.COHERE_API_KEY)

# Prices in USD per one million tokens. Update these if provider pricing changes.
PRICING_PER_MILLION = {
    "openai:gpt-4o-mini": {
        "input": 0.15,
        "output": 0.60,
    },
    "cohere:command-a-03-2025": {
        "input": 2.50,
        "output": 10.00,
    },
}

# In-memory accounting across the pipeline.
# output_tokens means visible output tokens; thinking_tokens are tracked separately.
cost_tracker = {
    "total_cost": 0.0,
    "openai_calls": 0,
    "cohere_calls": 0,
    "input_tokens": 0,
    "thinking_tokens": 0,
    "output_tokens": 0,
    "usage_by_model": {},
}


def record_usage(provider, model, input_tokens, output_tokens, thinking_tokens=0):
    """Record provider-reported usage and calculate its token-based cost."""
    model_key = f"{provider}:{model}"
    try:
        pricing = PRICING_PER_MILLION[model_key]
    except KeyError as error:
        raise ValueError(f"No pricing configured for {model_key}") from error

    input_tokens = int(input_tokens or 0)
    output_tokens = int(output_tokens or 0)
    thinking_tokens = int(thinking_tokens or 0)

    # For OpenAI, reasoning tokens are included in completion_tokens and are
    # therefore charged at the output rate. Do not add them twice.
    billed_output_tokens = output_tokens + thinking_tokens
    cost = (
        input_tokens * pricing["input"]
        + billed_output_tokens * pricing["output"]
    ) / 1_000_000

    cost_tracker["total_cost"] += cost
    cost_tracker["input_tokens"] += input_tokens
    cost_tracker["thinking_tokens"] += thinking_tokens
    cost_tracker["output_tokens"] += output_tokens

    model_usage = cost_tracker["usage_by_model"].setdefault(
        model_key,
        {
            "input_tokens": 0,
            "thinking_tokens": 0,
            "output_tokens": 0,
            "cost": 0.0,
        },
    )
    model_usage["input_tokens"] += input_tokens
    model_usage["thinking_tokens"] += thinking_tokens
    model_usage["output_tokens"] += output_tokens
    model_usage["cost"] += cost


def call_openai(prompt):
    """Call OpenAI and record its reported token usage."""
    model = "gpt-4o-mini"
    response = openai_client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )

    usage = response.usage
    details = usage.completion_tokens_details
    thinking_tokens = getattr(details, "reasoning_tokens", 0) or 0
    visible_output_tokens = max(
        usage.completion_tokens - thinking_tokens,
        0,
    )
    record_usage(
        "openai",
        model,
        input_tokens=usage.prompt_tokens,
        output_tokens=visible_output_tokens,
        thinking_tokens=thinking_tokens,
    )

    cost_tracker["openai_calls"] += 1
    return response.choices[0].message.content


def call_cohere(prompt):
    """Call Cohere and record its reported billable token usage."""
    model = "command-a-03-2025"
    response = cohere_client.chat(
        model=model,
        message=prompt,
        temperature=0.3
    )

    billed_units = getattr(getattr(response, "meta", None), "billed_units", None)
    if billed_units is None:
        raise RuntimeError("Cohere did not return billed token usage")
    record_usage(
        "cohere",
        model,
        input_tokens=billed_units.input_tokens,
        output_tokens=billed_units.output_tokens,
    )

    cost_tracker["cohere_calls"] += 1
    return response.text

def ask_with_fallback(prompt, primary="openai"):
    """
    Attempts the primary AI provider. If it fails or times out, 
    it retries up to MAX_RETRIES, then cleanly falls back to the secondary.
    """
    retries = config.MAX_RETRIES
    
    # 1. Try Primary Provider
    for attempt in range(retries):
        try:
            if primary == "openai":
                return call_openai(prompt), "OpenAI"
            else:
                return call_cohere(prompt), "Cohere"
        except Exception as e:
            print(f"⚠️ {primary.capitalize()} failed (Attempt {attempt + 1}/{retries}): {e}")
            if attempt < retries - 1:
                time.sleep(2) # Backoff pause to respect rate limits
            
    print(f"🚨 {primary.capitalize()} completely failed. Triggering fallback...")
    
    # 2. Try Fallback Provider
    fallback = "cohere" if primary == "openai" else "openai"
    for attempt in range(retries):
        try:
            if fallback == "cohere":
                return call_cohere(prompt), "Cohere (Fallback)"
            else:
                return call_openai(prompt), "OpenAI (Fallback)"
        except Exception as e:
            print(f"⚠️ Fallback {fallback.capitalize()} failed (Attempt {attempt + 1}/{retries}): {e}")
            if attempt < retries - 1:
                time.sleep(2)
            
    raise Exception("Both primary and fallback LLM providers failed. Pipeline halted.")

# Checkpoint 3: Run this file directly to test both AIs and the routing logic
if __name__ == "__main__":
    print("Testing OpenAI connection...")
    try:
        oi_answer, oi_source = ask_with_fallback("Write a one-sentence summary of the internet.", primary="openai")
        print(f"✅ {oi_source} responded: {oi_answer}")
    except Exception as e:
        print(f"❌ OpenAI Test Failed: {e}")
        
    print("\nTesting Cohere connection...")
    try:
        co_answer, co_source = ask_with_fallback("Write a one-sentence summary of the internet.", primary="cohere")
        print(f"✅ {co_source} responded: {co_answer}")
    except Exception as e:
        print(f"❌ Cohere Test Failed: {e}")

    print(f"\n📊 Cost Tracking Summary:")
    print(f"Total estimated cost: ${cost_tracker['total_cost']:.6f}")
    print(f"Input tokens: {cost_tracker['input_tokens']}")
    print(f"Thinking tokens: {cost_tracker['thinking_tokens']}")
    print(f"Output tokens: {cost_tracker['output_tokens']}")
    for model, usage in cost_tracker["usage_by_model"].items():
        print(
            f"{model}: {usage['input_tokens']} input, "
            f"{usage['thinking_tokens']} thinking, "
            f"{usage['output_tokens']} output, "
            f"${usage['cost']:.6f}"
        )
    print(f"API Calls made: OpenAI ({cost_tracker['openai_calls']}), Cohere ({cost_tracker['cohere_calls']})")
