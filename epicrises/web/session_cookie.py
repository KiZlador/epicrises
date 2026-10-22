"""Browser session identity and the persistent signing key."""

import os
import re
import secrets
from pathlib import Path
from uuid import uuid4

from flask import session


def session_id() -> str:
    identifier = session.get("id", "")
    if not isinstance(identifier, str) or not re.fullmatch(r"[a-f0-9]{32}", identifier):
        identifier = uuid4().hex
        session["id"] = identifier
    return identifier


def signing_key(data_dir: Path) -> str:
    configured = os.getenv("SECRET_KEY")
    if configured:
        return configured
    path = data_dir / ".secret"
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        return path.read_text(encoding="ascii")
    secret = secrets.token_hex(32)
    with os.fdopen(descriptor, "w", encoding="ascii") as stream:
        stream.write(secret)
    return secret
