"""Test DeepSeek V4 Flash via OpenModel"""
import requests, json, time

BASE = 'https://math-teaching-agent-production-0537.up.railway.app'
print('=== 1. Admin Login ===')
r = requests.post(BASE + '/api/auth/teacher/login', json={'username':'admin','password':'admin123'}, timeout=30)
print('Login:', r.status_code, r.text[:100])
tok = r.json()['access_token']
print('OK, token:', tok[:30])

print('\n=== 2. AI Providers ===')
r = requests.get(BASE + '/api/admin/ai-providers', headers={'Authorization':'Bearer '+tok}, timeout=30)
for p in r.json():
    status = 'ACTIVE' if p['is_active'] else 'OFF'
    print('  [%s] %s key=%s...' % (status, p['name'], p['api_key'][:20]))

print('\n=== 3. Activate DeepSeek ===')
for p in r.json():
    if p['model'] == 'deepseek-v4-flash':
        if not p['is_active']:
            r2 = requests.put(BASE + '/api/admin/ai-providers/%d' % p['id'],
                json={'is_active': True}, headers={'Authorization':'Bearer '+tok}, timeout=30)
            print('Activate: %d %s' % (r2.status_code, r2.text[:100]))
        else:
            print('Already active')

print('\n=== 4. Verify DeepSeek can generate exam ===')
import random
uid = 'DS' + str(random.randint(1000,9999))
r = requests.post(BASE + '/api/auth/register', json={
    'name':'DS','student_id':uid,'password':'test123456','school_level':'初中'
}, timeout=30)
s_tok = r.json()['access_token']

r = requests.post(BASE + '/api/exam/generate', json={
    'knowledge_points':['一元二次方程'],'difficulty':3,'question_count':2
}, headers={'Authorization':'Bearer '+s_tok}, timeout=30)
eid = r.json()['exam_id']
print('Exam:', eid)

for i in range(36):
    r = requests.get(BASE + '/api/exam/generate/%d/status' % eid,
        headers={'Authorization':'Bearer '+s_tok}, timeout=30)
    data = r.json()
    if data['status'] == 'done':
        qs = data.get('questions', [])
        print('DONE! Questions:', len(qs))
        for q in qs[:2]:
            txt = q.get('question','')[:60]
            print('  Q:', txt)
        break
    elif data['status'] == 'error':
        err = data.get('error','')
        print('ERROR:', err)
        break
    else:
        if i % 6 == 5:
            print('Waiting...', i+1, '/36')
        time.sleep(5)

print('\n=== 5. Restore Agnes as default ===')
for p in requests.get(BASE + '/api/admin/ai-providers', headers={'Authorization':'Bearer '+tok}, timeout=30).json():
    if p['model'] == 'agnes-2.0-flash':
        requests.put(BASE + '/api/admin/ai-providers/%d' % p['id'],
            json={'is_active': True}, headers={'Authorization':'Bearer '+tok}, timeout=30)
        print('Restored Agnes AI Flash as active')
        break

print('\n=== DONE ===')
