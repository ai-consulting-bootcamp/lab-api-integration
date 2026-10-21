# Multi-Provider News Summarizer

Fetches recent articles from AskNews (asknews.app), summarizes each article with **OpenAI**, then passes that summary to **Cohere** for sentiment analysis (Cohere replaces Anthropic from the training). If one provider fails after its retries, the other one takes over, so there is no single point of failure.

```
AskNews (input) -> OpenAI summary -> Cohere sentiment -> console + output/run_<timestamp>.json
                    fallback: Cohere      fallback: OpenAI
```

## Features

| Requirement | Where |
|---|---|
| Environment-based configuration | `config.py` `Config` |
| External data source (AskNews) | `news_api.py` `fetch_news` |
| OpenAI summary passed to Cohere sentiment | `summarizer.py` `NewsSummarizer` |
| Fallback between providers | `LLMProviders.ask_with_fallback` |
| Retry with exponential backoff + jitter | `ProductionAPIClient` |
| Circuit breaker | `CircuitBreaker` | API Fundamentals, section 3 |
| Cost tracking from exact API token counts | `TokenBudgetManager` |
| Rate limiting (per provider and AskNews) | `RateLimiter` |
| Unit tests (all APIs mocked) | `test_summarizer.py` |

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env      # then add your OpenAI, Cohere and AskNews keys
python config.py          # validates configuration
```

## Run

```bash
python main.py                                   # interactive
python main.py --category technology --count 3   # non-interactive
pytest test_summarizer.py -v                     # tests, no API keys needed
```

Each module also runs on its own as a checkpoint: `python news_api.py`, `python llm_providers.py`, `python summarizer.py`.

## Example output

From a real run (`python main.py --category technology --count 3`):

```
============================================================
RESULTS
============================================================

1. 5 Emerging AI Technologies Reshaping Digital Search
   Source: uktechnews.co.uk
   📝 Summary (openai): As of October 20, 2026, digital search is being transformed by five emerging AI technologies that change how businesses manage digital visibility and SEO. Key developments include generative AI search engines, multimodal search technology, retrieval-augmented generation (RAG), conversational search, and AI-powered personalisation, all of which enhance user interaction and content strategies while necessitating a focus on privacy and credible information. Businesses are encouraged to explore how these advancements can be integrated into their broader marketing strategies with the assistance of specialist digital marketing companies like 'theaiseoagency.io'.
   🎭 Sentiment (cohere): 1. Sentiment: Positive. 

2. The news summary highlights innovative AI technologies that revolutionize digital search, offering enhanced user experiences and strategic advantages for businesses, presenting a generally optimistic outlook on the future of digital marketing.

2. Young Indian Innovators Drive Automation and AI Beyond Metros
   Source: aninews.in
   📝 Summary (openai): On October 20, 2026, ANI News highlighted young innovators in India's smaller cities who are advancing automation and AI technologies. In Jodhpur, Narayan Jangid's Robo AI Hub develops custom machines for industries like jewellery and agriculture, while in Dombivli, Virendra Palan's Leela Electronics has created indigenous ultrasonic cleaning technology to replace imported equipment. These initiatives reflect a growing trend of homegrown engineering solutions aligned with the 'Make in India' vision.
   🎭 Sentiment (cohere): 1. Sentiment: Positive. 

2. The news summary celebrates the innovative spirit and practical applications of AI and automation in India's smaller cities, highlighting how these initiatives contribute to the country's self-reliance and economic growth.

3. AI Specialists Warn of 'Progressive Dispossession' and Skill Loss
   Source: lesnumeriques.com
   📝 Summary (openai): A CBS News investigation published on October 19, 2026, reveals concerns from AI specialists about the societal risks of relying on autonomous AI assistants, warning of a phenomenon called 'progressive dispossession,' which leads to a loss of human capability as organizations replace labor with machines. A survey found that one in five American workers delegates tasks to AI, with a significant portion accepting machine-generated content without modification. Experts advocate for 'strategic friction' to keep humans involved in decision-making, while calls for a slowdown in AI development grow among industry professionals.
   🎭 Sentiment (cohere): 1. Sentiment: Negative.
2. The news summary highlights concerns and potential negative consequences of over-reliance on AI, suggesting a loss of human skills and capabilities, which evokes a negative sentiment.

============================================================
TOKEN BUDGET SUMMARY
============================================================
Daily Budget: $5.00
Used: $0.0006 (0.0%)
Remaining: $4.9994

Provider Breakdown:

  OPENAI:
    Input tokens: 1,861
    Output tokens: 321
    Total cost: $0.0005

  COHERE:
    Input tokens: 427
    Output tokens: 133
    Total cost: $0.0001
============================================================

💾 Results saved to output/run_20261021_131225.json
```

## Cost analysis

Each article makes two calls: one summary (about 150-250 input tokens, 50-100 output) and one sentiment check (about 100-150 input tokens, 30-60 output). Using the prices in `TokenBudgetManager` (USD per 1M tokens: gpt-4o-mini 0.15 / 0.60, Cohere command-r-08-2024 0.15 / 0.60), one article costs roughly **$0.0001**, so 1,000 articles a day cost about $0.10. Both providers are priced the same per token, so cost follows prompt length. A Cohere trial key is free but rate-limited. Ways to reduce cost: cap output length, cache already-processed URLs, or switch to a smaller model when the budget is tight.

**Actual run:** 3 articles processed, total cost $0.000616 (about $0.000205 per article), 0.012% of the $5.00 daily budget.

**Verify prices** on the OpenAI and Cohere pricing pages and update `TokenBudgetManager.pricing` if they differ.
