import asyncio
import requests
import yfinance as yf
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import Command
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

COMPANIES = {
    "Евротранс": None,
    "Балтийский лизинг": None,
    "Рольф": None,
    "Brent": "BZ=F"
}

USER_CHAT_ID = None

# --- загрузка chat_id
try:
    with open("chat_id.txt", "r") as f:
        USER_CHAT_ID = int(f.read())
except:
    USER_CHAT_ID = None


# --- данные рынка
def get_stock_data(ticker):
    stock = yf.Ticker(ticker)
    return stock.history(period="6mo", interval="1d")


# --- индикатор
def calculate_ttm_squeeze(df):
    close = df["Close"]

    ma = close.rolling(20).mean()
    std = close.rolling(20).std()

    upper_bb = ma + 2 * std
    lower_bb = ma - 2 * std

    tr = df["High"] - df["Low"]
    atr = tr.rolling(20).mean()

    upper_kc = ma + 1.5 * atr
    lower_kc = ma - 1.5 * atr

    squeeze_on = (lower_bb > lower_kc) & (upper_bb < upper_kc)
    momentum = close - ma

    return squeeze_on.iloc[-1], momentum.iloc[-1]


# --- новости (без зависаний)
def get_news(company):
    news_list = []

    try:
        url = f"https://www.rbc.ru/search/?query={company}"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)

        if r.status_code == 200:
            parts = r.text.split('item__title')
            for p in parts[1:4]:
                title = p.split('>')[1].split('<')[0]
                news_list.append(f"RBC: {title}")
    except:
        pass

    if not news_list:
        return ["Нет новостей"]

    return news_list


# --- бесплатный анализ (без AI)
def ai_analysis(company, price, change, squeeze, momentum, news):

    if squeeze and momentum > 0:
        action = "🔥 BUY"
    elif squeeze and momentum < 0:
        action = "⚠️ WAIT"
    elif momentum < 0:
        action = "❌ AVOID"
    else:
        action = "HOLD"

    sentiment = "позитивный" if momentum > 0 else "негативный"

    news_text = "\n".join(news)

    return f"""
📊 {company}

💰 Цена: {price} ({change}%)

💡 Действие: {action}
🎯 Срок: 1-3 месяца
🧠 Причина: momentum={round(momentum,2)}

📰 Новости:
{news_text}

📊 Сентимент: {sentiment}
"""


# --- отправка
async def send_analysis():
    global USER_CHAT_ID

    print("CHAT_ID:", USER_CHAT_ID)

    if not USER_CHAT_ID:
        return

    for company, ticker in COMPANIES.items():

        if ticker:
            df = get_stock_data(ticker)
        else:
            df = None

        if df is None or df.empty:
            price = "нет данных"
            change = 0
            squeeze = False
            momentum = 0
        else:
            price = round(df["Close"].iloc[-1], 2)
            prev = df["Close"].iloc[-2]
            change = round(((price - prev) / prev) * 100, 2)

            squeeze, momentum = calculate_ttm_squeeze(df)

        news = get_news(company)

        analysis = ai_analysis(company, price, change, squeeze, momentum, news)

        await bot.send_message(USER_CHAT_ID, analysis)


# --- старт
@dp.message(Command("start"))
async def start(message: Message):
    global USER_CHAT_ID
    USER_CHAT_ID = message.chat.id

    with open("chat_id.txt", "w") as f:
        f.write(str(USER_CHAT_ID))

    await message.answer("Бот запущен ✅ Аналитика будет будет в 14:00")


# --- запуск
async def main():
    scheduler.add_job(send_analysis, "cron", hour=14, minute=0)
    
    # 🔥 тест сразу
    await send_analysis()

    scheduler.start()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())