import threading
import asyncio
import sys
import os
import logging

# Добавляем путь к вашему проекту (если требуется)
PROJECT_HOME = os.path.dirname(os.path.abspath(__file__))
if PROJECT_HOME not in sys.path:
    sys.path.insert(0, PROJECT_HOME)

# Импортируйте ваш основной модуль, который запускает aiohttp сервер.
# Предположим, что ваш основной код находится в файле mybot.py и там определена функция main(),
# которая запускает и возвращает ваш aiohttp веб-приложение.
from mybot import main, app  # app – это ваш aiohttp веб-приложение

# Создаем отдельный event loop для асинхронного приложения
loop = asyncio.new_event_loop()

def run_app():
    asyncio.set_event_loop(loop)
    # Запускаем основной цикл вашего асинхронного приложения.
    # Здесь main() должна быть асинхронной функцией, которая запускает ваш aiohttp сервер (web.run_app)
    loop.run_until_complete(main())

# Запускаем ваш aiohttp сервер в отдельном потоке
t = threading.Thread(target=run_app)
t.setDaemon(True)
t.start()

# Это WSGI-приложение, которое будет вызываться PythonAnywhere.
# Оно может возвращать фиксированный ответ, поскольку наше асинхронное приложение уже запущено.
def application(environ, start_response):
    status = '200 OK'
    headers = [('Content-type', 'text/plain; charset=utf-8')]
    start_response(status, headers)
    return [b'Bot is running in background']
