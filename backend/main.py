from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
import json
import asyncio
import threading
import queue
from pydantic import BaseModel
from backend.agents.mock_agents import OrchestratorAgent
from backend.agents.booking_agent import BookingAgent
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
booking_agent = BookingAgent()

@app.post("/api/plan-trip-stream")
async def plan_trip_stream(request: TripRequest):
    async def event_stream():
        q = queue.Queue()

        def run_orchestrator():
            try:
                for event in orchestrator.process_prompt_stream(request.prompt):
                    q.put(event)
            except AgentAPIError as e:
                print(f"Orchestration API error: {e.detail or e.user_message}")
                q.put({'type': 'error', 'message': e.user_message})
            except Exception as e:
                print(f"Orchestration error: {type(e).__name__}: {e}")
                q.put({'type': 'error', 'message': f'An unexpected error occurred: {type(e).__name__}. Please try again.'})
            finally:
                q.put(None)  # sentinel

        thread = threading.Thread(target=run_orchestrator, daemon=True)
        thread.start()

        while True:
            try:
                item = q.get(timeout=15)
            except queue.Empty:
                # Heartbeat: SSE comment keeps the HTTP/2 stream alive
                yield ": heartbeat\n\n"
                continue

            if item is None:
                break
            yield f"data: {json.dumps(item)}\n\n"
            await asyncio.sleep(0)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

@app.post("/api/settle")
async def settle_balance(request: SettlementRequest):
    # Simulate payment settlement (TC-02)
    success, message = ledger_service.settle_payment(
        request.user_id, request.card_number
    )
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return {"status": "success", "message": message}

class AmendRequest(BaseModel):
    item_type: str  # "hotel", "food", "activity"
    current_item: dict
    user_preference: str
    trip_summary: dict

@app.post("/api/amend-item")
async def amend_item(request: AmendRequest):
    try:
        result = booking_agent.amend_item(
            item_type=request.item_type,
            current_item=request.current_item,
            user_preference=request.user_preference,
            trip_summary=request.trip_summary,
        )
        return {"status": "success", "data": result}
    except AgentAPIError as e:
        raise HTTPException(status_code=502, detail=e.user_message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
async def health_check():
    return {"status": "ok"}

# Mount the static frontend files
import os
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.isdir(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
