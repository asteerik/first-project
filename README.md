# Ковчег Труда

Сайт для поиска вакансий в православных и социально ориентированных организациях.

## Django-проект

Серверная часть построена на Django REST Framework и MySQL. Модели, API и инструкции запуска описаны в [DATABASE.md](./DATABASE.md).

## Структура для команды

Карта папок, распределение задач всех трёх участников и правила совместной работы приведены в [PROJECT_STRUCTURE.md](./PROJECT_STRUCTURE.md).

## Быстрый локальный запуск

Установите Python и MySQL Server 8, затем откройте PowerShell в корне проекта.

1. В первом терминале запустите MySQL:

   ```powershell
   .\scripts\start-mysql.ps1
   ```

2. Откройте второй терминал в корне проекта и запустите Django:

   ```powershell
   py -m pip install -r requirements.txt
   py manage.py migrate
   py manage.py runserver
   ```

Административная панель: `http://127.0.0.1:8000/admin/`. Локальные настройки находятся в `.env`; не публикуйте секреты, пароли и дампы базы данных.

## Проверки

```powershell
py manage.py test jobs --settings=config.test_settings
py manage.py check
py manage.py makemigrations --check --dry-run
```

Шаблоны и статические ресурсы интерфейса пока являются заготовками в `templates/` и `static/`.
