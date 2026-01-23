"""Configuration management for ICU Copilot"""
from __future__ import annotations
import os
from dataclasses import dataclass
from dotenv import load_dotenv
load_dotenv()

@dataclass(frozen = True)
class Settings:
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "gemma3:4b")
    embed_model: str = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    top_k: int = int(os.getenv("TOP_K", "8"))
    max_tokens: int = int(os.getenv("NUM_PREDICT", "1024"))  # Reduced for smaller model

    ## llm decoding defaults
    temperature: float = float(os.getenv("TEMPERATURE", "0.2"))
    top_p: float = float(os.getenv("TOP_P", "0.9"))
    num_ctx: int = int(os.getenv("NUM_CTX", "16384"))  # Increased to 16k for better context
    
    # Token budget settings (for context management)
    max_prompt_tokens: int = int(os.getenv("MAX_PROMPT_TOKENS", "12000"))  # Reserve ~4k for output
    max_evidence_chars: int = int(os.getenv("MAX_EVIDENCE_CHARS", "8000"))  # Per-call evidence limit
    chars_per_token: float = float(os.getenv("CHARS_PER_TOKEN", "3.5"))  # Approx chars per token

SETTINGS = Settings()
