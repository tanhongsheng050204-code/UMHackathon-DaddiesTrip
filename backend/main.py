from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
import json
from pydantic import BaseModel
from backend.agents.mock_agents import OrchestratorAgent
from backend.agents.base_agent import AgentAPIError
from backend.ledger.ledger_service import LedgerService
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="DaddiesTrip API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TripRequest(BaseModel):
    prompt: str

class SettlementRequest(BaseModel):
    group_id: str
    user_id: str
    card_number: str

ledger_service = LedgerService()
orchestrator = OrchestratorAgent()

@app.post("/api/plan-trip-stream")
async def plan_trip_stream(request: TripRequest):
    def event_stream():
        try:
            for event in orchestrator.process_prompt_stream(request.prompt):
                # The orchestrator already computes split inside process_prompt_stream.
                # No additional calculation needed here.
                yield f"data: {json.dumps(event)}\n\n"
        except AgentAPIError as e:
            print(f"Orchestration API error: {e.detail or e.user_message}")
            yield f"data: {json.dumps({'type': 'error', 'message': e.user_message})}\n\n"
        except Exception as e:
            print(f"Orchestration error: {type(e).__name__}: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': f'An unexpected error occurred: {type(e).__name__}. Please try again.'})}\n\n"
            
    return StreamingResponse(event_stream(), media_type="text/event-stream")

@app.post("/api/settle")
async def settle_balance(request: SettlementRequest):
    # Simulate payment settlement (TC-02)
    success, message = ledger_service.settle_payment(
        request.user_id, request.card_number
    )
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return {"status": "success", "message": message}

@app.get("/api/health")
async def health_check():
    return {"status": "ok"}

# Mount the static frontend files
import os
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
