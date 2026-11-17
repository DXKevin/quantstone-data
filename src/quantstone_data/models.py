from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    provider: Mapped[str] = mapped_column(String(64), index=True)
    region: Mapped[str] = mapped_column(String(32), index=True)
    instrument: Mapped[str] = mapped_column(String(64), index=True)
    dataset_name: Mapped[str] = mapped_column(String(128))
    market: Mapped[str | None] = mapped_column(String(32), nullable=True)
    display_name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    current_schema_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    schemas: Mapped[list[DatasetSchemaVersion]] = relationship(
        back_populates="dataset",
        cascade="all, delete-orphan",
        order_by="DatasetSchemaVersion.version",
    )


class DatasetSchemaVersion(Base):
    __tablename__ = "dataset_schema_versions"
    __table_args__ = (UniqueConstraint("dataset_id", "version"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(Integer)
    primary_key: Mapped[str] = mapped_column(Text, default="")
    time_field: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    dataset: Mapped[Dataset] = relationship(back_populates="schemas")
    fields: Mapped[list[DatasetField]] = relationship(
        back_populates="schema_version",
        cascade="all, delete-orphan",
        order_by="DatasetField.position",
    )

    @property
    def primary_key_fields(self) -> list[str]:
        return [item for item in self.primary_key.split(",") if item]


class DatasetField(Base):
    __tablename__ = "dataset_fields"
    __table_args__ = (UniqueConstraint("schema_version_id", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    schema_version_id: Mapped[int] = mapped_column(
        ForeignKey("dataset_schema_versions.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(128))
    data_type: Mapped[str] = mapped_column(String(64))
    nullable: Mapped[bool] = mapped_column(Boolean, default=True)
    description: Mapped[str] = mapped_column(Text)
    unit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    position: Mapped[int] = mapped_column(Integer)

    schema_version: Mapped[DatasetSchemaVersion] = relationship(back_populates="fields")


class CollectionJob(Base):
    __tablename__ = "collection_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    dataset_id: Mapped[str] = mapped_column(
        ForeignKey("datasets.id", ondelete="RESTRICT"), index=True
    )
    operation: Mapped[str] = mapped_column(String(32), index=True)
    input_method: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    collector_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    staged_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    source_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    source_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
