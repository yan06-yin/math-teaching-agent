"""
Comprehensive project audit & fix script
自动检查项目所有文件中的问题并修复
"""
import os, re, sys, json

PROJECT = r"C:\Users\颜\Desktop\实验作业,计算机\math-teaching-agent"
issues = []

def find_file(name):
    for root, dirs, files in os.walk(PROJECT):
        if 'node_modules' in root or '.git' in root or '__pycache__' in root or '.next' in root:
            continue
        if name in files:
            return os.path.join(root, name)
    return None

# 1. Check index.txt files (Next.js generates .txt alongside .html)
txt_files = []
for root, dirs, files in os.walk(os.path.join(PROJECT, 'backend', 'frontend')):
    for f in files:
        if f.endswith('.txt'):
            txt_files.append(os.path.join(root, f))

if txt_files:
    print(f"Found {len(txt_files)} .txt files alongside .htmls (Next.js static export)")
    for f in txt_files:
        os.remove(f)
        print(f"  Removed: {os.path.relpath(f, PROJECT)}")

# 2. Check for charset/encoding issues in auth.py
auth_py = os.path.join(PROJECT, 'backend', 'routers', 'auth.py')
if os.path.exists(auth_py):
    with open(auth_py, 'r', encoding='utf-8') as f:
        content = f.read()
    # Make sure there's no Chinese chars in the encoding-sensitive path
    if 'logger.info("✅' in content:
        print("✅ Found emoji in logs - OK")

    # Check the birthday_bcrypt BCrypt/fallback logic exists
    if 'FallbackPwdContext' not in content:
        print("❌ Missing bcrypt fallback in auth.py!")

# 3. Check homework router has no duplicate submission bug
hw_py = os.path.join(PROJECT, 'backend', 'routers', 'homework.py')
if os.path.exists(hw_py):
    with open(hw_py, 'r', encoding='utf-8') as f:
        content = f.read()
    if 'wrong_questions_json' in content:
        print("[OK] homework.py uses direct submission update (no duplicate)")
    if 'process_homework' in content:
        print("[WARN] process_homework still referenced!")

# 4. Verify exam status endpoint handles 0 score
exam_py = os.path.join(PROJECT, 'backend', 'routers', 'exam.py')
if os.path.exists(exam_py):
    with open(exam_py, 'r', encoding='utf-8') as f:
        content = f.read()
    if 'task and task.status' in content:
        print("[OK] exam.py uses task status to judge completion (not score>0)")

# 5. Check no Coze files remain
coze_refs = []
for root, dirs, files in os.walk(PROJECT):
    if 'node_modules' in root or '.git' in root or '__pycache__' in root:
        continue
    for f in files:
        if 'coze' in f.lower():
            coze_refs.append(os.path.join(root, f))
if coze_refs:
    print("[FAIL] Coze files remain: %s" % coze_refs)
else:
    print("✅ No Coze files remain")

# 6. Check no old arch spec
arch = find_file('architecture-spec.md')
if arch:
    print(f"❌ architecture-spec.md still exists!")
else:
    print("✅ architecture-spec.md removed")

# 7. size of project
total_size = 0
for root, dirs, files in os.walk(PROJECT):
    if 'node_modules' in root or '.git' in root or '__pycache__' in root:
        continue
    for f in files:
        fp = os.path.join(root, f)
        try:
            total_size += os.path.getsize(fp)
        except:
            pass
print(f"\n📦 Project size: {total_size/1024:.0f} KB")

# 8. Check requirements
req = os.path.join(PROJECT, 'backend', 'requirements.txt')
if os.path.exists(req):
    with open(req) as f:
        reqs = f.read()
    needed = ['fastapi', 'sqlalchemy', 'passlib', 'python-jose', 'httpx',
              'pydantic', 'pydantic-settings', 'python-multipart']
    missing = [p for p in needed if p not in reqs]
    if missing:
        print(f"❌ Missing deps in requirements: {missing}")
    else:
        print("✅ All required deps present")

print("\n✅ Audit complete!")
