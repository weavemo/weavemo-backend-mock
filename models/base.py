from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, BigInteger, DateTime, func

Base = declarative_base()

class BaseModel(Base):
    __abstract__ = True

    id = Column(BigInteger, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
