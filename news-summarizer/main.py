import config
from news_api import NewsAPIError
from summarizer import summarize_news, print_report


def ask_count():
    """Pregunta cuántas noticias procesar (1 a 5) o 'q' para salir."""
    while True:
        answer = input("\n¿Cuántas noticias de tecnología quieres resumir? (1-5, q para salir): ").strip().lower()
        if answer == "q":
            return None
        if answer.isdigit() and 1 <= int(answer) <= 5:
            return int(answer)
        print("Escribe un número del 1 al 5, o q para salir.")


def main():
    """Aplicación interactiva: comprueba la configuración y procesa noticias en bucle."""
    try:
        config.validate()
    except RuntimeError as error:
        raise SystemExit(f"ERROR: {error}")

    print(f"=== News Summarizer ({config.ENVIRONMENT}) ===")
    while True:
        count = ask_count()
        if count is None:
            print("Hasta luego.")
            break
        try:
            results, tracker = summarize_news(count)
        except NewsAPIError as error:
            print(f"No se pudieron obtener noticias: {error}")
            continue
        print_report(results, tracker)


if __name__ == "__main__":
    main()
