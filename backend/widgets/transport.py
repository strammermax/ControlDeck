"""Bounded provider transport; targets come exclusively from trusted vault configuration."""
import json
from urllib.parse import urlsplit
import requests


class ProviderError(ValueError):
    pass


def provider_url(value, allow_http=False):
    if not isinstance(value, str) or len(value) > 2048 or any(ord(c) < 33 for c in value) or "\\" in value:
        raise ProviderError("Ongeldig bronadres.")
    u = urlsplit(value)
    if u.scheme not in (["https", "http"] if allow_http else ["https"]) or not u.hostname or u.username or u.password or u.query or u.fragment or ".." in u.path.split("/"):
        raise ProviderError("Ongeldig bronadres.")
    _ = u.port
    return value.rstrip("/")


class Transport:
    def __init__(self, source):
        self.url = provider_url(source.get("url"), source.get("allowHttp") is True)
        self.session = requests.Session()
        self.source = source

    def close(self):
        self.session.close()

    def call(self, path="", method="GET", *, headers=None, raw=False, timeout=12, **kwargs):
        try:
            with self.session.request(method, self.url + path, headers=headers or {}, timeout=(4, timeout),
                                      allow_redirects=False, stream=True, verify=self.source.get("caBundle") or True, **kwargs) as response:
                if response.status_code in (401, 403):
                    raise ProviderError("De bron weigert de toegangsgegevens.")
                if response.status_code not in (200, 207):
                    raise ProviderError("De bron geeft geen geldig antwoord.")
                chunks, size = [], 0
                for chunk in response.iter_content(65536):
                    size += len(chunk)
                    if size > 2 * 1024 * 1024:
                        raise ProviderError("Het bronantwoord is te groot.")
                    chunks.append(chunk)
                body = b"".join(chunks).decode("utf-8-sig")
                return body if raw else json.loads(body)
        except (requests.RequestException, UnicodeError, json.JSONDecodeError):
            raise ProviderError("De bron is niet bereikbaar of geeft ongeldige gegevens.") from None
