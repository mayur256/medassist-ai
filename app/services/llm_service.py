"""LLM service — supports local model or HuggingFace Inference API."""

import json
import logging
import re

from transformers import pipeline as hf_pipeline

from app.config import settings

logger = logging.getLogger(__name__)

_text_pipeline = None
_hf_client = None


def _get_hf_client():
    global _hf_client
    if _hf_client is None:
        from huggingface_hub import InferenceClient
        _hf_client = InferenceClient(api_key=settings.hf_api_token)
    return _hf_client


def _get_pipeline():
    global _text_pipeline
    if _text_pipeline is None:
        logger.info("Loading local LLM model: %s", settings.llm_model)
        _text_pipeline = hf_pipeline("text-generation", model=settings.llm_model)
    return _text_pipeline


async def _query_hf_api(prompt: str) -> str:
    """Query HuggingFace Inference API via InferenceClient."""
    try:
        client = _get_hf_client()
        response = client.chat_completion(
            model=settings.hf_inference_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=512,
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error("HF Inference API failed: %s", e)
        return ""


async def _query_local(prompt: str) -> str:
    """Query local model."""
    pipe = _get_pipeline()
    try:
        messages = [{"role": "user", "content": prompt}]
        outputs = pipe(messages, max_new_tokens=512, temperature=0.3, do_sample=True, return_full_text=False)
        return outputs[0]["generated_text"].strip() if outputs else ""
    except Exception as e:
        logger.error("Local LLM inference failed: %s", e)
        return ""


async def query_llm(prompt: str, model: str | None = None) -> str:
    """Generate text — uses HF API if token is set, otherwise local model."""
    if settings.hf_api_token:
        return await _query_hf_api(prompt)
    return await _query_local(prompt)


def _extract_json(raw: str) -> dict | list | None:
    """Try multiple strategies to extract JSON from LLM output."""
    if not raw:
        return None

    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError:
        pass

    if "```" in raw:
        blocks = re.findall(r"```(?:json)?\s*(.*?)```", raw, re.DOTALL)
        for block in blocks:
            try:
                return json.loads(block.strip())
            except json.JSONDecodeError:
                continue

    # Find nested JSON object
    brace_start = raw.find("{")
    if brace_start != -1:
        depth = 0
        for i in range(brace_start, len(raw)):
            if raw[i] == "{":
                depth += 1
            elif raw[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(raw[brace_start:i + 1])
                    except json.JSONDecodeError:
                        break

    logger.warning("Failed to parse LLM response as JSON: %s", raw[:200])
    return None


async def query_llm_json(prompt: str) -> dict | list | None:
    """Query LLM and attempt to parse response as JSON."""
    raw = await query_llm(prompt)
    return _extract_json(raw)
