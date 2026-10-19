from summarizer import NewsSummarizer
from llm_providers import cost_tracker

def main():
    print("📰 Welcome to the Two Brains News Summarizer!")
    print("---------------------------------------------")
    
    summarizer = NewsSummarizer()
    
    try:
        # Prompt the user for input, defaulting to 3 if they just press Enter
        limit_input = input("How many top tech articles would you like to process? (Recommended: 3-5): ")
        limit = int(limit_input) if limit_input.isdigit() else 3
        
        print(f"\n🚀 Kicking off pipeline for {limit} articles...\n")
        results = summarizer.process_articles(limit=limit)
        
        if results:
            print("\n" + "="*50)
            print("🎉 PIPELINE COMPLETE: FINAL OUTPUT")
            print("="*50)
            
            for idx, art in enumerate(results, 1):
                print(f"\n[{idx}] {art['title']} (Source: {art['source']})")
                print(f"Summary ({art['summary_provider']}): {art['summary']}")
                print(f"Sentiment ({art['sentiment_provider']}): {art['sentiment']}")
                
            print("\n" + "="*50)
            print("💸 FINAL COST ANALYSIS")
            print("="*50)
            print(f"Total simulated cost: ${cost_tracker['total_cost']:.4f}")
            print(f"OpenAI Calls: {cost_tracker['openai_calls']}")
            print(f"Cohere Calls: {cost_tracker['cohere_calls']}\n")

    except KeyboardInterrupt:
        print("\n\nPipeline cancelled by user.")
    except Exception as e:
        print(f"\n❌ An unexpected error occurred: {e}")

# Checkpoint 6: Run this file to test the full interactive app
if __name__ == "__main__":
    main()