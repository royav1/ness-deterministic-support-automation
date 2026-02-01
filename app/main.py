from fastapi import FastAPI
from app.api.chat_routes import router as chat_router

app = FastAPI(title="Chatbox Support API")

@app.get("/")
def root():
    return {"message": "Go to /docs or /health"}

@app.get("/health")
def health():
    return {"status": "ok"}

app.include_router(chat_router, prefix="/api", tags=["chat"])
