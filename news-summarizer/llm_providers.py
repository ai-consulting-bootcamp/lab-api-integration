import os
import sys
import time

from openai import OpenAI
import cohere

import config

# Modelos (se pueden cambiar desde el .env sin tocar el código)
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
COHERE_MODEL = os.getenv("COHERE_MODEL", "command-r-08-2024")

# Precio por token en dólares (OpenAI y Cohere cobran por millón de tokens).
# Comprueba los precios vigentes en la web de cada proveedor.
PRICING = {
    OPENAI_MODEL: {"input": 0.15 / 1_000_000, "output": 0.60 / 1_000_000},
    COHERE_MODEL: {"input": 0.15 / 1_000_000, "output": 0.60 / 1_000_000},
}

RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}
MIN_SECONDS_BETWEEN_CALLS = 0.5  # límite de ritmo sencillo
_last_call_time = 0.0


class BudgetExceededError(Exception):
    """Se alcanzó el presupuesto diario."""


class ProviderError(Exception):
    """Un proveedor falló definitivamente (tras sus reintentos)."""


class CostTracker:
    """Acumula tokens y dinero gastado, con los datos exactos de cada respuesta."""

    def __init__(self, daily_budget=None):
        self.daily_budget = config.DAILY_BUDGET if daily_budget is None else daily_budget
        self.spent = 0.0
        self.calls = []

    def check_budget(self):
        """Para si ya se gastó el presupuesto, ANTES de hacer otra llamada."""
        if self.spent >= self.daily_budget:
            raise BudgetExceededError(
                f"Presupuesto diario alcanzado: ${self.spent:.6f} de ${self.daily_budget:.2f}."
            )

    def record(self, provider, model, input_tokens, output_tokens):
        """Calcula el coste de una llamada y lo suma al total."""
        price = PRICING.get(model, {"input": 0.0, "output": 0.0})
        cost = input_tokens * price["input"] + output_tokens * price["output"]
        self.spent += cost
        self.calls.append((provider, model, input_tokens, output_tokens, cost))
        return cost

    def print_summary(self):
        print("\n--- Resumen de costes ---")
        for provider, model, tin, tout, cost in self.calls:
            print(f"{provider:7} {model:20} entrada={tin:5} salida={tout:5} coste=${cost:.6f}")
        print(f"TOTAL: ${self.spent:.6f} de ${self.daily_budget:.2f} de presupuesto diario")


def _rate_limit():
    """Garantiza una pausa mínima entre llamadas seguidas."""
    global _last_call_time
    wait = MIN_SECONDS_BETWEEN_CALLS - (time.time() - _last_call_time)
    if wait > 0:
        time.sleep(wait)
    _last_call_time = time.time()


def call_openai(prompt, model=None):
    """Una llamada a OpenAI. Devuelve texto y tokens en el formato común."""
    model = model or OPENAI_MODEL
    client = OpenAI(api_key=config.OPENAI_API_KEY, timeout=config.REQUEST_TIMEOUT, max_retries=0)
    response = client.chat.completions.create(model=model, messages=[{"role": "user", "content": prompt}])
    return {
        "text": response.choices[0].message.content,
        "model": model,
        "input_tokens": response.usage.prompt_tokens,
        "output_tokens": response.usage.completion_tokens,
    }


def call_cohere(prompt, model=None):
    """Una llamada a Cohere. Devuelve texto y tokens en el MISMO formato común."""
    model = model or COHERE_MODEL
    client = cohere.ClientV2(api_key=config.COHERE_API_KEY, timeout=config.REQUEST_TIMEOUT, max_retries=0)
    response = client.chat(model=model, messages=[{"role": "user", "content": prompt}])
    return {
        "text": response.message.content[0].text,
        "model": model,
        "input_tokens": int(response.usage.tokens.input_tokens or 0),
        "output_tokens": int(response.usage.tokens.output_tokens or 0),
    }


def _is_retryable(error):
    """Reintentar solo si el fallo puede ser temporal (red, saturación, 5xx)."""
    if "insufficient_quota" in str(error):
        return False  # sin saldo: esperar no lo arregla
    status = getattr(error, "status_code", None)
    return status is None or status in RETRYABLE_STATUS


def call_with_retries(call, prompt, label):
    """Llama a `call` hasta MAX_RETRIES veces, esperando 1 s, 2 s, 4 s... entre intentos."""
    last_error = None
    for attempt in range(1, config.MAX_RETRIES + 1):
        try:
            return call(prompt)
        except Exception as error:  # el SDK lanza muchos tipos; los clasificamos abajo
            last_error = error
            if not _is_retryable(error) or attempt == config.MAX_RETRIES:
                break
            pause = 2 ** (attempt - 1)
            print(f"  ! {label} falló ({type(error).__name__}); reintento {attempt}/{config.MAX_RETRIES} en {pause} s")
            time.sleep(pause)
    raise ProviderError(f"{label} falló: {type(last_error).__name__}: {last_error}")


PROVIDERS = {"openai": call_openai, "cohere": call_cohere}


def ask(prompt, primary="openai", secondary="cohere", tracker=None):
    """Pregunta al proveedor principal; si falla del todo, usa el secundario."""
    tracker = tracker or CostTracker()
    last_error = None
    for position, provider in enumerate((primary, secondary)):
        tracker.check_budget()
        _rate_limit()
        try:
            result = call_with_retries(PROVIDERS[provider], prompt, provider)
        except ProviderError as error:
            last_error = error
            print(f"  ✗ {error}")
            continue
        cost = tracker.record(provider, result["model"], result["input_tokens"], result["output_tokens"])
        return {**result, "provider": provider, "cost": cost, "used_fallback": position == 1}
    raise ProviderError(f"Fallaron los dos proveedores. Último error: {last_error}")


if __name__ == "__main__":
    tracker = CostTracker()
    if len(sys.argv) > 1 and sys.argv[1] == "fallback":
        # Demostración: el modelo de OpenAI no existe -> falla -> entra Cohere
        PROVIDERS["openai"] = lambda prompt: call_openai(prompt, model="modelo-que-no-existe")
        result = ask("Di hola en una frase.", tracker=tracker)
        print(f"Respondió {result['provider']} (fallback={result['used_fallback']}): {result['text']}")
    else:
        for name in ("openai", "cohere"):
            result = ask("Di hola en una frase.", primary=name, secondary=name, tracker=tracker)
            print(f"{name}: {result['text']}")
    tracker.print_summary()
