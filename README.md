# Procura - BOM/PO Multi-Agent System

A multi-agent AI system for Bill of Materials (BOM) processing and Purchase Order (PO) automation. Built to demonstrate expertise in agentic AI architectures.

## Features

- **Multi-Agent Architecture**: 5 specialized agents working together via LangGraph
- **RAG-Powered Matching**: Semantic search for supplier/part matching using pgvector
- **Human-in-the-Loop**: Approval workflows for critical decisions
- **Real-time Progress**: WebSocket updates during processing
- **Modern UI**: React + Tailwind with Framer Motion animations

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Frontend   │────▶│   Backend    │────▶│  PostgreSQL  │
│  React/TS    │     │   FastAPI    │     │  + pgvector  │
└──────────────┘     └──────────────┘     └──────────────┘
                            │
                   ┌────────┴────────┐
                   │    LangGraph    │
                   │   Orchestrator  │
                   └────────┬────────┘
         ┌─────────┬───────┼───────┬─────────┐
         ▼         ▼       ▼       ▼         ▼
      Parser   Matcher  Optimizer  PO Gen  Tracker
      Agent    Agent    Agent      Agent   Agent
```

## Agents

1. **BOM Parser Agent** - Extracts items from Excel, CSV, PDF, images
2. **Supplier Matcher Agent** - Matches items to suppliers using RAG
3. **Pricing Optimizer Agent** - Optimizes supplier selection for cost
4. **PO Generator Agent** - Creates purchase orders
5. **Order Tracker Agent** - Tracks PO status

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Node.js 20+ (for local frontend dev)
- Python 3.12+ (for local backend dev)

### With Docker

```bash
# Clone and setup
cd Procura
cp .env.example .env
# Add your API keys to .env

# Start all services
docker-compose up -d

# Seed demo data
docker-compose exec backend python seed_db.py

# Open http://localhost:5173
```

### Local Development

```bash
# Start database
docker-compose up -d db redis

# Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python seed_db.py
uvicorn main:app --reload

# Frontend (new terminal)
cd frontend
npm install
npm run dev
```

## Demo Workflow

1. **Upload BOM** - Upload an Excel/CSV file with part numbers and quantities
2. **Watch Processing** - See the agents parse, match, and optimize in real-time
3. **Review Matches** - Approve low-confidence matches or select alternatives
4. **Generate POs** - Automatically create purchase orders grouped by supplier
5. **Approve & Send** - Review and approve POs over threshold amounts

## Tech Stack

| Component | Technology |
|-----------|------------|
| Frontend | React 18, TypeScript, Tailwind, Framer Motion |
| Backend | FastAPI, Python 3.12, Pydantic |
| Agents | LangGraph, LangChain, Claude Sonnet |
| Database | PostgreSQL + pgvector |
| Embeddings | OpenAI text-embedding-3-small |

## API Endpoints

### BOMs
- `POST /api/boms/upload` - Upload BOM file
- `GET /api/boms/{id}` - Get BOM with items
- `POST /api/boms/{id}/process` - Start processing
- `GET /api/boms/{id}/status` - Processing status

### Suppliers
- `GET /api/suppliers` - List suppliers
- `POST /api/suppliers/search/semantic` - Semantic search

### Purchase Orders
- `GET /api/pos` - List POs
- `POST /api/pos/{id}/approve` - Approve/reject
- `POST /api/pos/{id}/send` - Send to supplier

### Agents
- `GET /api/agents/tasks` - List tasks
- `GET /api/agents/approvals` - Pending approvals
- `WS /api/agents/ws/tasks/{id}` - Real-time updates

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `ANTHROPIC_API_KEY` | Claude API key | Yes |
| `OPENAI_API_KEY` | OpenAI API key (embeddings) | Yes |
| `DATABASE_URL` | PostgreSQL connection | Yes |
| `LANGSMITH_API_KEY` | LangSmith for tracing | No |
| `PO_APPROVAL_THRESHOLD` | PO amount requiring approval | No (default: 10000) |

## Project Structure

```
Procura/
├── backend/
│   ├── api/           # FastAPI endpoints
│   ├── agents/        # LangGraph agents
│   ├── models/        # SQLAlchemy models
│   ├── tools/         # Agent tools
│   ├── services/      # Business logic
│   └── prompts/       # Agent prompts
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── hooks/
│   │   └── api/
│   └── package.json
├── data/
│   └── seed_data/     # Demo data
└── docker-compose.yml
```

## License

MIT
