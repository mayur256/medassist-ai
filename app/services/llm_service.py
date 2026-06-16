"""LLM service — Groq API (primary), HuggingFace (fallback), local (last resort)."""

import json
import logging
import re
import time

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# Module-level context for audit trail (set by callers)
_audit_context: dict = {"conversation_id": None, "step": "unknown"}


def set_audit_context(conversation_id: str | None = None, step: str = "unknown"):
    """Set context for audit logging of subsequent LLM calls."""
    _audit_context["conversation_id"] = conversation_id
    _audit_context["step"] = step


async def _query_groq(prompt: str) -> str:
    """Query Groq API (OpenAI-compatible)."""
    headers = {
        "Authorization": f"Bearer {settings.groq_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.groq_model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 512,
        "temperature": 0.3,
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(GROQ_URL, json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()
            return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.error("Groq API failed: %s", e)
        return ""


async def query_llm(prompt: str, model: str | None = None) -> str:
    """Generate text via Groq with audit logging."""
    start = time.time()
    result = await _query_groq(prompt)
    latency_ms = (time.time() - start) * 1000

    try:
        from app.services.audit import log_llm_call
        await log_llm_call(
            step=_audit_context.get("step", "unknown"),
            prompt=prompt,
            raw_response=result,
            latency_ms=latency_ms,
            conversation_id=_audit_context.get("conversation_id"),
        )
    except Exception as e:
        logger.debug("Audit log failed (non-critical): %s", e)

    return result


def _extract_json(raw: str) -> dict | list | None:
    """Extract JSON from LLM output."""
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
    """Query LLM and parse response as JSON."""
    raw = await query_llm(prompt)
    return _extract_json(raw)
