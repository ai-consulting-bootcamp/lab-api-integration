# Lab Proof: Multi-Provider News Summarizer

Evidence below is generated from a real run (`main.py --category technology --count 3`).

## 1. Workflow configuration

**Trigger:** `python main.py` (manual run; category + article count as input)
**Transform:** AskNews article -> OpenAI summary (fallback Cohere) -> Cohere sentiment on that summary (fallback OpenAI). Cohere replaces Anthropic from the training.
**Action / destination:** console report + JSON output record in `output/run_<timestamp>.json`

| Setting | Value | Source |
|---|---|---|
| Summary model | gpt-4o-mini | `Config.load_config` |
| Sentiment model | command-r-08-2024 (Cohere) | `Config.load_config` / `.env` COHERE_MODEL |
| Retries per call | 3 (backoff + jitter) | `.env` MAX_RETRIES |
| Circuit breaker | opens after 3 failures, 30s timeout | `LLMProviders` |
| Request timeout | 30s | `.env` REQUEST_TIMEOUT |
| Daily budget | $5.00 | `.env` DAILY_BUDGET |
| Rate limits | 50 rpm OpenAI, 10 rpm Cohere, 10 rpm AskNews | `RateLimiter` |

**Field mapping**

| Input field (AskNews) | Used for | Output field |
|---|---|---|
| title, source, summary (description), key points (content) | summary prompt | `summary`, `providers.summary` |
| `summary` (OpenAI output) | sentiment prompt | `sentiment`, `providers.sentiment` |
| token usage from both API responses | `TokenBudgetManager` | `usage`, `budget_summary` |

## 2. Execution trace

