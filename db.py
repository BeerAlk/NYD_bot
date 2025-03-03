import os
import sqlalchemy
from databases import Database

# Получаем URL подключения к БД из переменной окружения (на Heroku она будет DATABASE_URL)
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL is None:
    # Локальное тестирование: укажите здесь URL подключения к вашей локальной базе, например:
    DATABASE_URL = "mysql+aiomysql://NYD_ADMIN:fg4xZ9H4vu@127.0.0.1:3306/subscribers"

# Инициализируем объект Database
database = Database(DATABASE_URL)

# Определяем метаданные и таблицу
metadata = sqlalchemy.MetaData()

# Определяем таблицу для хранения подписчиков
subscribers = sqlalchemy.Table(
    "subscribers",
    metadata,
    sqlalchemy.Column("user_id", sqlalchemy.BigInteger, primary_key=True)
)

# Функция для загрузки подписчиков из базы данных
async def load_subscribers_db() -> list:
    query = subscribers.select()
    rows = await database.fetch_all(query)
    return [row["user_id"] for row in rows]

# Функция для добавления подписчика в базу данных
async def add_user_to_subscribers_db(user_id: int):
    query = subscribers.insert().values(user_id=user_id)
    try:
        await database.execute(query)
        print(f"Пользователь {user_id} добавлен в базу подписчиков.")
    except Exception as e:
        print(f"Ошибка добавления пользователя {user_id}: {e}")
        
# Функция для удаления подписчика из базы данных
async def remove_user_from_subscribers_db(user_id: int):
    query = subscribers.delete().where(subscribers.c.user_id == user_id)
    try:
        await database.execute(query)
        print(f"Пользователь {user_id} удалён из базы подписчиков.")
    except Exception as e:
        print(f"Ошибка удаления пользователя {user_id}: {e}")
        
# Создание таблиц (только для локального тестирования)
if __name__ == "__main__":
    engine = sqlalchemy.create_engine(DATABASE_URL)
    metadata.create_all(engine)

        
# Создаем объект engine для создания таблиц (при локальном тестировании)
engine = sqlalchemy.create_engine(DATABASE_URL)
