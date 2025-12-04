from typing import List

from sqlalchemy.orm import Session

from src.infrastructure.database.models.optimization import OptimizationModel
from src.infrastructure.database.repositories.base import BaseRepository


class OptimizationRepository(BaseRepository[OptimizationModel]):
    """Repository para Optimization con operaciones específicas"""

    def __init__(self, db: Session):
        super().__init__(OptimizationModel, db)

    def get_by_client(
        self, client_id: int, skip: int = 0, limit: int = 100
    ) -> List[OptimizationModel]:
        """Obtiene optimizaciones por cliente"""
        return (
            self.db.query(OptimizationModel)
            .filter(OptimizationModel.client_id == client_id)
            .offset(skip)
            .limit(limit)
            .all()
        )
