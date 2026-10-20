
# Lab Proof — Multi-Provider News Summarizer

## 1. Configuration

Environment: macOS, Python 3.11.17

Providers:
- NewsAPI
- OpenAI GPT-4o-mini
- Cohere Command A (`command-a-03-2025`)

Credentials are loaded from `.env` and are not included in this evidence.

Daily budget configuration: $5.00.

## 2. Input Payload

Article title:

The Witcher 3: Wild Hunt – Remastered on Nintendo Switch 2 Gets Patch 5.01 With Better Visuals and Resolution

Source: GameWatcher

URL:
https://www.gamewatcher.com/the-witcher-3-wild-hunt-remastered-on-nintendo-switch-2-gets-patch-5-01-with-better-visuals-and-resolution

The application supplied the article title, description, and available content to the summarization provider.

## 3. Execution Trace

Command:

```bash
python main.py
```

Selected number of articles: 1

Output:

```text
Trying OpenAI...
OpenAI tokens: 150 input, 57 output
OpenAI estimated cost: $0.000057
Daily estimated spending: $0.001595
Provider used: OpenAI

Cohere tokens: 574.0 input, 5.0 output
Cohere estimated cost: $0.001485
Daily estimated spending: $0.003080
```

## 4. Output Record

Summary:

Patch 5.01 for The Witcher 3: Wild Hunt – Remastered on Nintendo Switch 2 has been released, offering significant improvements to visuals and resolution. This update includes tweaks and fixes that were previously applied to other platforms, tailored specifically for the Switch 2.

Sentiment: Positive

Source: GameWatcher

Processing completed successfully.

## 5. Cost Evidence

OpenAI estimated cost: $0.000057

Cohere estimated cost: $0.001485

Combined estimated cost of this run: $0.001542

Recorded cumulative daily estimated spending: $0.003080

Costs are estimates based on configured token rates.

## 6. Fallback Evidence

The OpenAI failure scenario was previously simulated using `unittest.mock.patch` and a `RuntimeError`.

The application successfully switched to Cohere and returned a fallback summary.

## 7. Automated Test Results

Command:

```bash
python -m pytest -v
```

Results:

```text
test_cost_calculation PASSED
test_openai_success PASSED
test_openai_fallback PASSED

3 passed in 0.91s
```

## 8. Known Limitations

The current implementation does not guarantee a strict spending cap. Rate limiting is not independently implemented, and some transient API failure paths remain untested.
