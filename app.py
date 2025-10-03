# ==============================================================================
# app.py - V4.3 KORREKT & KOMPLET
# ==============================================================================
import os
import re
import requests
import subprocess
import traceback
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from flask_bcrypt import Bcrypt
from sqlalchemy import desc

# --- KONFIGURATION ---
TMDB_API_KEY = "b3edf66f42b954dc3b97074aa9bec670"

if TMDB_API_KEY == "DIN_TMDB_API_NØGLE_HER":
    print("\n\n!!! ADVARSEL: Du mangler at indsætte din TMDB API-nøgle i app.py !!!\n\n")

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
USER_MEDIA_LIMIT = 100

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = "Du skal være logget ind for at se denne side."

# --- DATABASE MODELLER ---
@login_manager.user_loader
def load_user(user_id): return User.query.get(int(user_id))

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(60), nullable=False)

class Movie(db.Model):
    id = db.Column(db.Integer, primary_key=True); user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False); title = db.Column(db.String(200), nullable=False); overview = db.Column(db.Text); poster_path = db.Column(db.String(200)); release_year = db.Column(db.Integer); duration = db.Column(db.Float, default=0.0); server_path = db.Column(db.String(300), unique=True, nullable=False); date_added = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

class TVShow(db.Model):
    id = db.Column(db.Integer, primary_key=True); user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False); tmdb_id = db.Column(db.Integer, nullable=False); title = db.Column(db.String(200), nullable=False); overview = db.Column(db.Text); poster_path = db.Column(db.String(200)); episodes = db.relationship('Episode', backref='show', lazy='dynamic', cascade="all, delete-orphan"); __table_args__ = (db.UniqueConstraint('user_id', 'tmdb_id', name='_user_show_uc'),)

class Episode(db.Model):
    id = db.Column(db.Integer, primary_key=True); show_id = db.Column(db.Integer, db.ForeignKey('tv_show.id'), nullable=False); season_number = db.Column(db.Integer, nullable=False); episode_number = db.Column(db.Integer, nullable=False); title = db.Column(db.String(200), nullable=False); duration = db.Column(db.Float, default=0.0); server_path = db.Column(db.String(300), unique=True, nullable=False); date_added = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

class UserProgress(db.Model):
    id = db.Column(db.Integer, primary_key=True); user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False); media_type = db.Column(db.String(50), nullable=False); media_id = db.Column(db.Integer, nullable=False); resume_position = db.Column(db.Float, default=0.0); is_watched = db.Column(db.Boolean, default=False); last_watched = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow); __table_args__ = (db.UniqueConstraint('user_id', 'media_type', 'media_id', name='_user_media_uc'),)

# ==============================================================================
# == HJÆLPEFUNKTIONER (ALLE SAMLET HER FOR AT UNDGÅ FEJL)
# ==============================================================================
def get_media_info_from_filename(filename):
    clean_name = os.path.splitext(filename)[0].replace('.', ' ').replace('_', ' ')
    series_match = re.search(r'(.*?)[sS](\d{1,2})[eE](\d{1,2})', clean_name, re.IGNORECASE)
    if series_match:
        return {'type': 'episode', 'show_name': series_match.group(1).strip(), 'season': int(series_match.group(2)), 'episode': int(series_match.group(3))}
    year_match = re.search(r'\b(19\d{2}|20\d{2})\b', clean_name)
    year = year_match.group(1) if year_match else None
    title = clean_name[:year_match.start()].strip() if year_match else clean_name
    return {'type': 'movie', 'title': title, 'year': year}

def get_video_duration(filepath):
    try:
        command = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', filepath]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except Exception as e:
        print(f"Kunne ikke finde varighed for {filepath}: {e}")
        return 0.0

def get_tmdb_data(url):
    try:
        response = requests.get(url, timeout=5) # Timeout på 5 sekunder
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"TMDB fejl: {e}")
        return None

