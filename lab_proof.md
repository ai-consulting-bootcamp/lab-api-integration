# Multi-Provider News Summarizer — Lab Proof
## Workflow
El usuario indica cuántas noticias quiere procesar, entre 3 y 5. El programa obtiene noticias sobre IA responsable mediante News API. OpenAI resume el título, la descripción y el fragmento disponible en hasta 60 palabras; después, Cohere clasifica el sentimiento del resumen. Al final, el usuario recibe el título, el enlace, el resumen, el sentimiento, los proveedores utilizados, los tokens y los costes estimados.
## Configuration

- [Environment template](.env.example)
- [Configuration validation](config.py)
- [Provider routing, retries and cost controls](llm_providers.py)

## Execution evidence

- [Input article — first single-article run](evidence/input_article.json)
- [Output record — same single-article run](evidence/output_record.json)
- [Terminal trace — separate three-article run](evidence/main_run.txt)

## Tests

- [Test code](test_summarizer.py)
- [Saved pytest results](evidence/pytest_results.txt)

## First failure to monitor
gastar más de lo previsto es un riesgo por ello debemos de comparar el coste diario acumulado y la estimación de la próxima llamada con DAILY_BUDGET y si la suma supera el presupuesto, debemos bloquear la llamada si no queda presupuesto suficiente.
El coste es estimado: los intentos fallidos sin datos de consumo pueden hacer que el gasto real sea mayor que el registrado.

## Known limitations
Los resúmenes usan fragmentos; no disponemos siempre del artículo completo.
Las validaciones de longitud y sentimiento no comprueban la exactitud de los hechos.
El presupuesto es estimado y su archivo admite una sola ejecución del programa a la vez.
El intervalo entre llamadas es fijo y los errores 429 no tienen recuperación automática.