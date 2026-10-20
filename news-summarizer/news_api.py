import requests

import config

NEWS_URL = "https://newsapi.org/v2/everything"


class NewsAPIError(Exception):
    """Error al obtener noticias (red, clave rechazada o respuesta inválida)."""


def fetch_news(topic, page_size=5):
    """Pide a NewsAPI artículos sobre `topic` y devuelve una lista de diccionarios."""
    try:
        response = requests.get(
            NEWS_URL,
            params={"q": topic, "pageSize": page_size, "language": "en", "sortBy": "publishedAt"},
            headers={"X-Api-Key": config.NEWS_API_KEY},  # la clave va en la cabecera, no en la URL
            timeout=config.REQUEST_TIMEOUT,
        )
    except requests.exceptions.Timeout:
        raise NewsAPIError(f"NewsAPI no respondió en {config.REQUEST_TIMEOUT} s.")
    except requests.exceptions.RequestException as error:
        raise NewsAPIError(f"No se pudo conectar con NewsAPI: {type(error).__name__}")

    if response.status_code != 200:
        raise NewsAPIError(f"NewsAPI devolvió el código {response.status_code}.")

    data = response.json()
    if data.get("status") != "ok":
        raise NewsAPIError(f"NewsAPI informa de un error: {data.get('code', 'desconocido')}")

    articles = []
    for item in data.get("articles", []):
        if not item.get("title") or item["title"] == "[Removed]":
            continue  # artículos borrados o sin título
        articles.append({
            "title": item["title"],
            "source": (item.get("source") or {}).get("name", "desconocida"),
            "description": item.get("description") or "",
            "url": item.get("url", ""),
        })
    return articles


if __name__ == "__main__":
    for number, article in enumerate(fetch_news("artificial intelligence", 3), start=1):
        print(f"{number}. {article['title']} ({article['source']})")
