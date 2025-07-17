import os
from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel
from temporalio.client import Client
from temporalio.contrib.opentelemetry import TracingInterceptor

TEMPORAL_SERVER = os.getenv("TEMPORAL_SERVER", "temporal-frontend.temporal.svc:7233")

app = FastAPI()


class TransferRequest(BaseModel):
    from_account: str
    to_account: str
    amount: float


@app.on_event("startup")
async def startup_event():
    app.client = await Client.connect(TEMPORAL_SERVER, interceptors=[TracingInterceptor()])


@app.get("/")
async def index() -> FileResponse:
    # serve the simple HTML form
    path = os.path.join(os.path.dirname(__file__), "index.html")
    return FileResponse(path)


@app.post("/transfer")
async def transfer(req: TransferRequest):
    handle = await app.client.start_workflow(
        "bank_transfer",
        req.from_account,
        req.to_account,
        req.amount,
        id=f"transfer-{req.from_account}-{req.to_account}",
        task_queue="bank-transfer",
    )
    return {"workflow_id": handle.id}
