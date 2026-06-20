"""
数学教学智能体 - 全功能集成测试
测试所有接口串联工作
"""
import requests
import json
import sys

BASE = 'https://math-teaching-agent-production-0537.up.railway.app'
passed = 0
failed = 0

def test(name, fn):
    global passed, failed
    try:
        fn()
        passed += 1
        print(f'  ✅ {name}')
    except Exception as e:
        failed += 1
        print(f'  ❌ {name}: {e}')

def check_status(r, expected=200):
    if r.status_code != expected:
        raise Exception(f'状态码 {r.status_code}, 期望 {expected}: {r.text[:200]}')

def has_key(d, key):
    if key not in d:
        raise Exception(f'缺少字段 {key}: {d}')

print('=' * 50)
print('数学教学智能体 - 全功能集成测试')
print(f'目标: {BASE}')
print('=' * 50)

# ====== 1. 健康检查 ======
print('\n📡 1. 健康检查')
def test_health():
    r = requests.get(f'{BASE}/api/health', timeout=10)
    check_status(r)
    data = r.json()
    has_key(data, 'database')
    assert data['status'] == 'ok'
test('GET /api/health', test_health)

# ====== 2. 学生注册 ======
print('\n👨‍🎓 2. 学生注册')
import random
_sid = f'TEST{random.randint(10000,99999)}'
_student_data = None
_student_token = None

def test_student_register():
    global _student_data, _student_token
    r = requests.post(f'{BASE}/api/auth/register', json={
        'name': '测试小明',
        'student_id': _sid,
        'password': 'test123456',
        'school_level': '初中'
    }, timeout=10)
    check_status(r)
    data = r.json()
    has_key(data, 'access_token')
    has_key(data, 'student_id')
    _student_token = data['access_token']
    _student_data = data
test('注册学生', test_student_register)

def test_student_duplicate():
    r = requests.post(f'{BASE}/api/auth/register', json={
        'name': '测试小明',
        'student_id': _sid,
        'password': 'test123456',
        'school_level': '初中'
    }, timeout=10)
    check_status(r, 400)
    assert '已注册' in r.text
test('重复注册拒绝', test_student_duplicate)

def test_student_login():
    r = requests.post(f'{BASE}/api/auth/login', json={
        'name': '测试小明',
        'student_id': _sid,
        'password': 'test123456'
    }, timeout=10)
    check_status(r)
    data = r.json()
    has_key(data, 'access_token')
    global _student_token
    _student_token = data['access_token']
test('学生登录', test_student_login)

def test_student_wrong_password():
    r = requests.post(f'{BASE}/api/auth/login', json={
        'name': '测试小明',
        'student_id': _sid,
        'password': 'wrongpassword'
    }, timeout=10)
    check_status(r, 401)
test('错误密码拒绝', test_student_wrong_password)

def test_student_wrong_id():
    r = requests.post(f'{BASE}/api/auth/login', json={
        'name': '测试小明',
        'student_id': 'NOTEXIST',
        'password': 'test123456'
    }, timeout=10)
    check_status(r, 401)
test('错误学号拒绝', test_student_wrong_id)

# ====== 3. 学生端功能 ======
print('\n📚 3. 学生端功能')
def test_student_profile():
    sid = _student_data['student_id']
    r = requests.get(f'{BASE}/api/analysis/student/{sid}',
        headers={'Authorization': f'Bearer {_student_token}'}, timeout=10)
    check_status(r)
test('获取学生档案', test_student_profile)

def test_student_trends():
    sid = _student_data['student_id']
    r = requests.get(f'{BASE}/api/analysis/class/{sid}/trends',
        headers={'Authorization': f'Bearer {_student_token}'}, timeout=10)
    check_status(r)
    assert isinstance(r.json(), list)
test('获取成绩趋势', test_student_trends)

# ====== 4. 教师注册 ======
print('\n👨‍🏫 4. 教师注册')
_tid = f'teacher{random.randint(10000,99999)}'
_teacher_token = None

def test_teacher_register():
    global _teacher_token
    r = requests.post(f'{BASE}/api/auth/teacher/register', json={
        'name': '测试张老师',
        'username': _tid,
        'password': 'test123456',
        'school': '测试学校'
    }, timeout=10)
    check_status(r)
    data = r.json()
    has_key(data, 'access_token')
    _teacher_token = data['access_token']
test('注册教师', test_teacher_register)

def test_teacher_login():
    global _teacher_token
    r = requests.post(f'{BASE}/api/auth/teacher/login', json={
        'username': _tid,
        'password': 'test123456'
    }, timeout=10)
    check_status(r)
    _teacher_token = r.json()['access_token']
test('教师登录', test_teacher_login)

# ====== 5. 教师端功能 ======
print('\n📊 5. 教师端功能')
def test_teacher_dashboard():
    r = requests.get(f'{BASE}/api/teacher/dashboard',
        headers={'Authorization': f'Bearer {_teacher_token}'}, timeout=10)
    check_status(r)
    data = r.json()
    has_key(data, 'total_students')
    has_key(data, 'total_homework')
    has_key(data, 'total_exams')
    assert data['total_students'] >= 1, f'学生数应为至少1, 实际{data["total_students"]}'
test('教师总览', test_teacher_dashboard)

def test_teacher_students():
    r = requests.get(f'{BASE}/api/teacher/students',
        headers={'Authorization': f'Bearer {_teacher_token}'}, timeout=10)
    check_status(r)
    data = r.json()
    assert isinstance(data, list), f'应为列表, 实际{type(data)}'
    assert len(data) >= 1, f'学生列表应≥1, 实际{len(data)}'
    s = data[0]
    has_key(s, 'id')
    has_key(s, 'name')
    has_key(s, 'student_id')
test('学生列表', test_teacher_students)

def test_teacher_errors():
    r = requests.get(f'{BASE}/api/teacher/errors',
        headers={'Authorization': f'Bearer {_teacher_token}'}, timeout=10)
    check_status(r)
    data = r.json()
    assert isinstance(data, list)
test('错题汇总', test_teacher_errors)

def test_teacher_unauthorized():
    r = requests.get(f'{BASE}/api/teacher/students', timeout=10)
    check_status(r, 401)
test('未授权拒绝', test_teacher_unauthorized)

# ====== 6. 知识点映射 ======
print('\n🧠 6. 知识点系统')
def test_knowledge_points_with_student():
    r = requests.get(f'{BASE}/api/analysis/knowledge-points',
        headers={'Authorization': f'Bearer {_student_token}'}, timeout=10)
    if r.status_code == 200 or r.status_code == 404:
        pass  # 可能存在或不存在，不强制
    else:
        check_status(r)
test('知识点列表', test_knowledge_points_with_student)

print('\n' + '=' * 50)
print(f'📋 测试结果: {passed} 通过, {failed} 失败')
print('=' * 50)
sys.exit(0 if failed == 0 else 1)