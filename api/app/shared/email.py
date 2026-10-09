"""Backend email console (dev). Remplacer par SMTP plus tard."""

from __future__ import annotations

import logging

logger = logging.getLogger("ourtdev.email")


async def send_email(*, to: str, subject: str, body: str) -> None:
    logger.info("EMAIL to=%s subject=%s\n%s", to, subject, body)
    print(f"\n=== EMAIL to={to} | {subject} ===\n{body}\n=== END EMAIL ===\n")
