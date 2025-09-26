import os

SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN")
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

DB_PATH = os.environ.get("DB_PATH", "messages.db")
INDEX_PATH = os.environ.get("INDEX_PATH", "index.faiss")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "text-embedding-3-small")
CHAT_MODEL = os.environ.get("CHAT_MODEL", "gpt-4o-mini")
TOP_K_PER_QUERY = int(os.environ.get("TOP_K_PER_QUERY", "10"))
N_QUERY_AUG = int(os.environ.get("N_QUERY_AUG", "3"))
MAX_RETURN = int(os.environ.get("MAX_RETURN", "10"))
INDEX_CHANNELS = [c.strip() for c in os.environ.get("INDEX_CHANNELS", "").split(",") if c.strip()]
