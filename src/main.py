from __future__ import annotations

import sys

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from .config import SLACK_APP_TOKEN, SLACK_BOT_TOKEN, SLACK_SIGNING_SECRET
from .slack_handlers import register_handlers


def run():
    if not SLACK_BOT_TOKEN or not SLACK_APP_TOKEN:
        raise SystemExit(
            "環境変数 SLACK_BOT_TOKEN / SLACK_APP_TOKEN が必要です（Socket Mode）"
        )
    app = App(token=SLACK_BOT_TOKEN, signing_secret=SLACK_SIGNING_SECRET)
    register_handlers(app)
    print("Starting Slack Vector Search Bot…")
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()


if __name__ == "__main__":
    run()
