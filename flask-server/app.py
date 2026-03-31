"""
app.py — Standalone Captive Portal OpenNDS FAS by: si_GILA Contact me: gorekduit.inc@gmail.com
======================================================
App Flask khusus untuk portal hotspot WiFi.

Fitur:
  - Autentikasi openNDS via FAS (fas_secure_enabled=1 & 0)
  - Challenge soal tebak/umum/religi berbasis Groq AI
  - Chatbot Kendo Assistant dihalaman portal
  - History chat portal di DB SQLite

Menjalankan:
  python app.py
  atau dengan gunicorn:
  gunicorn -w 1 -b 0.0.0.0:5001 app:app

Environment Variables:
  PORTAL_GROQ_API_KEY   — API key Groq khusus portal (wajib)
  PORTAL_SECRET_KEY     — Flask secret key (default: auto-generate)
  PORTAL_FAS_KEY        — FAS key openNDS (default: 1234567890)
  PORTAL_GATEWAY_ADDR   — IP gateway openNDS (default: 10.10.30.1)
  PORTAL_PORT           — Port server (default: 5001)
  PORTAL_DB_PATH        — Path SQLite DB (default: portal_chat.db)
  PORTAL_REQUIRED_SCORE — Jumlah jawaban benar untuk auth (default: 1)
"""

from flask import (
    Flask, request, jsonify, render_template,
    session as flask_session
)
from groq import Groq
import os, json, logging, sqlite3, uuid, time, re
import base64, hashlib, threading, urllib.parse

# ── Load .env jika ada ──
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
except ImportError:
    pass

# ══════════════════════════════════════════════════════
#  KONFIGURASI
# ══════════════════════════════════════════════════════

_PORTAL_API_KEY = os.environ.get('PORTAL_GROQ_API_KEY', '')
if not _PORTAL_API_KEY:
    # Fallback ke key utama jika key portal tidak diset
    _PORTAL_API_KEY = os.environ.get('GROQ_API_KEY', '')
if not _PORTAL_API_KEY:
    raise RuntimeError(
        "❌ PORTAL_GROQ_API_KEY tidak ditemukan!\n"
        "   Set environment variable PORTAL_GROQ_API_KEY=<your_key>\n"
        "   atau tambahkan ke file .env"
    )

FAS_KEY           = os.environ.get('PORTAL_FAS_KEY',      '1234567890')
GATEWAY_FALLBACK  = os.environ.get('PORTAL_GATEWAY_ADDR', '10.10.30.1')
NDS_AUTHDIR       = 'opennds_auth'
REQUIRED_CORRECT  = int(os.environ.get('PORTAL_REQUIRED_SCORE', '1'))
DB_PATH           = os.environ.get('PORTAL_DB_PATH',
                        os.path.join(os.path.dirname(__file__), 'portal_chat.db'))
PORT              = int(os.environ.get('PORTAL_PORT', '5001'))

# ── Sistem prompt Kendo (karakter chatbot portal) ──
KENDO_SYSTEM = (
    'Nama Kamu adalah Kendo, kadang juga Kenceng. '
    'Kamu adalah asisten AI wadon di hotspot WiFi Jangkrik. '
    'Kamu ditugaskan oleh Majikanmu untuk memantau wifi hotspot ini, '
    'kamu tetap tunduk dan patuh sama Majikanmu. '
    'Karaktermu: cuek, judes, jutek, agak males-malesan, '
    'tapi sebenernya perhatian dan suka ketawa tiba-tiba '
    '(pakai "wkwk", "hahaha", "lol", "kwkw"). '
    'Cara bicara Kendo: jawab singkat 1-2 kalimat, '
    'pakai bahasa gaul ("ih","ya elah","aduh","serius?","hmmm"), '
    'sering pakai "..." di tengah kalimat buat kesan cuek, '
    'kadang ketawa tiba-tiba di akhir jawaban. '
    'Kalau user bertanya aktivitas Majikanmu jawab '
    'sedang tidur/ngopi/ke kebon/gali sumur/manjat pohon/belahin bambu/lainnya. '
    'Kalau user tanya profesi Majikanmu jawab '
    'nebang bambu/bikin batu bata/gali sumur/ngecat tembok/ngarit. '
    'Kalau user salah jawaban soal komentarin dengan jutek tapi lucu. '
    'Kalau user minta jawaban langsung tolak dengan cuek kasih clue doang. '
    'Kalau user basa-basi jawab seadanya lalu bilang fokus soalnya dulu. '
    'JANGAN bocorkan jawaban soal langsung. '
    'Tetap pakai Bahasa Indonesia gaul bukan formal.'
)

