import html
import logging

from azure.communication.email import EmailClient

from . import config
from .models import Job


def _section(title: str, jobs: list[Job]) -> str:
    if not jobs:
        return ""
    rows = "".join(
        f'<li style="margin-bottom:12px"><b>{j.score}</b> &ndash; '
        f'<a href="{html.escape(j.url)}">{html.escape(j.title)}</a> at {html.escape(j.company)} '
        f'({html.escape(j.location)}) <i>[{j.source}]</i><br>{html.escape(j.reason)}</li>'
        for j in jobs
    )
    return f"<h3>{title}</h3><ol>{rows}</ol>"


def send_digest(jobs: list[Job]) -> None:
    jobs = sorted(jobs, key=lambda j: j.score, reverse=True)[: config.MAX_RESULTS_IN_EMAIL]
    body = _section("Remote", [j for j in jobs if j.remote]) + _section("Greenville / Spartanburg area", [j for j in jobs if not j.remote])
    content = {
        "subject": f"Job matches: {len(jobs)} new",
        "html": f"<html><body><h2>Your daily job matches</h2>{body}</body></html>",
    }
    if not (config.ACS_CONNECTION_STRING and config.EMAIL_SENDER and config.EMAIL_TO):
        logging.warning("Email not configured; digest would have been:\n%s", content["html"])
        return
    client = EmailClient.from_connection_string(config.ACS_CONNECTION_STRING)
    msg = {
        "senderAddress": config.EMAIL_SENDER,
        "recipients": {"to": [{"address": a} for a in config.EMAIL_TO]},
        "content": content,
    }
    client.begin_send(msg).result()
    logging.info("Digest sent to %s", config.EMAIL_TO)
