import logging
import os
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required
from models import Domain, DomainGroup, DomainLog, db
from modules.domain_manager import DomainManager
from datetime import datetime, timedelta

bp = Blueprint('domains', __name__, url_prefix='/domains')
logger = logging.getLogger(__name__)

@bp.route('/')
@login_required
def index():
    """Show list of domains."""
    # Получаем параметр группы из запроса
    group_id = request.args.get('group_id', type=int)
    show_ungrouped = request.args.get('show_ungrouped') == '1'
    
    # Получаем все группы доменов для фильтра
    domain_groups = DomainGroup.query.all()
    
    if group_id:
        # Если указана группа, фильтруем домены по этой группе
        group = DomainGroup.query.get_or_404(group_id)
        domains = group.domains.all()
    elif show_ungrouped:
        # Показываем только домены без групп
        from sqlalchemy import select, not_, exists

        # Находим домены, которые не имеют связей в таблице domain_group_association
        ungrouped_domains = []
        
        # Получаем все домены
        all_domains = Domain.query.all()
        
        # Фильтруем только те, у которых нет групп
        for domain in all_domains:
            if not domain.groups:
                ungrouped_domains.append(domain)
                
        domains = ungrouped_domains
    else:
        # Иначе показываем все домены
        domains = Domain.query.all()
    
    return render_template('domains/index.html', 
                          domains=domains, 
                          domain_groups=domain_groups,
                          selected_group_id=group_id,
                          show_ungrouped=show_ungrouped)

@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """Handle domain creation."""
    if request.method == 'POST':
        name = request.form.get('name')
        target_ip = request.form.get('target_ip')
        server_id = request.form.get('server_id')
        target_port = request.form.get('target_port', 80, type=int)
        ssl_enabled = 'ssl_enabled' in request.form
        
        # Validate required fields
        if not name or not target_ip:
            flash('Domain name and target IP are required', 'danger')
            return redirect(url_for('domains.create'))
        
        # Check if domain already exists
        existing_domain = Domain.query.filter_by(name=name).first()
        if existing_domain:
            flash(f'Domain {name} already exists', 'danger')
            return redirect(url_for('domains.create'))
        
        # Получаем ожидаемые NS-записи
        expected_nameservers = request.form.get('expected_nameservers', '')
        
        # Получаем настройки FFPanel
        ffpanel_enabled = 'ffpanel_enabled' in request.form
        ffpanel_target_ip = None
        
        if ffpanel_enabled:
            # Проверяем, был ли выбран сервер для FFPanel
            server_id = request.form.get('server_id')
            if server_id:
                # Если выбран сервер, используем его IP-адрес для FFPanel
                from models import Server
                server = Server.query.get(server_id)
                if server:
                    ffpanel_target_ip = server.ip_address
            else:
                # Иначе используем введенный вручную IP
                ffpanel_target_ip = request.form.get('ffpanel_target_ip')
            
            # Если FFPanel включен, но не указан специальный IP, используем основной target_ip
            if not ffpanel_target_ip:
                ffpanel_target_ip = target_ip
            
        # Create domain
        domain = Domain(
            name=name,
            target_ip=target_ip,
            target_port=target_port,
            ssl_enabled=ssl_enabled,
            expected_nameservers=expected_nameservers,
            ffpanel_enabled=ffpanel_enabled,
            ffpanel_target_ip=ffpanel_target_ip
        )
        
        db.session.add(domain)
        db.session.commit()
        
        # Add to domain groups if specified
        group_ids = request.form.getlist('groups[]')
        if group_ids:
            for group_id in group_ids:
                group = DomainGroup.query.get(group_id)
                if group:
                    group.domains.append(domain)
            
            db.session.commit()
            flash(f'Domain {name} created and added to {len(group_ids)} group(s)', 'success')
        else:
            flash(f'Domain {name} created successfully', 'success')
        
        return redirect(url_for('domains.index'))
    
    # Get all domain groups for dropdown
    domain_groups = DomainGroup.query.all()
    
    # Get all servers for dropdown
    from models import Server
    servers = Server.query.all()
    
    return render_template('domains/create.html', 
                          domain_groups=domain_groups, 
                          servers=servers)

