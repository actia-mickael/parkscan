"""Importe tous les modèles pour qu'Alembic et SQLAlchemy les connaissent."""

from app.db.models.tenant import Tenant

__all__ = ["Tenant"]
