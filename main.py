import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
import requests
import pandas as pd
import datetime as dt
import pytz
from ta.momentum import RSIIndicator
from ta.trend import ADXIndicator

BOT_TOKEN = os.getenv("BOT_TOKEN")
TIMEZONE = pytz.timezone("Asia/Ho_Chi_Minh")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

def get_binance_symbols():
    url = "https://api.binance.com/api/v3/exchangeInfo"
    data = requests.get(url).json()
    usdt_pairs = [s['symbol'] for s in data['symbols'] if s['quoteAsset'] == 'USDT' and s['status'] == 'TRADING']
    return [s for s in usdt_pairs if not s.endswith('BULLUSDT') and not s.endswith('BEARUSDT')]

def fetch_ohlcv(symbol, interval, limit=100):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    try:
        data = requests.get(url).json()
        df = pd.DataFrame(data, columns=["time", "open", "high", "low", "close", "volume", "close_time", "quote_asset_volume", "trades", "taker_base", "taker_quote", "ignore"])
        df['close'] = pd.to_numeric(df['close'])
        df['high'] = pd.to_numeric(df['high'])
        df['low'] = pd.to_numeric(df['low'])
        return df
    except:
        return None

def analyze_rsi_adx(df):
    rsi = RSIIndicator(close=df['close'], window=14).rsi()
    adx = ADXIndicator(high=df['high'], low=df['low'], close=df['close'], window=14)
    return {
        'RSI': round(rsi.iloc[-1], 2),
        'ADX': round(adx.adx().iloc[-1], 2),
        '+DI': round(adx.adx_pos().iloc[-1], 2),
        '-DI': round(adx.adx_neg().iloc[-1], 2),
    }

def get_price(symbol):
    try:
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
        return float(requests.get(url).json()['price'])
    except:
        return None

def build_report(interval, limit):
    symbols = get_binance_symbols()[:limit]
    hits = []
    for sym in symbols:
        df = fetch_ohlcv(sym, interval)
        if df is None or len(df) < 20:
            continue
        r = analyze_rsi_adx(df)
        if r['RSI'] < 23 or r['RSI'] > 70:
            price = get_price(sym)
            hits.append(f"{sym} – Giá: {price} – RSI: {r['RSI']} – ADX: {r['ADX']} – +DI: {r['+DI']} – -DI: {r['-DI']}")
    now = dt.datetime.now(TIMEZONE).strftime("%d-%m %H:%M")
    report = f"🌆 Báo cáo {interval.upper()} – {now}\n"
    if hits:
        report += "\n".join(hits)
    else:
        report += "Không có tín hiệu RSI <23 hoặc >70"
    return report

@dp.message_handler(commands=['start', 'help'])
async def send_welcome(message: types.Message):
    await message.reply("Chào bạn! Gõ ví dụ: gửi 4h 20coin hoặc gửi 1d 100coin")

@dp.message_handler(lambda msg: 'gửi' in msg.text.lower())
async def handle_report(message: types.Message):
    text = message.text.lower()
    parts = text.split()
    try:
        interval_input = parts[1]
        limit = int(parts[2].replace('coin', '')) if len(parts) > 2 else 100
        interval_map = {'1h': '1h', '4h': '4h', '1d': '1d'}
        real_interval = interval_map.get(interval_input, None)
        if real_interval:
            await message.reply(f"⏳ Đang tạo báo cáo RSI {real_interval.upper()} cho top {limit} coin...")
            report = build_report(real_interval, limit)
            await message.reply(report)
        else:
            await message.reply("Khung thời gian không hợp lệ. Dùng 1h, 4h, hoặc 1d.")
    except Exception as e:
        await message.reply(f"Lỗi xử lý lệnh: {e}")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
