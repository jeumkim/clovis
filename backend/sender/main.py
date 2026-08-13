from fastapi import FastAPI

app = FastAPI(title="Clovis Sender API")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "sender"}
