"""Точка входа. Запускает FastAPI + движок ботов в одном процессе."""
import os
import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "web.main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info",
    )
