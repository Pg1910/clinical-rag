"""LLM client and API interactions"""
from __future__ import annotations

import httpx
import json
import logging
from typing import Any, Dict, List

from icu_copilot.config import SETTINGS

logger = logging.getLogger(__name__)


def estimate_tokens(text: str) -> int:
    """Estimate token count from text using chars_per_token ratio."""
    return int(len(text) / SETTINGS.chars_per_token)


def truncate_to_token_limit(text: str, max_tokens: int) -> str:
    """Truncate text to approximately fit within token limit."""
    max_chars = int(max_tokens * SETTINGS.chars_per_token)
    if len(text) <= max_chars:
        return text
    # Truncate and add indicator
    truncated = text[:max_chars - 50]
    # Try to break at a sensible point (newline or period)
    last_break = max(truncated.rfind('\n'), truncated.rfind('. '))
    if last_break > max_chars * 0.8:
        truncated = truncated[:last_break + 1]
    return truncated + "\n[... truncated due to context limit ...]"


def truncate_evidence_list(
    evidences: List[Dict[str, str]], 
    max_total_chars: int | None = None
) -> str:
    """Build evidence text, truncating individual items and total if needed."""
    max_chars = max_total_chars or SETTINGS.max_evidence_chars
    max_per_item = max_chars // max(len(evidences), 1)  # Distribute budget
    max_per_item = max(max_per_item, 200)  # Minimum 200 chars per item
    
    parts = []
    total_chars = 0
    
    for ev in evidences:
        eid = ev.get('evidence_id', ev.get('id', 'UNK'))
        text = ev.get('text', ev.get('raw_text', ''))
        
        # Truncate individual evidence if too long
        if len(text) > max_per_item:
            text = text[:max_per_item - 20] + "...[truncated]"
        
        item = f"[{eid}] {text}"
        
        # Check if adding this would exceed total limit
        if total_chars + len(item) > max_chars:
            remaining = max_chars - total_chars - 50
            if remaining > 100:
                parts.append(item[:remaining] + "...[truncated]")
            parts.append(f"\n[{len(evidences) - len(parts)} more items truncated]")
            break
        
        parts.append(item)
        total_chars += len(item) + 1  # +1 for newline
    
    return "\n".join(parts)


class OllamaClient:
    def __init__(self):
        self.base_url = SETTINGS.ollama_base_url
        self.model = SETTINGS.ollama_model

    def generate(self, prompt: str, *, json_mode: bool = False, max_retries: int = 2) -> str:
        """Generate response from LLM with automatic context management."""
        
        # Check and warn about prompt size
        est_tokens = estimate_tokens(prompt)
        if est_tokens > SETTINGS.max_prompt_tokens:
            logger.warning(
                f"Prompt exceeds recommended limit: ~{est_tokens} tokens "
                f"(max: {SETTINGS.max_prompt_tokens}). Truncating..."
            )
            prompt = truncate_to_token_limit(prompt, SETTINGS.max_prompt_tokens)
            est_tokens = estimate_tokens(prompt)
        
        payload: Dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": SETTINGS.temperature,
                "top_p": SETTINGS.top_p,
                "num_ctx": SETTINGS.num_ctx,
                "num_predict": SETTINGS.max_tokens,
            },
        }
        if json_mode:
            payload["format"] = "json"

        print(f"\n=== OLLAMA REQUEST ===")
        print(f"URL: {self.base_url}/api/generate")
        print(f"Model: {self.model}")
        print(f"JSON Mode: {json_mode}")
        print(f"Prompt length: {len(prompt)} chars (~{est_tokens} tokens)")
        print(f"Context window: {SETTINGS.num_ctx} tokens\n")

        for attempt in range(max_retries + 1):
            try:
                with httpx.Client(timeout=600) as client:  # 10 min timeout for large contexts
                    r = client.post(f"{self.base_url}/api/generate", json=payload)
                    r.raise_for_status()
                    data = r.json()
                break
            except httpx.TimeoutException:
                if attempt < max_retries:
                    logger.warning(f"Request timeout, retrying ({attempt + 1}/{max_retries})...")
                    # Reduce context on retry
                    if est_tokens > 4000:
                        prompt = truncate_to_token_limit(prompt, int(est_tokens * 0.7))
                        payload["prompt"] = prompt
                        est_tokens = estimate_tokens(prompt)
                        logger.info(f"Reduced prompt to ~{est_tokens} tokens")
                else:
                    raise
            except httpx.HTTPStatusError as e:
                if "context" in str(e).lower() or "token" in str(e).lower():
                    if attempt < max_retries:
                        logger.warning(f"Context limit error, reducing prompt size...")
                        prompt = truncate_to_token_limit(prompt, int(est_tokens * 0.6))
                        payload["prompt"] = prompt
                        est_tokens = estimate_tokens(prompt)
                    else:
                        raise
                else:
                    raise

        print(f"=== OLLAMA RESPONSE ===")
        print(f"Status: {r.status_code}")
        response_preview = data.get('response', '')[:200]
        print(f"Response preview: '{response_preview}...'")
        print(f"Response length: {len(data.get('response', ''))} chars")
        print(f"Prompt eval count: {data.get('prompt_eval_count', 'N/A')} tokens")
        print(f"Eval count (tokens generated): {data.get('eval_count', 0)}")
        print(f"Full response keys: {list(data.keys())}\n")

        response = data.get("response", "")
        if not response or response.strip() in ("", "{}"):
            print("WARNING: LLM returned empty or minimal response!")
            print(f"Full data: {json.dumps(data, indent=2)}\n")

        return response
