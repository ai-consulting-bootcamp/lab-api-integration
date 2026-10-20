import sys

from news_api import fetch_news, NewsAPIError
from llm_providers import ask, CostTracker, ProviderError, BudgetExceededError

# Plantillas de prompt: texto fijo + datos que se insertan en tiempo de ejecución
SUMMARY_TEMPLATE = (
    "Resume en español, en 2 frases, esta noticia.\n\n"
    "Título: {title}\nDescripción: {description}"
)
SENTIMENT_TEMPLATE = (
    "Clasifica el sentimiento de este texto. Responde con UNA sola palabra: "
    "positivo, neutral o negativo.\n\nTexto: {text}"
)
VALID_SENTIMENTS = {"positivo", "neutral", "negativo"}
MAX_DESCRIPTION_CHARS = 500  # tope por noticia: una descripción enorme no se come el presupuesto del resto


def remove_duplicates(articles):
    """Quita noticias con el mismo título (ignorando mayúsculas y espacios) para no pagar dos veces."""
    seen, unique = set(), []
    for article in articles:
        key = article["title"].strip().lower()
        if key not in seen:
            seen.add(key)
            unique.append(article)
    return unique


def summarize_article(article, tracker):
    """Resume una noticia con OpenAI (respaldo: Cohere). Devuelve texto y proveedor usado."""
    description = (article["description"] or "(sin descripción)")[:MAX_DESCRIPTION_CHARS]
    prompt = SUMMARY_TEMPLATE.format(title=article["title"], description=description)
    result = ask(prompt, primary="openai", secondary="cohere", tracker=tracker)
    return result["text"].strip(), result["provider"]


def analyze_sentiment(summary, tracker):
    """Clasifica el sentimiento del resumen con Cohere (respaldo: OpenAI)."""
    result = ask(SENTIMENT_TEMPLATE.format(text=summary), primary="cohere", secondary="openai", tracker=tracker)
    word = result["text"].strip().lower().strip(".")
    return (word if word in VALID_SENTIMENTS else "indefinido"), result["provider"]


def summarize_news(count=2, tracker=None):
    """Obtiene `count` noticias y devuelve una lista con el resultado de cada una."""
    tracker = tracker or CostTracker()
    results = []
    for article in remove_duplicates(fetch_news("technology", page_size=count)):
        entry = {"title": article["title"], "status": "ok", "summary": None,
                 "sentiment": None, "summary_by": None, "sentiment_by": None, "error": None}
        try:
            entry["summary"], entry["summary_by"] = summarize_article(article, tracker)
            entry["sentiment"], entry["sentiment_by"] = analyze_sentiment(entry["summary"], tracker)
        except BudgetExceededError as error:
            entry.update(status="omitida", error=str(error))
            results.append(entry)
            break  # sin presupuesto, no se sigue
        except ProviderError as error:
            entry.update(status="error", error=str(error))  # una noticia fallida no para a las demás
        results.append(entry)
    return results, tracker


def print_report(results, tracker):
    """Muestra qué noticias salieron bien y cuáles no, y el coste total."""
    ok = [r for r in results if r["status"] == "ok"]
    print(f"\n=== {len(ok)} de {len(results)} noticias procesadas correctamente ===")
    for number, r in enumerate(results, start=1):
        mark = "✓" if r["status"] == "ok" else "✗"
        print(f"\n{mark} {number}. {r['title']}")
        if r["status"] == "ok":
            print(f"   Resumen ({r['summary_by']}): {r['summary']}")
            print(f"   Sentimiento ({r['sentiment_by']}): {r['sentiment']}")
        else:
            print(f"   {r['status'].upper()}: {r['error']}")
    tracker.print_summary()


if __name__ == "__main__":
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    try:
        results, tracker = summarize_news(count)
    except NewsAPIError as error:
        sys.exit(f"No se pudieron obtener noticias: {error}")
    print_report(results, tracker)
