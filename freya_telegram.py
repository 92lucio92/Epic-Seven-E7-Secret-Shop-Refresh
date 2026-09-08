"""Thin client for Freya's telegram_notify MCP skill.

Contract (agreed with freya-root-d6):
- notify(text) with no thread -> a new Telegram message every call
- notify(text, thread="shop") -> rewrites one message in place for the
  lifetime of this MCP session; a new process/session always starts a
  new message even with the same thread name
- the mcp-session-id header must be sent on every call, including
  tools/call, or each update becomes a new message instead of an edit
"""
import json
import os
import urllib.request

MCP_URL = 'http://localhost:7331/mcp'


def _load_api_key(env_path='.env'):
    if 'FREYA_KEY_EPIC7' in os.environ:
        return os.environ['FREYA_KEY_EPIC7']
    if os.path.isfile(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith('FREYA_KEY_EPIC7='):
                    return line.split('=', 1)[1]
    return None


class FreyaTelegram:
    def __init__(self, api_key=None, url=MCP_URL):
        self.api_key = api_key or _load_api_key()
        self.url = url
        self.session_id = None
        self._id = 0

    def _next_id(self):
        self._id += 1
        return self._id

    def _post(self, payload):
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json, text/event-stream',
            'X-Api-Key': self.api_key,
        }
        if self.session_id:
            headers['mcp-session-id'] = self.session_id
        req = urllib.request.Request(
            self.url, data=json.dumps(payload).encode('utf-8'),
            headers=headers, method='POST')
        with urllib.request.urlopen(req, timeout=10) as resp:
            session_header = resp.headers.get('mcp-session-id')
            if session_header:
                self.session_id = session_header
            return resp.read().decode('utf-8')

    def connect(self):
        self._post({
            'jsonrpc': '2.0', 'id': self._next_id(), 'method': 'initialize',
            'params': {
                'protocolVersion': '2024-11-05',
                'capabilities': {},
                'clientInfo': {'name': 'epic7', 'version': '1'},
            },
        })
        self._post({'jsonrpc': '2.0', 'method': 'notifications/initialized'})

    def notify(self, text, thread=None):
        args = {'text': text}
        if thread:
            args['thread'] = thread
        body = self._post({
            'jsonrpc': '2.0', 'id': self._next_id(), 'method': 'tools/call',
            'params': {'name': 'telegram_notify', 'arguments': args},
        })
        for line in body.splitlines():
            if line.startswith('data: '):
                try:
                    result_str = json.loads(line[6:])['result']['structuredContent']['result']
                    return json.loads(result_str).get('message_id')
                except (json.JSONDecodeError, KeyError, TypeError):
                    pass
        return None


def connect_if_configured():
    """Returns a connected FreyaTelegram, or None if not configured/reachable.
    Notifications are a nice-to-have — never let this block the shop refresh."""
    key = _load_api_key()
    if not key:
        return None
    client = FreyaTelegram(api_key=key)
    try:
        client.connect()
        return client
    except Exception as e:
        print(f'Telegram notify unavailable ({e}), continuing without it')
        return None
