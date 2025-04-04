import os
import logging
import tempfile
from jinja2 import Environment, FileSystemLoader
from datetime import datetime
from models import Server, Domain, DomainGroup, ProxyConfig, ServerLog, db
from modules.server_manager import ServerManager
from modules.domain_manager import DomainManager

logger = logging.getLogger(__name__)

class ProxyManager:
    """
    Handles operations related to proxy configuration generation and deployment.
    """
    
    def __init__(self, templates_path):
        """
        Initialize the ProxyManager with templates path.
        
        Args:
            templates_path: Path to the directory containing Nginx templates
        """
        self.templates_path = templates_path
        self.jinja_env = Environment(loader=FileSystemLoader(templates_path))
        
        # Add datetime function for templates
        self.jinja_env.globals['now'] = datetime.utcnow
    
    def check_ssl_certificate_exists(self, server, domain_name):
        """
        Проверяет наличие SSL-сертификатов для домена на сервере
        
        Args:
            server: Server model instance
            domain_name: Имя домена для проверки
            
        Returns:
            bool: True если сертификаты существуют и доступны, False в противном случае
        """
        try:
            # Проверяем наличие путей к сертификатам - обратите внимание, что это только проверка наличия, 
            # но не валидности самих сертификатов
            cert_check_cmd = f"sudo test -f /etc/letsencrypt/live/{domain_name}/fullchain.pem && sudo test -f /etc/letsencrypt/live/{domain_name}/privkey.pem && echo 'SSL_EXISTS' || echo 'SSL_NOT_FOUND'"
            result, _ = ServerManager.execute_command(server, cert_check_cmd)
            
            if "SSL_EXISTS" in result:
                logger.info(f"SSL certificates found for domain {domain_name}")
                return True
            else:
                logger.warning(f"SSL certificates not found for domain {domain_name}")
                return False
                
        except Exception as e:
            logger.error(f"Error checking SSL certificates for {domain_name}: {str(e)}")
            return False
    
    def generate_nginx_config(self, server):
        """
        Generate Nginx configuration for a server based on its domain groups.
        
        Args:
            server: Server model instance
            
        Returns:
            tuple: (main_config, site_configs) where:
                - main_config is the main nginx.conf content
                - site_configs is a dict mapping domain names to their site configurations
        """
        try:
            # Load templates
            main_template = self.jinja_env.get_template('nginx.conf.j2')
            site_template = self.jinja_env.get_template('site.conf.j2')
            
            # Get domains for the server using DomainManager
            domains = DomainManager.get_domains_by_server(server.id)
            
            # Проверяем, есть ли домены, и логируем для отладки
            if not domains:
                logger.warning(f"No domains found for server {server.id} ({server.name})")
                
                # Для дополнительной диагностики: проверим, есть ли группы доменов
                domain_groups = DomainGroup.query.filter_by(server_id=server.id).all()
                if not domain_groups:
                    logger.warning(f"No domain groups found for server {server.id}")
                else:
                    logger.info(f"Found {len(domain_groups)} domain groups for server {server.id}")
                    for group in domain_groups:
                        domain_count = group.domains.count()
                        logger.info(f"Group {group.id} ({group.name}) has {domain_count} domains")
            else:
                logger.info(f"Found {len(domains)} domains for server {server.id}")
            
            # Generate main Nginx config
            main_config = main_template.render(
                server_name=server.name,
                domains=domains
            )
            
            # Generate site configs for each domain
            site_configs = {}
            for domain in domains:
                # Проверяем наличие SSL сертификатов для доменов с включенным SSL
                ssl_available = False
                if domain.ssl_enabled:
                    ssl_available = self.check_ssl_certificate_exists(server, domain.name)
                
                site_config = site_template.render(
                    domain=domain.name,
                    target_ip=domain.target_ip,
                    target_port=domain.target_port,
                    ssl_enabled=domain.ssl_enabled,
                    ssl_available=ssl_available
                )
                site_configs[domain.name] = site_config
            
            return main_config, site_configs
            
        except Exception as e:
            logger.error(f"Error generating Nginx config for server {server.name}: {str(e)}")
            raise
    
    def deploy_proxy_config(self, server_id):
        """
        Deploy proxy configuration to a server.
        
        Args:
            server_id: ID of the server to deploy to
            
        Returns:
            bool: True if deployment was successful, False otherwise
        """
        try:
            server = Server.query.get(server_id)
            if not server:
                logger.error(f"Server with ID {server_id} not found")
                return False
            
            # Check server connectivity first
            if not ServerManager.check_connectivity(server):
                logger.error(f"Cannot deploy to server {server.name}: Server is not reachable")
                return False
            
            # Generate Nginx configurations
            main_config, site_configs = self.generate_nginx_config(server)
            
            # Create ProxyConfig record
            proxy_config = ProxyConfig(
                server_id=server.id,
                config_content=main_config,
                status='pending'
            )
            db.session.add(proxy_config)
            db.session.commit()
            
            # Ensure Nginx is installed
            stdout, stderr = ServerManager.execute_command(
                server, 
                "dpkg -l | grep nginx || sudo apt-get update && sudo apt-get install -y nginx"
            )
            
            if "nginx" not in stdout and not "nginx" in stderr:
                logger.error(f"Failed to verify Nginx installation on server {server.name}")
                proxy_config.status = 'error'
                db.session.commit()
                return False
            
            # Upload main Nginx config
            ServerManager.upload_string_to_file(
                server,
                main_config,
                "/etc/nginx/nginx.conf"
            )
            
            # Create sites-available and sites-enabled directories if they don't exist
            ServerManager.execute_command(
                server,
                "sudo mkdir -p /etc/nginx/sites-available /etc/nginx/sites-enabled"
            )
            
            # Upload site configurations
            for domain_name, site_config in site_configs.items():
                sanitized_name = domain_name.replace(".", "_")
                site_path = f"/etc/nginx/sites-available/{sanitized_name}"
                
                # Upload site config
                ServerManager.upload_string_to_file(
                    server,
                    site_config,
                    site_path
                )
                
                # Create symlink in sites-enabled
                ServerManager.execute_command(
                    server,
                    f"sudo ln -sf {site_path} /etc/nginx/sites-enabled/{sanitized_name}"
                )
            
            # Убедимся, что все каталоги для сертификатов существуют
            ServerManager.execute_command(
                server,
                "sudo mkdir -p /etc/letsencrypt/live/ /etc/ssl/certs/ /etc/ssl/private/"
            )
            
            # Test Nginx configuration
            stdout, stderr = ServerManager.execute_command(
                server,
                "sudo nginx -t"
            )
            
            if "successful" not in stdout and "successful" not in stderr:
                # Проверяем, является ли ошибка конфликтом default_server
                if "duplicate default server for 0.0.0.0:80" in stderr:
                    logger.warning(f"Detected duplicate default server conflict, trying to fix it")
                    
                    # Пытаемся удалить существующие default_server параметры
                    ServerManager.execute_command(
                        server,
                        "sudo sed -i 's/default_server//g' /etc/nginx/sites-enabled/*"
                    )
                    
                    # Повторно проверяем конфигурацию
                    stdout, stderr = ServerManager.execute_command(
                        server,
                        "sudo nginx -t"
                    )
                    
                    if "successful" not in stdout and "successful" not in stderr:
                        logger.error(f"Still failing after fixing default_server conflict: {stderr}")
                        proxy_config.status = 'error'
                        db.session.commit()
                        
                        # Create log entry
                        log = ServerLog(
                            server_id=server.id,
                            action='proxy_deployment',
                            status='error',
                            message=f"Nginx configuration test failed after trying to fix: {stderr}"
                        )
                        db.session.add(log)
                        db.session.commit()
                        return False
                    else:
                        logger.info("Successfully fixed default_server conflict")
                else:
                    logger.error(f"Nginx configuration test failed on server {server.name}: {stderr}")
                    proxy_config.status = 'error'
                    db.session.commit()
                    
                    # Create log entry
                    log = ServerLog(
                        server_id=server.id,
                        action='proxy_deployment',
                        status='error',
                        message=f"Nginx configuration test failed: {stderr}"
                    )
                    db.session.add(log)
                    db.session.commit()
                    return False
            
            # Проверяем наличие SSL сертификатов для каждого домена и обновляем конфигурацию
            domains = DomainManager.get_domains_by_server(server.id)
            ssl_domains = [d for d in domains if d.ssl_enabled]
            
            # Если есть домены с включенным SSL, проверяем наличие сертификатов
            if ssl_domains:
                logger.info(f"Checking SSL certificates for {len(ssl_domains)} domains")
                for domain in ssl_domains:
                    domain_safe = domain.name.replace(".", "_")
                    site_path = f"/etc/nginx/sites-available/{domain_safe}"
                    
                    # Проверяем наличие сертификатов
                    cert_check_cmd = f"sudo ls -la /etc/letsencrypt/live/{domain.name}/fullchain.pem 2>/dev/null || echo 'Not found'"
                    cert_result, _ = ServerManager.execute_command(server, cert_check_cmd)
                    
                    if "Not found" not in cert_result:
                        # Сертификаты существуют, заменяем самоподписанные на настоящие
                        logger.info(f"Found SSL certificates for {domain.name}, updating configuration")
                        
                        # Команда для замены самоподписанных сертификатов на настоящие в конфигурации
                        update_cmd = f"""sudo sed -i 's|ssl_certificate .*snakeoil.pem;|ssl_certificate /etc/letsencrypt/live/{domain.name}/fullchain.pem;|' {site_path} && \
                                        sudo sed -i 's|ssl_certificate_key .*snakeoil.key;|ssl_certificate_key /etc/letsencrypt/live/{domain.name}/privkey.pem;|' {site_path} && \
                                        sudo sed -i 's|# include /etc/letsencrypt/options-ssl-nginx.conf;|include /etc/letsencrypt/options-ssl-nginx.conf;|' {site_path} && \
                                        sudo sed -i 's|# ssl_dhparam|ssl_dhparam|' {site_path}"""
                        
                        try:
                            ServerManager.execute_command(server, update_cmd)
                            logger.info(f"SSL configuration updated for {domain.name}")
                        except Exception as e:
                            logger.warning(f"Could not update SSL configuration for {domain.name}: {str(e)}")
            
            # Reload Nginx to apply changes
            stdout, stderr = ServerManager.execute_command(
                server,
                "sudo systemctl reload nginx || sudo systemctl restart nginx"
            )
            
            # Update ProxyConfig status
            proxy_config.status = 'deployed'
            db.session.commit()
            
            # Create log entry
            log = ServerLog(
                server_id=server.id,
                action='proxy_deployment',
                status='success',
                message="Proxy configuration deployed successfully"
            )
            db.session.add(log)
            db.session.commit()
            
            logger.info(f"Successfully deployed proxy configuration to server {server.name}")
            return True
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error deploying proxy configuration to server {server_id}: {str(e)}")
            
            # Create log entry if server exists
            try:
                if server:
                    log = ServerLog(
                        server_id=server.id,
                        action='proxy_deployment',
                        status='error',
                        message=f"Deployment error: {str(e)}"
                    )
                    db.session.add(log)
                    db.session.commit()
            except:
                pass
                
            return False
