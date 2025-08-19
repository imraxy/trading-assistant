from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Integer, String, Float, DateTime
from datetime import datetime
from .database import Base


class PositionSnapshot(Base):
    __tablename__ = "position_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String(50), index=True)
    side: Mapped[str] = mapped_column(String(10))
    size: Mapped[float] = mapped_column(Float)
    entry_price: Mapped[float] = mapped_column(Float)
    current_price: Mapped[float] = mapped_column(Float)
    position_value: Mapped[float] = mapped_column(Float)
    unrealized_pnl: Mapped[float] = mapped_column(Float)
    pnl_percentage: Mapped[float] = mapped_column(Float)
    leverage: Mapped[float] = mapped_column(Float)
    category: Mapped[str] = mapped_column(String(20))
    captured_at: Mapped[datetime] = mapped_column(DateTime, index=True, default=datetime.utcnow)


class DecisionCache(Base):
    __tablename__ = "decision_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String(50), index=True)
    side: Mapped[str] = mapped_column(String(10), index=True)
    decision: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(String(2000))
    # Store JSON as string; SQLite-friendly. For Postgres, switch to JSONB.
    factors_json: Mapped[str] = mapped_column(String(8000), default="{}")
    provenance_json: Mapped[str] = mapped_column(String(4000), default="{}")
    context_json: Mapped[str] = mapped_column(String(8000), default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, index=True, default=datetime.utcnow)

