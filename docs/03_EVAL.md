# 03. Оценка качества

Статус: черновик M0. Методика и результаты заполняются в M3-T5.

## Планируемые метрики (AGENTS.md, 2.4 и M3)

- `accuracy` по gold-набору ≥ 40 вопросов;
- `hallucinated_id_rate = 0`;
- `refusal_correctness ≥ 90%`;
- латентность p50/p95, prompt_tokens, VRAM peak;
- распределение категорий: `catalog_type` 10, `catalog_prop` 8, `list` 4,
  `compare` 6, `principle` 5, `methodology` 4, `environment` 3,
  `negative/out_of_scope` 6.

Инструмент: `tools/run_eval.py` (появится в M3-T2), отчёты — `eval/reports/`.
