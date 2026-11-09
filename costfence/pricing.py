"""Token pricing per provider and model. Prices in USD per million tokens."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ModelPricing:
    input_per_million: float
    output_per_million: float
    cache_read_per_million: float = 0.0
    cache_write_per_million: float = 0.0


# Prices as of late 2026 — override via config.yaml
DEFAULT_PRICING: dict[str, dict[str, ModelPricing]] = {
    "anthropic": {
        "claude-opus-4": ModelPricing(15.0, 75.0, 1.5, 18.75),
        "claude-sonnet-4": ModelPricing(3.0, 15.0, 0.3, 3.75),
        "claude-haiku-4": ModelPricing(0.80, 4.0, 0.08, 1.0),
        "claude-opus-5.5": ModelPricing(15.0, 75.0, 1.5, 18.75),
        "claude-sonnet-5.5": ModelPricing(3.0, 15.0, 0.3, 3.75),
        "claude-haiku-5.5": ModelPricing(1.0, 5.0, 0.1, 1.25),
    },
    "openai": {
        "gpt-4o": ModelPricing(2.50, 10.0),
        "gpt-4o-mini": ModelPricing(0.15, 0.60),
        "gpt-4-turbo": ModelPricing(10.0, 30.0),
        "o1": ModelPricing(15.0, 60.0),
        "o1-mini": ModelPricing(3.0, 12.0),
        "o3": ModelPricing(10.0, 40.0),
        "o3-mini": ModelPricing(1.10, 4.40),
    },
    "bedrock": {
        "anthropic.claude-opus-4-6-v1": ModelPricing(15.0, 75.0, 1.5, 18.75),
        "anthropic.claude-sonnet-5-5": ModelPricing(3.0, 15.0, 0.3, 3.75),
        "anthropic.claude-opus-5-5": ModelPricing(15.0, 75.0, 1.5, 18.75),
        "anthropic.claude-haiku-5-5": ModelPricing(1.0, 5.0, 0.1, 1.25),
    },
}


def get_pricing(provider: str, model: str, custom: Optional[dict] = None) -> ModelPricing:
    source = custom if custom else DEFAULT_PRICING
    provider_models = source.get(provider, {})
    if model in provider_models:
        return provider_models[model]
    for key, pricing in provider_models.items():
        if key in model or model in key:
            return pricing
    return ModelPricing(5.0, 15.0)
