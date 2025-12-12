
from pydantic import BaseModel

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
    epiresIn: int
    refreshToken: str | None = None
