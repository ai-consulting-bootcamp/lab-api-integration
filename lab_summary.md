
# Lab Summary — Two Brains, Zero Single Point of Failure

## Objective

Build a news summarization application that integrates multiple AI providers and remains functional when its primary summarization provider fails.

## Implementation

The application integrates three services:

1. NewsAPI for article retrieval.
2. OpenAI GPT-4o-mini for article summarization.
3. Cohere Command A for sentiment analysis and fallback summarization.

The original lab referenced Anthropic. Cohere was used instead with instructor approval.

## Reliability

A retry decorator provides exponential backoff.

When OpenAI summarization fails, the application attempts summarization using Cohere.

A daily spending tracker records estimated API costs and prevents new requests after the configured budget is reached.

## Testing

Three automated tests passed:

- Cost calculation
- Successful OpenAI summarization
- Cohere fallback when OpenAI fails

## Results

The application successfully retrieved a technology article, summarized it with OpenAI, analyzed sentiment with Cohere, and recorded estimated token costs.

Latest recorded daily spending: $0.003080.

## Lessons Learned

- Integrating multiple AI providers
- Handling API failures and fallback behavior
- Using token usage to estimate costs
- Building automated tests with pytest
- Protecting API credentials with environment variables

## Future Improvements

- More comprehensive retry and fallback tests
- Strict pre-request budget reservations
- Rate limiting
- Persistent structured article output
- Improved article text retrieval
