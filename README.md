<p align="center">
  <img src="frontend/logo.jpeg" alt="DaddiesTrip Logo" width="150" style="border-radius:20px;">
</p>

<h1 align="center">DaddiesTrip</h1>

<p align="center">
  <strong>An AI-Enabled Cross-Border Travel Orchestration & Group Accounting Platform</strong>
</p>

## 📌 Overview

**DaddiesTrip** is an AI-enabled cross-border travel orchestration and multi-currency group accounting application. Planning group travel and managing shared expenses across different currencies is a highly fragmented, stressful process. Users typically switch between multiple apps for itineraries, flight bookings, and manual spreadsheets for conversions.

**Our Mission**: DaddiesTrip automates the entire lifecycle of group travel—from conversational itinerary generation to precise multi-currency expense splitting. We aim to facilitate frictionless, secure digital planning to ensure absolute financial accuracy and beautiful trip organization.

---

## 🚀 Key Features

- **Conversational Planning & Validation**
  Turn unstructured travel ideas into structured itineraries using advanced AI inference. If a prompt is missing key information (destination, dates, participants, budget), the system safely halts and asks the user for clarification.
- **Real-time Streaming**
  Results are streamed progressively via Server-Sent Events (SSE). The AI uses token-level streaming to prevent gateway timeouts, and partial itinerary/flight data is pushed to the frontend as soon as it's ready.
- **Flight & Hotel Orchestration**
  Provides accurate data routing with flight options linked directly to Skyscanner and Google Flights. Smart routing detects local vs. international travel and bypasses unnecessary flight steps.
- **Enhanced POI (Point of Interest) Enrichment**
  Aggregates real Google Reviews, star ratings, and accurate real-world cost metrics for both daily activities and food recommendations.
- **Smart Multi-Currency Ledger**
  Splits costs equally using live currency conversions powered by the open, keyless Fawaz Ahmed Exchange API (`@fawazahmed0/currency-api`). Falls back to static rates if the CDN is unavailable.
- **Interactive Map Integration**
  Every generated activity is dynamically embedded as a Google Maps iframe showing the exact location.
- **Secure Settlement UI**
  A card payment modal allows group members to settle their share. Invalid cards (e.g., starting with `0000`) are rejected with a clear error.

---

## 🧠 Multi-Agent Architecture

DaddiesTrip uses a modular **4-Agent Workflow** executed sequentially. Each agent is strictly scoped to a single domain to reduce hallucination and improve speed.

### 1. Analyzer Agent *(Pure Python — zero LLM cost)*
- **Role:** Input validation gatekeeper.
- **How it works:** Uses regex and keyword matching to verify 4 required fields: Destination, Trip Dates, Participants, and Budget. If any are missing, returns a structured `clarification` event with the specific missing fields so the frontend can show a targeted prompt.

### 2. Planner Agent *(LLM — streamed)*
- **Role:** Chronological itinerary drafter.
- **How it works:** Given the validated prompt, generates a day-by-day itinerary with activities, food recommendations, transport between POIs, and a `requires_flight` flag. Output is streamed token-by-token to prevent API gateway timeouts.

### 3. Booking Agent *(LLM — streamed)*
- **Role:** Real-world booking and cost enrichment concierge.
- **How it works:** Receives a compressed version of the planner output and enriches each day with hotel names/costs, flight options (3 airlines with Skyscanner/Google Flights deep-links), food costs, and destination review metadata. Token streaming keeps the connection alive during generation.

### 4. Edge Agent *(Pure Python — zero LLM cost)*
- **Role:** Quality assurance and data integrity.
- **How it works:** Runs deterministic Python heuristic checks on the final merged JSON before it's emitted:
  - Detects and nullifies hallucinated uniform activity costs (e.g., every activity priced at exactly RM25).
  - Flags round-trip flights with identical departure and return airports.
  - Ensures every itinerary day has required fields (`day`, `location`).

> **Note:** The Budget Agent and Translation Agent have been removed. Budget calculation is now handled entirely in Python inside the Orchestrator (`_calculate_budget`), eliminating an LLM call and making cost computation instant and deterministic.

---

## 🛠 Setup & Deployment Instructions

### 1. Install Python Environment
Ensure you have **Python 3.10+** installed.
```bash
pip install -r backend/requirements.txt
```

### 2. Configure Environment Variables
Create a `.env` file in the **root directory** with your LLM API credentials:
```env
Z_AI_API_KEY=your_api_key_here
Z_AI_BASE_URL=https://api.ilmu.ai/v1/chat/completions
Z_AI_MODEL=glm-4
```

> The `Z_AI_BASE_URL` accepts either the base URL (`https://api.ilmu.ai/v1`) or the full completions endpoint — the server normalizes it automatically.

### 3. Start the Backend (FastAPI)
Run from the **root directory** of the project:
```bash
uvicorn backend.main:app --reload
```
The API will be available at `http://localhost:8000`.

### 4. Start the Frontend (Vite + React)
In a separate terminal, navigate to the `frontend` directory:
```bash
cd frontend
npm install
npm run dev
```

### 5. Access the Application
Open your browser and navigate to the Vite dev server:
```
http://localhost:5173
```

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/plan-trip-stream` | Streams the full trip planning pipeline as SSE events |
| `POST` | `/api/settle` | Simulates a card payment settlement for the group ledger |
| `GET`  | `/api/health` | Health check — returns `{"status": "ok"}` |

### SSE Event Types (`/api/plan-trip-stream`)

| Event Type | Payload | When |
|------------|---------|------|
| `progress` | `{ text }` | Each pipeline stage starts |
| `clarification` | `{ message, missing_fields }` | Prompt is missing required info |
| `partial_itinerary` | `{ days, num_participants }` | Planner output ready |
| `partial_flights` | `{ flight_options, num_participants }` | Booking output ready |
| `complete` | Full trip data object | All agents finished |
| `error` | `{ message }` | Any pipeline failure |

---

## ⚙️ Testing & QA

The application ships with a PyTest suite covering key acceptance criteria.

Run from the root directory:
```bash
pytest backend/tests/test_agents.py
```

**Test Coverage:**
- **TC-01:** Verifies the full streaming pipeline returns a correct payload schema including itinerary, flights, budget, and split data.
- **TC-02:** Verifies that invalid payment cards (starting with `0000`) are correctly rejected by the ledger service.
- **AI-01:** Verifies that oversized prompts (>1500 words) are safely truncated before being passed to the LLM pipeline.
