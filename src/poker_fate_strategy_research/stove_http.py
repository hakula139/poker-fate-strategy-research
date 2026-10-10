from __future__ import annotations

import hmac
import html
import json
from http.server import BaseHTTPRequestHandler
from textwrap import dedent
from urllib.parse import parse_qs

from .stove import Credentials, SignIn


def handler(state: SignIn) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            pass

        def respond(
            self,
            content: str,
            status: int = 200,
            content_type: str = 'text/html; charset=utf-8',
        ) -> None:
            data = content.encode()
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Referrer-Policy', 'same-origin')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header(
                'Content-Security-Policy',
                (
                    "default-src 'none'; connect-src 'self'; "
                    "style-src 'unsafe-inline'; "
                    "form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
                ),
            )
            self.end_headers()
            self.wfile.write(data)

        def valid_host(self) -> bool:
            return self.headers.get('Host') == state.origin.removeprefix('http://')

        def do_GET(self) -> None:
            if not self.valid_host():
                self.respond('Not found', 404)
                return
            if self.path == '/status':
                with state.lock:
                    self.respond(
                        json.dumps(state.public_status()),
                        content_type='application/json',
                    )
                return
            if self.path == '/challenge-info':
                with state.lock:
                    if state.phase != 'captcha':
                        self.respond('No verification is pending', 409)
                        return
                    try:
                        info = state.challenge_info()
                    except Exception as error:
                        self.respond(type(error).__name__, 502)
                        return
                    self.respond(json.dumps(info), content_type='application/json')
                return
            if self.path != '/':
                self.respond('Not found', 404)
                return
            with state.lock:
                self.respond(self.page())

        def page(self) -> str:
            form = ''
            if state.phase == 'credentials':
                fields = (
                    ''
                    if state.credentials
                    else dedent("""
                        <label>Email
                          <input name="email" type="email" required autocomplete="off">
                        </label>
                        <label>Password
                          <input name="password" type="password" required
                                 autocomplete="off">
                        </label>
                        <p>Saved locally with owner-only permissions.</p>
                    """)
                )
                form = dedent(f'''
                    <form method="post" action="/login" autocomplete="off">
                      <input type="hidden" name="csrf" value="{state.csrf}">
                      {fields}
                      <button type="submit">Sign in</button>
                    </form>
                ''')
            elif state.phase == 'captcha':
                form = dedent("""
                    <p>Complete verification in the STOVE Verification window.
                    Sign-in continues automatically.</p>
                """)
            return dedent(f"""<!doctype html>
                <html lang="en"><meta charset="utf-8">
                <meta name="viewport" content="width=device-width,initial-scale=1">
                <title>STOVE Sign-in</title>
                <style>
                  body{{font:16px system-ui;max-width:660px;margin:8vh auto;
                        padding:24px;line-height:1.7}}
                  label{{display:block;margin:20px 0}}
                  input{{display:block;width:100%;box-sizing:border-box;padding:10px}}
                  button{{padding:12px 18px}}h1{{font-size:24px}}
                </style>
                <h1>STOVE Sign-in</h1>
                <p>Credentials are sent to STOVE over HTTPS.
                Session tokens remain in memory.</p>
                <p>{html.escape(state.status)}</p>{form}</html>
            """)

        def do_POST(self) -> None:
            if not self.valid_host() or self.headers.get('Origin') != state.origin:
                self.respond('Rejected request', 403)
                return
            if self.path not in {'/login', '/captcha-token'}:
                self.respond('Not found', 404)
                return
            expected_type = (
                'application/json'
                if self.path == '/captcha-token'
                else 'application/x-www-form-urlencoded'
            )
            if self.headers.get('Content-Type') != expected_type:
                self.respond('Unsupported content type', 415)
                return
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 16384:
                    raise ValueError
                raw = self.rfile.read(size).decode()
                if self.path == '/captcha-token':
                    payload = json.loads(raw)
                else:
                    fields = parse_qs(raw, strict_parsing=True)
                    if any(len(values) != 1 for values in fields.values()):
                        raise ValueError
                    payload = {key: values[0] for key, values in fields.items()}
                if not isinstance(payload, dict) or not isinstance(
                    payload.get('csrf'), str
                ):
                    raise ValueError
                if self.path == '/captcha-token' and isinstance(
                    payload.get('token'), str
                ):
                    payload['token'].encode()
            except (ValueError, UnicodeError):
                self.respond('Invalid input', 400)
                return
            with state.lock:
                if not payload['csrf'].isascii() or not hmac.compare_digest(
                    payload['csrf'], state.csrf
                ):
                    self.respond('Rejected request', 403)
                    return
                if self.path == '/captcha-token':
                    token = payload.get('token')
                    if (
                        not isinstance(token, str)
                        or not token
                        or len(token.encode()) > 12000
                    ):
                        self.respond('Invalid verification result', 400)
                        return
                    if state.phase != 'captcha':
                        self.respond('No verification is pending', 409)
                        return
                    state.authenticate(token)
                    self.respond('Verification received')
                    return
                if state.phase != 'credentials':
                    self.respond('Sign-in is already in progress', 409)
                    return
                if state.credentials is None:
                    email, password = payload.get('email'), payload.get('password')
                    if (
                        not isinstance(email, str)
                        or not email
                        or not isinstance(password, str)
                        or not password
                    ):
                        self.respond('Email and password are required', 400)
                        return
                    credentials = Credentials(email, password)
                    try:
                        credentials.save(state.credentials_path)
                    except Exception as error:
                        self.respond(
                            f'Cannot save credentials ({type(error).__name__})', 500
                        )
                        return
                    state.credentials = credentials
                state.authenticate()
            self.send_response(303)
            self.send_header('Location', '/')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', '0')
            self.end_headers()

    return Handler
