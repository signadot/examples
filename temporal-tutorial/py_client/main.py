import os
import asyncio
import uuid
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from decimal import Decimal, InvalidOperation
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry import baggage

from models import PaymentDetails
from temporal_client import start_workflow_with_routing

# FastAPI App Setup
app = FastAPI()
FastAPIInstrumentor().instrument_app(app)

templates = Jinja2Templates(directory="templates")

MOCK_ACCOUNTS = ["acc_001", "acc_002", "acc_003", "acc_004", "acc_005_large_balance"]

def extract_baggage_info() -> dict:
    """
    Extract all baggage information from the current OpenTelemetry context.
    Returns a dictionary of baggage key-value pairs.
    """
    baggage_info = {}
    try:
        # Use the baggage class directly - it returns a dict-like object
        baggage_items = baggage.get_all()
        for key, value in baggage_items.items():
            baggage_info[str(key)] = str(value)
    except Exception as e:
        print(f"Error extracting baggage: {e}")
        baggage_info = {"error": f"Failed to extract baggage: {str(e)}"}
    
    return baggage_info

# FastAPI Routes
@app.get("/", response_class=HTMLResponse)
async def get_workflow_form(request: Request):
    """Serves the HTML form."""
    return templates.TemplateResponse("index.html", {"request": request, "accounts": MOCK_ACCOUNTS})

@app.post("/api/start-workflow")
async def handle_start_workflow(
    request: Request,
    from_account: str = Form(...),
    to_account: str = Form(...),
    amount: str = Form(...),
    reference: str = Form(""),
):
    """API endpoint to receive form data and start the Temporal workflow."""
    try:
        if from_account == to_account:
            return JSONResponse(status_code=400, content={"error": "From and To accounts cannot be the same."})
        try:
            parsed_amount = Decimal(amount)
            if parsed_amount <= 0:
                return JSONResponse(status_code=400, content={"error": "Amount must be a positive number."})
        except InvalidOperation:
            return JSONResponse(status_code=400, content={"error": "Invalid amount format."})

        payment = PaymentDetails(
            from_account=from_account,
            to_account=to_account,
            amount=str(parsed_amount),
            reference=reference
        )
        
        # Extract baggage info for the response
        baggage_info = extract_baggage_info()
        
        # Start the workflow
        result = await start_workflow_with_routing(payment_details=payment)
        
        # Add baggage info to the result
        result["baggage_headers"] = baggage_info
        result["routing_key"] = baggage_info.get("sd-routing-key", "undefined")
        
        return JSONResponse(content=result)
    except ValueError as ve:
        return JSONResponse(status_code=400, content={"error": str(ve)})
    except Exception as e:
        print(f"Error starting workflow: {e}")
        return JSONResponse(status_code=500, content={"error": f"An unexpected error occurred: {str(e)}"})