import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime
import json
import os

# Page Configuration
st.set_page_config(page_title="Apex Trading Assistant", layout="wide", page_icon="📈")

TRADES_FILE = "trades.json"

# Symbol mapper for common futures/forex (e.g., XAUUSD -> GC=F, NQ1! -> NQ=F)
SYMBOL_MAP = {
    "XAUUSD": "GC=F",
    "GOLD": "GC=F",
    "NQ1!": "NQ=F",
    "MNQ1!": "MNQ=F",
    "USOIL": "CL=F",
}

def clean_symbol(symbol):
    sym = symbol.strip().upper()
    return SYMBOL_MAP.get(sym, sym)

# --- TRADE STORAGE ---
def load_trades():
    if not os.path.exists(TRADES_FILE):
        return []
    try:
        with open(TRADES_FILE, "r") as f:
            return json.load(f)
    except:
        return []

def save_trades(trades):
    with open(TRADES_FILE, "w") as f:
        json.dump(trades, f, indent=4)

# --- MARKET DATA FETCHER (0 TOKENS) ---
def get_market_data(ticker, period="5d", interval="15m"):
    yf_ticker = clean_symbol(ticker)
    try:
        data = yf.download(yf_ticker, period=period, interval=interval, progress=False)
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = [col[0] for col in data.columns]
        return data
    except Exception as e:
        return pd.DataFrame()

# --- RULE / ASSISTANT ENGINE ---
def analyze_position(trade, current_price):
    entry = trade["entry_price"]
    side = trade["side"].upper()
    sl = trade.get("stop_loss")
    tp = trade.get("take_profit")
    
    if side == "BUY/LONG":
        pnl_pct = ((current_price - entry) / entry) * 100
        hit_sl = sl and current_price <= sl
        hit_tp = tp and current_price >= tp
    else:
        pnl_pct = ((entry - current_price) / entry) * 100
        hit_sl = sl and current_price >= sl
        hit_tp = tp and current_price <= tp

    status = "RUNNING"
    alert_msg = "Price within parameters."
    if hit_sl:
        status = "STOP LOSS TRIGGERED"
        alert_msg = f"⚠️ Stop loss breached at {sl}!"
    elif hit_tp:
        status = "TAKE PROFIT TRIGGERED"
        alert_msg = f"🎯 Target reached at {tp}!"
        
    return pnl_pct, status, alert_msg

# --- UI HEADER ---
st.title("📈 Apex 24/7 Trading Assistant")
st.caption("Live market tracker & chart viewer — 100% token-free.")

# --- SIDEBAR: ADD POSITION ---
st.sidebar.header("Log Open Trade")
with st.sidebar.form("trade_form"):
    ticker = st.text_input("Symbol (e.g., XAUUSD, NQ1!, BTC-USD)", "XAUUSD").upper()
    side = st.selectbox("Position Side", ["BUY/LONG", "SELL/SHORT"])
    entry = st.number_input("Entry Price", min_value=0.0001, format="%.2f")
    sl = st.number_input("Stop Loss (optional)", min_value=0.0, format="%.2f")
    tp = st.number_input("Take Profit (optional)", min_value=0.0, format="%.2f")
    submit = st.form_submit_button("Monitor Trade")
    
    if submit:
        trades = load_trades()
        trades.append({
            "ticker": ticker,
            "side": side,
            "entry_price": entry,
            "stop_loss": sl if sl > 0 else None,
            "take_profit": tp if tp > 0 else None,
            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        })
        save_trades(trades)
        st.sidebar.success(f"Now tracking {ticker}!")

# Auto-refresh every 30 seconds
from streamlit_autorefresh import st_autorefresh
st_autorefresh(interval=30 * 1000, key="screen_refresh")

# --- MAIN DISPLAY ---
trades = load_trades()

st.subheader("📋 Active Monitored Positions")
if not trades:
    st.info("No active trades logged. Use the sidebar to add your first position.")
else:
    for i, trade in enumerate(trades):
        df = get_market_data(trade["ticker"], period="1d", interval="5m")
        if df.empty or 'Close' not in df.columns:
            st.warning(f"Waiting for market data on {trade['ticker']}...")
            continue
            
        current_price = float(df['Close'].iloc[-1])
        pnl, status, alert_msg = analyze_position(trade, current_price)
        
        with st.container():
            col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 3, 1])
            col1.metric("Symbol", trade['ticker'], trade['side'])
            col2.metric("Current Price", f"{current_price:,.2f}", f"{pnl:+.2f}%")
            col3.metric("Entry", f"{trade['entry_price']:,.2f}")
            
            if "TRIGGERED" in status:
                col4.error(f"{status}: {alert_msg}")
            else:
                col4.success(f"STATUS: {status}")
                
            if col5.button("Delete", key=f"del_{i}"):
                trades.pop(i)
                save_trades(trades)
                st.rerun()

    # --- CHART VIEWER ---
    st.markdown("---")
    st.subheader("📊 Live Chart & Levels")
    selected = st.selectbox("Select symbol to view chart:", [t["ticker"] for t in trades])
    
    chart_df = get_market_data(selected, period="5d", interval="15m")
    if not chart_df.empty:
        fig = go.Figure(data=[go.Candlestick(
            x=chart_df.index,
            open=chart_df['Open'],
            high=chart_df['High'],
            low=chart_df['Low'],
            close=chart_df['Close'],
            name=selected
        )])
        
        active_trade = next(t for t in trades if t["ticker"] == selected)
        if active_trade.get("stop_loss"):
            fig.add_hline(y=active_trade["stop_loss"], line_dash="dash", line_color="red", annotation_text="Stop Loss")
        if active_trade.get("take_profit"):
            fig.add_hline(y=active_trade["take_profit"], line_dash="dash", line_color="green", annotation_text="Take Profit")
            
        fig.update_layout(xaxis_rangeslider_visible=False, height=520, template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)
      
