import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
import requests
import json
import os
import hashlib
import tempfile
import pytz
import time
import warnings
warnings.filterwarnings('ignore')

# Try to import nsepython for NSE data
try:
    from nsepython import nse_eq, nsefetch
    NSEPYTHON_AVAILABLE = True
except ImportError:
    NSEPYTHON_AVAILABLE = False

IST = pytz.timezone('Asia/Kolkata')

def get_ist_now():
    return datetime.now(IST)

def get_ist_date():
    return datetime.now(IST).date()

DHAN_SECURITY_IDS = {
    "RELIANCE": "2885", "TCS": "11536", "HDFCBANK": "1333", "ICICIBANK": "4963",
    "INFY": "1594", "HINDUNILVR": "1394", "ITC": "1660", "SBIN": "3045",
    "BHARTIARTL": "10604", "KOTAKBANK": "1922", "LT": "11483", "AXISBANK": "5900",
    "ASIANPAINT": "236", "MARUTI": "10999", "TITAN": "3506", "SUNPHARMA": "3351",
    "BAJFINANCE": "317", "WIPRO": "3787", "ULTRACEMCO": "11532", "NESTLEIND": "17963",
    "POWERGRID": "14977", "NTPC": "11630", "TATASTEEL": "3499", "M&M": "2031",
    "HCLTECH": "1851", "TECHM": "13538", "INDUSINDBK": "5258", "GRASIM": "1232",
    "ADANIENT": "25", "CIPLA": "694", "SBILIFE": "21808", "BAJAJFINSV": "16675",
    "BRITANNIA": "1406", "APOLLOHOSP": "157", "ONGC": "2475", "EICHERMOT": "910",
    "TATAMOTORS": "3456", "DIVISLAB": "10568", "HDFCLIFE": "467", "COALINDIA": "20374",
    "JSWSTEEL": "11723", "HEROMOTOCO": "1348", "BPCL": "526", "DRREDDY": "881",
    "ADANIPORTS": "15083", "HINDALCO": "1363", "UPL": "11287", "SHREECEM": "3103",
    "BAJAJ-AUTO": "16669", "TATACONSUM": "3432",
}

DHAN_BASE_URL = "https://api.dhan.co/v2"

def get_dhan_headers(access_token):
    return {
        'Content-Type': 'application/json',
        'access-token': access_token
    }

