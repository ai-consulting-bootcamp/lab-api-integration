from news_api import fetch_latest_news
from llm_providers import ask_with_fallback, cost_tracker
from config import get_config

class NewsSummarizer:
    """Orchestrates the fetching, summarizing, and sentiment analysis of news."""
    
    def __init__(self):
        self.config = get_config()

    def process_articles(self, limit=2):
        print(f"Fetching top {limit} articles...")
        articles = fetch_latest_news(limit)
        
        if not articles:
            print("No articles fetched. Check your News API configuration.")
            return []
            
        processed_results = []
        
        for index, article in enumerate(articles, 1):
            print(f"\nProcessing Article {index}/{len(articles)}: {article['title']}")
            
            # 1. Summarization Transform (Primary: OpenAI)
            summary_prompt = f"Summarize the following news article in exactly 2 sentences. Article: {article['content']}"
            print("   -> Requesting summary...")
            summary, summary_source = ask_with_fallback(summary_prompt, primary="openai")
            
            # 2. Sentiment Transform (Primary: Cohere)
            sentiment_prompt = f"Analyze the sentiment of this text. Respond with EXACTLY ONE WORD (Positive, Negative, or Neutral). Text: {summary}"
            print("   -> Requesting sentiment analysis...")
            sentiment, sentiment_source = ask_with_fallback(sentiment_prompt, primary="cohere")
            
            processed_results.append({
                "title": article['title'],
                "source": article['source'],
                "summary": summary,
                "sentiment": sentiment,
                "summary_provider": summary_source,
                "sentiment_provider": sentiment_source
            })
            
        return processed_results

# Checkpoint 4: Run this file directly to test the full data flow
if __name__ == "__main__":
    summarizer = NewsSummarizer()
    results = summarizer.process_articles(limit=2)
    
    if results:
        print("\n" + "="*50)
        print("✅ Checkpoint 4 passed! FINAL PIPELINE OUTPUT")
        print("="*50)
        
        for art in results:
            print(f"\nTitle: {art['title']}")
            print(f"Summary ({art['summary_provider']}): {art['summary']}")
            print(f"Sentiment ({art['sentiment_provider']}): {art['sentiment']}")
            
        print("\n" + "="*50)
        print("COST ANALYSIS")
        print("="*50)
        print(f"Total simulated cost: ${cost_tracker['total_cost']:.4f}")
        print(f"OpenAI Calls: {cost_tracker['openai_calls']}")
        print(f"Cohere Calls: {cost_tracker['cohere_calls']}")