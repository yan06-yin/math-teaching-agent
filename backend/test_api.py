"""
基础接口测试 — pytest
运行: cd backend && python -m pytest test_api.py -v
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest
from fastapi.testclient import TestClient
from config import settings

# 测试用数据库（内存 SQLite）
settings.DATABASE_URL = "sqlite:///./test.db"

from database import init_db, SessionLocal, engine
from models import Base, Student, Class, ClassStudent, InviteCode
from main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    """每个测试前重建表"""
    Base.metadata.drop_all(bind=engine)
    init_db()
    yield
    # 清理测试数据库
    try:
        os.remove("test.db")
    except:
        pass


class TestAuth:
    """认证接口测试"""

    def test_student_register(self):
        resp = client.post("/api/auth/register", json={
            "name": "测试学生",
            "student_id": "2024001",
            "password": "123456",
            "school_level": "初中",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["user_type"] == "student"

    def test_student_duplicate_register(self):
        client.post("/api/auth/register", json={
            "name": "测试学生", "student_id": "2024001",
            "password": "123456", "school_level": "初中",
        })
        resp = client.post("/api/auth/register", json={
            "name": "测试学生2", "student_id": "2024001",
            "password": "123456", "school_level": "初中",
        })
        assert resp.status_code == 400
        assert "已被注册" in resp.json()["detail"]

    def test_student_login(self):
        client.post("/api/auth/register", json={
            "name": "测试学生", "student_id": "2024001",
            "password": "123456", "school_level": "初中",
        })
        resp = client.post("/api/auth/login", json={
            "name": "测试学生", "student_id": "2024001", "password": "123456",
        })
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    def test_teacher_register_and_login(self):
        # 注册
        r = client.post("/api/auth/teacher/register", json={
            "name": "张老师", "username": "zhang", "password": "123456", "school": "一中",
        })
        assert r.status_code == 200
        token = r.json()["access_token"]

        # 登录
        r = client.post("/api/auth/teacher/login", json={
            "username": "zhang", "password": "123456",
        })
        assert r.status_code == 200

        # 使用 token 访问教师接口
        r = client.get("/api/teacher/dashboard", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200

    # ===== 密码重置测试 =====

    def test_student_reset_password(self):
        """学生重置密码：先注册，再重置"""
        client.post("/api/auth/register", json={
            "name": "测试学生", "student_id": "2024001", "password": "123456", "school_level": "初中",
        })
        resp = client.post("/api/auth/student/reset-password", json={
            "student_id": "2024001", "name": "测试学生",
            "old_password": "123456", "new_password": "654321",
        })
        assert resp.status_code == 200

        # 用旧密码登录应失败
        login_old = client.post("/api/auth/login", json={
            "student_id": "2024001", "name": "测试学生", "password": "123456",
        })
        assert login_old.status_code == 401

        # 用新密码登录应成功
        login_new = client.post("/api/auth/login", json={
            "student_id": "2024001", "name": "测试学生", "password": "654321",
        })
        assert login_new.status_code == 200

    def test_student_reset_password_wrong_old(self):
        """学生密码重置：旧密码错误应拒绝"""
        client.post("/api/auth/register", json={
            "name": "测试学生", "student_id": "2024001", "password": "123456", "school_level": "初中",
        })
        resp = client.post("/api/auth/student/reset-password", json={
            "student_id": "2024001", "name": "测试学生",
            "old_password": "wrong", "new_password": "654321",
        })
        assert resp.status_code == 401

    def test_teacher_reset_password(self):
        """教师重置密码：先注册，再重置"""
        client.post("/api/auth/teacher/register", json={
            "name": "张老师", "username": "zhang", "password": "123456", "school": "一中",
        })
        resp = client.post("/api/auth/teacher/reset-password", json={
            "username": "zhang", "old_password": "123456", "new_password": "654321",
        })
        assert resp.status_code == 200


class TestClass:
    """班级接口测试"""

    def _get_teacher_token(self):
        r = client.post("/api/auth/teacher/register", json={
            "name": "张老师", "username": "zhang", "password": "123456", "school": "一中",
        })
        return r.json()["access_token"]

    def _get_student_token(self):
        r = client.post("/api/auth/register", json={
            "name": "测试学生", "student_id": "2024001",
            "password": "123456", "school_level": "初中",
        })
        return r.json()["access_token"]

    def test_create_class(self):
        token = self._get_teacher_token()
        r = client.post("/api/classes", json={
            "name": "初二(3)班", "school_level": "初中",
        }, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["name"] == "初二(3)班"

    def test_list_classes(self):
        token = self._get_teacher_token()
        client.post("/api/classes", json={"name": "初二(3)班", "school_level": "初中"},
                     headers={"Authorization": f"Bearer {token}"})
        r = client.get("/api/classes", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert len(r.json()) == 1

    def test_generate_invite_code(self):
        token = self._get_teacher_token()
        r = client.post("/api/classes", json={"name": "初二(3)班", "school_level": "初中"},
                         headers={"Authorization": f"Bearer {token}"})
        class_id = r.json()["id"]

        r = client.post(f"/api/classes/{class_id}/invite-codes", json={},
                         headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert len(r.json()["code"]) == 8

    def test_join_class_via_invite(self):
        teacher_token = self._get_teacher_token()
        r = client.post("/api/classes", json={"name": "初二(3)班", "school_level": "初中"},
                         headers={"Authorization": f"Bearer {teacher_token}"})
        class_id = r.json()["id"]

        r = client.post(f"/api/classes/{class_id}/invite-codes", json={},
                         headers={"Authorization": f"Bearer {teacher_token}"})
        code = r.json()["code"]

        student_token = self._get_student_token()
        r = client.post("/api/classes/join", json={"code": code},
                         headers={"Authorization": f"Bearer {student_token}"})
        assert r.status_code == 200
        assert "加入班级" in r.json()["message"]

    def test_my_class(self):
        teacher_token = self._get_teacher_token()
        r = client.post("/api/classes", json={"name": "初二(3)班", "school_level": "初中"},
                         headers={"Authorization": f"Bearer {teacher_token}"})
        class_id = r.json()["id"]
        r = client.post(f"/api/classes/{class_id}/invite-codes", json={},
                         headers={"Authorization": f"Bearer {teacher_token}"})
        code = r.json()["code"]

        student_token = self._get_student_token()
        client.post("/api/classes/join", json={"code": code},
                     headers={"Authorization": f"Bearer {student_token}"})

        r = client.get("/api/classes/my", headers={"Authorization": f"Bearer {student_token}"})
        assert r.status_code == 200
        assert r.json()["class_name"] == "初二(3)班"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
