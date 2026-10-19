"""Terminal entry point for the news summarizer."""

from summarizer import summarize_articles


def display_results(result):
    """Display article results and token totals without making API calls."""
    if not result["articles"]:
        print("Keine Artikel mit verwertbarem Text gefunden.")

    for number, article in enumerate(result["articles"], start=1):
        print(f"\n{number}. {article['title'] or 'Ohne Titel'}")
        print("Link:", article["url"] or "Nicht vorhanden")
        print("Zusammenfassung:", article["summary"])
        print("Stimmung:", article["sentiment"])
        print("-" * 60)

    print("\nTOKENVERBRAUCH")
    for provider, tokens in result["usage"].items():
        total = tokens["input_tokens"] + tokens["output_tokens"]
        print(f"{provider.upper()}: Input {tokens['input_tokens']:g} | "
              f"Output {tokens['output_tokens']:g} | Gesamt {total:g}")
    print("Tokenzahlen sind keine Geldkosten; diese werden noch nicht berechnet.")


def main():
    print("News Summarizer - OpenAI und Cohere")
    topic = input("Nach welchem Thema moechtest du suchen? ").strip()

    if not topic:
        print("Bitte gib ein Suchthema ein.")
        return

    print("Artikel werden geladen und analysiert ...")
    result = summarize_articles(topic)
    display_results(result)


if __name__ == "__main__":
    main()
