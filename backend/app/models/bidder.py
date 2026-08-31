import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import UUID

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.document import Document
    from app.models.user import User


class Bidder(Base):
    """Bidder organization entity referencing a platform user."""

    __tablename__ = "bidders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_name: Mapped[str] = mapped_column(
        String(255),
        index=True,
        nullable=False,
    )
    registration_number: Mapped[Optional[str]] = mapped_column(
        String(100),
        index=True,
        nullable=True,
        doc="Official identification/registration details (e.g., GSTIN, PAN, CIN)",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="bidders",
    )
    documents: Mapped[List["Document"]] = relationship(
        "Document",
        back_populates="bidder",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Bidder id={self.id} org={self.organization_name} user_id={self.user_id}>"
