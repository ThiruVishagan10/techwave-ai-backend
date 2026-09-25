import pytest
import pytest_asyncio
import uuid
import jwt
from datetime import datetime, timedelta, timezone
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.config import settings
from app.core.security import create_access_token
from app.db.database import init_db, AsyncSessionLocal
from app.services.opportunity_service import opportunity_service
from app.services.profile_service import profile_service
from app.services.user_service import user_service


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_db():
    await init_db()
    async with AsyncSessionLocal() as session:
        await user_service.seed_default_user(session)
        await opportunity_service.seed_from_file(session, "seed/opportunities.json")
        await profile_service.seed_default_profile(session, "seed/default_profile.json")


@pytest.fixture
def auth_headers():
    token = create_access_token({"sub": "user_default", "email": "alex.morgan@pathbridge.ai", "role": "student"})
    return {"Authorization": f"Bearer {token}"}


# ==========================================
# Health & Middleware Security Tests
# ==========================================

@pytest.mark.asyncio
async def test_health_check():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "pathbridge-ai"
        assert data["version"] == "0.1.0"


@pytest.mark.asyncio
async def test_middleware_blocks_unauthenticated_request():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Protected route without token must be blocked with 401
        res = await client.get("/api/opportunities")
        assert res.status_code == 401
        data = res.json()
        assert data["success"] is False
        assert data["error"]["code"] == "UNAUTHORIZED"
        assert "Authentication required" in data["error"]["message"]


@pytest.mark.asyncio
async def test_middleware_blocks_invalid_token():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Protected route with malformed/forged token must return 401
        res = await client.get(
            "/api/opportunities",
            headers={"Authorization": "Bearer this.is.a.completely.bogus.jwt"},
        )
        assert res.status_code == 401
        data = res.json()
        assert data["success"] is False
        assert data["error"]["code"] == "INVALID_TOKEN"