@bp.route('/<int:domain_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(domain_id):
    """Handle domain editing."""
    domain = Domain.query.get_or_404(domain_id)
    
    if request.method == 'POST':
        name = request.form.get('name')
        target_ip = request.form.get('target_ip')
        target_port = request.form.get('target_port', 80, type=int)
        ssl_enabled = 'ssl_enabled' in request.form
        
        # Validate required fields
        if not name or not target_ip:
            flash('Domain name and target IP are required', 'danger')
            return redirect(url_for('domains.edit', domain_id=domain_id))
        
        # Check if domain name changed and if new name already exists
        if name != domain.name:
            existing_domain = Domain.query.filter_by(name=name).first()
            if existing_domain:
                flash(f'Domain {name} already exists', 'danger')
                return redirect(url_for('domains.edit', domain_id=domain_id))
        
        # Получаем ожидаемые NS-записи
        expected_nameservers = request.form.get('expected_nameservers', '')
        
        # Получаем настройки FFPanel
        ffpanel_enabled = 'ffpanel_enabled' in request.form
        ffpanel_target_ip = None
        
        if ffpanel_enabled:
            # Проверяем, был ли выбран сервер для FFPanel
            server_id = request.form.get('server_id')
            if server_id:
                # Если выбран сервер, используем его IP-адрес для FFPanel
                from models import Server
                server = Server.query.get(server_id)
                if server:
                    ffpanel_target_ip = server.ip_address
            else:
                # Иначе используем введенный вручную IP
                ffpanel_target_ip = request.form.get('ffpanel_target_ip')
            
            # Если FFPanel включен, но не указан специальный IP, используем основной target_ip
            if not ffpanel_target_ip:
                ffpanel_target_ip = target_ip
        
        # Update domain
        domain.name = name
        domain.target_ip = target_ip
        domain.target_port = target_port
        domain.ssl_enabled = ssl_enabled
        domain.expected_nameservers = expected_nameservers
        domain.ffpanel_enabled = ffpanel_enabled
        domain.ffpanel_target_ip = ffpanel_target_ip
        
        # Update domain groups
        domain.groups = []
        group_ids = request.form.getlist('groups[]')
        if group_ids:
            for group_id in group_ids:
                group = DomainGroup.query.get(group_id)
                if group:
                    domain.groups.append(group)
        
        db.session.commit()
        flash(f'Domain {name} updated successfully', 'success')
        
        return redirect(url_for('domains.index'))
    
    # Get all domain groups for dropdown
    domain_groups = DomainGroup.query.all()
    
    # Get all servers for dropdown
    from models import Server
    servers = Server.query.all()
    
    return render_template('domains/edit.html', 
                          domain=domain, 
                          domain_groups=domain_groups, 
                          servers=servers)

@bp.route('/<int:domain_id>/delete', methods=['POST'])
@login_required
def delete(domain_id):
    """Handle domain deletion."""
    domain = Domain.query.get_or_404(domain_id)
    name = domain.name
    
    # Remove domain from all groups
    domain.groups = []
    
    # Delete domain
    db.session.delete(domain)
    db.session.commit()
    
    flash(f'Domain {name} deleted successfully', 'success')
    return redirect(url_for('domains.index'))

@bp.route('/<int:domain_id>/nameservers', methods=['GET', 'POST'])
@login_required
def nameservers(domain_id):
    """Управление NS-записями домена."""
    domain = Domain.query.get_or_404(domain_id)
    
    if request.method == 'POST':
        expected_nameservers = request.form.get('expected_nameservers', '')
        if DomainManager.update_expected_nameservers(domain_id, expected_nameservers):
            flash(f'Ожидаемые NS-записи для домена {domain.name} обновлены', 'success')
        else:
            flash('Произошла ошибка при обновлении NS-записей', 'danger')
        
        return redirect(url_for('domains.nameservers', domain_id=domain_id))
    
    # Получаем текущие NS-записи для отображения
    actual_ns = []
    if domain.actual_nameservers:
        actual_ns = domain.actual_nameservers.split(',')
    
    return render_template('domains/nameservers.html', domain=domain, actual_ns=actual_ns)

@bp.route('/<int:domain_id>/check-ns', methods=['POST'])
@login_required
def check_ns(domain_id):
    """Проверка NS-записей домена."""
    import logging
    import traceback
    
    logger = logging.getLogger(__name__)
    
    try:
        # Оборачиваем весь блок получения домена в отдельную сессию
        with db.session.begin_nested():
            domain = Domain.query.get(domain_id)
            if not domain:
                flash(f'Домен с ID {domain_id} не найден', 'danger')
                return redirect(url_for('domains.index'))
            
            # Для логирования используем маскированное имя
            from modules.telegram_notifier import mask_domain_name
            masked_domain = mask_domain_name(domain.name)
            logger.info(f"Начинаем проверку NS для домена {masked_domain} (ID: {domain_id})")
    except Exception as e:
        logger.error(f"Ошибка при получении домена {domain_id}: {str(e)}")
        logger.error(traceback.format_exc())
        db.session.rollback()
        flash(f'Не удалось получить информацию о домене: {str(e)}', 'danger')
        return redirect(url_for('domains.index'))
    
    try:
        # Добавляем запись в общий журнал активности о ручной проверке NS для одного домена
        try:
            from models import ServerLog
            activity_log = ServerLog(
                server_id=None,  # Используем None для общесистемных событий
                action='domain_ns_check_single_manual',
                status='success',
                message=f"Запущена ручная проверка NS-записей для домена {mask_domain_name(domain.name)} (ID: {domain_id})"
            )
            db.session.add(activity_log)
            db.session.commit()
            logger.info(f"Added activity log for manual check of domain {domain_id}")
        except Exception as log_error:
            logger.error(f"Error adding activity log for single domain NS check: {str(log_error)}")
            db.session.rollback()  # Rollback if there was an error

        # Выполняем проверку в отдельном блоке
        result = DomainManager.check_domain_ns_status(domain_id)
        
        # После проверки получаем обновленный статус
        try:
            updated_domain = Domain.query.get(domain_id)
            if result:
                flash('Проверка NS-записей завершена успешно', 'success')
            elif updated_domain and updated_domain.ns_status == 'mismatch':
                flash('Ожидаемые NS-записи не все обнаружены в фактическом списке NS. Убедитесь, что все NS-серверы настроены правильно.', 'warning')
            else:
                flash('Произошла ошибка при проверке NS-записей или статус не определен', 'danger')
                
        except Exception as db_error:
            logger.error(f"Ошибка при получении обновленного статуса домена {domain_id}: {str(db_error)}")
            logger.error(traceback.format_exc())
            db.session.rollback()
            flash('Ошибка при получении обновленного статуса домена', 'danger')
    except Exception as e:
        logger.error(f"Ошибка при проверке NS для домена {domain_id}: {str(e)}")
        logger.error(traceback.format_exc())
        try:
            db.session.rollback()
        except Exception as rollback_error:
            logger.error(f"Ошибка при откате транзакции: {str(rollback_error)}")
        flash(f'Ошибка при проверке NS-записей: {str(e)}', 'danger')
    
    return redirect(url_for('domains.nameservers', domain_id=domain_id))

@bp.route('/check-all-ns', methods=['POST'])
@login_required
def check_all_ns():
    """Проверка NS-записей всех доменов."""
    import logging
    import traceback
    import html
    
    logger = logging.getLogger(__name__)
    
    logger.info("Начинаем проверку NS-записей всех доменов")
    
    try:
        # Добавляем запись в общий журнал активности о ручном запуске проверки NS доменов
        try:
            from models import ServerLog
            # Найдем количество доменов с заданными NS
            from models import Domain
            domains_to_check = Domain.query.filter(Domain.expected_nameservers.isnot(None)).all()
            
            activity_log = ServerLog(
                server_id=None,  # Используем None для общесистемных событий
                action='domain_ns_check_batch_manual',
                status='success',
                message=f"Запущена ручная проверка NS-записей для {len(domains_to_check)} доменов"
            )
            db.session.add(activity_log)
            db.session.commit()
            logger.info(f"Added activity log for manual check of {len(domains_to_check)} domains")
        except Exception as log_error:
            logger.error(f"Error adding activity log for NS check: {str(log_error)}")
            db.session.rollback()  # Rollback if there was an error
        
        # Выполняем проверку с отельной обработкой отката транзакций
        try:
            results = DomainManager.check_all_domains_ns_status()
            logger.info(f"Результаты проверки всех NS-записей: {results}")
            
            # Дополнительная проверка на валидность результатов
            if not isinstance(results, dict):
                logger.error(f"Неверный формат результатов: {type(results)}")
                raise ValueError("Результаты проверки имеют неверный формат")
                
            # Безопасно получаем количество проверенных доменов 
            ok_count = results.get('ok', 0)
            mismatch_count = results.get('mismatch', 0)
            error_count = results.get('error', 0)
            
            # Формируем сообщения для пользователя
            if ok_count > 0:
                message_success = f"{ok_count} доменов с корректными NS-записями"
                flash(message_success, 'success')
                
            if mismatch_count > 0:
                message_warning = f"{mismatch_count} доменов имеют несоответствие NS-записей. Проверьте настройки NS-серверов."
                flash(message_warning, 'warning')
                
            if error_count > 0:
                message_error = f"{error_count} доменов имеют ошибки при проверке NS-записей"
                flash(message_error, 'danger')
            
            total_count = ok_count + mismatch_count + error_count
            if total_count == 0:
                flash("Нет доменов с указанными ожидаемыми NS-записями для проверки", 'info')
                
        except Exception as inner_error:
            error_str = html.escape(str(inner_error))
            logger.error(f"Ошибка при выполнении проверки всех NS-записей: {error_str}")
            logger.error(traceback.format_exc())
            
            try:
                db.session.rollback()
            except Exception as rollback_error:
                logger.error(f"Ошибка при откате транзакции: {html.escape(str(rollback_error))}")
                
            # Создаем безопасное сообщение об ошибке для пользователя
            flash('Произошла ошибка при проверке NS-записей доменов. Пожалуйста, попробуйте позже.', 'danger')
            return redirect(url_for('domains.index'))
            
    except Exception as e:
        # Обработка и экранирование возможных ошибок
        error_message = html.escape(str(e))
        logger.error(f"Критическая ошибка при проверке всех NS-записей: {error_message}")
        logger.error(traceback.format_exc())
        
        try:
            db.session.rollback()
        except Exception as rollback_error:
            logger.error(f"Критическая ошибка при откате транзакции: {html.escape(str(rollback_error))}")
            
        # Отображаем более информативное сообщение
        if 'database' in error_message.lower() or 'db' in error_message.lower() or 'sql' in error_message.lower():
            flash('Ошибка соединения с базой данных при проверке NS-записей. Пожалуйста, попробуйте позже.', 'danger')
        elif 'unicode' in error_message.lower() or 'encode' in error_message.lower() or 'decode' in error_message.lower():
            flash('Ошибка кодировки при проверке NS-записей. Возможно, в именах доменов используются специальные символы.', 'danger')
        else:
            # Безопасно отображаем только общее сообщение без технических деталей
            flash('Произошла ошибка при проверке NS-записей. Пожалуйста, попробуйте позже.', 'danger')
    
    return redirect(url_for('domains.index'))

@bp.route('/api/check-nameservers/<domain_name>', methods=['GET'])
@login_required
def api_check_nameservers(domain_name):
    """API для проверки NS-записей по имени домена."""
    import traceback
    import html
    
    # Создаем безопасную строку имени домена для логирования
    from modules.telegram_notifier import mask_domain_name
    
    try:
        # Безопасно обрабатываем имя домена, экранируя возможные проблемные символы
        masked_domain_name = mask_domain_name(domain_name.strip())
        
        # Проверяем допустимость имени домена
        if not domain_name or len(domain_name.strip()) == 0:
            logger.error("API error: Empty domain name provided")
            return jsonify({
                'success': False,
                'error': 'Необходимо указать имя домена'
            }), 400
        
        # Выполняем проверку NS-записей с расширенным логированием
        try:
            logger.info(f"API checking nameservers for domain: {masked_domain_name}")
            nameservers = DomainManager.check_nameservers(domain_name)
            
            # Проверка результатов
            if not isinstance(nameservers, list):
                raise ValueError(f"Unexpected nameservers format: {type(nameservers)}")
                
            logger.info(f"API successfully checked nameservers for {masked_domain_name}: {nameservers}")
            return jsonify({
                'success': True,
                'nameservers': nameservers
            })
            
        except Exception as dns_error:
            # Детальное логирование ошибки DNS-проверки
            error_text = html.escape(str(dns_error))
            logger.error(f"DNS error checking nameservers for {masked_domain_name}: {error_text}")
            logger.error(traceback.format_exc())
            
            return jsonify({
                'success': False,
                'error': 'Ошибка при проверке NS-записей. Проверьте правильность имени домена.'
            }), 400
            
    except Exception as e:
        # Логируем общую ошибку, но не показываем технические детали пользователю
        error_text = html.escape(str(e))
        logger.error(f"API critical error checking nameservers: {error_text}")
        logger.error(traceback.format_exc())
        
        # Проверка наличия ошибки соединения с базой данных
        if 'database' in error_text.lower() or 'db' in error_text.lower() or 'sql' in error_text.lower():
            logger.error(f"Database connection error during nameserver check")
            try:
                db.session.rollback()
            except Exception as rollback_error:
                logger.error(f"Failed to rollback: {html.escape(str(rollback_error))}")
            
            return jsonify({
                'success': False,
                'error': 'Ошибка соединения с базой данных. Пожалуйста, попробуйте позже.'
            }), 500
        
        # Ошибки кодировки Unicode
        elif 'unicode' in error_text.lower() or 'encode' in error_text.lower() or 'decode' in error_text.lower():
            return jsonify({
                'success': False,
                'error': 'Ошибка кодировки при проверке домена. Проверьте, что имя домена не содержит специальных символов.'
            }), 400
            
        # Для остальных ошибок возвращаем универсальное сообщение
        return jsonify({
            'success': False,
            'error': 'Ошибка при проверке NS-записей. Пожалуйста, попробуйте позже.'
        }), 500


@bp.route('/<int:domain_id>/ns-logs', methods=['GET'])
@login_required
def domain_ns_logs(domain_id):
    """Просмотр логов NS-проверок для конкретного домена."""
    try:
        # Получаем домен
        domain = Domain.query.get_or_404(domain_id)
        
        # Маскируем домен для логирования
        from modules.telegram_notifier import mask_domain_name
        masked_domain_name = mask_domain_name(domain.name)
        
        # Получаем параметры фильтрации из запроса
        action = request.args.get('action')
        status = request.args.get('status')
        date_range = request.args.get('date_range', '30')  # По умолчанию - 30 дней
        
        # Создаем базовый запрос
        logs_query = DomainLog.query.filter_by(domain_id=domain_id)
        
        # Применяем фильтры
        if action:
            logs_query = logs_query.filter_by(action=action)
        if status:
            logs_query = logs_query.filter_by(status=status)
        
        # Применяем фильтр по дате
        if date_range != 'all':
            if date_range.isdigit():
                days = int(date_range)
                date_from = datetime.utcnow() - timedelta(days=days)
                logs_query = logs_query.filter(DomainLog.created_at >= date_from)
        
        # Сортируем по дате в обратном порядке
        logs_query = logs_query.order_by(DomainLog.created_at.desc())
        
        # Получаем логи
        logs = logs_query.all()
        
        # Получаем уникальные значения для фильтров
        actions = db.session.query(DomainLog.action).distinct().all()
        actions = [action[0] for action in actions]
        
        # Собираем статистику
        stats = {
            'total': len(logs),
            'success': sum(1 for log in logs if log.status == 'success'),
            'warning': sum(1 for log in logs if log.status == 'warning'),
            'error': sum(1 for log in logs if log.status == 'error')
        }
        
        # Топ действий для статистики
        from collections import Counter
        action_counter = Counter(log.action for log in logs)
        top_actions = action_counter.most_common(5)
        
        return render_template('domains/ns_logs.html',
                              domain=domain,
                              logs=logs,
                              actions=actions,
                              stats=stats,
                              top_actions=top_actions,
                              selected_action=action,
                              selected_status=status,
                              selected_date_range=date_range,
                              masked_domain_name=masked_domain_name)
    except Exception as e:
        logger.error(f"Ошибка при просмотре логов NS-проверок для домена {domain_id}: {str(e)}")
        flash(f'Ошибка при загрузке логов NS-проверок: {str(e)}', 'danger')
        return redirect(url_for('domains.index'))


@bp.route('/<int:domain_id>/ffpanel', methods=['GET', 'POST'])
@login_required
def ffpanel(domain_id):
    """Управление интеграцией домена с FFPanel."""
    domain = Domain.query.get_or_404(domain_id)
    
    # Проверяем, установлен ли токен FFPanel
    ffpanel_token = os.environ.get('FFPANEL_TOKEN')
    if not ffpanel_token:
        flash('Не настроен токен FFPanel API. Пожалуйста, добавьте FFPANEL_TOKEN в переменные окружения.', 'danger')
        return redirect(url_for('domains.edit', domain_id=domain_id))
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        # Синхронизация домена с FFPanel
        if action == 'sync':
            # Обновляем параметры домена для FFPanel
            domain.ffpanel_port = request.form.get('ffpanel_port', '80')
            domain.ffpanel_port_out = request.form.get('ffpanel_port_out', '80')
            domain.ffpanel_port_ssl = request.form.get('ffpanel_port_ssl', '443')
            domain.ffpanel_port_out_ssl = request.form.get('ffpanel_port_out_ssl', '443')
            domain.ffpanel_dns = request.form.get('ffpanel_dns', '')
            db.session.commit()
            
            # Запускаем синхронизацию
            result = DomainManager.sync_domain_with_ffpanel(domain_id)
            
            if result['success']:
                flash(result['message'], 'success')
            else:
                flash(result['message'], 'danger')
                
        # Удаление домена из FFPanel
        elif action == 'delete':
            result = DomainManager.delete_domain_from_ffpanel(domain_id)
            
            if result['success']:
                flash(result['message'], 'success')
            else:
                flash(result['message'], 'danger')
        
        return redirect(url_for('domains.ffpanel', domain_id=domain_id))
    
    return render_template('domains/ffpanel.html', domain=domain)

@bp.route('/ffpanel/import', methods=['GET', 'POST'])
@login_required
def ffpanel_import():
    """Импорт доменов из FFPanel."""
    
    # Проверяем, установлен ли токен FFPanel (в настройках системы или переменных окружения)
    from models import SystemSetting
    
    # Пытаемся получить токен из настроек системы
    ffpanel_token = SystemSetting.get_value('ffpanel_token')
    
    # Если в настройках нет, проверяем переменные окружения
    if not ffpanel_token:
        ffpanel_token = os.environ.get('FFPANEL_TOKEN')
        
    # Если токен не найден нигде, выводим сообщение об ошибке    
    if not ffpanel_token:
        flash('Не настроен токен FFPanel API. Пожалуйста, добавьте токен в настройках системы или переменной окружения FFPANEL_TOKEN.', 'danger')
        return redirect(url_for('settings.index'))
    
    if request.method == 'POST':
        # Запускаем импорт доменов
        stats = DomainManager.import_domains_from_ffpanel()
        
        flash(stats['message'], 'info')
        
        if stats['imported'] > 0 or stats['updated'] > 0:
            flash(f"Импортировано новых доменов: {stats['imported']}, обновлено существующих: {stats['updated']}", 'success')
        
        if stats['failed'] > 0:
            flash(f"Ошибок при импорте: {stats['failed']}", 'warning')
            
            # Отображаем детали ошибок
            if 'errors' in stats and stats['errors']:
                for error in stats['errors']:
                    flash(f"Детали ошибки: {error}", 'danger')
            
        return redirect(url_for('domains.index'))
    
    return render_template('domains/ffpanel_import.html')
