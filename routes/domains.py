import logging
import os
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required
from models import Domain, DomainGroup, db
from modules.domain_manager import DomainManager

bp = Blueprint('domains', __name__, url_prefix='/domains')
logger = logging.getLogger(__name__)

@bp.route('/')
@login_required
def index():
    """Show list of domains."""
    # Получаем параметр группы из запроса
    group_id = request.args.get('group_id', type=int)
    
    # Получаем все группы доменов для фильтра
    domain_groups = DomainGroup.query.all()
    
    if group_id:
        # Если указана группа, фильтруем домены по этой группе
        group = DomainGroup.query.get_or_404(group_id)
        domains = group.domains.all()
    else:
        # Иначе показываем все домены
        domains = Domain.query.all()
    
    return render_template('domains/index.html', 
                          domains=domains, 
                          domain_groups=domain_groups,
                          selected_group_id=group_id)

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
        
        # Если выбран сервер, используем его IP-адрес
        if server_id and not target_ip:
            from models import Server
            server = Server.query.get(server_id)
            if server:
                target_ip = server.ip_address
        
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
        
        # Create domain
        domain = Domain(
            name=name,
            target_ip=target_ip,
            target_port=target_port,
            ssl_enabled=ssl_enabled,
            expected_nameservers=expected_nameservers
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
        server_id = request.form.get('server_id')
        target_port = request.form.get('target_port', 80, type=int)
        ssl_enabled = 'ssl_enabled' in request.form
        
        # Если выбран сервер, используем его IP-адрес
        if server_id and not target_ip:
            from models import Server
            server = Server.query.get(server_id)
            if server:
                target_ip = server.ip_address
        
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
        
        # Update domain
        domain.name = name
        domain.target_ip = target_ip
        domain.target_port = target_port
        domain.ssl_enabled = ssl_enabled
        domain.expected_nameservers = expected_nameservers
        
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
    logger = logging.getLogger(__name__)
    
    logger.info("Начинаем проверку NS-записей всех доменов")
    
    try:
        # Выполняем проверку с отельной обработкой отката транзакций
        try:
            results = DomainManager.check_all_domains_ns_status()
            logger.info(f"Результаты проверки всех NS-записей: {results}")
            
            if results['ok'] > 0:
                message_success = f"{results['ok']} доменов с корректными NS-записями"
                flash(message_success, 'success')
                
            if results['mismatch'] > 0:
                message_warning = f"{results['mismatch']} доменов имеют несоответствие NS-записей. Проверьте настройки NS-серверов."
                flash(message_warning, 'warning')
                
            if results['error'] > 0:
                message_error = f"{results['error']} доменов имеют ошибки при проверке NS-записей"
                flash(message_error, 'danger')
            
            if results['ok'] + results['mismatch'] + results['error'] == 0:
                flash("Нет доменов с указанными ожидаемыми NS-записями для проверки", 'info')
                
        except Exception as inner_error:
            logger.error(f"Ошибка при выполнении проверки всех NS-записей: {str(inner_error)}")
            logger.error(traceback.format_exc())
            try:
                db.session.rollback()
            except Exception as rollback_error:
                logger.error(f"Ошибка при откате транзакции: {str(rollback_error)}")
            raise  # Передаем ошибку во внешний блок try/except
    except Exception as e:
        logger.error(f"Критическая ошибка при проверке всех NS-записей: {str(e)}")
        logger.error(traceback.format_exc())
        try:
            db.session.rollback()
        except Exception as rollback_error:
            logger.error(f"Критическая ошибка при откате транзакции: {str(rollback_error)}")
        # Отображаем более информативное сообщение
        error_message = str(e)
        if 'database' in error_message.lower() or 'db' in error_message.lower() or 'sql' in error_message.lower():
            flash('Ошибка соединения с базой данных при проверке NS-записей. Пожалуйста, попробуйте позже.', 'danger')
        else:
            flash(f'Ошибка при проверке всех NS-записей: {error_message}', 'danger')
    
    return redirect(url_for('domains.index'))

@bp.route('/api/check-nameservers/<domain_name>', methods=['GET'])
@login_required
def api_check_nameservers(domain_name):
    """API для проверки NS-записей по имени домена."""
    from modules.telegram_notifier import mask_domain_name
    masked_domain_name = mask_domain_name(domain_name)
    
    try:
        nameservers = DomainManager.check_nameservers(domain_name)
        logger.info(f"API successfully checked nameservers for {masked_domain_name}: {nameservers}")
        return jsonify({
            'success': True,
            'nameservers': nameservers
        })
    except Exception as e:
        logger.error(f"API error checking nameservers for {masked_domain_name}: {str(e)}")
        # Проверка наличия ошибки соединения с базой данных
        if 'database' in str(e).lower() or 'db' in str(e).lower() or 'sql' in str(e).lower():
            logger.error(f"Database connection error during nameserver check")
            try:
                db.session.rollback()
            except:
                pass  # Игнорируем ошибки при откате транзакции
            
            return jsonify({
                'success': False,
                'error': 'Ошибка соединения с базой данных. Пожалуйста, попробуйте позже.'
            }), 500
            
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

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
    
    # Проверяем, установлен ли токен FFPanel
    ffpanel_token = os.environ.get('FFPANEL_TOKEN')
    if not ffpanel_token:
        flash('Не настроен токен FFPanel API. Пожалуйста, добавьте FFPANEL_TOKEN в переменные окружения.', 'danger')
        return redirect(url_for('domains.index'))
    
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
