from fastapi import FastAPI
from app.api.chat_routes import router as chat_router
from app.api.email_routes import router as email_router  # ✅ NEW

app = FastAPI(title="Chatbox Support API")

@app.get("/")
def root():
    return {"message": "Go to /docs or /health"}

@app.get("/health")
def health():
    return {"status": "ok"}

app.include_router(chat_router, prefix="/api", tags=["chat"])
app.include_router(email_router, prefix="/api", tags=["email"])  # ✅ NEW
