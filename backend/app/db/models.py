"""SQLAlchemy ORM models for the tourist-safety domain.

Geospatial columns use GeoAlchemy2 (PostGIS, SRID 4326 / WGS84). Agent risk
events carry a pgvector embedding plus grounding fields (source / time /
confidence). Importing this module registers all tables on `Base.metadata`.
"""

import uuid
from datetime import datetime

from geoalchemy2 import Geometry, WKBElement
from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, uuid_pk
from app.db.enums import (
    AlertSeverity,
    AlertStatus,
    ConsentPurpose,
    IncidentStatus,
    IncidentType,
    RiskCategory,
    RiskEventType,
)

# Embedding dimension for risk-event vectors (small local sentence-transformer
# models, e.g. all-MiniLM-L6-v2). Pinned here so the column type is stable.
EMBEDDING_DIM = 384


class Tourist(Base, TimestampMixin):
    """A monitored tourist. PII is kept minimal (DPDP data minimization)."""

    __tablename__ = "tourists"

    id: Mapped[uuid.UUID] = uuid_pk()
    external_ref: Mapped[str | None] = mapped_column(String(128), unique=True)
    display_name: Mapped[str | None] = mapped_column(String(128))
    nationality: Mapped[str | None] = mapped_column(String(64))
    emergency_contact: Mapped[str | None] = mapped_column(String(64))

    # Planned trip route (for M2 route-deviation checks). Optional.
    planned_route: Mapped[WKBElement | None] = mapped_column(
        Geometry(geometry_type="LINESTRING", srid=4326, spatial_index=False)
    )

    # --- DPDP consent / retention ---
    consent_given: Mapped[bool] = mapped_column(default=False, nullable=False)
    consent_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consent_purpose: Mapped[ConsentPurpose] = mapped_column(
        default=ConsentPurpose.SAFETY_MONITORING, nullable=False
    )
    retention_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    pings: Mapped[list["LocationPing"]] = relationship(
        back_populates="tourist", cascade="all, delete-orphan"
    )
    incidents: Mapped[list["Incident"]] = relationship(back_populates="tourist")


class Zone(Base, TimestampMixin):
    """A geographic area with a risk classification (PostGIS polygon)."""

    __tablename__ = "zones"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    risk_category: Mapped[RiskCategory] = mapped_column(
        default=RiskCategory.LOW, nullable=False
    )
    restricted: Mapped[bool] = mapped_column(default=False, nullable=False)
    # Soft capacity for crowd-density checks (M2); null = no capacity modelled.
    capacity: Mapped[int | None] = mapped_column(Integer)

    geom: Mapped[WKBElement] = mapped_column(
        Geometry(geometry_type="POLYGON", srid=4326), nullable=False
    )


class LocationPing(Base):
    """A single location report for a tourist (PostGIS point + time)."""

    __tablename__ = "location_pings"
    __table_args__ = (
        Index("ix_pings_tourist_recorded", "tourist_id", "recorded_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tourist_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tourists.id", ondelete="CASCADE"), nullable=False
    )
    geom: Mapped[WKBElement] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326), nullable=False
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    speed_mps: Mapped[float | None] = mapped_column(Float)
    accuracy_m: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str | None] = mapped_column(String(32))

    tourist: Mapped["Tourist"] = relationship(back_populates="pings")


class RiskEvent(Base, TimestampMixin):
    """A grounded risk signal (from agents/external sources or detection).

    Every event carries `source`, `event_time`, and `confidence` per the
    grounding rule. `embedding` enables pgvector similarity retrieval (M4).
    """

    __tablename__ = "risk_events"
    __table_args__ = (
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_confidence_unit"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    event_type: Mapped[RiskEventType] = mapped_column(
        default=RiskEventType.OTHER, nullable=False
    )
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    geom: Mapped[WKBElement | None] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326)
    )
    zone_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("zones.id", ondelete="SET NULL")
    )

    # --- grounding ---
    source: Mapped[str] = mapped_column(String(256), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(512))
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)

    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))


class Incident(Base, TimestampMixin):
    """A flagged incident produced by the detection layer / orchestrator."""

    __tablename__ = "incidents"

    id: Mapped[uuid.UUID] = uuid_pk()
    tourist_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tourists.id", ondelete="SET NULL")
    )
    zone_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("zones.id", ondelete="SET NULL")
    )
    incident_type: Mapped[IncidentType] = mapped_column(nullable=False)
    status: Mapped[IncidentStatus] = mapped_column(
        default=IncidentStatus.OPEN, nullable=False
    )
    geom: Mapped[WKBElement | None] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326)
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    # Free-form detector context (thresholds breached, distances, etc.).
    details: Mapped[dict | None] = mapped_column(JSONB)

    tourist: Mapped["Tourist"] = relationship(back_populates="incidents")
    alerts: Mapped[list["Alert"]] = relationship(
        back_populates="incident", cascade="all, delete-orphan"
    )


class Alert(Base, TimestampMixin):
    """An advisory alert for human authorities (never auto-dispatches)."""

    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = uuid_pk()
    incident_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False
    )
    severity: Mapped[AlertSeverity] = mapped_column(
        default=AlertSeverity.INFO, nullable=False
    )
    status: Mapped[AlertStatus] = mapped_column(
        default=AlertStatus.PENDING, nullable=False
    )
    summary: Mapped[str | None] = mapped_column(Text)
    recommended_action: Mapped[str | None] = mapped_column(Text)
    # Which component/agent produced this (e.g. "orchestrator", "triage_agent").
    created_by: Mapped[str | None] = mapped_column(String(64))

    incident: Mapped["Incident"] = relationship(back_populates="alerts")

