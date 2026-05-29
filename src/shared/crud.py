from typing import Generic, List, Optional, Type, TypeVar

from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.shared.database import Base
from src.shared.exceptions import ConflictError, EntityNotFoundError

ModelT = TypeVar("ModelT", bound=Base)
CreateT = TypeVar("CreateT", bound=BaseModel)
UpdateT = TypeVar("UpdateT", bound=BaseModel)


class CRUDService(Generic[ModelT, CreateT, UpdateT]):
    """Servicio CRUD genérico sobre un modelo ORM.

    Las subclases definen ``model`` y, opcionalmente, ``conflict_messages``
    (substring de la restricción -> mensaje legible) y métodos específicos.

    Reemplaza el CRUD repetido en los servicios y los repositorios por entidad.
    """

    model: Type[ModelT]
    conflict_messages: dict = {}

    def __init__(self, db: Session):
        self.db = db

    def get(self, id: int) -> Optional[ModelT]:
        return self.db.get(self.model, id)

    def get_or_404(self, id: int) -> ModelT:
        obj = self.get(id)
        if obj is None:
            raise EntityNotFoundError(self.model.__name__, id)
        return obj

    def list(self, skip: int = 0, limit: int = 100) -> List[ModelT]:
        return self.db.query(self.model).offset(skip).limit(limit).all()

    def create(self, data: CreateT) -> ModelT:
        return self._persist(self.model(**data.model_dump()))

    def update(self, id: int, data: UpdateT) -> ModelT:
        obj = self.get_or_404(id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(obj, field, value)
        return self._persist(obj)

    def delete(self, id: int) -> None:
        self.db.delete(self.get_or_404(id))
        self.db.commit()

    def _persist(self, obj: ModelT) -> ModelT:
        try:
            self.db.add(obj)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(self._conflict_detail(exc)) from exc
        self.db.refresh(obj)
        return obj

    def _conflict_detail(self, exc: IntegrityError) -> str:
        text = str(exc.orig) if exc.orig else str(exc)
        for needle, message in self.conflict_messages.items():
            if needle in text:
                return message
        return "Violación de restricción de integridad"
