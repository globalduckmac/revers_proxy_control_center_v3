from app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Секретный ключ для шифрования (можно получить из переменной окружения)
SECRET_KEY = os.environ.get("SESSION_SECRET", "default-secret-key-for-encryption")

def get_encryption_key(secret):
    """Генерирует ключ шифрования на основе секрета"""
    salt = b'static_salt_for_server_passwords'  # Постоянная соль для консистентности
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(secret.encode()))
    return key

def encrypt_password(password):
    """Шифрует пароль для обратимого хранения"""
    if not password:
        return None
    
    key = get_encryption_key(SECRET_KEY)
    f = Fernet(key)
    encrypted = f.encrypt(password.encode())
    return encrypted.decode()

def decrypt_password(encrypted_password):
    """Дешифрует пароль из хранилища"""
    if not encrypted_password:
        return None
    
    key = get_encryption_key(SECRET_KEY)
    f = Fernet(key)
    try:
        decrypted = f.decrypt(encrypted_password.encode())
        return decrypted.decode()
    except Exception as e:
        print(f"Ошибка дешифрования: {e}")
        return None


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_admin = db.Column(db.Boolean, default=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


# Таблица связи между серверами и группами серверов
server_group_association = db.Table('server_group_association',
    db.Column('server_id', db.Integer, db.ForeignKey('server.id', ondelete='CASCADE'), primary_key=True),
    db.Column('server_group_id', db.Integer, db.ForeignKey('server_group.id', ondelete='CASCADE'), primary_key=True)
)

class Server(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    ip_address = db.Column(db.String(45), nullable=False)
    ssh_port = db.Column(db.Integer, default=22)
    ssh_user = db.Column(db.String(64), nullable=False)
    ssh_key = db.Column(db.Text, nullable=True)  # SSH private key for authentication
    ssh_password_hash = db.Column(db.String(256), nullable=True)  # Hashed password storage
    ssh_encrypted_password = db.Column(db.Text, nullable=True)  # Encrypted password for automated checks
    status = db.Column(db.String(20), default='pending')  # pending, active, error
    last_check = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Новые поля для биллинга и оплаты
    comment = db.Column(db.Text, nullable=True)  # Комментарий к серверу
    billing_provider = db.Column(db.String(128), nullable=True)  # Где был куплен сервер
    billing_login = db.Column(db.String(128), nullable=True)  # Логин от биллинга
    billing_password_encrypted = db.Column(db.Text, nullable=True)  # Зашифрованный пароль от биллинга
    payment_date = db.Column(db.Date, nullable=False)  # Дата оплаты сервера (обязательное поле)
    payment_reminder_sent = db.Column(db.Boolean, default=False)  # Флаг отправки напоминания
    
    # Поля для интеграции с Glances
    glances_enabled = db.Column(db.Boolean, default=False)  # Включен ли мониторинг через Glances
    glances_installed = db.Column(db.Boolean, default=False)  # Установлен ли Glances на сервере
    glances_port = db.Column(db.Integer, default=61208)  # Порт для Glances API (по умолчанию 61208)
    glances_web_port = db.Column(db.Integer, default=61209)  # Порт для веб-интерфейса Glances
    glances_status = db.Column(db.String(20), default='not_installed')  # not_installed, active, error
    glances_last_check = db.Column(db.DateTime, nullable=True)  # Время последней проверки Glances
    
    def set_ssh_password(self, password):
        """
        Хеширует и сохраняет пароль SSH с использованием werkzeug.security
        Также сохраняет зашифрованную версию для автоматической проверки
        
        Args:
            password: Пароль в открытом виде
        """
        if password:
            # Хешируем пароль для безопасного хранения (необратимо)
            self.ssh_password_hash = generate_password_hash(password)
            
            # Шифруем пароль для возможности автоматических проверок (обратимо)
            self.ssh_encrypted_password = encrypt_password(password)
        else:
            self.ssh_password_hash = None
            self.ssh_encrypted_password = None
            
    def check_ssh_password(self, password):
        """
        Проверяет соответствие пароля хешу
        
        Args:
            password: Пароль для проверки
            
        Returns:
            bool: True если пароль правильный, False в противном случае
        """
        if not self.ssh_password_hash:
            return False
        return check_password_hash(self.ssh_password_hash, password)
    
    def get_decrypted_password(self):
        """
        Расшифровывает сохраненный пароль для использования в автоматических проверках
        
        Returns:
            str: Расшифрованный пароль или None, если пароля нет
        """
        if not self.ssh_encrypted_password:
            return None
        return decrypt_password(self.ssh_encrypted_password)
    
    @property
    def ssh_password(self):
        """
        Для совместимости с существующим кодом
        При необходимости расшифровывает пароль для автоматических задач
        """
        # Временный пароль для проверки соединения имеет приоритет
        if hasattr(self, '_temp_password') and self._temp_password:
            return self._temp_password
            
        # Если есть зашифрованный пароль, возвращаем расшифрованную версию
        if self.ssh_encrypted_password:
            return self.get_decrypted_password()
            
        # Если ничего нет, невозможно получить пароль
        return None
        
    @ssh_password.setter
    def ssh_password(self, password):
        self.set_ssh_password(password)
    
    def set_billing_password(self, password):
        """
        Шифрует и сохраняет пароль биллинга для обратимого хранения
        
        Args:
            password: Пароль от биллинга в открытом виде
        """
        if password:
            self.billing_password_encrypted = encrypt_password(password)
        else:
            self.billing_password_encrypted = None
    
    def get_billing_password(self):
        """
        Расшифровывает пароль от биллинга
        
        Returns:
            str: Расшифрованный пароль или None, если пароля нет
        """
        if not self.billing_password_encrypted:
            return None
        return decrypt_password(self.billing_password_encrypted)
    
    # Метод для проверки, нужно ли отправить напоминание об оплате
    def check_payment_reminder_needed(self):
        """
        Проверяет, нужно ли отправить напоминание об оплате
        (за два дня до даты оплаты)
        
        Returns:
            bool: True, если напоминание нужно отправить, False - если нет
        """
        if not self.payment_date:
            return False
        
        today = datetime.now().date()
        reminder_date = self.payment_date - timedelta(days=2)
        
        # Если уже отправляли напоминание
        if self.payment_reminder_sent:
            return False
            
        # Если сегодня или позже дня напоминания (за 2 дня до оплаты)
        return today >= reminder_date and today < self.payment_date
    
    # Методы для работы с Glances
    def get_glances_url(self):
        """
        Получает URL для доступа к API Glances
        
        Returns:
            str: URL для доступа к API Glances
        """
        if not self.glances_enabled or not self.glances_installed:
            return None
        return f"http://{self.ip_address}:{self.glances_port}"
    
    def get_glances_web_url(self):
        """
        Получает URL для доступа к веб-интерфейсу Glances
        
        Returns:
            str: URL для доступа к веб-интерфейсу Glances
        """
        if not self.glances_enabled or not self.glances_installed:
            return None
        # Теперь и API, и веб-интерфейс находятся на одном порту 61208
        return f"http://{self.ip_address}:61208"
        
    def get_key_file_path(self):
        """
        Создает временный файл с SSH ключом сервера для подключения.
        
        Returns:
            str: Путь к временному файлу с SSH ключом
        """
        if not self.ssh_key:
            return None
            
        import tempfile
        import os
        
        # Создаем временный файл для SSH ключа
        fd, path = tempfile.mkstemp()
        try:
            with os.fdopen(fd, 'w') as tmp:
                tmp.write(self.ssh_key)
            # Устанавливаем правильные разрешения для ключа
            os.chmod(path, 0o600)
            return path
        except Exception as e:
            print(f"Ошибка при создании временного файла для SSH ключа: {e}")
            try:
                os.remove(path)
            except:
                pass
            return None
    
    # Relationships
    domain_groups = db.relationship('DomainGroup', backref='server', lazy=True, cascade='all, delete-orphan')
    logs = db.relationship('ServerLog', backref='server', lazy=True, cascade='all, delete-orphan')
    # Связь многие-ко-многим с группами серверов
    groups = db.relationship('ServerGroup', secondary=server_group_association, 
                            backref=db.backref('servers', lazy='dynamic'))


class Domain(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, unique=True)
    target_ip = db.Column(db.String(45), nullable=False)
    target_port = db.Column(db.Integer, default=80)
    ssl_enabled = db.Column(db.Boolean, default=False)
    ssl_status = db.Column(db.String(20), default='pending')  # pending, active, error
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Ожидаемые NS-записи, разделенные запятыми
    expected_nameservers = db.Column(db.Text, nullable=True)
    # Статус проверки NS: ok, mismatch, pending
    ns_status = db.Column(db.String(20), default='pending')
    # Фактические NS-записи, разделенные запятыми
    actual_nameservers = db.Column(db.Text, nullable=True)
    # Дата последней проверки NS
    ns_check_date = db.Column(db.DateTime, nullable=True)
    
    # Поля для интеграции с FFPanel
    ffpanel_enabled = db.Column(db.Boolean, default=False)  # Включена ли интеграция с FFPanel
    ffpanel_target_ip = db.Column(db.String(45), nullable=True)  # IP-адрес специально для FFPanel (может отличаться от target_ip)
    ffpanel_id = db.Column(db.Integer, nullable=True)  # ID домена в FFPanel
    ffpanel_status = db.Column(db.String(20), default='not_synced')  # not_synced, synced, error
    ffpanel_port = db.Column(db.String(10), default='80')  # Порт в FFPanel
    ffpanel_port_out = db.Column(db.String(10), default='80')  # Внешний порт в FFPanel
    ffpanel_port_ssl = db.Column(db.String(10), default='443')  # SSL порт в FFPanel
    ffpanel_port_out_ssl = db.Column(db.String(10), default='443')  # Внешний SSL порт в FFPanel
    ffpanel_dns = db.Column(db.String(255), nullable=True)  # DNS в FFPanel
    ffpanel_last_sync = db.Column(db.DateTime, nullable=True)  # Дата последней синхронизации
    
    # Many-to-many relationship with DomainGroup
    groups = db.relationship('DomainGroup', secondary='domain_group_association', 
                            backref=db.backref('domains', lazy='dynamic'))


class DomainGroup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    server_id = db.Column(db.Integer, db.ForeignKey('server.id', ondelete='CASCADE'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# Association table for many-to-many relationship between Domain and DomainGroup
domain_group_association = db.Table('domain_group_association',
    db.Column('domain_id', db.Integer, db.ForeignKey('domain.id', ondelete='CASCADE'), primary_key=True),
    db.Column('domain_group_id', db.Integer, db.ForeignKey('domain_group.id', ondelete='CASCADE'), primary_key=True)
)


class ProxyConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.Integer, db.ForeignKey('server.id', ondelete='CASCADE'), nullable=False)
    config_content = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, deployed, error
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    server = db.relationship('Server', backref=db.backref('proxy_configs', lazy=True, cascade='all, delete-orphan'))


class ServerLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.Integer, db.ForeignKey('server.id', ondelete='CASCADE'), nullable=True)  # Nullable для общесистемных событий
    action = db.Column(db.String(64), nullable=False)  # deploy, configure, check, etc.
    status = db.Column(db.String(20), nullable=False)  # success, error
    message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    
class DomainLog(db.Model):
    """Хранит записи о действиях с доменами и изменениях их статуса."""
    id = db.Column(db.Integer, primary_key=True)
    domain_id = db.Column(db.Integer, db.ForeignKey('domain.id', ondelete='CASCADE'), nullable=False)
    action = db.Column(db.String(64), nullable=False)  # ns_check, status_change, etc.
    status = db.Column(db.String(20), nullable=False)  # success, error, warning
    message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Отношение с моделью Domain
    domain = db.relationship('Domain', backref=db.backref('logs', lazy=True, cascade='all, delete-orphan'))
    
class ServerMetric(db.Model):
    """Stores monitoring metrics for servers."""
    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.Integer, db.ForeignKey('server.id', ondelete='CASCADE'), nullable=False)
    cpu_usage = db.Column(db.Float, nullable=True)
    memory_usage = db.Column(db.Float, nullable=True)
    disk_usage = db.Column(db.Float, nullable=True)
    load_average = db.Column(db.String(30), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    collection_method = db.Column(db.String(20), default='ssh', nullable=True)  # 'ssh' или 'glances_api'
    
    server = db.relationship('Server', backref=db.backref('metrics', lazy=True, cascade='all, delete-orphan'))
    
class ServerGroup(db.Model):
    """Группы серверов для организации и фильтрации."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DomainMetric(db.Model):
    """Stores traffic metrics for domains."""
    id = db.Column(db.Integer, primary_key=True)
    domain_id = db.Column(db.Integer, db.ForeignKey('domain.id', ondelete='CASCADE'), nullable=False)
    requests_count = db.Column(db.Integer, default=0)
    bandwidth_used = db.Column(db.BigInteger, default=0)  # in bytes
    avg_response_time = db.Column(db.Float, nullable=True)  # in milliseconds
    status_2xx_count = db.Column(db.Integer, default=0)
    status_3xx_count = db.Column(db.Integer, default=0)
    status_4xx_count = db.Column(db.Integer, default=0)
    status_5xx_count = db.Column(db.Integer, default=0)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    domain = db.relationship('Domain', backref=db.backref('metrics', lazy=True, cascade='all, delete-orphan'))


class SystemSetting(db.Model):
    """Хранит системные настройки приложения."""
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(64), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=True)
    description = db.Column(db.String(255), nullable=True)
    is_encrypted = db.Column(db.Boolean, default=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    @classmethod
    def get_value(cls, key, default=None):
        """
        Получает значение настройки по ключу.
        Если настройка зашифрована, то автоматически расшифровывает её.
        
        Args:
            key: Ключ настройки
            default: Значение по умолчанию, если настройка не найдена
            
        Returns:
            str: Значение настройки или default, если настройка не найдена
        """
        setting = cls.query.filter_by(key=key).first()
        if not setting:
            return default
            
        if setting.is_encrypted and setting.value:
            try:
                return decrypt_password(setting.value)
            except Exception:
                return default
        
        return setting.value
    
    @classmethod
    def set_value(cls, key, value, description=None, is_encrypted=False):
        """
        Устанавливает значение настройки по ключу.
        Если is_encrypted=True, то значение будет зашифровано.
        
        Args:
            key: Ключ настройки
            value: Значение настройки
            description: Описание настройки (необязательно)
            is_encrypted: Флаг, указывающий, нужно ли шифровать значение
            
        Returns:
            SystemSetting: Объект настройки
        """
        setting = cls.query.filter_by(key=key).first()
        if not setting:
            setting = cls(key=key)
            if description:
                setting.description = description
        
        if is_encrypted and value:
            setting.value = encrypt_password(value)
            setting.is_encrypted = True
        else:
            setting.value = value
            setting.is_encrypted = is_encrypted
        
        db.session.add(setting)
        db.session.commit()
        return setting
