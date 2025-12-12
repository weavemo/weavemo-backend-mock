
from pydantic import BaseModel
from typing import Optional

class LoginRequest(BaseModel):
    email: str
    password: str

class RegisterRequest(BaseModel):
    email: str
    password: str
    nickname: str

class AuthResponse(BaseModel):
    user: dict
    token: str
    expiresIn: int
    refreshToken: Optional[str] = None