```
============================================================
📰 MULTI-PROVIDER NEWS SUMMARIZER
   OpenAI = summary | Cohere = sentiment
============================================================
📰 Fetching 3 technology articles from AskNews...
   Found 3 articles

============================================================
Article 1/3
============================================================

Step 1: Summarizing '5 Emerging AI Technologies Reshaping Digital Search'...
Trying OpenAI (primary)...
💰 Tokens: 638 input + 114 output = 752 total
   Cost: $0.000164 ($4.9998 remaining)
✓ OpenAI succeeded

Step 2: Analyzing sentiment...
Trying Cohere (primary)...
💰 Tokens: 151 input + 44 output
   Cost: $0.000049 ($4.9998 remaining)
✓ Cohere succeeded

============================================================
Article 2/3
============================================================

Step 1: Summarizing 'Young Indian Innovators Drive Automation and AI Beyond Metros'...
Trying OpenAI (primary)...
💰 Tokens: 514 input + 97 output = 611 total
   Cost: $0.000135 ($4.9997 remaining)
✓ OpenAI succeeded

Step 2: Analyzing sentiment...
Trying Cohere (primary)...
💰 Tokens: 128 input + 47 output
   Cost: $0.000047 ($4.9996 remaining)
✓ Cohere succeeded

============================================================
Article 3/3
============================================================

Step 1: Summarizing 'AI Specialists Warn of 'Progressive Dispossession' and Skill Loss'...
Trying OpenAI (primary)...
💰 Tokens: 709 input + 110 output = 819 total
   Cost: $0.000172 ($4.9994 remaining)
✓ OpenAI succeeded

Step 2: Analyzing sentiment...
Trying Cohere (primary)...
💰 Tokens: 148 input + 42 output
   Cost: $0.000047 ($4.9994 remaining)
✓ Cohere succeeded

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

## 3. Input payload (one article)

Source file: `output/run_20261021_131225.json`

```json
{
  "title": "5 Emerging AI Technologies Reshaping Digital Search",
  "source": "uktechnews.co.uk",
  "description": "As of October 20, 2026, digital search is undergoing a significant transformation driven by five emerging AI technologies, reshaping how businesses approach digital visibility and SEO. According to a UK Tech News article, the key developments include: 1. Generative AI Search Engines: AI-powered systems using large language models (LLMs) now produce detailed, conversational responses by synthesizing information from multiple sources, making accurate and credible content essential for inclusion. 2. Multimodal Search Technology: This enables systems to process text, images, audio, and video, allowing users to search via visual inputs like photographs, which has significant implications for ecommerce and retail. 3. Retrieval-Augmented Generation (RAG): This approach combines generative AI with external data retrieval, allowing AI to access current or specialized information from websites before generating responses, reinforcing the need for accessible and trustworthy site structures. 4. Conversational Search and Natural Language Processing: Advances allow search systems to interpret complex questions and conversational follow-ups, encouraging businesses to create detailed content like FAQs and guides rather than relying solely on short keywords. 5. AI-Powered Personalisation and Predictive Search: Machine learning enables platforms to tailor recommendations based on location, history, and interests, though this must be balanced with privacy expectations and regulations. The article notes that businesses can investigate specialist digital marketing companies, such as 'theaiseoagency.io', to assess how these technologies fit into broader strategies.",
  "content": "As of October 20, 2026, digital search is undergoing a significant transformation driven by five emerging AI technologies, reshaping how businesses approach digital visibility and SEO. According to a UK Tech News article, the key developments include: 1. Generative AI Search Engines: AI-powered systems using large language models (LLMs) now produce detailed, conversational responses by synthesizing information from multiple sources, making accurate and credible content essential for inclusion. 2. Multimodal Search Technology: This enables systems to process text, images, audio, and video, allowing users to search via visual inputs like photographs, which has significant implications for ecommerce and retail. 3. Retrieval-Augmented Generation (RAG): This approach combines generative AI with external data retrieval, allowing AI to access current or specialized information from websites before generating responses, reinforcing the need for accessible and trustworthy site structures. 4. Conversational Search and Natural Language Processing: Advances allow search systems to interpret complex questions and conversational follow-ups, encouraging businesses to create detailed content like FAQs and guides rather than relying solely on short keywords. 5. AI-Powered Personalisation and Predictive Search: Machine learning enables platforms to tailor recommendations based on location, history, and interests, though this must be balanced with privacy expectations and regulations. The article notes that businesses can investigate specialist digital marketing companies, such as 'theaiseoagency.io', to assess how these technologies fit into broader strategies.",
  "url": "https://uktechnews.co.uk/2026/10/20/5-emerging-ai-technologies-reshaping-digital-search/",
  "published_at": "2026-10-20T11:15:50+00:00"
}
```

## 4. Output record

```json
{
  "article": {
    "title": "5 Emerging AI Technologies Reshaping Digital Search",
    "source": "uktechnews.co.uk",
    "description": "As of October 20, 2026, digital search is undergoing a significant transformation driven by five emerging AI technologies, reshaping how businesses approach digital visibility and SEO. According to a UK Tech News article, the key developments include: 1. Generative AI Search Engines: AI-powered systems using large language models (LLMs) now produce detailed, conversational responses by synthesizing information from multiple sources, making accurate and credible content essential for inclusion. 2. Multimodal Search Technology: This enables systems to process text, images, audio, and video, allowing users to search via visual inputs like photographs, which has significant implications for ecommerce and retail. 3. Retrieval-Augmented Generation (RAG): This approach combines generative AI with external data retrieval, allowing AI to access current or specialized information from websites before generating responses, reinforcing the need for accessible and trustworthy site structures. 4. Conversational Search and Natural Language Processing: Advances allow search systems to interpret complex questions and conversational follow-ups, encouraging businesses to create detailed content like FAQs and guides rather than relying solely on short keywords. 5. AI-Powered Personalisation and Predictive Search: Machine learning enables platforms to tailor recommendations based on location, history, and interests, though this must be balanced with privacy expectations and regulations. The article notes that businesses can investigate specialist digital marketing companies, such as 'theaiseoagency.io', to assess how these technologies fit into broader strategies.",
    "content": "As of October 20, 2026, digital search is undergoing a significant transformation driven by five emerging AI technologies, reshaping how businesses approach digital visibility and SEO. According to a UK Tech News article, the key developments include: 1. Generative AI Search Engines: AI-powered systems using large language models (LLMs) now produce detailed, conversational responses by synthesizing information from multiple sources, making accurate and credible content essential for inclusion. 2. Multimodal Search Technology: This enables systems to process text, images, audio, and video, allowing users to search via visual inputs like photographs, which has significant implications for ecommerce and retail. 3. Retrieval-Augmented Generation (RAG): This approach combines generative AI with external data retrieval, allowing AI to access current or specialized information from websites before generating responses, reinforcing the need for accessible and trustworthy site structures. 4. Conversational Search and Natural Language Processing: Advances allow search systems to interpret complex questions and conversational follow-ups, encouraging businesses to create detailed content like FAQs and guides rather than relying solely on short keywords. 5. AI-Powered Personalisation and Predictive Search: Machine learning enables platforms to tailor recommendations based on location, history, and interests, though this must be balanced with privacy expectations and regulations. The article notes that businesses can investigate specialist digital marketing companies, such as 'theaiseoagency.io', to assess how these technologies fit into broader strategies.",
    "url": "https://uktechnews.co.uk/2026/10/20/5-emerging-ai-technologies-reshaping-digital-search/",
    "published_at": "2026-10-20T11:15:50+00:00"
  },
  "summary": "As of October 20, 2026, digital search is being transformed by five emerging AI technologies that change how businesses manage digital visibility and SEO. Key developments include generative AI search engines, multimodal search technology, retrieval-augmented generation (RAG), conversational search, and AI-powered personalisation, all of which enhance user interaction and content strategies while necessitating a focus on privacy and credible information. Businesses are encouraged to explore how these advancements can be integrated into their broader marketing strategies with the assistance of specialist digital marketing companies like 'theaiseoagency.io'.",
  "sentiment": "1. Sentiment: Positive. \n\n2. The news summary highlights innovative AI technologies that revolutionize digital search, offering enhanced user experiences and strategic advantages for businesses, presenting a generally optimistic outlook on the future of digital marketing.",
  "providers": {
    "summary": "openai",
    "sentiment": "cohere"
  },
  "fallback_used": false,
  "usage": {
    "summary": {
      "prompt_tokens": 638,
      "completion_tokens": 114,
      "total_tokens": 752
    },
    "sentiment": {
      "input_tokens": 151,
      "output_tokens": 44
    }
  }
}
```

## 5. Tests

```
[1m============================= test session starts ==============================[0m
platform darwin -- Python 3.11.17, pytest-9.1.1, pluggy-1.6.0 -- /opt/anaconda3/envs/bootcamp-env/bin/python
cachedir: .pytest_cache
rootdir: /Users/macbook-air/Desktop/AI consulting/Week3/Day1/lab-api-integration
plugins: langsmith-0.14.11, platformdirs-4.12.3, anyio-4.15.1
[1mcollecting ... [0mcollected 20 items

test_summarizer.py::test_config_validate_passes_with_keys [32mPASSED[0m[33m         [  5%][0m
test_summarizer.py::test_config_validate_reports_missing_keys [32mPASSED[0m[33m     [ 10%][0m
test_summarizer.py::test_config_environment_settings [32mPASSED[0m[33m              [ 15%][0m
test_summarizer.py::test_backoff_with_jitter_stays_within_bounds [32mPASSED[0m[33m  [ 20%][0m
test_summarizer.py::test_jittered_retry_recovers_from_transient_failures [32mPASSED[0m[33m [ 25%][0m
test_summarizer.py::test_budget_error_is_not_retried [32mPASSED[0m[33m              [ 30%][0m
test_summarizer.py::test_circuit_breaker_opens_and_fails_fast [32mPASSED[0m[33m     [ 35%][0m
test_summarizer.py::test_circuit_breaker_half_open_recovers [32mPASSED[0m[33m       [ 40%][0m
test_summarizer.py::test_calculate_cost_uses_exact_tokens [32mPASSED[0m[33m         [ 45%][0m
test_summarizer.py::test_track_request_updates_usage [32mPASSED[0m[33m              [ 50%][0m
test_summarizer.py::test_budget_exceeded_raises [32mPASSED[0m[33m                   [ 55%][0m
test_summarizer.py::test_fallback_used_when_primary_fails [32mPASSED[0m[33m         [ 60%][0m
test_summarizer.py::test_no_fallback_when_primary_works [32mPASSED[0m[33m           [ 65%][0m
test_summarizer.py::test_all_providers_failed [32mPASSED[0m[33m                     [ 70%][0m
test_summarizer.py::test_openai_summary_is_passed_to_cohere [32mPASSED[0m[33m       [ 75%][0m
test_summarizer.py::test_failed_article_does_not_stop_batch [32mPASSED[0m[33m       [ 80%][0m
test_summarizer.py::test_batch_stops_when_budget_used_up [32mPASSED[0m[33m          [ 85%][0m
test_summarizer.py::test_fetch_news_maps_asknews_articles [32mPASSED[0m[33m         [ 90%][0m
test_summarizer.py::test_fetch_news_returns_empty_list_on_error [32mPASSED[0m[33m   [ 95%][0m
test_summarizer.py::test_rate_limiter_waits_between_requests [32mPASSED[0m[33m      [100%][0m

[33m=============================== warnings summary ===============================[0m
../../../../../../../opt/anaconda3/envs/bootcamp-env/lib/python3.11/site-packages/asknews_sdk/dto/common.py:16
  /opt/anaconda3/envs/bootcamp-env/lib/python3.11/site-packages/asknews_sdk/dto/common.py:16: PydanticDeprecatedSince20: Support for class-based `config` is deprecated, use ConfigDict instead. Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.13/migration/
    class FilterParams(BaseModel):

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
[33m======================== [32m20 passed[0m, [33m[1m1 warning[0m[33m in 0.48s[0m[33m =========================[0m
```

## 6. Explain: first failure mode to monitor if this ran daily

**Silent fallback.** The pipeline keeps working when one provider fails, which also means a broken model ID, expired key or outage is invisible unless someone looks. I would monitor the share of records with `fallback_used: true` and alert above a set threshold (for example 10% of a day's records). A second signal is the circuit breaker opening, visible in the trace as "Circuit breaker OPEN".
