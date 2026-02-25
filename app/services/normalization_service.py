import hashlib
from urllib.parse import urlparse


class NormalizationService:
    @staticmethod
    def normalize(raw):
        title = raw.get("title", "").strip()
        snippet = raw.get("snippet", "").strip()
        url = raw.get("funding_link", "").strip()

        domain = urlparse(url).netloc if url else "unknown"

        normalized_hash = hashlib.sha256(f"{title.lower().str}")