def fetch_dhan_intraday_data(security_id, access_token, interval="5", from_date=None, to_date=None):
    try:
        if from_date is None:
            from_date = (get_ist_now() - timedelta(days=5)).strftime('%Y-%m-%d %H:%M:%S')
        if to_date is None:
            to_date = get_ist_now().strftime('%Y-%m-%d %H:%M:%S')
        url = f"{DHAN_BASE_URL}/charts/intraday"
        payload = {
            "securityId": security_id,
            "exchangeSegment": "NSE_EQ",
            "instrument": "EQUITY",
            "interval": interval,
            "fromDate": from_date,
            "toDate": to_date
        }
        response = requests.post(url, json=payload, headers=get_dhan_headers(access_token), timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data and 'open' in data:
                df = pd.DataFrame({
                    'Open': data['open'],
                    'High': data['high'],
                    'Low': data['low'],
                    'Close': data['close'],
                    'Volume': data['volume'],
                    'timestamp': data['timestamp']
                })
                df['Date'] = pd.to_datetime(df['timestamp'], unit='s').dt.tz_localize('UTC').dt.tz_convert('Asia/Kolkata')
                df = df.drop('timestamp', axis=1)
                return df
        return None
    except Exception as e:
        st.error(f"Dhan API Error: {e}")
        return None

def fetch_dhan_daily_data(security_id, access_token, from_date=None, to_date=None):
    try:
        if from_date is None:
            from_date = (get_ist_now() - timedelta(days=30)).strftime('%Y-%m-%d')
        if to_date is None:
            to_date = get_ist_now().strftime('%Y-%m-%d')
        url = f"{DHAN_BASE_URL}/charts/historical"
        payload = {
            "securityId": security_id,
            "exchangeSegment": "NSE_EQ",
            "instrument": "EQUITY",
            "fromDate": from_date,
            "toDate": to_date
        }
        response = requests.post(url, json=payload, headers=get_dhan_headers(access_token), timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data and 'open' in data:
                df = pd.DataFrame({
                    'Open': data['open'],
                    'High': data['high'],
                    'Low': data['low'],
                    'Close': data['close'],
                    'Volume': data['volume'],
                    'timestamp': data['timestamp']
                })
                df['Date'] = pd.to_datetime(df['timestamp'], unit='s').dt.tz_localize('UTC').dt.tz_convert('Asia/Kolkata')
                df = df.drop('timestamp', axis=1)
                return df
        return None
    except Exception as e:
        st.error(f"Dhan API Error: {e}")
        return None

def get_symbol_from_ns(symbol_ns):
    return symbol_ns.replace('.NS', '')

def get_dhan_security_id(symbol_ns):
    symbol = get_symbol_from_ns(symbol_ns)
    return DHAN_SECURITY_IDS.get(symbol, None)

TEMP_DIR = tempfile.gettempdir()
DATA_FILE = os.path.join(TEMP_DIR, "scanner_data.json")

DEFAULT_USERNAME = "Akki"
DEFAULT_PASSWORD = "Ca@1809"

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'username' not in st.session_state:
    st.session_state.username = ""

def login(username, password):
    valid_username = DEFAULT_USERNAME
    valid_password_hash = hash_password(DEFAULT_PASSWORD)
    if username == valid_username and hash_password(password) == valid_password_hash:
        st.session_state.authenticated = True
        st.session_state.username = username
        return True
    return False

def logout():
    st.session_state.authenticated = False
    st.session_state.username = ""

if 'saved_results' not in st.session_state:
    st.session_state.saved_results = None
    st.session_state.saved_sector_perf = None
    st.session_state.saved_timestamp = None
    st.session_state.saved_stock_list = None
    st.session_state.saved_settings = None
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
                st.session_state.saved_results = data.get('results')
                st.session_state.saved_sector_perf = data.get('sector_perf')
                st.session_state.saved_timestamp = data.get('timestamp')
                st.session_state.saved_stock_list = data.get('stock_list')
                st.session_state.saved_settings = data.get('settings')
        except:
            pass

def save_scan_data(results, sector_perf, stock_list, settings):
    try:
        serializable_results = []
        for r in results:
            sr = {k: v for k, v in r.items() if k not in ['oi_data', 'news_data', 'filter_details']}
            if 'filter_details' in r:
                sr['filter_details'] = [[name, passed, detail] for name, passed, detail in r['filter_details']]
            serializable_results.append(sr)
        data = {
            'results': serializable_results,
            'sector_perf': sector_perf,
            'timestamp': get_ist_now().strftime('%Y-%m-%d %H:%M:%S'),
            'stock_list': stock_list,
            'settings': settings
        }
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, default=str)
        st.session_state.saved_results = serializable_results
        st.session_state.saved_sector_perf = sector_perf
        st.session_state.saved_timestamp = data['timestamp']
        st.session_state.saved_stock_list = stock_list
        st.session_state.saved_settings = settings
        return True
    except Exception as e:
        st.error(f"Error saving data: {e}")
        return False

def load_scan_data():
    if st.session_state.saved_results:
        return {
            'results': st.session_state.saved_results,
            'sector_perf': st.session_state.saved_sector_perf,
            'timestamp': st.session_state.saved_timestamp,
            'stock_list': st.session_state.saved_stock_list,
            'settings': st.session_state.saved_settings
        }
    return None

def clear_saved_data():
    st.session_state.saved_results = None
    st.session_state.saved_sector_perf = None
    st.session_state.saved_timestamp = None
    st.session_state.saved_stock_list = None
    st.session_state.saved_settings = None
    if os.path.exists(DATA_FILE):
        try:
            os.remove(DATA_FILE)
        except:
            pass

if not st.session_state.authenticated:
    st.set_page_config(page_title="Scanner Login", page_icon="", layout="centered")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("""
        <div style="text-align: center; padding: 40px 20px;">
            <h1 style="font-size: 50px;"></h1>
            <h2 style="color: #1f77b4;">Independent Sector Scanner</h2>
            <p style="color: #666;">Secure Access Required</p>
        </div>
        """, unsafe_allow_html=True)
        with st.form("login_form"):
            username = st.text_input("Username", placeholder="Enter username")
            password = st.text_input("Password", type="password", placeholder="Enter password")
            submitted = st.form_submit_button("Login", use_container_width=True)
            if submitted:
                if login(username, password):
                    st.success("Login successful! Redirecting...")
                    st.rerun()
                else:
                    st.error("Invalid username or password!")
        st.markdown("""
        <div style="text-align: center; margin-top: 20px; padding: 15px; background: #f0f2f6; border-radius: 10px;">
            <small><b>Default Credentials:</b><br>Username: <code>admin</code> | Password: <code>scanner123</code></small>
        </div>
        """, unsafe_allow_html=True)
    st.stop()

st.set_page_config(page_title="Independent Sector Scanner", page_icon="", layout="wide", initial_sidebar_state="expanded")

with st.sidebar:
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                padding: 15px; border-radius: 10px; color: white; text-align: center; margin-bottom: 20px;">
        <b>Welcome, {st.session_state.username}</b><br>
        <small>{get_ist_now().strftime('%d %b %Y | %H:%M')}</small>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Logout", use_container_width=True):
        logout()
        st.rerun()

st.markdown("""
    <style>
    .main-header { font-size: 40px; font-weight: bold; color: #1f77b4; text-align: center; margin-bottom: 10px; }
    .sub-header { font-size: 18px; color: #666; text-align: center; margin-bottom: 30px; }
    .metric-card { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; border-radius: 15px; color: white; box-shadow: 0 4px 15px rgba(0,0,0,0.2); }
    .signal-card { padding: 20px; border-radius: 15px; margin: 10px 0; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
    .strong-buy { background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); color: white; }
    .buy { background: linear-gradient(135deg, #56ab2f 0%, #a8e063 100%); color: white; }
    .strong-sell { background: linear-gradient(135deg, #cb2d3e 0%, #ef473a 100%); color: white; }
    .sell { background: linear-gradient(135deg, #eb3349 0%, #f45c43 100%); color: white; }
    .neutral { background: linear-gradient(135deg, #f7971e 0%, #ffd200 100%); color: #333; }
    .accuracy-badge { display: inline-block; padding: 8px 20px; border-radius: 25px; font-weight: bold; font-size: 18px; color: white; text-align: center; }
    .acc-90 { background: linear-gradient(135deg, #00b09b 0%, #96c93d 100%); }
    .acc-80 { background: linear-gradient(135deg, #f7971e 0%, #ffd200 100%); color: #333; }
    .acc-70 { background: linear-gradient(135deg, #ff6b6b 0%, #ee5a24 100%); }
    .filter-box { background: #f8f9fa; padding: 15px; border-radius: 10px; border-left: 5px solid #667eea; margin: 5px 0; }
    .sector-card { background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); color: white; padding: 15px; border-radius: 10px; text-align: center; margin: 5px 0; }
    .sector-strong { background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); }
    .sector-weak { background: linear-gradient(135deg, #cb2d3e 0%, #ef473a 100%); }
    .sector-neutral { background: linear-gradient(135deg, #f7971e 0%, #ffd200 100%); color: #333; }
    .news-positive { background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); color: white; padding: 10px; border-radius: 10px; }
    .news-negative { background: linear-gradient(135deg, #cb2d3e 0%, #ef473a 100%); color: white; padding: 10px; border-radius: 10px; }
    .news-neutral { background: linear-gradient(135deg, #f7971e 0%, #ffd200 100%); color: #333; padding: 10px; border-radius: 10px; }
    .persistence-info { background: #e8f4f8; border-left: 4px solid #1f77b4; padding: 12px 15px; border-radius: 8px; margin: 10px 0; }
    </style>
""", unsafe_allow_html=True)

def color_signal(val):
    v = str(val)
    if "STRONG BUY" in v: return "background:#00ff0030;color:#00ff00;font-weight:700;"
    if "BUY" in v: return "background:#00cc0020;color:#00cc00;font-weight:700;"
    if "STRONG SELL" in v: return "background:#ff000030;color:#ff2020;font-weight:700;"
    if "SELL" in v: return "background:#cc000020;color:#ff4060;font-weight:700;"
    if "WAIT" in v: return "background:#ffc70020;color:#ffc700;font-weight:700;"
    return ""

def color_strength(val):
    try:
        v = int(str(val).replace("%",""))
        if v >= 80: return "background:#00ff0025;color:#00ff00;font-weight:700;"
        if v >= 60: return "background:#88ff0015;color:#88ff00;font-weight:700;"
        if v >= 40: return "background:#ffc70020;color:#ffc700;font-weight:700;"
        return "background:#ff406020;color:#ff4060;font-weight:700;"
    except: return ""

def color_ema(val):
    if "BULLISH" in str(val): return 'color:#00ff88;font-weight:700'
    if "BEARISH" in str(val): return 'color:#ff4060;font-weight:700'
    return ''

def color_vwap(val):
    if "ABOVE" in str(val): return 'color:#00ff88'
    if "BELOW" in str(val): return 'color:#ff4060'
    return ''

def color_chg(val):
    try:
        v = str(val).replace('%','').replace('+','').strip()
        if v == '-' or v == '':
            return ''
        num = float(v)
        if num > 0: return 'color:#00ff88;font-weight:700'
        if num < 0: return 'color:#ff4060;font-weight:700'
    except:
        pass
    return ''

def color_oi(val):
    try:
        v = str(val).replace('%','').replace('+','').strip()
        if v == '-' or v == '':
            return ''
        num = float(v)
        if num > 0: return 'color:#00ff88;font-weight:700'
        if num < 0: return 'color:#ff4060;font-weight:700'
    except:
        pass
    return ''

def color_oi_interp(val):
    v = str(val)
    if 'LONG BUILD' in v: return 'background:#00ff8820;color:#00ff88;font-weight:700;'
    if 'SHORT BUILD' in v: return 'background:#ff406020;color:#ff4060;font-weight:700;'
    if 'SHORT COVER' in v: return 'background:#ffc70020;color:#ffc700;font-weight:700;'
    if 'LONG UNWIND' in v: return 'background:#ff820020;color:#ff8200;font-weight:700;'
    return ''

def color_pnl(val):
    try:
        if float(val) > 0: return 'color:#00ff88;font-weight:700'
        if float(val) < 0: return 'color:#ff4060;font-weight:700'
    except: pass
    return ''

def color_status(val):
    if val == "HIT TARGET": return 'color:#00ff88;font-weight:700'
    if val == "HIT SL": return 'color:#ff4060;font-weight:700'
    if val == "OPEN": return 'color:#ffc700;font-weight:700'
    return ''

def color_news(val):
    v = str(val)
    if 'NEGATIVE' in v: return 'background:#ff000030;color:#ff2020;font-weight:700;'
    if 'POSITIVE' in v: return 'background:#00ff0030;color:#00ff00;font-weight:700;'
    if 'NEUTRAL' in v: return 'background:#ffc70030;color:#ffc700;font-weight:700;'
    return 'color:#6a8aaa;'

st.markdown('<p class="main-header">Independent Sector Scanner</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">5-Filter ORB System | Gap+Spike Protection | Clean Setup</p>', unsafe_allow_html=True)

saved_data = load_scan_data()
if saved_data and saved_data['timestamp']:
    st.markdown(f"""
    <div class="persistence-info">
        <b>Last Scan Saved:</b> {saved_data['timestamp']} |
        <b>Stocks:</b> {len(saved_data['stock_list']) if saved_data['stock_list'] else 0} |
        <b>Signals:</b> {len(saved_data['results']) if saved_data['results'] else 0}
        <br><small>Data is saved automatically. Even if PC sleeps, your last scan will be here!</small>
    </div>
    """, unsafe_allow_html=True)

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
    for stock in stocks[1:]:
        STOCK_TO_SECTOR[stock] = sector

@st.cache_data(ttl=300)
def get_sector_performance():
    sector_perf = {}
    for sector, etf_list in SECTOR_ETFS.items():
        try:
            etf = yf.Ticker(etf_list[0])
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
            sector_perf[sector] = {"change": round(change_pct, 2), "trend": trend, "open": open_price, "current": current}
        except:
            sector_perf[sector] = {"change": 0, "trend": "NEUTRAL"}
    return sector_perf

def fetch_stock_news(symbol):
    try:
        ticker = yf.Ticker(symbol)
        news = ticker.news
        if not news or len(news) == 0:
            return None
        positive_keywords = ['profit', 'growth', 'rise', 'gain', 'bullish', 'buy', 'upgrade', 'strong', 'beat', 'surge', 'rally', 'positive', 'outperform', 'record', 'high', 'up', 'increase', 'boost', 'good', 'excellent', 'dividend', 'bonus', 'split', 'deal', 'contract', 'expansion']
        negative_keywords = ['loss', 'fall', 'drop', 'decline', 'bearish', 'sell', 'downgrade', 'weak', 'miss', 'plunge', 'crash', 'negative', 'underperform', 'low', 'down', 'decrease', 'cut', 'bad', 'poor', 'debt', 'fraud', 'scam', 'investigation', 'penalty', 'layoff', 'bankrupt']
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
            analyzed_news.append({'title': item.get('title', ''), 'publisher': publisher, 'sentiment': sentiment, 'score': score})
        if total_score >= 2:
            overall = "POSITIVE"
        elif total_score <= -2:
            overall = "NEGATIVE"
        else:
            overall = "NEUTRAL"
        return {'overall_sentiment': overall, 'total_score': total_score, 'news_count': len(analyzed_news), 'articles': analyzed_news}
    except:
        return None

def get_nse_headers():
    return {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36', 'Accept': 'application/json, text/plain, */*', 'Accept-Language': 'en-US,en;q=0.9', 'Referer': 'https://www.nseindia.com/'}

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
    return {'underlying': round(underlying_value, 2), 'atm_strike': atm_strike, 'total_ce_oi': total_ce_oi, 'total_pe_oi': total_pe_oi, 'pcr_oi': round(pcr_oi, 2), 'oi_buildup': oi_buildup, 'oi_signal': oi_signal}

# ============================================================
# OI SPURTS DATA FETCHING
# ============================================================

def fetch_oi_spurts_nse(max_retries=3):
    """Fetch OI Spurts data from NSE - top stocks with highest OI change"""

    # METHOD 1: Try nsepython library (best for cloud)
    if NSEPYTHON_AVAILABLE:
        try:
            st.info("📡 Trying nsepython for OI data...")

            # Use nsefetch for OI spurts
            url = "https://www.nseindia.com/api/live-analysis-oi-spurts"
            data = nsefetch(url)

            if data and 'data' in data:
                oi_spurts = []
                for item in data['data']:
                    symbol = item.get('symbol', '')
                    oi_change = item.get('oiChange', 0)
                    oi_change_pct = item.get('oiChangePer', 0)
                    volume = item.get('volume', 0)
                    price_change = item.get('priceChange', 0)
                    price_change_pct = item.get('priceChangePer', 0)

                    oi_spurts.append({
                        'symbol': symbol,
                        'oi_change': oi_change,
                        'oi_change_pct': oi_change_pct,
                        'volume': volume,
                        'price_change': price_change,
                        'price_change_pct': price_change_pct,
                        'oi_spurt_score': abs(oi_change_pct) + abs(price_change_pct)
                    })

                oi_spurts.sort(key=lambda x: x['oi_change_pct'], reverse=True)
                st.success(f"✅ nsepython OI loaded! Top: {oi_spurts[0]['symbol']} (+{oi_spurts[0]['oi_change_pct']:.1f}%)")
                return oi_spurts
        except Exception as e:
            st.warning(f"nsepython failed: {e}. Trying direct requests...")

    # METHOD 2: Direct requests with retries
    for attempt in range(max_retries):
        try:
            session = requests.Session()
            headers = get_nse_headers()

            session.get('https://www.nseindia.com/', headers=headers, timeout=15)
            time.sleep(1)

            url = "https://www.nseindia.com/api/live-analysis-oi-spurts"
            response = session.get(url, headers=headers, timeout=15)

            if response.status_code == 200:
                data = response.json()
                if data and 'data' in data:
                    oi_spurts = []
                    for item in data['data']:
                        symbol = item.get('symbol', '')
                        oi_change = item.get('oiChange', 0)
                        oi_change_pct = item.get('oiChangePer', 0)
                        volume = item.get('volume', 0)
                        price_change = item.get('priceChange', 0)
                        price_change_pct = item.get('priceChangePer', 0)

                        oi_spurts.append({
                            'symbol': symbol,
                            'oi_change': oi_change,
                            'oi_change_pct': oi_change_pct,
                            'volume': volume,
                            'price_change': price_change,
                            'price_change_pct': price_change_pct,
                            'oi_spurt_score': abs(oi_change_pct) + abs(price_change_pct)
                        })

                    oi_spurts.sort(key=lambda x: x['oi_change_pct'], reverse=True)
                    return oi_spurts

            if attempt < max_retries - 1:
                time.sleep(2)
                continue

        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            else:
                st.warning(f"Direct NSE API failed. Using fallback...")

    # FALLBACK: Yahoo Finance
    return fetch_oi_spurts_fallback()


def fetch_oi_spurts_fallback():
    """Fallback OI data using Yahoo Finance options volume as proxy"""
    try:
        # Top Nifty 50 stocks - check options activity via Yahoo Finance
        fallback_symbols = [
            "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
            "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS", "LT.NS",
            "AXISBANK.NS", "ASIANPAINT.NS", "MARUTI.NS", "TITAN.NS", "SUNPHARMA.NS",
            "BAJFINANCE.NS", "WIPRO.NS", "ULTRACEMCO.NS", "POWERGRID.NS", "NTPC.NS",
            "TATASTEEL.NS", "M&M.NS", "HCLTECH.NS", "TECHM.NS", "ADANIENT.NS"
        ]

        oi_spurts = []
        for symbol in fallback_symbols:
            try:
                ticker = yf.Ticker(symbol)
                # Get options chain for near expiry
                options = ticker.options
                if options and len(options) > 0:
                    opt_chain = ticker.option_chain(options[0])
                    calls = opt_chain.calls
                    puts = opt_chain.puts

                    total_call_oi = calls['openInterest'].sum() if 'openInterest' in calls.columns else 0
                    total_put_oi = puts['openInterest'].sum() if 'openInterest' in puts.columns else 0
                    total_oi = total_call_oi + total_put_oi

                    # Get stock price change
                    hist = ticker.history(period="2d")
                    if len(hist) >= 2:
                        price_change_pct = ((hist['Close'].iloc[-1] - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100
                    else:
                        price_change_pct = 0

                    # Estimate OI change (we don't have historical OI, so use volume as proxy)
                    volume = hist['Volume'].iloc[-1] if len(hist) > 0 else 0
                    avg_volume = hist['Volume'].mean() if len(hist) > 0 else 1
                    volume_ratio = volume / avg_volume if avg_volume > 0 else 1

                    # Synthetic OI change % based on volume spike and price action
                    oi_change_pct = (volume_ratio - 1) * 10 + abs(price_change_pct) * 2

                    oi_spurts.append({
                        'symbol': symbol.replace('.NS', ''),
                        'oi_change': int(total_oi * 0.1),  # Estimate 10% change
                        'oi_change_pct': round(oi_change_pct, 2),
                        'volume': int(volume),
                        'price_change': round(hist['Close'].iloc[-1] - hist['Close'].iloc[-2], 2) if len(hist) >= 2 else 0,
                        'price_change_pct': round(price_change_pct, 2),
                        'oi_spurt_score': round(oi_change_pct + abs(price_change_pct), 2),
                        'source': 'fallback'  # Mark as fallback data
                    })
            except:
                continue

        oi_spurts.sort(key=lambda x: x['oi_change_pct'], reverse=True)

        if oi_spurts:
            st.info(f"⚠️ Using fallback OI data (Yahoo Finance proxy). Top: {oi_spurts[0]['symbol']} (+{oi_spurts[0]['oi_change_pct']:.1f}%)")

        return oi_spurts if oi_spurts else None

    except Exception as e:
        st.error(f"Fallback OI fetch also failed: {e}")
        return None


def get_oi_spurt_rank(symbol, oi_spurts_data):
    """Get OI spurt rank for a symbol (1 = highest OI change)"""
    if not oi_spurts_data:
        return None, None

    symbol_clean = symbol.replace('.NS', '')

    for i, item in enumerate(oi_spurts_data):
        if item['symbol'] == symbol_clean:
            return i + 1, item  # Rank starts at 1

    return None, None


def add_oi_spurts_to_results(results, oi_spurts_data):
    """Add OI Spurts ranking to scan results and sort by OI change % descending"""
    if not oi_spurts_data:
        return results

    for r in results:
        rank, oi_data = get_oi_spurt_rank(r['symbol'], oi_spurts_data)
        r['oi_spurt_rank'] = rank if rank else 999
        r['oi_change_pct'] = oi_data['oi_change_pct'] if oi_data else 0
        r['oi_spurt_score'] = oi_data['oi_spurt_score'] if oi_data else 0

    # Sort by OI change % descending (highest OI change first)
    # Then by accuracy descending
    results.sort(key=lambda x: (-x['oi_change_pct'], -x['accuracy']))

    return results


st.sidebar.header("Scanner Settings")

st.sidebar.subheader("Data Source")
data_source = st.sidebar.radio(
    "Select Data Provider",
    ["Yahoo Finance (Free, 15min delay)", "Dhan API (Real-time, requires API key)"]
)

dhan_access_token = ""

if "Dhan" in data_source:
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Dhan API Setup")
    st.sidebar.markdown("**Step 1:** [Click here to generate token](https://web.dhan.co/dhanhq)")
    st.sidebar.caption("Login → DhanHQ Trading APIs → Generate Access Token → Copy")
    st.sidebar.markdown("**Step 2:** Paste your token below")
    dhan_access_token = st.sidebar.text_input(
        "Dhan Access Token",
        type="password",
        placeholder="Paste token here and press Enter",
        help="Token expires in 24 hours. Generate a new one daily."
    )
    if dhan_access_token:
        st.sidebar.success("Token saved for this session!")
        st.sidebar.caption("Token will be lost if you refresh the page. That's normal.")
    else:
        st.sidebar.warning("Please paste your Dhan Access Token above")
    st.sidebar.markdown("---")
    st.sidebar.info("Token expires every 24 hours. Generate a new one each morning before market opens.")

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
    "Nifty Next 50": [
        "BERGEPAINT.NS", "CHOLAFIN.NS", "DABUR.NS", "GODREJCP.NS", "HAVELLS.NS",
        "ICICIPRULI.NS", "INDIGO.NS", "JINDALSTEL.NS", "LICI.NS", "LODHA.NS",
        "MCDOWELL-N.NS", "MOTHERSON.NS", "NAUKRI.NS", "PIDILITIND.NS", "POLYCAB.NS",
        "SAMMAANCAP.NS", "SIEMENS.NS", "SRF.NS", "TORNTPHARM.NS", "TVSMOTOR.NS",
        "ABB.NS", "ACC.NS", "AMBUJACEM.NS", "AUROPHARMA.NS", "BANDHANBNK.NS",
        "BANKBARODA.NS", "BEL.NS", "BHEL.NS", "CANBK.NS", "COLPAL.NS",
        "CONCOR.NS", "CUMMINSIND.NS", "DMART.NS", "GAIL.NS", "GODREJPROP.NS",
        "HAL.NS", "HINDPETRO.NS", "IDBI.NS", "IDFCFIRSTB.NS", "INDUSTOWER.NS",
        "IOB.NS", "IRCTC.NS", "JUBLFOOD.NS", "L&TFH.NS", "LUPIN.NS",
        "MARICO.NS", "MUTHOOTFIN.NS", "NMDC.NS", "OBEROIRLTY.NS", "PFC.NS"
    ],
    "Nifty Midcap 100": [
        "ABBOTINDIA.NS", "ALKEM.NS", "APLAPOLLO.NS", "ASTRAL.NS", "ATUL.NS",
        "BATAINDIA.NS", "BHARATFORG.NS", "BIKAJI.NS", "BLUESTARCO.NS", "BSOFT.NS",
        "CGPOWER.NS", "CHAMBLFERT.NS", "COFORGE.NS", "COROMANDEL.NS", "CREDITACC.NS",
        "CROMPTON.NS", "CYIENT.NS", "DALBHARAT.NS", "DEEPAKNTR.NS", "DELHIVERY.NS",
        "DIXON.NS", "ESCORTS.NS", "EXIDEIND.NS", "FEDERALBNK.NS", "GLAND.NS",
        "GLAXO.NS", "GLENMARK.NS", "GNFC.NS", "GODREJIND.NS", "GUJGASLTD.NS",
        "HAPPSTMNDS.NS", "HINDCOPPER.NS", "HINDZINC.NS", "HUDCO.NS", "IIFL.NS",
        "INDIAMART.NS", "INDIANB.NS", "IPCALAB.NS", "JBCHEPHARM.NS", "JSL.NS",
        "KEI.NS", "KPITTECH.NS", "LALPATHLAB.NS", "LAURUSLABS.NS", "LINDEINDIA.NS",
        "LTTS.NS", "M&MFIN.NS", "MANAPPURAM.NS", "MAXHEALTH.NS", "METROBRAND.NS"
    ],
    "Bank Nifty": [
        "HDFCBANK.NS", "ICICIBANK.NS", "KOTAKBANK.NS", "AXISBANK.NS", "SBIN.NS",
        "INDUSINDBK.NS", "BANDHANBNK.NS", "FEDERALBNK.NS", "IDFCFIRSTB.NS", "PNB.NS",
        "BANKBARODA.NS", "CANBK.NS", "UNIONBANK.NS", "AUBANK.NS", "RBLBANK.NS"
    ],
    "Nifty 200": [
        "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
        "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS",
        "LT.NS", "AXISBANK.NS", "ASIANPAINT.NS", "MARUTI.NS", "TITAN.NS",
        "SUNPHARMA.NS", "BAJFINANCE.NS", "WIPRO.NS", "ULTRACEMCO.NS", "NESTLEIND.NS",
        "POWERGRID.NS", "NTPC.NS", "TATASTEEL.NS", "M&M.NS", "HCLTECH.NS",
        "TECHM.NS", "INDUSINDBK.NS", "GRASIM.NS", "ADANIENT.NS", "CIPLA.NS",
        "SBILIFE.NS", "BAJAJFINSV.NS", "BRITANNIA.NS", "APOLLOHOSP.NS", "ONGC.NS",
        "EICHERMOT.NS", "TATAMOTORS.NS", "DIVISLAB.NS", "HDFCLIFE.NS", "COALINDIA.NS",
        "JSWSTEEL.NS", "HEROMOTOCO.NS", "BPCL.NS", "DRREDDY.NS", "ADANIPORTS.NS",
        "HINDALCO.NS", "UPL.NS", "SHREECEM.NS", "BAJAJ-AUTO.NS", "TATACONSUM.NS",
        "ABB.NS", "ACC.NS", "AMBUJACEM.NS", "ASHOKLEY.NS", "AUBANK.NS",
        "AUROPHARMA.NS", "BAJAJHLDNG.NS", "BANDHANBNK.NS", "BANKBARODA.NS", "BATAINDIA.NS",
        "BEL.NS", "BERGEPAINT.NS", "BHEL.NS", "BOSCHLTD.NS", "CANBK.NS",
        "CHOLAFIN.NS", "COLPAL.NS", "CONCOR.NS", "CUMMINSIND.NS", "DABUR.NS",
        "DLF.NS", "GAIL.NS", "GODREJCP.NS", "GODREJPROP.NS", "HAL.NS",
        "HAVELLS.NS", "HINDPETRO.NS", "ICICIGI.NS", "ICICIPRULI.NS", "IDBI.NS",
        "IDFCFIRSTB.NS", "INDIGO.NS", "INDUSTOWER.NS", "IOB.NS", "IRCTC.NS",
        "JINDALSTEL.NS", "JUBLFOOD.NS", "L&TFH.NS", "LICI.NS", "LODHA.NS",
        "LUPIN.NS", "MARICO.NS", "MCDOWELL-N.NS", "MOTHERSON.NS", "MUTHOOTFIN.NS",
        "NAUKRI.NS", "NMDC.NS", "OBEROIRLTY.NS", "PEL.NS", "PFC.NS",
        "PIDILITIND.NS", "PNB.NS", "POLYCAB.NS", "RBLBANK.NS", "RECLTD.NS",
        "SAIL.NS", "SBICARD.NS", "SIEMENS.NS", "SRF.NS", "SUNTV.NS",
        "TATACOMM.NS", "TATAPOWER.NS", "TORNTPHARM.NS", "TORNTPOWER.NS", "TRENT.NS",
        "TVSMOTOR.NS", "UBL.NS", "UNITDSPR.NS", "UNOMINDA.NS", "VOLTAS.NS",
        "ZOMATO.NS", "ZYDUSLIFE.NS", "AARTIIND.NS", "ABCAPITAL.NS", "ABFRL.NS",
        "ADANIGREEN.NS", "ADANIPOWER.NS", "AJANTPHARM.NS", "ALKEM.NS", "ALKYLAMINE.NS",
        "AMARAJABAT.NS", "ANURAS.NS", "APLAPOLLO.NS", "APLLTD.NS", "ASTRAL.NS",
        "ASTRAZEN.NS", "ATGL.NS", "ATUL.NS", "BAJAJELEC.NS", "BALKRISIND.NS",
        "BALRAMCHIN.NS", "BAYERCROP.NS", "BDL.NS", "BEML.NS", "BIKAJI.NS",
        "BLUEDART.NS", "BLUESTARCO.NS", "BRIGADE.NS", "BSOFT.NS", "CANFINHOME.NS",
        "CARBORUNIV.NS", "CASTROLIND.NS", "CEATLTD.NS", "CENTRALBK.NS", "CENTURYTEX.NS",
        "CESC.NS", "CGPOWER.NS", "CHAMBLFERT.NS", "CHOLAHLDNG.NS", "CLEAN.NS",
        "COCHINSHIP.NS", "COFORGE.NS", "COROMANDEL.NS", "CREDITACC.NS", "CROMPTON.NS",
        "CSBBANK.NS", "CUB.NS", "CYIENT.NS", "DALBHARAT.NS", "DCBBANK.NS",
        "DEEPAKFERT.NS", "DEEPAKNTR.NS", "DELHIVERY.NS", "DIXON.NS", "EIDPARRY.NS",
        "EMAMILTD.NS", "ENDURANCE.NS", "ESCORTS.NS", "EXIDEIND.NS", "FEDERALBNK.NS",
        "FORTIS.NS", "FSL.NS", "GLAND.NS", "GLAXO.NS", "GLENMARK.NS",
        "GMRINFRA.NS", "GNFC.NS", "GODREJAGRO.NS", "GODREJIND.NS", "GRANULES.NS",
        "GRAPHITE.NS", "GRINDWELL.NS", "GSPL.NS", "GUJGASLTD.NS", "HAPPSTMNDS.NS",
        "HATHWAY.NS", "HINDCOPPER.NS", "HINDZINC.NS", "HUDCO.NS", "IBULHSGFIN.NS",
        "IDFC.NS", "IEX.NS", "IGL.NS", "IIFL.NS", "INDHOTEL.NS",
        "INDIAMART.NS", "INDIANB.NS", "INDOCO.NS", "INFIBEAM.NS", "INTELLECT.NS",
        "IPCALAB.NS", "IRB.NS", "ISEC.NS", "ITI.NS", "J&KBANK.NS",
        "JBCHEPHARM.NS", "JINDALSAW.NS", "JISLJALEQS.NS", "JKCEMENT.NS", "JKLAKSHMI.NS",
        "JKTYRE.NS", "JMFINANCIL.NS", "JSL.NS", "JUBLINGREA.NS", "JUSTDIAL.NS",
        "KAJARIACER.NS", "KALPATPOWR.NS", "KANSAINER.NS", "KARURVYSYA.NS", "KEC.NS",
        "KEI.NS", "KNRCON.NS", "KPITTECH.NS", "KPRMILL.NS", "KRBL.NS",
        "KSB.NS", "LALPATHLAB.NS", "LAURUSLABS.NS", "LEMONTREE.NS", "LICHSGFIN.NS",
        "LINDEINDIA.NS", "LTTS.NS", "M&MFIN.NS", "MAHABANK.NS", "MAHINDCIE.NS",
        "MAHLIFE.NS", "MANAPPURAM.NS", "MASTEK.NS", "MAXHEALTH.NS", "MAZDOCK.NS",
        "METROBRAND.NS", "MFSL.NS", "MGL.NS", "MIDHANI.NS", "MINDACORP.NS",
        "MINDTREE.NS", "MMTC.NS", "MOIL.NS", "MOTILALOFS.NS", "MPHASIS.NS",
        "MRF.NS", "NATCOPHARM.NS", "NATIONALUM.NS", "NAVINFLUOR.NS", "NBCC.NS",
        "NCC.NS", "NESCO.NS", "NETWORK18.NS", "NH.NS", "NHPC.NS",
        "NIACL.NS", "NLCINDIA.NS", "NOCIL.NS", "OIL.NS", "ORIENTCEM.NS",
        "ORIENTELEC.NS", "ORIENTPPR.NS", "PAGEIND.NS", "PERSISTENT.NS", "PETRONET.NS",
        "PFIZER.NS", "PGHL.NS", "PGHH.NS", "PHOENIXLTD.NS", "PIIND.NS",
        "PNBHOUSING.NS", "POLYMED.NS", "POONAWALLA.NS", "PRAJIND.NS", "PRESTIGE.NS",
        "PRINCEPIPE.NS", "PRIVISCL.NS", "PSB.NS", "PSPPROJECT.NS", "PTC.NS",
        "PVRINOX.NS", "QUESS.NS", "RAILTEL.NS", "RAIN.NS", "RAJESHEXPO.NS",
        "RALLIS.NS", "RAMCOCEM.NS", "RATNAMANI.NS", "RAYMOND.NS", "RCF.NS",
        "REDINGTON.NS", "RELAXO.NS", "RENUKA.NS", "ROSSARI.NS", "RTNPOWER.NS",
        "RVNL.NS", "SAGCEM.NS", "SAKSOFT.NS", "SANDHAR.NS", "SANOFI.NS",
        "SARDAEN.NS", "SCHAEFFLER.NS", "SCHNEIDER.NS", "SCI.NS", "SEQUENT.NS",
        "SHILPAMED.NS", "SHOPERSTOP.NS", "SHRIRAMFIN.NS", "SIS.NS", "SJVN.NS",
        "SKFINDIA.NS", "SOBHA.NS", "SOLARINDS.NS", "SONACOMS.NS", "SPANDANA.NS",
        "SPLPETRO.NS", "STAR.NS", "STARCEMENT.NS", "STLTECH.NS", "SUBROS.NS",
        "SUDARSCHEM.NS", "SUMICHEM.NS", "SUNDRMFAST.NS", "SUNTECK.NS", "SUPRAJIT.NS",
        "SUPREMEIND.NS", "SUVENPHAR.NS", "SWANENERGY.NS", "SWARAJENG.NS", "SYMPHONY.NS",
        "SYNGENE.NS", "TATACHEM.NS", "TATAELXSI.NS", "TEAMLEASE.NS", "TEJASNET.NS",
        "THERMAX.NS", "TIMKEN.NS", "TRIDENT.NS", "TRITURBINE.NS", "TTKPRESTIG.NS",
        "TV18BRDCST.NS", "UCOBANK.NS", "UJJIVANSFB.NS", "UNIONBANK.NS", "UTIAMC.NS",
        "VAKRANGEE.NS", "VARROC.NS", "VEDL.NS", "VENKEYS.NS", "VGUARD.NS",
        "VIJAYA.NS", "VINATIORGA.NS", "VIPIND.NS", "VRLLOG.NS", "VSTIND.NS",
        "WABAG.NS", "WELCORP.NS", "WELSPUNIND.NS", "WESTLIFE.NS", "WHIRLPOOL.NS",
        "WOCKPHARMA.NS", "WONDERLA.NS", "YESBANK.NS", "ZEEL.NS", "ZENSARTECH.NS",
        "ZYDUSWELL.NS"
    ],
    "Custom": []
}

selected_universe = st.sidebar.selectbox("Select Universe", list(stock_options.keys()))
if selected_universe == "Custom":
    custom_stocks = st.sidebar.text_area("Enter Symbols (comma separated)", "RELIANCE.NS, TCS.NS")
    stock_list = [s.strip().upper() for s in custom_stocks.split(",") if s.strip()]
else:
    stock_list = stock_options[selected_universe]

st.sidebar.subheader("ORB Settings")
orb_minutes = st.sidebar.slider("Opening Range (minutes)", 5, 30, 15)

st.sidebar.subheader("Gap + Spike Filter")
st.sidebar.markdown("Skip stocks with 2% gap + 1.5% first 5-min move")
gap_spike_filter = st.sidebar.checkbox("Enable Gap+Spike Filter", value=True)

st.sidebar.subheader("Accuracy Mode")
accuracy_mode = st.sidebar.selectbox("Select Mode", ["Conservative (80%+)", "Balanced (70-80%)", "Aggressive (60-70%)"])
min_accuracy = {"Conservative (80%+)": 80, "Balanced (70-80%)": 70, "Aggressive (60-70%)": 60}[accuracy_mode]

st.sidebar.subheader("Optional Extras")
use_oi = st.sidebar.checkbox("OI Buildup Analysis", value=True)
use_news = st.sidebar.checkbox("News Sentiment", value=True)

st.sidebar.subheader("Risk Management")
risk_reward = st.sidebar.slider("Risk : Reward", 1.0, 4.0, 2.5, 0.5)

st.sidebar.subheader("Price Filters")
min_price = st.sidebar.number_input("Min Price (Rs)", 50, 50000, 100)
max_price = st.sidebar.number_input("Max Price (Rs)", 50, 50000, 10000)

st.sidebar.markdown("---")
refresh = st.sidebar.button("SCAN NOW", type="primary", use_container_width=True)

if st.sidebar.button("Clear Saved Data", use_container_width=True):
    clear_saved_data()
    st.sidebar.success("Saved data cleared!")
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.info(f"""**{accuracy_mode}**
- Min Accuracy: {min_accuracy}%
- 5 Filters: ORB | Volume | VWAP | EMA20 | Gap+Spike
- STRONG: 80%+ | BUY: 60-79%
- RSI Removed | Prev Day Removed""")

@st.cache_data(ttl=300)
def fetch_data(symbol, period="5d", interval="5m", data_source="Yahoo Finance", access_token=""):
    try:
        if "Dhan" in data_source and access_token and access_token.strip():
            security_id = get_dhan_security_id(symbol)
            if security_id:
                interval_map = {"1m": "1", "5m": "5", "15m": "15", "30m": "25", "60m": "60"}
                dhan_interval = interval_map.get(interval, "5")
                days_map = {"1d": 1, "5d": 5, "10d": 10, "30d": 30, "90d": 90}
                days = days_map.get(period, 5)
                from_date = (get_ist_now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
                to_date = get_ist_now().strftime('%Y-%m-%d %H:%M:%S')
                df = fetch_dhan_intraday_data(security_id, access_token, dhan_interval, from_date, to_date)
                if df is not None and not df.empty:
                    return df
                else:
                    st.warning(f"Dhan API failed for {symbol}, falling back to Yahoo Finance")
            else:
                st.warning(f"Dhan Security ID not found for {symbol}, using Yahoo Finance")
        max_retries = 3
        for attempt in range(max_retries):
            try:
                ticker = yf.Ticker(symbol)
                df = ticker.history(period=period, interval=interval)
                break
            except Exception as e:
                if "Too Many Requests" in str(e) and attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                raise
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
    except Exception as e:
        st.error(f"Error fetching data for {symbol}: {e}")
        return None

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

def analyze_orb_ultimate(symbol, sector_perf, orb_mins=15):
    df_5m = fetch_data(symbol, period="5d", interval="5m", data_source=data_source, access_token=dhan_access_token)
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

    # ============================================================
    # GAP + SPIKE FILTER (NEW)
    # ============================================================
    gap_info = {"gap_pct": 0, "spike_pct": 0, "skipped": False, "reason": ""}

    if gap_spike_filter and len(df_today) >= 1:
        first_candle = df_today.iloc[0]
        prev_close = df_5m[df_5m['Date'].dt.date < today]['Close'].iloc[-1] if len(df_5m[df_5m['Date'].dt.date < today]) > 0 else first_candle['Open']

        gap_pct = ((first_candle['Open'] - prev_close) / prev_close) * 100
        gap_info["gap_pct"] = gap_pct

        if abs(gap_pct) > 2:
            high_move = ((first_candle['High'] - first_candle['Open']) / first_candle['Open']) * 100
            low_move = ((first_candle['Open'] - first_candle['Low']) / first_candle['Open']) * 100

            if gap_pct > 2 and high_move > 1.5:
                gap_info["skipped"] = True
                gap_info["spike_pct"] = high_move
                gap_info["reason"] = f"Gap Up {gap_pct:.1f}% + Spike {high_move:.1f}%"
                return None, f"SKIP: {gap_info['reason']}"

            if gap_pct < -2 and low_move > 1.5:
                gap_info["skipped"] = True
                gap_info["spike_pct"] = low_move
                gap_info["reason"] = f"Gap Down {gap_pct:.1f}% + Spike {low_move:.1f}%"
                return None, f"SKIP: {gap_info['reason']}"

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

    # ============================================================
    # 5 FILTERS ONLY
    # ============================================================
    filters_passed = 1  # ORB Breakout already passed
    total_filters = 1   # Start with ORB
    filter_details = []
    filter_details.append(("ORB Breakout", True, f"Price broke {base_signal}"))

    # FILTER 2: Volume
    try:
        avg_volume = df_today['Volume'].rolling(window=5).mean().iloc[-1]
        volume_ratio = current_candle['Volume'] / avg_volume if avg_volume > 0 else 0
        volume_pass = volume_ratio >= 1.3
        if volume_pass:
            filters_passed += 1
        total_filters += 1
        filter_details.append(("Volume", volume_pass, f"{volume_ratio:.1f}x"))
    except:
        total_filters += 1
        filter_details.append(("Volume", False, "Error"))

    # FILTER 3: VWAP
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
        total_filters += 1
        filter_details.append(("VWAP", vwap_pass, f"Rs{vwap:.2f}"))
    else:
        total_filters += 1
        filter_details.append(("VWAP", False, "Error"))

    # FILTER 4: EMA20
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
        total_filters += 1
        filter_details.append(("EMA20", ema_pass, f"Rs{ema20:.2f}"))
    else:
        total_filters += 1
        filter_details.append(("EMA20", False, "Error"))

    # FILTER 5: Gap+Spike
    if gap_spike_filter:
        # Already checked above - if we reached here, it passed
        filters_passed += 1
        total_filters += 1
        filter_details.append(("Gap+Spike", True, "Passed"))
    # If disabled, don't add to total_filters at all

    accuracy = (filters_passed / total_filters) * 100 if total_filters > 0 else 0
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
        'sector': STOCK_TO_SECTOR.get(symbol, None),
        'day_high': round(df_today['High'].max(), 2),
        'day_low': round(df_today['Low'].min(), 2),
        'vwap': round(vwap, 2) if vwap else None,
        'atr': round(atr, 2),
        'ema20': round(ema20, 2) if ema20 else None,
    }, None

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

    # Simplified logic: Accuracy determines strength
    if accuracy >= 80:
        if orb_signal == "BUY":
            return "STRONG BUY", combined, oi_signal, oi_buildup, news_impact
        elif orb_signal == "SELL":
            return "STRONG SELL", combined, oi_signal, oi_buildup, news_impact
    elif accuracy >= 60:
        if orb_signal == "BUY":
            return "BUY", combined, oi_signal, oi_buildup, news_impact
        elif orb_signal == "SELL":
            return "SELL", combined, oi_signal, oi_buildup, news_impact
    return "NEUTRAL", combined, oi_signal, oi_buildup, news_impact

def display_results(results, sector_perf):
    if not results:
        st.warning("No signals found.")
        st.info("Market hours: 9:15 AM - 3:30 PM IST")
        return

    strong_buy_list = [r for r in results if r.get('final_signal') and "STRONG BUY" in r.get('final_signal', '')]
    buy_list = [r for r in results if r.get('final_signal') == "BUY"]
    strong_sell_list = [r for r in results if r.get('final_signal') and "STRONG SELL" in r.get('final_signal', '')]
    sell_list = [r for r in results if r.get('final_signal') == "SELL"]

    strong_buy = len(strong_buy_list)
    buy = len(buy_list)
    strong_sell = len(strong_sell_list)
    sell = len(sell_list)

    # Top metrics row
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    with col1:
        st.markdown(f'<div class="metric-card" style="background: linear-gradient(135deg, #00b09b 0%, #96c93d 100%);"><h4>STRONG BUY</h4><h1>{strong_buy}</h1></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="metric-card" style="background: linear-gradient(135deg, #56ab2f 0%, #a8e063 100%);"><h4>BUY</h4><h1>{buy}</h1></div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="metric-card" style="background: linear-gradient(135deg, #f7971e 0%, #ffd200 100%); color: #333;"><h4>TOTAL BUY</h4><h1>{strong_buy + buy}</h1></div>', unsafe_allow_html=True)
    with col4:
        st.markdown(f'<div class="metric-card" style="background: linear-gradient(135deg, #cb2d3e 0%, #ef473a 100%);"><h4>STRONG SELL</h4><h1>{strong_sell}</h1></div>', unsafe_allow_html=True)
    with col5:
        st.markdown(f'<div class="metric-card" style="background: linear-gradient(135deg, #eb3349 0%, #f45c43 100%);"><h4>SELL</h4><h1>{sell}</h1></div>', unsafe_allow_html=True)
    with col6:
        st.markdown(f'<div class="metric-card" style="background: linear-gradient(135deg, #8e2de2 0%, #4a00e0 100%);"><h4>TOTAL SELL</h4><h1>{strong_sell + sell}</h1></div>', unsafe_allow_html=True)

    st.markdown("---")

    # Side-by-side BUY and SELL columns
    buy_col, sell_col = st.columns(2)

    # LEFT COLUMN - BUY SIGNALS
    with buy_col:
        st.markdown("<div style='background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); padding: 15px; border-radius: 15px; text-align: center; color: white; margin-bottom: 20px;'><h2>🟢 BUY SIGNALS</h2><h4>{0} Signals</h4></div>".format(strong_buy + buy), unsafe_allow_html=True)

        if not strong_buy_list and not buy_list:
            st.info("No BUY signals found")
        else:
            # STRONG BUY first
            for row in strong_buy_list:
                _display_buy_card(row, "STRONG BUY", "strong-buy")
            # Then normal BUY
            for row in buy_list:
                _display_buy_card(row, "BUY", "buy")

    # RIGHT COLUMN - SELL SIGNALS
    with sell_col:
        st.markdown("<div style='background: linear-gradient(135deg, #cb2d3e 0%, #ef473a 100%); padding: 15px; border-radius: 15px; text-align: center; color: white; margin-bottom: 20px;'><h2>🔴 SELL SIGNALS</h2><h4>{0} Signals</h4></div>".format(strong_sell + sell), unsafe_allow_html=True)

        if not strong_sell_list and not sell_list:
            st.info("No SELL signals found")
        else:
            # STRONG SELL first
            for row in strong_sell_list:
                _display_sell_card(row, "STRONG SELL", "strong-sell")
            # Then normal SELL
            for row in sell_list:
                _display_sell_card(row, "SELL", "sell")

    st.markdown("---")

    # Export
    export_results = []
    for r in results:
        er = {k: v for k, v in r.items() if k not in ['oi_data', 'news_data', 'filter_details']}
        er['NEWS_SENTIMENT'] = r.get('news_data', {}).get('overall_sentiment', 'NO DATA') if r.get('news_data') else 'NO DATA'
        er['NEWS_IMPACT'] = r.get('news_impact', 'NO DATA')
        export_results.append(er)
    df_export = pd.DataFrame(export_results)
    csv = df_export.to_csv(index=False)
    st.download_button(label="Download Signals", data=csv, file_name=f"sector_scanner_{get_ist_now().strftime('%Y%m%d_%H%M')}.csv", mime="text/csv")

def _display_buy_card(row, sig, card_class):
    """Display BUY signal card"""
    acc = row.get('accuracy', 0)
    oi_rank = row.get('oi_spurt_rank', 999)
    oi_change = row.get('oi_change_pct', 0)

    # OI badge - show OI change % prominently
    oi_badge = ""
    oi_change = row.get('oi_change_pct', 0)
    if oi_change != 0:
        if abs(oi_change) >= 20:
            oi_badge = f" 🔥 OI {oi_change:+.1f}%"
        elif abs(oi_change) >= 10:
            oi_badge = f" ⚡ OI {oi_change:+.1f}%"
        elif abs(oi_change) >= 5:
            oi_badge = f" 📈 OI {oi_change:+.1f}%"
        else:
            oi_badge = f" OI {oi_change:+.1f}%"

    news_badge = ""
    if row.get('news_impact') and row['news_impact'] != "NO DATA":
        if row['news_impact'] == "SUPPORTS":
            news_badge = " 🟢"
        elif row['news_impact'] == "CONTRADICTS":
            news_badge = " 🔴"
        else:
            news_badge = " 🟡"

    acc_class = "acc-90" if acc >= 90 else ("acc-80" if acc >= 80 else "acc-70")

    # Build OI info for title
    oi_change_val = row.get('oi_change_pct', 0)
    oi_rank = row.get('oi_spurt_rank', 999)

    # OI badge for title
    oi_title_badge = ""
    if oi_change_val != 0:
        if abs(oi_change_val) >= 20:
            oi_title_badge = f" 🔥 OI {oi_change_val:+.1f}%"
        elif abs(oi_change_val) >= 10:
            oi_title_badge = f" ⚡ OI {oi_change_val:+.1f}%"
        elif abs(oi_change_val) >= 5:
            oi_title_badge = f" 📈 OI {oi_change_val:+.1f}%"
        elif oi_change_val != 0:
            oi_title_badge = f" OI {oi_change_val:+.1f}%"

    with st.expander(f"{sig} **{row.get('symbol', 'N/A')}** | Rs{row.get('current_price', 0)} | {acc}%{news_badge}{oi_title_badge}"):
        st.markdown(f'<div class="signal-card {card_class}"><h3>{sig}</h3></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="accuracy-badge {acc_class}">{acc}% ({row["filters_passed"]}/{row["total_filters"]})</div>', unsafe_allow_html=True)

        # OI Spurts info - PROMINENT display
        if oi_change_val != 0:
            oi_color = "#ff6b35" if abs(oi_change_val) >= 20 else ("#f9ca24" if abs(oi_change_val) >= 10 else "#6c5ce7")
            oi_bg = "#fff5f0" if abs(oi_change_val) >= 20 else ("#fffbe6" if abs(oi_change_val) >= 10 else "#f0f0ff")
            st.markdown(f"""
            <div style='background: {oi_bg}; padding: 12px 15px; margin: 10px 0; border-radius: 10px; 
                        border-left: 5px solid {oi_color}; text-align: center;'>
                <span style='font-size: 24px; font-weight: bold; color: {oi_color};'>
                    📈 OI Change: {oi_change_val:+.1f}%
                </span>
                <br><span style='color: #666; font-size: 13px;'>
                    OI Spurts Rank: #{oi_rank} | Score: {row.get('oi_spurt_score', 0):.1f}
                </span>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style='background: #f8f9fa; padding: 10px 15px; margin: 10px 0; border-radius: 10px; 
                        border-left: 5px solid #ccc; text-align: center; color: #888;'>
                📊 OI Data: Not Available
            </div>
            """, unsafe_allow_html=True)

        if row.get('sector'):
            st.markdown(f'<div class="filter-box"><b>Sector: {row["sector"]}</b></div>', unsafe_allow_html=True)

        if row.get('news_impact') and row['news_impact'] != "NO DATA":
            news_sentiment = "POSITIVE" if row['news_impact'] == "SUPPORTS" else ("NEGATIVE" if row['news_impact'] == "CONTRADICTS" else "NEUTRAL")
            news_class = "news-positive" if news_sentiment == "POSITIVE" else ("news-negative" if news_sentiment == "NEGATIVE" else "news-neutral")
            st.markdown(f'<div class="{news_class}"><b>News Impact: {row["news_impact"]}</b></div>', unsafe_allow_html=True)
            if row.get('news_data') and row['news_data'].get('articles'):
                with st.expander("📰 View News Details"):
                    for article in row['news_data']['articles'][:3]:
                        sentiment_emoji = "🟢" if article.get('sentiment') == "POSITIVE" else ("🔴" if article.get('sentiment') == "NEGATIVE" else "⚪")
                        st.markdown(f"{sentiment_emoji} **{article.get('title', 'No title')}**")
                        st.caption(f"Source: {article.get('publisher', 'Unknown')} | Score: {article.get('score', 0)}")
                        st.markdown("---")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f'<div class="filter-box"><b>Trade</b><br>Entry: <b>Rs{row["entry_price"]}</b><br>SL: <span style="color:red">Rs{row["stop_loss"]}</span><br>Target: <span style="color:green">Rs{row["target"]}</span><br>Risk: Rs{row["risk"]} ({row["risk_percent"]}%)<br>R:R = 1:{risk_reward}</div>', unsafe_allow_html=True)
        with col2:
            st.markdown(f'<div class="filter-box"><b>Tech</b><br>VWAP: Rs{row["vwap"] if row.get("vwap") else "N/A"}<br>ATR: Rs{row.get("atr", "N/A")}<br>EMA20: Rs{row["ema20"] if row.get("ema20") else "N/A"}</div>', unsafe_allow_html=True)

        if row.get('oi_signal') and row['oi_signal'] != "NEUTRAL":
            st.markdown(f'<div class="filter-box"><b>OI Analysis</b><br>{row.get("oi_buildup", "N/A")}<br>Signal: {row["oi_signal"]}</div>', unsafe_allow_html=True)





        st.markdown("---")
        st.markdown("**📋 Filter Analysis:**")

        filter_details = row.get('filter_details', [])
        pass_count = 0
        fail_count = 0

        for item in filter_details:
            if isinstance(item, list) and len(item) >= 3:
                filter_name, passed, detail = item[0], item[1], item[2]
            elif isinstance(item, tuple) and len(item) >= 3:
                filter_name, passed, detail = item[0], item[1], item[2]
            else:
                continue

            if passed:
                pass_count += 1
                st.markdown(f"<div style='background: linear-gradient(90deg, #00ff0015 0%, transparent 100%); padding: 6px 12px; margin: 2px 0; border-radius: 6px; border-left: 3px solid #00ff88; font-size: 13px;'><span style='color:#00ff88; font-weight:bold;'>✅</span> <b>{filter_name}</b> <span style='color:#888; float:right;'>{detail}</span></div>", unsafe_allow_html=True)
            else:
                fail_count += 1
                st.markdown(f"<div style='background: linear-gradient(90deg, #ff000015 0%, transparent 100%); padding: 6px 12px; margin: 2px 0; border-radius: 6px; border-left: 3px solid #ff4060; font-size: 13px;'><span style='color:#ff4060; font-weight:bold;'>❌</span> <b>{filter_name}</b> <span style='color:#888; float:right;'>{detail}</span></div>", unsafe_allow_html=True)

        st.markdown(f"<div style='text-align: center; padding: 8px; margin-top: 8px; background: #f0f2f6; border-radius: 8px; font-size: 13px;'><b>Summary:</b> <span style='color:#00ff88; font-weight:bold;'>{pass_count} ✓</span> | <span style='color:#ff4060; font-weight:bold;'>{fail_count} ✗</span> | <b>Accuracy: {acc}%</b></div>", unsafe_allow_html=True)

def _display_sell_card(row, sig, card_class):
    """Display SELL signal card"""
    acc = row.get('accuracy', 0)
    oi_rank = row.get('oi_spurt_rank', 999)
    oi_change = row.get('oi_change_pct', 0)

    # OI badge
    oi_badge = ""
    if oi_rank and oi_rank <= 10:
        oi_badge = f" 🔥 OI#{oi_rank} ({oi_change:.1f}%)"
    elif oi_rank and oi_rank <= 50:
        oi_badge = f" ⚡ OI#{oi_rank}"

    news_badge = ""
    if row.get('news_impact') and row['news_impact'] != "NO DATA":
        if row['news_impact'] == "SUPPORTS":
            news_badge = " 🟢"
        elif row['news_impact'] == "CONTRADICTS":
            news_badge = " 🔴"
        else:
            news_badge = " 🟡"

    acc_class = "acc-90" if acc >= 90 else ("acc-80" if acc >= 80 else "acc-70")

    # Build OI info for title
    oi_change_val = row.get('oi_change_pct', 0)
    oi_rank = row.get('oi_spurt_rank', 999)

    # OI badge for title
    oi_title_badge = ""
    if oi_change_val != 0:
        if abs(oi_change_val) >= 20:
            oi_title_badge = f" 🔥 OI {oi_change_val:+.1f}%"
        elif abs(oi_change_val) >= 10:
            oi_title_badge = f" ⚡ OI {oi_change_val:+.1f}%"
        elif abs(oi_change_val) >= 5:
            oi_title_badge = f" 📈 OI {oi_change_val:+.1f}%"
        elif oi_change_val != 0:
            oi_title_badge = f" OI {oi_change_val:+.1f}%"

    with st.expander(f"{sig} **{row.get('symbol', 'N/A')}** | Rs{row.get('current_price', 0)} | {acc}%{news_badge}{oi_title_badge}"):
        st.markdown(f'<div class="signal-card {card_class}"><h3>{sig}</h3></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="accuracy-badge {acc_class}">{acc}% ({row["filters_passed"]}/{row["total_filters"]})</div>', unsafe_allow_html=True)

        # OI Spurts info - PROMINENT display
        if oi_change_val != 0:
            oi_color = "#ff6b35" if abs(oi_change_val) >= 20 else ("#f9ca24" if abs(oi_change_val) >= 10 else "#6c5ce7")
            oi_bg = "#fff5f0" if abs(oi_change_val) >= 20 else ("#fffbe6" if abs(oi_change_val) >= 10 else "#f0f0ff")
            st.markdown(f"""
            <div style='background: {oi_bg}; padding: 12px 15px; margin: 10px 0; border-radius: 10px; 
                        border-left: 5px solid {oi_color}; text-align: center;'>
                <span style='font-size: 24px; font-weight: bold; color: {oi_color};'>
                    📈 OI Change: {oi_change_val:+.1f}%
                </span>
                <br><span style='color: #666; font-size: 13px;'>
                    OI Spurts Rank: #{oi_rank} | Score: {row.get('oi_spurt_score', 0):.1f}
                </span>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style='background: #f8f9fa; padding: 10px 15px; margin: 10px 0; border-radius: 10px; 
                        border-left: 5px solid #ccc; text-align: center; color: #888;'>
                📊 OI Data: Not Available
            </div>
            """, unsafe_allow_html=True)

        if row.get('sector'):
            st.markdown(f'<div class="filter-box"><b>Sector: {row["sector"]}</b></div>', unsafe_allow_html=True)

        if row.get('news_impact') and row['news_impact'] != "NO DATA":
            news_sentiment = "POSITIVE" if row['news_impact'] == "SUPPORTS" else ("NEGATIVE" if row['news_impact'] == "CONTRADICTS" else "NEUTRAL")
            news_class = "news-positive" if news_sentiment == "POSITIVE" else ("news-negative" if news_sentiment == "NEGATIVE" else "news-neutral")
            st.markdown(f'<div class="{news_class}"><b>News Impact: {row["news_impact"]}</b></div>', unsafe_allow_html=True)
            if row.get('news_data') and row['news_data'].get('articles'):
                with st.expander("📰 View News Details"):
                    for article in row['news_data']['articles'][:3]:
                        sentiment_emoji = "🟢" if article.get('sentiment') == "POSITIVE" else ("🔴" if article.get('sentiment') == "NEGATIVE" else "⚪")
                        st.markdown(f"{sentiment_emoji} **{article.get('title', 'No title')}**")
                        st.caption(f"Source: {article.get('publisher', 'Unknown')} | Score: {article.get('score', 0)}")
                        st.markdown("---")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f'<div class="filter-box"><b>Trade</b><br>Entry: <b>Rs{row["entry_price"]}</b><br>SL: <span style="color:red">Rs{row["stop_loss"]}</span><br>Target: <span style="color:green">Rs{row["target"]}</span><br>Risk: Rs{row["risk"]} ({row["risk_percent"]}%)<br>R:R = 1:{risk_reward}</div>', unsafe_allow_html=True)
        with col2:
            st.markdown(f'<div class="filter-box"><b>Tech</b><br>VWAP: Rs{row["vwap"] if row.get("vwap") else "N/A"}<br>ATR: Rs{row.get("atr", "N/A")}<br>EMA20: Rs{row["ema20"] if row.get("ema20") else "N/A"}</div>', unsafe_allow_html=True)

        if row.get('oi_signal') and row['oi_signal'] != "NEUTRAL":
            st.markdown(f'<div class="filter-box"><b>OI Analysis</b><br>{row.get("oi_buildup", "N/A")}<br>Signal: {row["oi_signal"]}</div>', unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("**📋 Filter Analysis:**")

        filter_details = row.get('filter_details', [])
        pass_count = 0
        fail_count = 0

        for item in filter_details:
            if isinstance(item, list) and len(item) >= 3:
                filter_name, passed, detail = item[0], item[1], item[2]
            elif isinstance(item, tuple) and len(item) >= 3:
                filter_name, passed, detail = item[0], item[1], item[2]
            else:
                continue

            if passed:
                pass_count += 1
                st.markdown(f"<div style='background: linear-gradient(90deg, #00ff0015 0%, transparent 100%); padding: 6px 12px; margin: 2px 0; border-radius: 6px; border-left: 3px solid #00ff88; font-size: 13px;'><span style='color:#00ff88; font-weight:bold;'>✅</span> <b>{filter_name}</b> <span style='color:#888; float:right;'>{detail}</span></div>", unsafe_allow_html=True)
            else:
                fail_count += 1
                st.markdown(f"<div style='background: linear-gradient(90deg, #ff000015 0%, transparent 100%); padding: 6px 12px; margin: 2px 0; border-radius: 6px; border-left: 3px solid #ff4060; font-size: 13px;'><span style='color:#ff4060; font-weight:bold;'>❌</span> <b>{filter_name}</b> <span style='color:#888; float:right;'>{detail}</span></div>", unsafe_allow_html=True)

        st.markdown(f"<div style='text-align: center; padding: 8px; margin-top: 8px; background: #f0f2f6; border-radius: 8px; font-size: 13px;'><b>Summary:</b> <span style='color:#00ff88; font-weight:bold;'>{pass_count} ✓</span> | <span style='color:#ff4060; font-weight:bold;'>{fail_count} ✗</span> | <b>Accuracy: {acc}%</b></div>", unsafe_allow_html=True)
def _display_signal_card(row, sig, card_class, acc_class):
    acc = row.get('accuracy', 0)
    news_badge = ""
    if row.get('news_impact') and row['news_impact'] != "NO DATA":
        if row['news_impact'] == "SUPPORTS":
            news_badge = " 🟢"
        elif row['news_impact'] == "CONTRADICTS":
            news_badge = " 🔴"
        else:
            news_badge = " 🟡"
    with st.expander(f"{sig} **{row.get('symbol', 'N/A')}** | Rs{row.get('current_price', 0)} | {acc}%{news_badge}"):
        st.markdown(f'<div class="signal-card {card_class}"><h2>{sig}</h2></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="accuracy-badge {acc_class}">{acc}% ({row["filters_passed"]}/{row["total_filters"]})</div>', unsafe_allow_html=True)
        if row.get('sector'):
            st.markdown(f'<div class="filter-box"><b>Sector: {row["sector"]}</b></div>', unsafe_allow_html=True)
        if row.get('news_impact') and row['news_impact'] != "NO DATA":
            news_sentiment = "POSITIVE" if row['news_impact'] == "SUPPORTS" else ("NEGATIVE" if row['news_impact'] == "CONTRADICTS" else "NEUTRAL")
            news_class = "news-positive" if news_sentiment == "POSITIVE" else ("news-negative" if news_sentiment == "NEGATIVE" else "news-neutral")
            st.markdown(f'<div class="{news_class}"><b>News Impact: {row["news_impact"]}</b></div>', unsafe_allow_html=True)
            if row.get('news_data') and row['news_data'].get('articles'):
                with st.expander("📰 View News Details"):
                    for article in row['news_data']['articles'][:3]:
                        sentiment_emoji = "🟢" if article.get('sentiment') == "POSITIVE" else ("🔴" if article.get('sentiment') == "NEGATIVE" else "⚪")
                        st.markdown(f"{sentiment_emoji} **{article.get('title', 'No title')}**")
                        st.caption(f"Source: {article.get('publisher', 'Unknown')} | Score: {article.get('score', 0)}")
                        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f'<div class="filter-box"><b>Trade</b><br>Entry: <b>Rs{row["entry_price"]}</b><br>SL: <span style="color:red">Rs{row["stop_loss"]}</span><br>Target: <span style="color:green">Rs{row["target"]}</span><br>Risk: Rs{row["risk"]} ({row["risk_percent"]}%)<br>R:R = 1:{risk_reward}</div>', unsafe_allow_html=True)
        with col2:
            st.markdown(f'<div class="filter-box"><b>Tech</b><br>VWAP: Rs{row["vwap"] if row.get("vwap") else "N/A"}<br>ATR: Rs{row.get("atr", "N/A")}<br>EMA20: Rs{row["ema20"] if row.get("ema20") else "N/A"}</div>', unsafe_allow_html=True)
        with col3:
            if row.get('oi_signal') and row['oi_signal'] != "NEUTRAL":
                st.markdown(f'<div class="filter-box"><b>OI</b><br>{row.get("oi_buildup", "N/A")}<br>Signal: {row["oi_signal"]}</div>', unsafe_allow_html=True)
        st.markdown("---")
        st.markdown("**📋 Filter Analysis:**")
        filter_details = row.get('filter_details', [])
        pass_count = 0
        fail_count = 0
        for item in filter_details:
            if isinstance(item, list) and len(item) >= 3:
                filter_name, passed, detail = item[0], item[1], item[2]
            elif isinstance(item, tuple) and len(item) >= 3:
                filter_name, passed, detail = item[0], item[1], item[2]
            else:
                continue
            if passed:
                pass_count += 1
                st.markdown(f"<div style='background: linear-gradient(90deg, #00ff0015 0%, transparent 100%); padding: 8px 15px; margin: 3px 0; border-radius: 8px; border-left: 4px solid #00ff88;'><span style='color:#00ff88; font-weight:bold;'>✅ PASS</span> <b>{filter_name}</b> — <span style='color:#888;'>{detail}</span></div>", unsafe_allow_html=True)
            else:
                fail_count += 1
                st.markdown(f"<div style='background: linear-gradient(90deg, #ff000015 0%, transparent 100%); padding: 8px 15px; margin: 3px 0; border-radius: 8px; border-left: 4px solid #ff4060;'><span style='color:#ff4060; font-weight:bold;'>❌ FAIL</span> <b>{filter_name}</b> — <span style='color:#888;'>{detail}</span></div>", unsafe_allow_html=True)
        st.markdown(f"<div style='text-align: center; padding: 10px; margin-top: 10px; background: #f0f2f6; border-radius: 10px;'><b>Summary:</b> <span style='color:#00ff88;'>{pass_count} PASSED</span> | <span style='color:#ff4060;'>{fail_count} FAILED</span> | <b>Accuracy: {acc}%</b></div>", unsafe_allow_html=True)

# ============================================
# MAIN LOGIC
# ============================================
if not refresh and saved_data and saved_data['results']:
    st.markdown(f'<div style="background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); color: white; padding: 15px; border-radius: 10px; text-align: center; margin-bottom: 20px;"><h3>Showing Last Saved Scan</h3><p>Last scanned on: <b>{saved_data["timestamp"]}</b> | Click "SCAN NOW" for fresh data</p></div>', unsafe_allow_html=True)
    if saved_data['sector_perf']:
        st.markdown("### Sector Performance (Saved)")
        sector_cols = st.columns(4)
        col_idx = 0
        for sector, data in saved_data['sector_perf'].items():
            trend = data.get('trend', 'NEUTRAL')
            change = data.get('change', 0)
            if trend in ["STRONG_UP", "UP"]:
                sec_class = "sector-strong"
            elif trend in ["STRONG_DOWN", "DOWN"]:
                sec_class = "sector-weak"
            else:
                sec_class = "sector-neutral"
            with sector_cols[col_idx % 4]:
                st.markdown(f'<div class="sector-card {sec_class}"><b>{sector}</b><br>{change:+.2f}%<br>{trend}</div>', unsafe_allow_html=True)
            col_idx += 1
    st.markdown("---")
    display_results(saved_data['results'], saved_data['sector_perf'])

elif refresh:
    st.subheader("Scanning (5-Filter ORB System)...")
    sector_perf = get_sector_performance()
    if sector_perf:
        st.markdown("### Sector Performance Today")
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
    # Fetch OI Spurts data first
    status_text = st.empty()
    status_text.text("Fetching OI Spurts data...")
    oi_spurts_data = fetch_oi_spurts_nse()
    if oi_spurts_data:
        st.success(f"✅ OI Spurts loaded: Top stock {oi_spurts_data[0]['symbol']} (+{oi_spurts_data[0]['oi_change_pct']:.1f}% OI)")
    else:
        st.warning("⚠️ OI Spurts data unavailable. Scanning without OI sorting.")

    progress_bar = st.progress(0)
    status_text = st.empty()
    results = []
    total_stocks = len(stock_list)
    for i, symbol in enumerate(stock_list):
        time.sleep(0.3)
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
                final_signal, confidence, oi_signal, oi_buildup, news_impact = get_final_signal(orb_result['signal'], orb_result['accuracy'], oi_data, news_data)
                if news_impact == "CONTRADICTS" and use_news:
                    continue
                if "BUY" in final_signal or "SELL" in final_signal:
                    result = {**orb_result, 'final_signal': final_signal, 'confidence': round(abs(confidence) * 100, 1), 'oi_signal': oi_signal, 'oi_buildup': oi_buildup, 'news_impact': news_impact, 'oi_data': oi_data, 'news_data': news_data}
                    results.append(result)
    progress_bar.empty()
    status_text.empty()
    # Add OI Spurts ranking and sort
    if oi_spurts_data and results:
        results = add_oi_spurts_to_results(results, oi_spurts_data)
        if results:
            st.info(f"📊 Sorted by OI: Top stock {results[0]['symbol']} with OI change {results[0].get('oi_change_pct', 0):+.1f}%")
    elif results:
        # Sort by accuracy only if no OI data
        results.sort(key=lambda x: (-x['accuracy'], x['symbol']))
        st.info("📊 Sorted by Accuracy (OI data unavailable)")

    settings = {'accuracy_mode': accuracy_mode, 'min_accuracy': min_accuracy, 'orb_minutes': orb_minutes, 'risk_reward': risk_reward, 'min_price': min_price, 'max_price': max_price, 'use_oi': use_oi, 'use_news': use_news}
    if results:
        save_scan_data(results, sector_perf, stock_list, settings)
        st.success(f"Scan complete! {len(results)} signals found. Data saved automatically.")
    else:
        save_scan_data([], sector_perf, stock_list, settings)
    display_results(results, sector_perf)

else:
    st.info("Welcome! Click SCAN NOW in the sidebar to start scanning. Your scan results will be automatically saved even if your PC goes to sleep!")

with st.expander("5-Filter System Explained"):
    st.markdown("""
    ### 5-Filter ORB System

    **Filter 1: ORB Breakout**
    - First 15-30 min range ke bahar nikla?
    - Momentum confirm

    **Filter 2: Volume**
    - Breakout mein volume spike hai?
    - 1.3x average volume minimum
    - Fakeout avoid karne ke liye

    **Filter 3: VWAP**
    - Price VWAP ke upar (BUY) / niche (SELL)?
    - Institutional bias confirm

    **Filter 4: EMA20**
    - Price EMA20 ke upar (BUY) / niche (SELL)?
    - Short-term trend direction

    **Filter 5: Gap + Spike Protection**
    - 2% gap up + 1.5% first 5-min spike = SKIP
    - 2% gap down + 1.5% first 5-min spike = SKIP
    - FOMO trap aur panic selling avoid karne ke liye

    ### Removed Filters
    - ❌ RSI (sir dard filter)
    - ❌ Previous Day High/Low
    - ❌ Price Action (Engulfing, Hammer, etc.)
    - ❌ 15m Multi-Timeframe
    - ❌ Sector Strength (optional mein hai)

    ### Signal Logic
    ```
    IF 5/5 filters pass -> STRONG BUY/SELL
    IF 4/5 filters pass -> BUY/SELL
    IF <4/5 filters pass -> SKIP
    ```
    """)

st.markdown("---")
st.markdown("""
<div style="text-align: center; color: gray; font-size: 12px;">
<b>Disclaimer:</b> Educational purposes only. Not financial advice.
<br><b>5-Filter ORB System | Gap+Spike Protection | Clean Setup</b>
<br><b>Secure Login Enabled | Auto-Save Enabled</b>
</div>
""", unsafe_allow_html=True)
