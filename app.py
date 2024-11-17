from flask import Flask, request, render_template, redirect, url_for, flash, session, jsonify, send_from_directory, abort
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin
import os
import sqlite3
from moviepy.editor import VideoFileClip
from models import db, User, Video, Comment, VideoAction, Report, Ban, ChannelComment, Notification, VideoView, SiteSettings, Subscription, ModLog, IPBan
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import Table, or_, and_, func, case
import requests
from PIL import Image
import io
from flask_migrate import Migrate
import traceback
from faker import Faker
import random
from functools import wraps
from sqlalchemy import func
import ffmpeg
import os.path
import math
from flask_wtf import FlaskForm
from wtforms import TextAreaField, StringField, PasswordField
from wtforms.validators import DataRequired
from flask_cors import CORS
from dotenv import load_dotenv
import hashlib
import binascii
from alembic import op
import sqlalchemy as sa
import socket
from humanize import naturaltime
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from sqlalchemy.exc import OperationalError
import time
import warnings
from sqlalchemy.exc import SAWarning
import imghdr
import magic
import subprocess
import json
from urllib.error import URLError
from urllib.request import Request, urlopen
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_caching import Cache
import ipaddress
from werkzeug.serving import WSGIRequestHandler
import glob
import psutil
import platform
import flask
import os
import subprocess

warnings.filterwarnings('ignore', category=SAWarning)

load_dotenv()  

TEMP_UPLOAD_FOLDER = os.path.join('static', 'uploads', 'temp')
FINAL_UPLOAD_FOLDER = os.path.join('static', 'uploads', 'videos')

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024 * 1024  
app.config['MAX_CONTENT_PATH'] = None
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_POOL_SIZE'] = 10
app.config['SQLALCHEMY_POOL_TIMEOUT'] = 30
app.config['SQLALCHEMY_POOL_RECYCLE'] = 1800
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads', 'videos')
app.config['THUMBNAIL_FOLDER'] = os.path.join('static','uploads', 'videos', 'thumbnails')
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 31536000
app.config['SERVER_NAME'] = 'localhost:5000' # eğer domaininizde çalışıyorsanız burayı değiştirin
db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

migrate = Migrate(app, db)

cache = Cache(app, config={
    'CACHE_TYPE': 'simple',
    'CACHE_DEFAULT_TIMEOUT': 300
})

maintenance_mode = False
video_uploads_enabled = True

limiter = Limiter(
    app=app,
    key_func=get_remote_address,  
    storage_uri="memory://", 
    default_limits=["500 per day", "100 per hour"],
    storage_options={"queue_size": 5}  
)

active_visitors = set()

active_visitors_last_seen = {}

DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL')

class SSLRedirect:
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        proto = environ.get('HTTP_X_FORWARDED_PROTO', '')
        if proto == 'http':
            url = 'https://' + environ['HTTP_HOST'] + environ['PATH_INFO']
            if environ.get('QUERY_STRING'):
                url += '?' + environ['QUERY_STRING']

            start_response('301 Moved Permanently', [('Location', url)])
            return []

        return self.app(environ, start_response)

app.wsgi_app = SSLRedirect(app.wsgi_app)  
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1, x_for=1)  

app.config['SESSION_COOKIE_SECURE'] = True  
app.config['REMEMBER_COOKIE_SECURE'] = True  

WSGIRequestHandler.protocol_version = "HTTP/1.1"

def get_real_ip():
    """Gerçek IP adresini al ve VPN/proxy kontrolü yap"""
    ip = None
    if request.environ.get('HTTP_X_FORWARDED_FOR'):
        ip = request.environ['HTTP_X_FORWARDED_FOR'].split(',')[0]
    else:
        ip = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)

    try:
        ipaddress.ip_address(ip)
        return ip
    except ValueError:
        return request.remote_addr

@app.route("/get_my_ip", methods=["GET"])
def get_my_ip():
    return jsonify({
        'ip': get_real_ip(),
        'forwarded_for': request.environ.get('HTTP_X_FORWARDED_FOR'),
        'real_ip': request.environ.get('HTTP_X_REAL_IP'),
        'remote_addr': request.remote_addr
    }), 200

def is_vpn():
    try:
        ip = get_real_ip()

        ip = request.remote_addr

        checks = [
            check_ports(ip),
            check_dns_blacklist(ip),
            check_headers(),
            check_connection_type()
        ]

        return any(checks)

    except Exception as e:
        print(f"VPN kontrolü sırasında hata: {str(e)}")
        return False

def check_ports(ip):
    """Yaygın VPN portlarını kontrol et"""
    vpn_ports = [1194, 1723, 500, 4500, 1701]  
    for port in vpn_ports:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            result = sock.connect_ex((ip, port))
            sock.close()
            if result == 0:
                return True
        except:
            continue
    return False

def check_dns_blacklist(ip):
    """DNS karalistelerini kontrol et"""
    try:

        ip_parts = ip.split('.')
        reversed_ip = '.'.join(reversed(ip_parts))

        blacklists = [
            'zen.spamhaus.org',
            'dnsbl.sorbs.net',
            'bl.spamcop.net'
        ]

        for bl in blacklists:
            try:
                socket.gethostbyname(f'{reversed_ip}.{bl}')
                return True
            except:
                continue

        return False
    except:
        return False

def check_headers():
    """HTTP başlıklarını kontrol et"""
    suspicious_headers = [
        'HTTP_VIA',
        'VIA',
        'Proxy-Connection',
        'HTTP_X_FORWARDED_FOR',
        'HTTP_FORWARDED_FOR',
        'HTTP_X_FORWARDED',
        'HTTP_FORWARDED',
        'HTTP_CLIENT_IP',
        'HTTP_FORWARDED_FOR_IP',
        'X-PROXY-ID',
        'MT-PROXY-ID',
        'X-TINYPROXY',
        'X_FORWARDED_FOR',
        'FORWARDED_FOR',
        'X_FORWARDED',
        'FORWARDED',
        'CLIENT-IP',
        'CLIENT_IP',
        'PROXY-AGENT',
        'HTTP_X_PROXY_ID',
        'HTTP_X_FORWARDED_SERVER'
    ]

    headers = request.headers

    for header in suspicious_headers:
        if header in headers:
            return True

    return False

def check_connection_type():
    """Bağlantı türünü kontrol et"""
    headers = request.headers

    connection_type = headers.get('Connection', '').lower()
    if 'proxy' in connection_type:
        return True

    user_agent = headers.get('User-Agent', '').lower()
    suspicious_keywords = ['vpn', 'proxy', 'tor', 'tunnel']
    if any(keyword in user_agent for keyword in suspicious_keywords):
        return True

    return False

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
def get_db_connection():
    conn = sqlite3.connect('site.db')
    conn.row_factory = sqlite3.Row
    return conn

def create_table():
    conn = get_db_connection()
    conn.execute()
    conn.commit()
    conn.close()

def create_user_table():
    conn = get_db_connection()
    conn.execute()
    conn.commit()
    conn.close()

def get_user_by_username(username):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()
    return user

def add_upload_date_column():
    conn = get_db_connection()
    try:
        conn.execute('ALTER TABLE videos ADD COLUMN upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
        conn.commit()
    except sqlite3.OperationalError:

        pass
    conn.close()

def update_existing_videos():
    conn = get_db_connection()
    conn.execute('UPDATE videos SET upload_date = CURRENT_TIMESTAMP WHERE upload_date IS NULL')
    conn.commit()
    conn.close()

def add_test_videos():
    fake = Faker()

    test_user = User.query.filter_by(username='test_user').first()
    if not test_user:
        test_user = User(
            username='test_user',
            email='test@example.com',
            profile_image='default.jpg'
        )
        test_user.set_password('test_password')
        db.session.add(test_user)
        db.session.commit()

    for i in range(10):
        title = fake.sentence(nb_words=6, variable_nb_words=True)
        description = fake.paragraph(nb_sentences=3, variable_nb_sentences=True)
        filename = f"test_video_{i+1}.mp4"
        thumbnail = f"test_thumbnail_{i+1}.jpg"
        views = random.randint(100, 10000)
        upload_date = fake.date_time_between(start_date="-1y", end_date="now")

        new_video = Video(
            title=title,
            description=description,
            filename=filename,
            thumbnail=f"uploads/videos/thumbnails/{thumbnail}",
            views=views,
            user_id=test_user.id,
            upload_date=upload_date
        )
        db.session.add(new_video)

    db.session.commit()
    print("10 test videosu başarıyla eklendi.")

def check_table_structure():
    conn = get_db_connection()
    table_info = conn.execute("PRAGMA table_info(videos)").fetchall()
    print("Videos table structure:", table_info)
    conn.close()

def add_password_hash_column():
    conn = get_db_connection()
    try:
        conn.execute('ALTER TABLE users ADD COLUMN password_hash TEXT')
        conn.commit()
    except sqlite3.OperationalError:

        pass
    conn.close()

def ensure_upload_folder():
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    thumbnail_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'videos','thumbnails')
    if not os.path.exists(thumbnail_folder):
        os.makedirs(thumbnail_folder)

def check_database():
    conn = get_db_connection()
    print("Veritabanı bağlantısı başarılı.")

    users = conn.execute('SELECT * FROM users').fetchall()
    print(f"Kullanıcı sayısı: {len(users)}")
    if len(users) == 0:
        print("Kullanıcı tablosu boş. Örnek kullanıcı ekleniyor...")
        conn.execute('INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)',
                     ('test_user', 'test@example.com', 'hashed_password'))
        conn.commit()

    videos = conn.execute('SELECT * FROM videos').fetchall()
    print(f"Video sayıs: {len(videos)}")

    conn.close()

def remove_example_video():
    conn = get_db_connection()
    conn.execute("DELETE FROM videos WHERE title = 'rnek Video'")
    conn.commit()
    print("Örnek video silindi.")
    conn.close()

def add_uploader_column():
    conn = get_db_connection()
    try:
        conn.execute('ALTER TABLE videos ADD COLUMN uploader TEXT')
        conn.commit()
    except sqlite3.OperationalError:

        pass
    conn.close()

def update_existing_videos_uploader():
    conn = get_db_connection()
    conn.execute()
    conn.commit()
    conn.close()

def nl2br(value):
    if not value:
        return value
    return value.replace('\n', '<br>')

app.jinja_env.filters['nl2br'] = nl2br

def time_ago(dt):
    """
    Verilen tarihi 'x süre önce' formatına çevirir
    """
    now = datetime.utcnow()
    diff = now - dt

    seconds = diff.total_seconds()

    intervals = (
        ('yıl', seconds / 31536000),    
        ('ay', seconds / 2592000),      
        ('hafta', seconds / 604800),    
        ('gün', seconds / 86400),       
        ('saat', seconds / 3600),       
        ('dakika', seconds / 60),
        ('saniye', seconds)
    )

    for name, count in intervals:
        if count >= 1:
            count = int(count)
            return f"{count} {name}{'' if count == 1 else ''} önce"

    return "Az önce"

app.jinja_env.filters['time_ago'] = time_ago

