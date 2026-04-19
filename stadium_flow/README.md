# 🏟️ StadiumFlow AI — Smart Venue Experience Platform

> A multi-agent AI system that optimizes crowd movement, reduces waiting times, and provides real-time coordination for large-scale sporting venues.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green.svg)](https://fastapi.tiangolo.com)
[![Google Gemini](https://img.shields.io/badge/Google-Gemini%20AI-orange.svg)](https://ai.google.dev)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 🎯 Problem Statement

Large-scale sporting venues (100,000+ capacity) face critical challenges:

- **Crowd Bottlenecks** — Uneven distribution causes dangerous congestion at entry gates, concourses, and concession areas
- **Long Wait Times** — Fans spend 15-25% of event time in queues instead of enjoying the action
- **Poor Coordination** — Disconnected systems prevent real-time response to crowd dynamics
- **Accessibility Gaps** — Attendees with disabilities lack real-time navigation assistance

## 💡 Solution: StadiumFlow AI

StadiumFlow AI transforms venue management with a **multi-agent AI architecture** that provides:

1. **🤖 Sentinel Agent** — Real-time crowd density monitoring with predictive congestion alerts
2. **💬 Concierge Agent** — AI-powered fan assistant (Google Gemini) for navigation, recommendations, and accessibility
3. **👮 Orchestra Agent** — Automated staff coordination and resource deployment
4. **🗺️ Interactive Dashboard** — Live venue map with congestion heatmap and activity feed

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend Dashboard                        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │ Live Map │ │Zone List │ │AI Chat   │ │Feed      │       │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘       │
│       └─────────────┴────────────┴─────────────┘             │
│                         WebSocket                            │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────┐
│                    FastAPI Backend                            │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐               │
│  │ Sentinel  │  │ Concierge │  │ Orchestra │               │
│  │  Agent    │  │  Agent    │  │  Agent    │               │
│  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘               │
│        └───────────────┼───────────────┘                     │
│               Shared Memory Bus                              │
│            (Pub/Sub Pattern)                                 │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐               │
│  │Simulation │  │ Routing   │  │ Analytics │               │
│  │ Engine    │  │ Engine    │  │ Service   │               │
│  └───────────┘  └───────────┘  └───────────┘               │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────┐
│                   Google Services                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │Gemini AI │  │Google    │  │BigQuery  │  │Firebase  │   │
│  │          │  │Maps     │  │Analytics │  │Auth      │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## ☁️ Google Services Integration

| Service | Purpose | Implementation |
|---------|---------|---------------|
| **Gemini AI** | AI Concierge conversational assistant | System prompts with venue context, streaming responses, smart fallback |
| **Google Maps** | Navigation and outdoor directions | Directions API for venue approach, custom indoor routing engine |
| **Firebase Auth** | Secure API access control | JWT token verification, API key validation middleware |
| **BigQuery** | Analytics and crowd pattern analysis | Time-series data logging, historical trend queries, peak time predictions |
| **Cloud Pub/Sub** | Real-time messaging (pattern) | SharedMemory bus for inter-agent event-driven communication |

---

## 🚀 Quick Start

### Prerequisites
- Python 3.12+
- pip

### 1. Clone & Install

```bash
cd stadium_flow
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your Google API keys (optional — works without them in demo mode)
```

### 3. Run the Application

```bash
python -m uvicorn app.main:app --reload --port 8000
```

### 4. Open the Dashboard

Navigate to **http://localhost:8000** for the live dashboard, or **http://localhost:8000/docs** for the API documentation.

### 5. Run Tests

```bash
pytest tests/ -v --cov=app
```

---

## 📁 Project Structure

```
stadium_flow/
├── app/
│   ├── main.py                  # FastAPI entry point + lifespan
│   ├── core/
│   │   ├── config.py            # Pydantic Settings (env vars)
│   │   ├── security.py          # Auth, rate limiting, sanitization
│   │   └── logging_config.py    # Structured logging + correlation IDs
│   ├── api/
│   │   ├── routes/
│   │   │   ├── venues.py        # Venue info & stats
│   │   │   ├── zones.py         # Zone status & heatmaps
│   │   │   ├── routing.py       # Dijkstra pathfinding
│   │   │   ├── chat.py          # AI Concierge (Gemini)
│   │   │   └── websocket.py     # Real-time WS updates
│   │   └── middleware.py        # CORS, tracing, timing
│   ├── models/                  # Domain models (dataclasses)
│   ├── schemas/                 # Pydantic request/response models
│   ├── services/
│   │   ├── simulation_engine.py # Agent-based crowd simulation
│   │   ├── routing_engine.py    # Dijkstra + congestion avoidance
│   │   ├── crowd_analytics.py   # Heatmaps, predictions, wait times
│   │   └── google_services.py   # Gemini, Maps, BigQuery wrappers
│   ├── agents/
│   │   ├── base_agent.py        # Abstract agent + SharedMemory bus
│   │   ├── sentinel_agent.py    # Crowd intelligence
│   │   ├── concierge_agent.py   # Fan assistant (Gemini AI)
│   │   └── orchestra_agent.py   # Staff coordination
│   └── database/
│       ├── connection.py        # Async SQLite setup
│       └── repository.py        # Repository pattern (events, analytics, chat)
├── frontend/
│   ├── index.html               # Dashboard (semantic HTML5, ARIA)
│   ├── css/styles.css           # Glassmorphism design system
│   └── js/
│       ├── app.js               # Main orchestrator
│       ├── dashboard.js         # Stats, zone list, activity feed
│       ├── map.js               # Interactive SVG venue map
│       ├── chat.js              # AI Concierge widget
│       ├── websocket.js         # Auto-reconnect WS client
│       └── accessibility.js     # A11y utilities
├── tests/
│   ├── conftest.py              # Shared fixtures
│   ├── test_simulation.py       # Simulation engine tests
│   ├── test_routing.py          # Routing engine tests
│   ├── test_agents.py           # Multi-agent system tests
│   └── test_api.py              # API endpoint tests
├── requirements.txt
├── Dockerfile                   # Multi-stage, non-root user
├── docker-compose.yml
├── pyproject.toml               # pytest + ruff config
├── .env.example
└── README.md
```

## 🎨 Key Features

### Smart Dynamic Assistant
- **Context-Aware AI** — Gemini-powered responses with real-time venue state injection
- **Predictive Routing** — Dijkstra's algorithm with dynamic congestion-aware weights
- **Autonomous Agents** — Perceive → Decide → Act lifecycle with inter-agent communication

### Logical Decision Making
- **SentinelAgent** — Threshold-based crowd alerts with deduplication and auto-resolution
- **OrchestraAgent** — Proactive staff deployment based on predictive occupancy trends
- **ConciergeAgent** — Intent detection, destination inference, and wait time estimation

### Accessibility (WCAG 2.1 AA)
- Skip navigation links
- ARIA labels and live regions
- Keyboard-navigable venue map
- High-contrast mode (Alt+H)
- Screen reader announcements
- `prefers-reduced-motion` support

### Security
- Constant-time API key comparison (prevents timing attacks)
- Input sanitization (XSS prevention)
- Rate limiting (sliding window)
- CORS configuration
- Non-root Docker container
- Environment-based secret management

---

## 📊 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/health` | System health check |
| `GET` | `/api/v1/venues/info` | Venue information |
| `GET` | `/api/v1/venues/stats` | Dashboard statistics |
| `GET` | `/api/v1/zones/` | List all zones |
| `GET` | `/api/v1/zones/{id}` | Zone details |
| `GET` | `/api/v1/zones/analytics/heatmap` | Crowd density heatmap |
| `GET` | `/api/v1/zones/analytics/recommendations` | AI recommendations |
| `GET` | `/api/v1/zones/{id}/prediction` | Congestion prediction |
| `POST` | `/api/v1/routing/find` | Find optimal route |
| `GET` | `/api/v1/routing/nearest/{zone}/{type}` | Find nearest facility |
| `POST` | `/api/v1/chat/message` | AI Concierge chat |
| `GET` | `/api/v1/chat/quick-actions` | Quick action buttons |
| `WS` | `/ws/dashboard` | Real-time updates |

---

## 🧪 Testing

```bash
# Run all tests with coverage
pytest tests/ -v --cov=app --cov-report=html

# Run specific test modules
pytest tests/test_simulation.py -v    # Crowd simulation
pytest tests/test_routing.py -v       # Pathfinding
pytest tests/test_agents.py -v        # Multi-agent system
pytest tests/test_api.py -v           # API endpoints
```

## 🐳 Docker Deployment

```bash
# Build and run
docker-compose up --build

# Or deploy to Google Cloud Run
gcloud run deploy stadiumflow --source .
```

---

## 📄 License

MIT License — Built for the hackathon with ❤️
