
"""
全功能集成测试 — pytest
运行: cd backend && python -m pytest test_comprehensive.py -v
"""
import sys, os as os_mod
sys.path.insert(0, os_mod.path.dirname(os_mod.path.abspath(__file__)))
import pytest
from fastapi.testclient import TestClient
from config import settings
settings.DATABASE_URL = "sqlite:///./test_comp.db"
from database import init_db, SessionLocal, engine
from models import Base, Student, Teacher, Class, ClassStudent, HomeworkSubmission, ExamAttempt, ErrorRecord
from main import app
client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.drop_all(bind=engine)
    init_db()
    yield
    try: os_mod.remove("test_comp.db")
    except: pass


class TestPerm:
    def test_register_login(self):
        r = client.post("/api/auth/register", json={"name": "s1","student_id":"S1","password":"123456","school_level":"初中"})
        assert r.status_code == 200 and r.json()["user_type"] == "student"
        r = client.post("/api/auth/register", json={"name":"s2","student_id":"S1","password":"123456","school_level":"初中"})
        assert r.status_code == 400
        r = client.post("/api/auth/teacher/register", json={"name":"张老师","username":"zh1","password":"123456","school":"一中"})
        assert r.status_code == 200
        r = client.post("/api/auth/teacher/login", json={"username":"zh1","password":"wrong"})
        assert r.status_code == 401

    def test_permission(self):
        r = client.post("/api/auth/register", json={"name":"x","student_id":"X1","password":"123456","school_level":"初中"})
        t = r.json()["access_token"]
        assert client.get("/api/teacher/dashboard", headers={"Authorization":f"Bearer {t}"}).status_code == 403
        assert client.get("/api/teacher/errors", headers={"Authorization":f"Bearer {t}"}).status_code == 403
        r = client.post("/api/auth/teacher/register", json={"name":"t","username":"tx","password":"123456","school":"s"})
        t = r.json()["access_token"]
        assert client.get("/api/classes/my", headers={"Authorization":f"Bearer {t}"}).status_code == 403

    def test_unauth(self):
        assert client.get("/api/teacher/dashboard").status_code == 401
        assert client.get("/api/classes/my").status_code == 401


class TestClass:
    def _t(self):
        return client.post("/api/auth/teacher/register", json={"name":"t","username":"t1","password":"123456","school":"s"}).json()["access_token"]
    def _s(self, sid="S1"):
        return client.post("/api/auth/register", json={"name":"s","student_id":sid,"password":"123456","school_level":"初中"}).json()["access_token"]

    def test_crud(self):
        t = self._t()
        r = client.post("/api/classes", json={"name":"C1","school_level":"初中"}, headers={"Authorization":f"Bearer {t}"})
        assert r.status_code == 200
        cid = r.json()["id"]
        assert len(client.get("/api/classes", headers={"Authorization":f"Bearer {t}"}).json()) == 1
        assert client.delete(f"/api/classes/{cid}", headers={"Authorization":f"Bearer {t}"}).status_code == 200
        assert client.get(f"/api/classes/{cid}", headers={"Authorization":f"Bearer {t}"}).status_code == 404

    def test_join(self):
        t = self._t()
        r = client.post("/api/classes", json={"name":"C1","school_level":"初中"}, headers={"Authorization":f"Bearer {t}"})
        cid = r.json()["id"]
        r = client.post(f"/api/classes/{cid}/invite-codes", json={}, headers={"Authorization":f"Bearer {t}"})
        code = r.json()["code"]
        assert len(code) == 8
        s = self._s()
        r = client.post("/api/classes/join", json={"code":code}, headers={"Authorization":f"Bearer {s}"})
        assert "加入班级" in r.json()["message"]
        assert client.get("/api/classes/my", headers={"Authorization":f"Bearer {s}"}).json()["class_name"] == "C1"
        r2 = client.post("/api/classes/join", json={"code":code}, headers={"Authorization":f"Bearer {s}"})
        assert r2.status_code == 400
        assert client.post("/api/classes/join", json={"code":"BAD"}, headers={"Authorization":f"Bearer {self._s('X1')}"}).status_code == 404


class TestHw:
    def test_upload(self):
        client.post("/api/auth/teacher/register", json={"name":"t","username":"t2","password":"123456","school":"s"})
        r = client.post("/api/auth/register", json={"name":"s1","student_id":"S1","password":"123456","school_level":"初中"})
        t = r.json()["access_token"]
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"data"); tmp = f.name
        try:
            with open(tmp, "rb") as f:
                r = client.post("/api/homework/upload", files={"file":("t.jpg",f,"image/jpeg")}, data={"student_answers":"x=2"}, headers={"Authorization":f"Bearer {t}"})
        finally: os_mod.unlink(tmp)
        assert r.status_code == 200
        d = r.json()
        assert "task_id" in d and "submission_id" in d
        assert client.get(f"/api/homework/upload/{d['submission_id']}/status", headers={"Authorization":f"Bearer {t}"}).status_code == 200
        assert len(client.get("/api/homework/my", headers={"Authorization":f"Bearer {t}"}).json()) >= 1


class TestExam:
    def test_generate(self):
        r = client.post("/api/auth/register", json={"name":"s1","student_id":"S1","password":"123456","school_level":"初中"})
        t = r.json()["access_token"]
        r = client.post("/api/exam/generate", json={"knowledge_points":[],"difficulty":3,"question_count":5}, headers={"Authorization":f"Bearer {t}"})
        assert r.status_code == 200 and "exam_id" in r.json()
        assert isinstance(client.get("/api/exam/my", headers={"Authorization":f"Bearer {t}"}).json(), list)
        assert client.get("/api/exam/99999/status", headers={"Authorization":f"Bearer {t}"}).status_code == 404


class TestTeacher:
    def _setup(self):
        r = client.post("/api/auth/teacher/register", json={"name":"t","username":"tx","password":"123456","school":"s"})
        tt = r.json()["access_token"]
        r = client.post("/api/classes", json={"name":"C1","school_level":"初中"}, headers={"Authorization":f"Bearer {tt}"})
        cid = r.json()["id"]
        r = client.post(f"/api/classes/{cid}/invite-codes", json={}, headers={"Authorization":f"Bearer {tt}"})
        code = r.json()["code"]
        st = client.post("/api/auth/register", json={"name":"s","student_id":"S1","password":"123456","school_level":"初中","invite_code":code}).json()["access_token"]
        return tt, st

    def test_dashboard_empty(self):
        r = client.post("/api/auth/teacher/register", json={"name":"t2","username":"ty","password":"123456","school":"s"})
        t = r.json()["access_token"]
        assert client.get("/api/teacher/dashboard", headers={"Authorization":f"Bearer {t}"}).json()["total_students"] == 0

    def test_dashboard_data(self):
        tt, st = self._setup()
        assert client.get("/api/teacher/dashboard", headers={"Authorization":f"Bearer {tt}"}).status_code == 200

    def test_students(self):
        tt, st = self._setup()
        assert "students" in client.get("/api/teacher/students", headers={"Authorization":f"Bearer {tt}"}).json()

    def test_errors(self):
        tt, st = self._setup()
        assert isinstance(client.get("/api/teacher/errors", headers={"Authorization":f"Bearer {tt}"}).json(), list)


class TestHealth:
    def test_health(self):
        assert client.get("/api/health").json()["status"] == "ok"
