"""GET/PUT /api/coa — the editable chart of accounts (spec 11 section 4 F1)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.coa import get_coa, parse_coa, reload_coa
from app.logging import get_logger
from app.schemas import AccountOut, CoaOut, CoaUpdate
from app.settings import get_settings

router = APIRouter(prefix="/api/coa", tags=["chart of accounts"])
log = get_logger("spendsort.coa")


@router.get("", response_model=CoaOut)
def read_coa() -> CoaOut:
    coa = get_coa()
    return CoaOut(
        accounts=[AccountOut(code=a.code, name=a.name, kind=a.kind, description=a.description) for a in coa.accounts],
        count=len(coa),
    )


@router.get("/yaml")
def read_coa_yaml() -> dict[str, str]:
    """The raw YAML, for the editor screen."""
    path = get_settings().coa_path
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"no chart of accounts at {path}")
    return {"yaml": path.read_text(encoding="utf-8")}


@router.put("", response_model=CoaOut)
def update_coa(payload: CoaUpdate) -> CoaOut:
    """Replace the CoA.

    Validated *before* it is written: an invalid chart of accounts would break every
    subsequent categorization, so a bad edit must fail here rather than at run time.
    """
    try:
        candidate = parse_coa(payload.yaml)
    except Exception as exc:  # yaml errors and our own ValueErrors alike
        raise HTTPException(422, detail=f"invalid CoA: {exc}") from exc

    path = get_settings().coa_path
    # Explicit UTF-8: account names contain em-dashes and this box's locale is cp1252 (D15).
    path.write_text(payload.yaml, encoding="utf-8")
    coa = reload_coa()

    log.info("coa updated", extra={"context": {"accounts": len(coa), "path": str(path)}})

    return CoaOut(
        accounts=[
            AccountOut(code=a.code, name=a.name, kind=a.kind, description=a.description) for a in candidate.accounts
        ],
        count=len(coa),
    )
