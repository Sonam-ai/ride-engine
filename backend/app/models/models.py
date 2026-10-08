from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Driver(Base):
    __tablename__ = "drivers"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Rider(Base):
    __tablename__ = "riders"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Ride(Base):
    __tablename__ = "rides"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    rider_id: Mapped[str] = mapped_column(ForeignKey("riders.id"), index=True)
    driver_id: Mapped[str | None] = mapped_column(ForeignKey("drivers.id"), nullable=True)
    pickup_lat: Mapped[float] = mapped_column(Float)
    pickup_lng: Mapped[float] = mapped_column(Float)
    pickup_h3: Mapped[str] = mapped_column(String(20), index=True)
    dest_lat: Mapped[float] = mapped_column(Float)
    dest_lng: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), index=True)
    quoted_fare: Mapped[float | None] = mapped_column(Float, nullable=True)
    surge_multiplier: Mapped[float | None] = mapped_column(Float, nullable=True)
    final_fare: Mapped[float | None] = mapped_column(Float, nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RideAssignment(Base):
    __tablename__ = "ride_assignments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ride_id: Mapped[str] = mapped_column(ForeignKey("rides.id"), index=True)
    driver_id: Mapped[str] = mapped_column(ForeignKey("drivers.id"), index=True)
    batch_id: Mapped[str] = mapped_column(String(16))
    pickup_distance_km: Mapped[float] = mapped_column(Float)
    pickup_eta_seconds: Mapped[float] = mapped_column(Float)
    cost: Mapped[float] = mapped_column(Float)
    matching_latency_seconds: Mapped[float] = mapped_column(Float)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TripEvent(Base):
    """Audit log: one row per important thing that happened to a ride."""

    __tablename__ = "trip_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ride_id: Mapped[str] = mapped_column(ForeignKey("rides.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(40))
    detail: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FareTransaction(Base):
    __tablename__ = "fare_transactions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ride_id: Mapped[str] = mapped_column(ForeignKey("rides.id"), index=True)
    driver_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8))
    surge_multiplier: Mapped[float | None] = mapped_column(Float, nullable=True)
    distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SurgeHistory(Base):
    __tablename__ = "surge_history"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    h3_id: Mapped[str] = mapped_column(String(20), index=True)
    surge_multiplier: Mapped[float] = mapped_column(Float)
    supply: Mapped[int] = mapped_column(Integer)
    demand: Mapped[int] = mapped_column(Integer)
    demand_supply_ratio: Mapped[float] = mapped_column(Float)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class DriverLocationHistory(Base):
    """Sampled GPS history. Never written per ping (that would swamp the database)."""

    __tablename__ = "driver_location_history"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    driver_id: Mapped[str] = mapped_column(String(64), index=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    h3_cell: Mapped[str] = mapped_column(String(20))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)