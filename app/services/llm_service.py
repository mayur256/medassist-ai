"""LLM service using local transformers pipeline."""

import json
import logging

from transformers import pipeline

from app.config import settings

logger = logging.getLogger(__name__)

_text_pipeline = None


def _get_pipeline():
    global _text_pipeline
    if _text_pipeline is None:
        logger.info("Loading LLM model: %s", settings.llm_model)
        _text_pipeline = pipeline(
            "text-generation",
            model=settings.llm_model,
            device_map="auto",
            torch_dtype="auto",
        )
    return _text_pipeline


async def query_llm(prompt: str, model: str | None = None) -> str:
    """Generate text using local model."""
    pipe = _get_pipeline()
    try:
        outputs = pipe(
            prompt,
            max_new_tokens=512,
            temperature=0.3,
            do_sample=True,
            return_full_text=False,
        )
        return outputs[0]["generated_text"].strip() if outputs else ""
    except Exception as e:
        logger.error("LLM inference failed: %s", e)
        return ""


async def query_llm_json(prompt: str) -> dict | list | None:
    """Query LLM and attempt to parse response as JSON."""
    raw = await query_llm(prompt)
    if not raw:
        return None
    # Try to extract JSON from response (LLMs often wrap in markdown)
    json_match = raw
    if "```json" in raw:
        json_match = raw.split("```json")[1].split("```")[0]
    elif "```" in raw:
        json_match = raw.split("```")[1].split("```")[0]
    try:
        return json.loads(json_match.strip())
    except json.JSONDecodeError:
        logger.warning("Failed to parse LLM response as JSON: %s", raw[:200])
        return None
