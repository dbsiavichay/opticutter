from datetime import datetime
from typing import Optional

from pydantic import Field

from src.modules.branches.schemas import BranchRefResponse
from src.shared.schemas import CamelModel


class DraftCreate(CamelModel):
    """Create an optimizer draft.

    Fields map 1:1 to columns so ``CRUDService.create`` works with
    ``self.model(**data.model_dump())``. ``payload`` is an opaque JSON object:
    the backend doesn't validate its internal shape (it's defined by the
    frontend).
    """

    name: str = Field(..., min_length=1, max_length=128, description="Draft name")
    client_id: Optional[int] = Field(
        default=None, description="Optional client this draft is associated with"
    )
    branch_id: Optional[int] = Field(
        default=None,
        description=(
            "Target branch. Ignored for the operator (forced to their own branch); "
            "optional for the seller (defaults to their base branch, overridable); "
            "required for a global admin."
        ),
    )
    payload: dict = Field(
        ..., description="Opaque optimizer form state (materials + pieces, as-is)"
    )


class DraftUpdate(CamelModel):
    """Update (overwrite) a draft. All fields are optional."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    client_id: Optional[int] = None
    payload: Optional[dict] = None


class DraftResponse(CamelModel):
    """Draft detail, including the full ``payload``."""

    id: int
    name: str
    client_id: Optional[int] = None
    branch: BranchRefResponse = Field(..., description="Owning branch")
    payload: dict
    created_at: datetime
    updated_at: datetime


class DraftSummaryResponse(CamelModel):
    """Lightweight summary for the listing: ``payload`` is deliberately omitted."""

    id: int
    name: str
    client_id: Optional[int] = None
    branch: BranchRefResponse = Field(..., description="Owning branch")
    created_at: datetime
    updated_at: datetime
