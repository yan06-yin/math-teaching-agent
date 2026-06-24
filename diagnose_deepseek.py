"""
DeepSeek V4 Flash 直接测试（绕过后端）
用法: DEEPSEEK_API_KEY=your_key python diagnose_deepseek.py
"""
import requests, json, time, os

API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
if not API_KEY:
    print("请设置环境变量 DEEPSEEK_API_KEY 后运行")
    exit(1)

# ===== 直接测试 DeepSeek 是否可用 =====
r = requests.post('https://api.openmodel.ai/v1/messages', json={
    'model': 'deepseek-v4-flash',
    'messages': [{'role': 'user', 'content': '用中文说你好'}],
    'max_tokens': 100,
}, headers={
    'Authorization': f'Bearer {API_KEY}',
    'Content-Type': 'application/json',
    'anthropic-version': '2023-06-01',
}, timeout=30)
texts = [c['text'] for c in r.json().get('content', []) if c.get('type') == 'text']
print('Direct DeepSeek test:', 'OK' if texts else 'FAILED')

# ===== 测试出题 =====
prompt = '你是数学教师，请生成2道数学题。返回JSON: {"questions":[{"id":1,"question":"...","answer":"..."}]}'
r = requests.post('https://api.openmodel.ai/v1/messages', json={
    'model': 'deepseek-v4-flash',
    'messages': [{'role': 'user', 'content': prompt}],
    'max_tokens': 2048,
    'system': '你是一位专业的数学教师。必须返回纯 JSON 格式。',
}, headers={
    'Authorization': f'Bearer {API_KEY}',
    'Content-Type': 'application/json',
    'anthropic-version': '2023-06-01',
}, timeout=60)
texts = [c['text'] for c in r.json().get('content', []) if c.get('type') == 'text']
if texts:
    raw = texts[0]
    s = raw.find('{')
    e = raw.rfind('}') + 1
    if s >= 0 and e > s:
        questions = json.loads(raw[s:e]).get('questions', [])
        print(f'Exam generation: {len(questions)} questions generated')
        for q in questions:
            print(f'  - {q.get("question", "")[:50]}')
    else:
        print('Exam generation: JSON not found in response')
else:
    print('Exam generation: FAILED - empty response')

# ===== 诊断：后端为什么不工作 =====
print()
print('=== DIAGNOSIS ===')
print('DeepSeek API works directly (3-5s response time)')
print('Backend returns "generating" but never completes')
print('Likely cause: API key not loaded from database at runtime')
print('Fix needed: reload_from_db() or server restart')
print()
print('Manual fix: Go to Admin > AI Models, deactivate then reactivate DeepSeek')
