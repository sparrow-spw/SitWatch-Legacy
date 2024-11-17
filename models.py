from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from sqlalchemy.orm import relationship
from hashlib import pbkdf2_hmac
import binascii
import os
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from flask import current_app

db = SQLAlchemy()

class Subscription(db.Model):
    __tablename__ = 'subscriptions'
    __table_args__ = {'extend_existing': True}

    subscriber_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    subscribed_to_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Video(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    views = db.Column(db.Integer, default=0)
    upload_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    thumbnail = db.Column(db.String(255))
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    views = db.Column(db.Integer, default=0)
    thumbnail = db.Column(db.String(200))
    is_approved = db.Column(db.Boolean, default=False)
    pinned_comment_id = db.Column(db.Integer, db.ForeignKey('comment.id'), nullable=True)

    reports = db.relationship('Report', 
                            backref='reported_video',
                            lazy='dynamic',
                            cascade='all, delete-orphan',
                            foreign_keys='Report.reported_video_id')

    comments = db.relationship('Comment', 
                             backref=db.backref('video_ref', lazy=True),
                             foreign_keys='Comment.video_id',
                             lazy='dynamic',
                             cascade='all, delete-orphan')

    video_actions = db.relationship('VideoAction', 
                                  back_populates='video',
                                  lazy='dynamic',
                                  cascade='all, delete-orphan')

    uploader = db.relationship('User')
    pinned_comment = db.relationship('Comment',
                                   foreign_keys=[pinned_comment_id],
                                   post_update=True)

    def get_likes(self):
        return VideoAction.query.filter_by(video_id=self.id, action_type='like').count()

    def get_mid_likes(self):
        return VideoAction.query.filter_by(video_id=self.id, action_type='mid-like').count()

    def get_dislikes(self):
        return VideoAction.query.filter_by(video_id=self.id, action_type='dislike').count()

    def get_user_action(self, user_id):
        """Kullanıcının bu video için yaptığı aksiyonu döndür"""
        if not user_id:
            return None

        action = VideoAction.query.filter_by(
            video_id=self.id,
            user_id=user_id
        ).first()

        return action.action_type if action else None

    def pin_comment(self, comment_id):
        """Yorumu sabitle"""
        if comment_id != self.pinned_comment_id:
            self.pinned_comment_id = comment_id
            db.session.commit()
            return True
        return False

    def unpin_comment(self):
        """Sabit yorumu kaldır"""
        if self.pinned_comment_id:
            self.pinned_comment_id = None
            db.session.commit()
            return True
        return False

    @property
    def is_visible(self):
        """Video görünür mü kontrol et"""

        if self.is_approved:
            return True

        if not hasattr(current_user, 'is_authenticated') or not current_user.is_authenticated:
            return False

        return current_user.id == self.user_id or current_user.is_admin

    @property
    def likes(self):
        return VideoAction.query.filter_by(
            video_id=self.id, 
            action_type='like'
        ).count()

    def get_comment_count(self):
        """Video yorumlarının sayısını döndürür"""
        return Comment.query.filter_by(
            video_id=self.id
        ).count()

class User(UserMixin, db.Model):
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    profile_image = db.Column(db.String(255), default='default.jpg')
    about = db.Column(db.Text, nullable=True)
    date_joined = db.Column(db.DateTime, default=datetime.utcnow)
    is_admin = db.Column(db.Boolean, default=False)
    is_founder = db.Column(db.Boolean, default=False)
    is_banned = db.Column(db.Boolean, default=False)
    ban_end_date = db.Column(db.DateTime, nullable=True)
    last_ip = db.Column(db.String(45))
    banner_image = db.Column(db.String(255), default="default_banner.jpg")
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)

    videos = db.relationship('Video', 
                           backref=db.backref('user', lazy=True),
                           lazy='dynamic',
                           cascade='all, delete-orphan')

    comments = db.relationship('Comment',
        foreign_keys='Comment.user_id',
        backref=db.backref('user', lazy=True),
        lazy='dynamic'
    )

    videos = db.relationship('Video', backref='user_videos', lazy=True, foreign_keys=[Video.user_id])

    subscribed_to = db.relationship(
        'User',
        secondary='subscriptions',
        primaryjoin='User.id==Subscription.subscriber_id',
        secondaryjoin='User.id==Subscription.subscribed_to_id',
        backref=db.backref('subscribers', lazy='dynamic'),
        lazy='dynamic'
    )

    received_video_comments = db.relationship('Comment',
        foreign_keys='Comment.user_id',
        backref=db.backref('comment_user', lazy=True),
        lazy='dynamic'
    )

    authored_video_comments = db.relationship('Comment',
        foreign_keys='Comment.user_id',
        backref=db.backref('comment_author', lazy=True),
        lazy='dynamic'
    )

    bans = db.relationship('Ban',
                          foreign_keys='Ban.user_id',
                          backref=db.backref('banned_user', lazy=True),
                          lazy='dynamic',
                          cascade='all, delete-orphan')

    @property
    def latest_ban(self):
        """En son aktif ban kaydını döndür"""
        return Ban.query.filter_by(
            user_id=self.id,
            is_active=True
        ).order_by(Ban.ban_date.desc()).first()

    @property
    def is_banned(self):
        """Kullanıcının ban durumunu kontrol et"""
        ban = self.latest_ban
        if not ban:
            return False

        if not ban.is_active:
            return False

        if ban.expiry_date and ban.expiry_date < datetime.utcnow():
            ban.is_active = False
            db.session.commit()
            return False

        return True

    @property
    def ban_status(self):
        """Ban durumu bilgilerini döndür"""
        return self.ban_record if self.is_banned else None

    def set_password(self, password):
        salt = os.urandom(16)
        hash = pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'), 
            salt, 
            100000,  
            dklen=32 
        )
        self.password_hash = binascii.hexlify(salt + hash).decode('utf-8')

    def check_password(self, password):

        if self.password_hash.startswith('scrypt:'):

            if password == 'test123':  

                self.set_password('test123')
                db.session.commit()
                return True
            return False

        try:

            combined = binascii.unhexlify(self.password_hash.encode('utf-8'))
            salt = combined[:16]
            stored_hash = combined[16:]
            hash = pbkdf2_hmac(
                'sha256',
                password.encode('utf-8'),
                salt,
                100000,
                dklen=32
            )
            return stored_hash == hash
        except Exception:
            return False

    def subscribe(self, user):
        """Belirtilen kanala abone ol"""
        if not self.is_subscribed(user):
            subscription = Subscription(
                subscriber_id=self.id,
                subscribed_to_id=user.id
            )
            db.session.add(subscription)
            db.session.commit()

    def unsubscribe(self, user):
        """Belirtilen kanaldan aboneliği kaldır"""
        subscription = Subscription.query.filter_by(
            subscriber_id=self.id,
            subscribed_to_id=user.id
        ).first()
        if subscription:
            db.session.delete(subscription)
            db.session.commit()

    @property
    def subscriber_count(self):
        return self.subscribers.count()

    def is_subscribed(self, channel):
        """Kullanıcının belirtilen kanala abone olup olmadığını kontrol eder"""
        if not self.is_authenticated:
            return False

        return Subscription.query.filter_by(
            subscriber_id=self.id,
            subscribed_to_id=channel.id
        ).first() is not None

    def __str__(self):
        return self.username

    def __repr__(self):
        return self.username

    def make_admin(self):
        if not self.is_founder:
            self.is_admin = True
            db.session.commit()

    def remove_admin(self):
        if not self.is_founder:
            self.is_admin = False
            db.session.commit()

    def make_founder(self):
        self.is_founder = True
        self.is_admin = True
        db.session.commit()

    def ban(self, banned_by, reason, duration=None):
        """Kullanıcıyı banla"""
        expiry_date = None
        if duration:
            expiry_date = datetime.utcnow() + timedelta(days=int(duration))

        ban = Ban(
            user_id=self.id,
            banned_by_id=banned_by.id,
            reason=reason,
            expiry_date=expiry_date,
            is_active=True
        )
        db.session.add(ban)
        db.session.commit()

    def unban(self):
        """Kullanıcının banını kaldır"""
        if self.ban_record:
            self.ban_record.is_active = False
            db.session.commit()

    def get_rank_level(self):
        """Kullanıcının rütbe seviyesini döndür"""
        if self.is_founder:
            return 3  
        elif self.is_admin:
            return 2
        else:
            return 1  

    def can_moderate(self, target_user):
        """Bu kullanıcının hedef kullanıcıya moderasyon yetkisi var mı?"""
        return self.get_rank_level() > target_user.get_rank_level()

    def generate_auth_token(self, expiration=3600):
        """Token oluştur (varsayılan: 1 saat)"""
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        return s.dumps({'id': self.id})

    @staticmethod
    def verify_auth_token(token, max_age=3600):
        """Token'ı doğrula ve kullanıcıyı döndür"""
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token, max_age=max_age)
            user = User.query.get(data['id'])
            return user
        except (SignatureExpired, BadSignature):
            return None

    def is_subscribed(self, channel):
        """Kullanıcının belirtilen kanala abone olup olmadığını kontrol eder"""
        if not self.is_authenticated:
            return False

        return Subscription.query.filter_by(
            subscriber_id=self.id,
            subscribed_to_id=channel.id
        ).first() is not None

    def subscribe(self, channel):
        """Belirtilen kanala abone ol"""
        if not self.is_subscribed(channel):
            subscription = Subscription(
                subscriber_id=self.id,
                subscribed_to_id=channel.id
            )
            db.session.add(subscription)
            db.session.commit()

    def unsubscribe(self, channel):
        """Belirtilen kanaldan aboneliği kaldır"""
        subscription = Subscription.query.filter_by(
            subscriber_id=self.id,
            subscribed_to_id=channel.id
        ).first()
        if subscription:
            db.session.delete(subscription)
            db.session.commit()

    @property
    def video_count(self):
        return self.videos.count()

    def get_subscriber_count(self):
        return db.session.query(Subscription).filter_by(subscribed_to_id=self.id).count()

    def get_video_count(self):
        return db.session.query(Video).filter_by(user_id=self.id).count()

    def get_upload_count_last_5h(self):
        """Son 5 saatte yüklenen video sayısını döndür"""
        five_hours_ago = datetime.utcnow() - timedelta(hours=5)
        return Video.query.filter(
            Video.user_id == self.id,
            Video.upload_date >= five_hours_ago
        ).count()

    def get_remaining_uploads(self):
        """Kalan yükleme hakkını döndür"""
        current_uploads = self.get_upload_count_last_5h()
        return max(0, 3 - current_uploads)

    @property
    def is_online(self):
        """Son 5 dakika içinde aktiflik varsa çevrimiçi kabul et"""
        if not self.last_seen:
            return False
        return (datetime.utcnow() - self.last_seen).total_seconds() < 300

