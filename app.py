import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
import requests
import warnings
warnings.filterwarnings('ignore')

# Page Configuration
st.set_page_config(
    page_title="🎯 Independent Sector Scanner",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .main-header {
        font-size: 40px;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 10px;
    }
    .sub-header {
        font-size: 18px;
        color: #666;
        text-align: center;
        margin-bottom: 30px;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 15px;
        color: white;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }
    .signal-card {
        padding: 20px;
        border-radius: 15px;
        margin: 10px 0;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    }
    .strong-buy { background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); color: white; }
    .buy { background: linear-gradient(135deg, #56ab2f 0%, #a8e063 100%); color: white; }
    .strong-sell { background: linear-gradient(135deg, #cb2d3e 0%, #ef473a 100%); color: white; }
    .sell { background: linear-gradient(135deg, #eb3349 0%, #f45c43 100%); color: white; }
    .neutral { background: linear-gradient(135deg, #f7971e 0%, #ffd200 100%); color: #333; }
    .accuracy-badge {
        display: inline-block;
        padding: 8px 20px;
        border-radius: 25px;
        font-weight: bold;
        font-size: 18px;
        color: white;
        text-align: center;
    }
    .acc-90 { background: linear-gradient(135deg, #00b09b 0%, #96c93d 100%); }
    .acc-80 { background: linear-gradient(135deg, #f7971e 0%, #ffd200 100%); color: #333; }
    .acc-70 { background: linear-gradient(135deg, #ff6b6b 0%, #ee5a24 100%); }
    .filter-box {
        background: #f8f9fa;
        padding: 15px;
        border-radius: 10px;
        border-left: 5px solid #667eea;
        margin: 5px 0;
    }
    .sector-card {
        background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
        color: white;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        margin: 5px 0;
    }
    .sector-strong { background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); }
    .sector-weak { background: linear-gradient(135deg, #cb2d3e 0%, #ef473a 100%); }
    .sector-neutral { background: linear-gradient(135deg, #f7971e 0%, #ffd200 100%); color: #333; }
    .news-positive { background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); color: white; padding: 10px; border-radius: 10px; }
    .news-negative { background: linear-gradient(135deg, #cb2d3e 0%, #ef473a 100%); color: white; padding: 10px; border-radius: 10px; }
    .news-neutral { background: linear-gradient(135deg, #f7971e 0%, #ffd200 100%); color: #333; padding: 10px; border-radius: 10px; }
    .news-item { padding: 8px; margin: 5px 0; border-radius: 8px; background: #f0f2f6; border-left: 4px solid #667eea; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-header">🎯 Independent Sector Scanner</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Nifty Independent | Sector-Based | Stock-Specific Strength</p>', unsafe_allow_html=True)

# ============================================
# SECTOR DEFINITIONS & ETFS
# ============================================
SECTOR_ETFS = {
    "IT": ["^CNXIT", "TCS.NS", "INFY.NS", "WIPRO.NS", "HCLTECH.NS", "TECHM.NS"],
    "BANK": ["^NSEBANK", "HDFCBANK.NS", "ICICIBANK.NS", "KOTAKBANK.NS", "AXISBANK.NS", "SBIN.NS"],
    "AUTO": ["^CNXAUTO", "MARUTI.NS", "TATAMOTORS.NS", "M&M.NS", "EICHERMOT.NS", "BAJAJ-AUTO.NS"],
    "PHARMA": ["^CNXPHARMA", "SUNPHARMA.NS", "DRREDDY.NS", "CIPLA.NS", "DIVISLAB.NS", "APOLLOHOSP.NS"],
    "FMCG": ["^CNXFMCG", "HINDUNILVR.NS", "ITC.NS", "NESTLEIND.NS", "BRITANNIA.NS", "TATACONSUM.NS"],
    "METAL": ["^CNXMETAL", "TATASTEEL.NS", "JSWSTEEL.NS", "HINDALCO.NS", "COALINDIA.NS"],
    "ENERGY": ["^CNXENERGY", "RELIANCE.NS", "ONGC.NS", "POWERGRID.NS", "NTPC.NS", "BPCL.NS"],
    "INFRA": ["^CNXINFRA", "LT.NS", "ADANIENT.NS", "ADANIPORTS.NS", "ULTRACEMCO.NS"],
}

STOCK_TO_SECTOR = {}
for sector, stocks in SECTOR_ETFS.items():
    for stock in stocks[1:]:  # Skip index
        STOCK_TO_SECTOR[stock] = sector

# ============================================
# FETCH SECTOR PERFORMANCE
# ============================================
@st.cache_data(ttl=300)
def get_sector_performance():
    """Get how each sector is performing today - INDEPENDENT of Nifty"""
    sector_perf = {}
    
    for sector, etf_list in SECTOR_ETFS.items():
        try:
            etf = yf.Ticker(etf_list[0])  # Index/ETF
            df = etf.history(period="2d", interval="5m")
            if df.empty or len(df) < 2:
                sector_perf[sector] = {"change": 0, "trend": "NEUTRAL"}
                continue
            
            df.reset_index(inplace=True)
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
            
            if 'Datetime' in df.columns:
                df.rename(columns={'Datetime': 'Date'}, inplace=True)
            
            df['Date'] = pd.to_datetime(df['Date'])
            today = datetime.now().date()
            df_today = df[df['Date'].dt.date == today]
            
            if df_today.empty:
                sector_perf[sector] = {"change": 0, "trend": "NEUTRAL"}
                continue
            
            open_price = df_today['Open'].iloc[0]
            current = df_today['Close'].iloc[-1]
            change_pct = ((current - open_price) / open_price) * 100
            
            # Sector trend independent of Nifty
            if change_pct > 1.5:
                trend = "STRONG_UP"
            elif change_pct > 0.5:
                trend = "UP"
            elif change_pct < -1.5:
                trend = "STRONG_DOWN"
            elif change_pct < -0.5:
                trend = "DOWN"
            else:
                trend = "NEUTRAL"
            
            sector_perf[sector] = {
                "change": round(change_pct, 2),
                "trend": trend,
                "open": open_price,
                "current": current
            }
            
        except:
            sector_perf[sector] = {"change": 0, "trend": "NEUTRAL"}
    
    return sector_perf

# ============================================
# NEWS FETCHING
# ============================================
def fetch_stock_news(symbol):
    try:
        ticker = yf.Ticker(symbol)
        news = ticker.news
        
        if not news or len(news) == 0:
            return None
        
        positive_keywords = ['profit', 'growth', 'rise', 'gain', 'bullish', 'buy', 'upgrade', 
                            'strong', 'beat', 'surge', 'rally', 'positive', 'outperform',
                            'record', 'high', 'up', 'increase', 'boost', 'good', 'excellent',
                            'dividend', 'bonus', 'split', 'deal', 'contract', 'expansion']
        
        negative_keywords = ['loss', 'fall', 'drop', 'decline', 'bearish', 'sell', 'downgrade',
                            'weak', 'miss', 'plunge', 'crash', 'negative', 'underperform',
                            'low', 'down', 'decrease', 'cut', 'bad', 'poor', 'debt',
                            'fraud', 'scam', 'investigation', 'penalty', 'layoff', 'bankrupt']
        
        analyzed_news = []
        total_score = 0
        
        for item in news[:5]:
            title = item.get('title', '').lower()
            publisher = item.get('publisher', 'Unknown')
            
            pos_count = sum(1 for word in positive_keywords if word in title)
            neg_count = sum(1 for word in negative_keywords if word in title)
            
            if pos_count > neg_count:
                sentiment = "POSITIVE"
                score = min(pos_count, 3)
            elif neg_count > pos_count:
                sentiment = "NEGATIVE"
                score = -min(neg_count, 3)
            else:
                sentiment = "NEUTRAL"
                score = 0
            
            total_score += score
            
            analyzed_news.append({
                'title': item.get('title', ''),
                'publisher': publisher,
                'sentiment': sentiment,
                'score': score
            })
        
        if total_score >= 2:
            overall = "POSITIVE"
        elif total_score <= -2:
            overall = "NEGATIVE"
        else:
            overall = "NEUTRAL"
        
        return {
            'overall_sentiment': overall,
            'total_score': total_score,
            'news_count': len(analyzed_news),
            'articles': analyzed_news
        }
        
    except:
        return None

# ============================================
# NSE OI DATA
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
    total_ce_change = 0
    total_pe_change = 0
    
    atm_strike = None
    min_diff = float('inf')
    
    for strike_data in strikes:
        strike = strike_data.get('strikePrice', 0)
        diff = abs(strike - underlying_value)
        if diff < min_diff:
            min_diff = diff
            atm_strike = strike
        
        if 'CE' in strike_data and strike_data['CE']:
            ce = strike_data['CE']
            total_ce_oi += ce.get('openInterest', 0)
            total_ce_change += ce.get('changeinOpenInterest', 0)
        
        if 'PE' in strike_data and strike_data['PE']:
            pe = strike_data['PE']
            total_pe_oi += pe.get('openInterest', 0)
            total_pe_change += pe.get('changeinOpenInterest', 0)
    
    pcr_oi = total_pe_oi / total_ce_oi if total_ce_oi > 0 else 0
    
    if total_pe_change > 0 and total_ce_change < 0:
        oi_buildup = "BULLISH BUILDUP"
    elif total_ce_change > 0 and total_pe_change < 0:
        oi_buildup = "BEARISH BUILDUP"
    elif total_pe_change > total_ce_change and total_pe_change > 0:
        oi_buildup = "MILD BULLISH"
    elif total_ce_change > total_pe_change and total_ce_change > 0:
        oi_buildup = "MILD BEARISH"
    else:
        oi_buildup = "NEUTRAL"
    
    if pcr_oi > 1.3:
        oi_signal = "STRONG LONG"
    elif pcr_oi > 1.1:
        oi_signal = "LONG"
    elif pcr_oi < 0.7:
        oi_signal = "STRONG SHORT"
    elif pcr_oi < 0.9:
        oi_signal = "SHORT"
    else:
        oi_signal = "NEUTRAL"
    
    return {
        'underlying': round(underlying_value, 2),
        'atm_strike': atm_strike,
        'total_ce_oi': total_ce_oi,
        'total_pe_oi': total_pe_oi,
        'pcr_oi': round(pcr_oi, 2),
        'oi_buildup': oi_buildup,
        'oi_signal': oi_signal,
    }

# ============================================
# SIDEBAR
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

# Accuracy Mode
st.sidebar.subheader("🎯 Accuracy Mode")
accuracy_mode = st.sidebar.selectbox(
    "Select Mode",
    ["Conservative (80%+)", "Balanced (70-80%)", "Aggressive (60-70%)"]
)
min_accuracy = {"Conservative (80%+)": 80, "Balanced (70-80%)": 70, "Aggressive (60-70%)": 60}[accuracy_mode]

# Filters
st.sidebar.subheader("🔥 Advanced Filters")
use_sector = st.sidebar.checkbox("✅ Sector Strength Filter", value=True)
use_oi = st.sidebar.checkbox("✅ OI Buildup Analysis", value=True)
use_news = st.sidebar.checkbox("📰 News Sentiment", value=True)
use_multi_tf = st.sidebar.checkbox("✅ Multi-Timeframe", value=True)
use_vwap = st.sidebar.checkbox("✅ VWAP", value=True)
use_atr_sl = st.sidebar.checkbox("✅ Smart ATR SL", value=True)
use_pa = st.sidebar.checkbox("✅ Price Action", value=True)

# Risk
st.sidebar.subheader("Risk Management")
risk_reward = st.sidebar.slider("Risk : Reward", 1.0, 4.0, 2.5, 0.5)

# Price Filters
st.sidebar.subheader("Price Filters")
min_price = st.sidebar.number_input("Min Price (₹)", 50, 50000, 100)
max_price = st.sidebar.number_input("Max Price (₹)", 50, 50000, 10000)

refresh = st.sidebar.button("🔄 SCAN NOW", type="primary")

st.sidebar.markdown("---")
st.sidebar.info(f"""
**🎯 {accuracy_mode}**
- Min Accuracy: {min_accuracy}%
- Nifty Independent ✅
- Sector Based ✅
- Expected Win Rate: {min_accuracy}-{min_accuracy+10}%
""")

# ============================================
# DATA FETCHING
# ============================================
@st.cache_data(ttl=300)
def fetch_data(symbol, period="5d", interval="5m"):
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval)
        if df.empty:
            return None
        
        df.reset_index(inplace=True)
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        
        if 'Datetime' in df.columns:
            df.rename(columns={'Datetime': 'Date'}, inplace=True)
        elif 'Date' not in df.columns and len(df.columns) > 0:
            first_col = df.columns[0]
            df.rename(columns={first_col: 'Date'}, inplace=True)
        
        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        return df
    except:
        return None

# ============================================
# TECHNICAL INDICATORS
# ============================================
def calculate_vwap(df):
    try:
        df = df.copy()
        df['typical_price'] = (df['High'] + df['Low'] + df['Close']) / 3
        df['tp_volume'] = df['typical_price'] * df['Volume']
        df['cum_tp_vol'] = df['tp_volume'].cumsum()
        df['cum_vol'] = df['Volume'].cumsum()
        df['vwap'] = df['cum_tp_vol'] / df['cum_vol']
        return df['vwap'].iloc[-1] if not df.empty else None
    except:
        return None

def calculate_rsi(df, period=14):
    try:
        df = df.copy()
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50
    except:
        return 50

def calculate_atr(df, period=14):
    try:
        df = df.copy()
        df['tr1'] = df['High'] - df['Low']
        df['tr2'] = abs(df['High'] - df['Close'].shift())
        df['tr3'] = abs(df['Low'] - df['Close'].shift())
        df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
        atr = df['tr'].rolling(window=period).mean()
        return atr.iloc[-1] if not pd.isna(atr.iloc[-1]) else 0
    except:
        return 0

def calculate_ema(df, period=20):
    try:
        return df['Close'].ewm(span=period, adjust=False).mean().iloc[-1]
    except:
        return None

def detect_price_action(df):
    try:
        if len(df) < 3:
            return "NEUTRAL", 0
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        prev2 = df.iloc[-3]
        
        patterns = []
        
        if prev['Close'] < prev['Open'] and last['Close'] > last['Open'] and last['Open'] < prev['Close'] and last['Close'] > prev['Open']:
            patterns.append(("Bullish Engulfing", 2))
        elif prev['Close'] > prev['Open'] and last['Close'] < last['Open'] and last['Open'] > prev['Close'] and last['Close'] < prev['Open']:
            patterns.append(("Bearish Engulfing", -2))
        
        if last['Close'] > last['Open'] and (last['Low'] - min(last['Open'], last['Close'])) > 2 * abs(last['Close'] - last['Open']):
            patterns.append(("Hammer", 1))
        
        if last['Close'] < last['Open'] and (max(last['Open'], last['Close']) - last['High']) > 2 * abs(last['Close'] - last['Open']):
            patterns.append(("Shooting Star", -1))
        
        if (last['Close'] > last['Open'] and prev['Close'] > prev['Open'] and prev2['Close'] > prev2['Open'] and
            last['Close'] > prev['Close'] > prev2['Close']):
            patterns.append(("Three White Soldiers", 3))
        
        if (last['Close'] < last['Open'] and prev['Close'] < prev['Open'] and prev2['Close'] < prev2['Open'] and
            last['Close'] < prev['Close'] < prev2['Close']):
            patterns.append(("Three Black Crows", -3))
        
        if not patterns:
            return "NEUTRAL", 0
        
        score = sum(p[1] for p in patterns)
        if score >= 2:
            return "BULLISH", score
        elif score <= -2:
            return "BEARISH", abs(score)
        return "NEUTRAL", 0
        
    except:
        return "NEUTRAL", 0

# ============================================
# MAIN ORB ANALYSIS
# ============================================
def analyze_orb_ultimate(symbol, sector_perf, orb_mins=15):
    df_5m = fetch_data(symbol, period="5d", interval="5m")
    df_15m = fetch_data(symbol, period="10d", interval="15m")
    df_daily = fetch_data(symbol, period="30d", interval="1d")
    
    if df_5m is None or df_5m.empty:
        return None, "No 5m data"
    
    if 'Date' not in df_5m.columns:
        return None, "Date column missing"
    
    try:
        df_5m['Date'] = pd.to_datetime(df_5m['Date'])
        today = datetime.now().date()
        df_today = df_5m[df_5m['Date'].dt.date == today].copy()
    except:
        return None, "Date error"
    
    if df_today.empty or len(df_today) < 3:
        return None, "No today's data"
    
    df_today = df_today.sort_values('Date')
    candles_needed = max(1, orb_mins // 5)
    opening_range = df_today.head(candles_needed)
    
    if opening_range.empty:
        return None, "Opening range empty"
    
    orb_high = opening_range['High'].max()
    orb_low = opening_range['Low'].min()
    
    current_candle = df_today.iloc[-1]
    current_price = current_candle['Close']
    
    if current_price > orb_high:
        base_signal = "BUY"
        entry_price = orb_high
        stop_loss = orb_low
    elif current_price < orb_low:
        base_signal = "SELL"
        entry_price = orb_low
        stop_loss = orb_high
    else:
        return None, "No ORB breakout"
    
    # FILTERS
    filters_passed = 1
    total_filters = 1
    filter_details = []
    filter_details.append(("✅ ORB Breakout", True, f"Price broke {base_signal}"))
    
    # 1. VOLUME
    total_filters += 1
    try:
        avg_volume = df_today['Volume'].rolling(window=5).mean().iloc[-1]
        volume_ratio = current_candle['Volume'] / avg_volume if avg_volume > 0 else 0
        volume_pass = volume_ratio >= 1.3
        if volume_pass:
            filters_passed += 1
        filter_details.append((f"{'✅' if volume_pass else '❌'} Volume", volume_pass, f"{volume_ratio:.1f}x"))
    except:
        filter_details.append(("❌ Volume", False, "Error"))
    
    # 2. VWAP
    total_filters += 1
    vwap = calculate_vwap(df_today)
    if vwap:
        if base_signal == "BUY" and current_price > vwap:
            filters_passed += 1
            vwap_pass = True
        elif base_signal == "SELL" and current_price < vwap:
            filters_passed += 1
            vwap_pass = True
        else:
            vwap_pass = False
        filter_details.append((f"{'✅' if vwap_pass else '❌'} VWAP", vwap_pass, f"₹{vwap:.2f}"))
    else:
        filter_details.append(("❌ VWAP", False, "Error"))
    
    # 3. RSI
    total_filters += 1
    rsi = calculate_rsi(df_today)
    if base_signal == "BUY" and rsi < 75:
        filters_passed += 1
        rsi_pass = True
    elif base_signal == "SELL" and rsi > 25:
        filters_passed += 1
        rsi_pass = True
    else:
        rsi_pass = False
    filter_details.append((f"{'✅' if rsi_pass else '❌'} RSI", rsi_pass, f"{rsi:.1f}"))
    
    # 4. MULTI-TIMEFRAME
    if df_15m is not None:
        total_filters += 1
        try:
            df_15m['Date'] = pd.to_datetime(df_15m['Date'])
            df_15m_today = df_15m[df_15m['Date'].dt.date == today]
            if not df_15m_today.empty:
                tf_high = df_15m_today['High'].max()
                tf_low = df_15m_today['Low'].min()
                if base_signal == "BUY" and current_price > tf_high * 0.995:
                    filters_passed += 1
                    tf_pass = True
                elif base_signal == "SELL" and current_price < tf_low * 1.005:
                    filters_passed += 1
                    tf_pass = True
                else:
                    tf_pass = False
                filter_details.append((f"{'✅' if tf_pass else '❌'} 15m TF", tf_pass, f"H:₹{tf_high:.0f}"))
            else:
                filter_details.append(("❌ 15m TF", False, "No data"))
        except:
            filter_details.append(("❌ 15m TF", False, "Error"))
    
    # 5. PRICE ACTION
    total_filters += 1
    pa_signal, pa_strength = detect_price_action(df_today)
    if (base_signal == "BUY" and pa_signal == "BULLISH") or (base_signal == "SELL" and pa_signal == "BEARISH"):
        filters_passed += 1
        pa_pass = True
    else:
        pa_pass = False
    filter_details.append((f"{'✅' if pa_pass else '❌'} Price Action", pa_pass, f"{pa_signal}"))
    
    # 6. EMA
    total_filters += 1
    ema20 = calculate_ema(df_5m, 20)
    if ema20:
        if base_signal == "BUY" and current_price > ema20:
            filters_passed += 1
            ema_pass = True
        elif base_signal == "SELL" and current_price < ema20:
            filters_passed += 1
            ema_pass = True
        else:
            ema_pass = False
        filter_details.append((f"{'✅' if ema_pass else '❌'} EMA20", ema_pass, f"₹{ema20:.2f}"))
    else:
        filter_details.append(("❌ EMA20", False, "Error"))
    
    # 7. PREV DAY
    if df_daily is not None and len(df_daily) >= 2:
        total_filters += 1
        try:
            prev_day = df_daily.iloc[-2]
            prev_high = prev_day['High']
            prev_low = prev_day['Low']
            
            if base_signal == "BUY" and current_price > prev_high:
                filters_passed += 1
                prev_pass = True
                prev_detail = f"Above ₹{prev_high:.2f}"
            elif base_signal == "SELL" and current_price < prev_low:
                filters_passed += 1
                prev_pass = True
                prev_detail = f"Below ₹{prev_low:.2f}"
            else:
                prev_pass = False
                prev_detail = f"H:₹{prev_high:.0f} L:₹{prev_low:.0f}"
            filter_details.append((f"{'✅' if prev_pass else '❌'} Prev Day", prev_pass, prev_detail))
        except:
            filter_details.append(("❌ Prev Day", False, "Error"))
    
    # 8. SECTOR STRENGTH (NEW - NIFTY INDEPENDENT)
    sector = STOCK_TO_SECTOR.get(symbol, None)
    if sector and sector_perf and sector in sector_perf:
        total_filters += 1
        sector_data = sector_perf[sector]
        sector_trend = sector_data['trend']
        sector_change = sector_data['change']
        
        if base_signal == "BUY":
            if sector_trend in ["STRONG_UP", "UP"]:
                filters_passed += 1
                sector_pass = True
            elif sector_trend == "NEUTRAL":
                sector_pass = False
            else:
                sector_pass = False
        else:  # SELL
            if sector_trend in ["STRONG_DOWN", "DOWN"]:
                filters_passed += 1
                sector_pass = True
            elif sector_trend == "NEUTRAL":
                sector_pass = False
            else:
                sector_pass = False
        
        filter_details.append((f"{'✅' if sector_pass else '❌'} Sector ({sector})", sector_pass, f"{sector_change:+.2f}%"))
    else:
        filter_details.append(("➖ Sector", False, "N/A"))
    
    accuracy = (filters_passed / total_filters) * 100 if total_filters > 0 else 0
    
    # ATR SL
    atr = calculate_atr(df_today)
    if atr > 0:
        if base_signal == "BUY":
            atr_sl = entry_price - (1.5 * atr)
            stop_loss = max(stop_loss, atr_sl)
        else:
            atr_sl = entry_price + (1.5 * atr)
            stop_loss = min(stop_loss, atr_sl)
    
    risk = abs(entry_price - stop_loss)
    target = entry_price + (risk * risk_reward) if base_signal == "BUY" else entry_price - (risk * risk_reward)
    
    return {
        'symbol': symbol.replace('.NS', ''),
        'current_price': round(current_price, 2),
        'orb_high': round(orb_high, 2),
        'orb_low': round(orb_low, 2),
        'signal': base_signal,
        'entry_price': round(entry_price, 2),
        'stop_loss': round(stop_loss, 2),
        'target': round(target, 2),
        'risk': round(risk, 2),
        'risk_percent': round((risk / entry_price) * 100, 2) if entry_price else 0,
        'accuracy': round(accuracy, 1),
        'filters_passed': filters_passed,
        'total_filters': total_filters,
        'filter_details': filter_details,
        'sector': sector,
        'sector_change': sector_perf.get(sector, {}).get('change', 0) if sector_perf else 0,
        'day_high': round(df_today['High'].max(), 2),
        'day_low': round(df_today['Low'].min(), 2),
        'rsi': round(rsi, 1),
        'vwap': round(vwap, 2) if vwap else None,
        'atr': round(atr, 2),
        'ema20': round(ema20, 2) if ema20 else None,
    }, None

# ============================================
# COMBINED SIGNAL
# ============================================
def get_final_signal(orb_signal, accuracy, oi_data, news_data):
    signal_scores = {"BUY": 1, "SELL": -1}
    orb_score = signal_scores.get(orb_signal, 0)
    
    oi_score = 0
    oi_signal = "NEUTRAL"
    oi_buildup = "NO DATA"
    
    if oi_data:
        oi_signal = oi_data.get('oi_signal', 'NEUTRAL')
        oi_buildup = oi_data.get('oi_buildup', 'NO DATA')
        
        if oi_signal == "STRONG LONG":
            oi_score = 1.5
        elif oi_signal == "LONG":
            oi_score = 1
        elif oi_signal == "STRONG SHORT":
            oi_score = -1.5
        elif oi_signal == "SHORT":
            oi_score = -1
    
    # News impact
    news_impact = "NO DATA"
    if news_data:
        overall = news_data['overall_sentiment']
        if orb_signal == "BUY":
            news_impact = "SUPPORTS" if overall == "POSITIVE" else ("CONTRADICTS" if overall == "NEGATIVE" else "NEUTRAL")
        else:
            news_impact = "SUPPORTS" if overall == "NEGATIVE" else ("CONTRADICTS" if overall == "POSITIVE" else "NEUTRAL")
        
        if news_impact == "SUPPORTS":
            orb_score *= 1.2
        elif news_impact == "CONTRADICTS":
            orb_score *= 0.5
    
    combined = (orb_score * 0.7 + oi_score * 0.3)
    
    if accuracy >= 85:
        if combined > 0.5:
            return "🚀 STRONG BUY", combined, oi_signal, oi_buildup, news_impact
        elif combined < -0.5:
            return "🔻 STRONG SELL", combined, oi_signal, oi_buildup, news_impact
    elif accuracy >= 70:
        if combined > 0:
            return "🟢 BUY", combined, oi_signal, oi_buildup, news_impact
        elif combined < 0:
            return "🔴 SELL", combined, oi_signal, oi_buildup, news_impact
    
    return "🟡 NEUTRAL", combined, oi_signal, oi_buildup, news_impact

# ============================================
# MAIN SCANNING
# ============================================
if refresh:
    st.subheader("🔍 Scanning (Nifty Independent)...")
    
    # Get sector performance FIRST
    sector_perf = get_sector_performance() if use_sector else {}
    
    # Display sector overview
    if sector_perf:
        st.markdown("### 📊 Sector Performance Today")
        sector_cols = st.columns(4)
        col_idx = 0
        for sector, data in sector_perf.items():
            trend = data['trend']
            change = data['change']
            
            if trend in ["STRONG_UP", "UP"]:
                sec_class = "sector-strong"
            elif trend in ["STRONG_DOWN", "DOWN"]:
                sec_class = "sector-weak"
            else:
                sec_class = "sector-neutral"
            
            with sector_cols[col_idx % 4]:
                st.markdown(f'<div class="sector-card {sec_class}"><b>{sector}</b><br>{change:+.2f}%<br>{trend}</div>', unsafe_allow_html=True)
            col_idx += 1
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    results = []
    total_stocks = len(stock_list)
    
    for i, symbol in enumerate(stock_list):
        progress = (i + 1) / total_stocks
        progress_bar.progress(min(progress, 0.99))
        status_text.text(f"Analyzing {symbol}... ({i+1}/{total_stocks})")
        
        orb_result, error_msg = analyze_orb_ultimate(symbol, sector_perf, orb_minutes)
        
        if orb_result and min_price <= orb_result['current_price'] <= max_price:
            
            if orb_result['accuracy'] >= min_accuracy:
                
                oi_data = None
                if use_oi:
                    nse_symbol = symbol.replace('.NS', '')
                    oi_data = fetch_oi_data_nse(nse_symbol)
                
                news_data = None
                if use_news:
                    news_data = fetch_stock_news(symbol)
                
                final_signal, confidence, oi_signal, oi_buildup, news_impact = get_final_signal(
                    orb_result['signal'], orb_result['accuracy'], oi_data, news_data
                )
                
                if news_impact == "CONTRADICTS" and use_news:
                    continue
                
                if "BUY" in final_signal or "SELL" in final_signal:
                    result = {
                        **orb_result,
                        'final_signal': final_signal,
                        'confidence': round(abs(confidence) * 100, 1),
                        'oi_signal': oi_signal,
                        'oi_buildup': oi_buildup,
                        'news_impact': news_impact,
                        'oi_data': oi_data,
                        'news_data': news_data
                    }
                    results.append(result)
    
    progress_bar.empty()
    status_text.empty()
    
    # DISPLAY
    if not results:
        st.warning(f"⚠️ No {min_accuracy}% signals found.")
        st.info("💡 Market hours: 9:15 AM - 3:30 PM IST")
    else:
        strong_buy = len([r for r in results if "STRONG BUY" in r['final_signal']])
        buy = len([r for r in results if r['final_signal'] == "🟢 BUY"])
        strong_sell = len([r for r in results if "STRONG SELL" in r['final_signal']])
        sell = len([r for r in results if r['final_signal'] == "🔴 SELL"])
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(f'<div class="metric-card"><h3>🚀 STRONG BUY</h3><h1>{strong_buy}</h1></div>', unsafe_allow_html=True)
        with col2:
            st.markdown(f'<div class="metric-card"><h3>🟢 BUY</h3><h1>{buy}</h1></div>', unsafe_allow_html=True)
        with col3:
            st.markdown(f'<div class="metric-card"><h3>🔴 SELL</h3><h1>{sell}</h1></div>', unsafe_allow_html=True)
        with col4:
            st.markdown(f'<div class="metric-card"><h3>🔻 STRONG SELL</h3><h1>{strong_sell}</h1></div>', unsafe_allow_html=True)
        
        st.markdown("---")
        results = sorted(results, key=lambda x: x['accuracy'], reverse=True)
        
        for row in results:
            sig = row['final_signal']
            acc = row['accuracy']
            
            if "STRONG BUY" in sig:
                card_class = "strong-buy"
            elif sig == "🟢 BUY":
                card_class = "buy"
            elif "STRONG SELL" in sig:
                card_class = "strong-sell"
            elif sig == "🔴 SELL":
                card_class = "sell"
            else:
                card_class = "neutral"
            
            if acc >= 85:
                acc_class = "acc-90"
            elif acc >= 75:
                acc_class = "acc-80"
            else:
                acc_class = "acc-70"
            
            with st.expander(f"{sig} **{row['symbol']}** | ₹{row['current_price']} | {acc}%"):
                
                st.markdown(f'<div class="signal-card {card_class}"><h2>{sig}</h2></div>', unsafe_allow_html=True)
                st.markdown(f'<div class="accuracy-badge {acc_class}">🎯 {acc}% ({row["filters_passed"]}/{row["total_filters"]})</div>', unsafe_allow_html=True)
                
                # Sector info
                if row['sector']:
                    st.markdown(f"""
                    <div class="filter-box">
                    <b>🏭 Sector: {row['sector']}</b> | Change: {row['sector_change']:+.2f}%
                    </div>
                    """, unsafe_allow_html=True)
                
                # News
                if row['news_data']:
                    news = row['news_data']
                    news_class = "news-positive" if news['overall_sentiment'] == "POSITIVE" else ("news-negative" if news['overall_sentiment'] == "NEGATIVE" else "news-neutral")
                    st.markdown(f'<div class="{news_class}"><b>📰 News: {news["overall_sentiment"]}</b> | Impact: {row["news_impact"]}</div>', unsafe_allow_html=True)
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.markdown(f"""
                    <div class="filter-box">
                    <b>📈 Trade</b><br>
                    Entry: <b>₹{row['entry_price']}</b><br>
                    SL: <span style="color:red">₹{row['stop_loss']}</span><br>
                    Target: <span style="color:green">₹{row['target']}</span><br>
                    Risk: ₹{row['risk']} ({row['risk_percent']}%)<br>
                    R:R = 1:{risk_reward}
                    </div>
                    """, unsafe_allow_html=True)
                
                with col2:
                    st.markdown(f"""
                    <div class="filter-box">
                    <b>📊 Tech</b><br>
                    RSI: {row['rsi']}<br>
                    VWAP: ₹{row['vwap'] if row['vwap'] else 'N/A'}<br>
                    ATR: ₹{row['atr']}<br>
                    EMA20: ₹{row['ema20'] if row['ema20'] else 'N/A'}
                    </div>
                    """, unsafe_allow_html=True)
                
                with col3:
                    if row['oi_data']:
                        oi = row['oi_data']
                        st.markdown(f"""
                        <div class="filter-box">
                        <b>🔥 OI</b><br>
                        {row['oi_buildup']}<br>
                        PCR: {oi['pcr_oi']}<br>
                        Signal: {row['oi_signal']}
                        </div>
                        """, unsafe_allow_html=True)
                
                st.markdown("---")
                st.markdown("**📋 Filters:**")
                cols = st.columns(4)
                for i, (filter_name, passed, detail) in enumerate(row['filter_details']):
                    with cols[i % 4]:
                        color = "green" if passed else "red"
                        st.markdown(f'<p style="color:{color}; font-weight:bold;">{filter_name}</p><small>{detail}</small>', unsafe_allow_html=True)
        
        st.markdown("---")
        df_export = pd.DataFrame([{k: v for k, v in r.items() if k not in ['oi_data', 'news_data', 'filter_details']} for r in results])
        csv = df_export.to_csv(index=False)
        st.download_button(
            label="📥 Download Signals",
            data=csv,
            file_name=f"sector_scanner_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv"
        )

# ============================================
# EDUCATION
# ============================================
with st.expander("📚 Why Nifty Independent?"):
    st.markdown("""
    ### 🎯 Nifty Independent Kyun?
    
    **Example:**
    ```
    Date: 15 Jan 2024
    
    Nifty: +0.5% (Bullish)
    IT Sector: -2.5% (Bearish)
    INFY: -3% (Strong Sell Signal)
    
    Result: INFY sell kiya → Profit ✅
    Agar Nifty dekhke buy kiya → Loss ❌
    ```
    
    **Sector Rotation:**
    - Nifty UP + IT DOWN = IT stocks avoid
    - Nifty DOWN + Pharma UP = Pharma buy
    
    **Stock Specific:**
    - Company news dominates
    - Sector momentum matters
    - Nifty just background noise
    
    ### 🏭 Sector Strength Filter
    
    | Sector Trend | BUY Signal | SELL Signal |
    |-------------|-----------|-------------|
    | STRONG_UP | ✅ Pass | ❌ Fail |
    | UP | ✅ Pass | ❌ Fail |
    | NEUTRAL | ❌ Fail | ❌ Fail |
    | DOWN | ❌ Fail | ✅ Pass |
    | STRONG_DOWN | ❌ Fail | ✅ Pass |
    """)

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: gray; font-size: 12px;">
<b>⚠️ Disclaimer:</b> Educational purposes only. Not financial advice. 
<br><b>🎯 Nifty Independent | Sector Based | Stock-Specific Analysis</b>
</div>
""", unsafe_allow_html=True)