def generate_file_chunks(path, start, length, chunk_size=1024*1024):
    with open(path, 'rb') as f:
        f.seek(start)
        bytes_left = length
        while bytes_left > 0:
            data = f.read(min(chunk_size, bytes_left))
            if not data: break
            bytes_left -= len(data)
            yield data
# ==============================================================================

# --- HOVEDRUTER ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/library')
@login_required
def library():
    movie_count = Movie.query.filter_by(user_id=current_user.id).count()
    episode_count = Episode.query.join(TVShow).filter(TVShow.user_id == current_user.id).count()
    current_file_count = movie_count + episode_count
    
    in_progress_movies = db.session.query(Movie, UserProgress).join(UserProgress, (Movie.id == UserProgress.media_id) & (UserProgress.media_type == 'movie')).filter(UserProgress.user_id == current_user.id, UserProgress.is_watched == False, UserProgress.resume_position > 30).all()
    in_progress_episodes = db.session.query(Episode, UserProgress).join(UserProgress, (Episode.id == UserProgress.media_id) & (UserProgress.media_type == 'episode')).filter(UserProgress.user_id == current_user.id, UserProgress.is_watched == False, UserProgress.resume_position > 30).all()
    continue_watching_items = sorted(in_progress_movies + in_progress_episodes, key=lambda x: x[1].last_watched, reverse=True)
    
    recently_added_movies = Movie.query.filter_by(user_id=current_user.id).order_by(desc(Movie.date_added)).limit(20).all()
    recently_added_shows = TVShow.query.filter_by(user_id=current_user.id).order_by(desc(TVShow.id)).limit(20).all()
    
    all_movies = Movie.query.filter_by(user_id=current_user.id).all()
    all_tv_shows = TVShow.query.filter_by(user_id=current_user.id).order_by(TVShow.title).all()

    return render_template('library.html', current_file_count=current_file_count, limit=USER_MEDIA_LIMIT, continue_watching=continue_watching_items, recently_added_movies=recently_added_movies, recently_added_shows=recently_added_shows, all_movies=all_movies, all_tv_shows=all_tv_shows)

# --- BRUGER- OG API-RUTER ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('library'))
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user and bcrypt.check_password_hash(user.password_hash, request.form.get('password')):
            login_user(user, remember=True); return redirect(url_for('library'))
        else: flash('Login mislykkedes.', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated: return redirect(url_for('library'))
    if request.method == 'POST':
        if User.query.filter_by(username=request.form.get('username')).first():
            flash('Brugernavn er allerede taget.', 'danger'); return redirect(url_for('register'))
        hashed_password = bcrypt.generate_password_hash(request.form.get('password')).decode('utf-8')
        db.session.add(User(username=request.form.get('username'), password_hash=hashed_password)); db.session.commit()
        flash('Konto oprettet! Du kan nu logge ind.', 'success'); return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    logout_user(); return redirect(url_for('index'))

@app.route('/api/check_upload_limit', methods=['GET'])
@login_required
def check_upload_limit():
    movie_count = Movie.query.filter_by(user_id=current_user.id).count()
    episode_count = Episode.query.join(TVShow).filter(TVShow.user_id == current_user.id).count()
    if (movie_count + episode_count) >= USER_MEDIA_LIMIT: return jsonify({'error': f'Du har nået din grænse på {USER_MEDIA_LIMIT} filer.'}), 403
    return jsonify({'success': 'Klar til upload'}), 200

@app.route('/upload_chunk', methods=['POST'])
@login_required
def upload_chunk():
    try:
        file_chunk = request.files['file']; upload_id = request.form['uploadId']; original_filename = request.form['originalFilename']
        user_upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], str(current_user.id)); os.makedirs(user_upload_dir, exist_ok=True)
        temp_path = os.path.join(user_upload_dir, f"{upload_id}_{secure_filename(original_filename)}.part")
        with open(temp_path, 'ab') as f: f.write(file_chunk.read())
        return jsonify({'success': 'Chunk modtaget'}), 200
    except Exception as e:
        print(f"Fejl: {e}"); traceback.print_exc()
        return jsonify({'error': f'Serverfejl: {str(e)}'}), 500

