# Responsible AI News Summarizer

## What it does
El usuario indica cuántas noticias quiere procesar, entre 3 y 5. El programa obtiene noticias sobre IA responsable mediante News API. OpenAI resume el título, la descripción y el fragmento disponible en hasta 60 palabras; después, Cohere clasifica el sentimiento del resumen. Al final, el usuario recibe el título, el enlace, el resumen, el sentimiento, los proveedores utilizados, los tokens y los costes estimados.

## Setup
python -m pip install -r requirements.txt
cp .env.example .env 
completar las claves en .env
## How to run
python main.py
python -m pytest test_summarizer.py -v
el usuario elige entre 3 y 5 noticias y que ejecutar la aplicación consume API.

## Example output
See the [saved output record](evidence/output_record.json) from a real single-article run. It includes the summary, sentiment, provider names, token usage, and estimated costs.

## Cost analysis
la ejecución guardada de tres noticias tuvo un coste estimado de 0.0009865 USD. El programa actual muestra el acumulado diario conocido.
## Limitations
- News API may provide truncated content. Summaries use only the available title, description, and excerpt.
- Length and sentiment-label checks do not guarantee factual accuracy.
- Costs are estimates. Failed requests without usage data may cause actual costs to exceed the recorded amount.
- The daily budget file supports one application process at a time.
- The fixed interval between calls does not guarantee compliance with every provider rate limit.
- HTTP 429 errors are reported without automatic retries.
- Fallback helps when one provider fails, but both providers can fail.

## Lab evidence
Start the review in [lab_proof.md](lab_proof.md).

- [Input article](evidence/input_article.json)
- [Output from the same single-article run](evidence/output_record.json)
- [Separate three-article execution trace](evidence/main_run.txt)
- [Saved pytest results](evidence/pytest_results.txt)
- [Learning summary](lab_summary.md)