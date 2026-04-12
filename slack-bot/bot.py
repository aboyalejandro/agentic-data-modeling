import os
import re

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

load_dotenv()

from agent import Agent  # noqa: E402 — load dotenv before importing agent

app = App(token=os.environ["SLACK_BOT_TOKEN"])
agent = Agent()


def _strip_mention(text: str) -> str:
    return re.sub(r"<@[A-Z0-9]+>", "", text).strip()


@app.event("app_mention")
def handle_mention(event, say, client):
    thread_ts = event.get("thread_ts", event["ts"])
    user_message = _strip_mention(event.get("text", ""))

    if not user_message:
        say(text="Hey! Ask me anything about the data catalog.", thread_ts=thread_ts)
        return

    thinking = say(text=":thinking_face: Working on it...", thread_ts=thread_ts)

    try:
        answer = agent.run(thread_ts=thread_ts, user_message=user_message)
    except Exception as e:
        answer = f":warning: Error: {e}"

    client.chat_update(
        channel=event["channel"],
        ts=thinking["ts"],
        text=answer,
    )


@app.event("message")
def handle_thread_message(event, say):
    # Ignore bot messages and top-level messages (no thread_ts)
    if event.get("bot_id") or event.get("subtype"):
        return
    thread_ts = event.get("thread_ts")
    if not thread_ts:
        return
    # Only respond if we have an active conversation for this thread
    if thread_ts not in agent.conversations:
        return

    user_message = event.get("text", "").strip()
    if not user_message:
        return

    try:
        answer = agent.run(thread_ts=thread_ts, user_message=user_message)
    except Exception as e:
        answer = f":warning: Error: {e}"

    say(text=answer, thread_ts=thread_ts)


if __name__ == "__main__":
    print("Starting databot...")
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    handler.start()
