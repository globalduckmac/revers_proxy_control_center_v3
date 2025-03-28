import logging
import time
import threading
import asyncio
import pytz
from datetime import datetime, timedelta

from app import db
from models import Server, Domain, DomainGroup
from modules.server_manager import ServerManager
from modules.domain_manager import DomainManager
from modules.monitoring import MonitoringManager
from modules.telegram_notifier import TelegramNotifier

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Интервалы выполнения задач (в секундах)
CHECK_SERVER_INTERVAL = 300  # 5 минут - мониторинг серверов только через Glances API
CHECK_DOMAIN_NS_INTERVAL = 3600  # 1 час
COLLECT_SERVER_METRICS_INTERVAL = 300  # 5 минут - сбор метрик только через Glances API
DAILY_REPORT_INTERVAL = 86400  # 24 часа
PAYMENT_REMINDER_INTERVAL = 43200  # 12 часов

class BackgroundTasks:
    """
    Класс для управления фоновыми задачами в системе.
    """
    def __init__(self):
        self.is_running = False
        self.threads = []
    
    def start(self):
        """Запускает все фоновые задачи."""
        if self.is_running:
            logger.warning("Background tasks are already running")
            return
        
        self.is_running = True
        
        # Запускаем задачу проверки серверов
        server_check_thread = threading.Thread(
            target=self._run_task,
            args=(self._check_servers, CHECK_SERVER_INTERVAL, "Server check"),
            daemon=True
        )
        self.threads.append(server_check_thread)
        server_check_thread.start()
        
        # Запускаем задачу проверки NS-записей доменов
        domain_ns_check_thread = threading.Thread(
            target=self._run_task,
            args=(self._check_domains_ns, CHECK_DOMAIN_NS_INTERVAL, "Domain NS check"),
            daemon=True
        )
        self.threads.append(domain_ns_check_thread)
        domain_ns_check_thread.start()
        
        # Запускаем задачу сбора метрик серверов
        server_metrics_thread = threading.Thread(
            target=self._run_task,
            args=(self._collect_server_metrics, COLLECT_SERVER_METRICS_INTERVAL, "Server metrics collection"),
            daemon=True
        )
        self.threads.append(server_metrics_thread)
        server_metrics_thread.start()
        
        # Сбор метрик доменов отключен
        
        # Запускаем задачу проверки напоминаний об оплате серверов
        payment_reminder_thread = threading.Thread(
            target=self._run_task,
            args=(self._check_payment_reminders, PAYMENT_REMINDER_INTERVAL, "Payment reminder check"),
            daemon=True
        )
        self.threads.append(payment_reminder_thread)
        payment_reminder_thread.start()
        
        # Запускаем задачу отправки ежедневных отчетов
        daily_report_thread = threading.Thread(
            target=self._run_task,
            args=(self._send_daily_report, DAILY_REPORT_INTERVAL, "Daily report"),
            daemon=True
        )
        self.threads.append(daily_report_thread)
        daily_report_thread.start()
        
        logger.info("Background tasks started with Glances API for server monitoring only")
    
    def stop(self):
        """Останавливает все фоновые задачи."""
        self.is_running = False
        logger.info("Background tasks stopped")
    
    def _run_task(self, task_func, interval, task_name):
        """
        Запускает задачу с указанным интервалом.
        
        Args:
            task_func: Функция для выполнения
            interval: Интервал между выполнениями в секундах
            task_name: Имя задачи для логирования
        """
        logger.info(f"Starting {task_name} task, interval: {interval} seconds")
        
        # Специальная обработка для ежедневного отчета
        if task_name == "Daily report":
            self._run_scheduled_task(task_func, task_name)
            return
        
        while self.is_running:
            try:
                # Выполняем задачу
                logger.info(f"Running {task_name} task")
                task_func()
                
                # Устанавливаем следующее время выполнения
                logger.info(f"{task_name} task completed, next run in {interval} seconds")
                
                # Ждем до следующего запуска
                for _ in range(interval):
                    if not self.is_running:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                logger.error(f"Error in {task_name} task: {str(e)}")
                time.sleep(60)  # В случае ошибки ждем минуту перед повторной попыткой
                
    def _run_scheduled_task(self, task_func, task_name):
        """
        Запускает задачу по расписанию (в 9:00 по немецкому времени).
        
        Args:
            task_func: Функция для выполнения
            task_name: Имя задачи для логирования
        """
        logger.info(f"Starting scheduled {task_name} task at 9:00 AM German time")
        
        germany_tz = pytz.timezone('Europe/Berlin')
        
        while self.is_running:
            try:
                # Получаем текущее время в немецкой временной зоне
                now = datetime.now(germany_tz)
                
                # Вычисляем время следующего запуска (9:00 утра)
                if now.hour < 9:
                    # Ещё сегодня в 9:00
                    next_run = now.replace(hour=9, minute=0, second=0, microsecond=0)
                else:
                    # Завтра в 9:00
                    next_run = now.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=1)
                
                # Вычисляем время до следующего запуска в секундах
                seconds_until_next_run = (next_run - now).total_seconds()
                
                logger.info(f"Next {task_name} scheduled at {next_run.strftime('%Y-%m-%d %H:%M:%S')} "
                           f"({int(seconds_until_next_run)} seconds from now)")
                
                # Ждем до следующего запуска
                sleep_interval = 60  # Проверяем каждую минуту
                for _ in range(int(seconds_until_next_run / sleep_interval) + 1):
                    if not self.is_running:
                        return
                    
                    # Пересчитываем время до запуска, чтобы корректно обрабатывать изменения времени системы
                    now = datetime.now(germany_tz)
                    seconds_left = (next_run - now).total_seconds()
                    
                    if seconds_left <= 0:
                        break  # Пора запускать задачу
                    
                    time.sleep(min(sleep_interval, seconds_left))
                
                # Запускаем задачу
                logger.info(f"Running scheduled {task_name} task")
                task_func()
                logger.info(f"{task_name} task completed")
                
            except Exception as e:
                logger.error(f"Error in scheduled {task_name} task: {str(e)}")
                time.sleep(60)  # В случае ошибки ждем минуту перед повторной попыткой
    
    def _check_servers(self):
        """
        Проверяет доступность всех серверов только через Glances API.
        Сервера без настроенного Glances будут пропущены.
        """
        from app import app
        from modules.glances_manager import GlancesManager
        
        with app.app_context():
            servers = Server.query.all()
            
            for server in servers:
                try:
                    # Запоминаем текущий статус перед проверкой
                    old_status = server.status
                    
                    # Проверяем доступность сервера через Glances API, если доступно
                    if server.glances_installed and server.glances_enabled:
                        logger.info(f"Checking server {server.name} via Glances API")
                        
                        try:
                            # Пытаемся получить метрики через API
                            api_metrics = GlancesManager.get_server_metrics_via_api(server)
                            
                            if api_metrics:
                                # Если API доступен - сервер активен
                                server.status = 'active'
                                server.last_check = datetime.utcnow()
                                
                                logger.info(f"Server {server.name} is active via Glances API")
                            else:
                                # Если API недоступен - отмечаем сервер как недоступный
                                server.status = 'error'
                                server.glances_status = 'error'
                                server.glances_last_check = datetime.utcnow()
                                logger.warning(f"Server {server.name} is not reachable via Glances API")
                        except Exception as e:
                            logger.error(f"Error checking server {server.name} via Glances API: {str(e)}")
                            
                            # При ошибке отмечаем сервер как недоступный
                            server.status = 'error'
                            server.glances_status = 'error'
                            server.last_check = datetime.utcnow()
                            server.glances_last_check = datetime.utcnow()
                    else:
                        # Если Glances не установлен или не включен - отмечаем как необработанный
                        logger.info(f"Skipping server {server.name} check - Glances not installed or not enabled")
                        continue
                    
                    # Если статус изменился, добавляем запись в лог и отправляем уведомление
                    if old_status != server.status:
                        # Добавляем запись в лог об изменении статуса
                        from models import ServerLog
                        log = ServerLog(
                            server_id=server.id,
                            action='status_change',
                            status='success' if server.status == 'active' else 'error',
                            message=f"Server status changed from {old_status} to {server.status}"
                        )
                        db.session.add(log)
                        
                        # Отправляем уведомление, если настроен Telegram
                        if TelegramNotifier.is_configured():
                            try:
                                # Используем новый event loop для асинхронной отправки уведомления
                                logger.info(f"Sending status change notification for server {server.name}")
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)
                                
                                try:
                                    loop.run_until_complete(
                                        TelegramNotifier.notify_server_status_change(
                                            server, old_status, server.status
                                        )
                                    )
                                    logger.info(f"Server status notification sent for {server.name}")
                                finally:
                                    loop.close()
                            except Exception as e:
                                logger.error(f"Error sending server status notification: {str(e)}")
                    
                    # Сохраняем все изменения в базе данных
                    db.session.commit()
                    
                except Exception as e:
                    logger.error(f"Error checking server {server.name}: {str(e)}")
                    db.session.rollback()
    
    def _check_domains_ns(self):
        """Проверяет NS-записи всех доменов, для которых указаны ожидаемые значения."""
        from app import app
        with app.app_context():
            try:
                # Получаем все домены с указанными ожидаемыми NS
                domains = Domain.query.filter(Domain.expected_nameservers.isnot(None)).all()
                
                # Добавляем запись в общий журнал активности о запуске проверки NS доменов
                from models import ServerLog
                activity_log = ServerLog(
                    server_id=None,  # Используем None для общесистемных событий
                    action='domain_ns_check_batch',
                    status='success',
                    message=f"Запущена автоматическая проверка NS-записей для {len(domains)} доменов"
                )
                db.session.add(activity_log)
                db.session.commit()
                logger.info(f"Started batch NS check for {len(domains)} domains")
                
                for domain in domains:
                    try:
                        # Запоминаем текущий статус
                        old_status = domain.ns_status
                        
                        # Проверяем NS-записи
                        DomainManager.check_domain_ns_status(domain.id)
                        
                        # Получаем обновленный домен
                        domain = Domain.query.get(domain.id)
                        
                        # Если статус изменился, добавляем запись в лог и отправляем уведомление
                        if old_status != domain.ns_status:
                            # Добавляем запись в лог об изменении статуса
                            from models import DomainLog
                            log = DomainLog(
                                domain_id=domain.id,
                                action='ns_status_change',
                                status='success' if domain.ns_status == 'active' else 'warning' if domain.ns_status == 'warning' else 'error',
                                message=f"Domain NS status changed from {old_status} to {domain.ns_status}"
                            )
                            db.session.add(log)
                            db.session.commit()
                            
                            # Маскируем домен для логирования
                            from modules.telegram_notifier import mask_domain_name
                            masked_domain_name = mask_domain_name(domain.name)
                            logger.info(f"Domain NS status change logged for {masked_domain_name}: {old_status} -> {domain.ns_status}")
                            
                            # Отправляем уведомление, если настроен Telegram
                            if TelegramNotifier.is_configured():
                                try:
                                    loop = asyncio.new_event_loop()
                                    asyncio.set_event_loop(loop)
                                    
                                    try:
                                        loop.run_until_complete(
                                            TelegramNotifier.notify_domain_ns_status_change(
                                                domain, old_status, domain.ns_status
                                            )
                                        )
                                        logger.info(f"Domain NS status notification sent for {masked_domain_name}")
                                    finally:
                                        loop.close()
                                except Exception as e:
                                    logger.error(f"Error sending domain NS status notification for {masked_domain_name}: {str(e)}")
                        
                    except Exception as e:
                        # Маскируем домен даже в сообщениях об ошибках
                        from modules.telegram_notifier import mask_domain_name
                        masked_domain_name = mask_domain_name(domain.name)
                        logger.error(f"Error checking NS for domain {masked_domain_name}: {str(e)}")
                
            except Exception as e:
                logger.error(f"Error in domain NS check task: {str(e)}")
                db.session.rollback()
    
    def _collect_server_metrics(self):
        """Собирает метрики со всех активных серверов только через Glances API."""
        from app import app
        with app.app_context():
            try:
                # Получаем все активные сервера
                servers = Server.query.filter_by(status='active').all()
                
                for server in servers:
                    try:
                        # Собираем и сохраняем метрики сервера
                        logger.info(f"Collecting metrics for server {server.name}")
                        metric = MonitoringManager.collect_server_metrics(server)
                        
                        if metric:
                            logger.info(f"Collected metrics for server {server.name}: CPU: {metric.cpu_usage}%, Memory: {metric.memory_usage}%, Disk: {metric.disk_usage}%")
                            
                            # Проверяем на высокую нагрузку и отправляем уведомление при необходимости
                            self._check_high_load_metrics(server, metric)
                        else:
                            logger.warning(f"Failed to collect metrics for server {server.name}")
                            
                    except Exception as e:
                        logger.error(f"Error collecting metrics for server {server.name}: {str(e)}")
                
            except Exception as e:
                logger.error(f"Error in server metrics collection task: {str(e)}")
                db.session.rollback()
    
    def _collect_domain_metrics(self):
        """Функция сбора метрик доменов отключена в этой версии."""
        logger.info("Domain metrics collection via SSH has been disabled in this version.")
    
    def _send_daily_report(self):
        """Отправляет ежедневный отчет о состоянии системы."""
        from app import app
        
        # Проверяем, настроены ли Telegram уведомления
        if not TelegramNotifier.is_configured():
            logger.warning("Telegram notifications are not configured, skipping daily report")
            return
        
        logger.info("Sending daily report...")
        
        with app.app_context():
            try:
                # Запускаем асинхронную задачу для отправки отчета
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    loop.run_until_complete(TelegramNotifier.send_daily_report())
                    logger.info("Daily report sent successfully")
                finally:
                    loop.close()
                
            except Exception as e:
                logger.error(f"Error sending daily report: {str(e)}")
                
    def _check_payment_reminders(self):
        """Проверяет необходимость отправки напоминаний об оплате серверов."""
        from app import app
        
        # Проверяем, настроены ли Telegram уведомления
        if not TelegramNotifier.is_configured():
            logger.warning("Telegram notifications are not configured, skipping payment reminders check")
            return
        
        logger.info("Checking server payment reminders...")
        
        with app.app_context():
            try:
                # Запускаем асинхронную задачу для проверки и отправки напоминаний
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    reminder_count = loop.run_until_complete(TelegramNotifier.check_server_payment_reminders())
                    if reminder_count > 0:
                        logger.info(f"Sent {reminder_count} payment reminders")
                    else:
                        logger.info("No payment reminders needed at this time")
                finally:
                    loop.close()
                
            except Exception as e:
                logger.error(f"Error checking payment reminders: {str(e)}")
    
    def _check_high_load_metrics(self, server, metric):
        """
        Проверяет метрики сервера на превышение пороговых значений и отправляет уведомления.
        
        Args:
            server (Server): Объект сервера
            metric (ServerMetric): Объект метрики
        """
        if not TelegramNotifier.is_configured():
            return
            
        # Проверяем превышение пороговых значений
        has_high_load = (metric.cpu_usage and metric.cpu_usage > 80) or \
                        (metric.memory_usage and metric.memory_usage > 80) or \
                        (metric.disk_usage and metric.disk_usage > 85)
        
        if has_high_load:
            # Отправляем уведомление о высокой нагрузке
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                loop.run_until_complete(TelegramNotifier.notify_server_high_load(server, metric))
                logger.info(f"High load notification sent for server {server.name}")
            except Exception as e:
                logger.error(f"Error sending high load notification: {str(e)}")
            finally:
                loop.close()

# Создаем глобальный экземпляр менеджера задач
background_tasks = BackgroundTasks()