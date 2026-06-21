"""E2E test for math teaching agent"""
import requests, random, time

BASE = 'https://math-teaching-agent-production-0537.up.railway.app'
ok = 0; fail = 0
def t(name, fn):
    global ok,fail
    try:
        fn(); ok+=1; print(f'  OK {name}')
    except Exception as e:
        fail+=1; print(f'  FAIL {name}: {e}')

# 1. Register
sid=f'FT{random.randint(10000,99999)}'
r=requests.post(f'{BASE}/api/auth/register',json={
    'name':'小明','student_id':sid,'password':'test123456','school_level':'初中'
},timeout=10)
t('register',lambda: r.status_code==200)
tok_s=r.json()['access_token']
sid_num=r.json()['student_id']
print(f'  StudentID={sid}')

# 2. Login
r=requests.post(f'{BASE}/api/auth/login',json={
    'name':'小明','student_id':sid,'password':'test123456'
},timeout=10)
t('login',lambda: r.status_code==200)

# 3. Wrong password
r=requests.post(f'{BASE}/api/auth/login',json={
    'name':'小明','student_id':sid,'password':'wrong'
},timeout=10)
t('login wrong pw',lambda: r.status_code==401)

# 4. Teacher register
tid=f'teacher_ft{random.randint(10000,99999)}'
r=requests.post(f'{BASE}/api/auth/teacher/register',json={
    'name':f'张老师{tid[-4:]}','username':tid,'password':'test123456','school':'测试学校'
},timeout=10)
print(f'  Teacher register: {r.status_code} {r.text[:100]}')
tok_t=r.json()['access_token']

# 5. Admin login
r=requests.post(f'{BASE}/api/auth/teacher/login',json={
    'username':'admin','password':'admin123'
},timeout=10)
t('admin login',lambda: r.status_code==200)
tok_a=r.json()['access_token']

# 6. Create class
r=requests.post(f'{BASE}/api/classes/',json={'name':'测试班','school_level':'初中'},
    headers={'Authorization':f'Bearer {tok_t}'},timeout=10)
t('create class',lambda: r.status_code==200)
cid=r.json()['id']

# 7. Invite code
r=requests.post(f'{BASE}/api/classes/{cid}/invite-codes',json={},
    headers={'Authorization':f'Bearer {tok_t}'},timeout=10)
print(f'  Invite response: {r.status_code} {r.text[:200]}')
t('invite code',lambda: r.status_code==200)
code=r.json().get('code') or ''

# 8. Join class
r=requests.post(f'{BASE}/api/classes/join',json={'code':code},
    headers={'Authorization':f'Bearer {tok_s}'},timeout=10)
t('join class',lambda: r.status_code==200)

# 9. Assignment
r=requests.post(f'{BASE}/api/assignments/teacher',json={
    'title':'作业','description':'完成','class_id':cid,
    'questions':[{'id':1,'question':'1+1=?','answer':'2'}]
},headers={'Authorization':f'Bearer {tok_t}'},timeout=10)
print(f'  Assignment create: {r.status_code} {r.text[:200]}')
t('create assignment',lambda: r.status_code==200)
aid=r.json().get('id',0)

r=requests.get(f'{BASE}/api/assignments/student',
    headers={'Authorization':f'Bearer {tok_s}'},timeout=10)
t('view assignments',lambda: r.status_code==200 and len(r.json())>0)

r=requests.post(f'{BASE}/api/assignments/student/{aid}/submit',json={
    'answers':[{'question_index':0,'answer':'2'}]
},headers={'Authorization':f'Bearer {tok_s}'},timeout=10)
t('submit assignment',lambda: r.status_code==200)

# 10. Exam
r=requests.post(f'{BASE}/api/exam/generate',json={
    'knowledge_points':[],'difficulty':3,'question_count':2
},headers={'Authorization':f'Bearer {tok_s}'},timeout=30)
t('generate exam',lambda: r.status_code==200)
eid=r.json()['exam_id']

for i in range(30):
    r=requests.get(f'{BASE}/api/exam/generate/{eid}/status',
        headers={'Authorization':f'Bearer {tok_s}'},timeout=10)
    if r.json().get('status')=='done':break
    time.sleep(5)
t('poll generation',lambda: r.json().get('status')=='done')

r=requests.post(f'{BASE}/api/exam/{eid}/submit',json={
    'answers':[{'question_index':0,'answer':'x=2'},{'question_index':1,'answer':'不会'}]
},headers={'Authorization':f'Bearer {tok_s}'},timeout=30)
t('submit exam',lambda: r.status_code==200)

for i in range(30):
    r=requests.get(f'{BASE}/api/exam/{eid}/status',
        headers={'Authorization':f'Bearer {tok_s}'},timeout=10)
    if r.json().get('status')=='done':break
    time.sleep(5)
t('poll grading',lambda: r.json().get('status')=='done')
print(f'  Score: {r.json().get("score")}')

# 11. Teacher
r=requests.get(f'{BASE}/api/teacher/dashboard',
    headers={'Authorization':f'Bearer {tok_t}'},timeout=10)
t('teacher dashboard',lambda: r.status_code==200)

# 12. Admin
r=requests.get(f'{BASE}/api/admin/dashboard',
    headers={'Authorization':f'Bearer {tok_a}'},timeout=10)
t('admin dashboard',lambda: r.status_code==200)

# 13. Profile
r=requests.get(f'{BASE}/api/analysis/student/{sid_num}',
    headers={'Authorization':f'Bearer {tok_s}'},timeout=10)
t('student profile',lambda: r.status_code==200)

# 14. Exam history
r=requests.get(f'{BASE}/api/exam/my',
    headers={'Authorization':f'Bearer {tok_s}'},timeout=10)
t('exam history',lambda: r.status_code==200 and len(r.json())>0)

print(f'\n=== Results: {ok} OK, {fail} FAIL ===')
