import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
import requests

# Page Configuration
st.set_page_config(
    page_title="Intraday ORB + OI Scanner",
    page_icon="📈",
    layout="wide"
)

# Custom CSS
st.markdown("""
    <style>
    .main-header {
        font-size: 36px;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 20px;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        border-left: 4px solid #1f77b4;
    }
    .buy-signal { color: #00cc00; font-weight: bold; font-size: 18px; }
    .sell-signal { color: #ff4444; font-weight: bold; font-size: 18px; }
    .neutral-signal { color: #ffaa00; font-weight: bold; font-size: 18px; }
    .oi-long { background-color: #d4edda; padding: 5px; border-radius: 5px; }
    .oi-short { background-color: #f8d7da; padding: 5px; border-radius: 5px; }
    .oi-neutral { background-color: #fff3cd; padding: 5px; border-radius: 5px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-header">📊 Intraday ORB + OI Scanner</p>', unsafe_allow_html=True)

# ============================================
# NSE API FUNCTIONS FOR OI DATA
# ============================================
def get_nse_headers():
    return {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.nseindia.com/',
    }

def fetch_oi_data_nse(symbol):
    try:
        session = requests.Session()
        headers = get_nse_headers()
        session.get('https://www.nseindia.com/', headers=headers, timeout=5)
        
        url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}" if symbol in ['NIFTY', 'BANKNIFTY', 'FINNIFTY'] else f"https://www.nseindia.com/api/option-chain-equities?symbol={symbol}"
        
        response = session.get(url, headers=headers, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            return parse_oi_data(data)
        return None
    except:
        return None

def parse_oi_data(data):
    if not data or 'records' not in data:
        return None
    
    records = data['records']
    underlying_value = records.get('underlyingValue', 0)
    strikes = records.get('data', [])
    
    if not strikes:
        return None
    
    total_ce_oi = 0
    total_pe_oi = 0
    atm_strike = None
    min_diff = float('inf')
    
    for strike_data in strikes:
        strike = strike_data.get('strikePrice', 0)
        diff = abs(strike - underlying_value)
        if diff < min_diff:
            min_diff = diff
            atm_strike = strike
        
        if 'CE' in strike_data and strike_data['CE']:
            total_ce_oi += strike_data['CE'].get('openInterest', 0)
        if 'PE' in strike_data and strike_data['PE']:
            total_pe_oi += strike_data['PE'].get('openInterest', 0)
    
    pcr = total_pe_oi / total_ce_oi if total_ce_oi > 0 else 0
    
    if pcr > 1.2:
        oi_sentiment = "BULLISH (High PE OI - Support)"
        oi_signal = "LONG"
    elif pcr < 0.8:
        oi_sentiment = "BEARISH (High CE OI - Resistance)"
        oi_signal = "SHORT"
    else:
        oi_sentiment = "NEUTRAL"
        oi_signal = "NEUTRAL"
    
    return {
        'underlying': round(underlying_value, 2),
        'atm_strike': atm_strike,
        'total_ce_oi': total_ce_oi,
        'total_pe_oi': total_pe_oi,
        'pcr': round(pcr, 2),
        'oi_sentiment': oi_sentiment,
        'oi_signal': oi_signal,
    }

# ============================================
# SIDEBAR CONFIGURATION
# ============================================
st.sidebar.header("⚙️ Scanner Settings")

stock_options = {
    "Nifty 50": [
        "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
        "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS",
        "LT.NS", "AXISBANK.NS", "ASIANPAINT.NS", "MARUTI.NS", "TITAN.NS",
        "SUNPHARMA.NS", "BAJFINANCE.NS", "WIPRO.NS", "ULTRACEMCO.NS", "NESTLEIND.NS",
        "POWERGRID.NS", "NTPC.NS", "TATASTEEL.NS", "M&M.NS", "HCLTECH.NS",
        "TECHM.NS", "INDUSINDBK.NS", "GRASIM.NS", "ADANIENT.NS", "CIPLA.NS",
        "SBILIFE.NS", "BAJAJFINSV.NS", "BRITANNIA.NS", "APOLLOHOSP.NS", "ONGC.NS",
        "EICHERMOT.NS", "TATAMOTORS.NS", "DIVISLAB.NS", "HDFCLIFE.NS", "COALINDIA.NS",
        "JSWSTEEL.NS", "HEROMOTOCO.NS", "BPCL.NS", "DRREDDY.NS", "ADANIPORTS.NS",
        "HINDALCO.NS", "UPL.NS", "SHREECEM.NS", "BAJAJ-AUTO.NS", "TATACONSUM.NS"
    ],
    "Bank Nifty": [
        "HDFCBANK.NS", "ICICIBANK.NS", "KOTAKBANK.NS", "AXISBANK.NS", "SBIN.NS",
        "INDUSINDBK.NS", "BANDHANBNK.NS", "FEDERALBNK.NS", "IDFCFIRSTB.NS", "PNB.NS",
        "BANKBARODA.NS", "CANBK.NS", "UNIONBANK.NS", "AUBANK.NS", "RBLBANK.NS"
    ],
    "Indices (OI Available)": ["NIFTY", "BANKNIFTY"],
    "Custom": []
}

selected_universe = st.sidebar.selectbox("Select Universe", list(stock_options.keys()))

if selected_universe == "Custom":
    custom_stocks = st.sidebar.text_area("Enter Symbols (comma separated)", "RELIANCE.NS, TCS.NS")
    stock_list = [s.strip().upper() for s in custom_stocks.split(",") if s.strip()]
else:
    stock_list = stock_options[selected_universe]

# ORB Settings
st.sidebar.subheader("ORB Settings")
orb_minutes = st.sidebar.slider("Opening Range (minutes)", 5, 30, 15)
volume_multiplier = st.sidebar.slider("Volume Multiplier", 1.0, 3.0, 1.5, 0.1)

# OI Settings
st.sidebar.subheader("🔥 OI Analysis")
enable_oi = st.sidebar.checkbox("Enable OI Analysis", value=True)
oi_weight = st.sidebar.slider("OI Weight in Signal (%)", 0, 50, 30)

# Risk Management
st.sidebar.subheader("Risk Management")
risk_reward = st.sidebar.slider("Risk : Reward", 1.0, 3.0, 2.0, 0.5)

# Filters
st.sidebar.subheader("Filters")
min_price = st.sidebar.number_input("Min Price (₹)", 50, 50000, 100)
max_price = st.sidebar.number_input("Max Price (₹)", 50, 50000, 10000)

refresh = st.sidebar.button("🔄 Refresh Data", type="primary")

# ============================================
# DATA FETCHING FUNCTIONS
# ============================================
@st.cache_data(ttl=300)
def fetch_intraday_data(symbol, period="1d", interval="5m"):
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval)
        if df.empty:
            return None
        
        df.reset_index(inplace=True)
        # Handle different column names
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        
        # Rename date column if needed
        if 'Datetime' in df.columns:
            df.rename(columns={'Datetime': 'Date'}, inplace=True)
        elif 'Date' not in df.columns and len(df.columns) > 0:
            # Use first column as date
            first_col = df.columns[0]
            df.rename(columns={first_col: 'Date'}, inplace=True)
            
        return df
    except Exception as e:
        return None

@st.cache_data(ttl=300)
def fetch_daily_data(symbol, period="20d"):
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval="1d")
        if df.empty:
            return None
        
        df.reset_index(inplace=True)
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        
        if 'Datetime' in df.columns:
            df.rename(columns={'Datetime': 'Date'}, inplace=True)
        elif 'Date' not in df.columns and len(df.columns) > 0:
            first_col = df.columns[0]
            df.rename(columns={first_col: 'Date'}, inplace=True)
            
        return df
    except:
        return None

# ============================================
# ORB ANALYSIS
# ============================================
def analyze_orb(df_intraday, symbol, orb_mins=15):
    if df_intraday is None or df_intraday.empty:
        return None
    
    # Ensure Date column exists
    if 'Date' not in df_intraday.columns:
        return None
    
    try:
        df_intraday['Date'] = pd.to_datetime(df_intraday['Date'])
        today = datetime.now().date()
        df_today = df_intraday[df_intraday['Date'].dt.date == today].copy()
    except:
        return None
    
    if df_today.empty:
        return None
    
    df_today = df_today.sort_values('Date')
    candles_needed = max(1, orb_mins // 5)
    opening_range = df_today.head(candles_needed)
    
    if opening_range.empty:
        return None
    
    orb_high = opening_range['High'].max()
    orb_low = opening_range['Low'].min()
    current_price = df_today['Close'].iloc[-1]
    current_high = df_today['High'].max()
    current_low = df_today['Low'].min()
    
    signal = "NEUTRAL"
    entry_price = None
    stop_loss = None
    target = None
    
    if current_price > orb_high:
        signal = "BUY"
        entry_price = orb_high
        stop_loss = orb_low
        target = entry_price + (entry_price - stop_loss) * risk_reward
        
    elif current_price < orb_low:
        signal = "SELL"
        entry_price = orb_low
        stop_loss = orb_high
        target = entry_price - (stop_loss - entry_price) * risk_reward
    
    risk_per_share = abs(entry_price - stop_loss) if entry_price and stop_loss else 0
    risk_percent = (risk_per_share / entry_price) * 100 if entry_price else 0
    
    return {
        'symbol': symbol.replace('.NS', ''),
        'current_price': round(current_price, 2),
        'orb_high': round(orb_high, 2),
        'orb_low': round(orb_low, 2),
        'signal': signal,
        'entry_price': round(entry_price, 2) if entry_price else None,
        'stop_loss': round(stop_loss, 2) if stop_loss else None,
        'target': round(target, 2) if target else None,
        'risk_percent': round(risk_percent, 2),
        'day_high': round(current_high, 2),
        'day_low': round(current_low, 2)
    }

# ============================================
# COMBINED SIGNAL CALCULATION
# ============================================
def get_combined_signal(orb_signal, oi_signal, oi_weight):
    signal_scores = {"BUY": 1, "NEUTRAL": 0, "SELL": -1}
    
    orb_score = signal_scores.get(orb_signal, 0)
    oi_score = signal_scores.get(oi_signal, 0)
    
    combined = (orb_score * (100 - oi_weight) + oi_score * oi_weight) / 100
    
    if combined > 0.3:
        return "STRONG BUY", combined
    elif combined > 0:
        return "BUY", combined
    elif combined < -0.3:
        return "STRONG SELL", combined
    elif combined < 0:
        return "SELL", combined
    else:
        return "NEUTRAL", combined

# ============================================
# MAIN SCANNING LOGIC
# ============================================
if refresh:
    st.subheader("🔍 Scanning Stocks...")
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    results = []
    total_stocks = len(stock_list)
    
    for i, symbol in enumerate(stock_list):
        progress = (i + 1) / total_stocks
        progress_bar.progress(min(progress, 0.99))
        status_text.text(f"Analyzing {symbol}... ({i+1}/{total_stocks})")
        
        df_5m = fetch_intraday_data(symbol, period="1d", interval="5m")
        orb_result = analyze_orb(df_5m, symbol, orb_minutes)
        
        if orb_result and min_price <= orb_result['current_price'] <= max_price:
            
            oi_data = None
            if enable_oi:
                nse_symbol = symbol.replace('.NS', '')
                oi_data = fetch_oi_data_nse(nse_symbol)
            
            orb_signal = orb_result['signal']
            oi_signal = oi_data['oi_signal'] if oi_data else "NEUTRAL"
            
            combined_signal, confidence_score = get_combined_signal(
                orb_signal, oi_signal, oi_weight
            )
            
            result = {
                **orb_result,
                'combined_signal': combined_signal,
                'confidence': round(abs(confidence_score) * 100, 1),
                'orb_signal': orb_signal,
                'oi_signal': oi_signal,
                'oi_data': oi_data
            }
            
            results.append(result)
    
    progress_bar.empty()
    status_text.empty()
    
    # ============================================
    # DISPLAY RESULTS
    # ============================================
    if not results:
        st.warning("⚠️ No signals found. Market might be closed or no breakouts yet.")
        st.info("💡 Tip: Indian market hours are 9:15 AM - 3:30 PM IST. ORB works best between 9:30-11:00 AM.")
    else:
        df_results = pd.DataFrame([{k: v for k, v in r.items() if k != 'oi_data'} for r in results])
        
        signal_order = {'STRONG BUY': 0, 'BUY': 1, 'NEUTRAL': 2, 'SELL': 3, 'STRONG SELL': 4}
        df_results['sort_key'] = df_results['combined_signal'].map(signal_order)
        df_results = df_results.sort_values(['sort_key', 'confidence'], ascending=[True, False])
        df_results = df_results.drop('sort_key', axis=1)
        
        # Summary
        col1, col2, col3, col4, col5 = st.columns(5)
        
        signals_count = df_results['combined_signal'].value_counts().to_dict()
        
        with col1:
            st.metric("🟢 STRONG BUY", signals_count.get('STRONG BUY', 0))
        with col2:
            st.metric("🟩 BUY", signals_count.get('BUY', 0))
        with col3:
            st.metric("🟡 NEUTRAL", signals_count.get('NEUTRAL', 0))
        with col4:
            st.metric("🟥 SELL", signals_count.get('SELL', 0))
        with col5:
            st.metric("🔴 STRONG SELL", signals_count.get('STRONG SELL', 0))
        
        st.markdown("---")
        
        # Display each stock
        for idx, row in enumerate(results):
            sig = row['combined_signal']
            if 'STRONG BUY' in sig:
                emoji, color_class = "🚀", "buy-signal"
            elif 'BUY' in sig:
                emoji, color_class = "🟢", "buy-signal"
            elif 'STRONG SELL' in sig:
                emoji, color_class = "🔻", "sell-signal"
            elif 'SELL' in sig:
                emoji, color_class = "🔴", "sell-signal"
            else:
                emoji, color_class = "🟡", "neutral-signal"
            
            with st.expander(f"{emoji} **{row['symbol']}** | {sig} | ₹{row['current_price']} | Confidence: {row['confidence']}%"):
                
                col1, col2, col3 = st.columns([2, 2, 2])
                
                with col1:
                    st.markdown(f"""
                    <div class="metric-card">
                    <b>📈 ORB Analysis</b><br>
                    Current: <b>₹{row['current_price']}</b><br>
                    ORB High: ₹{row['orb_high']}<br>
                    ORB Low: ₹{row['orb_low']}<br>
                    Day High: ₹{row['day_high']}<br>
                    Day Low: ₹{row['day_low']}<br>
                    <hr>
                    <b>ORB Signal:</b> {row['orb_signal']}
                    </div>
                    """, unsafe_allow_html=True)
                
                with col2:
                    if row['entry_price']:
                        st.markdown(f"""
                        <div class="metric-card">
                        <b>🎯 Trade Setup</b><br>
                        Entry: <b>₹{row['entry_price']}</b><br>
                        SL: <span style="color:red">₹{row['stop_loss']}</span><br>
                        Target: <span style="color:green">₹{row['target']}</span><br>
                        Risk: {row['risk_percent']}%<br>
                        R:R = 1:{risk_reward}
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown("""
                        <div class="metric-card">
                        <b>⏳ Waiting</b><br>
                        Price within ORB range.<br>
                        Wait for breakout.
                        </div>
                        """, unsafe_allow_html=True)
                
                with col3:
                    if row['oi_data']:
                        oi = row['oi_data']
                        oi_class = "oi-long" if oi['oi_signal'] == "LONG" else ("oi-short" if oi['oi_signal'] == "SHORT" else "oi-neutral")
                        
                        st.markdown(f"""
                        <div class="metric-card">
                        <b>🔥 OI Analysis</b><br>
                        <div class="{oi_class}">
                        <b>OI Signal:</b> {oi['oi_signal']}<br>
                        <b>Sentiment:</b> {oi['oi_sentiment']}
                        </div>
                        <hr>
                        PCR Ratio: <b>{oi['pcr']}</b><br>
                        ATM Strike: {oi['atm_strike']}<br>
                        CE OI: {oi['total_ce_oi']:,}<br>
                        PE OI: {oi['total_pe_oi']:,}
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown("""
                        <div class="metric-card">
                        <b>🔥 OI Analysis</b><br>
                        OI data not available.<br>
                        (NSE API limit or non-F&O stock)
                        </div>
                        """, unsafe_allow_html=True)
                
                st.markdown("---")
                st.markdown(f"**📊 Signal Logic:** ORB = {row['orb_signal']} + OI = {row['oi_signal']} → **{sig}** (Confidence: {row['confidence']}%)")
        
        st.markdown("---")
        csv = df_results.to_csv(index=False)
        st.download_button(
            label="📥 Download Results",
            data=csv,
            file_name=f"orb_oi_scanner_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv"
        )

# ============================================
# OI EDUCATION SECTION
# ============================================
with st.expander("📚 OI Analysis Guide"):
    st.markdown("""
    ### 🔥 Open Interest (OI) Kya Hai?
    
    **OI** = Total outstanding derivative contracts (Futures + Options) jo abhi open hain.
    
    ### 📊 Key Metrics:
    
    | Metric | Value | Interpretation |
    |--------|-------|----------------|
    | **PCR > 1.2** | High Put OI | Bullish (Support) |
    | **PCR < 0.8** | High Call OI | Bearish (Resistance) |
    | **PCR 0.8-1.2** | Balanced | Neutral |
    
    ### 🎯 Combined Signal Logic:
    
    | ORB Signal | OI Signal | Combined | Action |
    |------------|-----------|----------|--------|
    | BUY | LONG | 🚀 STRONG BUY | High confidence buy |
    | BUY | SHORT | 🟢 BUY | Caution - weak buy |
    | SELL | SHORT | 🔻 STRONG SELL | High confidence short |
    | SELL | LONG | 🔴 SELL | Caution - weak short |
    
    ### ⚠️ Important:
    - OI data **NSE India** se aata hai (real-time)
    - Sirf **F&O stocks** ke liye available hai
    - **Max Pain** = Strike jahan sabse zyada loss hoga
    """)

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: gray; font-size: 12px;">
<b>⚠️ Disclaimer:</b> Educational purposes only. Not financial advice. 
Data from Yahoo Finance (delayed) & NSE India. Trade at your own risk.
</div>
""", unsafe_allow_html=True)