@pytest.mark.asyncio
async def test_middleware_blocks_expired_token():
    # Construct explicitly expired JWT token
    expired_payload = {
        "sub": "user_default",
        "email": "alex.morgan@pathbridge.ai",
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),
    }
    expired_token = jwt.encode(expired_payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(
            "/api/opportunities",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert res.status_code == 401
        data = res.json()
        assert data["success"] is False
        assert data["error"]["code"] == "INVALID_TOKEN"


@pytest.mark.asyncio
async def test_middleware_supports_cookie_token():
    token = create_access_token({"sub": "user_default", "email": "alex.morgan@pathbridge.ai", "role": "student"})
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", cookies={"access_token": token}) as client:
        res = await client.get("/api/opportunities")
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True


@pytest.mark.asyncio
async def test_middleware_exempt_routes():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Health check is open
        res_health = await client.get("/health")
        assert res_health.status_code == 200

        # 2. Interactive documentation is open
        res_docs = await client.get("/docs")
        assert res_docs.status_code == 200

        # 3. OpenAPI schema is open
        res_openapi = await client.get("/openapi.json")
        assert res_openapi.status_code == 200

        # 4. CORS preflight (OPTIONS) passes without auth
        res_options = await client.options(
            "/api/opportunities",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert res_options.status_code == 200


# ==========================================
# Authenticated Core API Endpoints
# ==========================================

@pytest.mark.asyncio
async def test_list_opportunities(auth_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/opportunities", headers=auth_headers)
        assert response.status_code == 200
        json_data = response.json()
        assert json_data["success"] is True
        assert isinstance(json_data["data"], list)
        assert len(json_data["data"]) > 0


@pytest.mark.asyncio
async def test_get_opportunity_by_id(auth_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/opportunities/opp-msft-aiml", headers=auth_headers)
        assert response.status_code == 200
        json_data = response.json()
        assert json_data["success"] is True
        assert json_data["data"]["company"] == "Microsoft"
        assert json_data["data"]["title"] == "AI/ML Intern"


@pytest.mark.asyncio
async def test_profile_analyze(auth_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resume_text = (
            "Alex Morgan\n"
            "Education: B.Tech in AI & Data Science, NIT (2027)\n"
            "Skills: Python, PyTorch, SQL, FastAPI, Docker, Machine Learning\n"
            "Projects: Predictive Healthcare Classifier, Distributed Stream ETL Pipeline"
        )
        response = await client.post(
            "/api/profiles/analyze",
            data={"resume_text": resume_text, "user_id": "test_user_1", "name": "Alex Morgan"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        json_data = response.json()
        assert json_data["success"] is True
        assert json_data["data"]["name"] is not None
        assert "Python" in json_data["data"]["skills"]


@pytest.mark.asyncio
async def test_matching_engine(auth_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        profile_res = await client.get("/api/profiles/profile-alex-morgan", headers=auth_headers)
        if profile_res.status_code != 200:
            seed_profile = {
                "name": "Alex Morgan",
                "skills": ["Python", "SQL", "Machine Learning", "PyTorch", "FastAPI"],
                "career_interests": ["AI/ML"],
                "preferred_locations": ["Hyderabad"],
                "preferred_work_modes": ["Hybrid"],
                "preferred_opportunity_types": ["Internship"],
            }
            create_res = await client.post("/api/profiles", json=seed_profile, headers=auth_headers)
            profile_id = create_res.json()["data"]["id"]
        else:
            profile_id = "profile-alex-morgan"

        match_req = {
            "profile_id": profile_id,
            "opportunity_id": "opp-msft-aiml",
            "force_refresh": True,
        }
        res = await client.post("/api/recommendations/match", json=match_req, headers=auth_headers)
        assert res.status_code == 200
        json_data = res.json()
        assert json_data["success"] is True
        match_data = json_data["data"]
        assert match_data["match_score"] > 60
        assert "Python" in match_data["matched_skills"]
        assert len(match_data["explanation"]) > 10


@pytest.mark.asyncio
async def test_recommendations_ranking(auth_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/recommendations/profile-alex-morgan", headers=auth_headers)
        assert res.status_code == 200
        json_data = res.json()
        assert json_data["success"] is True
        assert isinstance(json_data["data"], list)
        assert len(json_data["data"]) > 0


@pytest.mark.asyncio
async def test_verification_engine(auth_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Test verified opportunity
        res_msft = await client.post(
            "/api/verification/analyze",
            json={"opportunity_id": "opp-msft-aiml", "force_refresh": True},
            headers=auth_headers,
        )
        assert res_msft.status_code == 200
        data_msft = res_msft.json()["data"]
        assert data_msft["status"] == "VERIFIED"
        assert data_msft["confidence"] > 80

        # 2. Test suspicious scam opportunity
        res_scam = await client.post(
            "/api/verification/analyze",
            json={"opportunity_id": "opp-cryptoapex-scam", "force_refresh": True},
            headers=auth_headers,
        )
        assert res_scam.status_code == 200
        data_scam = res_scam.json()["data"]
        assert data_scam["status"] == "SUSPICIOUS"
        assert len(data_scam["risk_factors"]) > 0


@pytest.mark.asyncio
async def test_application_tracking(auth_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        app_data = {
            "profile_id": "profile-alex-morgan",
            "opportunity_id": "opp-msft-aiml",
            "status": "APPLIED",
            "notes": "Submitted official portal application",
        }
        res = await client.post("/api/applications", json=app_data, headers=auth_headers)
        assert res.status_code == 201
        data = res.json()["data"]
        assert data["status"] == "APPLIED"

        app_id = data["id"]
        res_update = await client.patch(
            f"/api/applications/{app_id}",
            json={"status": "INTERVIEW", "notes": "Technical round scheduled"},
            headers=auth_headers,
        )
        assert res_update.status_code == 200
        assert res_update.json()["data"]["status"] == "INTERVIEW"

        res_list = await client.get("/api/applications/profile-alex-morgan", headers=auth_headers)
        assert res_list.status_code == 200
        assert len(res_list.json()["data"]) >= 1

        res_delete = await client.delete(f"/api/applications/{app_id}", headers=auth_headers)
        assert res_delete.status_code == 200
        assert res_delete.json()["success"] is True


@pytest.mark.asyncio
async def test_filter_opportunities(auth_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res_remote = await client.get("/api/opportunities?work_mode=Remote", headers=auth_headers)
        assert res_remote.status_code == 200
        data_remote = res_remote.json()["data"]
        assert all(item["work_mode"].lower() == "remote" for item in data_remote)

        res_verif = await client.get("/api/opportunities?verification_status=VERIFIED", headers=auth_headers)
        assert res_verif.status_code == 200
        data_verif = res_verif.json()["data"]
        assert all(item["verification_status"] == "VERIFIED" for item in data_verif)

        res_search = await client.get("/api/opportunities?search=Microsoft", headers=auth_headers)
        assert res_search.status_code == 200
        assert len(res_search.json()["data"]) >= 1


@pytest.mark.asyncio
async def test_external_url_verification(auth_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        req = {
            "url": "https://t.me/SuspiciousRecruiterBot",
            "company": "Telegram Instant Hires",
            "description": "Earn 5000 daily with 1500 registration deposit fee",
        }
        res = await client.post("/api/verification/analyze", json=req, headers=auth_headers)
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["status"] == "SUSPICIOUS"
        assert len(data["risk_factors"]) > 0


# ==========================================
# Authentication & User Flow Tests
# ==========================================

@pytest.mark.asyncio
async def test_auth_register_and_login():
    test_email = f"user_{uuid.uuid4().hex[:8]}@techwave.ai"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Register a new user
        reg_payload = {
            "email": test_email,
            "password": "StrongPassword123!",
            "full_name": "Test User",
            "role": "student",
        }
        res_reg = await client.post("/api/auth/register", json=reg_payload)
        assert res_reg.status_code == 201
        data_reg = res_reg.json()
        assert data_reg["success"] is True
        auth_data = data_reg["data"]
        assert "access_token" in auth_data
        assert auth_data["token_type"] == "bearer"
        assert auth_data["user"]["email"] == test_email
        assert auth_data["user"]["profile_id"] is not None

        # 2. Duplicate registration should be rejected
        res_dup = await client.post("/api/auth/register", json=reg_payload)
        assert res_dup.status_code == 400

        # 3. Login with wrong password should fail
        res_bad_login = await client.post(
            "/api/auth/login",
            json={"email": test_email, "password": "WrongPassword!"},
        )
        assert res_bad_login.status_code == 401

        # 4. Login with correct password
        res_login = await client.post(
            "/api/auth/login",
            json={"email": test_email, "password": "StrongPassword123!"},
        )
        assert res_login.status_code == 200
        data_login = res_login.json()["data"]
        assert "access_token" in data_login
        assert data_login["user"]["email"] == test_email


@pytest.mark.asyncio
async def test_auth_me_protected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # First login with demo user
        res_login = await client.post(
            "/api/auth/login",
            json={"email": "alex.morgan@pathbridge.ai", "password": "Password123!"},
        )
        assert res_login.status_code == 200
        token = res_login.json()["data"]["access_token"]

        # Call /api/auth/me with valid Bearer token
        res_me = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res_me.status_code == 200
        me_data = res_me.json()["data"]
        assert me_data["email"] == "alex.morgan@pathbridge.ai"
        assert me_data["full_name"] == "Alex Morgan"

        # Calling without token should be blocked by middleware
        res_no_auth = await client.get("/api/auth/me")
        assert res_no_auth.status_code == 401

        # Logout endpoint
        res_logout = await client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res_logout.status_code == 200
        assert res_logout.json()["success"] is True


@pytest.mark.asyncio
async def test_newly_seeded_opportunities(auth_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res_deepmind = await client.get("/api/opportunities/opp-deepmind-quantum", headers=auth_headers)
        assert res_deepmind.status_code == 200
        assert res_deepmind.json()["data"]["company"] == "Google DeepMind"

        res_cohere = await client.get("/api/opportunities/opp-cohere-rag-search", headers=auth_headers)
        assert res_cohere.status_code == 200
        assert res_cohere.json()["data"]["company"] == "Cohere"

        res_figma = await client.get("/api/opportunities/opp-figma-webgl-eng", headers=auth_headers)
        assert res_figma.status_code == 200
        assert res_figma.json()["data"]["company"] == "Figma"

        res_vercel = await client.get("/api/opportunities/opp-vercel-edge-infra", headers=auth_headers)
        assert res_vercel.status_code == 200
        assert res_vercel.json()["data"]["company"] == "Vercel"

        res_all = await client.get("/api/opportunities", headers=auth_headers)
        assert res_all.status_code == 200
        assert len(res_all.json()["data"]) >= 34


@pytest.mark.asyncio
async def test_google_auth_flow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Missing credential -> 400
        res_empty = await client.post("/api/auth/google", json={})
        assert res_empty.status_code == 400

        # 2. New Google user auto-registration & login
        unique_id = uuid.uuid4().hex[:6]
        google_email = f"google.student.{unique_id}@gmail.com"
        res_new_google = await client.post(
            "/api/auth/google",
            json={"credential": f"mock_google_{google_email}", "role": "student"},
        )
        assert res_new_google.status_code == 200
        data = res_new_google.json()
        assert data["success"] is True
        auth_data = data["data"]
        assert "access_token" in auth_data
        assert auth_data["user"]["email"] == google_email
        assert auth_data["user"]["profile_id"] is not None

        # 3. Existing user signing in via Google
        res_existing = await client.post(
            "/api/auth/google",
            json={"credential": "mock_google_alex.morgan@pathbridge.ai"},
        )
        assert res_existing.status_code == 200
        assert res_existing.json()["data"]["user"]["email"] == "alex.morgan@pathbridge.ai"

