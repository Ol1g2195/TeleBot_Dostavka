from aiogram import Bot, Dispatcher, types
import asyncio

TOKEN = "6403214241:AAEn5GhgkZNRZMReAq9cKTpJ8XgEA2QHqcc"  # Замените на действительный токен вашего бота
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)  # Инициализируйте Dispatcher с объектом Bot

lock = asyncio.Lock()

users = {}  # словарь пользователей
messages = []  # список сообщений
rejected_messages = {}  # список отклоненных сообщений для каждого пользователя
orders_in_progress = {}  # словарь счетчиков заказов для каждого пользователя

async def on_startup(dp):
    print('Бот запущен!')

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    if message.chat.type == 'private':
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        buttons = ["+", "-"]
        keyboard.add(*buttons)
        await bot.send_message(chat_id=message.from_user.id, text="Выберите действие:", reply_markup=keyboard)

@dp.message_handler(lambda message: message.text == "+")
async def add_user(message: types.Message):
    if message.chat.type == 'private':
        user_id = message.from_user.id
        user_name = message.from_user.full_name
        if user_id not in users:
            users[user_id] = user_name
            rejected_messages[user_id] = []
            orders_in_progress[user_id] = 0
            await message.reply("Вы были добавлены в список пользователей.")
        else:
            await message.reply("Вы уже в списке пользователей.")

@dp.message_handler(lambda message: message.text == "-")
async def remove_user(message: types.Message):
    if message.chat.type == 'private':
        user_id = message.from_user.id
        if user_id in users:
            del users[user_id]
            del rejected_messages[user_id]
            del orders_in_progress[user_id]
            await message.reply("Вы были удалены из списка пользователей.")
        else:
            await message.reply("Вы не в списке пользователей.")

@dp.message_handler(commands=['list'])
async def list_users(message: types.Message):
    if message.chat.type == 'private':
        user_list = '\n'.join(f"{name} (Сейчас в работе: {orders_in_progress[id]} заказ(ов))" for id, name in users.items())
        await message.reply(f"Список добавленных пользователей:\n{user_list}")

async def handle_message(message: types.Message):
    if message.chat.type == 'group' or message.chat.type == 'supergroup':
        messages.append((message.chat.id, message.text))
        await send_message((message.chat.id, message.text))

rejection_counts = {}  # Добавляем словарь для отслеживания количества отклонений

async def send_message(message_to_forward):
    if users:
        keyboard = types.InlineKeyboardMarkup().add(
            types.InlineKeyboardButton("Принять", callback_data='done'),
            types.InlineKeyboardButton("Завершил", callback_data='finished')
        )
        async with lock:
            while message_to_forward in messages:
                user = list(users.keys())[0]
                if message_to_forward not in rejected_messages[user]:
                    sent_message = await bot.send_message(chat_id=user, text=message_to_forward[1], reply_markup=keyboard)
                    await asyncio.sleep(10)
                    if message_to_forward in messages:
                        await bot.delete_message(chat_id=user, message_id=sent_message.message_id)
                        rejection_counts[message_to_forward] = rejection_counts.get(message_to_forward, 0) + 1  # Увеличиваем счетчик отклонений
                if message_to_forward not in messages:
                    break
                next_user = list(users.keys()).pop(0)
                users[next_user] = users.pop(next_user)
                if rejection_counts.get(message_to_forward, 0) == len(users):  # Если сообщение было отклонено всеми пользователями
                    await bot.send_message(chat_id=message_to_forward[0], text=f"Заказ был проигнорирован: {message_to_forward[1]}")
                    messages.remove(message_to_forward)  # Удалить сообщение из списка сообщений



async def button(callback_query: types.CallbackQuery):
    if callback_query.data == "done":
        if messages:
            message_to_remove = messages.pop(0)
            for user in users:
                if message_to_remove in rejected_messages[user]:
                    rejected_messages[user].remove(message_to_remove)
            orders_in_progress[callback_query.from_user.id] += 1
            await bot.send_message(chat_id=callback_query.from_user.id, text="Вы приняли заказ")
            next_user = list(users.keys()).pop(0)
            users[next_user] = users.pop(next_user)
    elif callback_query.data == "finished":
        if orders_in_progress[callback_query.from_user.id] > 0:
            orders_in_progress[callback_query.from_user.id] -= 1
            await bot.edit_message_reply_markup(chat_id=callback_query.from_user.id, message_id=callback_query.message.message_id, reply_markup=None)
            await bot.send_message(chat_id=callback_query.from_user.id, text="Вы завершили заказ")

dp.register_message_handler(handle_message)
dp.register_callback_query_handler(button)

if __name__ == '__main__':
    from aiogram import executor
    executor.start_polling(dp, on_startup=on_startup)