@app.route('/finalize_upload', methods=['POST'])
@login_required
def finalize_upload():
    temp_path = None
    try:
        movie_count = Movie.query.filter_by(user_id=current_user.id).count()
        episode_count = Episode.query.join(TVShow).filter(TVShow.user_id == current_user.id).count()
        if (movie_count + episode_count) >= USER_MEDIA_LIMIT: return jsonify({'error': f'Du har nået din grænse på {USER_MEDIA_LIMIT} filer.'}), 403
        
        upload_id = request.json['uploadId']; original_filename = request.json['originalFilename']
        user_upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], str(current_user.id))
        temp_path = os.path.join(user_upload_dir, f"{upload_id}_{secure_filename(original_filename)}.part")
        final_path = os.path.join(user_upload_dir, secure_filename(original_filename))
        if not os.path.exists(temp_path): return jsonify({'error': 'Midlertidig fil ikke fundet.'}), 404
        
        subprocess.run(['ffmpeg', '-i', temp_path, '-c', 'copy', '-movflags', '+faststart', '-y', final_path], check=True, capture_output=True, text=True)
        duration = get_video_duration(final_path)
        media_info = get_media_info_from_filename(original_filename)

        if media_info['type'] == 'movie':
            url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={media_info['title']}&language=da-DK"
            if media_info['year']: url += f"&year={media_info['year']}"
            data = get_tmdb_data(url); details = data['results'][0] if data and data['results'] else {}
            new_movie = Movie(user_id=current_user.id, title=details.get('title', media_info['title']), overview=details.get('overview'), poster_path=f"https://image.tmdb.org/t/p/w500{details.get('poster_path')}" if details.get('poster_path') else None, release_year=int(details.get('release_date', '0-0-0').split('-')[0]) if details.get('release_date') else None, duration=duration, server_path=final_path)
            db.session.add(new_movie)
        elif media_info['type'] == 'episode':
            show_url = f"https://api.themoviedb.org/3/search/tv?api_key={TMDB_API_KEY}&query={media_info['show_name']}&language=da-DK"
            show_data = get_tmdb_data(show_url)
            if not show_data or not show_data['results']: return jsonify({'error': f"Kunne ikke finde TV-serien '{media_info['show_name']}'."}), 404
            show_details = show_data['results'][0]; tmdb_id = show_details['id']
            show = TVShow.query.filter_by(user_id=current_user.id, tmdb_id=tmdb_id).first()
            if not show:
                show = TVShow(user_id=current_user.id, tmdb_id=tmdb_id, title=show_details.get('name'), overview=show_details.get('overview'), poster_path=f"https://image.tmdb.org/t/p/w500{show_details.get('poster_path')}" if show_details.get('poster_path') else None)
                db.session.add(show); db.session.flush()
            episode_url = f"https://api.themoviedb.org/3/tv/{tmdb_id}/season/{media_info['season']}/episode/{media_info['episode']}?api_key={TMDB_API_KEY}&language=da-DK"
            episode_details = get_tmdb_data(episode_url) or {}
            new_episode = Episode(show_id=show.id, season_number=media_info['season'], episode_number=media_info['episode'], title=episode_details.get('name', f"Afsnit {media_info['episode']}"), duration=duration, server_path=final_path)
            db.session.add(new_episode)
        
        db.session.commit()
        return jsonify({'success': 'Filen er færdigbehandlet!'})
    except Exception as e:
        db.session.rollback(); print(f"Fejl: {e}"); traceback.print_exc()
        return jsonify({'error': f'En intern serverfejl opstod: {str(e)}'}), 500
    finally:
        if temp_path and os.path.exists(temp_path): os.remove(temp_path)

