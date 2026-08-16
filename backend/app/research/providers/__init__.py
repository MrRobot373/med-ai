"""Trusted-source providers — spec §65. Each module exposes one
`async def search(query: str, settings: Settings, max_results: int) -> list[WebResult]`
— independently best-effort, never raises past its own boundary (see `base.py`).
"""
