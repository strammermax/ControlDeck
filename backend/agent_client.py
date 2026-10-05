"""Client for the local ControlDeck agent proxy (Unix socket). The web app never holds the SSH key."""
import json
import os
import socket

SOCKET = "/run/controldeck-agent/agent.sock"


class AgentUnavailable(Exception):
    """The proxy is not installed or not running; the message is safe to show."""


def proxy_request(request, timeout=75):
    path = os.environ.get("CONTROLDECK_AGENT_SOCKET", SOCKET)
    if not hasattr(socket, "AF_UNIX"):
        raise AgentUnavailable("De agent-proxy is alleen op Linux beschikbaar.")
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(timeout)
            connection.connect(path)
            connection.sendall((json.dumps(request) + "\n").encode())
            data = b""
            while not data.endswith(b"\n"):
                chunk = connection.recv(65536)
                if not chunk:
                    break
                data += chunk
                if len(data) > 1024 * 1024:
                    raise AgentUnavailable("Antwoord van de agent-proxy is te groot.")
    except (FileNotFoundError, ConnectionRefusedError):
        raise AgentUnavailable("De agent-proxy draait niet. Voer als root bash scripts/install-wizard.sh uit.") from None
    except PermissionError:
        raise AgentUnavailable("ControlDeck heeft geen toegang tot de agent-proxy (herstart ControlDeck na install-wizard.sh).") from None
    except (OSError, socket.timeout):
        raise AgentUnavailable("De agent-proxy antwoordt niet.") from None
    try:
        response = json.loads(data)
        if not isinstance(response, dict) or "ok" not in response:
            raise ValueError
        return response
    except ValueError:
        raise AgentUnavailable("Ongeldig antwoord van de agent-proxy.") from None
