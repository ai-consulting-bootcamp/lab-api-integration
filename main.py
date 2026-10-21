# main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

app = FastAPI(title="AI API", version="1.0")

class SummariseRequest(BaseModel):
    text: str
    max_words: int = 100

class SummariseResponse(BaseModel):
    summary: str
    word_count: int

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/summarise", response_model=SummariseResponse)
def summarise(request: SummariseRequest):
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="text cannot be empty")

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": f"Summarise the following text in {request.max_words} words or fewer."
            },
            {"role": "user", "content": request.text}
        ]
    )
    summary = response.choices[0].message.content.strip()
    return SummariseResponse(summary=summary, word_count=len(summary.split()))