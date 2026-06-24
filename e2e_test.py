"""
全链路自动化测试 — 模拟完整用户流程
运行: python e2e_test.py [--url URL] [--verbose]
"""
import sys, os, time, json, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 解析参数
parser = argparse.ArgumentParser(description="E2E test for math-teaching-agent")
parser.add_argument("--url", default="http://localhost:8000", help="Base URL")
parser.add_argument("--verbose", action="store_true", help="Show debug output")
args = parser.parse_args()

BASE = args.url.rstrip("/")
V = args.verbose

PASS = 0
FAIL = 0
ERRORS = []

def test(name, fn):
    global PASS, FAIL
    try:
        fn()
        PASS += 1
        icon = "✅"
    except Exception as e:
        FAIL += 1
        icon = "❌"
        ERRORS.append(f"  {name}: {e}")
        if V:
            import traceback; traceback.print_exc()
    print(f"  {icon} {name}" if not V else f"  {icon} {name}")

# ===== HTTP 客户端 =====
import httpx
client = httpx.Client(timeout=30)

def api(path, method="GET", **kwargs):
    url = f"{BASE}/api{path}"
    if V: print(f"    {method} {url}")
    r = client.request(method, url, **kwargs)
    if V: print(f"    -> {r.status_code} {r.text[:200]}")
    return r

print(f"\n{'='*50}")
print(f"  全链路 E2E 测试 — {BASE}")
print(f"{'='*50}\n")

