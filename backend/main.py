from fastapi import FastAPI
from api import workspaces, files

app = FastAPI()

app.include_router(workspaces.router)
app.include_router(files.router)


@app.get("/health")
def health():
    return {"status": "ok"}