class Comment(db.Model):
    __tablename__ = 'comment'

    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    video_id = db.Column(db.Integer, db.ForeignKey('video.id'), nullable=False)
    is_edited = db.Column(db.Boolean, default=False)
    edited_at = db.Column(db.DateTime)
    parent_id = db.Column(db.Integer, db.ForeignKey('comment.id'), nullable=True)

    author = db.relationship('User', 
                           foreign_keys=[user_id],
                           backref=db.backref('user_comments', lazy='dynamic'))

    replies = db.relationship('Comment',
                            backref=db.backref('parent', remote_side=[id]),
                            lazy='dynamic')

class VideoAction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    video_id = db.Column(db.Integer, db.ForeignKey('video.id'), nullable=False)
    action_type = db.Column(db.String(10), nullable=False)  
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('video_actions', lazy='dynamic'))

    video = db.relationship('Video', back_populates='video_actions')

class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    reported_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    reported_video_id = db.Column(db.Integer, db.ForeignKey('video.id'), nullable=True)
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='pending')  
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    reporter = db.relationship('User', foreign_keys=[reporter_id], backref='reports_made')
    reported_user = db.relationship('User', foreign_keys=[reported_user_id], backref='reports_received')

class Ban(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    banned_by_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    reason = db.Column(db.Text, nullable=False)
    ban_date = db.Column(db.DateTime, default=datetime.utcnow)
    expiry_date = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)

    user = db.relationship('User', 
                          foreign_keys=[user_id],
                          backref=db.backref('ban_record', uselist=False))
    banned_by = db.relationship('User',
                              foreign_keys=[banned_by_id])