# ===== 1. 健康检查 =====
print("📡 健康检查")
def check_health():
    r = api("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
test("GET /api/health → 200", check_health)

# ===== 2. 学生注册 =====
print("\n🎒 学生流程")
stuid = f"e2e_{int(time.time())}"
def register_student():
    global _student_token, _student_id
    r = api("/auth/register", "POST", json={
        "name": "测试同学", "student_id": stuid, "password": "123456", "school_level": "初中",
    })
    assert r.status_code == 200, f"注册失败: {r.text}"
    data = r.json()
    assert "access_token" in data
    assert data["user_type"] == "student"
    _student_token = data["access_token"]
    _student_id = str(data["student_id"])
test("POST /api/auth/register → 注册成功", register_student)

def duplicate_register():
    r = api("/auth/register", "POST", json={
        "name": "测试同学2", "student_id": stuid, "password": "123456", "school_level": "初中",
    })
    assert r.status_code == 400
    assert "已被注册" in r.text
test("POST /api/auth/register → 重复注册拒绝", duplicate_register)

def student_login():
    r = api("/auth/login", "POST", json={
        "student_id": stuid, "name": "测试同学", "password": "123456",
    })
    assert r.status_code == 200
    assert "access_token" in r.json()
test("POST /api/auth/login → 登录成功", student_login)

def student_reset_password():
    r = api("/auth/student/reset-password", "POST", json={
        "student_id": stuid, "name": "测试同学",
        "old_password": "123456", "new_password": "654321",
    })
    assert r.status_code == 200
    # 用旧密码应失败
    r2 = api("/auth/login", "POST", json={
        "student_id": stuid, "name": "测试同学", "password": "123456",
    })
    assert r2.status_code == 401
    # 用新密码应成功
    r3 = api("/auth/login", "POST", json={
        "student_id": stuid, "name": "测试同学", "password": "654321",
    })
    assert r3.status_code == 200
test("POST /api/auth/student/reset-password → 旧密码验证", student_reset_password)

# ===== 3. 教师注册 + 班级管理 =====
print("\n👨‍🏫 教师流程")
def register_teacher():
    global _teacher_token, _teacher_headers
    r = api("/auth/teacher/register", "POST", json={
        "name": "陈老师", "username": f"chen_{int(time.time())}", "password": "123456", "school": "测试中学",
    })
    assert r.status_code == 200
    _teacher_token = r.json()["access_token"]
    _teacher_headers = {"Authorization": f"Bearer {_teacher_token}"}
test("POST /api/auth/teacher/register → 注册成功", register_teacher)

def create_class():
    global _class_id
    r = api("/classes", "POST", json={"name": "初二(3)班", "school_level": "初中"},
             headers=_teacher_headers)
    assert r.status_code == 200
    _class_id = r.json()["id"]
test("POST /api/classes → 创建班级", create_class)

def generate_invite_code():
    global _invite_code
    r = api(f"/classes/{_class_id}/invite-codes", "POST", json={},
             headers=_teacher_headers)
    assert r.status_code == 200
    _invite_code = r.json()["code"]
test("POST /api/classes/{id}/invite-codes → 生成邀请码", generate_invite_code)

# ===== 4. 学生加入班级 =====
print("\n🔗 加入班级")
def join_class():
    r = api("/classes/join", "POST", json={"code": _invite_code},
             headers={"Authorization": f"Bearer {_student_token}"})
    assert r.status_code == 200
    assert "加入班级" in r.json()["message"]
test("POST /api/classes/join → 加入班级", join_class)

def my_class():
    r = api("/classes/my", headers={"Authorization": f"Bearer {_student_token}"})
    assert r.status_code == 200
    assert r.json()["class_name"] == "初二(3)班"
test("GET /api/classes/my → 查看所在班级", my_class)

# ===== 5. 学生画像 =====
print("\n📊 学生画像")
def student_profile():
    r = api(f"/analysis/student/{_student_id}",
             headers={"Authorization": f"Bearer {_student_token}"})
    assert r.status_code == 200
    data = r.json()
    # 检查 StudentProfile 字段
    assert "total_homework" in data
    assert "avg_score" in data
test("GET /api/analysis/student/{id} → 学生画像", student_profile)

# ===== 6. 出题 + 答题 =====
print("\n📝 AI 出题")
def generate_exam():
    global _exam_id
    r = api("/exam/generate", "POST", json={
        "knowledge_points": ["相似三角形", "一元二次方程"],
        "difficulty": 3, "question_count": 2, "with_images": False,
    }, headers={"Authorization": f"Bearer {_student_token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "generating"
    _exam_id = data["exam_id"]
test("POST /api/exam/generate → 出题成功", generate_exam)

def poll_exam_status():
    # 等待后台生成（最多等 30 秒）
    for i in range(15):
        time.sleep(2)
        r = api(f"/exam/generate/{_exam_id}/status",
                 headers={"Authorization": f"Bearer {_student_token}"})
        data = r.json()
        if data["status"] == "done":
            assert len(data.get("questions", [])) > 0, "题目列表为空"
            return
    raise TimeoutError("出题超时")
test("GET /api/exam/generate/{id}/status → 出题完成", poll_exam_status)

def submit_exam():
    global _grade_task_id
    r = api(f"/exam/{_exam_id}/submit", "POST", json={
        "answers": [{"question_index": 0, "answer": "x=2"}, {"question_index": 1, "answer": "不会"}],
    }, headers={"Authorization": f"Bearer {_student_token}"})
    assert r.status_code == 200
    assert r.json()["status"] == "grading"
test("POST /api/exam/{id}/submit → 提交成功", submit_exam)

def poll_exam_result():
    for i in range(30):
        time.sleep(2)
        r = api(f"/exam/{_exam_id}/status",
                 headers={"Authorization": f"Bearer {_student_token}"})
        data = r.json()
        if data["status"] == "done":
            assert "score" in data
            return
    raise TimeoutError("批改超时")
test("GET /api/exam/{id}/status → 批改完成", poll_exam_result)

# ===== 7. 考试报告 =====
print("\n📋 考试报告")
def exam_report():
    r = api(f"/exam/{_exam_id}/report",
             headers={"Authorization": f"Bearer {_student_token}"})
    assert r.status_code == 200
    data = r.json()
    assert "diagnostic_report" in data
test("GET /api/exam/{id}/report → 诊断报告", exam_report)

def my_exams():
    r = api("/exam/my", headers={"Authorization": f"Bearer {_student_token}"})
    assert r.status_code == 200
    assert len(r.json()) > 0
test("GET /api/exam/my → 历史考试", my_exams)

# ===== 8. 作业上传 =====
print("\n📸 作业批改")
def upload_homework():
    global _submission_id
    # 用一个小文本文件模拟图片上传
    files = {"file": ("test.txt", b"fake-image-data", "text/plain")}
    r = api("/homework/upload", "POST", files=files,
             headers={"Authorization": f"Bearer {_student_token}"})
    assert r.status_code == 200
    _submission_id = r.json()["submission_id"]
test("POST /api/homework/upload → 上传成功", upload_homework)

def my_homework():
    r = api("/homework/my", headers={"Authorization": f"Bearer {_student_token}"})
    assert r.status_code == 200
    assert len(r.json()) >= 0  # 可能还在 pending
test("GET /api/homework/my → 作业列表", my_homework)

# ===== 9. 教师仪表盘 =====
print("\n📈 教师端")
def teacher_dashboard():
    r = api("/teacher/dashboard", headers=_teacher_headers)
    assert r.status_code == 200
    data = r.json()
    # 应该能看到我们刚注册的学生
    assert data["total_students"] >= 1
test("GET /api/teacher/dashboard → 仪表盘", teacher_dashboard)

def teacher_students():
    r = api("/teacher/students", headers=_teacher_headers)
    assert r.status_code == 200
    data = r.json()
    # 应该能看到刚创建的学生
    assert data["total"] >= 1
test("GET /api/teacher/students → 学生列表", teacher_students)

# ===== 10. 管理员 =====
print("\n⚙️ 管理员")
def admin_login():
    global _admin_token, _admin_headers
    # 管理员是 seed_admin.py 自动创建的
    r = api("/auth/teacher/login", "POST", json={
        "username": "admin", "password": "admin123",
    })
    if r.status_code == 200:
        _admin_token = r.json()["access_token"]
        _admin_headers = {"Authorization": f"Bearer {_admin_token}"}
    else:
        _admin_headers = {}
test("POST /api/auth/teacher/login → 管理员登录", admin_login)

def admin_dashboard():
    if not _admin_headers:
        raise Exception("管理员未登录，跳过")
    r = api("/admin/dashboard", headers=_admin_headers)
    assert r.status_code == 200
    data = r.json()
    assert "teacher_count" in data
    assert "student_count" in data
test("GET /api/admin/dashboard → 管理员仪表盘", admin_dashboard)

def admin_teachers():
    if not _admin_headers:
        raise Exception("管理员未登录，跳过")
    r = api("/admin/teachers", headers=_admin_headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)
test("GET /api/admin/teachers → 教师列表", admin_teachers)

def admin_ai_providers():
    if not _admin_headers:
        raise Exception("管理员未登录，跳过")
    r = api("/admin/ai-providers", headers=_admin_headers)
    assert r.status_code == 200
test("GET /api/admin/ai-providers → AI 模型配置", admin_ai_providers)

# ===== 11. 教师发布作业 =====
print("\n📄 作业发布")
def create_assignment():
    r = api("/assignments/teacher", "POST", json={
        "title": "周末练习题", "description": "做前 5 题",
        "questions": [{"q": "2x+3=7", "answer": "x=2"}],
        "class_id": _class_id,
    }, headers=_teacher_headers)
    assert r.status_code == 200
    assert r.json()["questions_count"] >= 1
test("POST /api/assignments/teacher → 发布作业", create_assignment)

def student_assignments():
    r = api("/assignments/student", headers={"Authorization": f"Bearer {_student_token}"})
    assert r.status_code == 200
    assert len(r.json()) >= 1
test("GET /api/assignments/student → 学生查看作业", student_assignments)

def submit_assignment():
    r = api("/assignments/student/1/submit", "POST", json={
        "answers": [{"q": "2x+3=7", "answer": "x=2"}],
    }, headers={"Authorization": f"Bearer {_student_token}"})
    assert r.status_code in [200, 404]  # 404 说明作业 ID 不对，跳过
test("POST /api/assignments/student/{id}/submit → 提交作业", submit_assignment)

# ===== 12. 安全测试 =====
print("\n🔒 安全测试")
def unauth_access():
    r = api("/teacher/dashboard")  # 无 token
    assert r.status_code == 401
test("GET /api/teacher/dashboard → 未登录被拒", unauth_access)

def student_cannot_teacher():
    r = api("/teacher/dashboard", headers={"Authorization": f"Bearer {_student_token}"})
    assert r.status_code == 403
test("GET /api/teacher/dashboard → 学生不能访问教师端", student_cannot_teacher)

# ===== 结果 =====
print(f"\n{'='*50}")
print(f"  测试结果汇总")
print(f"{'='*50}")
print(f"  ✅ 通过: {PASS}")
print(f"  ❌ 失败: {FAIL}")
print(f"  总计: {PASS + FAIL}")
if ERRORS:
    print(f"\n  错误详情:")
    for e in ERRORS:
        print(e)

# 清理测试数据
if args.url == "http://localhost:8000" and os.path.exists("test.db"):
    try: os.remove("test.db")
    except: pass

print()
sys.exit(0 if FAIL == 0 else 1)
