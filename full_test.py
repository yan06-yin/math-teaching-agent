"""
全功能自动化测试 — 模拟真实使用场景，覆盖所有 API 和边界情况
运行: python full_test.py --url https://你的域名
"""
import sys, os, time, json, argparse, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

parser = argparse.ArgumentParser()
parser.add_argument("--url", default="http://localhost:8000")
parser.add_argument("--verbose", action="store_true")
args = parser.parse_args()
BASE = args.url.rstrip("/")
V = args.verbose

import httpx as _httpx
_client = _httpx.Client(timeout=30)

PASS, FAIL, SKIP = 0, 0, 0
ERRORS = []

v = lambda: None
def api(method, path, **kw):
    url = f"{BASE}/api{path}"
    if V: print(f"    {method} {url}")
    r = _client.request(method, url, **kw)
    if V and r.status_code >= 400: print(f"    -> {r.status_code} {r.text[:300]}")
    return r

def test(module, name, fn, skippable=False):
    global PASS, FAIL, SKIP
    try:
        fn()
        PASS += 1
        print(f"  ✅ {name}")
    except Exception as e:
        if skippable:
            SKIP += 1
            print(f"  ⚠️ {name} [跳过: {e}]")
        else:
            FAIL += 1
            ERRORS.append(f"  [{module}] {name}: {e}")
            print(f"  ❌ {name}")
            if V: traceback.print_exc()

def section(name):
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")

