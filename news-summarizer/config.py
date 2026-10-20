import os
import sys
from dotenv import load_dotenv

load_dotenv()

# --- Ajustes (llegan como texto; se convierten al tipo correcto) ---
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))
DAILY_BUDGET = float(os.getenv("DAILY_BUDGET", "5.00"))

# --- Claves (solo se leen; nunca se imprimen) ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
COHERE_API_KEY = os.getenv("COHERE_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")

REQUIRED_KEYS = {
    "OPENAI_API_KEY": OPENAI_API_KEY,
    "COHERE_API_KEY": COHERE_API_KEY,
    "NEWS_API_KEY": NEWS_API_KEY,
}


def missing_keys():
    """Devuelve los nombres de las claves que no existen o están vacías."""
    return [name for name, value in REQUIRED_KEYS.items() if not value]


def validate():
    """Para si falta alguna clave, diciendo cuáles (sin mostrar ningún valor)."""
    missing = missing_keys()
    if missing:
        raise RuntimeError(
            "Faltan claves en el archivo .env: " + ", ".join(missing)
            + ". Añádelas y guarda el archivo (Ctrl+S)."
        )


if __name__ == "__main__":
    print(f"Entorno: {ENVIRONMENT} | reintentos: {MAX_RETRIES} | "
          f"timeout: {REQUEST_TIMEOUT}s | presupuesto diario: ${DAILY_BUDGET}")
    for name, value in REQUIRED_KEYS.items():
        print(f"  {name}: {'OK' if value else 'FALTA'}")
    try:
        validate()
        print("Configuración válida.")
    except RuntimeError as error:
        print("ERROR:", error)
        sys.exit(1)