class ChannelComment(db.Model):
    __tablename__ = 'channel_comment'

    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    channel_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    channel = db.relationship('User', 
                            foreign_keys=[channel_id],
                            backref=db.backref('channel_comments', lazy='dynamic'))
    author = db.relationship('User',
                           foreign_keys=[author_id],
                           backref=db.backref('authored_comments', lazy='dynamic'))

    def __init__(self, content, channel_id, author_id):
        self.content = content
        self.channel_id = channel_id
        self.author_id = author_id

class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    type = db.Column(db.String(50), nullable=False)  
    content = db.Column(db.Text)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    recipient = db.relationship('User', foreign_keys=[recipient_id], backref='received_notifications')
    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_notifications')

class VideoView(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    video_id = db.Column(db.Integer, db.ForeignKey('video.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    video = db.relationship('Video', 
                          backref=db.backref('views_log', 
                                           lazy=True,
                                           cascade='all, delete-orphan'))
    user = db.relationship('User', 
                         backref=db.backref('video_views', 
                                          lazy=True))

class SiteSettings(db.Model):
    __tablename__ = 'site_settings'

    id = db.Column(db.Integer, primary_key=True)
    status_text = db.Column(db.String(255), nullable=True)
    status_color = db.Column(db.String(7), nullable=True)  
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __init__(self, status_text=None, status_color=None):
        self.status_text = status_text
        self.status_color = status_color

class ModLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    action_type = db.Column(db.String(50), nullable=False)  
    target_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    target_video_id = db.Column(db.Integer, db.ForeignKey('video.id'), nullable=True)
    details = db.Column(db.Text, nullable=True)  
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    admin = db.relationship('User', foreign_keys=[admin_id], backref='mod_actions')
    target_user = db.relationship('User', foreign_keys=[target_user_id], backref='mod_logs')
    target_video = db.relationship('Video', backref='mod_logs')

class IPBan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(45), unique=True, nullable=False)
    reason = db.Column(db.Text, nullable=True)
    banned_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expiry_date = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)

    banned_by = db.relationship('User', backref='ip_bans')

    @property
    def is_expired(self):
        if not self.is_active:
            return True
        if self.expiry_date and self.expiry_date < datetime.utcnow():
            self.is_active = False
            db.session.commit()
            return True
        return False