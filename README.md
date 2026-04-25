<div align="center">
  <img src="frontend/logo.jpeg" alt="DaddiesTrip Logo" width="150" style="border-radius: 20px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); margin-bottom: 20px;">

  <h1>DaddiesTrip</h1>

  <p><strong>An AI-Enabled Cross-Border Travel Orchestration & Group Accounting Platform</strong></p>

  <p>
    <a href="https://daddies-trip.vercel.app/"><strong>Live Demo</strong></a>
  </p>

  [![Vite](https://img.shields.io/badge/Vite-B73BFE?style=for-the-badge&logo=vite&logoColor=FFD62E)](https://vitejs.dev/)
  [![React](https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)](https://reactjs.org/)
  [![FastAPI](https://img.shields.io/badge/fastapi-109989?style=for-the-badge&logo=FASTAPI&logoColor=white)](https://fastapi.tiangolo.com/)
  [![Python](https://img.shields.io/badge/Python-FFD43B?style=for-the-badge&logo=python&logoColor=blue)](https://www.python.org/)
  [![Railway](https://img.shields.io/badge/Railway-0B0D0E?style=for-the-badge&logo=railway&logoColor=white)](https://railway.app/)
  [![Vercel](https://img.shields.io/badge/Vercel-000000?style=for-the-badge&logo=vercel&logoColor=white)](https://vercel.com/)
</div>

<br />

## Table of Contents
- [Project Overview](#-project-overview)
- [Key Features](#-key-features)
- [System Architecture](#-system-architecture)
- [Local Development Setup](#-local-development-setup)
- [Deployment](#-deployment)
  - [Backend on Railway](#-backend-on-railway-recommended)
  - [Frontend on Vercel](#-frontend-on-vercel)
- [API Documentation](#-api-documentation)
- [Testing & QA](#-testing--qa)

---

## Project Overview

**DaddiesTrip** addresses the highly fragmented process of group travel planning and multi-currency expense management. Typically, users switch between multiple apps for itinerary drafting, flight bookings, map routing, and manual spreadsheet calculations for cost splitting.

**Our Mission:** Automate the entire lifecycle of group travel through a unified, conversational interface. From initial natural language prompts to structured itineraries, real-world flight options, and precise multi-currency expense splitting, DaddiesTrip provides a frictionless and secure digital planning experience.

---

## Key Features

- **Conversational Planning & Validation:** Transforms unstructured text into strict JSON itineraries using advanced LLM inference. If critical parameters (destination, dates, participants, budget) are missing, the pipeline halts safely and requests user clarification.
- **Real-Time Token Streaming (SSE):** Utilizes Server-Sent Events to stream data progressively. This prevents API gateway timeouts and delivers an ultra-responsive UI experience.
- **Flight & Hotel Orchestration:** Intelligently routes flight options using real-world airline data. Bypasses flight generation for localized travel dynamically.
- **POI Enrichment:** Aggregates real-world cost metrics, Google Reviews, and star ratings for activities, dining, and accommodations.
- **Smart Multi-Currency Ledger:** Calculates exact cost divisions across groups using live exchange rates via the open `@fawazahmed0/currency-api`, with deterministic offline fallbacks.
- **Interactive Geolocation:** Dynamically embeds Google Maps iframes for every generated activity point.
- **Responsive UI/UX:** Built with Tailwind CSS, the application is fully responsive, ensuring flawless operation across mobile, tablet, and desktop viewports.

---

## System Architecture

DaddiesTrip utilizes a highly modular **4-Agent Pipeline**, strictly decoupling tasks to eliminate LLM hallucinations and optimize processing speed.

```mermaid
graph TD
    A[Client Prompt] --> B[Analyzer Agent]
    B -- "Missing Info" --> A
    B -- "Valid Prompt" --> C[Planner Agent]
    C -- "Draft Itinerary" --> D[Booking Agent]
    D -- "Enriched POIs & Flights" --> E[Edge Agent]
    E -- "Validated Data" --> F[Orchestrator]
    F -- "SSE Stream" --> G[Frontend UI]
```

1. **Analyzer Agent *(Python Heuristics)*:** Validates the prompt using regex and keyword extraction. Ensures strict adherence to required fields before incurring any LLM costs.
2. **Planner Agent *(LLM Stream)*:** Drafts the chronological day-by-day itinerary, including transport vectors and activity logic.
3. **Booking Agent *(LLM Stream)*:** Injects real-world metadata (hotels, flights, precise POI costs, and star ratings) into the planner's draft.
4. **Edge Agent *(Python Heuristics)*:** A deterministic QA layer that nullifies AI hallucinations (e.g., repeating identical costs, invalid flight routes) before final payload emission.

---

## Local Development Setup

### Prerequisites
- **Python 3.10+**
- **Node.js 18+** & npm
- Valid **Ilmu AI API Key** (or compatible OpenAI-format API key)

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/UMHackathon-DaddiesTrip.git
cd UMHackathon-DaddiesTrip
```

### 2. Environment Configuration
Copy the example env file and fill in your keys:
```bash
cp .env.example .env
```

Edit `.env`:
```env
Z_AI_API_KEY=your_api_key_here
Z_AI_BASE_URL=https://api.ilmu.ai/v1/chat/completions
Z_AI_MODEL=glm-4

# Leave empty for local dev (Vite proxy handles it)
VITE_API_BASE_URL=
```

### 3. Backend Setup (FastAPI)
Install dependencies and run the server (Terminal 1):
```bash
python -m pip install -r requirements.txt
python -m uvicorn backend.main:app --reload
```
The API will run at `http://localhost:8000`. Verify via the health check: `http://localhost:8000/api/health`.

### 4. Frontend Setup (React/Vite)
Install node modules and start the dev server (Terminal 2):
```bash
cd frontend
npm install
npm run dev
```
The Vite dev server will start at `http://localhost:5173`. API requests are automatically proxied to the backend.

---

## Deployment

The app uses a **split deployment** architecture:
- **Backend** (FastAPI) on **Railway** — no timeout limits, supports long-running LLM agent pipelines
- **Frontend** (React/Vite) on **Vercel** — fast CDN-served static site

### Why Railway for the Backend?

Vercel Serverless Functions have a **10-second timeout on the Hobby plan** and **60 seconds on Pro**. The DaddiesTrip agent pipeline (Analyzer → Planner → Booking) can take 30–90+ seconds per request. Railway runs **persistent containers** with no hard timeout, making it the right fit.

### Backend on Railway (Recommended)

1. **Create a Railway project**
   - Go to [railway.app](https://railway.app) and sign up
   - Click **"New Project"** → **"Deploy from GitHub repo"**
   - Select your repository

2. **Configure the service**
   - Railway auto-detects the `Dockerfile` in the project root
   - No additional build configuration needed

3. **Set environment variables**
   In the Railway dashboard, go to **Variables** and add:
   ```
   Z_AI_API_KEY=your_api_key_here
   Z_AI_BASE_URL=https://api.ilmu.ai/v1/chat/completions
   Z_AI_MODEL=ilmu-glm-5.1
   ```
   Railway automatically provides the `PORT` variable.

4. **Deploy**
   - Railway builds and deploys automatically
   - Note your app URL (e.g. `https://daddiestrip-backend.up.railway.app`)
   - Test: visit `https://your-app.up.railway.app/api/health`

### Frontend on Vercel

1. **Set the API base URL**
   In your `.env` file (or Vercel dashboard environment variables), set:
   ```
   VITE_API_BASE_URL=https://your-app.up.railway.app
   ```
   This tells the frontend to call the Railway backend instead of using relative paths.

2. **Deploy to Vercel**
   - Connect your GitHub repository to Vercel
   - Set the **Framework Preset** to `Vite`
   - Set the **Root Directory** to `./`
   - Add the environment variable `VITE_API_BASE_URL` with your Railway backend URL
   - Deploy

3. **Update `vercel.json`**
   The `vercel.json` no longer needs the `api/` function config since the backend is on Railway. The rewrites for `/api/*` can be removed — the frontend now calls the Railway URL directly.

### Fallback: All-in-One Vercel Deployment

If you prefer to keep everything on Vercel (with timeout limitations):

1. Follow the original setup with `vercel.json` pointing `api/` to the Python serverless function
2. Set environment variables in the Vercel dashboard
3. Note: Vercel Hobby plan has a **10-second timeout** — expect failures on complex prompts. Pro plan allows up to 60 seconds.

---

## API Documentation

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/plan-trip-stream` | Primary pipeline trigger. Streams data via Server-Sent Events (SSE). |
| `POST` | `/api/amend-item` | Amend a specific hotel, food, or activity item. |
| `POST` | `/api/settle` | Simulates secure group ledger card payment settlement. |
| `GET`  | `/api/health` | Service health check. |

### SSE Stream Payload States (`/api/plan-trip-stream`)
| Event Type | Payload Data | Trigger Condition |
|------------|--------------|-------------------|
| `progress` | `{ text }` | Emitted when a new pipeline stage begins. |
| `clarification` | `{ message, missing_fields }` | Emitted if the Analyzer Agent detects missing prompt context. |
| `partial_itinerary`| `{ days, num_participants }` | Emitted when the Planner Agent completes drafting. |
| `partial_flights` | `{ flight_options, num_participants }` | Emitted when the Booking Agent resolves transport. |
| `complete` | `{ data: FullTripObject }` | Final payload emission upon Edge Agent validation. |
| `error` | `{ message }` | Fatal pipeline failure. |

---

## Testing & QA

DaddiesTrip includes a comprehensive PyTest suite covering agent validation, streaming schema integrity, and ledger operations.

Execute tests from the root directory:
```bash
python -m pytest backend/tests/test_agents.py
```

**Key Test Coverage:**
- `TC-01`: Validates end-to-end SSE pipeline schema generation (Itinerary, Flights, Budget, Split).
- `TC-02`: Validates deterministic ledger rejections for invalid payment methods.
- `AI-01`: Ensures buffer overflow protection against massive user prompts.

---
<div align="center">
  <i>Engineered with ❤️ by UTM's students</i>
</div>
