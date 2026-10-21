# Companion Guide: `main.py` (Your First AI API)


---

## The big picture

`main.py` turns an OpenAI call into an **API**: a URL that anyone (a teammate, a website, n8n) can send text to and get a summary back, without touching your code.

```
Caller (Swagger / n8n / app / script)
        │  POST /summarise   {"text": "...", "max_words": 20}
        ▼
┌──────────────── main.py ────────────────┐
│ 1. Check the request matches the form   │
│ 2. Reject empty text                    │
│ 3. Ask OpenAI to summarise              │
│ 4. Send back the answer in a fixed form │
└─────────────────────────────────────────┘
        │  {"summary": "...", "word_count": 12}
        ▼
Caller
```

---

## How to run it

```powershell
uvicorn main:app --reload
```

| Part | Meaning |
|---|---|
| `uvicorn` | The web server that runs your API and keeps it listening |
| `main` | The file name, **without** `.py` |
| `:app` | The variable inside the file that holds the FastAPI app (a **colon**, not a dot) |
| `--reload` | Restart automatically every time you save the file |

> ⚠️ `python main.py` does **nothing visible**. It defines the app and exits. You need `uvicorn` to actually serve it.
> For a file called `main1.py`: `uvicorn main1:app --reload`

Then open **http://127.0.0.1:8000/docs**.
Leave the terminal open; the server lives there, and so do its error messages.

---

## Block 1: Imports

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv
import os
```

The new pieces today:

| Import | What it's for |
|---|---|
| `FastAPI` | Creates the API |
| `HTTPException` | Sends a clean error back to the caller (with a status code) |
| `BaseModel` | Defines the **forms** for what comes in and what goes out |

The rest (`OpenAI`, `load_dotenv`, `os`) you know from the earlier labs.

---

## Block 2: Key and OpenAI client

```python
load_dotenv()
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
```

Same as in your labs. One thing to notice: the client is created **once, when the server starts**, and then reused for every request.

> 💡 If the key is wrong, the server still **starts fine**. The error only appears when `/summarise` is called (as a **500** error in the browser and a `401` in the terminal).

---

## Block 3: Create the app

```python
app = FastAPI(title="AI API", version="1.0")
```

- `app` is **your API**. It's the object uvicorn runs (`main:app`).
- `title` and `version` appear at the top of the `/docs` page.

---

## Block 4: The forms (Pydantic models)

```python
class SummariseRequest(BaseModel):
    text: str
    max_words: int = 100

class SummariseResponse(BaseModel):
    summary: str
    word_count: int
```

Think of these as an **order form** and a **receipt**.

| Model | Field | Rule |
|---|---|---|
| `SummariseRequest` (what the caller sends) | `text` | **Required**, must be text |
| | `max_words` | **Optional**, defaults to `100` |
| `SummariseResponse` (what we send back) | `summary` | Always text |
| | `word_count` | Always a number |

What FastAPI does with these **automatically**:
- Checks every incoming request. Missing `text`, or `"max_words": "twenty"` → **422** error, and your function never runs.
- Shows example forms in `/docs`.

> These two classes are the **contract** between your API and anyone who uses it.

---

## Block 5: Health check endpoint

```python
@app.get("/health")
def health():
    return {"status": "ok"}
