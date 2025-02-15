import logging
import os
import aiohttp
import asyncio
import asyncpg
from aiogram import Bot, Dispatcher, types, F
from aiogram import Router
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ChatJoinRequest
from aiocron import crontab
from aiohttp import web
from db import database, load_subscribers_db, add_user_to_subscribers_db, remove_user_from_subscribers_db

# Конфигурация
API_TOKEN = '7415146600:AAFvHQt3Kkr0_XIFYM2mPfea-ZqRG8NulZc'
# Подставляем ваш публичный домен, полученный на PythonAnywhere:
WEBHOOK_HOST = 'https://shy-leaf-f5f6.skat21-90.workers.dev'
WEBHOOK_PATH = '/webhook'
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

main_channel_url = "https://t.me/not_yet_design"
main_channel_id = -1001844574074
closed_channel_link = "https://t.me/+Ek0Zwec_-ghhMTcy"
closed_group_chat = -1001864564323
ADMIN_ID = 551926727
ADMIN_USERNAME = "@Skat2190"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
router = Router()
dp = Dispatcher(bot=bot, storage=storage)
dp.include_router(router)

# Пример обработчика для необработанных сообщений (отладка)
@router.message()
async def catch_all_messages(message: types.Message):
    logging.warning(f"Необработанное сообщение: {message}")

# Функция проверки подписки (без изменений)
async def check_subscription(user_id):
    try:
        member = await bot.get_chat_member(main_channel_id, user_id)
        if member.status not in ["member", "administrator", "creator"]:
            return False
        bot_member = await bot.get_chat_member(user_id, user_id)
        if bot_member.status != "member":
            return False
        return True
    except Exception as e:
        logging.error(f"Ошибка проверки подписки для {user_id}: {e}")
        return False

def is_admin(message: types.Message):
    return message.from_user.id == ADMIN_ID

# Обработчик заявок на вступление в закрытую группу
@dp.chat_join_request(F.chat.id == closed_group_chat)
async def handle_join_request(request: ChatJoinRequest):
    user_id = request.from_user.id
    username = request.from_user.username or "Без имени"
    if await check_subscription(user_id):
        await bot.approve_chat_join_request(closed_group_chat, user_id)
        logging.info(f"✅ Заявка одобрена: {username} ({user_id})")
        await add_user_to_subscribers_db(user_id)
    else:
        await bot.decline_chat_join_request(closed_group_chat, user_id)
        logging.info(f"❌ Заявка отклонена: {username} ({user_id})")

# Обработчик команды /start
@dp.message(Command("start"))
async def start_command(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Проверить подписку", callback_data="check_subscription")],
        [InlineKeyboardButton(text="Написать администратору", url=f"https://t.me/{ADMIN_USERNAME.lstrip('@')}")]
    ])
    await message.answer(
        f"Привет! Я бот канала Not Yet Design!\n\n"
        f"Подпишитесь на основной канал: {main_channel_url},\n"
        f"а затем нажмите \"Проверить подписку\".",
        reply_markup=keyboard
    )

# Обработчик callback для проверки подписки
@dp.callback_query(lambda c: c.data == "check_subscription")
async def check_subscription_callback(callback_query: types.CallbackQuery):
    logging.info(f"Callback получен: {callback_query.data} от пользователя {callback_query.from_user.id}")
    user_id = callback_query.from_user.id
    if await check_subscription(user_id):
        await add_user_to_subscribers_db(user_id)
        await callback_query.answer("Проверка пройдена!")
        await callback_query.message.answer(
            "Спасибо за подписку! 🎉 Теперь вы можете присоединиться к закрытому каналу: " +
            closed_channel_link
        )
    else:
        await callback_query.answer("Вы ещё не подписаны на основной канал.", show_alert=True)

# Обработчик новых участников в группе
@dp.chat_member()
async def handle_new_chat_members(event: types.ChatMemberUpdated):
    if event.new_chat_member:
        logging.info(f"Новый участник в группе: {event.new_chat_member.user.id} ({event.new_chat_member.user.first_name})")

