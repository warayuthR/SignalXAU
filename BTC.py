import streamlit as st
import pandas as pd
import numpy as np
import requests
from streamlit_autorefresh import st_autorefresh

# รีเฟรชอัตโนมัติทุก 10 วินาที (เพื่อให้แสดงข้อมูลใหม่ทันทีหลังแท่งเทียน 5 นาทีปิดแล้ว)
st_autorefresh(interval=10000, limit=100, key="datarefresh")

def get_price_data(symbol="PAXGUSDT", interval="5m", limit=200):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    try:
        response = requests.get(url)
        data = response.json()
        if isinstance(data, dict) and data.get("code"):
            st.error("Error fetching data: " + data.get("msg", "Unknown error"))
            return pd.DataFrame()
        df = pd.DataFrame(data, columns=[
            "timestamp", "open", "high", "low", "close", "volume",
            "close_time", "quote_asset_volume", "number_of_trades",
            "taker_buy_base_volume", "taker_buy_quote_volume", "ignore"
        ])
        # แปลงเวลาให้เป็น UTC แล้วแปลงเป็นเวลาประเทศไทย (Asia/Bangkok)
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True).dt.tz_convert("Asia/Bangkok")
        df["open"] = df["open"].astype(float)
        df["high"] = df["high"].astype(float)
        df["low"] = df["low"].astype(float)
        df["close"] = df["close"].astype(float)
        df["volume"] = df["volume"].astype(float)
        return df.copy(deep=True)
    except Exception as e:
        st.error(f"Exception fetching data: {e}")
        return pd.DataFrame()

def calculate_signals(df):
    """
    คำนวณสัญญาณแบบ vectorized:
    - BUY: เมื่อแท่งเทียนปัจจุบันมี close > open และแท่งก่อนหน้ามี close <= open
    - SELL: เมื่อแท่งเทียนปัจจุบันมี close < open และแท่งก่อนหน้ามี close >= open
    """
    df = df.copy()
    df["prev_open"] = df["open"].shift(1)
    df["prev_close"] = df["close"].shift(1)
    conditions = [
        (df["close"] > df["open"]) & (df["prev_close"] <= df["prev_open"]),
        (df["close"] < df["open"]) & (df["prev_close"] >= df["prev_open"])
    ]
    choices = ["BUY", "SELL"]
    df["Signal"] = np.select(conditions, choices, default="")
    df.drop(columns=["prev_open", "prev_close"], inplace=True)
    return df

def calculate_take_profit(df, profit_threshold=0.02):
    """
    คำนวณ Take Profit:
    - สำหรับสัญญาณ BUY: ถ้าแท่งก่อนหน้ามีสัญญาณ BUY และแท่งปัจจุบันมี close >= close ของแท่งก่อนหน้าคูณ (1 + profit_threshold)
    - สำหรับสัญญาณ SELL: ถ้าแท่งก่อนหน้ามีสัญญาณ SELL และแท่งปัจจุบันมี close <= close ของแท่งก่อนหน้าคูณ (1 - profit_threshold)
    """
    df = df.copy()
    tp_signals = ["" for _ in range(len(df))]
    for i in range(1, len(df)):
        if df["Signal"].iloc[i-1] == "BUY" and df["close"].iloc[i] >= df["close"].iloc[i-1] * (1 + profit_threshold):
            tp_signals[i] = "TP"
        elif df["Signal"].iloc[i-1] == "SELL" and df["close"].iloc[i] <= df["close"].iloc[i-1] * (1 - profit_threshold):
            tp_signals[i] = "TP"
    df["Take Profit"] = tp_signals
    return df

def main():
    st.title("Real-Time Gold Data Table with Signals")
    st.markdown("แสดง Data Table สำหรับทองคำ (PAXGUSDT) พร้อมสัญญาณ BUY/SELL และ Take Profit ทันทีหลังจากแท่งเทียน 5 นาทีปิดแล้ว")

    # ดึงข้อมูลและเรียงลำดับตามเวลา
    df = get_price_data(symbol="PAXGUSDT", interval="5m", limit=200)
    if df.empty:
        st.error("ไม่มีข้อมูลจาก API")
        return
    df = df.sort_values(by="timestamp")
    
    # คำนวณสัญญาณเทรดและ Take Profit
    df = calculate_signals(df)
    df = calculate_take_profit(df, profit_threshold=0.02)
    
    # แสดง Data Table (ข้อมูลแท่งล่าสุด)
    st.dataframe(df[["timestamp", "open", "high", "low", "close", "Signal", "Take Profit"]].tail(50))

if __name__ == "__main__":
    main()
