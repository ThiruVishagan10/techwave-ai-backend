# PathBridge 2.0 — AI Career Intelligence Backend

> **Discover. Verify. Match.**  
> An explainable, AI-powered internship and job discovery, trust verification, and career recommendation backend engine built with **FastAPI**, **Google Gemini API**, and **PostgreSQL/Supabase**.

---

## 1. What PathBridge Is

**PathBridge 2.0** is an opportunity intelligence platform that transforms the college-to-career pipeline. Traditional job boards overwhelm students with noise, ambiguous prerequisites, and predatory ghost postings. PathBridge helps students answer three fundamental career questions:

1. **Can I find the opportunity?** — Multi-faceted, real-time discovery of internships and early-career roles.
2. **Can I trust the opportunity?** — Dual-layer AI and deterministic verification engine detecting scam posts, upfront fee schemes, and domain spoofing.
3. **Is this opportunity right for me?** — Explainable, multi-dimensional alignment analysis with matched skills, skill gap diagnostics, and action roadmaps.

---

## 2. Problem Being Solved

- **The Information Asymmetry Gap**: Students spend hours submitting resumes to roles where requirements don't match or where postings are already obsolete.
- **The Recruitment Fraud Epidemic**: Fraudulent postings on Telegram, WhatsApp, and spoofed domains trick students into paying "registration deposits", "equipment fees", or sharing crypto keys.
- **The Black-Box Rejection Problem**: Generic platforms give arbitrary match percentages without explainability, leaving students clueless about what skills to learn next.

PathBridge solves this by pairing **deterministic rules engines** with **Google Gemini structured intelligence** to deliver **explainable recommendations** and **trust confidence scores**.

---

## 3. Architecture

```mermaid
graph TD
    Client["Next.js Frontend (Port 3000)"]
    API["FastAPI Intelligence Gateway (Port 8000)"]
    
    subgraph "Core AI Services (app/ai)"
        PA["Profile Analyzer (PyMuPDF + Gemini)"]
        ME["Matcher Engine (Multi-Dimension Alignment)"]
        VE["Verification Engine (Rules + Gemini Trust Signals)"]
        RE["Recommender (Composite Multi-Objective Ranking)"]
    end
    
    subgraph "External AI & Data"
        Gemini["Google Gemini 3.8 Flash / Embeddings"]
        DB[("PostgreSQL / Supabase (Fallback: Async SQLite)")]
    end

    Client -->|REST API / JSON| API
    API --> PA
    API --> ME
    API --> VE
    API --> RE
    
    PA -->|Structured Schema| Gemini
    ME -->|Semantic Reasoning| Gemini
    VE -->|Safety Audit| Gemini
    
    API --> DB
```

---

## 4. Technology Stack

