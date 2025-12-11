from fastapi import FastAPI
from routers import auth, user

app = FastAPI()

app.include_router(auth.router, prefix="/auth")
app.include_router(user.router, prefix="/user")
