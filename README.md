# QueueLess AI

**Know Before You Go.**

QueueLess AI is an AI-powered South African service-access assistant. Tell it what you need — it identifies the service, checks documents, predicts queues from sample/historical data, and recommends when and where to go.

> Not a live government queue tracker. MVP runs in **Demo Mode** with clearly labelled sample data.

## Quick start

```bash
cd "queless AI"
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
python -m backend.data.generate_queue_data
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000**

## Public prototype

Try the live demo: [QueueLess AI](https://queueless-ai-demo.onrender.com)

Deploy the demo to Render using the project Blueprint:

[Deploy QueueLess AI to Render](https://render.com/deploy?repo=https://github.com/mmolawamatenche-cloud/queueless-ai)

The hosted app is a public prototype, not a live government service. It uses sample queue data and has no DHA integration. Plans, reports, and feedback are held in in-memory storage and may reset when the service restarts or redeploys. Do not enter sensitive personal information.

## 2-minute demo

1. Home → enter: `I need to renew my passport.`
2. AI identifies **Passport renewal** (Home Affairs).
3. AI analyses branches / queues / documents.
4. You get a plan: branch, wait range, recommended time, checklist.
5. **Report Queue** → submit crowd level → prediction updates.
6. **Dashboard** shows reports and model metrics.

## Stack

| Layer | Tech |
|--------|------|
| Frontend | HTML, CSS, JavaScript |
| Backend | Python, FastAPI |
| AI / ML | Rule + pattern NLU, scikit-learn Gradient Boosting |
| Data | CSV sample datasets + SQLite reports/plans |

## API

- `POST /api/assist` — full AI plan
- `POST /api/classify` — service intent only
- `GET /api/documents?service_id=...` — document checklist, optionally filtered by service
- `POST /api/reports` — crowdsourced queue report
- `GET /api/dashboard` — admin metrics
- `GET /api/history` — past plans
- `GET /api/health` — status + model meta

## Data labels

- **Demo Mode** — no live DHA API
- Predictions = **AI estimate based on historical/sample data**
- Crowd submissions = **user-reported**
- Document lists = **sample MVP checklist** (confirm with Home Affairs)

## Project layout

```text
queueless-ai/
├── frontend/
├── backend/
│   ├── main.py
│   ├── ai/
│   ├── data/
│   └── database/
├── models/
├── requirements.txt
└── README.md
```

## Value proposition

QueueLess AI understands what you need, predicts service demand, checks what you need before you travel, and recommends when and where to go.

**Less waiting. Fewer wasted trips. Smarter access to essential services.**
