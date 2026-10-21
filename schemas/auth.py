# weavemo-backend-mock/schemas/auth.py

from typing import Literal, Optional

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    nickname: str = Field(min_length=1, max_length=30)
    locale: Literal["ko-KR", "en-US"] = "en-US"
    notificationTimezone: str = Field(min_length=1, max_length=100)


class AuthResponse(BaseModel):
    user: dict
    token: str
    expiresIn: int
    refreshToken: Optional[str] = None


class RegisterResponse(BaseModel):
    confirmationRequired: bool
    user: Optional[dict] = None
    token: Optional[str] = None
    expiresIn: Optional[int] = None
    refreshToken: Optional[str] = None