@app.route('/api/tvshows/<int:show_id>/episodes')
@login_required
def get_episodes(show_id):
    show = TVShow.query.get_or_404(show_id)
    if show.user_id != current_user.id: return jsonify({'error': 'Adgang nægtet'}), 403
    episodes = db.session.query(Episode, UserProgress).outerjoin(UserProgress, (Episode.id == UserProgress.media_id) & (UserProgress.media_type == 'episode') & (UserProgress.user_id == current_user.id)).filter(Episode.show_id == show_id).order_by(Episode.season_number, Episode.episode_number).all()
    episodes_data = [{'id': ep.id, 'title': ep.title, 's_num': ep.season_number, 'e_num': ep.episode_number, 'duration': ep.duration, 'resume_pos': progress.resume_position if progress else 0, 'is_watched': progress.is_watched if progress else False} for ep, progress in episodes]
    return jsonify(episodes_data)

@app.route('/stream/<media_type>/<int:media_id>')
@login_required
def stream(media_type, media_id):
    model = Movie if media_type == 'movie' else Episode
    media = model.query.get_or_404(media_id)
    owner_id = media.user_id if media_type == 'movie' else media.show.user_id
    if owner_id != current_user.id: return "Adgang nægtet", 403
    path = media.server_path
    range_header = request.headers.get('Range', None)
    if not os.path.exists(path): return "Fil ikke fundet", 404
    file_size = os.path.getsize(path)
    if not range_header: return Response(generate_file_chunks(path, 0, file_size), mimetype='video/mp4', headers={'Content-Length': str(file_size)})
    byte1, byte2 = 0, None; m = re.search(r'(\d+)-(\d*)', range_header); g = m.groups()
    if g[0]: byte1 = int(g[0])
    if g[1]: byte2 = int(g[1])
    start = byte1; end = byte2 if byte2 is not None else file_size - 1
    length = end - start + 1
    response = Response(generate_file_chunks(path, start, length), 206, mimetype='video/mp4')
    response.headers.add('Content-Range', f'bytes {start}-{end}/{file_size}'); response.headers.add('Accept-Ranges', 'bytes'); response.headers.add('Content-Length', str(length))
    return response

@app.route('/delete/<media_type>/<int:media_id>', methods=['POST'])
@login_required
def delete_media(media_type, media_id):
    model = Movie if media_type == 'movie' else Episode
    media = model.query.get_or_404(media_id)
    owner_id = media.user_id if media_type == 'movie' else media.show.user_id
    if owner_id != current_user.id: return jsonify({'error': 'Adgang nægtet'}), 403
    try:
        UserProgress.query.filter_by(media_id=media_id, media_type=media_type, user_id=current_user.id).delete()
        show_to_delete = None
        if media_type == 'episode':
            show = media.show
            if len(show.episodes.all()) == 1: show_to_delete = show
        if os.path.exists(media.server_path): os.remove(media.server_path)
        db.session.delete(media)
        if show_to_delete: db.session.delete(show_to_delete)
        db.session.commit()
        return jsonify({'success': 'Slettet!'})
    except Exception as e:
        db.session.rollback(); print(f"Fejl ved sletning: {e}")
        return jsonify({'error': 'Fejl under sletning.'}), 500

@app.route('/api/progress/<media_type>/<int:media_id>', methods=['POST'])
@login_required
def save_progress(media_type, media_id):
    time = request.json.get('time'); model = Movie if media_type == 'movie' else Episode
    media_item = model.query.get(media_id)
    if time is None or not media_item: return jsonify({'error': 'Manglende data'}), 400
    progress = UserProgress.query.filter_by(user_id=current_user.id, media_type=media_type, media_id=media_id).first()
    if not progress:
        progress = UserProgress(user_id=current_user.id, media_type=media_type, media_id=media_id)
        db.session.add(progress)
    progress.resume_position = time
    progress.is_watched = (time / media_item.duration) > 0.95 if media_item.duration > 0 else False
    db.session.commit()
    return jsonify({'success': True})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0')