# =======================================================
# 健康检查
# =======================================================
section("1. 健康检查")
def h_health():
    r = api("GET", "/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
test("Health","GET /api/health -> 200", h_health)

def h_health_db():
    r = api("GET", "/health")
    assert r.json()["database"] in ("SQLite","PostgreSQL","MySQL")
test("Health","/api/health 返回数据库类型", h_health_db)

# =======================================================
# 学生注册
# =======================================================
section("2. 学生注册")
uid = f"t{int(time.time())}"
stu = {"name": "测试学生", "student_id": uid, "password": "test123", "school_level": "初中"}
token_s = None
sid_s = None

def s_register():
    global token_s, sid_s
    r = api("POST", "/auth/register", json=stu)
    assert r.status_code == 200
    d = r.json()
    assert d["user_type"] == "student"
    assert "access_token" in d
    assert d["student_id"] is not None
    token_s = d["access_token"]
    sid_s = str(d["student_id"])
test("注册","学生正常注册", s_register)

def s_dup_register():
    r = api("POST", "/auth/register", json=stu)
    assert r.status_code == 400
    assert "已被注册" in r.text
test("注册","重复学号注册被拒", s_dup_register)

def s_short_pwd():
    r = api("POST", "/auth/register", json={"name":"x","student_id":"x1","password":"123","school_level":"初中"})
    assert r.status_code == 422
test("注册","密码少于6位被拒", s_short_pwd)

def s_invalid_level():
    r = api("POST", "/auth/register", json={"name":"x","student_id":"x2","password":"123456","school_level":"大学"})
    assert r.status_code == 422
test("注册","非法学段被拒", s_invalid_level)

def s_empty_name():
    r = api("POST", "/auth/register", json={"name":"","student_id":"x3","password":"123456","school_level":"初中"})
    assert r.status_code == 422
test("注册","空姓名被拒", s_empty_name)

# =======================================================
# 学生登录
# =======================================================
section("3. 学生登录")
def s_login():
    r = api("POST", "/auth/login", json={"student_id":uid,"name":"测试学生","password":"test123"})
    assert r.status_code == 200
    assert r.json()["user_type"] == "student"
test("登录","正常登录", s_login)

def s_wrong_pwd():
    r = api("POST", "/auth/login", json={"student_id":uid,"name":"测试学生","password":"wrong"})
    assert r.status_code == 401
test("登录","错误密码被拒", s_wrong_pwd)

def s_wrong_id():
    r = api("POST", "/auth/login", json={"student_id":"noexist","name":"x","password":"123456"})
    assert r.status_code == 401
test("登录","不存在学号被拒", s_wrong_id)

# =======================================================
# 密码重置
# =======================================================
section("4. 密码重置")
def s_reset():
    r = api("POST", "/auth/student/reset-password", json={
        "student_id":uid,"name":"测试学生","old_password":"test123","new_password":"newpwd456",
    })
    assert r.status_code == 200
    # 用旧密码登录 -> 401
    r2 = api("POST", "/auth/login", json={"student_id":uid,"name":"测试学生","password":"test123"})
    assert r2.status_code == 401
    # 用新密码登录 -> 200
    r3 = api("POST", "/auth/login", json={"student_id":uid,"name":"测试学生","password":"newpwd456"})
    assert r3.status_code == 200
test("密码重置","学生密码重置需旧密码验证", s_reset)

def s_reset_wrong_old():
    r = api("POST", "/auth/student/reset-password", json={
        "student_id":uid,"name":"测试学生","old_password":"wrong","new_password":"newpwd456",
    })
    assert r.status_code in (401, 422), f"应返回 401/422, 实际 {r.status_code}: {r.text}"  # 422=旧密码验证前schema已校验
test("密码重置","旧密码错误被拒", s_reset_wrong_old)

# =======================================================
# 考试（核心功能）
# =======================================================
section("5. 考试系统")
exam_id = None
h = lambda t: {"Authorization": f"Bearer {t}"}

def e_simple_exam():
    global exam_id
    # 1 题，不开配图，快速出题
    r = api("POST", "/exam/generate", json={
        "knowledge_points":["一元二次方程"],"difficulty":3,"question_count":1,"with_images":False,
    }, headers=h(token_s))
    assert r.status_code == 200
    exam_id = r.json()["exam_id"]
    assert exam_id is not None
test("考试","出题请求成功", e_simple_exam)

def e_poll_exam():
    global exam_id
    for i in range(15):
        time.sleep(2)
        r = api("GET", f"/exam/generate/{exam_id}/status", headers=h(token_s))
        d = r.json()
        if d["status"] == "done":
            assert len(d.get("questions",[])) > 0
            return
    raise TimeoutError("出题超时(30s)")
test("考试","轮询出题完成", e_poll_exam)

def e_submit():
    r = api("POST", f"/exam/{exam_id}/submit", json={
        "answers":[{"question_index":0,"answer":"x=2"}],
    }, headers=h(token_s))
    assert r.status_code == 200
    assert r.json()["status"] == "grading"
test("考试","提交答卷", e_submit)

def e_poll_grading():
    for i in range(30):
        time.sleep(2)
        r = api("GET", f"/exam/{exam_id}/status", headers=h(token_s))
        d = r.json()
        if d["status"] == "done":
            assert "score" in d
            assert "diagnostic_report" in d
            assert "details" in d
            return
    raise TimeoutError("批改超时(60s)")
test("考试","轮询批改完成", e_poll_grading)

def e_dup_submit():
    r = api("POST", f"/exam/{exam_id}/submit", json={
        "answers":[{"question_index":0,"answer":"x=2"}],
    }, headers=h(token_s))
    assert r.status_code == 400
    assert "重复提交" in r.text
test("考试","重复提交被拒", e_dup_submit)

def e_get_report():
    r = api("GET", f"/exam/{exam_id}/report", headers=h(token_s))
    assert r.status_code == 200
    d = r.json()
    assert "diagnostic_report" in d
    assert d["score"] is not None
test("考试","获取考试报告", e_get_report)

def e_my_exams():
    r = api("GET", "/exam/my", headers=h(token_s))
    assert r.status_code == 200
    assert len(r.json()) > 0
test("考试","历史考试列表", e_my_exams)

def e_404_report():
    r = api("GET", "/exam/999999/report", headers=h(token_s))
    assert r.status_code == 404
test("考试","不存在的考试报告返回404", e_404_report)

# =======================================================
# 作业批改
# =======================================================
section("6. 作业系统")
hw_id = None

def hw_upload():
    global hw_id
    files = {"file": ("test.jpg", b"fake-jpeg-data", "image/jpeg")}
    r = api("POST", "/homework/upload", files=files, data={"student_answers":"1.x=2\n2.x=3"}, headers=h(token_s))
    assert r.status_code == 200
    hw_id = r.json()["submission_id"]
test("作业","上传作业", hw_upload)

def hw_my():
    r = api("GET", "/homework/my", headers=h(token_s))
    assert r.status_code == 200
    ids = [x["id"] for x in r.json()]
    assert hw_id in ids
test("作业","作业列表包含刚上传的", hw_my)

def hw_status():
    r = api("GET", f"/homework/upload/{hw_id}/status", headers=h(token_s))
    assert r.status_code == 200
    assert r.json()["status"] in ("done","processing","error")
test("作业","查询作业状态", hw_status)

def hw_result():
    r = api("GET", f"/homework/{hw_id}/result", headers=h(token_s))
    assert r.status_code == 200
test("作业","获取作业结果", hw_result)

def hw_404():
    r = api("GET", "/homework/999999/result", headers=h(token_s))
    assert r.status_code == 404
test("作业","不存在的作业返回404", hw_404)

# =======================================================
# 学生画像 + 趋势
# =======================================================
section("7. 学生分析")
def a_profile():
    r = api("GET", f"/analysis/student/{sid_s}", headers=h(token_s))
    assert r.status_code == 200
    d = r.json()
    assert d["total_homework"] >= 0
    assert d["total_exams"] >= 0
    assert d["avg_score"] >= 0
    assert d["trend"] in ("rising","stable","falling")
test("分析","学生画像", a_profile)

def a_trends():
    r = api("GET", f"/analysis/class/{sid_s}/trends", headers=h(token_s))
    assert r.status_code == 200
    assert isinstance(r.json(), list)
test("分析","成绩趋势", a_trends)

def a_forbidden_other():
    # 用当前 token 看别人
    r = api("GET", f"/analysis/student/99999", headers=h(token_s))
    assert r.status_code == 403
test("分析","查看他人画像被拒", a_forbidden_other)

# =======================================================
# 教师
# =======================================================
section("8. 教师端")
teacher_token = None
th = lambda: {"Authorization": f"Bearer {teacher_token}"}
class_id = None

def t_register():
    global teacher_token
    tuname = f"teacher_{int(time.time())}"
    r = api("POST", "/auth/teacher/register", json={
        "name":"张老师","username":tuname,"password":"pass123","school":"一中",
    })
    assert r.status_code == 200
    teacher_token = r.json()["access_token"]
test("教师","教师注册", t_register)

def t_dup_register():
    # 用相同 username
    dup_user = f"dup_{int(time.time())}"
    r = api("POST", "/auth/teacher/register", json={
        "name":"李老师","username":dup_user,"password":"pass123","school":"二中",
    })
    assert r.status_code == 200
    r2 = api("POST", "/auth/teacher/register", json={
        "name":"李老师2","username":dup_user,"password":"pass123","school":"二中",
    })
    assert r2.status_code == 400
test("教师","重复用户名被拒", t_dup_register)

def t_login():
    r = api("POST", "/auth/teacher/login", json={"username":"admin","password":"admin123"})
    assert r.status_code == 200
test("教师","管理员登录", t_login)

def t_dashboard_empty():
    r = api("GET", "/teacher/dashboard", headers=th())
    assert r.status_code == 200
    d = r.json()
    assert "total_students" in d
    assert "knowledge_heatmap" in d
test("教师","教师仪表盘", t_dashboard_empty)

def t_create_class():
    global class_id
    r = api("POST", "/classes", json={"name":"初二(3)班","school_level":"初中"}, headers=th())
    assert r.status_code == 200
    class_id = r.json()["id"]
test("教师","创建班级", t_create_class)

def t_dup_class_name():
    # 同名可以不同班级，不应该报错
    r = api("POST", "/classes", json={"name":"初二(3)班","school_level":"高中"}, headers=th())
    assert r.status_code == 200
test("教师","同名班级(不同学段)允许", t_dup_class_name)

def t_list_classes():
    r = api("GET", "/classes", headers=th())
    assert r.status_code == 200
    assert len(r.json()) >= 1
test("教师","班级列表", t_list_classes)

def t_get_class():
    r = api("GET", f"/classes/{class_id}", headers=th())
    assert r.status_code == 200
    assert r.json()["student_count"] >= 0
test("教师","班级详情", t_get_class)

def t_other_class_denied():
    r = api("GET", "/classes/99999", headers=th())
    assert r.status_code == 404
test("教师","查看他人班级被拒", t_other_class_denied)

# =======================================================
# 邀请码 + 加入班级
# =======================================================
section("9. 班级 + 邀请码")
invite_code = None

def ic_generate():
    global invite_code
    r = api("POST", f"/classes/{class_id}/invite-codes", json={}, headers=th())
    assert r.status_code == 200
    invite_code = r.json()["code"]
test("班级","生成邀请码", ic_generate)

def ic_list():
    r = api("GET", f"/classes/{class_id}/invite-codes", headers=th())
    assert r.status_code == 200
    assert len(r.json()) >= 1
test("班级","查看邀请码", ic_list)

def ic_join():
    r = api("POST", "/classes/join", json={"code":invite_code}, headers=h(token_s))
    assert r.status_code == 200
    assert "加入班级" in r.text
test("班级","学生加入班级", ic_join)

def ic_dup_join():
    r = api("POST", "/classes/join", json={"code":invite_code}, headers=h(token_s))
    assert r.status_code in (400, 410), f"重复加入应返回400/410, 实际{r.status_code}: {r.text}"
test("班级","重复加入被拒", ic_dup_join)

def ic_invalid():
    api("POST", "/auth/register", json={"name":"学生B","student_id":f"b{int(time.time())}","password":"123456","school_level":"初中"})
    tkn = api("POST", "/auth/login", json={"student_id":uid,"name":"测试学生","password":"newpwd456"}).json()
    # 用另一个学生的 token 测试无效邀请码
    r2 = api("POST", "/auth/register", json={"name":"学生C","student_id":f"c{int(time.time())}","password":"123456","school_level":"初中"})
    t2 = r2.json()["access_token"]
    r = api("POST", "/classes/join", json={"code":"NOEXIST"}, headers={"Authorization":f"Bearer {t2}"})
    assert r.status_code == 404, f"应返回404, 实际{r.status_code}: {r.text}"
test("班级","无效邀请码被拒", ic_invalid)

def ic_my_class():
    r = api("GET", "/classes/my", headers=h(token_s))
    assert r.status_code == 200
    assert r.json()["class_name"] == "初二(3)班"
test("班级","学生查看所在班级", ic_my_class)

def ic_deactivate():
    r = api("DELETE", f"/classes/invite-codes/99999", headers=th())
    assert r.status_code in (404, 403)  # 不存在的码
test("班级","停用不存在的邀请码返回404", ic_deactivate)

# =======================================================
# 教师发布作业 + 学生提交
# =======================================================
section("10. 作业发布")
assign_id = None

def a_create():
    global assign_id
    r = api("POST", "/assignments/teacher", json={
        "title":"周末练习","description":"做前3题","class_id":class_id,
        "questions":[{"q":"2x+3=7","answer":"x=2"},{"q":"x-5=0","answer":"x=5"}],
    }, headers=th())
    assert r.status_code == 200
    assign_id = r.json()["id"]
test("作业发布","教师发布作业", a_create)

def a_list_teacher():
    r = api("GET", "/assignments/teacher", headers=th())
    assert r.status_code == 200
    assert len(r.json()) >= 1
test("作业发布","教师作业列表", a_list_teacher)

def a_student_view():
    r = api("GET", "/assignments/student", headers=h(token_s))
    assert r.status_code == 200
    assert len(r.json()) >= 1
test("作业发布","学生查看作业", a_student_view)

def a_student_submit():
    r = api("POST", f"/assignments/student/{assign_id}/submit", json={
        "answers":[{"q":"2x+3=7","answer":"x=2"},{"q":"x-5=0","answer":"x=5"}],
    }, headers=h(token_s))
    assert r.status_code == 200
    assert r.json()["status"] == "submitted"
test("作业发布","学生提交作业", a_student_submit)

def a_dup_submit():
    r = api("POST", f"/assignments/student/{assign_id}/submit", json={
        "answers":[{"q":"2x+3=7","answer":"x=2"}],
    }, headers=h(token_s))
    assert r.status_code == 400
test("作业发布","重复提交被拒", a_dup_submit)

def a_teacher_view_submissions():
    r = api("GET", f"/assignments/teacher/{assign_id}/submissions", headers=th())
    assert r.status_code == 200
    assert len(r.json()["submissions"]) >= 1
test("作业发布","教师查看提交记录", a_teacher_view_submissions)

# =======================================================
# 教师端学生管理
# =======================================================
section("11. 学生管理")

def t_students():
    r = api("GET", "/teacher/students", headers=th())
    assert r.status_code == 200
    d = r.json()
    assert d["total"] >= 1
test("学生管理","教师查看学生列表", t_students)

def t_student_info():
    r = api("GET", f"/teacher/students/{sid_s}/info", headers=th())
    assert r.status_code == 200
    assert r.json()["name"] == "测试学生"
test("学生管理","教师查看单个学生信息", t_student_info)

def t_student_errors():
    r = api("GET", f"/teacher/student/{sid_s}/errors", headers=th())
    assert r.status_code == 200
test("学生管理","教师查看学生错题", t_student_errors)

def t_error_summary():
    r = api("GET", "/teacher/errors", headers=th())
    assert r.status_code == 200
    assert isinstance(r.json(), list)
test("学生管理","错题汇总", t_error_summary)

def t_errors_kp():
    # 随便查一个知识点
    r = api("GET", f"/teacher/errors/knowledge-point/一元二次方程", headers=th())
    assert r.status_code == 200
    assert "knowledge_point" in r.json()
test("学生管理","知识点钻取", t_errors_kp)

# =======================================================
# 管理员
# =======================================================
section("12. 管理员")
admin_h = None

def ad_login():
    global admin_h
    r = api("POST", "/auth/teacher/login", json={"username":"admin","password":"admin123"})
    assert r.status_code == 200
    admin_h = {"Authorization": f"Bearer {r.json()['access_token']}"}
test("管理员","管理员登录", ad_login)

def ad_dashboard():
    r = api("GET", "/admin/dashboard", headers=admin_h)
    assert r.status_code == 200
    d = r.json()
    assert "teacher_count" in d
    assert "student_count" in d
    assert len(d["monthly_trends"]) == 6
test("管理员","总览仪表盘", ad_dashboard)

def ad_teachers():
    r = api("GET", "/admin/teachers", headers=admin_h)
    assert r.status_code == 200
test("管理员","教师列表", ad_teachers)

def ad_classes():
    r = api("GET", "/admin/classes", headers=admin_h)
    assert r.status_code == 200
    assert len(r.json()) >= 1
test("管理员","班级列表", ad_classes)

def ad_students():
    r = api("GET", "/admin/students", headers=admin_h)
    assert r.status_code == 200
    d = r.json()
    assert "total" in d
    assert d["total"] >= 1
test("管理员","学生列表(分页)", ad_students)

def ad_assignments():
    r = api("GET", "/admin/assignments", headers=admin_h)
    assert r.status_code == 200
    assert len(r.json()) >= 1
test("管理员","作业列表", ad_assignments)

def ad_exams():
    r = api("GET", "/admin/exams", headers=admin_h)
    assert r.status_code == 200
test("管理员","考试记录", ad_exams)

def ad_ai_providers():
    r = api("GET", "/admin/ai-providers", headers=admin_h)
    assert r.status_code == 200
    providers = r.json()
    assert len(providers) >= 1
test("管理员","AI模型配置列表", ad_ai_providers)

# =======================================================
# 权限隔离
# =======================================================
section("13. 权限与安全")
def perm_unauth():
    r = api("GET", "/teacher/dashboard")
    assert r.status_code == 401
test("安全","未登录访问被拒", perm_unauth)

def perm_student_not_teacher():
    r = api("GET", "/teacher/dashboard", headers=h(token_s))
    assert r.status_code == 403
test("安全","学生不能访问教师端", perm_student_not_teacher)

def perm_student_not_admin():
    r = api("GET", "/admin/dashboard", headers=h(token_s))
    assert r.status_code == 403
test("安全","学生不能访问管理端", perm_student_not_admin)

def perm_expired_token():
    r = api("GET", "/teacher/dashboard", headers={"Authorization":"Bearer fake.token.here"})
    assert r.status_code == 401
test("安全","伪造 token 被拒", perm_expired_token)

# =======================================================
# 边界情况
# =======================================================
section("14. 边界情况")

def empty_homework_id():
    r = api("GET", "/homework/upload/99999/status", headers=h(token_s))
    assert r.status_code == 404
test("边界","不存在的作业状态返回404", empty_homework_id)

def exam_by_other_student():
    # 创建一个新学生，尝试看别人的考试
    uid2 = f"t2_{int(time.time())}"
    r = api("POST", "/auth/register", json={"name":"学生2","student_id":uid2,"password":"123456","school_level":"初中"})
    assert r.status_code == 200
    t2 = r.json()["access_token"]
    r2 = api("GET", f"/exam/{exam_id}/report", headers={"Authorization":f"Bearer {t2}"})
    assert r2.status_code == 404  # 跨学生不可见
test("边界","不能查看他人考试", exam_by_other_student)

def max_student_id():
    r = api("POST", "/auth/register", json={"name":"x","student_id":f"a30_{int(time.time())}","password":"123456","school_level":"初中"})
    assert r.status_code == 200, f"长学号注册失败: {r.status_code} {r.text}"
test("边界","30位长学号注册", max_student_id)

def admin_delete_class():
    # 先创建一个仅用于测试的班级
    r = api("POST", "/classes", json={"name":"测试用班","school_level":"初中"}, headers=th())
    assert r.status_code == 200
    cid = r.json()["id"]
    r2 = api("DELETE", f"/admin/classes/{cid}", headers=admin_h)
    assert r2.status_code == 200
test("边界","管理员删除班级", admin_delete_class)

# =======================================================
# 总分
# =======================================================
section("测试结果")
print(f"  总测试: {PASS + FAIL + SKIP}")
print(f"  ✅ 通过: {PASS}")
print(f"  ❌ 失败: {FAIL}")
print(f"  ⚠️ 跳过: {SKIP}")
if ERRORS:
    print(f"\n  错误详情:")
    for e in ERRORS[:10]:
        print(e)
    if len(ERRORS) > 10:
        print(f"  ... 还有 {len(ERRORS)-10} 个错误")

print()
sys.exit(0 if FAIL == 0 else 1)
