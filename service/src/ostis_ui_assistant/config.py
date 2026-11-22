"""Конфигурация сервиса из .env."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- LLM ---
    llm_backend: Literal["ollama", "openai"] = "ollama"
    llm_base_url: str = "http://127.0.0.1:11434"
    llm_model: str = "qwen3.5:4b"
    llm_api_key: str = ""
    llm_num_ctx: int = 8192
    llm_temperature: float = 0.2
    llm_top_p: float = 0.9
    llm_think: bool = False
    llm_keep_alive: str = "30m"
    # Интерактивный таймаут меньше 30 с, которые ждёт редактор (previewHtml.ts).
    llm_timeout_s: float = 25.0
    # Отдельный таймаут для eval: батч может позволить себе ждать дольше.
    llm_timeout_s_batch: float = 120.0
    llm_max_output_tokens: int = 512

    # --- Обработка запросов диалога (B0-1) ---
    dialog_worker_threads: int = 1
    dialog_queue_size: int = 16
    service_heartbeat_interval_s: float = 5.0
    service_lease_ttl_s: float = 20.0
    watchdog_max_age_minutes: int = 30

    # --- OSTIS ---
    sc_ws_url: str = "ws://127.0.0.1:8090/ws_json"
    assistant_transport: Literal["sc-memory", "direct-http"] = "sc-memory"
    knowledge_source: Literal["kb", "fallback"] = "kb"
    kb_fallback_allowed: bool = True

    # --- Сервис ---
    api_host: str = "127.0.0.1"
    api_port: int = 8770
    log_level: str = "INFO"
    prompt_version: str = "v4"

    # --- Пути ---
    knowledge_pack_path: Path = ROOT_DIR / "knowledge" / "pack.json"
    prompt_path: Path = ROOT_DIR / "knowledge" / "prompt_v4.md"
    dialog_log_path: Path = ROOT_DIR / "service" / "logs" / "dialog.jsonl"
    cors_origins: list[str] = [
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ]

    @property
    def project_root(self) -> Path:
        return ROOT_DIR

    @property
    def is_ollama(self) -> bool:
        return self.llm_backend == "ollama"
