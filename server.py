import json, os, sqlite3, secrets, hashlib, hmac, mimetypes, socket
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from http.cookies import SimpleCookie
from pathlib import Path
ROOT=Path(__file__).resolve().parent
DB=ROOT/'mingle.db'
SESS={}
CALLS={} # ephemeral call state, only real accounts
CALL_EVENTS={}
import threading, time
CALL_LOCK=threading.Lock()
def emit(uid,event):
 with CALL_LOCK:
  CALL_EVENTS.setdefault(uid,[]).append(dict(event,seq=time.time_ns()))
  CALL_EVENTS[uid]=CALL_EVENTS[uid][-100:]
def db():
 c=sqlite3.connect(DB,timeout=15); c.row_factory=sqlite3.Row; return c
def init():
 with db() as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, salt TEXT NOT NULL, password TEXT NOT NULL, bio TEXT DEFAULT '', created TEXT DEFAULT CURRENT_TIMESTAMP); CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY, sender INTEGER NOT NULL, recipient INTEGER NOT NULL, body TEXT NOT NULL, created TEXT DEFAULT CURRENT_TIMESTAMP); CREATE TABLE IF NOT EXISTS friendships(user_id INTEGER NOT NULL, friend_id INTEGER NOT NULL, UNIQUE(user_id,friend_id)); CREATE TABLE IF NOT EXISTS rooms(id INTEGER PRIMARY KEY, title TEXT, category TEXT, host TEXT);''')
  if not c.execute('SELECT COUNT(*) FROM rooms').fetchone()[0]: c.executemany('INSERT INTO rooms(title,category,host) VALUES(?,?,?)',[('Tamil Chill Vibes','Tamil','Mingle'),('Music & Memories','Music','Mingle'),('Late Night Talks','Hangout','Mingle'),('New Friends Corner','Friends','Mingle'),('Gaming Squad','Games','Mingle'),('English Café','English','Mingle')])
  # Clearly labeled sample profiles for UI testing; not real members.
  demos=[('Arjun Kumar','Gaming, cricket and weekend hangouts 🎮'),('Priya S','Music lover 🎧 | Chennai vibes'),('Naveen Raj','Tech talks and new friendships 💻'),('Divya M','Coffee, books and good conversations ☕'),('Karthik V','Football and movies ⚽'),('Meera Anand','Art, travel and photography 📷'),('Rahul Dev','Late night music sessions 🎵'),('Anu Sri','Foodie exploring new places 🍜'),('Sanjay R','Anime and gaming buddy 🎮'),('Keerthana P','Dancing and positive vibes ✨'),('Vishal N','Coding and startup ideas 🚀'),('Harini B','Books, nature and pets 🐾')]
  for i,(name,bio) in enumerate(demos,1):
   email=f'mingle-demo-{i}@example.invalid'
   if not c.execute('SELECT id FROM users WHERE email=?',(email,)).fetchone():
    salt=secrets.token_hex(16)
    c.execute('INSERT INTO users(name,email,salt,password,bio) VALUES(?,?,?,?,?)',(name,email,salt,hashlib.pbkdf2_hmac('sha256',secrets.token_bytes(24),bytes.fromhex(salt),220000).hex(),bio))
def password(p,s): return hashlib.pbkdf2_hmac('sha256',p.encode(),bytes.fromhex(s),220000).hex()
def public_user(r): return {'id':r['id'],'name':r['name'],'bio':r['bio'] or '', 'initial':r['name'][:1].upper(), 'demo':r['email'].endswith('@example.invalid')}
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*a): pass
 def reply(self,obj,status=200,cookie=None):
  raw=json.dumps(obj,ensure_ascii=False).encode(); self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');
  if cookie:self.send_header('Set-Cookie',cookie)
  self.end_headers();self.wfile.write(raw)
 def user(self):
  cookie=SimpleCookie()
  try: cookie.load(self.headers.get('Cookie',''))
  except: return None
  sid=cookie.get('mingle_session');uid=SESS.get(sid.value) if sid else None
  if not uid:return None
  with db() as c:return c.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
 def body(self):
  size=int(self.headers.get('Content-Length','0'))
  if size>20000:raise ValueError('Request too large')
  return json.loads(self.rfile.read(size) or b'{}')
 def do_GET(self):
  path=urlparse(self.path).path
  if path.startswith('/api/'):
   u=self.user()
   if path=='/api/me':return self.reply({'user':public_user(u) if u else None})
   if path=='/api/rooms':
    with db() as c:return self.reply({'rooms':[dict(r) for r in c.execute('SELECT * FROM rooms')]})
   if not u:return self.reply({'error':'Please log in'},401)
   if path=='/api/call/events':
    from urllib.parse import parse_qs
    since=int(parse_qs(urlparse(self.path).query).get('since',['0'])[0])
    with CALL_LOCK: events=[e for e in CALL_EVENTS.get(u['id'],[]) if e['seq']>since]
    return self.reply({'events':events})
   with db() as c:
    if path=='/api/people':return self.reply({'people':[public_user(r) for r in c.execute('SELECT * FROM users WHERE id != ? ORDER BY id DESC LIMIT 100',(u['id'],))]})
    if path=='/api/friends':return self.reply({'friends':[public_user(r) for r in c.execute('SELECT u.* FROM users u JOIN friendships f ON u.id=f.friend_id WHERE f.user_id=?',(u['id'],))]})
    if path=='/api/messages':
     try:other=int(__import__('urllib.parse',fromlist=['parse_qs']).parse_qs(urlparse(self.path).query).get('with',['0'])[0])
     except:return self.reply({'error':'Invalid user'},400)
     rows=c.execute('SELECT id,sender,recipient,body,created FROM messages WHERE (sender=? AND recipient=?) OR (sender=? AND recipient=?) ORDER BY id DESC LIMIT 100',(u['id'],other,other,u['id'])).fetchall()
     return self.reply({'messages':[dict(r) for r in reversed(rows)]})
   return self.reply({'error':'Not found'},404)
  if path=='/':path='/index.html'
  target=(ROOT/'public'/path.lstrip('/')).resolve()
  if not target.is_relative_to((ROOT/'public').resolve()) or not target.is_file():self.send_error(404);return
  raw=target.read_bytes();self.send_response(200);self.send_header('Content-Type',mimetypes.guess_type(target)[0] or 'text/plain');self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store, max-age=0');self.end_headers();self.wfile.write(raw)
 def do_POST(self):
  path=urlparse(self.path).path
  try:data=self.body()
  except Exception:return self.reply({'error':'Invalid request'},400)
  if path in ('/api/register','/api/login'):
   email=str(data.get('email','')).strip().lower();p=str(data.get('password',''));name=str(data.get('name','')).strip()
   if '@' not in email or len(p)<6:return self.reply({'error':'Enter a valid email and password (6+ characters)'},400)
   with db() as c:
    if path=='/api/register':
     if len(name)<2 or len(name)>40:return self.reply({'error':'Name must be 2–40 characters'},400)
     salt=secrets.token_hex(16)
     try:c.execute('INSERT INTO users(name,email,salt,password) VALUES(?,?,?,?)',(name,email,salt,password(p,salt)))
     except sqlite3.IntegrityError:return self.reply({'error':'Email already registered'},409)
    u=c.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
    if not u or not hmac.compare_digest(u['password'],password(p,u['salt'])):return self.reply({'error':'Invalid email or password'},401)
   sid=secrets.token_urlsafe(32);SESS[sid]=u['id'];return self.reply({'user':public_user(u)},cookie=f'mingle_session={sid}; HttpOnly; SameSite=Lax; Path=/')
  if path=='/api/logout':
   cookie=SimpleCookie();cookie.load(self.headers.get('Cookie',''));sid=cookie.get('mingle_session')
   if sid:SESS.pop(sid.value,None)
   return self.reply({'ok':True},cookie='mingle_session=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0')
  u=self.user()
  if not u:return self.reply({'error':'Please log in'},401)
  if path=='/api/call/signal':
   try: other=int(data.get('to'));kind=str(data.get('type'));payload=data.get('payload',{})
   except:return self.reply({'error':'Bad signal'},400)
   if other==u['id'] or kind not in ('offer','answer','ice','hangup','reject') or len(json.dumps(payload))>12000:return self.reply({'error':'Invalid call signal'},400)
   with db() as c: target=c.execute('SELECT * FROM users WHERE id=?',(other,)).fetchone()
   if not target or target['email'].endswith('@example.invalid') or u['email'].endswith('@example.invalid'):return self.reply({'error':'Calls only work between real registered users, not DEMO profiles'},400)
   emit(other,{'from':u['id'],'name':u['name'],'type':kind,'payload':payload})
   return self.reply({'ok':True})
  if path=='/api/profile':
   name=str(data.get('name','')).strip();bio=str(data.get('bio','')).strip()
   if not 2<=len(name)<=40 or len(bio)>180:return self.reply({'error':'Invalid name or bio'},400)
   with db() as c:c.execute('UPDATE users SET name=?,bio=? WHERE id=?',(name,bio,u['id']))
   return self.reply({'ok':True})
  if path=='/api/friend':
   try:other=int(data.get('id'))
   except:return self.reply({'error':'Invalid friend'},400)
   if other==u['id']:return self.reply({'error':'Cannot add yourself'},400)
   with db() as c:
    if not c.execute('SELECT id FROM users WHERE id=?',(other,)).fetchone():return self.reply({'error':'User not found'},404)
    c.execute('INSERT OR IGNORE INTO friendships(user_id,friend_id) VALUES(?,?)',(u['id'],other))
   return self.reply({'ok':True})
  if path=='/api/message':
   try:other=int(data.get('to'))
   except:return self.reply({'error':'Invalid recipient'},400)
   body=str(data.get('body','')).strip()
   if not 1<=len(body)<=1000 or other==u['id']:return self.reply({'error':'Message must be 1–1000 characters'},400)
   with db() as c:
    if not c.execute('SELECT id FROM users WHERE id=?',(other,)).fetchone():return self.reply({'error':'User not found'},404)
    c.execute('INSERT INTO messages(sender,recipient,body) VALUES(?,?,?)',(u['id'],other,body))
   return self.reply({'ok':True})
  return self.reply({'error':'Not found'},404)
if __name__=='__main__':
 init();port=int(os.environ.get('PORT','8765'));server=ThreadingHTTPServer(('0.0.0.0',port),Handler)
 print(f'VIBELY is running: http://localhost:{port}',flush=True)
 try:server.serve_forever()
 except KeyboardInterrupt:pass
