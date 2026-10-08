import io
import json
import logging

from azure.storage.blob import BlobServiceClient

from . import config


def _container():
    svc = BlobServiceClient.from_connection_string(config.STORAGE_CONNECTION)
    c = svc.get_container_client(config.CONTAINER)
    if not c.exists():
        c.create_container()
    return c


def load_resume_text() -> str:
    """Reads the first blob named resume.* (txt, md, or pdf) from the container."""
    c = _container()
    blobs = list(c.list_blobs(name_starts_with="resume."))
    if not blobs:
        raise RuntimeError(
            f"No resume found. Upload one named resume.pdf/.txt/.md to container '{config.CONTAINER}'."
        )
    name = blobs[0].name
    data = c.download_blob(name).readall()
    if name.lower().endswith(".pdf"):
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        return "\n".join(p.extract_text() or "" for p in reader.pages)
    return data.decode("utf-8", errors="ignore")


def load_seen() -> dict:
    c = _container()
    try:
        return json.loads(c.download_blob("seen.json").readall())
    except Exception:
        return {}


def save_seen(seen: dict) -> None:
    # Keep the file bounded: retain the 5000 most recent entries.
    items = sorted(seen.items(), key=lambda kv: kv[1])[-5000:]
    _container().upload_blob("seen.json", json.dumps(dict(items)), overwrite=True)
    logging.info("Saved %d seen job ids", len(items))
