"""Fetch news context from AskNews with clear input and API errors."""

from asknews_sdk import AskNewsSDK

from config import settings


class NewsFetchError(RuntimeError):
    """Raised when AskNews cannot return usable news context."""


def fetch_news(query: str, articles: int = 3) -> str:
    """Search AskNews and return prompt-ready news context.

    Raises:
        ValueError: If query or article count is invalid.
        NewsFetchError: If AskNews fails or returns no usable content.
    """
    query = query.strip()
    if not query:
        raise ValueError("Search query cannot be empty.")

    if not 1 <= articles <= 5:
        raise ValueError("Article count must be between 1 and 5.")

    if not settings.asknews_api_key:
        raise NewsFetchError("ASKNEWS_API_KEY is missing.")

    try:
        ask = AskNewsSDK(
            api_key=settings.asknews_api_key,
            scopes=["news"],
        )
        result = ask.news.search_news(query, n_articles=articles)
        context = result.as_string
    except Exception as error:
        # Keep the underlying exception available for debugging, but don't
        # print credentials or request headers to the user.
        raise NewsFetchError(
            f"AskNews request failed ({type(error).__name__}). "
            "Check API access, network connectivity, and the query."
        ) from error

    if not context or not context.strip():
        raise NewsFetchError("AskNews returned no usable news context.")

    return context


if __name__ == "__main__":
    try:
        context = fetch_news("Effect of Fed policy on the tech sector")
        print(context)
    except (ValueError, NewsFetchError) as error:
        print(f"News retrieval failed: {error}")