```

A "doorbell": if it answers, the API is running.

| Part | Meaning |
|---|---|
| `@app.get("/health")` | "When someone sends a **GET** request to `/health`, run the function below." This line is a **decorator**. |
| `return {...}` | A Python dictionary, which FastAPI turns into JSON for you |

🧪 Open **http://127.0.0.1:8000/health** in your browser → `{"status":"ok"}`

---

## Block 6: The summarise endpoint

```python
@app.post("/summarise", response_model=SummariseResponse)
def summarise(request: SummariseRequest):
```

| Part | Meaning |
|---|---|
| `@app.post("/summarise")` | Listens for **POST** requests at `/summarise` |
| `request: SummariseRequest` | The incoming JSON must match the request form. By the time your code runs, it's already been checked. |
| `response_model=SummariseResponse` | What we return must match the response form |

**Why POST and not GET?** The caller is **sending data** (the text) in the request body. A browser address bar can only send GET, which is why opening `/summarise` in the browser gives **405 Method Not Allowed**.
👉 Test it in **Swagger** (`/docs` → POST /summarise → *Try it out* → *Execute*).

---

## Block 7: Reject empty text

```python
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="text cannot be empty")
```

- `.strip()` removes spaces, so `"    "` also counts as empty.
- Pydantic only checks that `text` **is a string**. `""` is a valid string, so we have to check this ourselves.
- **400** = "the caller sent something bad". We stop **before** paying for an OpenAI call.

---

## Block 8: Ask OpenAI

```python
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system",
             "content": f"Summarise the following text in {request.max_words} words or fewer."},
            {"role": "user", "content": request.text}
        ]
    )
```

A normal chat completion, like in your labs. What's new is **where the values come from**:
- `request.max_words` goes into the **system** instruction.
- `request.text` becomes the **user** message.

> 💡 The caller only controls the text and the word limit. **The prompt itself stays inside your API.** That's one of the main reasons to wrap an LLM in an API.

---

## Block 9: Send back the answer

```python
    summary = response.choices[0].message.content.strip()
    return SummariseResponse(summary=summary, word_count=len(summary.split()))
```

- Take the text out of OpenAI's reply.
- `len(summary.split())` is a rough word count (it splits on spaces).
- Return it in the **response form** → FastAPI converts it to JSON.

> 💡 `word_count` lets the caller check whether the model respected the limit. LLMs don't always obey.

---

## Your API at a glance

| Endpoint | Method | Full URL | Try it in the browser? |
|---|---|---|---|
| `/health` | GET | `http://127.0.0.1:8000/health` | ✅ Yes |
| `/summarise` | POST | `http://127.0.0.1:8000/summarise` | ❌ No, use `/docs` |
| `/docs` | GET | `http://127.0.0.1:8000/docs` | ✅ Free from FastAPI (Swagger UI) |
| `/openapi.json` | GET | `http://127.0.0.1:8000/openapi.json` | ✅ Free, a machine-readable description of your API |

---

## Status codes you'll meet today

| Code | Meaning | Typical cause |
|---|---|---|
| **200** | OK | Everything worked |
| **400** | Bad Request | Empty text (our own check in Block 7) |
| **404** | Not Found | Wrong path, e.g. `/helth` |
| **405** | Method Not Allowed | Right path, wrong method (opening `/summarise` in the browser) |
| **422** | Unprocessable Entity | JSON doesn't match the form (missing `text`, wrong type) |
| **500** | Internal Server Error | The server crashed (e.g. wrong API key). **Look at the uvicorn terminal.** |

---

## Common mistakes

1. Running `python main.py` instead of `uvicorn main:app --reload`
2. Typing `uvicorn main.py:app` or `uvicorn main.app` (no `.py`, and use a colon)
3. Opening `/summarise` in the browser → 405
4. Running uvicorn from the wrong folder → it can't find `main`
5. Port already in use → stop the old server (Ctrl+C) or add `--port 8001`

---

## Try it yourself

1. In Swagger, trigger each of these: **200**, **400**, **422**
2. Add a new GET endpoint `/hello` that returns `{"message": "Hello class!"}`
3. **Stretch:** add a POST `/translate` endpoint with its own request model (`text`, `target_language`) and response model (`translation`)

---

## Check yourself

1. What does `main:app` mean in the uvicorn command?
2. Why does `/health` work in the browser but `/summarise` doesn't?
3. What's the difference between a **422** and a **400** in this API?
4. Who decides the prompt: the caller or your API? Why does that matter for a client project?