@app.route('/')
def index():
    subscriptions = []
    top_channels = []
    recommended_channels = []

    site_settings = SiteSettings.query.first()

    if not current_user.is_authenticated or not current_user.is_admin:
        recommended_videos = Video.query.filter_by(is_approved=True).order_by(func.random()).limit(6).all()
        latest_videos = Video.query.filter_by(is_approved=True).order_by(Video.upload_date.desc()).limit(6).all()
        popular_videos = Video.query.filter_by(is_approved=True).order_by(Video.views.desc()).limit(6).all()
    else:
        recommended_videos = Video.query.order_by(func.random()).limit(6).all()
        latest_videos = Video.query.order_by(Video.upload_date.desc()).limit(6).all()
        popular_videos = Video.query.order_by(Video.views.desc()).limit(6).all()

    if current_user.is_authenticated:
        subscriptions = current_user.subscribed_to.limit(8).all()
        top_channels = User.query.join(Subscription, User.id == Subscription.subscribed_to_id)\
            .group_by(User.id)\
            .order_by(func.count(Subscription.subscriber_id).desc())\
            .limit(5).all()
        recommended_channels = User.query.filter(
            User.id != current_user.id,
            ~User.id.in_([sub.id for sub in current_user.subscribed_to])
        ).limit(5).all()

    return render_template('index.html',
                         recommended_videos=recommended_videos,
                         latest_videos=latest_videos,
                         popular_videos=popular_videos,
                         subscriptions=subscriptions,
                         top_channels=top_channels,
                         recommended_channels=recommended_channels,
                         site_settings=site_settings)

def notify_user(recipient_id, sender_id, notification_type, content):
    """
    Kullanıcıya bildirim gönderir

    Args:
        recipient_id: Bildirimi alacak kullanıcının ID'si
        sender_id: Bildirimi gönderen kullanıcının ID'si
        notification_type: Bildirim tipi (subscribe, unsubscribe, vb.)
        content: Bildirim içeriği
    """
    try:
        notification = Notification(
            recipient_id=recipient_id,
            sender_id=sender_id,
            type=notification_type,
            content=content,
            created_at=datetime.utcnow()
        )
        db.session.add(notification)
        db.session.commit()
        return True
    except Exception as e:
        app.logger.error(f"Bildirim gönderme hatası: {str(e)}")
        db.session.rollback()
        return False

def create_thumbnail(video_path, output_path):
    """Video'dan thumbnail oluştur"""
    try:
        clip = VideoFileClip(video_path)

        frame_time = min(1.0, clip.duration)
        frame = clip.get_frame(frame_time)

        img = Image.fromarray(frame)

        target_width = 1280
        target_height = 720
        img = img.resize((target_width, target_height), Image.LANCZOS)

        img.save(output_path, 'JPEG', quality=85, optimize=True)

        clip.close()
        return True

    except Exception as e:
        print(f"Thumbnail oluşturma hatası: {str(e)}")
        return False

