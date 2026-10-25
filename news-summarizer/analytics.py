from collections import Counter
import re

STOP_WORDS = {
    "the", "and", "for", "that", "with", "this", "from", "are",
    "was", "were", "has", "have", "had", "will", "its", "into",
    "about", "after", "before", "over", "under", "their", "they",
    "you", "your", "not", "but", "said", "says", "than", "then",
    "new", "more", "also", "could", "would", "been", "being"
}

def trending_topics(articles, top_n=10):
    """Rank recurring keywords across article titles and summaries."""
    counts = Counter()

    for article in articles:
        text = (
            f"{article.get('title', '')} "
            f"{article.get('description', '')} "
            f"{article.get('summary', '')}"
        )
        words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
        counts.update(word for word in words if word not in STOP_WORDS)

    return counts.most_common(top_n)
