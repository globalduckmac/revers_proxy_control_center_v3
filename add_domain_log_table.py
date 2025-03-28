#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Скрипт для добавления таблицы DomainLog для логирования проверок и изменений статуса NS доменов

Для запуска:
python add_domain_log_table.py
"""

import logging
import sys
from datetime import datetime

from app import app, db
from flask import Flask
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


def create_domain_log_table():
    """
    Создает таблицу domain_log для хранения информации о проверках NS и изменениях статуса доменов
    """
    from sqlalchemy import inspect, MetaData, Table
    
    # Проверяем, существует ли уже таблица domain_log
    inspector = inspect(db.engine)
    if 'domain_log' in inspector.get_table_names():
        logger.info("Таблица domain_log уже существует. Пропускаем создание.")
        return False
    
    # Создаем таблицу через SQLAlchemy Core для более гибкого контроля
    try:
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
        logger.info("Таблица domain_log успешно создана.")
        return True
    except Exception as e:
        logger.error(f"Ошибка при создании таблицы domain_log: {str(e)}")
        return False


if __name__ == '__main__':
    with app.app_context():
        if create_domain_log_table():
            logger.info("Миграция успешно выполнена")
        else:
            logger.info("Миграция не требуется или не удалась, проверьте логи")