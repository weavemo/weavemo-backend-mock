# models/user.py
from sqlalchemy import Column, String, Integer, ForeignKey, JSON
from sqlalchemy.orm import relationship
from models.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)  # Supabase UUID
    email = Column(String, nullable=False, unique=True)

    stats = relationship("UserStats", back_populates="user", uselist=False)


class UserStats(Base):
    __tablename__ = "user_stats"

    user_id = Column(String, ForeignKey("users.id"), primary_key=True)

    xp = Column(Integer, default=0)
    level = Column(Integer, default=1)
    streak_days = Column(Integer, default=0)

    badges = Column(JSON, default=list)
    skins = Column(JSON, default=list)
    challenges = Column(JSON, default=dict)
    plan = Column(String, default="free")

    user = relationship("User", back_populates="stats")
