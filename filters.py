from datetime import datetime
import time

def register_filters(app):
    """
    Регистрирует пользовательские фильтры для шаблонов Jinja2.
    
    Args:
        app: Flask application instance
    """
    
    @app.template_filter('humanize_timestamp')
    @app.template_filter('humanize')
    def humanize_timestamp(timestamp):
        """
        Преобразует временную метку в понятный человеку формат 'X минут/часов/дней назад'
        
        Args:
            timestamp: datetime объект или None
            
        Returns:
            str: Отформатированная строка с указанием времени
        """
        if timestamp is None:
            return "Never"
            
        now = datetime.utcnow()
        diff = now - timestamp
        
        seconds = diff.total_seconds()
        
        if seconds < 60:
            return "just now"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        elif seconds < 86400:  # 24 hours
            hours = int(seconds // 3600)
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif seconds < 604800:  # 7 days
            days = int(seconds // 86400)
            return f"{days} day{'s' if days > 1 else ''} ago"
        else:
            return timestamp.strftime("%Y-%m-%d %H:%M")
            
    @app.template_filter('slice')
    def slice_list(value, start, stop=None):
        """
        Возвращает часть списка (аналог slice() в Python)
        
        Args:
            value: список или итерируемый объект
            start: начальный индекс или количество элементов (если stop=None)
            stop: конечный индекс (опционально)
            
        Returns:
            list: Отфильтрованный список
        """
        if stop is None:
            # Если stop не указан, то start - это количество элементов
            return list(value)[:start]
        else:
            return list(value)[start:stop]