import logging
from pathlib import Path

from mitmproxy import ctx, http
from mitmproxy.addonmanager import Loader

from poker_fate_strategy_research.session import import_login


logger = logging.getLogger(__name__)


class LoginCapture:
    def __init__(self) -> None:
        self.saved = False

    def load(self, loader: Loader) -> None:
        loader.add_option('session_output', str, '', 'New private local session file.')
        loader.add_option(
            'client_channel', int, -1, 'Verified native distribution channel.'
        )
        loader.add_option(
            'login_host',
            str,
            'ga-foreign.poker-fate.com',
            'Exact official login host to capture.',
        )

    def response(self, flow: http.HTTPFlow) -> None:
        if self.saved or flow.request.host != ctx.options.login_host:
            return

        if flow.request.method != 'POST' or flow.request.path != '/login':
            return

        if flow.response is None or flow.response.status_code != 200:
            return

        if not ctx.options.session_output or ctx.options.client_channel < 0:
            logger.error('Set session_output and the verified client_channel first.')
            return

        try:
            session = import_login(
                flow.response.json(),
                flow.request.headers.get('Version', ''),
                ctx.options.client_channel,
            )
            session.save(Path(ctx.options.session_output))
        except (ValueError, TypeError, OSError):
            logger.error(
                'Session capture failed. Check login status and the output file.'
            )
            return

        self.saved = True
        logger.info('Saved official session. Stop the proxy before continuing.')


addons = [LoginCapture()]
