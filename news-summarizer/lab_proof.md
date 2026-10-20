# Lab 19 – Proof of work

Project: News Summarizer (OpenAI + Cohere with retries, fallback and cost tracking).
Repository: https://github.com/jaimegmarquerie-ui/news-summarizer

## 1. Workflow / configuration
Files: `config.py`, `news_api.py`, `llm_providers.py`, `summarizer.py`, `main.py`, `test_summarizer.py`, `.env.example`, `.gitignore`, `requirements.txt`, `README.md`.

Settings used: `MAX_RETRIES=3`, `REQUEST_TIMEOUT=30`, `DAILY_BUDGET=5.00`, models `gpt-4o-mini` (OpenAI) and `command-r-08-2024` (Cohere).

Flow: NewsAPI → remove duplicates → summary (OpenAI, fallback Cohere) → sentiment (Cohere, fallback OpenAI) → cost report.

## 2. Execution trace (fallback)
Command: `python llm_providers.py fallback`

```
  ✗ openai falló: NotFoundError: Error code: 404 - {'error': {'message': 'The model `modelo-que-no-existe` does not exist or you do not have access to it.', 'type': 'invalid_request_error', 'param': None, 'code': 'model_not_found'}}
Respondió cohere (fallback=True): ¡Hola, cómo estás hoy!

--- Resumen de costes ---
cohere  command-r-08-2024    entrada=  207 salida=   10 coste=$0.000037
TOTAL: $0.000037 de $5.00 de presupuesto diario
```

What this shows: The primary provider is forced to fail (a nonexistent model returns a 404, a permanent error that is not retried), and the app falls back to Cohere, which answers; the cost of that single call is tracked ($0.000037).

## 3. Input payload (one article from NewsAPI)
```json
{
  "title": "Hackers Use AI Agents to Do Hacking for Them",
  "source": "pymnts.com",
  "description": "New research shows the growing use of AI-powered hacking systems in cybercrime operations. The trend was uncovered in an investigation by cybersecurity firm NorForge, findings from which were published Monday (Oct. 19). The company’s investigation into public…",
  "url": "https://www.pymnts.com/news/artificial-intelligence/2026/hackers-use-ai-agents-to-do-hacking-for-them/"
}
```

## 4. Output record (same article, processed)
Command: `python summarizer.py 1`

```
  ✗ openai falló: RateLimitError: Error code: 429 - {'error': {'message': 'You have no credits remaining. Add credits to continue using the API at https://platform.openai.com/settings/organization/billing/.', 'type': 'insufficient_quota', 'param': None, 'code': 'credit_balance_exhausted'}}

=== 1 de 1 noticias procesadas correctamente ===

✓ 1. Hackers Use AI Agents to Do Hacking for Them
   Resumen (cohere): Los hackers están utilizando agentes de inteligencia artificial para llevar a cabo actividades de piratería informática, según una investigación publicada por la empresa de ciberseguridad NorForge. Este nuevo método, cada vez más popular, revela una tendencia preocupante en las operaciones de ciberdelincuencia.
   Sentimiento (cohere): negativo

--- Resumen de costes ---
cohere  command-r-08-2024    entrada=  284 salida=   57 coste=$0.000077
cohere  command-r-08-2024    entrada=  282 salida=    4 coste=$0.000045
TOTAL: $0.000121 de $5.00 de presupuesto diario
```

What this shows: OpenAI has no credit (429 `insufficient_quota`), so it is not retried and Cohere does both tasks: a Spanish summary of the article and a sentiment label (negativo). The summary call costs more ($0.000077, 57 output tokens) than the sentiment call ($0.000045, 4 output tokens), for a total of $0.000121.

## 5. Tests
Command: `pytest test_summarizer.py -v` → **14 passed**. (Screenshot attached in the submission.)
