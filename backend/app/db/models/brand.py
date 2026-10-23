"""Référentiel global des marques : libellés, alias de saisie, présence dans le modèle en production."""

from sqlalchemy import Boolean, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Brand(TimestampMixin, Base):
    __tablename__ = "brands"

    slug: Mapped[str] = mapped_column(String(40), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    aliases: Mapped[list[str]] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)
    # Recalculé à chaque rechargement du modèle de marques (étiquettes du modèle en production).
    in_model: Mapped[bool] = mapped_column(Boolean, server_default=text("false"), nullable=False)