- **Runtime & Web Framework**: Python 3.11+, [FastAPI](https://fastapi.tiangolo.com/), [Uvicorn](https://www.uvicorn.org/)
- **Data Validation & Settings**: [Pydantic v2](https://docs.pydantic.dev/), `pydantic-settings`
- **Generative AI & LLM**: [Official Google GenAI SDK](https://github.com/google-gemini/generative-ai-python) (`google-genai`), Gemini 3.8 Flash, `gemini-embedding-001`
- **PDF Resume Ingestion**: [PyMuPDF](https://pymupdf.readthedocs.io/)
- **Database & Persistence**: [SQLAlchemy 2.0 Asyncio](https://docs.sqlalchemy.org/), `asyncpg` (PostgreSQL / Supabase), `aiosqlite` (Zero-config local fallback)
- **HTTP Client**: [httpx](https://www.python-httpx.org/)
- **Testing**: [pytest](https://docs.pytest.org/), `pytest-asyncio`

---

## 5. Gemini AI Integration

PathBridge leverages the official Google GenAI SDK (`google-genai >= 2.3.0`) with model `gemini-3.8-flash`:

1. **Structured Outputs (`response_schema`)**:
   Instead of parsing unstructured markdown, Gemini directly outputs strict Pydantic schemas:
   - `StructuredProfileOutput`: Extracted degrees, categorized skills, prior internships, and quantifiable project impacts.
   - `StructuredMatchOutput`: Multi-dimensional score breakdown (`skills_score`, `experience_score`, `education_score`, `preference_score`, `career_alignment_score`, `matched_skills`, `skill_gaps`, `explanation`).
   - `StructuredVerificationOutput`: Confidence percentage, trust signals, verified attributes, and detected fraud risk factors.
2. **Semantic Similarity (Embeddings)**:
   Computes vector embeddings via `gemini-embedding-001` to capture latent semantic affinity between candidate project descriptions and job responsibilities.
3. **Resilient Demo Mode / Rate Limit Guard**:
   - Recommendations and verification audits are cached in the database.
   - If `GEMINI_API_KEY` is temporarily offline or rate-limited, the system falls back to high-fidelity deterministic heuristics without crashing.

---

## 6. Database Schema

The backend uses clean relational schemas with JSON/JSONB fields for AI flexibility:

```text
├── profiles
│   ├── id (PK)
│   ├── user_id
│   ├── name, education, skills, experience, projects
│   ├── career_interests, preferred_locations, preferred_work_modes
│   ├── resume_text, profile_strength
│   └── created_at, updated_at
│
├── opportunities
│   ├── id (PK)
│   ├── company, title, description, location, work_mode, opportunity_type
│   ├── skills, eligibility, salary, deadline, source_url, application_url
│   ├── company_domain, verification_status, verification_score
│   ├── responsibilities, requirements, benefits, verification_checks
│   └── created_at, updated_at
│
├── recommendations
│   ├── id (PK)
│   ├── profile_id (FK -> profiles.id)
│   ├── opportunity_id (FK -> opportunities.id)
│   ├── match_score, skills_score, experience_score, education_score
│   ├── preference_score, career_alignment_score
│   ├── matched_skills, skill_gaps, explanation
│   └── created_at (UNIQUE constraint on profile_id, opportunity_id)
│
├── verifications
│   ├── id (PK)
│   ├── opportunity_id (FK -> opportunities.id)
│   ├── status (VERIFIED | NEEDS_REVIEW | SUSPICIOUS)
│   ├── confidence, signals, risk_factors, explanation
│   └── created_at
│
└── applications
    ├── id (PK)
    ├── profile_id (FK -> profiles.id)
    ├── opportunity_id (FK -> opportunities.id)
    ├── status (SAVED | APPLIED | INTERVIEW | REJECTED | OFFER)
    ├── applied_at, notes, metadata_info
    └── created_at, updated_at
```

---

## 7. API Endpoints

All responses adhere to the standard envelope:
```json
{
  "success": true,
  "data": {},
  "error": null
}
```

### Health Check
- `GET /health` — Service status check (`{"status": "ok", "service": "pathbridge-ai", "version": "0.1.0"}`).

### Career Profiles (`/api/profiles`)
- `POST /api/profiles/analyze` — Upload resume PDF (`multipart/form-data`) or pass `resume_text` to extract candidate profile using Gemini.
- `GET /api/profiles/{id}` — Fetch profile by ID or user ID.
- `GET /api/profiles` — List profiles.
- `POST /api/profiles` — Create profile manually.

### Opportunities (`/api/opportunities`)
- `GET /api/opportunities` — Query opportunities with filters (`search`, `location`, `work_mode`, `opportunity_type`, `verification_status`, `minimum_match`, `skills`).
- `GET /api/opportunities/{id}` — Get single opportunity details.
- `POST /api/opportunities` — Create new opportunity.
- `POST /api/opportunities/{id}/verify` — Trigger AI verification analysis on an opportunity.
- `POST /api/opportunities/actions/seed` — Seed opportunities from `seed/opportunities.json`.

### Recommendations & Matching (`/api/recommendations`)
- `POST /api/recommendations/match` — Compare profile with opportunity; returns multi-dimensional scores, matched skills, skill gaps, and explanation.
- `GET /api/recommendations/{profile_id}` — Ranked recommendations prioritized by eligibility, match score, trust status, and career alignment.

### Verification Engine (`/api/verification`)
- `POST /api/verification/analyze` — Audit opportunity or external URL for upfront fee demands, unofficial domains, and scam channels.

### Application Tracking (`/api/applications`)
- `GET /api/applications/{profile_id}` — Retrieve candidate applications Kanban list.
- `POST /api/applications` — Save or apply to role (`SAVED`, `APPLIED`, `INTERVIEW`, `REJECTED`, `OFFER`).
- `PATCH /api/applications/{id}` — Update stage or notes.
- `DELETE /api/applications/{id}` — Remove application record.

---

## 8. Environment Variables

Create `.env` based on `.env.example`:

```bash
# Gemini AI API Configuration
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-3.8-flash

# Database Configuration (PostgreSQL / Supabase / SQLite Fallback)
# For Supabase / PostgreSQL:
# DATABASE_URL=postgresql+asyncpg://postgres:[YOUR-PASSWORD]@db.[YOUR-PROJECT].supabase.co:5432/postgres
# For Local Zero-Config SQLite Fallback:
DATABASE_URL=sqlite+aiosqlite:///./pathbridge.db

# Supabase Credentials (Optional)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_anon_or_service_key

# Application Settings
ENVIRONMENT=development
PORT=8000
HOST=0.0.0.0
CORS_ORIGINS=["http://localhost:3000","http://127.0.0.1:3000","http://localhost:8000"]
LOG_LEVEL=info
```

---

## 9. Local Setup

### 1. Clone Repository & Navigate
```bash
git clone https://github.com/ThiruVishagan10/techwave-ai-backend.git
cd techwave-ai-backend
```

### 2. Setup Virtual Environment
```bash
# Windows
python -m venv .venv
.\.venv\Scripts\activate

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment
```bash
cp .env.example .env
# Edit .env and insert your GEMINI_API_KEY
```

### 5. Run the Server
```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The API documentation will be available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- Health check: `http://localhost:8000/health`

### 6. Run the Test Suite
```bash
python -m pytest -v tests/test_api.py
```

---

## 10. End-to-End Demo Flow

```text
1. Student profile initialized (Alex Morgan — AI & Data Science @ NIT)
   ↓
2. Student views Opportunities:
   GET /api/opportunities?work_mode=Hybrid
   ↓
3. Student loads personalized recommendations:
   GET /api/recommendations/profile-alex-morgan
   → Microsoft AI/ML Intern is ranked #1 (94% match)
   ↓
4. Student views explainable match breakdown:
   POST /api/recommendations/match
   → Matched: Python, PyTorch, SQL, Machine Learning, Data Analysis
   → Skill Gap: Azure (Cloud Fundamentals)
   → AI Explanation explains alignment with medical imaging research
   ↓
5. Student checks trust & verification:
   POST /api/verification/analyze (with opp-msft-aiml)
   → VERIFIED (Confidence: 96%)
   → Official DNSSEC domain & Workday ATS confirmed
   ↓
6. Student tests scam detection:
   POST /api/verification/analyze (with opp-cryptoapex-scam)
   → SUSPICIOUS (Confidence: 94%)
   → Flags upfront ₹1,500 security deposit & unauthorized Telegram redirect
   ↓
7. Student clicks "Apply":
   POST /api/applications
   → Status: APPLIED
   ↓
8. Student moves role through recruitment funnel:
   PATCH /api/applications/{id}
   → Status: INTERVIEW -> OFFER
```

---

## 11. Current Limitations

- **Rate Limits on Free Gemini Tiers**: Free tier API keys are subject to requests-per-minute caps. PathBridge mitigates this by aggressively caching structured recommendations in PostgreSQL.
- **Pre-seeded Dataset**: In Round 1, opportunities are curated and verified in `seed/opportunities.json` rather than scraping thousands of unparsed web pages in real-time.

---

## 12. Future Roadmap

- **Autonomous Background Scraping Agent**: Antigravity/Gemini agents monitoring official university hiring portals weekly.
- **Enterprise ATS Webhooks**: Direct webhooks for Greenhouse, Lever, and Workday to automatically verify active job requisition statuses.
- **Mock Technical Interview Agent**: Interactive Gemini Live voice agent simulating technical rounds for matched roles based on diagnosed skill gaps.

---

## License
MIT License. Built for the TechWave Hackathon.
