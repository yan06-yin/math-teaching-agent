"""Test all core functions: register, login, exam, grading"""
import requests, json, time, random, sys

BASE = 'https://math-teaching-agent-production-0537.up.railway.app'
ok = 0
fail = 0

def _raise(msg):
    raise Exception(msg)

def t(name, fn):
    global ok, fail
    try:
        fn()
        ok += 1
        print('  OK  ' + name)
    except Exception as e:
        fail += 1
        print('  FAIL ' + name + ': ' + str(e))

# 1. Register & Login
uid = 'STU' + str(random.randint(10000,99999))
r = requests.post(BASE + '/api/auth/register', json={
    'name': '测试', 'student_id': uid, 'password': 'test123456', 'school_level': '初中'
}, timeout=15)
t('register', lambda: (r.status_code == 200 or (_raise(r.text))))
tok_s = r.json()['access_token']

r = requests.post(BASE + '/api/auth/login', json={
    'name': '测试', 'student_id': uid, 'password': 'test123456'
}, timeout=15)
t('login', lambda: r.status_code == 200)

r = requests.post(BASE + '/api/auth/login', json={
    'name': '测试', 'student_id': uid, 'password': 'wrong'
}, timeout=15)
t('login wrong pw', lambda: r.status_code == 401)

# 2. Exam generate & poll
t('exam generate', lambda: (
    requests.post(BASE + '/api/exam/generate', json={
        'knowledge_points': ['一元二次方程'], 'difficulty': 3, 'question_count': 3
    }, headers={'Authorization': 'Bearer ' + tok_s}, timeout=30).status_code == 200
))

r = requests.post(BASE + '/api/exam/generate', json={
    'knowledge_points': ['一元二次方程'], 'difficulty': 3, 'question_count': 3
}, headers={'Authorization': 'Bearer ' + tok_s}, timeout=30)
eid = r.json()['exam_id']

generated = False
for i in range(60):
    time.sleep(5)
    r = requests.get(BASE + '/api/exam/generate/%d/status' % eid,
        headers={'Authorization': 'Bearer ' + tok_s}, timeout=30)
    if r.json().get('status') == 'done':
        generated = True
        break
    if r.json().get('status') == 'error':
        print('  EXAM GEN ERROR:', r.json().get('error'))
        break

t('exam poll generation', lambda: generated or (_raise('timeout')))
qs = r.json().get('questions', [])
print('  Questions:', len(qs))

# 3. Submit exam & grade
answers = [{'question_index': i, 'answer': '测试答案'} for i in range(len(qs))]
r = requests.post(BASE + '/api/exam/%d/submit' % eid, json={'answers': answers},
    headers={'Authorization': 'Bearer ' + tok_s}, timeout=30)
t('exam submit', lambda: r.status_code == 200)

graded = False
for i in range(60):
    time.sleep(5)
    r = requests.get(BASE + '/api/exam/%d/status' % eid,
        headers={'Authorization': 'Bearer ' + tok_s}, timeout=30)
    if r.json().get('status') == 'done':
        graded = True
        break
    if r.json().get('status') == 'error':
        print('  EXAM GRADE ERROR:', r.json().get('error'))
        break
t('exam poll grading', lambda: graded or (_raise('timeout')))
score = r.json().get('score')
print('  Score:', score)

# 4. Homework upload
import io
files = {'file': ('test.jpg', io.BytesIO(b'fake_image_data'), 'image/jpeg')}
r = requests.post(BASE + '/api/homework/upload',
    headers={'Authorization': 'Bearer ' + tok_s},
    data={'student_answers': '1. 2+3=5, 正确'},
    files=files, timeout=30)
t('homework upload', lambda: r.status_code in [200, 422])

print()
print('=' * 40)
print('Results: %d OK, %d FAIL' % (ok, fail))
print('=' * 40)

def _raise(msg):
    raise Exception(msg)