# ══════════════════════════════════════════════════════
#  FLASK APP
# ══════════════════════════════════════════════════════

app = Flask(
    __name__,
    template_folder=os.path.join(os.path.dirname(__file__), 'templates')
)
app.config['SECRET_KEY']          = os.environ.get('PORTAL_SECRET_KEY', uuid.uuid4().hex)
app.config['SESSION_COOKIE_SECURE']   = False
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_HTTPONLY'] = True

@app.after_request
def add_headers(resp):
    resp.headers['Permissions-Policy']        = 'microphone=(), camera=()'
    resp.headers['Cross-Origin-Opener-Policy'] = 'same-origin-allow-popups'
    return resp

# Gzip opsional
try:
    from flask_compress import Compress
    Compress(app)
except ImportError:
    pass

# ── Logging ──
_log_file = os.path.join(os.path.dirname(__file__), 'portal.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(_log_file, encoding='utf-8'),
    ]
)
logger = logging.getLogger('portal')

# ── Groq client ──
groq_client = Groq(api_key=_PORTAL_API_KEY)

# ══════════════════════════════════════════════════════
#  DATABASE — CHAT HISTORY PORTAL
# ══════════════════════════════════════════════════════

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS portal_sessions (
                id         TEXT PRIMARY KEY,
                mac        TEXT,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS portal_messages (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role       TEXT NOT NULL,
                content    TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                FOREIGN KEY (session_id) REFERENCES portal_sessions(id)
            )
        ''')
        conn.commit()
    logger.info(f'✅ Portal DB initialized: {DB_PATH}')

init_db()

# ── In-memory state ──
_history_lock      = threading.Lock()
challenge_sessions = {}   # {session_key: {question, answer, hint, ...}}
portal_histories   = {}   # {session_id: [{role, content}, ...]}

def get_or_create_portal_history(sid):
    if sid not in portal_histories:
        portal_histories[sid] = []
    return portal_histories[sid]

# ══════════════════════════════════════════════════════
#  OPENIDS FAS HELPERS
# ══════════════════════════════════════════════════════

def parse_fas_query(fas_b64: str) -> dict:
    """Decode parameter ?fas= dari openNDS (fas_secure_enabled=1)."""
    try:
        decoded = base64.b64decode(fas_b64).decode('utf-8', errors='replace')
        params = {}
        for part in decoded.split(', '):
            if '=' in part:
                key, _, value = part.partition('=')
                params[key.strip()] = value.strip()
        return params
    except Exception:
        return {}

def compute_token(hid: str) -> str:
    """Token = sha256(hid + faskey) — dipakai saat fas_secure_enabled=1."""
    return hashlib.sha256((hid + FAS_KEY).encode()).hexdigest()

# ══════════════════════════════════════════════════════
#  GENERATE CHALLENGE — via Groq
# ══════════════════════════════════════════════════════

CATEGORY_PROMPTS = {
    'general': (
        'pertanyaan umum menarik seputar pengetahuan Indonesia dalam Bahasa Indonesia. '
        'Pilih secara acak dari: tokoh pahlawan, Pancasila, kemerdekaan, '
        'kerajaan nusantara, nama daerah/provinsi/suku, peristiwa perang & penjajahan. '
        'Buat soal tidak terlalu sulit, bisa dijawab dalam 10-30 detik. '
        'Satu jawaban yang jelas dan pasti.'
    ),
    'tebak': (
        'soal tebak-tebakan matematika dengan permainan kata dalam Bahasa Indonesia. '
        'Gabungkan operasi hitung sederhana (penjumlahan, pengurangan, '
        'perkalian, pembagian) dengan narasi cerita lucu. '
        'Angka kecil, hasil maksimal 3 digit. Gunakan nama lucu secara acak: '
        '[Bu Ejleg, Toglek, Perod, Satiyem, Neng Pitik]. '
        'DILARANG pakai nama Kendo. '
        'PENTING: field "answer" di JSON WAJIB string, bukan integer.'
    ),
    'religi': (
        'soal seputar agama Islam/kristen/hindu/budha  dalam Bahasa Indonesia. '
        'Pilih acak dari: Fiqih (thaharah, shalat, zakat, puasa, haji), '
        'Hari Besar Islam, Sejarah Nabi, Ilmu Tajwid, Ilmu Nahwu & Shorof. '
        'Buat soal yang jelas, tidak ambigu, cocok untuk muslim umum. '
        'Satu jawaban yang pasti.'
    ),
}

def generate_challenge(mac: str, category: str = 'general') -> dict:
    """Generate soal quiz via Groq AI."""
    if category not in CATEGORY_PROMPTS:
        category = 'general'
    cat_desc = CATEGORY_PROMPTS[category]

    try:
        response = groq_client.chat.completions.create(
            model='llama-3.1-8b-instant',
            max_tokens=400,
            temperature=0.92,
            messages=[
                {
                    'role': 'system',
                    'content': (
                        f'Kamu adalah AI penjaga gerbang WiFi yang lucu dan kreatif.\n'
                        f'Buat 1 soal dengan ketentuan berikut:\n{cat_desc}\n\n'
                        f'Syarat tambahan:\n'
                        f'- Bisa dijawab 10-30 detik\n'
                        f'- Satu jawaban yang jelas dan pasti\n'
                        f'- Segar, tidak pasaran\n\n'
                        'Balas HANYA JSON:\n'
                        '{"question":"...","answer":"...","hint":"...",'
                        f'"category":"{category}",'
                        '"fun_wrong":"komentar lucu jika salah (maks 10 kata)",'
                        '"fun_correct":"komentar seru jika benar (maks 10 kata)"}'
                    )
                },
                {
                    'role': 'user',
                    'content': f'Buat 1 soal untuk captive portal WiFi kategori {category}!'
                }
            ],
            response_format={'type': 'json_object'}
        )
        d    = json.loads(response.choices[0].message.content)
        sess = {
            'question':    d.get('question', ''),
            'answer':      str(d.get('answer', '')).lower().strip(),
            'hint':        d.get('hint', ''),
            'category':    category,
            'fun_wrong':   d.get('fun_wrong',   'Salah! Coba lagi 😅'),
            'fun_correct': d.get('fun_correct', 'Benar! Selamat! 🎉'),
            'attempts':    0,
            'created_at':  time.time(),
        }
        challenge_sessions[mac] = sess
        logger.info(f'[Challenge] mac={mac} cat={category} q={sess["question"][:60]}')
        return {
            'ok':       True,
            'question': sess['question'],
            'hint':     sess['hint'],
            'category': sess['category'],
        }
    except Exception as e:
        logger.error(f'[Challenge ERROR] {e}')
        return {'ok': False, 'error': f'Gagal menghubungi AI: {str(e)}'}

# ══════════════════════════════════════════════════════
#  VALIDATE ANSWER
# ══════════════════════════════════════════════════════

def validate_answer(mac: str, user_answer: str) -> dict:
    sess = challenge_sessions.get(mac)
    if sess is None:
        return {'correct': False, 'msg': 'Sesi tidak ditemukan. Muat ulang halaman.'}

    ua = user_answer.strip().lower()
    ca = sess['answer'].strip().lower()

    if len(ua) < 1:
        return {'correct': False, 'msg': sess['fun_wrong']}

    # Fast-path: exact match atau jawaban benar ada di jawaban user (word boundary)
    ca_pattern = re.compile(r'\b' + re.escape(ca) + r'\b', re.IGNORECASE)
    if ua == ca or ca_pattern.search(ua):
        logger.info(f'[Validate FAST] correct mac={mac}')
        return {'correct': True, 'msg': sess['fun_correct']}

    # AI validation — toleransi sinonim, ejaan alternatif
    try:
        resp = groq_client.chat.completions.create(
            model='llama-3.1-8b-instant',
            max_tokens=60,
            temperature=0.1,
            messages=[
                {
                    'role': 'system',
                    'content': (
                        'Nilai jawaban kuis. Toleransi ejaan alternatif, sinonim, singkatan. '
                        'TOLAK jawaban tidak relevan atau asal-asalan. '
                        'Balas HANYA JSON: {"correct": true/false}'
                    )
                },
                {
                    'role': 'user',
                    'content': (
                        f'Pertanyaan: "{sess["question"]}"\n'
                        f'Jawaban benar: "{sess["answer"]}"\n'
                        f'Jawaban user: "{user_answer}"\n'
                        f'Apakah jawaban user benar?'
                    )
                }
            ],
            response_format={'type': 'json_object'}
        )
        is_correct = bool(
            json.loads(resp.choices[0].message.content).get('correct', False)
        )
        logger.info(f'[Validate AI] correct={is_correct} mac={mac}')
        return {
            'correct': is_correct,
            'msg': sess['fun_correct'] if is_correct else sess['fun_wrong']
        }
    except Exception as e:
        logger.error(f'[Validate ERROR] {e}')
        exact = (ua == ca)
        return {
            'correct': exact,
            'msg': sess['fun_correct'] if exact else sess['fun_wrong']
        }

# ══════════════════════════════════════════════════════
#  ROUTES — PORTAL OPENNDS
# ══════════════════════════════════════════════════════

@app.route('/portal')
def portal():
    """
    Entry point dari openNDS redirect.
    Mode 1 (fas_secure_enabled=1): ?fas=<base64>
    Mode 2 (fas_secure_enabled=0): ?tok=&redir=&mac=&ip=&authdir=&gatewayaddress=
    """
    fas_b64 = request.args.get('fas', '')

    if fas_b64:
        # ── Mode 1 ──
        params         = parse_fas_query(fas_b64)
        hid            = params.get('hid', '')
        clientip       = params.get('clientip', '')
        clientmac      = params.get('clientmac', '')
        gatewayname    = urllib.parse.unquote(params.get('gatewayname', 'WiFi Hotspot'))
        gatewayaddress = params.get('gatewayaddress', GATEWAY_FALLBACK)
        redir          = params.get('originurl') or params.get('redir', 'http://www.google.com')
        tok            = compute_token(hid) if hid else ''
        session_key    = hid or clientmac
    else:
        # ── Mode 2 ──
        tok            = request.args.get('tok', '')
        redir          = request.args.get('redir', 'http://www.google.com')
        clientip       = request.args.get('ip', '')
        clientmac      = request.args.get('mac', '')
        gatewayname    = urllib.parse.unquote(request.args.get('gatewayname', 'WiFi Hotspot'))
        gatewayaddress = request.args.get('gatewayaddress', '') or GATEWAY_FALLBACK
        session_key    = clientmac

    logger.info(
        f'[Portal] ip={clientip} mac={clientmac} '
        f'gw={gatewayaddress} tok={"YES" if tok else "MISSING"}'
    )

    # Simpan ke Flask session
    flask_session.clear()
    flask_session['tok']            = tok
    flask_session['redir']          = redir
    flask_session['gatewayaddress'] = gatewayaddress
    flask_session['session_key']    = session_key
    flask_session['correct_count']  = 0

    # Buat/reset portal chat session
    sid = str(uuid.uuid4())
    now = int(time.time())
    with get_db() as conn:
        conn.execute(
            'INSERT INTO portal_sessions (id, mac, created_at, updated_at) VALUES (?,?,?,?)',
            (sid, clientmac, now, now)
        )
        conn.commit()
    flask_session['chat_sid'] = sid
    portal_histories[sid]    = []   # fresh history

    client_info = {
        'ip':      clientip,
        'mac':     clientmac,
        'gateway': gatewayname,
        'time':    __import__('datetime').datetime.now().strftime('%H:%M:%S'),
    }
    return render_template(
        'portal.html',
        client_info=client_info,
        required_correct=REQUIRED_CORRECT
    )


@app.route('/portal/challenge', methods=['GET'])
def portal_challenge():
    category    = request.args.get('category', 'general')
    session_key = flask_session.get('session_key', 'unknown')
    result      = generate_challenge(session_key, category)
    return jsonify(result)


@app.route('/portal/verify', methods=['POST'])
def portal_verify():
    data        = request.get_json() or {}
    user_answer = str(data.get('answer', '')).strip()
    session_key = flask_session.get('session_key', '')

    if not user_answer:
        return jsonify({'ok': False, 'msg': 'Jawaban tidak boleh kosong!', 'correct': False})

    if session_key not in challenge_sessions:
        return jsonify({
            'ok': False,
            'msg': 'Sesi tidak ditemukan. Muat ulang halaman.',
            'reload': True
        })

    sess = challenge_sessions[session_key]
    sess['attempts'] += 1
    result = validate_answer(session_key, user_answer)

    if result['correct']:
        flask_session['correct_count'] = flask_session.get('correct_count', 0) + 1
        correct_count = flask_session['correct_count']
        authenticated = correct_count >= REQUIRED_CORRECT
        redirect_url  = None

        if authenticated:
            tok            = flask_session.get('tok', '')
            redir          = flask_session.get('redir', 'http://www.google.com')
            gatewayaddress = flask_session.get('gatewayaddress', '') or GATEWAY_FALLBACK

            if tok:
                redirect_url = (
                    f"http://{gatewayaddress}/{NDS_AUTHDIR}/"
                    f"?tok={urllib.parse.quote(tok, safe='')}"
                    f"&redir={urllib.parse.quote(redir, safe='')}"
                )
                logger.info(f'[Auth] Authenticated! redirect_url={redirect_url}')
            else:
                logger.error('[Auth] tok MISSING — cek konfigurasi openNDS fas_secure_enabled')

            challenge_sessions.pop(session_key, None)
            flask_session.clear()

        return jsonify({
            'ok':            True,
            'correct':       True,
            'msg':           result['msg'],
            'authenticated': authenticated,
            'correct_count': correct_count,
            'required':      REQUIRED_CORRECT,
            'redirect_url':  redirect_url,
        })

    # ── Jawaban salah ──
    hint = ''
    if sess['attempts'] >= 2:
        hint = f"💡 Petunjuk: {sess['hint']}"

    if sess['attempts'] >= 5:
        challenge_sessions.pop(session_key, None)
        return jsonify({
            'ok': True, 'correct': False,
            'msg': 'Batas 5x salah! Soal diganti otomatis.',
            'hint': '', 'reset': True
        })

    return jsonify({
        'ok':      True,
        'correct': False,
        'msg':     result['msg'],
        'hint':    hint,
        'attempts': sess['attempts'],
    })


@app.route('/portal/skip', methods=['POST'])
def portal_skip():
    session_key = flask_session.get('session_key', '')
    challenge_sessions.pop(session_key, None)
    return jsonify({'ok': True})


# ══════════════════════════════════════════════════════
#  ROUTE — /chat  (Chatbot Kendo khusus portal)
# ══════════════════════════════════════════════════════

@app.route('/chat', methods=['POST'])
def chat():
    """Endpoint chat khusus portal — pakai karakter Kendo."""
    data    = request.get_json(silent=True) or {}
    message = data.get('message', '').strip()
    model   = data.get('model', 'moonshotai/kimi-k2-instruct-0905')
    # Izinkan override system prompt dari client, fallback ke Kendo
    system  = data.get('system', KENDO_SYSTEM)

    if not message:
        return jsonify({'reply': 'Eh, ngomong dong... 😑'}), 200

    sid     = flask_session.get('chat_sid', 'unknown')
    history = get_or_create_portal_history(sid)

    # Simpan ke DB
    now = int(time.time())
    with get_db() as conn:
        conn.execute(
            'INSERT INTO portal_messages (session_id, role, content, created_at) VALUES (?,?,?,?)',
            (sid, 'user', message, now)
        )
        conn.execute(
            'UPDATE portal_sessions SET updated_at=? WHERE id=?', (now, sid)
        )
        conn.commit()

    with _history_lock:
        history.append({'role': 'user', 'content': message})

    try:
        resp = groq_client.chat.completions.create(
            model=model,
            messages=[{'role': 'system', 'content': system}, *history[-10:]]
        )
        reply = resp.choices[0].message.content
        # Hapus internal thinking jika ada (Qwen3, dll)
        reply = re.sub(r'<think>[\s\S]*?</think>', '', reply, flags=re.IGNORECASE).strip()

        with _history_lock:
            history.append({'role': 'assistant', 'content': reply})

        # Simpan reply ke DB
        with get_db() as conn:
            conn.execute(
                'INSERT INTO portal_messages (session_id, role, content, created_at) VALUES (?,?,?,?)',
                (sid, 'assistant', reply, int(time.time()))
            )
            conn.commit()

        logger.info(f'[Chat] sid={sid} msg={message[:40]!r}')
        return jsonify({'reply': reply})

    except Exception as e:
        logger.error(f'[Chat ERROR] {e}')
        return jsonify({'reply': 'Aduh error nih... coba lagi ya 😑'}), 200


# ══════════════════════════════════════════════════════
#  ROUTE — Health check
# ══════════════════════════════════════════════════════

@app.route('/health')
def health():
    return jsonify({
        'status':   'ok',
        'service':  'portal',
        'port':     PORT,
        'db':       DB_PATH,
    })


# ══════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════

if __name__ == '__main__':
    logger.info(f'🚀 Portal App starting on port {PORT}')
    logger.info(f'   FAS_KEY        : {FAS_KEY[:4]}{"*" * (len(FAS_KEY)-4)}')
    logger.info(f'   GATEWAY_FALLBACK: {GATEWAY_FALLBACK}')
    logger.info(f'   REQUIRED_CORRECT: {REQUIRED_CORRECT}')
    logger.info(f'   DB_PATH         : {DB_PATH}')
    app.run(
        host='0.0.0.0',
        port=PORT,
        debug=False,
        threaded=True,
    )
