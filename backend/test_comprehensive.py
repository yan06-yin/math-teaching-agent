import sys, os, json, io
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
for f in ['database/math_teaching.db', 'test_comprehensive.db']:
    try: os.remove(f)
    except: pass
from fastapi.testclient import TestClient
from config import settings
settings.DATABASE_URL = 'sqlite:///./test_comprehensive.db'
from database import init_db
from models import Base
from main import app
client = TestClient(app)
init_db()
R = {'p': 0, 'f': 0, 't': []}
def ok(n, c, d=''):
    if c: R['p']+=1; R['t'].append('  OK: '+n); print('  OK: '+n)
    else: R['f']+=1; R['t'].append('  FAIL: '+n+'  '+str(d)); print('  FAIL: '+n+'  '+str(d))