# Обработчик команды /post для публикации постов
@dp.message(Command("post"))
async def post_command(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.reply("Команда доступна только администратору.")
        return
    try:
        sent_message = None
        if message.photo and message.video:
            sent_message = await bot.send_photo(
                main_channel_id,
                message.photo[-1].file_id,
                caption=message.caption
            )
            await bot.send_video(
                main_channel_id,
                message.video.file_id,
                caption="Видео дополнение:"
            )
        elif message.photo:
            sent_message = await bot.send_photo(
                main_channel_id,
                message.photo[-1].file_id,
                caption=message.caption
            )
        elif message.video:
            sent_message = await bot.send_video(
                main_channel_id,
                message.video.file_id,
                caption=message.caption
            )
        else:
            args = message.text.split(maxsplit=1)
            if len(args) < 2:
                await message.reply("Укажите текст поста или прикрепите фото/видео.")
                return
            text = args[1]
            sent_message = await bot.send_message(main_channel_id, text)
        if sent_message:
            post_url = f"https://t.me/{main_channel_url.split('/')[-1]}/{sent_message.message_id}"
            subscribers_list = await load_subscribers_db()
            for user_id in subscribers_list:
                try:
                    await bot.send_message(user_id, f"Новый пост на канале: {post_url}")
                except Exception as e:
                    logging.error(f"Не удалось отправить сообщение пользователю {user_id}: {e}")
                    await remove_user_from_subscribers_db(user_id)
            await message.reply("Пост опубликован и отправлен подписчикам!")
    except Exception as e:
        logging.error(f"Ошибка при публикации поста: {e}")

# Обработчик новых постов в канале (рассылка подписчикам)
processed_media_groups = {}

@dp.channel_post()
async def channel_post_handler(message: types.Message):
    if message.media_group_id:
        if message.media_group_id in processed_media_groups:
            logging.info(f"Media group {message.media_group_id} уже обработан, пропускаем сообщение {message.message_id}")
            return
        else:
            processed_media_groups[message.media_group_id] = True

    logging.info("channel_post_handler вызван")
    try:
        post_url = f"https://t.me/{main_channel_url.split('/')[-1]}/{message.message_id}"
        logging.info(f"Новый пост в канале: {post_url}")
        subscribers_list = await load_subscribers_db()
        for user_id in subscribers_list:
            try:
                await bot.send_message(user_id, f"Новый пост на канале: {post_url}")
            except Exception as e:
                logging.error(f"Не удалось отправить сообщение пользователю {user_id}: {e}")
                await remove_user_from_subscribers_db(user_id)
    except Exception as e:
        logging.error(f"Ошибка обработки поста из канала: {e}")

# Обработчик команды /check_users для проверки подписчиков
@dp.message(Command("check_users"))
async def check_users_command(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.reply("Команда доступна только администратору.")
        return
    subscribers_list = await load_subscribers_db()
    removed_users = []
    if not subscribers_list:
        await message.reply("Список подписчиков пуст. Никого не нужно проверять.")
        return
    for user_id in subscribers_list.copy():
        logging.info(f"Проверяем пользователя: {user_id}")
        is_subscribed = await check_subscription(user_id)
        logging.info(f"Пользователь {user_id} подписан на канал: {is_subscribed}")
        try:
            await bot.send_chat_action(user_id, "typing")
            is_active = True
        except Exception as e:
            is_active = False
            logging.warning(f"Пользователь {user_id} не взаимодействует с ботом: {e}")
        if not is_subscribed or not is_active:
            logging.info(f"Удаляем пользователя {user_id}: подписка={is_subscribed}, активен={is_active}")
            removed_users.append(user_id)
            await remove_user_from_subscribers_db(user_id)
            try:
                await bot.ban_chat_member(closed_group_chat, user_id)
                await bot.unban_chat_member(closed_group_chat, user_id)
                logging.info(f"Пользователь {user_id} успешно удален из группы.")
            except Exception as e:
                logging.error(f"Ошибка удаления пользователя {user_id} из группы: {e}")
        else:
            logging.info(f"Пользователь {user_id} соответствует условиям.")
    await message.reply(f"Проверка завершена. Удалено пользователей: {len(removed_users)}")

# Команда /clean_group для чистки базы подписчиков по статусу в группе
@dp.message(Command("clean_group"))
async def clean_group_command(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.reply("Команда доступна только администратору.")
        return
    chat_members_count = await bot.get_chat_member_count(closed_group_chat)
    logging.info(f"Всего участников в группе: {chat_members_count}")
    chat_admins = await bot.get_chat_administrators(closed_group_chat)
    admins = {admin.user.id for admin in chat_admins}
    logging.info(f"Администраторы группы: {admins}")
    subscribers_list = await load_subscribers_db()
    removed_users = []
    for user_id in subscribers_list.copy():
        if user_id in admins:
            continue
        try:
            member = await bot.get_chat_member(closed_group_chat, user_id)
            if member.status in ["left", "kicked"]:
                logging.info(f"Пользователь {user_id} уже покинул группу.")
                removed_users.append(user_id)
                await remove_user_from_subscribers_db(user_id)
        except Exception as e:
            if "PARTICIPANT_ID_INVALID" in str(e):
                logging.info(f"Неизвестный участник {user_id}, удаляем из базы.")
                removed_users.append(user_id)
                await remove_user_from_subscribers_db(user_id)
            else:
                logging.error(f"Ошибка проверки участника {user_id}: {e}")
    await message.reply(f"Чистка завершена. Из базы удалено пользователей: {len(removed_users)}")

# Команда /list_users для вывода списка подписчиков
@dp.message(Command("list_users"))
async def list_users_command(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.reply("Команда доступна только администратору.")
        return
    try:
        subscribers_list = await load_subscribers_db()
        if subscribers_list:
            await message.reply("Подписчики:\n" + "\n".join(str(uid) for uid in subscribers_list))
        else:
            await message.reply("Список подписчиков пуст.")
    except Exception as e:
        logging.error(f"Ошибка при получении списка участников: {e}")
        await message.reply("Ошибка при получении списка участников.")
# Функция ручной проверки подписчиков для автоматизации (без объекта message)

async def check_users_command_manual():
    subscribers_list = await load_subscribers_db()
    removed_users = []
    if not subscribers_list:
        logging.info("Список подписчиков пуст. Никого не нужно проверять.")
        return 0
    for user_id in subscribers_list.copy():
        is_subscribed = await check_subscription(user_id)
        try:
            await bot.send_chat_action(user_id, "typing")
            is_active = True
        except Exception as e:
            is_active = False
            logging.warning(f"Пользователь {user_id} не взаимодействует с ботом: {e}")
        if not is_subscribed or not is_active:
            removed_users.append(user_id)
            await remove_user_from_subscribers_db(user_id)
            try:
                await bot.ban_chat_member(closed_group_chat, user_id)
                await bot.unban_chat_member(closed_group_chat, user_id)
                logging.info(f"Пользователь {user_id} успешно удален из группы.")
            except Exception as e:
                logging.error(f"Ошибка удаления пользователя {user_id} из группы: {e}")
    logging.info(f"Проверка завершена. Удалено пользователей: {len(removed_users)}")
    return len(removed_users)

# Автоматическая проверка подписчиков каждые 4 часа
async def scheduled_check():
    removed_count = await check_users_command_manual()
    logging.info(f"Автоматическая проверка завершена. Удалено пользователей: {removed_count}")

async def start_cron():
    loop = asyncio.get_running_loop()
    crontab("0 */4 * * *", func=scheduled_check, loop=loop)
    logging.info("Cron-задача scheduled_check зарегистрирована.")

# Функции, вызываемые при старте и завершении работы веб-приложения
async def on_startup(app: web.Application):
    await database.connect()
    await bot.set_webhook(WEBHOOK_URL)
    asyncio.create_task(start_cron())
    logging.info("Webhook установлен и cron-задача запущена.")

async def on_shutdown(app: web.Application):
    await bot.delete_webhook()
    await database.disconnect()
    logging.info("Webhook удален и база отключена.")

async def webhook_handler(request: web.Request):
    try:
        update_data = await request.json()
    except Exception as e:
        logging.error(f"Ошибка получения JSON: {e}")
        return web.Response(status=400)
    
    # Создаем объект Update из полученных данных
    update = types.Update(**update_data)
    # Обработка обновления
    asyncio.create_task(dp.process_update(update))
    return web.Response(text="OK", status=200)

# Создаем экземпляр приложения aiohttp
app = web.Application()
# Регистрируем маршрут для вебхуков
app.router.add_post(WEBHOOK_PATH, webhook_handler)
# Привязываем функции on_startup и on_shutdown
app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)

if __name__ == '__main__':
    web.run_app(app, host="0.0.0.0", port=8000)

