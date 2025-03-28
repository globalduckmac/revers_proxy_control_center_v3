#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Скрипт инициализации базы данных для Reverse Proxy Control Center

Этот скрипт создаёт необходимые таблицы в базе данных при первом запуске.
"""

import logging
import sys
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Импортируем приложение
from app import app, db

# Импортируем все модели для создания таблиц
from models import (Domain, DomainGroup, DomainLog, DomainMetric, ProxyConfig, 
                   Server, ServerGroup, ServerLog, ServerMetric, SystemSetting, 
                   User, domain_group_association, server_group_association)

def update_server_log_schema():
    """
    Обновляет схему таблицы server_log, чтобы server_id мог быть NULL
    для общесистемных событий
    """
    from sqlalchemy import inspect, text
    
    logger.info("Обновление схемы таблицы server_log...")
    
    # Проверяем, существует ли таблица server_log
    inspector = inspect(db.engine)
    if 'server_log' not in inspector.get_table_names():
        logger.info("Таблица server_log не существует, пропускаем обновление")
        return
    
    # Проверяем, является ли server_id NOT NULL
    columns = inspector.get_columns('server_log')
    for column in columns:
        if column['name'] == 'server_id':
            if not column.get('nullable', True):
                # Если server_id NOT NULL, изменяем на NULL
                try:
                    with db.engine.connect() as connection:
                        connection.execute(text(
                            "ALTER TABLE server_log ALTER COLUMN server_id DROP NOT NULL;"
                        ))
                    logger.info("Схема таблицы server_log успешно обновлена (server_id может быть NULL)")
                    return True
                except Exception as e:
                    logger.error(f"Ошибка при обновлении схемы server_log: {str(e)}")
                    return False
            else:
                logger.info("Схема таблицы server_log уже обновлена (server_id может быть NULL)")
                return True
    
    logger.warning("Колонка server_id не найдена в таблице server_log")
    return False

def ensure_domain_log_exists():
    """
    Проверяет существование таблицы domain_log и создаёт её при необходимости
    """
    from sqlalchemy import inspect, MetaData, Table, Column, Integer, String, Text, DateTime, ForeignKey
    
    # Проверяем, существует ли уже таблица domain_log
    inspector = inspect(db.engine)
    if 'domain_log' in inspector.get_table_names():
        logger.info("Таблица domain_log уже существует")
        return True
    
    # Создаем таблицу через SQLAlchemy Core для более гибкого контроля
    try:
        logger.info("Создание таблицы domain_log...")
        metadata = MetaData()
        Table('domain_log', metadata,
              Column('id', Integer, primary_key=True),
              Column('domain_id', Integer, ForeignKey('domain.id', ondelete='CASCADE'), nullable=False),
              Column('action', String(64), nullable=False),
              Column('status', String(20), nullable=False),
              Column('message', Text, nullable=True),
              Column('created_at', DateTime, default=datetime.utcnow))
        
        # Создаем таблицу в базе данных
        metadata.create_all(db.engine, tables=[metadata.tables['domain_log']])
        logger.info("Таблица domain_log успешно создана")
        return True
    except Exception as e:
        logger.error(f"Ошибка при создании таблицы domain_log: {str(e)}")
        return False

if __name__ == '__main__':
    with app.app_context():
        # Создаем все таблицы, если они не существуют
        logger.info("Создание таблиц базы данных...")
        db.create_all()
        logger.info("Таблицы базы данных успешно созданы")
        
        # Обновляем схему server_log
        update_server_log_schema()
        
        # Убеждаемся, что таблица domain_log существует
        ensure_domain_log_exists()
        
        logger.info("Инициализация базы данных завершена успешно")