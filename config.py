import os
from dotenv import load_dotenv

load_dotenv()

def get_api_key() -> str:
    key = os.getenv("ANTHROPIC_API_KEY", "")
    if key:
        return key  # .env trouvé → on s'arrête là, jamais de st.secrets
    raise RuntimeError(
        "ANTHROPIC_API_KEY introuvable. Vérifiez votre fichier .env"
    )
