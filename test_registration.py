"""
测试注册和查询流程
"""
import requests, json, sys

BASE = 'https://math-teaching-agent-production-0537.up.railway.app'

# 1. 注册一个测试学生
r1 = requests.post(f'{BASE}/api/auth/register', json={
    'name': '测试学生',
    'student_id': 'TEST001',
    'password': 'test123456',
    'school_level': '初中'
}, timeout=10)
print(f'注册学生: {r1.status_code}')
if r1.status_code == 200:
    print(f'  学生ID: {r1.json().get("student_id")}')
else:
    print(f'  错误: {r1.text[:200]}')

# 2. 注册或登录教师
r2 = requests.post(f'{BASE}/api/auth/teacher/register', json={
    'name': '测试教师',
    'username': 'teacher001',
    'password': 'test123456',
    'school': '测试学校'
}, timeout=10)
print(f'\n注册教师: {r2.status_code}')
if r2.status_code == 200:
    token = r2.json()['access_token']
else:
    # 可能已注册，尝试登录
    r2 = requests.post(f'{BASE}/api/auth/teacher/login', json={
        'username': 'teacher001',
        'password': 'test123456'
    }, timeout=10)
    print(f'教师登录: {r2.status_code}')
    token = r2.json()['access_token'] if r2.status_code == 200 else None

if token:
    r3 = requests.get(f'{BASE}/api/teacher/students',
        headers={'Authorization': f'Bearer {token}'}, timeout=10)
    print(f'\n学生列表: {r3.status_code}')
    data = r3.json()
    if isinstance(data, list):
        print(f'  学生数量: {len(data)}')
        for s in data:
            print(f'  - {s["name"]} (学号: {s["student_id"]}, 学段: {s["level"]})')
    else:
        print(f'  返回: {json.dumps(data, ensure_ascii=False)[:500]}')

    # 3. 测试 dashboard
    r4 = requests.get(f'{BASE}/api/teacher/dashboard',
        headers={'Authorization': f'Bearer {token}'}, timeout=10)
    print(f'\nDashboard: {r4.status_code}')
    print(f'  {json.dumps(r4.json(), ensure_ascii=False)[:300]}')

sys.stdout.flush()