from typing import Optional

from fastapi import APIRouter, Depends, Query

from src.modules.users.dependencies import require_permission
from src.modules.users.schemas import UserCreate, UserResponse, UserUpdate
from src.modules.users.service import UserService, user_service
from src.shared.pagination import PageParams
from src.shared.responses import (
    ERROR_RESPONSES,
    DataResponse,
    PaginatedResponse,
    ok,
    page,
)

# User management: "administrador" only (RESOURCE_ROLES["users:manage"]).
router = APIRouter(
    prefix="/users",
    tags=["users"],
    responses=ERROR_RESPONSES,
    dependencies=[Depends(require_permission("users:manage"))],
)


@router.post("/", response_model=DataResponse[UserResponse], status_code=201)
def create_user(data: UserCreate, svc: UserService = Depends(user_service)):
    """Creates a new user."""
    return ok(svc.create(data))


@router.get("/", response_model=PaginatedResponse[UserResponse])
def list_users(
    paging: PageParams = Depends(),
    search: Optional[str] = Query(None, description="Search by email or name"),
    svc: UserService = Depends(user_service),
):
    """Lists users with optional search and pagination."""
    if search:
        items, total = svc.search_paginated(search, paging.limit, paging.offset)
    else:
        items, total = svc.list_paginated(paging.limit, paging.offset)
    return page(items, total, paging.limit, paging.offset)


@router.get("/{user_id}", response_model=DataResponse[UserResponse])
def get_user(user_id: int, svc: UserService = Depends(user_service)):
    """Gets a user by ID."""
    return ok(svc.get_or_404(user_id))


@router.put("/{user_id}", response_model=DataResponse[UserResponse])
def update_user(
    user_id: int, data: UserUpdate, svc: UserService = Depends(user_service)
):
    """Updates a user (includes password change and logical deactivation)."""
    return ok(svc.update(user_id, data))


@router.delete("/{user_id}", status_code=204)
def delete_user(user_id: int, svc: UserService = Depends(user_service)):
    """Deletes a user."""
    svc.delete(user_id)
