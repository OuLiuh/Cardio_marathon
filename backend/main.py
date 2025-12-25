from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

# Разрешаем запросы (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class InitData(BaseModel):
    initData: str

@app.get("/api/health")
def health():
    return {"status": "ok", "message": "Бэкенд работает!"}

@app.post("/api/auth")
def auth(data: InitData):
    # Тут будет логика проверки хеша Telegram
    return {"status": "success", "user_id": 12345, "username": "TestUser"}