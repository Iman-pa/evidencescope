from fastapi import FastAPI

app = FastAPI(title="EvidenceScope API")


@app.get("/health")
def health():
    return {"status": "ok"}
