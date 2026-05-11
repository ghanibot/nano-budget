from __future__ import annotations

# Per-million-token pricing (input, output) in USD
# Updated May 2026 — adjust as providers change prices
PRICING: dict[str, dict[str, float]] = {
    # Anthropic
    "claude-opus-4-7":              {"input": 15.00,  "output": 75.00},
    "claude-sonnet-4-6":            {"input": 3.00,   "output": 15.00},
    "claude-haiku-4-5-20251001":    {"input": 0.80,   "output": 4.00},
    "claude-haiku-4-5":             {"input": 0.80,   "output": 4.00},
    # OpenAI
    "gpt-4o":                       {"input": 2.50,   "output": 10.00},
    "gpt-4o-mini":                  {"input": 0.15,   "output": 0.60},
    "gpt-4-turbo":                  {"input": 10.00,  "output": 30.00},
    "o1":                           {"input": 15.00,  "output": 60.00},
    "o1-mini":                      {"input": 3.00,   "output": 12.00},
    # Groq (very cheap)
    "llama-3.3-70b-versatile":      {"input": 0.59,   "output": 0.79},
    "llama3-8b-8192":               {"input": 0.05,   "output": 0.08},
    "mixtral-8x7b-32768":           {"input": 0.24,   "output": 0.24},
    # Google Gemini
    "gemini-2.0-flash":             {"input": 0.075,  "output": 0.30},
    "gemini-1.5-pro":               {"input": 1.25,   "output": 5.00},
    "gemini-1.5-flash":             {"input": 0.075,  "output": 0.30},
    # Mistral
    "mistral-small-latest":         {"input": 0.20,   "output": 0.60},
    "mistral-medium-latest":        {"input": 2.70,   "output": 8.10},
    "mistral-large-latest":         {"input": 2.00,   "output": 6.00},
    # Together AI
    "meta-llama/Llama-3-8b-chat-hf": {"input": 0.10, "output": 0.10},
    "meta-llama/Llama-3-70b-chat-hf": {"input": 0.90, "output": 0.90},
    # OpenRouter (free tier)
    "meta-llama/llama-3.1-8b-instruct:free": {"input": 0.0, "output": 0.0},
    # Cohere
    "command-r":                    {"input": 0.15,   "output": 0.60},
    "command-r-plus":               {"input": 2.50,   "output": 10.00},
    # Ollama (local — free)
    "llama3.2":                     {"input": 0.0,    "output": 0.0},
    "codellama":                    {"input": 0.0,    "output": 0.0},
    "mistral":                      {"input": 0.0,    "output": 0.0},
}

# Fallback per provider if model not found
PROVIDER_FALLBACK: dict[str, dict[str, float]] = {
    "anthropic":  {"input": 3.00,  "output": 15.00},
    "openai":     {"input": 2.50,  "output": 10.00},
    "groq":       {"input": 0.10,  "output": 0.10},
    "gemini":     {"input": 0.10,  "output": 0.30},
    "mistral":    {"input": 0.20,  "output": 0.60},
    "openrouter": {"input": 0.10,  "output": 0.10},
    "together":   {"input": 0.10,  "output": 0.10},
    "perplexity": {"input": 0.20,  "output": 0.20},
    "cohere":     {"input": 0.15,  "output": 0.60},
    "ollama":     {"input": 0.0,   "output": 0.0},
    "nano-proxy": {"input": 1.00,  "output": 5.00},
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int, provider: str = "") -> float:
    price = PRICING.get(model) or PROVIDER_FALLBACK.get(provider, {"input": 1.0, "output": 5.0})
    return (input_tokens / 1_000_000 * price["input"]) + (output_tokens / 1_000_000 * price["output"])
