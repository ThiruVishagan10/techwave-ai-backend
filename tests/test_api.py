import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.db.database import init_db, AsyncSessionLocal
from app.services.opportunity_service import opportunity_service
from app.services.profile_service import profile_service


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_db():
    await init_db()
    async with AsyncSessionLocal() as session:
        await opportunity_service.seed_from_file(session, "seed/opportunities.json")
        await profile_service.seed_default_profile(session, "seed/default_profile.json")


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
async def test_list_opportunities():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/opportunities")
        assert response.status_code == 200
        json_data = response.json()
        assert json_data["success"] is True
        assert isinstance(json_data["data"], list)
        assert len(json_data["data"]) > 0


@pytest.mark.asyncio
async def test_get_opportunity_by_id():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/opportunities/opp-msft-aiml")
        assert response.status_code == 200
        json_data = response.json()
        assert json_data["success"] is True
        assert json_data["data"]["company"] == "Microsoft"
        assert json_data["data"]["title"] == "AI/ML Intern"


@pytest.mark.asyncio
async def test_profile_analyze():
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
        )
        assert response.status_code == 200
        json_data = response.json()
        assert json_data["success"] is True
        assert json_data["data"]["name"] is not None
        assert "Python" in json_data["data"]["skills"]


@pytest.mark.asyncio
async def test_matching_engine():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # First ensure we have profile-alex-morgan
        profile_res = await client.get("/api/profiles/profile-alex-morgan")
        if profile_res.status_code != 200:
            # Seed Alex
            seed_profile = {
                "name": "Alex Morgan",
                "skills": ["Python", "SQL", "Machine Learning", "PyTorch", "FastAPI"],
                "career_interests": ["AI/ML"],
                "preferred_locations": ["Hyderabad"],
                "preferred_work_modes": ["Hybrid"],
                "preferred_opportunity_types": ["Internship"],
            }
            create_res = await client.post("/api/profiles", json=seed_profile)
            profile_id = create_res.json()["data"]["id"]
        else:
            profile_id = "profile-alex-morgan"

        match_req = {
            "profile_id": profile_id,
            "opportunity_id": "opp-msft-aiml",
            "force_refresh": True,
        }
        res = await client.post("/api/recommendations/match", json=match_req)
        assert res.status_code == 200
        json_data = res.json()
        assert json_data["success"] is True
        match_data = json_data["data"]
        assert match_data["match_score"] > 60
        assert "Python" in match_data["matched_skills"]
        assert len(match_data["explanation"]) > 10


@pytest.mark.asyncio
async def test_recommendations_ranking():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/recommendations/profile-alex-morgan")
        assert res.status_code == 200
        json_data = res.json()
        assert json_data["success"] is True
        assert isinstance(json_data["data"], list)
        assert len(json_data["data"]) > 0


@pytest.mark.asyncio
async def test_verification_engine():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Test verified opportunity
        res_msft = await client.post(
            "/api/verification/analyze",
            json={"opportunity_id": "opp-msft-aiml", "force_refresh": True},
        )
        assert res_msft.status_code == 200
        data_msft = res_msft.json()["data"]
        assert data_msft["status"] == "VERIFIED"
        assert data_msft["confidence"] > 80

        # 2. Test suspicious scam opportunity
        res_scam = await client.post(
            "/api/verification/analyze",
            json={"opportunity_id": "opp-cryptoapex-scam", "force_refresh": True},
        )
        assert res_scam.status_code == 200
        data_scam = res_scam.json()["data"]
        assert data_scam["status"] == "SUSPICIOUS"
        assert len(data_scam["risk_factors"]) > 0


@pytest.mark.asyncio
async def test_application_tracking():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        app_data = {
            "profile_id": "profile-alex-morgan",
            "opportunity_id": "opp-msft-aiml",
            "status": "APPLIED",
            "notes": "Submitted official portal application",
        }
        res = await client.post("/api/applications", json=app_data)
        assert res.status_code == 201
        data = res.json()["data"]
        assert data["status"] == "APPLIED"

        app_id = data["id"]
        # Update stage to INTERVIEW
        res_update = await client.patch(
            f"/api/applications/{app_id}",
            json={"status": "INTERVIEW", "notes": "Technical round scheduled"},
        )
        assert res_update.status_code == 200
        assert res_update.json()["data"]["status"] == "INTERVIEW"

        # List applications
        res_list = await client.get("/api/applications/profile-alex-morgan")
        assert res_list.status_code == 200
        assert len(res_list.json()["data"]) >= 1

        # Delete application
        res_delete = await client.delete(f"/api/applications/{app_id}")
        assert res_delete.status_code == 200
        assert res_delete.json()["success"] is True


@pytest.mark.asyncio
async def test_filter_opportunities():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Filter remote
        res_remote = await client.get("/api/opportunities?work_mode=Remote")
        assert res_remote.status_code == 200
        data_remote = res_remote.json()["data"]
        assert all(item["work_mode"].lower() == "remote" for item in data_remote)

        # Filter verified
        res_verif = await client.get("/api/opportunities?verification_status=VERIFIED")
        assert res_verif.status_code == 200
        data_verif = res_verif.json()["data"]
        assert all(item["verification_status"] == "VERIFIED" for item in data_verif)

        # Search keyword
        res_search = await client.get("/api/opportunities?search=Microsoft")
        assert res_search.status_code == 200
        assert len(res_search.json()["data"]) >= 1


@pytest.mark.asyncio
async def test_external_url_verification():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        req = {
            "url": "https://t.me/SuspiciousRecruiterBot",
            "company": "Telegram Instant Hires",
            "description": "Earn 5000 daily with 1500 registration deposit fee",
        }
        res = await client.post("/api/verification/analyze", json=req)
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["status"] == "SUSPICIOUS"
        assert len(data["risk_factors"]) > 0
