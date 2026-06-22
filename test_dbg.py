"""Debug: Direct test of exam generation via DeepSeek"""
import requests, json, time

BASE = 'https://math-teaching-agent-production-0537.up.railway.app'

# Register student
r = requests.post(BASE + '/api/auth/register', json={
    'name':'DBG','student_id':'DBG001','password':'test123456','school_level':'初中'
}, timeout=15)
tok = r.json()['access_token']

# Generate exam
r = requests.post(BASE + '/api/exam/generate', json={
    'knowledge_points':['一元二次方程'],'difficulty':3,'question_count':2
}, headers={'Authorization':'Bearer '+tok}, timeout=30)
print('Generate:', r.status_code, r.text[:200])
eid = r.json()['exam_id']
print('Exam ID:', eid)

# Poll
for i in range(24):
    time.sleep(5)
    r = requests.get(BASE + '/api/exam/generate/%d/status' % eid,
        headers={'Authorization':'Bearer '+tok}, timeout=30)
    print('Poll', i+1, ':', r.json().get('status'), r.json().get('error','')[:80])
    if r.json().get('questions'):
        print('  Questions:', len(r.json()['questions']))
        break
    if r.json().get('status') == 'error':
        print('  ERROR:', r.json().get('error'))
        break
