"""Network diagnostic helpers for Immich-Go GUI.

Pure Python module, Qt-free.
"""

import ipaddress
from dataclasses import dataclass
from urllib.parse import urlsplit

import requests


@dataclass
class ConnectionTestResult:
    ok: bool
    message: str
    status_code: int | None = None
    server_version: str | None = None


def is_local_host(host: str) -> bool:
    """True for localhost, .local, single-label LAN names and IP addresses."""
    host = (host or "").strip("[]").lower()
    if (
        host == "localhost"
        or host.endswith((".local", ".localhost"))
        or "." not in host
    ):
        return True
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def normalize_server_url(url: str) -> str:
    """Ensure server URL has scheme and no trailing slash.

    A bare public hostname defaults to https; LAN hosts and IPs default to
    http. An explicit http:// or https:// is kept as typed.
    """
    url = url.strip()
    if not url:
        return ""
    if not (url.startswith(("http://", "https://"))):
        host = urlsplit("//" + url).hostname or ""
        url = ("http://" if is_local_host(host) else "https://") + url
    return url.rstrip("/")


def test_immich_connection(
    server_url: str,
    api_key: str,
    skip_ssl: bool = False,
    timeout: float = 6.0,
) -> ConnectionTestResult:
    """Test connectivity and API key validity against an Immich server.

    Does not leak or log the API key.
    """
    clean_url = normalize_server_url(server_url)
    if not clean_url:
        return ConnectionTestResult(ok=False, message="Server URL is empty")

    if not api_key:
        return ConnectionTestResult(ok=False, message="API key is empty")

    target_endpoint = f"{clean_url}/api/server/about"
    headers = {
        "x-api-key": api_key,
        "Accept": "application/json",
    }

    try:
        response = requests.get(
            target_endpoint,
            headers=headers,
            verify=not skip_ssl,
            timeout=timeout,
            allow_redirects=False,  # never forward the API key to another URL
        )
        status_code = response.status_code
        if 300 <= status_code < 400:
            return ConnectionTestResult(
                ok=False,
                message=(
                    f"The server redirected to another address (HTTP {status_code}). "
                    "For safety the API key isn't sent there. Enter the server's "
                    "final address (often https://) in Server URL."
                ),
                status_code=status_code,
            )

        if status_code == 200:
            version = None
            try:
                data = response.json()
                if isinstance(data, dict):
                    version = data.get("version") or data.get("serverVersion")
            except Exception:
                pass
            msg = "Successfully connected to Immich server"
            if version:
                msg += f" (Version: {version})"
            return ConnectionTestResult(
                ok=True,
                message=msg,
                status_code=200,
                server_version=version,
            )
        elif status_code in (401, 403):
            return ConnectionTestResult(
                ok=False,
                message=f"Authentication failed (HTTP {status_code}). Please verify your API key.",
                status_code=status_code,
            )
        elif status_code == 404:
            return ConnectionTestResult(
                ok=False,
                message="Server responded (HTTP 404), but the Immich API endpoint '/api/server/about' was not found.",
                status_code=404,
            )
        else:
            return ConnectionTestResult(
                ok=False,
                message=f"Server returned status code {status_code}.",
                status_code=status_code,
            )

    except requests.exceptions.SSLError:
        return ConnectionTestResult(
            ok=False,
            message="SSL certificate verification failed. Enable 'Skip SSL verification' if using self-signed certificates.",
        )
    except requests.exceptions.Timeout:
        return ConnectionTestResult(
            ok=False,
            message=f"Connection timed out after {timeout} seconds. Check server URL and network connection.",
        )
    except requests.exceptions.ConnectionError:
        return ConnectionTestResult(
            ok=False,
            message="Failed to connect to server. Verify server URL and network accessibility.",
        )
    except Exception as e:
        return ConnectionTestResult(
            ok=False,
            message=f"Unexpected connection error: {e!s}",
        )


def check_preflight_server_connection(
    tab_key: str,
    config_state: dict,
    tab_state: dict | None = None,
    timeout: float = 3.0,
) -> ConnectionTestResult:
    """Pre-flight check for server connectivity before execution.

    Only runs if tab_key is in SERVER_REQUIRED_TABS.
    """
    from core.cli_schema import SERVER_REQUIRED_TABS

    if tab_key not in SERVER_REQUIRED_TABS:
        return ConnectionTestResult(
            ok=True, message="Serverless command — no server required."
        )

    srv_url = config_state.get("server", "")
    api_key = config_state.get("api_key", "")
    skip_ssl = bool(config_state.get("skip-ssl", False))

    res = test_immich_connection(srv_url, api_key, skip_ssl=skip_ssl, timeout=timeout)
    if not res.ok:
        return res

    if tab_key == "upload-immich" and tab_state:
        from_srv = tab_state.get("from-server", "")
        from_key = tab_state.get("from-api-key", "")
        from_ssl = bool(tab_state.get("from-skip-ssl", False))
        if from_srv and from_key:
            from_res = test_immich_connection(
                from_srv, from_key, skip_ssl=from_ssl, timeout=timeout
            )
            if not from_res.ok:
                return ConnectionTestResult(
                    ok=False,
                    message=f"Source server ('{from_srv}') connection failed: {from_res.message}",
                    status_code=from_res.status_code,
                )

    return res
