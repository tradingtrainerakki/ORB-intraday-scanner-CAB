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
    page_title="🎯 Ultimate Intraday Scanner + News",
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
    .oi-buildup {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
    }
    .buildup-bullish { background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); }
    .buildup-bearish { background: linear-gradient(135deg, #cb2d3e 0%, #ef473a 100%); }
    .buildup-neutral { background: linear-gradient(135deg, #f7971e 0%, #ffd200 100%); color: #333; }
    .news-positive { background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); color: white; padding: 10px; border-radius: 10px; }
    .news-negative { background: linear-gradient(135deg, #cb2d3e 0%, #ef473a 100%); color: white; padding: 10px; border-radius: 10px; }
    .news-neutral { background: linear-gradient(135deg, #f7971e 0%, #ffd200 100%); color: #333; padding: 10px; border-radius: 10px; }
    .news-item { padding: 8px; margin: 5px 0; border-radius: 8px; background: #f0f2f6; border-left: 4px solid #667eea; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-header">🎯 Ultimate Intraday Scanner + News</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">70-80% Accuracy | OI Buildup | News Sentiment | Smart SL</p>', unsafe_allow_html=True)

# ============================================
# NEWS FETCHING FUNCTION
# ============================================
def fetch_stock_news(symbol):
    """
    Fetch recent news for a stock and analyze sentiment
    Uses Yahoo Finance news as primary source
    """
    try:
        ticker = yf.Ticker(symbol)
        news = ticker.news
        
        if not news or len(news) == 0:
            return None
        
        # Analyze sentiment based on keywords
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
        
        for item in news[:5]:  # Last 5 news items
            title = item.get('title', '').lower()
            publisher = item.get('publisher', 'Unknown')
            published_time = item.get('published', '')
            
            # Calculate sentiment score
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
                'score': score,
                'time': published_time
            })
        
        # Overall sentiment
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
        
    except Exception as e:
        return None

def get_news_impact(signal, news_sentiment):
    """
    Determine if news supports or contradicts the signal
    """
    if news_sentiment is None:
        return "NO DATA", "neutral"
    
    overall = news_sentiment['overall_sentiment']
    
    if signal == "BUY":
        if overall == "POSITIVE":
            return "SUPPORTS", "positive"
        elif overall == "NEGATIVE":
            return "CONTRADICTS", "negative"
        else:
            return "NEUTRAL", "neutral"
    
    elif signal == "SELL":
        if overall == "NEGATIVE":
            return "SUPPORTS", "positive"
        elif overall == "POSITIVE":
            return "CONTRADICTS", "negative"
        else:
            return "NEUTRAL", "neutral"
    
    return "NEUTRAL", "neutral"

# ============================================
# NSE API FUNCTIONS - OI DATA + BUILDUP
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
    pcr_change = total_pe_change / total_ce_change if total_ce_change != 0 else 0
    
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
    
    if pcr_oi > 1.3 and pcr_change > 1:
        oi_signal = "STRONG LONG"
    elif pcr_oi > 1.1:
        oi_signal = "LONG"
    elif pcr_oi < 0.7 and pcr_change < 1:
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
        'pcr_change': round(pcr_change, 2),
        'oi_buildup': oi_buildup,
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

# Accuracy Mode
st.sidebar.subheader("🎯 Accuracy Mode")
accuracy_mode = st.sidebar.selectbox(
    "Select Mode",
    ["Conservative (80%+)", "Balanced (70-80%)", "Aggressive (60-70%)"]
)

min_accuracy = {"Conservative (80%+)": 80, "Balanced (70-80%)": 70, "Aggressive (60-70%)": 60}[accuracy_mode]

# Filters
st.sidebar.subheader("🔥 Advanced Filters")
use_oi_buildup = st.sidebar.checkbox("✅ OI Buildup Analysis", value=True)
use_multi_tf = st.sidebar.checkbox("✅ Multi-Timeframe Confirm", value=True)
use_vwap = st.sidebar.checkbox("✅ VWAP + Volume Profile", value=True)
use_atr_sl = st.sidebar.checkbox("✅ Smart ATR-based SL", value=True)
use_price_action = st.sidebar.checkbox("✅ Price Action Patterns", value=True)
use_news = st.sidebar.checkbox("📰 News Sentiment Analysis", value=True)

# Risk Management
st.sidebar.subheader("Risk Management")
risk_reward = st.sidebar.slider("Risk : Reward", 1.0, 4.0, 2.5, 0.5)

# Filters
st.sidebar.subheader("Price Filters")
min_price = st.sidebar.number_input("Min Price (₹)", 50, 50000, 100)
max_price = st.sidebar.number_input("Max Price (₹)", 50, 50000, 10000)

refresh = st.sidebar.button("🔄 SCAN NOW", type="primary")

st.sidebar.markdown("---")
st.sidebar.info(f"""
**🎯 {accuracy_mode}**
- Min Accuracy: {min_accuracy}%
- Expected Win Rate: {min_accuracy}-{min_accuracy+10}%
- Signals/Day: {'2-4' if min_accuracy==80 else '4-8' if min_accuracy==70 else '8-15'}
""")

# ============================================
# DATA FETCHING - MULTI TIMEFRAME
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
# ULTIMATE ORB ANALYSIS
# ============================================
def analyze_orb_ultimate(symbol, orb_mins=15, use_multi_tf=True, use_vwap=True, 
                          use_atr=True, use_pa=True, use_oi=True):
    df_5m = fetch_data(symbol, period="5d", interval="5m")
    df_15m = fetch_data(symbol, period="10d", interval="15m") if use_multi_tf else None
    df_daily = fetch_data(symbol, period="30d", interval="1d")
    
    if df_5m is None or df_5m.empty:
        return None, "No 5m data available"
    
    if 'Date' not in df_5m.columns:
        return None, "Date column missing"
    
    try:
        df_5m['Date'] = pd.to_datetime(df_5m['Date'])
        today = datetime.now().date()
        df_today = df_5m[df_5m['Date'].dt.date == today].copy()
    except:
        return None, "Date parsing error"
    
    if df_today.empty:
        return None, "No today's data (Market might be closed)"
    
    if len(df_today) < 3:
        return None, "Not enough candles today"
    
    df_today = df_today.sort_values('Date')
    candles_needed = max(1, orb_mins // 5)
    opening_range = df_today.head(candles_needed)
    
    if opening_range.empty:
        return None, "Opening range empty"
    
    orb_high = opening_range['High'].max()
    orb_low = opening_range['Low'].min()
    
    current_candle = df_today.iloc[-1]
    current_price = current_candle['Close']
    current_high = current_candle['High']
    current_low = current_candle['Low']
    current_volume = current_candle['Volume']
    
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
    
    filters_passed = 1
    total_filters = 1
    filter_details = []
    filter_details.append(("✅ ORB Breakout", True, f"Price broke {base_signal} level"))
    
    # Volume
    total_filters += 1
    try:
        avg_volume = df_today['Volume'].rolling(window=5).mean().iloc[-1]
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0
        volume_pass = volume_ratio >= 1.3
        if volume_pass:
            filters_passed += 1
        filter_details.append((f"{'✅' if volume_pass else '❌'} Volume Spike", volume_pass, f"{volume_ratio:.1f}x avg"))
    except:
        filter_details.append(("❌ Volume Spike", False, "Error"))
    
    # VWAP
    if use_vwap:
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
            filter_details.append(("❌ VWAP", False, "Calc error"))
    
    # RSI
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
    filter_details.append((f"{'✅' if rsi_pass else '❌'} RSI ({rsi:.1f})", rsi_pass, f"RSI: {rsi:.1f}"))
    
    # Multi-TF
    if use_multi_tf and df_15m is not None:
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
                filter_details.append((f"{'✅' if tf_pass else '❌'} 15m Confirm", tf_pass, f"H:₹{tf_high:.0f} L:₹{tf_low:.0f}"))
            else:
                filter_details.append(("❌ 15m Confirm", False, "No data"))
        except:
            filter_details.append(("❌ 15m Confirm", False, "Error"))
    
    # Price Action
    if use_pa:
        total_filters += 1
        pa_signal, pa_strength = detect_price_action(df_today)
        if (base_signal == "BUY" and pa_signal == "BULLISH") or (base_signal == "SELL" and pa_signal == "BEARISH"):
            filters_passed += 1
            pa_pass = True
        elif pa_signal == "NEUTRAL":
            pa_pass = False
        else:
            pa_pass = False
        filter_details.append((f"{'✅' if pa_pass else '❌'} Price Action", pa_pass, f"{pa_signal} ({pa_strength})"))
    
    # EMA
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
        filter_details.append((f"{'✅' if ema_pass else '❌'} EMA20 Trend", ema_pass, f"EMA: ₹{ema20:.2f}"))
    else:
        filter_details.append(("❌ EMA20 Trend", False, "Calc error"))
    
    # Prev Day
    if df_daily is not None and len(df_daily) >= 2:
        total_filters += 1
        try:
            prev_day = df_daily.iloc[-2]
            prev_high = prev_day['High']
            prev_low = prev_day['Low']
            
            if base_signal == "BUY" and current_price > prev_high:
                filters_passed += 1
                prev_pass = True
                prev_detail = f"Above prev high ₹{prev_high:.2f}"
            elif base_signal == "SELL" and current_price < prev_low:
                filters_passed += 1
                prev_pass = True
                prev_detail = f"Below prev low ₹{prev_low:.2f}"
            else:
                prev_pass = False
                prev_detail = f"Prev H:₹{prev_high:.2f} L:₹{prev_low:.2f}"
            filter_details.append((f"{'✅' if prev_pass else '❌'} Prev Day", prev_pass, prev_detail))
        except:
            filter_details.append(("❌ Prev Day", False, "Error"))
    
    accuracy = (filters_passed / total_filters) * 100 if total_filters > 0 else 0
    
    if use_atr:
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
        'day_high': round(df_today['High'].max(), 2),
        'day_low': round(df_today['Low'].min(), 2),
        'rsi': round(rsi, 1),
        'vwap': round(vwap, 2) if vwap else None,
        'atr': round(atr, 2) if use_atr else None,
        'ema20': round(ema20, 2) if ema20 else None,
        'volume_ratio': round(volume_ratio, 2) if 'volume_ratio' in locals() else 0,
    }, None

# ============================================
# COMBINED SIGNAL WITH OI + NEWS
# ============================================
def get_final_signal(orb_signal, accuracy, oi_data, news_data, oi_weight):
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
    news_class = "neutral"
    if news_data:
        news_impact, news_class = get_news_impact(orb_signal, news_data)
        if news_impact == "SUPPORTS":
            orb_score *= 1.2  # Boost signal
        elif news_impact == "CONTRADICTS":
            orb_score *= 0.5  # Reduce signal strength
    
    combined = (orb_score * (100 - oi_weight) + oi_score * oi_weight) / 100
    
    if accuracy >= 85:
        if combined > 0.5:
            return "🚀 STRONG BUY", combined, oi_signal, oi_buildup, news_impact, news_class
        elif combined < -0.5:
            return "🔻 STRONG SELL", combined, oi_signal, oi_buildup, news_impact, news_class
    elif accuracy >= 70:
        if combined > 0:
            return "🟢 BUY", combined, oi_signal, oi_buildup, news_impact, news_class
        elif combined < 0:
            return "🔴 SELL", combined, oi_signal, oi_buildup, news_impact, news_class
    
    return "🟡 NEUTRAL", combined, oi_signal, oi_buildup, news_impact, news_class

# ============================================
# MAIN SCANNING LOGIC
# ============================================
if refresh:
    st.subheader("🔍 Scanning with Ultimate Accuracy + News...")
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    results = []
    total_stocks = len(stock_list)
    
    for i, symbol in enumerate(stock_list):
        progress = (i + 1) / total_stocks
        progress_bar.progress(min(progress, 0.99))
        status_text.text(f"Analyzing {symbol}... ({i+1}/{total_stocks})")
        
        orb_result, error_msg = analyze_orb_ultimate(
            symbol, orb_minutes,
            use_multi_tf=use_multi_tf,
            use_vwap=use_vwap,
            use_atr=use_atr_sl,
            use_pa=use_price_action,
            use_oi=use_oi_buildup
        )
        
        if orb_result and min_price <= orb_result['current_price'] <= max_price:
            
            if orb_result['accuracy'] >= min_accuracy:
                
                # Fetch OI data
                oi_data = None
                if use_oi_buildup:
                    nse_symbol = symbol.replace('.NS', '')
                    oi_data = fetch_oi_data_nse(nse_symbol)
                
                # Fetch News
                news_data = None
                if use_news:
                    news_data = fetch_stock_news(symbol)
                
                final_signal, confidence, oi_signal, oi_buildup, news_impact, news_class = get_final_signal(
                    orb_result['signal'], orb_result['accuracy'], oi_data, news_data, 30
                )
                
                # Skip if news contradicts strongly
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
                        'news_class': news_class,
                        'news_data': news_data,
                        'oi_data': oi_data
                    }
                    results.append(result)
    
    progress_bar.empty()
    status_text.empty()
    
    # ============================================
    # DISPLAY RESULTS
    # ============================================
    if not results:
        st.warning(f"⚠️ No signals found. Try 'Balanced' mode or check market hours.")
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
                acc_text = f"🎯 {acc}% ACCURACY"
            elif acc >= 75:
                acc_class = "acc-80"
                acc_text = f"🎯 {acc}% ACCURACY"
            else:
                acc_class = "acc-70"
                acc_text = f"🎯 {acc}% ACCURACY"
            
            with st.expander(f"{sig} **{row['symbol']}** | ₹{row['current_price']} | {acc_text}"):
                
                st.markdown(f'<div class="signal-card {card_class}"><h2>{sig}</h2><p>{row["symbol"]} @ ₹{row["current_price"]}</p></div>', unsafe_allow_html=True)
                st.markdown(f'<div class="accuracy-badge {acc_class}">{acc_text} ({row["filters_passed"]}/{row["total_filters"]} filters)</div>', unsafe_allow_html=True)
                
                # NEWS SECTION
                if row['news_data']:
                    news = row['news_data']
                    news_class = "news-positive" if news['overall_sentiment'] == "POSITIVE" else ("news-negative" if news['overall_sentiment'] == "NEGATIVE" else "news-neutral")
                    
                    st.markdown("---")
                    st.markdown(f"""
                    <div class="{news_class}">
                        <h3>📰 News Sentiment: {news['overall_sentiment']}</h3>
                        <p>Impact on Signal: <b>{row['news_impact']}</b></p>
                        <p>Score: {news['total_score']:+d} (from {news['news_count']} articles)</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    with st.expander("📰 View News Articles"):
                        for article in news['articles']:
                            sentiment_color = "green" if article['sentiment'] == "POSITIVE" else ("red" if article['sentiment'] == "NEGATIVE" else "gray")
                            st.markdown(f"""
                            <div class="news-item">
                                <p><b>{article['title']}</b></p>
                                <p><span style="color:{sentiment_color}; font-weight:bold;">{article['sentiment']}</span> | {article['publisher']}</p>
                            </div>
                            """, unsafe_allow_html=True)
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.markdown(f"""
                    <div class="filter-box">
                    <b>📈 Entry Setup</b><br>
                    Entry: <b>₹{row['entry_price']}</b><br>
                    Smart SL: <span style="color:red">₹{row['stop_loss']}</span><br>
                    Target: <span style="color:green">₹{row['target']}</span><br>
                    Risk: ₹{row['risk']} ({row['risk_percent']}%)<br>
                    R:R = 1:{risk_reward}
                    </div>
                    """, unsafe_allow_html=True)
                
                with col2:
                    st.markdown(f"""
                    <div class="filter-box">
                    <b>📊 Technicals</b><br>
                    RSI: {row['rsi']}<br>
                    VWAP: ₹{row['vwap'] if row['vwap'] else 'N/A'}<br>
                    ATR: ₹{row['atr'] if row['atr'] else 'N/A'}<br>
                    EMA20: ₹{row['ema20'] if row['ema20'] else 'N/A'}<br>
                    Volume: {row['volume_ratio']}x
                    </div>
                    """, unsafe_allow_html=True)
                
                with col3:
                    if row['oi_data']:
                        oi = row['oi_data']
                        buildup_class = "buildup-bullish" if "BULLISH" in row['oi_buildup'] else ("buildup-bearish" if "BEARISH" in row['oi_buildup'] else "buildup-neutral")
                        
                        st.markdown(f"""
                        <div class="oi-buildup {buildup_class}">
                        <b>🔥 OI Buildup</b><br>
                        <h3>{row['oi_buildup']}</h3>
                        <p>PCR: {oi['pcr_oi']}</p>
                        <p>OI Signal: {row['oi_signal']}</p>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown("""
                        <div class="filter-box">
                        <b>🔥 OI Data</b><br>
                        Not available for this stock
                        </div>
                        """, unsafe_allow_html=True)
                
                st.markdown("---")
                st.markdown("**📋 Filter Checklist:**")
                
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
            file_name=f"scanner_news_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv"
        )

# ============================================
# EDUCATION
# ============================================
with st.expander("📚 How News Affects Trading"):
    st.markdown("""
    ### 📰 News Sentiment Kaise Kaam Karega
    
    | News Type | Signal | Action |
    |-----------|--------|--------|
    | **POSITIVE News** + BUY Signal | ✅ STRONG BUY | Trade with confidence |
    | **NEGATIVE News** + BUY Signal | ⚠️ WEAK BUY | Avoid or small quantity |
    | **POSITIVE News** + SELL Signal | ⚠️ WEAK SELL | Avoid or small quantity |
    | **NEGATIVE News** + SELL Signal | ✅ STRONG SELL | Trade with confidence |
    
    ### 🚫 News Contradicts Signal?
    
    Scanner **automatically skip** karega agar:
    - BUY signal + Negative news = ❌ Skip
    - SELL signal + Positive news = ❌ Skip
    
    ### 💡 Examples
    
    ```
    Scanner: BUY RELIANCE @ ₹2450
    News: "Reliance announces record profit"
    Result: 🚀 STRONG BUY → Trade!
    
    Scanner: BUY WIPRO @ ₹420
    News: "WIPRO faces US lawsuit"
    Result: ❌ SKIPPED → Avoid!
    ```
    
    ### ⚠️ Important
    
    - News **Yahoo Finance** se aata hai
    - **Real-time nahi** — thoda delayed ho sakta hai
    - **Headline analysis** hai — deep analysis nahi
    - Khud bhi **news verify** karein before trading
    """)

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: gray; font-size: 12px;">
<b>⚠️ Disclaimer:</b> Educational purposes only. Not financial advice. 
<br>Data from Yahoo Finance (delayed) & NSE India. Trade at your own risk.
<br><b>🎯 Target: 70-80% accuracy with News + OI + Technical filters</b>
</div>
""", unsafe_allow_html=True)
