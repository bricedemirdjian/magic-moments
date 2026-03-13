import os
import json
import sqlite3
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, session, request, jsonify, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from authlib.integrations.flask_client import OAuth
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import uuid

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
app.config['PREFERRED_URL_SCHEME'] = 'https'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = {'mp4', 'mov', 'avi', 'mkv', 'webm'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Google OAuth
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.environ.get('GOOGLE_CLIENT_ID'),
    client_secret=os.environ.get('GOOGLE_CLIENT_SECRET'),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'},
)

# Database
DB_PATH = os.path.join(os.path.dirname(__file__), 'magic_moments.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            google_id TEXT UNIQUE NOT NULL,
            email TEXT NOT NULL,
            name TEXT NOT NULL,
            picture TEXT,
            plan TEXT DEFAULT 'free',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            status TEXT DEFAULT 'draft',
            video_filename TEXT,
            video_url TEXT,
            subtitles_json TEXT DEFAULT '[]',
            caption_style TEXT DEFAULT 'classic',
            duration REAL DEFAULT 0,
            views INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS clips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            start_time REAL NOT NULL,
            end_time REAL NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id)
        );
    ''')
    conn.commit()
    conn.close()


init_db()


# User model
class User(UserMixin):
    def __init__(self, id, google_id, email, name, picture, plan, created_at):
        self.id = id
        self.google_id = google_id
        self.email = email
        self.name = name
        self.picture = picture
        self.plan = plan
        self.created_at = created_at


@login_manager.user_loader
def load_user(user_id):
    conn = get_db()
    row = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    if row:
        return User(**dict(row))
    return None


# ========== PUBLIC ROUTES ==========

@app.route('/')
def index():
    return render_template('index.html', user=current_user if current_user.is_authenticated else None)


@app.route('/login')
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('login.html')


@app.route('/auth/google')
def auth_google():
    redirect_uri = url_for('auth_google_callback', _external=True)
    return google.authorize_redirect(redirect_uri)


@app.route('/auth/google/callback')
def auth_google_callback():
    try:
        token = google.authorize_access_token()
        user_info = token.get('userinfo')
        if not user_info:
            user_info = google.get('https://www.googleapis.com/oauth2/v3/userinfo').json()

        google_id = user_info['sub']
        email = user_info['email']
        name = user_info.get('name', email.split('@')[0])
        picture = user_info.get('picture', '')

        conn = get_db()
        existing = conn.execute('SELECT * FROM users WHERE google_id = ?', (google_id,)).fetchone()

        if existing:
            conn.execute('UPDATE users SET name = ?, picture = ? WHERE google_id = ?',
                         (name, picture, google_id))
            conn.commit()
            user = User(**dict(conn.execute('SELECT * FROM users WHERE google_id = ?', (google_id,)).fetchone()))
        else:
            conn.execute('INSERT INTO users (google_id, email, name, picture) VALUES (?, ?, ?, ?)',
                         (google_id, email, name, picture))
            conn.commit()
            user = User(**dict(conn.execute('SELECT * FROM users WHERE google_id = ?', (google_id,)).fetchone()))

        conn.close()
        login_user(user)
        return redirect(url_for('dashboard'))

    except Exception as e:
        print(f"Auth error: {e}")
        flash("Erreur de connexion. Réessayez.", "error")
        return redirect(url_for('login'))


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


# ========== DASHBOARD ROUTES ==========

@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db()
    projects = conn.execute(
        'SELECT * FROM projects WHERE user_id = ? ORDER BY updated_at DESC', (current_user.id,)
    ).fetchall()
    conn.close()

    stats = {
        'total_projects': len(projects),
        'published': sum(1 for p in projects if p['status'] == 'published'),
        'total_views': sum(p['views'] for p in projects),
        'draft': sum(1 for p in projects if p['status'] == 'draft'),
    }

    return render_template('dashboard.html', user=current_user, projects=projects, stats=stats)


@app.route('/project/new', methods=['GET', 'POST'])
@login_required
def new_project():
    if request.method == 'POST':
        title = request.form.get('title', 'Sans titre')
        video_filename = None
        video_url = None

        # Handle video file upload
        if 'video' in request.files:
            file = request.files['video']
            if file and file.filename and allowed_file(file.filename):
                ext = file.filename.rsplit('.', 1)[1].lower()
                unique_name = f"{uuid.uuid4().hex}.{ext}"
                filepath = os.path.join(UPLOAD_FOLDER, unique_name)
                file.save(filepath)
                video_filename = unique_name
                video_url = url_for('static', filename=f'uploads/{unique_name}')
                title = file.filename.rsplit('.', 1)[0]

        conn = get_db()
        conn.execute(
            'INSERT INTO projects (user_id, title, video_filename, video_url) VALUES (?, ?, ?, ?)',
            (current_user.id, title, video_filename, video_url)
        )
        conn.commit()
        project = conn.execute(
            'SELECT * FROM projects WHERE user_id = ? ORDER BY id DESC LIMIT 1', (current_user.id,)
        ).fetchone()
        conn.close()
        return redirect(url_for('editor', project_id=project['id']))

    return render_template('new_project.html', user=current_user)


@app.route('/editor/<int:project_id>')
@login_required
def editor(project_id):
    conn = get_db()
    project = conn.execute(
        'SELECT * FROM projects WHERE id = ? AND user_id = ?', (project_id, current_user.id)
    ).fetchone()
    conn.close()

    if not project:
        flash("Projet introuvable.", "error")
        return redirect(url_for('dashboard'))

    subtitles = json.loads(project['subtitles_json']) if project['subtitles_json'] else []
    return render_template('editor.html', user=current_user, project=project, subtitles=subtitles)


@app.route('/api/project/<int:project_id>/subtitles', methods=['POST'])
@login_required
def save_subtitles(project_id):
    conn = get_db()
    project = conn.execute(
        'SELECT * FROM projects WHERE id = ? AND user_id = ?', (project_id, current_user.id)
    ).fetchone()
    if not project:
        return jsonify({'error': 'Not found'}), 404

    data = request.json
    conn.execute(
        'UPDATE projects SET subtitles_json = ?, caption_style = ?, updated_at = ? WHERE id = ?',
        (json.dumps(data.get('subtitles', [])), data.get('style', 'classic'), datetime.now(), project_id)
    )
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/project/<int:project_id>/status', methods=['POST'])
@login_required
def update_project_status(project_id):
    conn = get_db()
    project = conn.execute(
        'SELECT * FROM projects WHERE id = ? AND user_id = ?', (project_id, current_user.id)
    ).fetchone()
    if not project:
        return jsonify({'error': 'Not found'}), 404

    data = request.json
    conn.execute(
        'UPDATE projects SET status = ?, updated_at = ? WHERE id = ?',
        (data.get('status', 'draft'), datetime.now(), project_id)
    )
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/project/<int:project_id>', methods=['DELETE'])
@login_required
def delete_project(project_id):
    conn = get_db()
    conn.execute('DELETE FROM projects WHERE id = ? AND user_id = ?', (project_id, current_user.id))
    conn.execute('DELETE FROM clips WHERE project_id = ?', (project_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/project/<int:project_id>/clips', methods=['POST'])
@login_required
def generate_clips(project_id):
    conn = get_db()
    project = conn.execute(
        'SELECT * FROM projects WHERE id = ? AND user_id = ?', (project_id, current_user.id)
    ).fetchone()
    if not project:
        return jsonify({'error': 'Not found'}), 404

    # Simulated AI clip generation
    duration = project['duration'] or 60
    clips = []
    clip_duration = 15
    for i in range(0, int(duration), int(clip_duration * 2)):
        end = min(i + clip_duration, duration)
        conn.execute(
            'INSERT INTO clips (project_id, title, start_time, end_time, status) VALUES (?, ?, ?, ?, ?)',
            (project_id, f'Clip {len(clips) + 1}', i, end, 'ready')
        )
        clips.append({'start': i, 'end': end, 'title': f'Clip {len(clips) + 1}'})

    conn.commit()
    all_clips = conn.execute('SELECT * FROM clips WHERE project_id = ?', (project_id,)).fetchall()
    conn.close()
    return jsonify({'clips': [dict(c) for c in all_clips]})


@app.route('/settings')
@login_required
def settings():
    return render_template('settings.html', user=current_user)


@app.route('/magic-clips')
@login_required
def magic_clips():
    conn = get_db()
    projects = conn.execute(
        'SELECT * FROM projects WHERE user_id = ? ORDER BY updated_at DESC', (current_user.id,)
    ).fetchall()
    conn.close()
    return render_template('magic_clips.html', user=current_user, projects=projects)


@app.route('/publish')
@login_required
def publish():
    conn = get_db()
    projects = conn.execute(
        "SELECT * FROM projects WHERE user_id = ? AND status IN ('ready', 'published') ORDER BY updated_at DESC",
        (current_user.id,)
    ).fetchall()
    conn.close()
    return render_template('publish.html', user=current_user, projects=projects)


if __name__ == '__main__':
    app.run(debug=True, port=8090)
