"""Test invite code specifically"""
import requests
BASE='https://math-teaching-agent-production-0537.up.railway.app'
import random
r=requests.post(f'{BASE}/api/auth/teacher/register',json={
    'name':f'测试{random.randint(1000,9999)}','username':f'teacher_invite_test_{random.randint(10000,99999)}','password':'test123456','school':'校'
},timeout=10)
print(f'Register: {r.status_code}')
tok=r.json().get('access_token','NONE')
r=requests.post(f'{BASE}/api/classes/',json={'name':'测试班','school_level':'初中'},
    headers={'Authorization':f'Bearer {tok}'},timeout=10)
cid=r.json()['id']
print(f'Class: {cid}')

import time
for i in range(3):
    r=requests.post(f'{BASE}/api/classes/{cid}/invite-codes',
        headers={'Authorization':f'Bearer {tok}'},timeout=10)
    print(f'Attempt {i+1}: {r.status_code} {r.text[:200]}')
    time.sleep(1)