def compress_video(video_path):
    """Video dosyasını sıkıştır"""
    try:
        output_path = video_path + '_compressed.mp4'

        cmd = [
            'ffmpeg', '-i', video_path,
            '-c:v', 'libx264',            
            '-crf', '23',                 
            '-preset', 'medium',          
            '-c:a', 'aac',               
            '-b:a', '128k',              
            '-movflags', '+faststart',    
            output_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:

            os.remove(video_path)
            os.rename(output_path, video_path)
            return True
        else:
            app.logger.error(f"Video sıkıştırma hatası: {result.stderr}")
            return False

    except Exception as e:
        app.logger.error(f"Video sıkıştırma hatası: {str(e)}")
        return False

def clean_video_metadata(input_path):
    """Video dosyasından metadata'yı temizler"""
    try:
        output_path = input_path + '_cleaned.mp4'

        stream = ffmpeg.input(input_path)
        stream = ffmpeg.output(stream, output_path,
                             map_metadata=-1,  
                             vcodec='copy',    
                             acodec='copy')    

        ffmpeg.run(stream, overwrite_output=True, capture_stdout=True, capture_stderr=True)

        os.remove(input_path)
        os.rename(output_path, input_path)
        return True

    except ffmpeg.Error as e:
        print(f'Metadata temizleme hatası: {e.stderr.decode()}')
        return False

def validate_image(stream):
    """Dosyanın gerçekten bir görüntü olup olmadığını kontrol eder"""
    header = stream.read(512)
    stream.seek(0)
    format = imghdr.what(None, header)
    if not format:
        return None
    return '.' + format.lower()

def process_thumbnail(file, max_size=(300, 300), allowed_types=None):
    """
    Thumbnail'i işler, doğrular ve optimize eder

    Args:
        file: Dosya nesnesi
        max_size: (genişlik, yükseklik) tuple
        allowed_types: İzin verilen MIME tipleri listesi

    Returns:
        (başarı, sonuç) tuple. Başarısızlık durumunda sonuç hata mesajıdır.
    """
    if allowed_types is None:
        allowed_types = ['image/jpeg', 'image/png', 'image/gif']

    try:

        mime = magic.from_buffer(file.read(1024), mime=True)
        file.seek(0)

        if mime not in allowed_types:
            return False, f"Desteklenmeyen dosya tipi: {mime}"

        img_format = validate_image(file)
        if not img_format:
            return False, "Geçersiz görüntü dosyası"

        image = Image.open(file)

        data = list(image.getdata())
        image_without_exif = Image.new(image.mode, image.size)
        image_without_exif.putdata(data)

        image_without_exif.thumbnail(max_size, Image.Resampling.LANCZOS)

        if image.format not in ['JPEG', 'PNG']:
            image_without_exif = image_without_exif.convert('RGB')
            img_format = '.jpg'

        return True, image_without_exif

    except Exception as e:
        return False, f"Görüntü işleme hatası: {str(e)}"

def save_thumbnail(image, filename, upload_folder):
    """İşlenmiş thumbnail'i kaydeder"""
    try:

        secure_name = secure_filename(filename)

        save_path = os.path.join(upload_folder, secure_name)

        image.save(
            save_path, 
            format='JPEG',
            quality=85, 
            optimize=True,
            progressive=True
        )

        return secure_name

    except Exception as e:
        app.logger.error(f"Thumbnail kaydetme hatası: {str(e)}")
        return None

def ensure_folders():
    folders = [
        app.config['UPLOAD_FOLDER'],
        os.path.join(app.config['UPLOAD_FOLDER'], 'thumbnails')
    ]
    for folder in folders:
        if not os.path.exists(folder):
            os.makedirs(folder)

def check_ffmpeg():
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        return False

def send_to_discord(action_type, admin, target, details):
    """
    Moderatör işlemlerini Discord'a bildirir
    """
    if not DISCORD_WEBHOOK_URL:
        print("Discord webhook URL'si tanımlanmamış")
        return

    try:
        data = {
            "embeds": [{
                "title": f"Moderatör İşlemi: {action_type}",
                "fields": [
                    {"name": "Admin", "value": admin.username, "inline": True},
                    {"name": "Hedef", "value": str(target), "inline": True}, 
                    {"name": "Detaylar", "value": str(details), "inline": False}
                ],
                "timestamp": datetime.utcnow().isoformat()
            }]
        }

        max_retries = 3
        retry_delay = 1  

        for attempt in range(max_retries):
            try:
                response = requests.post(
                    DISCORD_WEBHOOK_URL,
                    json=data,
                    timeout=5,  
                    headers={'Content-Type': 'application/json'}
                )

                if response.status_code == 204:
                    return  

                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', retry_delay))
                    time.sleep(retry_after)
                    continue

                print(f"Discord webhook hatası: {response.status_code}")
                print(f"Yanıt: {response.text}")
                break

            except requests.RequestException as e:
                if attempt == max_retries - 1:  
                    print(f"Discord webhook bağlantı hatası: {str(e)}")
                time.sleep(retry_delay)

    except Exception as e:
        print(f"Discord webhook beklenmeyen hata: {str(e)}")

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    remaining_uploads = current_user.get_remaining_uploads()
    upload_count = current_user.get_upload_count_last_5h()

    if request.method == 'POST':
        try:
            if remaining_uploads <= 0 and not current_user.is_admin:
                return jsonify({
                    'success': False, 
                    'error': '5 saatte en fazla 3 video yükleyebilirsiniz. Lütfen daha sonra tekrar deneyin.'
                })

            if not video_uploads_enabled and not current_user.is_admin:
                return jsonify({'success': False, 'error': 'Video yüklemeleri geçici olarak devre dışı'})

            if 'video' not in request.files:
                return jsonify({'success': False, 'error': 'Video dosyası bulunamadı'})

            video = request.files['video']
            if not video or not video.filename:
                return jsonify({'success': False, 'error': 'Geçersiz video dosyası'})

            if request.content_length > app.config['MAX_CONTENT_LENGTH']:
                return jsonify({'success': False, 'error': 'Dosya boyutu çok büyük (max 1GB)'})

            title = request.form.get('title')
            if not title:
                return jsonify({'success': False, 'error': 'Başlık gerekli'})

            video_filename = secure_filename(f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{video.filename}")
            video_path = os.path.join(app.config['UPLOAD_FOLDER'], video_filename)

            ensure_folders()

            video.save(video_path)

            if os.path.getsize(video_path) > 100 * 1024 * 1024:
                app.logger.info(f"Video sıkıştırılıyor: {video_filename}")
                if not compress_video(video_path):
                    return jsonify({'success': False, 'error': 'Video sıkıştırma hatası'})
                app.logger.info("Video sıkıştırma tamamlandı")

            thumbnail_filename = f"thumb_{video_filename}.jpg"
            thumbnail_path = os.path.join('uploads/videos/thumbnails', thumbnail_filename)
            full_thumbnail_path = os.path.join(app.root_path, 'static', thumbnail_path)

            if 'thumbnail' in request.files and request.files['thumbnail'].filename:
                thumbnail_file = request.files['thumbnail']
                success, result = process_thumbnail(thumbnail_file)
                if success:
                    result.save(full_thumbnail_path, 'JPEG', quality=85)
                else:
                    if not create_thumbnail(video_path, full_thumbnail_path):
                        return jsonify({'success': False, 'error': 'Thumbnail oluşturma hatası'})
            else:
                if not create_thumbnail(video_path, full_thumbnail_path):
                    return jsonify({'success': False, 'error': 'Thumbnail oluşturma hatası'})

            """            
            if os.path.getsize(video_path) > 100 * 1024 * 1024:  
                if not compress_video(video_path):
                    return jsonify({'success': False, 'error': 'Video sıkıştırma hatası'})
            """

            new_video = Video(
                title=title,
                filename=video_filename,
                description=request.form.get('description', ''),
                user_id=current_user.id,
                thumbnail=thumbnail_path.replace('\\', '/'),
                is_approved=current_user.is_admin  
            )

            db.session.add(new_video)
            db.session.commit()

            return jsonify({
                'success': True,
                'redirect': url_for('watch', video_id=new_video.id)
            })

        except Exception as e:
            print(f"Video yükleme hatası: {str(e)}")
            return jsonify({'success': False, 'error': 'Video yüklenirken bir hata oluştu'})

    return render_template('upload.html',
                         remaining_uploads=remaining_uploads,
                         upload_count=upload_count)

class CommentForm(FlaskForm):
    content = TextAreaField('Yorum', validators=[DataRequired()])

@app.route('/watch/<int:video_id>')
def watch(video_id):
    video = Video.query.get_or_404(video_id)

    if not video.is_approved and (not current_user.is_authenticated or 
        (current_user.id != video.user_id and not current_user.is_admin)):
        abort(404)

    try:

        session_key = f'video_view_{video_id}'
        current_time = datetime.utcnow()

        last_view_time = session.get(f'video_view_time_{video_id}')
        can_count_view = False

        if not last_view_time or (current_time - datetime.fromisoformat(last_view_time) > timedelta(minutes=30)):
            can_count_view = True

        if can_count_view:
            try:

                view = VideoView(
                    video_id=video_id,
                    user_id=current_user.id if current_user.is_authenticated else None
                )
                db.session.add(view)

                video.views += 1
                db.session.commit()

                session[session_key] = True
                session[f'video_view_time_{video_id}'] = current_time.isoformat()

            except Exception as e:
                db.session.rollback()
                print(f"Görüntülenme kaydı hatası: {str(e)}")

    except Exception as e:
        print(f"Video izleme hatası: {str(e)}")

    form = CommentForm()
    uploader = User.query.get(video.user_id)
    recommended_videos = Video.query.filter(Video.id != video_id).order_by(db.func.random()).limit(5).all()

    is_subscribed = False
    if current_user.is_authenticated and uploader:
        is_subscribed = current_user.is_subscribed(uploader)

    user_action = None
    if current_user.is_authenticated:
        user_action = video.get_user_action(current_user.id)

    sorted_comments = video.comments.order_by(Comment.created_at.desc()).all()
    return render_template('watch.html',
                         video=video,
                         form=form,
                         uploader=uploader,
                         recommended_videos=recommended_videos,
                         is_subscribed=is_subscribed,
                         comments=sorted_comments,
                         user_action=user_action)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email'].lower()
        password = request.form['password']
        token = request.form.get('cf-turnstile-response')

        if len(username) > 32:
            flash('Kullanıcı adı 32 karakterden uzun olamaz.', 'error')
            return redirect(url_for('register'))

        if not username.isascii():
            flash('Kullanıcı adı sadece İngilizce karakterler içerebilir.', 'error')
            return redirect(url_for('register'))

        if not all(c.isalnum() or c in '-_' for c in username):
            flash('Kullanıcı adı sadece harf, rakam, tire (-) ve alt çizgi (_) içerebilir.', 'error')
            return redirect(url_for('register'))

        username_lower = username.lower()
        existing_user = User.query.filter(func.lower(User.username) == username_lower).first()

        if existing_user:
            flash('Bu kullanıcı adı zaten kayıtlı.', 'error')
            return redirect(url_for('register'))

        existing_email = User.query.filter(func.lower(User.email) == email).first()
        if existing_email:
            flash('Bu e-posta adresi zaten kayıtlı.', 'error')
            return redirect(url_for('register'))

        secret_key = 'gizli_anahtarınız'  # Cloudflare Turnstile secret key'i değiştirilmeli
        response = requests.post('https://challenges.cloudflare.com/turnstile/v0/siteverify', data={
            'secret': secret_key,
            'response': token,
        })

        result = response.json()
        if result['success']:
            user = User(
                username=username, 
                email=email,
                profile_image='default.jpg'
            )
            user.set_password(password)
            db.session.add(user)
            db.session.commit()

            default_channels = User.query.filter(User.id.in_([1, 2])).all()
            for channel in default_channels:
                if channel:
                    subscription = Subscription(
                        subscriber_id=user.id,
                        subscribed_to_id=channel.id
                    )
                    db.session.add(subscription)

            db.session.commit()

            flash('Kayıt başarılı. Lütfen giriş yapın.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Robot doğrulaması başarısız oldu. Lütfen tekrar deneyin.', 'error')
            return redirect(url_for('register'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()

        if user:
            ban_status = user.is_banned
            if ban_status:
                ban_message = f"Hesabınız banlandı.\nNeden: {user.ban.reason}"
                if user.ban.expiry_date:
                    ban_message += f"\nBan bitiş tarihi: {user.ban.expiry_date.strftime('%d.%m.%Y %H:%M')}"
                flash(ban_message, 'error')
                return redirect(url_for('login'))

            if user.check_password(password):
                if maintenance_mode and not user.is_admin:
                    flash('Bakım modu aktif. Sadece yöneticiler giriş yapabilir.', 'error')
                    return redirect(url_for('login'))
                user.last_ip = request.remote_addr
                db.session.commit()
                login_user(user)
                return redirect(url_for('index'))
        flash('Geçersiz kullanıcı adı veya şifre', 'error')
    return render_template('login.html', maintenance_mode=maintenance_mode)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/profile/<username>')
def profile(username):
    user = User.query.filter_by(username=username).first_or_404()

    page = request.args.get('page', 1, type=int)
    videos = Video.query.filter_by(user_id=user.id)\
        .order_by(Video.upload_date.desc())\
        .paginate(page=page, per_page=12)

    user.channel_views = sum(video.views for video in videos.items)
    user.total_upload_views = sum(video.views for video in videos.items)

    if not user.date_joined:
        user.date_joined = datetime.utcnow()

    user.last_login = datetime.utcnow()

    db.session.commit()

    return render_template('profile.html', 
        user=user, 
        videos=videos,
        subscriber_count=user.subscribers.count(),
        is_banned=user.is_banned
    )

def save_profile_image(file, user_id):
    if file and file.filename:

        filename = secure_filename(f"profile_{user_id}_{int(datetime.now().timestamp())}.png")
        image_path = os.path.join('static', 'profile_images', filename)

        os.makedirs(os.path.join(app.root_path, 'static', 'profile_images'), exist_ok=True)

        img = Image.open(file)
        img = img.convert('RGB')
        img.thumbnail((300, 300))  
        img.save(os.path.join(app.root_path, image_path))

        old_image = User.query.get(user_id).profile_image
        if old_image and old_image != 'default.jpg':
            old_image_path = os.path.join(app.root_path, 'static', 'profile_images', old_image)
            if os.path.exists(old_image_path):
                os.remove(old_image_path)

        return filename
    return None

@app.route('/upload_profile_image', methods=['GET', 'POST'])
@login_required
def upload_profile_image():
    if request.method == 'POST':
        if 'profile_image' in request.files:
            image = request.files['profile_image']
            if image.filename:
                image_filename = f"profile_{current_user.id}.png"
                image_path = os.path.join("static", "profile_images", image_filename)
                image.save(image_path)

                conn = get_db_connection()
                conn.execute('UPDATE users SET profile_image = ? WHERE id = ?', (image_filename, current_user.id))
                conn.commit()
                conn.close()

                flash('Profil resmi baarıyla yüklendi.', 'success')
                return redirect(url_for('profile', user_id=current_user.id))
    return render_template('upload_profile_image.html')

@app.route('/videos')
def videos():
    currently_watching = Video.query.filter_by(is_approved=True).order_by(Video.views.desc()).limit(5).all()

    popular_videos = Video.query.order_by(
        Video.views.desc()
    ).limit(5).all()

    latest_videos = Video.query.order_by(
        Video.upload_date.desc()
    ).limit(5).all()

    most_liked_videos = db.session.query(Video).join(
        VideoAction, Video.id == VideoAction.video_id
    ).filter(
        VideoAction.action_type == 'like'
    ).group_by(
        Video.id
    ).order_by(
        func.count(VideoAction.id).desc()
    ).limit(5).all()

    most_commented_videos = db.session.query(Video).join(
        Comment, Video.id == Comment.video_id
    ).group_by(
        Video.id
    ).order_by(
        func.count(Comment.id).desc()
    ).limit(5).all()

    one_day_ago = datetime.utcnow() - timedelta(days=1)
    trending_videos = db.session.query(Video).join(
        VideoView, Video.id == VideoView.video_id
    ).filter(
        VideoView.timestamp >= one_day_ago
    ).group_by(
        Video.id
    ).order_by(
        func.count(VideoView.id).desc()
    ).limit(5).all()

    return render_template('videos.html',
                         currently_watching=currently_watching,
                         popular_videos=popular_videos,
                         latest_videos=latest_videos,
                         most_liked_videos=most_liked_videos,
                         most_commented_videos=most_commented_videos,
                         trending_videos=trending_videos)

@app.route('/user/<username>')
def user_profile(username):
    user = get_user_by_username(username)
    if user:
        return render_template('profile.html', user=user)
    return "Kullanıcı bulunamadı!", 404

@app.route('/subscribe/<int:user_id>', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def subscribe(user_id):
    try:

        if current_user.is_banned:
            return jsonify({
                'success': False,
                'error': 'Banlı kullanıcılar abone olamaz'
            }), 403

        user_to_subscribe = User.query.get_or_404(user_id)

        if user_to_subscribe.is_banned:
            return jsonify({
                'success': False,
                'error': 'Banlı kullanıcılara abone olunamaz'
            }), 403

        if current_user.id == user_id:
            return jsonify({
                'success': False, 
                'error': 'Kendinize abone olamazsınız'
            }), 400

        try:
            is_subscribed = current_user.is_subscribed(user_to_subscribe)

            if is_subscribed:
                current_user.unsubscribe(user_to_subscribe)
                subscribed = False

                notify_user(user_to_subscribe.id, current_user.id, 'unsubscribe', 
                          f"{current_user.username} abonelikten çıktı")
            else:
                current_user.subscribe(user_to_subscribe)
                subscribed = True

                notify_user(user_to_subscribe.id, current_user.id, 'subscribe',
                          f"{current_user.username} abone oldu")

            db.session.commit()

            return jsonify({
                'success': True,
                'subscribed': subscribed,
                'subscriber_count': user_to_subscribe.subscribers.count()
            })

        except Exception as e:
            db.session.rollback()
            raise e

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Abone olma hatası: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'İşlem sırasında bir hata oluştu'
        }), 500

@app.route('/search')
def search():
    search_query = request.args.get('q', '')
    search_type = request.args.get('type', 'all')
    sort_by = request.args.get('sort', 'relevance')

    start_time = time.time()

    if not search_query:
        return redirect(url_for('index'))

    results = []

    if search_type in ['all', 'users']:
        user_results = User.query.filter(or_(
            User.username.ilike(f'%{search_query}%'),
            User.about.ilike(f'%{search_query}%')
        )).all()  
        if search_type == 'users':
            results = user_results
        else:
            results.extend(user_results)

    if search_type in ['all', 'videos']:
        video_query = Video.query.filter(
            and_(
                or_(
                    Video.title.ilike(f'%{search_query}%'),
                    Video.description.ilike(f'%{search_query}%')
                ),
                Video.is_approved == True
            )
        )

        if sort_by == 'upload_date':
            video_query = video_query.order_by(Video.upload_date.desc())
        elif sort_by == 'view_count':
            video_query = video_query.order_by(Video.views.desc())
        elif sort_by == 'comment_count':
            video_query = video_query.order_by(Video.comments.count().desc())
        else:  
            video_query = video_query.order_by(
                case(
                    (Video.title.ilike(f'%{search_query}%'), 1),
                    (Video.description.ilike(f'%{search_query}%'), 2),
                    else_=3
                )
            )

        video_results = video_query.all()
        if search_type == 'videos':
            results = video_results
        else:
            results.extend(video_results)

    search_time = round(time.time() - start_time, 2)

    return render_template('search_results.html',
                         results=results,
                         search_query=search_query,
                         search_type=search_type,
                         search_time=search_time,
                         sort_by=sort_by)

@app.route('/community')
@login_required
def community():
    return render_template('community.html')

@app.route('/get_online_users')
@login_required
def get_online_users():
    users = User.query.filter(User.id != current_user.id).all()
    return jsonify([{'id': user.id, 'username': user.username} for user in users])

@app.route('/api/comments/<int:video_id>/add', methods=['POST'])
@limiter.limit("10 per minute")
@login_required
def add_comment(video_id):
    try:
        content = request.form.get('content')
        if not content:
            return jsonify({'success': False, 'error': 'Yorum içeriği boş olamaz'})

        video = Video.query.get_or_404(video_id)

        comment = Comment(
            content=content,
            video_id=video_id,
            user_id=current_user.id,
            created_at=datetime.utcnow()
        )

        db.session.add(comment)
        db.session.commit()

        return jsonify({
            'success': True,
            'comment': {
                'id': comment.id,
                'content': comment.content,
                'username': current_user.username,
                'user_avatar': url_for('static', filename='profile_images/' + current_user.profile_image) if current_user.profile_image else url_for('static', filename='images/default.jpg'),
                'created_at': comment.created_at.strftime('%d.%m.%Y %H:%M')
            }
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/comments/<int:comment_id>/edit', methods=['POST'])
@limiter.limit("20 per minute")
@login_required
def edit_comment(comment_id):
    try:
        content = request.form.get('content')
        if not content:
            return jsonify({'success': False, 'error': 'Yorum içeriği boş olamaz'})

        comment = Comment.query.get_or_404(comment_id)

        if comment.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Bu yorumu düzenleme yetkiniz yok'}), 403

        comment.content = content
        comment.is_edited = True
        comment.edited_at = datetime.utcnow()

        db.session.commit()

        return jsonify({
            'success': True,
            'comment': {
                'id': comment.id,
                'content': comment.content,
                'username': current_user.username,
                'user_avatar': current_user.profile_image or 'default.jpg',
                'created_at': comment.created_at.strftime('%d.%m.%Y %H:%M'),
                'is_edited': True,
                'edited_at': comment.edited_at.strftime('%d.%m.%Y %H:%M')
            }
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/comments/<int:comment_id>/reply', methods=['POST'])
@login_required
def reply_to_comment(comment_id):
    try:
        content = request.form.get('content')
        if not content:
            return jsonify({'success': False, 'error': 'Yorum içeriği boş olamaz'})

        parent_comment = Comment.query.get_or_404(comment_id)
        video = Video.query.get_or_404(parent_comment.video_id)

        reply = Comment(
            content=content,
            video_id=parent_comment.video_id,
            user_id=current_user.id,
            parent_id=comment_id,
            created_at=datetime.utcnow()
        )

        db.session.add(reply)
        db.session.commit()

        reply_data = {
            'id': reply.id,
            'content': reply.content,
            'username': current_user.username,
            'user_avatar': url_for('static', filename='profile_images/' + (current_user.profile_image or 'default.jpg')),
            'created_at': reply.created_at.strftime('%d.%m.%Y %H:%M'),
            'is_edited': False,
            'can_edit': True,
            'can_delete': True,
            'parent_id': reply.parent_id
        }

        return jsonify({
            'success': True,
            'reply': reply_data
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/comments/<int:video_id>', methods=['GET'])
def get_comments(video_id):
    try:
        print(f"Video {video_id} için yorumlar getiriliyor...")
        comments = Comment.query.filter_by(video_id=video_id).order_by(Comment.created_at.desc()).all()
        print(f"Toplam {len(comments)} yorum bulundu")

        comment_list = []
        for comment in comments:
            user = User.query.get(comment.user_id)
            if user:
                comment_data = {
                    'username': user.username,
                    'user_avatar': user.profile_image or 'default.jpg',
                    'content': comment.content,
                    'created_at': comment.created_at.strftime('%d.%m.%Y %H:%M')
                }
                comment_list.append(comment_data)

        return jsonify(comment_list)
    except Exception as e:
        print(f"Yorumlar getirilirken hata: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/send_friend_request/<int:user_id>', methods=['POST'])
@login_required
def send_friend_request(user_id):
    user = User.query.get_or_404(user_id)
    if current_user != user:
        current_user.send_friend_request(user)

        notification = Notification(
            recipient_id=user_id,
            sender_id=current_user.id,
            type='friend_request',
            content=f'{current_user.username} size arkadaşlık isteği gönderdi.'
        )
        db.session.add(notification)
        db.session.commit()

        flash('Arkadaşlık isteği gönderildi.', 'success')
    return redirect(url_for('profile', username=user.username))

@app.route('/video_action/<int:video_id>/<action>', methods=['POST'])
@login_required
def video_action_handler(video_id, action):
    try:

        db.session.remove()

        if action not in ['like', 'mid-like', 'dislike']:
            return jsonify({'success': False, 'error': 'Geçersiz işlem'}), 400

        with db.session.begin_nested():
            video = Video.query.get_or_404(video_id)
            user_action = VideoAction.query.filter_by(
                user_id=current_user.id, 
                video_id=video_id
            ).with_for_update().first()

            if user_action:
                if user_action.action_type == action:
                    db.session.delete(user_action)
                else:
                    user_action.action_type = action
            else:
                new_action = VideoAction(
                    user_id=current_user.id,
                    video_id=video_id,
                    action_type=action
                )
                db.session.add(new_action)

        db.session.commit()

        likes = VideoAction.query.filter_by(video_id=video_id, action_type='like').count()
        mid_likes = VideoAction.query.filter_by(video_id=video_id, action_type='mid-like').count()
        dislikes = VideoAction.query.filter_by(video_id=video_id, action_type='dislike').count()

        return jsonify({
            'success': True,
            'likes': likes,
            'mid_likes': mid_likes,
            'dislikes': dislikes
        })

    except Exception as e:
        db.session.rollback()
        print(f"Hata oluştu: {str(e)}")  
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        db.session.close()

@app.route('/video_action_status/<int:video_id>')
@login_required
def video_action_status(video_id):
    video = Video.query.get_or_404(video_id)
    user_action = VideoAction.query.filter_by(user_id=current_user.id, video_id=video_id).first()

    likes = VideoAction.query.filter_by(video_id=video_id, action='like').count()
    mid_likes = VideoAction.query.filter_by(video_id=video_id, action='mid-like').count()
    dislikes = VideoAction.query.filter_by(video_id=video_id, action='dislike').count()

    return jsonify({
        'likes': likes,
        'mid_likes': mid_likes,
        'dislikes': dislikes,
        'user_action': user_action.action if user_action else None
    })

def founder_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_founder:
            flash('Bu işlemi sadece kurucu yapabilir.', 'error')
            return redirect(url_for('mod_panel'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Bu sayfaya erişim izniniz yok.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/mod_panel')
@login_required
def mod_panel():

    if not current_user.is_admin:
        flash('Bu sayfaya erişim yetkiniz yok.', 'error')
        return redirect(url_for('index'))

    role_filter = request.args.get('role', 'all')
    search_query = request.args.get('q', '')
    ip_query = request.args.get('ip', '')
    page = request.args.get('page', 1, type=int)

    users_query = User.query

    if search_query:
        users_query = users_query.filter(
            or_(
                User.username.ilike(f'%{search_query}%'),
                User.email.ilike(f'%{search_query}%')
            )
        )

    if ip_query:
        users_query = users_query.filter(User.last_ip.ilike(f'%{ip_query}%'))

    if role_filter != 'all':
        if role_filter == 'admin':
            users_query = users_query.filter(User.is_admin == True)
        elif role_filter == 'banned':
            users_query = users_query.filter(User.is_banned == True)

    total_users = User.query.count()
    total_admins = User.query.filter_by(is_admin=True).count()
    total_banned = User.query.filter_by(is_banned=True).count()
    report_count = Report.query.filter_by(status='pending').count()

    users = users_query.order_by(User.date_joined.desc()).paginate(
        page=page, per_page=20, error_out=False
    )

    start_index = (page - 1) * 20 + 1
    end_index = min(start_index + 19, total_users)

    site_settings = SiteSettings.query.first()

    return render_template('mod_panel/mod_panel.html',
                         current_time=datetime.now(),
                         users=users,
                         total_users=total_users,
                         total_admins=total_admins,
                         total_banned=total_banned,
                         start_index=start_index,
                         end_index=end_index,
                         report_count=report_count,
                         role_filter=role_filter,
                         search_query=search_query,
                         ip_query=ip_query,
                         site_settings=site_settings)

@app.route('/mod_panel/update_role/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def update_role(user_id):
    try:
        user = User.query.get_or_404(user_id)

        if not current_user.can_moderate(user):
            return jsonify({
                'success': False,
                'error': 'Bu kullanıcının rolünü değiştirme yetkiniz yok.'
            }), 403

        role = request.form.get('role')

        if role == 'founder':
            if not current_user.is_founder:
                return jsonify({
                    'success': False,
                    'error': 'Founder rolünü sadece founderlar verebilir.'
                }), 403
            user.is_founder = True
            user.is_admin = True
        elif role == 'admin':
            user.is_founder = False
            user.is_admin = True
        else:  
            user.is_founder = False
            user.is_admin = False

        db.session.commit()
        return jsonify({'success': True})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

import random
import string

def generate_random_password(length=12):
    """Rastgele güçlü şifre oluştur"""
    characters = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(random.choice(characters) for _ in range(length))

@app.route('/mod_panel/get_related_accounts/<ip>')
@login_required
@admin_required
def get_related_accounts(ip):
    try:
        accounts = User.query.filter_by(last_ip=ip).all()

        accounts_data = []
        for account in accounts:
            accounts_data.append({
                'id': account.id,
                'username': account.username,
                'profile_image': account.profile_image,
                'is_banned': account.is_banned,
                'date_joined': account.date_joined.strftime('%d.%m.%Y'),
                'is_admin': account.is_admin,
                'is_founder': account.is_founder
            })

        return jsonify({
            'success': True,
            'accounts': accounts_data
        })

    except Exception as e:
        app.logger.error(f"IP'ye bağlı hesapları getirme hatası: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/mod_panel/get_password/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def get_user_password(user_id):
    try:
        if not current_user.is_admin:
            return jsonify({'success': False, 'error': 'Yetkiniz yok'})

        user = User.query.get_or_404(user_id)

        if not current_user.can_moderate(user):
            return jsonify({'success': False, 'error': 'Bu kullanıcının şifresini görüntüleme yetkiniz yok'})

        if user.is_founder:
            return jsonify({'success': False, 'error': 'Founder hesaplarının şifresini görüntüleyemezsiniz'})

        new_password = generate_random_password()
        user.set_password(new_password)

        log = ModLog(
            admin_id=current_user.id,
            action_type='view_password',
            target_user_id=user_id,
            details=f"Şifre görüntüleme ve değiştirme: {user.username}"
        )
        db.session.add(log)
        db.session.commit()

        return jsonify({
            'success': True,
            'password': new_password  
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/mod_panel/change_password/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def change_user_password(user_id):
    try:
        if not current_user.is_admin:
            return jsonify({'success': False, 'error': 'Yetkiniz yok'})

        data = request.get_json()
        new_password = data.get('new_password')

        if not new_password:
            return jsonify({'success': False, 'error': 'Yeni şifre boş olamaz'})

        user = User.query.get_or_404(user_id)

        if user.is_founder:
            return jsonify({'success': False, 'error': 'Founder hesaplarının şifresini değiştiremezsiniz'})

        user.set_password(new_password)

        log = ModLog(
            admin_id=current_user.id,
            action_type='change_password',
            target_user_id=user_id,
            details=f"Şifre değiştirildi: {user.username}"
        )
        db.session.add(log)
        db.session.commit()

        return jsonify({'success': True})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/mod_panel_settings')
@login_required
def mod_panel_settings():
    if not current_user.is_admin and not current_user.is_founder:
        abort(403)

    site_settings = SiteSettings.query.first()

    return render_template('mod_panel/mod_panel_settings.html',
                         site_settings=site_settings,
                         current_time=datetime.utcnow(),
                         maintenance_mode=maintenance_mode,
                         video_uploads_enabled=video_uploads_enabled)

@app.route('/mod_panel/toggle_maintenance', methods=['POST'])
@login_required
def toggle_maintenance():
    if not current_user.is_admin and not current_user.is_founder:
        return jsonify({'success': False, 'error': 'Yetkiniz yok'})

    global maintenance_mode
    maintenance_mode = not maintenance_mode
    target = f"Maintenance Mode"
    details = f"Maintenance Mode: {maintenance_mode}"
    send_to_discord('maintenance_mode', current_user, target, details)
    return jsonify({
        'success': True,
        'maintenance_mode': maintenance_mode
    })

@app.route('/mod_panel/toggle_video_uploads', methods=['POST'])
@login_required
def toggle_video_uploads():
    if not current_user.is_admin and not current_user.is_founder:
        return jsonify({'success': False, 'error': 'Yetkiniz yok'})

    global video_uploads_enabled
    video_uploads_enabled = not video_uploads_enabled

    return jsonify({
        'success': True,
        'video_uploads_enabled': video_uploads_enabled
    })

@app.route('/mod_panel/toggle_ban/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def toggle_ban(user_id):
    try:
        user = User.query.get_or_404(user_id)
        action = request.form.get('action')

        if action == 'unban':

            active_ban = Ban.query.filter_by(
                user_id=user_id,
                is_active=True
            ).first()

            if active_ban:
                active_ban.is_active = False
                db.session.commit()

            return jsonify({
                'success': True,
                'message': f'{user.username} kullanıcısının banı kaldırıldı.'
            })

        else:

            reason = request.form.get('reason')
            duration = request.form.get('duration')

            if not reason:
                return jsonify({'success': False, 'error': 'Ban nedeni belirtilmeli'})

            if not current_user.can_moderate(user):
                return jsonify({
                    'success': False,
                    'error': 'Bu kullanıcıyı banlama yetkiniz yok.'
                }), 403

            expiry_date = None
            if duration:
                try:
                    days = int(duration)
                    expiry_date = datetime.utcnow() + timedelta(days=days)
                except ValueError:
                    return jsonify({'success': False, 'error': 'Geçersiz süre formatı'})

            ban = Ban(
                user_id=user_id,
                banned_by_id=current_user.id,
                reason=reason,
                expiry_date=expiry_date,
                is_active=True
            )

            db.session.add(ban)
            db.session.commit()

            return jsonify({'success': True})

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Ban işlemi hatası: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/mod_panel/videos')
@login_required
@admin_required
def mod_panel_videos():
    page = request.args.get('page', 1, type=int)
    videos = Video.query.order_by(Video.upload_date.desc()).paginate(page=page, per_page=20)
    total_videos = Video.query.count()
    reported_videos = Video.query.filter(Video.reports.any()).count()

    today = datetime.now().date()

    return render_template('mod_panel/mod_panel_videos.html',
                         videos=videos,
                         total_videos=total_videos,
                         reported_videos=reported_videos,
                         current_time=datetime.now(),
                         today=today,  
                         start_index=(page-1)*20 + 1,
                         end_index=min(page*20, total_videos))

@app.route('/mod_panel/approve_video/<int:video_id>', methods=['POST'])
@login_required
@admin_required
def approve_video(video_id):
    try:
        video = Video.query.get_or_404(video_id)
        video.is_approved = True

        mod_log = ModLog(
            admin_id=current_user.id,
            action_type='approve_video',
            target_video_id=video_id,
            details="Video onaylandı"
        )
        db.session.add(mod_log)
        db.session.commit()

        target = f"{video.title} (ID: {video.id})"
        details = f"Yükleyen: {video.uploader.username}"
        send_to_discord('approve_video', current_user, target, details)

        return jsonify({'success': True})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/make_admin/<int:user_id>', methods=['POST'])
@login_required
@founder_required
def make_admin(user_id):
    user = User.query.get_or_404(user_id)
    user.make_admin()
    flash(f'{user.username} artık bir admin.', 'success')
    return redirect(url_for('mod_panel'))

@app.route('/remove_admin/<int:user_id>', methods=['POST'])
@login_required
@founder_required
def remove_admin(user_id):
    user = User.query.get_or_404(user_id)
    user.remove_admin()
    flash(f'{user.username} artık admin değil.', 'success')
    return redirect(url_for('mod_panel'))

@app.route('/ban_user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def ban_user(user_id):
    try:
        user = User.query.get_or_404(user_id)
        reason = request.form.get('reason')
        duration = request.form.get('duration')  

        if not reason:
            return jsonify({'success': False, 'error': 'Ban nedeni belirtilmeli'})

        if not current_user.can_moderate(user):
            return jsonify({
                'success': False,
                'error': 'Bu kullanıcıyı banlama yetkiniz yok.'
            }), 403

        videos = Video.query.filter_by(user_id=user_id).all()
        for video in videos:
            try:

                if video.filename:
                    video_path = os.path.join(app.config['UPLOAD_FOLDER'], video.filename)
                    if os.path.exists(video_path):
                        os.remove(video_path)

                if video.thumbnail:
                    thumbnail_path = os.path.join(app.config['UPLOAD_FOLDER'],'videos','thumbnails', video.thumbnail)
                    if os.path.exists(thumbnail_path):
                        os.remove(thumbnail_path)

                VideoView.query.filter_by(video_id=video.id).delete()
                VideoAction.query.filter_by(video_id=video.id).delete()
                Comment.query.filter_by(video_id=video.id).delete()
                Report.query.filter_by(reported_video_id=video.id).delete()

                db.session.delete(video)

            except Exception as e:
                app.logger.error(f"Video silme hatası: {str(e)}")
                continue

        expiry_date = None
        if duration:
            try:
                days = int(duration)
                expiry_date = datetime.utcnow() + timedelta(days=days)
            except ValueError:
                pass

        user.is_banned = True
        user.ban_end_date = expiry_date

        ban = Ban(
            user_id=user_id,
            banned_by=current_user.id,
            reason=reason,
            expiry_date=expiry_date
        )

        db.session.add(ban)
        db.session.commit()

        ban_message = {
            'type': 'ban',
            'user_id': user_id,
            'username': user.username,
            'reason': reason,
            'duration': duration if duration else 'Süresiz',
            'banned_by': current_user.username
        }

        try:
            cursor_url = app.config.get('CURSOR_URL')
            if cursor_url:
                requests.post(f"{cursor_url}/event", json=ban_message)
        except Exception as e:
            app.logger.error(f"Cursor bildirimi hatası: {str(e)}")

        mod_log = ModLog(
            admin_id=current_user.id,
            action_type='ban',
            target_user_id=user_id,
            details=f"Sebep: {reason}, Süre: {duration if duration else 'Süresiz'}"
        )
        db.session.add(mod_log)
        db.session.commit()

        target = f"{user.username} (ID: {user.id})"
        details = f"Sebep: {reason}\nSüre: {duration if duration else 'Süresiz'}"
        send_to_discord('ban', current_user, target, details)

        return jsonify({'success': True})

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Ban işlemi hatası: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/mod_panel/reset_username/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def reset_username(user_id):
    try:
        user = User.query.get_or_404(user_id)

        if not current_user.can_moderate(user):
            return jsonify({
                'success': False,
                'error': 'Bu kullanıcı üzerinde yetkiniz yok.'
            }), 403

        user.username = f"User{user.id}"
        db.session.commit()

        return jsonify({'success': True})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/mod_panel/reset_profile_image/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def reset_profile_image(user_id):
    try:
        user = User.query.get_or_404(user_id)

        if not current_user.can_moderate(user):
            return jsonify({
                'success': False,
                'error': 'Bu kullanıcı üzerinde yetkiniz yok.'
            }), 403

        if user.profile_image and user.profile_image != 'default.jpg':
            try:
                os.remove(os.path.join(app.root_path, 'static', 'profile_images', user.profile_image))
            except:
                pass

        user.profile_image = 'default.jpg'
        db.session.commit()

        return jsonify({'success': True})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/mod_panel/update_user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def update_user(user_id):
    try:
        user = User.query.get_or_404(user_id)
        data = request.get_json()

        if not current_user.can_moderate(user):
            return jsonify({
                'success': False,
                'error': 'Bu kullanıcı üzerinde yetkiniz yok.'
            }), 403

        new_username = data.get('username')
        if new_username:

            existing_user = User.query.filter(
                User.username == new_username,
                User.id != user_id
            ).first()

            if existing_user:
                return jsonify({
                    'success': False,
                    'error': 'Bu kullanıcı adı zaten kullanılıyor.'
                }), 400

            user.username = new_username
            db.session.commit()

        return jsonify({'success': True})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/video/<int:video_id>/delete', methods=['POST'])
@login_required
def delete_video(video_id):
    try:
        video = Video.query.get_or_404(video_id)

        if not (current_user.id == video.user_id or current_user.is_admin):
            return jsonify({'success': False, 'error': 'Bu işlem için yetkiniz yok'})

        VideoView.query.filter_by(video_id=video_id).delete()
        VideoAction.query.filter_by(video_id=video_id).delete()
        Comment.query.filter_by(video_id=video_id).delete()
        Report.query.filter_by(reported_video_id=video.id).delete()

        try:
            if video.filename:
                video_path = os.path.join(app.config['UPLOAD_FOLDER'], video.filename)
                if os.path.exists(video_path):
                    os.remove(video_path)

            if video.thumbnail:
                thumbnail_path = os.path.join('static', video.thumbnail)
                if os.path.exists(thumbnail_path):
                    os.remove(thumbnail_path)
        except Exception as e:
            app.logger.error(f"Dosya silme hatası: {str(e)}")

        db.session.delete(video)
        db.session.commit()

        return jsonify({'success': True})

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Video silme hatası: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'success': False, 'error': 'Video silinirken bir hata oluştu'})

@app.route('/video/<int:video_id>/edit_video', methods=['POST'])
@login_required
def edit_video(video_id):
    try:
        video = Video.query.get_or_404(video_id)

        if not (current_user.is_admin or current_user.id == video.user_id):
            return jsonify({'success': False, 'error': 'Bu işlem için yetkiniz yok'}), 403

        title = request.form.get('title')
        description = request.form.get('description')

        if not title:
            return jsonify({'success': False, 'error': 'Başlık boş olamaz'}), 400

        video.title = title
        video.description = description
        db.session.commit()

        return jsonify({'success': True})

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Video düzenleme hatası: {str(e)}")
        return jsonify({'success': False, 'error': 'Video gncellenirken bir hata oluştu'}), 500

def create_founder_accounts():
    try:
        sparrow = User.query.filter(
            or_(
                User.username == 'admin',
                User.email == 'admin@example.com' 
            )
        ).first()
        
        if not sparrow:
            sparrow = User(
                username='admin',
                email='admin@example.com',
                is_founder=True,
                is_admin=True,
                is_banned=False,
                ban_end_date=None
            )
            sparrow.set_password('bu_şifreyi_değiştirin')
            db.session.add(sparrow)

        db.session.commit()

    except Exception as e:
        db.session.rollback()
        print(f"Founder hesapları oluşturulurken hata: {str(e)}")

@app.route('/report', methods=['POST'])
@login_required
def report():
    data = request.json
    turnstile_response = data['gizli-site-key']  # Bu anahtar kaldırılmalı

    secret_key = 'bu gizli anahtarını değiştirin'  # Bu anahtar kaldırılmalı
    
    response = requests.post('https://challenges.cloudflare.com/turnstile/v0/siteverify', data={
        'secret': secret_key,
        'response': turnstile_response
    })
    result = response.json()

    if not result['success']:
        return jsonify({'success': False, 'message': 'Turnstile doğrulaması başarısız oldu.'})

    new_report = Report(
        reporter_id=current_user.id,
        reason=data['reason']
    )

    if data['type'] == 'user':
        new_report.reported_user_id = data['id']
    elif data['type'] == 'video':
        new_report.reported_video_id = data['id']

    db.session.add(new_report)
    db.session.commit()

    return jsonify({'success': True})

@app.route('/submit_report', methods=['POST'])
@login_required
def submit_report():
    try:
        data = request.get_json()

        if not data or not all(k in data for k in ['type', 'id', 'reason', 'description']):
            return jsonify({'success': False, 'error': 'Geçersiz istek.'})

        report_type = data['type']
        reported_id = data['id']
        reason = data['reason']
        description = data['description']

        if report_type == 'comment':
            comment = Comment.query.get(reported_id)
            if not comment:
                return jsonify({'success': False, 'error': 'Yorum bulunamadı.'})

            if comment.user_id == current_user.id:
                return jsonify({'success': False, 'error': 'Kendi yorumunuzu bildiremezsiniz.'})

            report = Report(
                reporter_id=current_user.id,
                reported_comment_id=reported_id,
                reason=f"{reason}: {description}",
                status='pending'
            )

        elif report_type == 'user':
            reported_user = User.query.get(reported_id)
            if not reported_user:
                return jsonify({'success': False, 'error': 'Kullanıcı bulunamadı.'})

            if reported_user.id == current_user.id:
                return jsonify({'success': False, 'error': 'Kendinizi bildiremezsiniz.'})

            report = Report(
                reporter_id=current_user.id,
                reported_user_id=reported_id,
                reason=f"{reason}: {description}",
                status='pending'
            )

        elif report_type == 'video':

            pass

        else:
            return jsonify({'success': False, 'error': 'Geçersiz bildirim türü.'})

        db.session.add(report)
        db.session.commit()

        admins = User.query.filter_by(is_admin=True).all()
        for admin in admins:
            notification = Notification(
                recipient_id=admin.id,
                sender_id=current_user.id,
                type='new_report',
                content=f'Yeni bir {reason} bildirimi yapıldı.'
            )
            db.session.add(notification)

        db.session.commit()

        return jsonify({'success': True})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/mod_panel/reports')
@login_required
@admin_required
def mod_panel_reports():
    reports = Report.query.order_by(Report.created_at.desc()).all()
    current_time = datetime.now()

    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    return render_template('mod_panel/mod_panel_reports.html',
                         reports=reports,
                         current_time=today_start)

@app.route('/mod_panel/logs')
@login_required
@admin_required
def mod_panel_logs():
    current_time = datetime.now()
    logs = ModLog.query.order_by(ModLog.created_at.desc()).all()
    return render_template('mod_panel/mod_panel_logs.html', logs=logs, current_time=current_time)

@app.route('/report_video', methods=['POST'])
@login_required
def report_video():
    try:
        data = request.get_json()

        if not data or 'video_id' not in data or 'reason' not in data:
            return jsonify({'success': False, 'message': 'Geçersiz istek'}), 400

        video = Video.query.get_or_404(data['video_id'])

        report = Report(
            reporter_id=current_user.id,
            reported_video_id=video.id,
            reason=f"{data['reason']}: {data.get('description', '')}",
            status='pending'
        )

        db.session.add(report)
        db.session.commit()

        notification = Notification(
            recipient_id=video.user_id,
            sender_id=current_user.id,
            type='video_report',
            content=f'Videonuz bildirildi: {video.title}'
        )
        db.session.add(notification)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Bildiriminiz başarıyla alındı'
        })

    except Exception as e:
        db.session.rollback()
        print(f"Hata: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Bir hata oluştu'
        }), 500

@app.route('/update_report_status', methods=['POST'])
@login_required
@admin_required
def update_report_status():
    if not request.is_json:
        return jsonify({'success': False, 'message': 'JSON verisi gerekli'}), 400

    data = request.get_json()
    report_id = data.get('report_id')
    status = data.get('status')

    if not report_id or not status:
        return jsonify({'success': False, 'message': 'Eksik parametreler'}), 400

    if status not in ['pending', 'resolved', 'rejected']:
        return jsonify({'success': False, 'message': 'Geçersiz durum'}), 400

    try:

        report = Report.query.get(report_id)
        if not report:
            return jsonify({'success': False, 'message': 'Rapor bulunamadı'}), 404

        report.status = status
        report.resolved_by = current_user.id
        report.resolved_at = datetime.now()
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Rapor durumu güncellendi'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': 'Bir hata oluştu'
        }), 500

@app.route('/resolve_report/<int:report_id>', methods=['POST'])
@login_required
@admin_required
def resolve_report(report_id):
    try:
        report = Report.query.get_or_404(report_id)
        report.status = 'approved'  
        report.resolved_by = current_user.id
        report.resolved_at = datetime.utcnow()

        notification = Notification(
            recipient_id=report.reporter_id,
            sender_id=current_user.id,
            type='report_resolved',
            content=f'Raporunuz onaylandı ve gerekli işlem yapıldı.'
        )

        db.session.add(notification)
        db.session.commit()

        return jsonify({'success': True})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/dismiss_report/<int:report_id>', methods=['POST'])
@login_required
@admin_required
def dismiss_report(report_id):
    try:
        report = Report.query.get_or_404(report_id)
        report.status = 'rejected'  
        report.resolved_by = current_user.id
        report.resolved_at = datetime.utcnow()

        notification = Notification(
            recipient_id=report.reporter_id,
            sender_id=current_user.id,
            type='report_dismissed',
            content=f'Raporunuz incelendi ve reddedildi.'
        )

        db.session.add(notification)
        db.session.commit()

        return jsonify({'success': True})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.before_request
def check_maintenance():
    if maintenance_mode and \
       not current_user.is_authenticated and \
       request.endpoint != 'maintenance' and \
       request.endpoint != 'login' and \
       request.endpoint != 'static':
        return redirect(url_for('maintenance'))

@app.route('/maintenance')
def maintenance():
    return render_template('maintenance.html')

@app.route('/create_account', methods=['POST'])
@login_required
@admin_required
def create_account():
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    is_admin = request.form.get('is_admin') == 'on'

    if User.query.filter_by(username=username).first():
        flash('Bu kullanıcı adı zaten kullanılıyor.', 'error')
        return redirect(url_for('mod_panel'))

    if User.query.filter_by(email=email).first():
        flash('Bu e-posta adresi zaten kullanılıyor.', 'error')
        return redirect(url_for('mod_panel'))

    new_user = User(
        username=username,
        email=email,
        is_admin=is_admin
    )
    new_user.set_password(password)

    db.session.add(new_user)
    db.session.commit()

    flash('Hesap başarıyla oluşturuldu.', 'success')
    return redirect(url_for('mod_panel'))

@app.route('/change_username/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def change_username(user_id):
    data = request.get_json()
    new_username = data.get('new_username')

    if not new_username:
        return jsonify({'success': False, 'error': 'Kullanıcı adı boş olamaz.'})

    if len(new_username) > 32:
        return jsonify({'success': False, 'error': 'Kullanıcı adı 32 karakterden uzun olamaz.'})

    if not new_username.isascii():
        return jsonify({'success': False, 'error': 'Kullanıcı adı sadece İngilizce karakterler içerebilir.'})

    if not all(c.isalnum() or c in '-_' for c in new_username):
        return jsonify({'success': False, 'error': 'Kullanıcı adı sadece harf, rakam, tire (-) ve alt çizgi (_) içerebilir.'})

    user = User.query.get_or_404(user_id)

    username_lower = new_username.lower()
    existing_user = User.query.filter(
        and_(
            func.lower(User.username) == username_lower,
            User.id != user_id
        )
    ).first()

    if existing_user:
        return jsonify({'success': False, 'error': 'Bu kullanıcı adı zaten kullanılıyor.'})

    user.username = new_username
    db.session.commit()

    return jsonify({'success': True})

@app.route('/settings')
@login_required
def settings():
    return render_template('settings.html', user=current_user)

@app.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    try:
        if 'profile_image' in request.files:
            profile_image = request.files['profile_image']

            if profile_image and profile_image.filename:

                image = Image.open(profile_image)

                if image.format != 'PNG':
                    png_buffer = io.BytesIO()
                    image.save(png_buffer, format='PNG')
                    image = Image.open(png_buffer)

                if current_user.profile_image and current_user.profile_image != 'default.jpg':
                    try:
                        old_path = os.path.join(app.root_path, 'static/profile_images', current_user.profile_image)
                        if os.path.exists(old_path):
                            os.remove(old_path)
                    except Exception as e:
                        print(f"Eski profil resmi silinirken hata: {str(e)}")

                filename = secure_filename(f"profile_{current_user.id}_{int(time.time())}.png")
                save_path = os.path.join(app.root_path, 'static/profile_images', filename)

                os.makedirs(os.path.dirname(save_path), exist_ok=True)

                image.save(save_path, 'PNG', optimize=True)

                current_user.profile_image = filename
                db.session.commit()

                return jsonify({'success': True})

        new_username = request.form.get('username')
        if new_username and new_username != current_user.username:

            if len(new_username) > 32:
                return jsonify({'success': False, 'error': 'Kullanıcı adı 32 karakterden uzun olamaz.'})

            if not new_username.isascii():
                return jsonify({'success': False, 'error': 'Kullanıcı adı sadece İngilizce karakterler içerebilir.'})

            if not all(c.isalnum() or c in '-_' for c in new_username):
                return jsonify({'success': False, 'error': 'Kullanıcı adı sadece harf, rakam, tire (-) ve alt çizgi (_) içerebilir.'})

            username_lower = new_username.lower()
            existing_user = User.query.filter(
                and_(
                    func.lower(User.username) == username_lower,
                    User.id != current_user.id
                )
            ).first()

            if existing_user:
                return jsonify({'success': False, 'error': 'Bu kullanıcı adı zaten kullanılıyor.'})

            current_user.username = new_username

        new_email = request.form.get('email')
        if new_email and new_email != current_user.email:
            if User.query.filter(User.email == new_email, User.id != current_user.id).first():
                return jsonify({'success': False, 'error': 'Bu e-posta adresi zaten kullanılıyor.'})
            current_user.email = new_email

        db.session.commit()
        return jsonify({'success': True})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

def add_missing_comment_columns():
    with app.app_context():
        try:
            db.engine.execute()
            print("Comment tablosu sütunları başarıyla eklendi")
        except Exception as e:
            print(f"Sütunlar zaten mevcut veya bir hata oluştu: {str(e)}")

def migrate_database():
    try:

        with app.app_context():

            inspector = sa.inspect(db.engine)
            existing_columns = [c['name'] for c in inspector.get_columns('comment')]

            with db.engine.begin() as conn:
                if 'is_edited' not in existing_columns:
                    conn.execute('ALTER TABLE comment ADD COLUMN is_edited BOOLEAN DEFAULT FALSE')

                if 'edited_at' not in existing_columns:
                    conn.execute('ALTER TABLE comment ADD COLUMN edited_at TIMESTAMP')

                if 'created_at' not in existing_columns:
                    conn.execute()

                if 'user_id' not in existing_columns:
                    conn.execute('ALTER TABLE comment ADD COLUMN user_id INTEGER REFERENCES user(id)')

                if 'video_id' not in existing_columns:
                    conn.execute('ALTER TABLE comment ADD COLUMN video_id INTEGER REFERENCES video(id)')

            existing_columns = [c['name'] for c in inspector.get_columns('video')]

            with db.engine.begin() as conn:
                if 'view_count' not in existing_columns:
                    conn.execute('ALTER TABLE video ADD COLUMN view_count INTEGER DEFAULT 0')

                if 'upload_date' not in existing_columns:
                    conn.execute()

                if 'description' not in existing_columns:
                    conn.execute('ALTER TABLE video ADD COLUMN description TEXT')

            existing_columns = [c['name'] for c in inspector.get_columns('user')]

            with db.engine.begin() as conn:
                if 'profile_picture' not in existing_columns:
                    conn.execute('ALTER TABLE user ADD COLUMN profile_picture TEXT')

                if 'join_date' not in existing_columns:
                    conn.execute()

                if 'is_banned' not in existing_columns:
                    conn.execute('ALTER TABLE user ADD COLUMN is_banned BOOLEAN DEFAULT FALSE')

        print("Veritabanı migrasyonu başarıyla tamamlandı.")

    except Exception as e:
        print(f"Migrasyon sırasında bir hata oluştu: {str(e)}")

        pass

@app.route('/add_channel_comment/<int:user_id>', methods=['POST'])
@login_required
def add_channel_comment(user_id):
    content = request.form.get('content')
    if not content:
        flash('Yorum içeriği boş olamaz.', 'error')
        return redirect(url_for('profile', user_id=user_id))

    user = User.query.get_or_404(user_id)

    comment = ChannelComment(
        content=content,
        channel_id=user.id,
        author_id=current_user.id
    )

    notification = Notification(
        recipient_id=user.id,
        sender_id=current_user.id,
        type='channel_comment',
        content=f'{current_user.username} kanalınıza yorum yaptı: {content[:50]}...'
    )

    db.session.add(comment)
    db.session.add(notification)
    db.session.commit()

    flash('Yorumunuz eklendi.', 'success')
    return redirect(url_for('profile', username=user.username))

@app.route('/channel-comment/<int:comment_id>/delete', methods=['POST'])
@login_required
def delete_channel_comment(comment_id):
    comment = ChannelComment.query.get_or_404(comment_id)

    if not (current_user.id == comment.author_id or 
            current_user.id == comment.channel_id or 
            current_user.is_admin):
        flash('Bu işlem için yetkiniz yok.', 'error')
        return redirect(url_for('profile', username=comment.channel.username))

    db.session.delete(comment)
    db.session.commit()
    flash('Yorum başarıyla silindi.', 'success')
    return redirect(url_for('profile', username=comment.channel.username))

@app.route('/channel-comment/<int:comment_id>/edit', methods=['POST'])
@login_required
def edit_channel_comment(comment_id):
    comment = ChannelComment.query.get_or_404(comment_id)

    if current_user.id != comment.author_id:
        flash('Bu işlem için yetkiniz yok.', 'error')
        return redirect(url_for('profile', username=comment.channel.username))

    content = request.form.get('content')
    if not content:
        flash('Yorum boş olamaz.', 'error')
        return redirect(url_for('profile', username=comment.channel.username))

    comment.content = content
    db.session.commit()
    flash('Yorum başarıyla güncellendi.', 'success')
    return redirect(url_for('profile', username=comment.channel.username))

@app.route('/get_notifications')
@limiter.limit("60 per minute")  
@login_required
def get_notifications():
    notifications = Notification.query.filter_by(
        recipient_id=current_user.id,
        is_read=False
    ).order_by(Notification.created_at.desc()).limit(10).all()

    return jsonify([{
        'id': notif.id,
        'message': notif.content,
        'type': notif.type,
        'time_ago': humanize_time(notif.created_at),
        'sender_image': url_for('static', filename=f'profile_images/{notif.sender.profile_image}') if notif.sender.profile_image else url_for('static', filename='images/default.jpg'),
        'sender_username': notif.sender.username,
        'link': generate_notification_link(notif)
    } for notif in notifications])

@app.route('/mark_all_notifications_read', methods=['POST'])
@limiter.limit("10 per minute")  
@login_required
def mark_all_notifications_read():
    Notification.query.filter_by(
        recipient_id=current_user.id,
        is_read=False
    ).update({Notification.is_read: True})

    db.session.commit()
    return jsonify({'success': True})

@app.route('/notifications')
@login_required
def notifications():
    page = request.args.get('page', 1, type=int)
    notifications = Notification.query.filter_by(
        recipient_id=current_user.id
    ).order_by(Notification.created_at.desc()).paginate(
        page=page, per_page=20
    )
    return render_template('notifications.html', 
                         notifications=notifications,
                         now=datetime.utcnow())

def humanize_time(dt):
    """Tarih/saat bilgisini insan dostu formata çevirir"""
    now = datetime.utcnow()
    diff = now - dt

    if diff.days > 7:
        return dt.strftime('%d.%m.%Y')
    elif diff.days > 0:
        return f"{diff.days} gün önce"
    elif diff.seconds > 3600:
        return f"{diff.seconds // 3600} saat önce"
    elif diff.seconds > 60:
        return f"{diff.seconds // 60} dakika önce"
    else:
        return "Az önce"

def generate_notification_link(notification):
    """Bildirim türüne göre yönlendirme linki oluşturur"""
    try:
        if notification.type == 'channel_comment':
            return url_for('profile', username=notification.sender.username)
        elif notification.type == 'video_comment':
            try:
                video_id = notification.content.split('|')[1].strip()
                return url_for('watch', video_id=int(video_id))
            except (IndexError, ValueError):
                return '#'
        elif notification.type in ['report_resolved', 'report_dismissed']:
            try:
                report_id = notification.content.split('|')[1].strip()
                report = Report.query.get(int(report_id))
                if report and report.reported_video_id:
                    return url_for('watch', video_id=report.reported_video_id)
                elif report and report.reported_user_id:
                    user = User.query.get(report.reported_user_id)
                    if user:
                        return url_for('profile', username=user.username)
            except (IndexError, ValueError):
                pass
    except Exception as e:
        print(f"Bildirim bağlantısı oluşturulurken hata: {str(e)}")
    return '#'

@app.route('/privacy-policy')
def privacy_policy():
    return render_template('privacy_policy.html')

@app.route('/terms')
def terms():
    return render_template('terms.html')

@app.route('/kvkk')
def kvkk():
    return render_template('kvkk.html')

@app.route('/docs/api')
def api_documentation():
    rate_limits = {
        'video_action': '30 per minute',
        'add_comment': '10 per minute',
        'edit_comment': '20 per minute',
        'delete_comment': '10 per minute',
        'get_notifications': '60 per minute',
        'mark_notifications': '10 per minute'
    }
    return render_template('api/index.html', rate_limits=rate_limits)

@app.errorhandler(429)  
def ratelimit_handler(e):

    if request.path.startswith('/api/'):
        return jsonify({
            'success': False,
            'error': 'Rate limit aşıldı. Lütfen daha sonra tekrar deneyin.',
            'retry_after': e.description
        }), 429

    flash('Çok fazla istek gönderdiniz. Lütfen bir süre bekleyin.', 'error')
    return redirect(url_for('index'))

@app.before_request
def track_visitors():
    visitor_ip = get_real_ip()
    current_time = time.time()

    global active_visitors
    active_visitors = {ip for ip in active_visitors if (current_time - active_visitors_last_seen.get(ip, 0)) < 300}

    if visitor_ip not in active_visitors:
        active_visitors.add(visitor_ip)
    active_visitors_last_seen[visitor_ip] = current_time

@app.context_processor
def inject_visitor_count():
    return {'active_visitors': len(active_visitors)}

@app.before_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.utcnow()
        db.session.commit()

    exempt_endpoints = {'static', 'maintenance', 'login', 'logout', 'banned'}

    if request.endpoint in exempt_endpoints:
        return

    if maintenance_mode and not (current_user.is_authenticated and current_user.is_admin):
        return redirect(url_for('maintenance'))

    if current_user.is_authenticated:
        if current_user.is_banned and request.endpoint not in {'logout', 'banned'}:
            return redirect(url_for('banned'))

@app.route('/banned')
def banned():

    if request.args.get('preview') == 'true':
        class PreviewBan:
            created_at = datetime.now()
            reason = "Kurallara aykırı davranış (Önizleme)"
            expiry_date = datetime.now() + timedelta(days=7)

        class PreviewUser:
            latest_ban = PreviewBan()

        preview_user = PreviewUser()
        return render_template('banned.html', current_user=preview_user)

    return render_template('banned.html')

@app.route('/mod_panel/update_status', methods=['POST'])
@login_required
@admin_required
def update_status():
    try:
        color = request.form.get('color', '#000000')
        text = request.form.get('text', '')

        site_settings = SiteSettings.query.first()
        if not site_settings:
            site_settings = SiteSettings()
            db.session.add(site_settings)

        site_settings.status_color = color
        site_settings.status_text = text
        db.session.commit()

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/comments/<int:comment_id>/delete', methods=['POST'])
@login_required
def delete_comment(comment_id):
    try:
        comment = Comment.query.get_or_404(comment_id)
        video = Video.query.get(comment.video_id)

        if not (comment.user_id == current_user.id or 
                video.user_id == current_user.id or 
                current_user.is_admin):
            return jsonify({'success': False, 'error': 'Bu yorumu silme yetkiniz yok'}), 403

        db.session.delete(comment)
        db.session.commit()

        return jsonify({'success': True})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/delete_video/<int:video_id>/<int:report_id>', methods=['POST'])
@login_required
def delete_video_from_report(video_id, report_id):
    if not current_user.is_admin:
        return jsonify({'success': False, 'error': 'Yetkiniz yok'})

    video = Video.query.get_or_404(video_id)
    report = Report.query.get_or_404(report_id)

    try:

        db.session.delete(video)

        mod_log = ModLog(
            admin_id=current_user.id,
            action_type='delete_video',
            target_video_id=video_id,
            details=f"Rapor ID: {report_id}, Sebep: {report.reason}"
        )
        db.session.add(mod_log)

        report.status = 'resolved'
        db.session.commit()

        target = f"{video.title} (ID: {video.id})"
        details = f"Yükleyen: {video.uploader.username}"
        send_to_discord('delete_video', current_user, target, details)

        return jsonify({'success': True})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/getVideo', methods=['POST'])
def get_video():
    try:
        video_id = request.args.get('videoID')
        if not video_id:
            return jsonify({
                'error': 'Video ID gerekli',
                'code': 400
            }), 400

        video = Video.query.get(video_id)
        if not video:
            return jsonify({
                'error': 'Video bulunamadı',
                'code': 404
            }), 404

        if not video.is_visible:
            return jsonify({
                'error': 'Bu videoyu görüntüleme yetkiniz yok',
                'code': 403
            }), 403

        return jsonify({
            'title': video.title,
            'description': video.description,
            'thumbnail_url': url_for('static', filename=video.thumbnail, _external=True),
            'video_url': url_for('static', filename=f'uploads/videos/{video.filename}', _external=True),
            'postdate': video.upload_date.strftime('%d %b %Y'),
            'viewcount': video.views,
            'like': video.get_likes(),
            'midlike': video.get_mid_likes(), 
            'dislike': video.get_dislikes()
        })

    except Exception as e:
        return jsonify({
            'error': 'Sunucu hatası',
            'details': str(e),
            'code': 500
        }), 500

@app.route('/update_about', methods=['POST'])
@login_required
def update_about():
    try:
        if not request.is_json:
            return jsonify({'success': False, 'error': 'JSON verisi gerekli'}), 400

        data = request.get_json()
        about = data.get('about', '').strip()

        if len(about) > 2500:
            return jsonify({'success': False, 'error': 'Açıklama 2500 karakterden uzun olamaz.'})

        current_user.about = about
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Profil açıklaması başarıyla güncellendi'
        })

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Profil güncelleme hatası: {str(e)}")
        return jsonify({
            'success': False, 
            'error': 'Profil güncellenirken bir hata oluştu'
        }), 500

@app.route('/update_banner', methods=['POST'])
@login_required
def update_banner():
    try:
        if 'banner_image' in request.files:
            banner_image = request.files['banner_image']

            if banner_image and banner_image.filename:

                image = Image.open(banner_image)

                if image.format != 'PNG':
                    png_buffer = io.BytesIO()
                    image.save(png_buffer, format='PNG')
                    image = Image.open(png_buffer)

                if current_user.banner_image and current_user.banner_image != 'default_banner.jpg':
                    try:
                        old_path = os.path.join(app.root_path, 'static/banner_images', current_user.banner_image)
                        if os.path.exists(old_path):
                            os.remove(old_path)
                    except Exception as e:
                        print(f"Eski banner silinirken hata: {str(e)}")

                filename = secure_filename(f"banner_{current_user.id}_{int(time.time())}.png")
                save_path = os.path.join(app.root_path, 'static/banner_images', filename)

                os.makedirs(os.path.dirname(save_path), exist_ok=True)

                image.save(save_path, 'PNG', optimize=True)

                current_user.banner_image = filename
                db.session.commit()

                return jsonify({'success': True})

        return jsonify({'success': False, 'error': 'Banner yüklenemedi'})

    except Exception as e:
        print(f"Banner güncelleme hatası: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/reset_banner', methods=['POST'])
@login_required
def reset_banner():
    try:

        if current_user.banner_image and current_user.banner_image != 'default_banner.jpg':
            try:
                old_banner_path = os.path.join(app.root_path, 'static/banner_images', current_user.banner_image)
                if os.path.exists(old_banner_path):
                    os.remove(old_banner_path)
            except Exception as e:
                print(f"Eski banner silinirken hata: {str(e)}")

        current_user.banner_image = 'default_banner.jpg'
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Banner başarıyla sıfırlandı'
        })

    except Exception as e:
        db.session.rollback()
        print(f"Banner sıfırlama hatası: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Banner sıfırlanırken bir hata oluştu'
        }), 500

@app.route('/api/comments/<int:comment_id>/pin', methods=['POST'])
@login_required
def pin_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    video = comment.video_ref

    if current_user.id != video.user_id:
        abort(403)

    if video.pin_comment(comment_id):
        return jsonify({'success': True})
    return jsonify({'success': False})

@app.route('/api/comments/<int:comment_id>/unpin', methods=['POST'])
@login_required
def unpin_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    video = comment.video_ref

    if current_user.id != video.user_id:
        abort(403)

    if video.unpin_comment():
        return jsonify({'success': True})
    return jsonify({'success': False})

@app.before_request
def check_ip_ban():
    if request.endpoint in {'static', 'banned_ip'}:
        return

    ip = get_real_ip()
    ip_ban = IPBan.query.filter_by(
        ip_address=ip,
        is_active=True
    ).first()

    if ip_ban and not ip_ban.is_expired:
        return redirect(url_for('banned_ip'))

@app.route('/banned_ip')
def banned_ip():
    ip = get_real_ip()
    ban = IPBan.query.filter_by(
        ip_address=ip,
        is_active=True
    ).first()

    if not ban:
        return redirect(url_for('index'))

    return render_template('banned_ip.html', ban=ban)

@app.route('/mod_panel/ip_bans')
@login_required
@admin_required
def ip_bans():
    current_time = datetime.utcnow()
    bans = IPBan.query.order_by(IPBan.created_at.desc()).all()
    return render_template('mod_panel/ip_bans.html', 
                         bans=bans, 
                         current_time=current_time,
                         active_tab='ip_bans')

@app.route('/mod_panel/ban_ip', methods=['POST'])
@login_required
@admin_required
def ban_ip():
    try:
        ip = request.form.get('ip')
        reason = request.form.get('reason')
        duration = request.form.get('duration')  

        if not ip or not reason:
            return jsonify({
                'success': False,
                'error': 'IP adresi ve sebep gerekli'
            }), 400

        try:
            ipaddress.ip_address(ip)
        except ValueError:
            return jsonify({
                'success': False,
                'error': 'Geçersiz IP adresi'
            }), 400

        expiry_date = None
        if duration:
            try:
                days = int(duration)
                expiry_date = datetime.utcnow() + timedelta(days=days)
            except ValueError:
                return jsonify({
                    'success': False,
                    'error': 'Geçersiz süre'
                }), 400

        existing_ban = IPBan.query.filter_by(
            ip_address=ip,
            is_active=True
        ).first()

        if existing_ban:
            return jsonify({
                'success': False,
                'error': 'Bu IP zaten banlanmış'
            }), 400

        ban = IPBan(
            ip_address=ip,
            reason=reason,
            banned_by_id=current_user.id,
            expiry_date=expiry_date
        )

        db.session.add(ban)
        db.session.commit()

        send_to_discord(
            'ip_ban',
            current_user,
            f"IP: {ip}",
            f"Sebep: {reason}\nSüre: {duration if duration else 'Süresiz'}"
        )

        return jsonify({'success': True})

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"IP ban hatası: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/mod_panel/unban_ip/<int:ban_id>', methods=['POST'])
@login_required
@admin_required
def unban_ip(ban_id):
    try:
        ban = IPBan.query.get_or_404(ban_id)
        ban.is_active = False
        db.session.commit()

        send_to_discord(
            'ip_unban',
            current_user,
            f"IP: {ban.ip_address}",
            f"Önceki Ban Sebebi: {ban.reason}"
        )

        return jsonify({'success': True})

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/change_password', methods=['POST'])
@login_required
def change_password():
    try:
        data = request.get_json()
        old_password = data.get('old_password')
        new_password = data.get('new_password')

        if not old_password or not new_password:
            return jsonify({
                'success': False,
                'message': 'Eski ve yeni şifre gerekli'
            }), 400

        if not current_user.check_password(old_password):
            return jsonify({
                'success': False,
                'message': 'Mevcut şifre yanlış'
            }), 400

        if len(new_password) < 6:
            return jsonify({
                'success': False,
                'message': 'Şifre en az 6 karakter olmalıdır'
            }), 400

        current_user.set_password(new_password)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Şifreniz başarıyla güncellendi'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': 'Şifre değiştirirken bir hata oluştu'
        }), 500

@app.route('/upload_chunk', methods=['POST'])
@login_required
def upload_chunk():
    try:
        app.logger.info("Chunk yükleme başladı")

        if 'chunk' not in request.files:
            app.logger.error("Chunk bulunamadı")
            return jsonify({'success': False, 'error': 'Chunk bulunamadı'}), 400

        chunk = request.files['chunk']
        chunk_number = int(request.form['chunkNumber'])
        total_chunks = int(request.form['totalChunks'])
        original_filename = request.form['filename']

        app.logger.info(f"Chunk bilgileri: {chunk_number + 1}/{total_chunks} - {original_filename}")

        temp_filename = secure_filename(f"{current_user.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{original_filename}")
        chunk_path = os.path.join(TEMP_UPLOAD_FOLDER, f"{temp_filename}.part{chunk_number}")

        app.logger.info(f"Chunk kaydediliyor: {chunk_path}")

        chunk.save(chunk_path)

        app.logger.info(f"Chunk başarıyla kaydedildi: {chunk_path}")

        if chunk_number == total_chunks - 1:
            app.logger.info("Son chunk, dosya birleştiriliyor...")

            final_filename = secure_filename(f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{original_filename}")
            final_path = os.path.join(FINAL_UPLOAD_FOLDER, final_filename)

            try:
                with open(final_path, 'wb') as outfile:
                    for i in range(total_chunks):
                        part_path = os.path.join(TEMP_UPLOAD_FOLDER, f"{temp_filename}.part{i}")
                        if os.path.exists(part_path):
                            with open(part_path, 'rb') as infile:
                                outfile.write(infile.read())
                            os.remove(part_path)
                            app.logger.info(f"Chunk silindi: {part_path}")

                chunk_pattern = os.path.join(TEMP_UPLOAD_FOLDER, f"{temp_filename}.part*")
                for remaining_chunk in glob.glob(chunk_pattern):
                    try:
                        os.remove(remaining_chunk)
                        app.logger.info(f"Kalan chunk silindi: {remaining_chunk}")
                    except Exception as e:
                        app.logger.error(f"Chunk silme hatası: {str(e)}")

                app.logger.info(f"Dosya başarıyla birleştirildi: {final_path}")

                return jsonify({
                    'success': True,
                    'status': 'completed',
                    'filename': final_filename
                })

            except Exception as e:
                app.logger.error(f"Dosya birleştirme hatası: {str(e)}")
                cleanup_chunks(temp_filename)
                raise e

        return jsonify({
            'success': True,
            'status': 'chunk_uploaded',
            'chunkNumber': chunk_number
        })

    except Exception as e:
        app.logger.error(f"Chunk upload error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

def cleanup_chunks(temp_filename):
    """Belirli bir yüklemeye ait tüm chunk'ları temizler"""
    try:
        chunk_pattern = os.path.join(TEMP_UPLOAD_FOLDER, f"{temp_filename}.part*")
        for chunk_file in glob.glob(chunk_pattern):
            try:
                os.remove(chunk_file)
                app.logger.info(f"Chunk temizlendi: {chunk_file}")
            except Exception as e:
                app.logger.error(f"Chunk temizleme hatası ({chunk_file}): {str(e)}")
    except Exception as e:
        app.logger.error(f"Chunk temizleme hatası: {str(e)}")

os.makedirs(TEMP_UPLOAD_FOLDER, exist_ok=True)
os.makedirs(FINAL_UPLOAD_FOLDER, exist_ok=True)

@app.route('/mod_panel/server')
@login_required
@admin_required
def mod_panel_server():
    def get_size(bytes):
        """Byte'ları okunaklı formata çevirir"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes < 1024:
                return f"{bytes:.2f} {unit}"
            bytes /= 1024

    def get_recent_logs(lines=50):
        """Son log kayıtlarını getirir"""
        try:
            with open('app.log', 'r') as f:
                return ''.join(f.readlines()[-lines:])
        except:
            return "Log dosyası bulunamadı"

    system_info = {

        'os': f"{platform.system()} {platform.release()}",
        'python_version': platform.python_version(),
        'flask_version': flask.__version__,

        'cpu_usage': psutil.cpu_percent(),
        'cpu_cores': psutil.cpu_count(),
        'cpu_freq': psutil.cpu_freq().current if hasattr(psutil.cpu_freq(), 'current') else 'N/A',

        'ram_usage': psutil.virtual_memory().percent,
        'ram_total': round(psutil.virtual_memory().total / (1024**3), 2),  
        'ram_available': round(psutil.virtual_memory().available / (1024**3), 2),  

        'disk_usage': psutil.disk_usage('/').percent,
        'disk_total': round(psutil.disk_usage('/').total / (1024**3), 2),
        'disk_free': round(psutil.disk_usage('/').free / (1024**3), 2),

        'active_sessions': len(active_visitors),
        'db_size': get_size(os.path.getsize('site.db')),
        'cache_status': f"{len(cache.cache._cache)} items",

        'network': psutil.net_io_counters(),

        'recent_logs': get_recent_logs()
    }

    try:
        system_info['load_avg'] = os.getloadavg()
    except:
        system_info['load_avg'] = 'N/A'

    try:
        system_info['uptime'] = subprocess.check_output(['uptime']).decode()
    except:
        system_info['uptime'] = 'N/A'

    return render_template('mod_panel/mod_panel_server.html',
                         system_info=system_info,
                         active_tab='server',
                         current_time=datetime.utcnow())

if __name__ == '__main__':
    app.run(
        host='localhost',
        port=3000,
        threaded=True,
        request_handler=WSGIRequestHandler
    )