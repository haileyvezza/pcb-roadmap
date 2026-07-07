"""Minimal HTTP client for the Vault streamable-http MCP server."""
import json
import urllib.request
import urllib.error

URL = "https://vault.shopify.io/mcp"
TOKEN = "96d1bbe5-1d6e-4d9e-956b-cbd0d64d3453"


class VaultMcp:
    def __init__(self, timeout=60):
        self.timeout = timeout
        self._id = 0
        self.session_id = None
        self._init()

    def _next_id(self):
        self._id += 1
        return self._id

    def _post(self, payload, extra_headers=None):
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.session_id:
            headers["mcp-session-id"] = self.session_id
        if extra_headers:
            headers.update(extra_headers)
        req = urllib.request.Request(URL, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                sid = resp.headers.get("mcp-session-id")
                if sid and not self.session_id:
                    self.session_id = sid
                raw = resp.read().decode("utf-8", errors="replace")
                return resp.status, dict(resp.headers), raw
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace") if e.fp else ""
            return e.code, dict(e.headers or {}), body

    @staticmethod
    def _parse_sse(raw):
        """Extract JSON payload(s) from SSE text."""
        out = []
        for chunk in raw.split("\n\n"):
            data_lines = [ln[5:].lstrip() for ln in chunk.splitlines() if ln.startswith("data:")]
            if not data_lines:
                continue
            payload = "\n".join(data_lines).strip()
            if not payload:
                continue
            try:
                out.append(json.loads(payload))
            except Exception:
                pass
        return out

    def _init(self):
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "vault-http-client", "version": "0.1"},
            },
        }
        status, headers, raw = self._post(payload)
        if status >= 400:
            raise RuntimeError(f"init failed status={status} body={raw[:400]}")
        # notifications/initialized (no id)
        note = {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
        self._post(note)

    def call(self, name, arguments):
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
        status, headers, raw = self._post(payload)
        if status >= 400:
            return {"error": f"HTTP {status}", "body": raw[:800]}
        ctype = headers.get("Content-Type", "") + headers.get("content-type", "")
        if "text/event-stream" in ctype:
            events = self._parse_sse(raw)
            if not events:
                return {"error": "empty sse", "raw": raw[:400]}
            return events[-1]
        try:
            return json.loads(raw)
        except Exception:
            return {"error": "not json", "raw": raw[:400]}


if __name__ == "__main__":
    c = VaultMcp()
    r = c.call("vault_get_team_members", {"team_id": "16570"})
    print(json.dumps(r)[:600])
