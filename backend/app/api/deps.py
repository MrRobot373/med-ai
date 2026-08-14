"""Shared FastAPI dependency type aliases.

`Annotated[X, Depends(y)]` declared once here and reused as a plain type annotation
everywhere avoids every router redeclaring `Depends(get_db)`/`Depends(get_settings)` as
a parameter *default value* — which is FastAPI's older idiom but trips ruff's B008
(function-call-in-default-argument) since defaults are evaluated at import time for
almost every other kind of function. FastAPI special-cases `Depends(...)` regardless of
which style is used; `Annotated` is simply the version that plays nicely with linters
and doesn't require non-default parameters to precede it.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session as DbSession

from app.config.settings import Settings, get_settings
from app.db.session import get_db

DbDep = Annotated[DbSession, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
