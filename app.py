import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import json
import os
import hashlib
import tempfile
import pytz
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# CONFIGURATION
# ============================================================
TEMP_DIR = tempfile.gettempdir()
DATA_FILE = os.path.join(TEMP_DIR, "scanner_data.json")
JOURNAL_FILE = os.path.join(TEMP_DIR, "journal.json")

IST = pytz.timezone('Asia/Kolkata')

def get_ist_now():
    return datetime.now(IST)

def get_ist_date():
    return datetime.now(IST).date()

# ============================================================
# PASSWORD PROTECTION
# ============================================================
USERS = {
    "akki":  "Ca@1809",
    "admin": "scanner123",
}

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'username' not in st.session_state:
    st.session_state.username = ""

def login(username, password):
    if username in USERS and USERS[username] == password:
        st.session_state.authenticated = True
        st.session_state.username = username
        return True
    return False

def logout():
    st.session_state.authenticated = False
    st.session_state.username = ""

# ============================================================
# DATA PERSISTENCE
# ============================================================
if 'saved_results' not in st.session_state:
    st.session_state.saved_results = None
    st.session_state.saved_timestamp = None
    st.session_state.saved_oi_list = None
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
                st.session_state.saved_results = data.get('results')
                st.session_state.saved_timestamp = data.get('timestamp')
                st.session_state.saved_oi_list = data.get('oi_list')
        except:
            pass

def save_scan_data(results, oi_list):
    try:
        data = {
            'results': results,
            'timestamp': get_ist_now().strftime('%Y-%m-%d %H:%M:%S'),
            'oi_list': oi_list
        }
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, default=str)
        st.session_state.saved_results = results
        st.session_state.saved_timestamp = data['timestamp']
        st.session_state.saved_oi_list = oi_list
        return True
    except Exception as e:
        st.error(f"Error saving data: {e}")
        return False

def load_scan_data():
    if st.session_state.saved_results:
        return {
            'results': st.session_state.saved_results,
            'timestamp': st.session_state.saved_timestamp,
            'oi_list': st.session_state.saved_oi_list
        }
    return None

def clear_saved_data():
    st.session_state.saved_results = None
    st.session_state.saved_timestamp = None
    st.session_state.saved_oi_list = None
    if os.path.exists(DATA_FILE):
        try:
            os.remove(DATA_FILE)
        except:
            pass

# ============================================================
# JOURNAL FUNCTIONS
# ============================================================
def load_journal():
    try:
        with open(JOURNAL_FILE, "r") as f:
            return json.load(f)
    except:
        return []

def save_journal(entries):
    with open(JOURNAL_FILE, "w") as f:
        json.dump(entries, f, indent=2)

# ============================================================
# NSE API FUNCTIONS (From Your Scanner)
# ============================================================
NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/", "Connection": "keep-alive",
}

def get_nse_session():
    session = requests.Session()
    session.headers.update(NSE_HEADERS)
    try:
        session.get("https://www.nseindia.com", timeout=10)
    except:
        pass
    return session

def get_oi_gainers():
    try:
        session = get_nse_session()
        url = "https://www.nseindia.com/api/live-analysis-oi-spurts-underlyings"
        response = session.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            items = []
            raw = data if isinstance(data, list) else data.get('data', [])
            for item in raw[:30]:
                sym = item.get('symbol', '')
                if not sym:
                    continue
                pchg = item.get('pchangeinOpenInterest', item.get('pChange', 0)) or 0
                prev_oi = item.get('prevOI', item.get('previousOI', 0)) or 0
                latest_oi = item.get('latestOI', item.get('openInterest', 0)) or 0
                chg_oi = item.get('changeinOpenInterest', item.get('changeInOpenInterest', 0)) or 0
                items.append({
                    'symbol': sym,
                    'oi_chg_pct': round((float(latest_oi) - float(prev_oi)) / float(prev_oi) * 100, 2)
                                  if float(prev_oi) > 0 else round(float(pchg), 2),
                    'prev_oi': int(prev_oi),
                    'latest_oi': int(latest_oi),
                    'chg_oi': int(chg_oi),
                })
            items.sort(key=lambda x: x['oi_chg_pct'], reverse=True)
            return items[:20]
    except:
        pass
    return []

# ============================================================
# TECHNICAL INDICATORS
# ============================================================
def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def calculate_vwap(df):
    try:
        df = df.copy()
        df['typical_price'] = (df['High'] + df['Low'] + df['Close']) / 3
        df['tp_volume'] = df['typical_price'] * df['Volume']
        df['cum_tp_vol'] = df['tp_volume'].cumsum()
        df['cum_vol'] = df['Volume'].cumsum()
        return df['cum_tp_vol'] / df['cum_vol']
    except:
        return None

def calculate_rsi(df, period=14):
    try:
        delta = df['Close'].diff()
        gain = delta.where(delta > 0, 0).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    except:
        return pd.Series([50] * len(df))

def calculate_atr(df, period=14):
    try:
        df = df.copy()
        df['tr1'] = df['High'] - df['Low']
        df['tr2'] = abs(df['High'] - df['Close'].shift())
        df['tr3'] = abs(df['Low'] - df['Close'].shift())
        df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
        return df['tr'].rolling(window=period).mean()
    except:
        return pd.Series([0] * len(df))

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

# ============================================================
# ORB ANALYSIS (From My Scanner)
# ============================================================
def analyze_orb_ultimate(symbol, orb_mins=15):
    try:
        df_5m = yf.download(symbol + ".NS", period="5d", interval="5m", progress=False)
        if len(df_5m) < 20:
            return None

        if isinstance(df_5m.columns, pd.MultiIndex):
            df_5m.columns = df_5m.columns.get_level_values(0)
        df_5m = df_5m.dropna()
        df_5m.reset_index(inplace=True)

        if 'Datetime' in df_5m.columns:
            df_5m.rename(columns={'Datetime': 'Date'}, inplace=True)

        df_5m['Date'] = pd.to_datetime(df_5m['Date'])
        today = get_ist_date()
        df_today = df_5m[df_5m['Date'].dt.date == today].copy()

        if df_today.empty or len(df_today) < 3:
            return None

        df_today = df_today.sort_values('Date')
        candles_needed = max(1, orb_mins // 5)
        opening_range = df_today.head(candles_needed)

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
            return None

        # Filters
        filters_passed = 1
        total_filters = 1
        filter_details = [("ORB Breakout", True, f"Price broke {base_signal}")]

        # Volume
        total_filters += 1
        avg_volume = df_today['Volume'].rolling(window=5).mean().iloc[-1]
        volume_ratio = current_candle['Volume'] / avg_volume if avg_volume > 0 else 0
        volume_pass = volume_ratio >= 1.3
        if volume_pass:
            filters_passed += 1
        filter_details.append((f"{'Pass' if volume_pass else 'Fail'} Volume", volume_pass, f"{volume_ratio:.1f}x"))

        # VWAP
        total_filters += 1
        vwap_series = calculate_vwap(df_today)
        vwap = vwap_series.iloc[-1] if vwap_series is not None else None
        if vwap:
            if base_signal == "BUY" and current_price > vwap:
                filters_passed += 1
                vwap_pass = True
            elif base_signal == "SELL" and current_price < vwap:
                filters_passed += 1
                vwap_pass = True
            else:
                vwap_pass = False
            filter_details.append((f"{'Pass' if vwap_pass else 'Fail'} VWAP", vwap_pass, f"Rs{vwap:.2f}"))

        # RSI
        total_filters += 1
        rsi = calculate_rsi(df_today).iloc[-1]
        if base_signal == "BUY" and rsi < 75:
            filters_passed += 1
            rsi_pass = True
        elif base_signal == "SELL" and rsi > 25:
            filters_passed += 1
            rsi_pass = True
        else:
            rsi_pass = False
        filter_details.append((f"{'Pass' if rsi_pass else 'Fail'} RSI", rsi_pass, f"{rsi:.1f}"))

        # Price Action
        total_filters += 1
        pa_signal, pa_strength = detect_price_action(df_today)
        if (base_signal == "BUY" and pa_signal == "BULLISH") or (base_signal == "SELL" and pa_signal == "BEARISH"):
            filters_passed += 1
            pa_pass = True
        else:
            pa_pass = False
        filter_details.append((f"{'Pass' if pa_pass else 'Fail'} Price Action", pa_pass, f"{pa_signal}"))

        # EMA
        total_filters += 1
        ema20 = ema(df_5m['Close'], 20).iloc[-1]
        if base_signal == "BUY" and current_price > ema20:
            filters_passed += 1
            ema_pass = True
        elif base_signal == "SELL" and current_price < ema20:
            filters_passed += 1
            ema_pass = True
        else:
            ema_pass = False
        filter_details.append((f"{'Pass' if ema_pass else 'Fail'} EMA20", ema_pass, f"Rs{ema20:.2f}"))

        accuracy = (filters_passed / total_filters) * 100 if total_filters > 0 else 0

        # ATR SL
        atr = calculate_atr(df_today).iloc[-1]
        if atr > 0:
            if base_signal == "BUY":
                atr_sl = entry_price - (1.5 * atr)
                stop_loss = max(stop_loss, atr_sl)
            else:
                atr_sl = entry_price + (1.5 * atr)
                stop_loss = min(stop_loss, atr_sl)

        risk = abs(entry_price - stop_loss)
        target = entry_price + (risk * 2.5) if base_signal == "BUY" else entry_price - (risk * 2.5)

        return {
            'orb_high': round(orb_high, 2),
            'orb_low': round(orb_low, 2),
            'signal': base_signal,
            'entry_price': round(entry_price, 2),
            'stop_loss': round(stop_loss, 2),
            'target': round(target, 2),
            'risk': round(risk, 2),
            'accuracy': round(accuracy, 1),
            'filters_passed': filters_passed,
            'total_filters': total_filters,
            'filter_details': filter_details,
            'rsi': round(rsi, 1),
            'vwap': round(vwap, 2) if vwap else None,
            'atr': round(atr, 2),
            'ema20': round(ema20, 2),
        }
    except:
        return None

# ============================================================
# MERGED ANALYSIS - OI + ORB
# ============================================================
def get_merged_signal(ticker, oi_info, orb_data):
    try:
        df = yf.download(ticker + ".NS", period="5d", interval="5m", progress=False)
        if len(df) < 20:
            return None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.dropna()

        today = pd.Timestamp.now().date()
        today_data = df[df.index.date == today]
        prev_data = df[df.index.date < today]

        if len(today_data) < 2:
            all_dates = sorted(df.index.date.unique())
            if len(all_dates) < 2:
                return None
            today_data = df[df.index.date == all_dates[-1]]
            prev_data = df[df.index.date == all_dates[-2]]

        if len(prev_data) == 0 or len(today_data) == 0:
            return None

        prev_close = float(prev_data['Close'].iloc[-1])
        today_open = float(today_data['Open'].iloc[0])
        cp = float(today_data['Close'].iloc[-1])
        chg = round(((cp - prev_close) / prev_close) * 100, 2)

        # Gap filter
        gap_pct = round(((today_open - prev_close) / prev_close) * 100, 2)
        if abs(gap_pct) >= 2.0:
            return None

        # VWAP
        v = today_data['Volume']
        p = (today_data['High'] + today_data['Low'] + today_data['Close']) / 3
        vwap = float((p * v).cumsum().iloc[-1] / v.cumsum().iloc[-1])

        # EMA
        ema9 = float(ema(df['Close'], 9).iloc[-1])
        ema21 = float(ema(df['Close'], 21).iloc[-1])

        # Volume ratio
        prev_avg_vol = float(prev_data['Volume'].mean())
        curr_vol = float(today_data['Volume'].iloc[-1])
        vol_ratio = round(curr_vol / prev_avg_vol, 1) if prev_avg_vol > 0 else 0.0

        # OI data
        oi_pct = oi_info.get('oi_chg_pct', 0)
        oi_up = oi_pct > 0
        price_up = chg > 0

        # OI Interpretation
        if oi_up and price_up:
            oi_interp = "LONG BUILD"
        elif oi_up and not price_up:
            oi_interp = "SHORT BUILD"
        elif not oi_up and price_up:
            oi_interp = "SHORT COVER"
        else:
            oi_interp = "LONG UNWIND"

        # ORB data
        orb_signal = orb_data.get('signal', 'NEUTRAL') if orb_data else 'NEUTRAL'
        orb_accuracy = orb_data.get('accuracy', 0) if orb_data else 0

        # MERGED SCORING
        score = 0

        # OI Spurt Score (0-30)
        if oi_pct > 5: score += 30
        elif oi_pct > 3: score += 25
        elif oi_pct > 1: score += 20
        elif oi_pct > 0: score += 10

        # ORB Score (0-30)
        if orb_signal == "BUY" and orb_accuracy >= 80: score += 30
        elif orb_signal == "BUY" and orb_accuracy >= 60: score += 20
        elif orb_signal == "SELL" and orb_accuracy >= 80: score += 0
        elif orb_signal == "SELL" and orb_accuracy >= 60: score += 10

        # Technical Score (0-40)
        if cp > vwap: score += 15
        if ema9 > ema21: score += 15
        if vol_ratio > 1.2: score += 10

        # Final Signal
        if score >= 80: signal = "STRONG BUY"
        elif score >= 60: signal = "BUY"
        elif score <= 20: signal = "STRONG SELL"
        elif score <= 40: signal = "SELL"
        else: signal = "WAIT"

        # SL/Target
        if "BUY" in signal:
            sl = round(cp * 0.993, 2)
            tgt = round(cp * 1.015, 2)
        elif "SELL" in signal:
            sl = round(cp * 1.007, 2)
            tgt = round(cp * 0.985, 2)
        else:
            sl = "-"
            tgt = "-"

        return {
            "STOCK": ticker,
            "OI SPURT %": f"{'+' if oi_pct >= 0 else ''}{oi_pct:.2f}%",
            "OI SIGNAL": oi_interp,
            "ORB": f"{orb_signal} ({orb_accuracy}%)" if orb_data else "NO BREAKOUT",
            "LTP": round(cp, 2),
            "CHG %": f"{'+' if chg >= 0 else ''}{chg}%",
            "SIGNAL": signal,
            "VWAP": "ABOVE" if cp > vwap else "BELOW",
            "EMA TREND": "BULLISH" if ema9 > ema21 else "BEARISH",
            "VOL RATIO": f"{vol_ratio}x",
            "STRENGTH": f"{score}%",
            "STOP LOSS": sl,
            "TARGET": tgt,
            "ORB_DATA": orb_data,
        }
    except:
        return None

# ============================================================
# CHART FUNCTIONS
# ============================================================
def get_candle_data(ticker, interval, period):
    try:
        df = yf.download(ticker + ".NS", period=period, interval=interval, progress=False)
        if df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.dropna()
        df['EMA9'] = ema(df['Close'], 9)
        df['EMA21'] = ema(df['Close'], 21)
        v = df['Volume']
        p = (df['High'] + df['Low'] + df['Close']) / 3
        df['VWAP'] = (p * v).cumsum() / v.cumsum()
        return df
    except:
        return None

def plot_candles(df, ticker, interval_label):
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        vertical_spacing=0.02, row_heights=[0.75, 0.25])
    fig.add_trace(go.Candlestick(
        x=df.index, open=df['Open'], high=df['High'],
        low=df['Low'], close=df['Close'], name="Price",
        increasing_line_color='#00ff88', decreasing_line_color='#ff4060',
        increasing_fillcolor='#00ff8855', decreasing_fillcolor='#ff406055',
    ), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA9'],
        line=dict(color='#ffc700', width=1.5), name='EMA 9'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA21'],
        line=dict(color='#ff6b6b', width=1.5), name='EMA 21'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['VWAP'],
        line=dict(color='#00d4ff', width=1.5, dash='dot'), name='VWAP'), row=1, col=1)
    colors = ['#00ff88' if float(df['Close'].iloc[i]) >= float(df['Open'].iloc[i])
              else '#ff4060' for i in range(len(df))]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'],
        marker_color=colors, name='Volume', opacity=0.6), row=2, col=1)
    fig.update_layout(
        title=dict(text=f"{ticker} — {interval_label}",
                   font=dict(size=16, color='#c8d8e8')),
        template="plotly_dark", paper_bgcolor='#080c12', plot_bgcolor='#0d1219',
        xaxis_rangeslider_visible=False, height=580,
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    font=dict(size=11), bgcolor='rgba(0,0,0,0)'),
        margin=dict(l=10, r=10, t=60, b=10),
        font=dict(family='JetBrains Mono')
    )
    fig.update_xaxes(showgrid=True, gridcolor='#1e2d3d', zeroline=False)
    fig.update_yaxes(showgrid=True, gridcolor='#1e2d3d', zeroline=False)
    return fig

# ============================================================
# STYLING FUNCTIONS
# ============================================================
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
        v = float(str(val).replace('%','').replace('+',''))
        if v > 0: return 'color:#00ff88;font-weight:700'
        if v < 0: return 'color:#ff4060;font-weight:700'
    except: pass
    return ''

def color_oi(val):
    try:
        v = float(str(val).replace('%','').replace('+',''))
        if v > 0: return 'color:#00ff88;font-weight:700'
        if v < 0: return 'color:#ff4060;font-weight:700'
    except: pass
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

# ============================================================
# PAGE CONFIG & LOGIN
# ============================================================
st.set_page_config(
    page_title="F&O Pro Scanner - Merged",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Syne:wght@700;800&display=swap');
html, body, [class*="css"] {
    font-family: 'JetBrains Mono', monospace !important;
    background-color: #080c12 !important;
    color: #c8d8e8 !important;
}
.main { background-color: #080c12 !important; }
section[data-testid="stSidebar"] { background-color: #0d1219 !important; }
#MainMenu, footer, header { visibility: hidden; }
.top-header {
    background: linear-gradient(135deg, #0d1a26, #091520);
    border-bottom: 1px solid #1e2d3d;
    padding: 18px 28px;
    border-radius: 0 0 12px 12px;
    margin-bottom: 20px;
}
.logo-text {
    font-family: 'Syne', sans-serif !important;
    font-size: 2rem;
    font-weight: 800;
    background: linear-gradient(90deg, #00d4ff, #00ff88);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    letter-spacing: 3px;
}
.logo-sub {
    font-size: 10px;
    color: #3a5a7a;
    letter-spacing: 4px;
    text-transform: uppercase;
    margin-top: -4px;
}
[data-testid="metric-container"] {
    background: linear-gradient(135deg, #0d1a26, #111820) !important;
    border: 1px solid #1e2d3d !important;
    border-radius: 10px !important;
    padding: 16px !important;
    box-shadow: 0 4px 20px rgba(0,0,0,0.3) !important;
}
[data-testid="stMetricLabel"] {
    font-size: 10px !important;
    letter-spacing: 2px !important;
    color: #6a8aaa !important;
    text-transform: uppercase !important;
}
[data-testid="stMetricValue"] {
    font-size: 1.6rem !important;
    font-weight: 700 !important;
    color: #00d4ff !important;
}
.stButton > button {
    background: linear-gradient(90deg, #00d4ff22, #00ff8822) !important;
    color: #00d4ff !important;
    font-weight: 700 !important;
    font-size: 13px !important;
    border-radius: 8px !important;
    padding: 10px 28px !important;
    border: 1px solid #00d4ff44 !important;
    letter-spacing: 1px !important;
    transition: all 0.2s !important;
    font-family: 'JetBrains Mono', monospace !important;
}
.stButton > button:hover {
    background: linear-gradient(90deg, #00d4ff, #00ff88) !important;
    color: #000 !important;
    border-color: transparent !important;
}
.stTabs [data-baseweb="tab-list"] {
    background: #0d1219 !important;
    border-bottom: 1px solid #1e2d3d !important;
    gap: 4px !important;
    padding: 0 8px !important;
    border-radius: 8px 8px 0 0 !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    color: #6a8aaa !important;
    border-radius: 6px 6px 0 0 !important;
    padding: 10px 20px !important;
    font-size: 12px !important;
    font-weight: 600 !important;
    letter-spacing: 1px !important;
    border: none !important;
}
.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, #00d4ff15, #00ff8815) !important;
    color: #00d4ff !important;
    border-bottom: 2px solid #00d4ff !important;
}
.stTextInput > div > div > input,
.stNumberInput > div > div > input,
.stTextArea > div > div > textarea,
.stSelectbox > div > div {
    background-color: #0d1219 !important;
    border: 1px solid #1e2d3d !important;
    border-radius: 8px !important;
    color: #c8d8e8 !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 12px !important;
}
.stDataFrame { border: 1px solid #1e2d3d !important; border-radius: 10px !important; overflow: hidden !important; }
.stProgress > div > div > div { background: linear-gradient(90deg, #00d4ff, #00ff88) !important; border-radius: 4px !important; }
.stSpinner > div { border-top-color: #00d4ff !important; }
hr { border-color: #1e2d3d !important; }
.section-header {
    font-family: 'Syne', sans-serif !important;
    font-size: 1.1rem;
    font-weight: 700;
    color: #00d4ff;
    letter-spacing: 2px;
    text-transform: uppercase;
    border-left: 3px solid #00d4ff;
    padding-left: 10px;
    margin: 16px 0 12px 0;
}
.login-container {
    max-width: 400px;
    margin: 80px auto;
    background: linear-gradient(135deg, #0d1a26, #111820);
    border: 1px solid #1e2d3d;
    border-radius: 16px;
    padding: 40px;
    text-align: center;
}
label {
    color: #6a8aaa !important;
    font-size: 11px !important;
    letter-spacing: 1px !important;
    text-transform: uppercase !important;
}
</style>
""", unsafe_allow_html=True)

# Login
if not st.session_state.authenticated:
    st.markdown("""
    <div class="login-container">
        <div style="font-family:'Syne',sans-serif;font-size:1.5rem;font-weight:800;
                    background:linear-gradient(90deg,#00d4ff,#00ff88);
                    -webkit-background-clip:text;-webkit-text-fill-color:transparent;">
            📈 F&O PRO SCANNER
        </div>
        <div style="color:#3a5a7a;font-size:10px;letter-spacing:3px;margin-bottom:24px;">NSE · INTRADAY · LIVE · MERGED</div>
    </div>
    """, unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div style="background:#0d1219;border:1px solid #1e2d3d;border-radius:12px;padding:28px;">', unsafe_allow_html=True)
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Login", use_container_width=True):
            if login(username, password):
                st.success("Login successful!")
                st.rerun()
            else:
                st.error("Wrong Username or Password!")
        st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# ============================================================
# MAIN APP
# ============================================================
now_str = get_ist_now().strftime("%d %b %Y · %H:%M:%S IST")

st.markdown(f"""
<div class="top-header">
  <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;">
    <div>
      <div class="logo-text">📈 F&O PRO SCANNER</div>
      <div class="logo-sub">NSE · Intraday · Live OI Spurts + ORB Breakout + EMA + VWAP</div>
    </div>
    <div style="display:flex;gap:16px;align-items:center;flex-wrap:wrap;">
      <div style="color:#3a5a7a;font-size:11px;">⏰ {now_str}</div>
      <div style="color:#6a8aaa;font-size:11px;">👤 {st.session_state.get('username','').upper()}</div>
      <div>
        <button onclick="window.location.reload()" style="background:#ff406020;border:1px solid #ff406040;color:#ff4060;padding:4px 12px;border-radius:4px;font-size:10px;cursor:pointer;">Logout</button>
      </div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #00d4ff22, #00ff8822); 
                padding: 15px; border-radius: 10px; color: #00d4ff; text-align: center; margin-bottom: 20px;
                border: 1px solid #00d4ff44;">
        <b>Welcome, {st.session_state.username}</b><br>
        <small>{get_ist_now().strftime('%d %b %Y | %H:%M')}</small>
    </div>
    """, unsafe_allow_html=True)

    if st.button("Logout", use_container_width=True):
        logout()
        st.rerun()

    st.markdown("---")
    st.markdown("### Scanner Settings")

    orb_minutes = st.slider("ORB Opening Range (minutes)", 5, 30, 15)
    min_accuracy = st.slider("Min ORB Accuracy %", 50, 100, 60)

    st.markdown("---")

    if st.button("Clear Saved Data", use_container_width=True):
        clear_saved_data()
        st.sidebar.success("Saved data cleared!")
        st.rerun()

    saved_data = load_scan_data()
    if saved_data and saved_data['timestamp']:
        st.markdown(f"""
        <div style="background:#00ff8815;border:1px solid #00ff8840;border-radius:8px;padding:10px;margin-top:10px;">
            <small>Last Scan: <b>{saved_data['timestamp']}</b><br>
            Signals: {len(saved_data['results']) if saved_data['results'] else 0}</small>
        </div>
        """, unsafe_allow_html=True)

# Tabs
tab1, tab2, tab3, tab4 = st.tabs(["  📡  MERGED SCANNER  ", "  📊  CHART VIEW  ", "  📓  TRADE JOURNAL  ", "  📋  ORB DETAILS  "])

# ============================================================
# TAB 1 - MERGED SCANNER
# ============================================================
with tab1:
    col_btn, col_info = st.columns([1, 3])
    with col_btn:
        scan_btn = st.button("🔍  SCAN MARKET", use_container_width=True)

    with col_info:
        st.markdown("""
        <div style="color:#6a8aaa;font-size:11px;padding:10px 0;">
        📊 <b>MERGED STRATEGY:</b> OI Spurt (Early Signal) + ORB Breakout (Confirmation) + EMA/VWAP Filters<br>
        <span style="color:#ffc700;">⚡ Gap Filter ON | Auto-Save ON | Sleep Mode Safe</span>
        </div>
        """, unsafe_allow_html=True)

    if scan_btn:
        with st.spinner("NSE se OI Spurts fetch ho rahe hain..."):
            oi_list = get_oi_gainers()

        if not oi_list:
            st.error("NSE OI data nahi mila — market band hai ya connection issue")
        else:
            st.markdown(f'<div class="section-header">📋 Top {len(oi_list)} OI Spurt Stocks + ORB Analysis</div>', unsafe_allow_html=True)

            # OI Preview
            oi_preview = pd.DataFrame([{
                'RANK': i+1,
                'SYMBOL': x['symbol'],
                'OI SPURT %': f"{'+' if x['oi_chg_pct'] >= 0 else ''}{x['oi_chg_pct']:.2f}%",
                'PREV OI': f"{x['prev_oi']:,}",
                'LATEST OI': f"{x['latest_oi']:,}",
            } for i, x in enumerate(oi_list)])

            with st.expander("📊 NSE OI Spurt Raw Data", expanded=False):
                st.dataframe(oi_preview, use_container_width=True, hide_index=True)

            # Merged Analysis
            results = []
            skipped = []
            progress = st.progress(0)
            status = st.empty()

            for i, oi_item in enumerate(oi_list):
                ticker = oi_item['symbol']
                status.markdown(
                    f'<div style="color:#6a8aaa;font-size:11px;">'
                    f'⏳ SCANNING: <span style="color:#00d4ff;font-weight:700;">{ticker}</span> '
                    f'({i+1}/{len(oi_list)})</div>',
                    unsafe_allow_html=True
                )

                # Get ORB data
                orb_data = analyze_orb_ultimate(ticker + ".NS", orb_minutes)

                # Get merged signal
                merged_data = get_merged_signal(ticker, oi_item, orb_data)

                if merged_data:
                    results.append(merged_data)
                else:
                    skipped.append(ticker)

                progress.progress((i + 1) / len(oi_list))

            status.empty()
            progress.empty()

            if skipped:
                st.markdown(
                    f'<div style="background:#ffc70015;border:1px solid #ffc70040;border-radius:8px;'
                    f'padding:10px;color:#ffc700;font-size:11px;margin-bottom:12px;">'
                    f'⚡ Skipped: {", ".join(skipped)}</div>',
                    unsafe_allow_html=True
                )

            if results:
                save_scan_data(results, oi_list)

                df_result = pd.DataFrame(results)
                st.session_state['scan_results'] = results
                st.session_state['oi_list'] = oi_list

                buy_c = len(df_result[df_result['SIGNAL'].str.contains('BUY')])
                sell_c = len(df_result[df_result['SIGNAL'].str.contains('SELL')])
                wait_c = len(df_result[df_result['SIGNAL'].str.contains('WAIT')])

                c1, c2, c3, c4, c5 = st.columns(5)
                c1.metric("Total Found", len(df_result))
                c2.metric("Strong Buy", buy_c)
                c3.metric("Sell", sell_c)
                c4.metric("Wait", wait_c)
                c5.metric("Scanned At", get_ist_now().strftime("%H:%M:%S"))

                st.markdown('<div class="section-header">📈 Merged Results — OI + ORB + Technicals</div>', unsafe_allow_html=True)

                f1, f2 = st.columns([1, 3])
                show_filter = f1.selectbox("Filter", ["All", "Strong Buy", "Buy", "Sell", "Wait"])

                df_show = df_result.copy()
                if show_filter != "All":
                    df_show = df_show[df_show['SIGNAL'].str.contains(show_filter.upper().replace(' ', ' '))]

                # Display columns
                display_cols = ['STOCK', 'OI SPURT %', 'OI SIGNAL', 'ORB', 'LTP', 'CHG %', 'SIGNAL', 
                               'VWAP', 'EMA TREND', 'VOL RATIO', 'STRENGTH', 'STOP LOSS', 'TARGET']

                styled = (
                    df_show[display_cols].style
                    .map(color_oi, subset=['OI SPURT %'])
                    .map(color_oi_interp, subset=['OI SIGNAL'])
                    .map(color_signal, subset=['SIGNAL'])
                    .map(color_strength, subset=['STRENGTH'])
                    .map(color_ema, subset=['EMA TREND'])
                    .map(color_vwap, subset=['VWAP'])
                    .map(color_chg, subset=['CHG %'])
                    .set_properties(**{
                        'background-color': '#0d1219',
                        'color': '#c8d8e8',
                        'border-color': '#1e2d3d',
                        'font-size': '12px',
                    })
                )

                st.dataframe(styled, use_container_width=True, height=520)

                csv = df_result.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 CSV Download",
                    data=csv,
                    file_name=f"merged_scan_{get_ist_now().strftime('%d%m%Y_%H%M')}.csv",
                    mime='text/csv',
                )
            else:
                st.warning("Koi signal nahi mila")

    elif 'scan_results' in st.session_state:
        st.info("💡 Pichli scan ke results dikh rahe hain")
        df_result = pd.DataFrame(st.session_state['scan_results'])
        styled = (
            df_result.style
            .map(color_oi, subset=['OI SPURT %'])
            .map(color_oi_interp, subset=['OI SIGNAL'])
            .map(color_signal, subset=['SIGNAL'])
            .map(color_strength, subset=['STRENGTH'])
        )
        st.dataframe(styled, use_container_width=True, height=520)

# ============================================================
# TAB 2 - CHART VIEW
# ============================================================
with tab2:
    st.markdown('<div class="section-header">📊 Candlestick Chart — EMA + VWAP</div>', unsafe_allow_html=True)

    col_a, col_b, col_c = st.columns([2, 1, 1])
    with col_a:
        chart_ticker = st.text_input("Stock Symbol", value="RELIANCE", placeholder="e.g. SBIN, TCS").upper()
    with col_b:
        timeframe = st.selectbox("Timeframe", ["5 Min", "15 Min", "1 Hour"])
    with col_c:
        st.markdown("<br>", unsafe_allow_html=True)
        load_btn = st.button("Load Chart", use_container_width=True)

    interval_map = {"5 Min": ("5m", "5d"), "15 Min": ("15m", "5d"), "1 Hour": ("1h", "30d")}

    if load_btn:
        interval, period = interval_map[timeframe]
        with st.spinner(f"Loading {chart_ticker}..."):
            df_chart = get_candle_data(chart_ticker, interval, period)
        if df_chart is not None and len(df_chart) > 5:
            fig = plot_candles(df_chart, chart_ticker, timeframe)
            st.plotly_chart(fig, use_container_width=True)
            last = df_chart.iloc[-1]
            prev = df_chart.iloc[-2]
            chg_val = round(float(last['Close']) - float(prev['Close']), 2)
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("LTP", round(float(last['Close']), 2), delta=chg_val)
            m2.metric("VWAP", round(float(last['VWAP']), 2))
            m3.metric("EMA 9", round(float(last['EMA9']), 2))
            m4.metric("EMA 21", round(float(last['EMA21']), 2))
        else:
            st.error("Data nahi mila")

# ============================================================
# TAB 3 - TRADE JOURNAL
# ============================================================
with tab3:
    st.markdown('<div class="section-header">📓 Trade Journal</div>', unsafe_allow_html=True)

    with st.expander("Add Trade", expanded=False):
        j1, j2, j3 = st.columns(3)
        j_date = j1.date_input("Date", datetime.now())
        j_stock = j2.text_input("Stock", placeholder="RELIANCE")
        j_type = j3.selectbox("Type", ["BUY", "SELL"])
        j4, j5, j6 = st.columns(3)
        j_entry = j4.number_input("Entry", min_value=0.0, format="%.2f")
        j_sl = j5.number_input("SL", min_value=0.0, format="%.2f")
        j_target = j6.number_input("Target", min_value=0.0, format="%.2f")
        j7, j8 = st.columns(2)
        j_qty = j7.number_input("Qty", min_value=1, value=1)
        j_status = j8.selectbox("Status", ["OPEN", "HIT TARGET", "HIT SL", "EXITED"])
        j_notes = st.text_area("Notes")

        if st.button("Save Entry", use_container_width=True):
            if j_stock:
                entries = load_journal()
                pnl = 0
                if j_status != "OPEN":
                    if j_type == "BUY":
                        exit_price = j_target if j_status == "HIT TARGET" else j_sl
                    else:
                        exit_price = j_sl if j_status == "HIT TARGET" else j_target
                    pnl = round((exit_price - j_entry) * j_qty if j_type == "BUY" else (j_entry - exit_price) * j_qty, 2)
                entries.append({
                    "date": str(j_date), "stock": j_stock.upper(),
                    "type": j_type, "entry": j_entry, "sl": j_sl,
                    "target": j_target, "qty": j_qty,
                    "status": j_status, "pnl": pnl, "notes": j_notes
                })
                save_journal(entries)
                st.success(f"{j_stock.upper()} saved!")
            else:
                st.error("Stock name daalo!")

    st.markdown("---")
    entries = load_journal()
    if entries:
        df_journal = pd.DataFrame(entries)
        total_pnl = df_journal['pnl'].sum()
        wins = len(df_journal[df_journal['pnl'] > 0])
        losses = len(df_journal[df_journal['pnl'] < 0])
        win_rate = round((wins / max(wins + losses, 1)) * 100, 1)
        p1, p2, p3, p4 = st.columns(4)
        p1.metric("Total P&L", f"Rs{round(total_pnl,2)}")
        p2.metric("Wins", wins)
        p3.metric("Losses", losses)
        p4.metric("Win Rate", f"{win_rate}%")
        styled_j = df_journal.style.map(color_pnl, subset=['pnl']).map(color_status, subset=['status'])
        st.dataframe(styled_j, use_container_width=True, height=420)
        if st.button("Clear Journal"):
            save_journal([])
            st.rerun()
    else:
        st.info("No entries yet")

# ============================================================
# TAB 4 - ORB DETAILS
# ============================================================
with tab4:
    st.markdown('<div class="section-header">📋 ORB Breakout Details</div>', unsafe_allow_html=True)

    if 'scan_results' in st.session_state:
        results = st.session_state['scan_results']
        for r in results:
            if r.get('ORB_DATA'):
                orb = r['ORB_DATA']
                with st.expander(f"{r['STOCK']} — {r['SIGNAL']}"):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.markdown(f"""
                        <div style="background:#0d1219;border:1px solid #1e2d3d;border-radius:8px;padding:15px;">
                        <b>ORB Levels</b><br>
                        High: Rs{orb['orb_high']}<br>
                        Low: Rs{orb['orb_low']}<br>
                        Signal: {orb['signal']}<br>
                        Accuracy: {orb['accuracy']}%
                        </div>
                        """, unsafe_allow_html=True)
                    with col2:
                        st.markdown(f"""
                        <div style="background:#0d1219;border:1px solid #1e2d3d;border-radius:8px;padding:15px;">
                        <b>Trade</b><br>
                        Entry: Rs{orb['entry_price']}<br>
                        SL: Rs{orb['stop_loss']}<br>
                        Target: Rs{orb['target']}<br>
                        Risk: Rs{orb['risk']}
                        </div>
                        """, unsafe_allow_html=True)
                    with col3:
                        st.markdown(f"""
                        <div style="background:#0d1219;border:1px solid #1e2d3d;border-radius:8px;padding:15px;">
                        <b>Tech</b><br>
                        RSI: {orb['rsi']}<br>
                        VWAP: Rs{orb['vwap']}<br>
                        ATR: Rs{orb['atr']}<br>
                        EMA20: Rs{orb['ema20']}
                        </div>
                        """, unsafe_allow_html=True)

                    st.markdown("**Filters:**")
                    for name, passed, detail in orb['filter_details']:
                        color = "#00ff88" if passed else "#ff4060"
                        st.markdown(f'<span style="color:{color}">●</span> {name} — {detail}')
    else:
        st.info("Pehle scan karo — ORB details yahan dikhenge")

st.markdown("---")
st.markdown("""
<div style="text-align:center;color:#3a5a7a;font-size:11px;">
<b>F&O Pro Scanner — Merged Edition</b> | OI Spurts + ORB Breakout + EMA + VWAP<br>
Educational purposes only. Not financial advice.<br>
Secure Login | Auto-Save | Sleep Mode Safe
</div>
""", unsafe_allow_html=True)import streamlit as st
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
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# TIMEZONE SETUP - IST (Indian Standard Time)
# ============================================================
IST = pytz.timezone('Asia/Kolkata')

def get_ist_now():
    """Get current time in IST"""
    return datetime.now(IST)

def get_ist_date():
    """Get current date in IST"""
    return datetime.now(IST).date()

# ============================================================
# DHAN API SETUP
# ============================================================
# Dhan Security IDs for Nifty 50 stocks
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

# Dhan API endpoints
DHAN_BASE_URL = "https://api.dhan.co/v2"

def get_dhan_headers(access_token):
    return {
        'Content-Type': 'application/json',
        'access-token': access_token
    }

def fetch_dhan_intraday_data(security_id, access_token, interval="5", from_date=None, to_date=None):
    """Fetch intraday data from Dhan API"""
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
    """Fetch daily data from Dhan API"""
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
    """Extract symbol from .NS format"""
    return symbol_ns.replace('.NS', '')

def get_dhan_security_id(symbol_ns):
    """Get Dhan security ID for a symbol"""
    symbol = get_symbol_from_ns(symbol_ns)
    return DHAN_SECURITY_IDS.get(symbol, None)

# ============================================================
# NSEPYTHON LIBRARY SETUP
# ============================================================
# NSEPython is actively maintained and uses NSE's new APIs
# Install: pip install nsepythonserver (for cloud/server)

def fetch_nsepython_data(symbol, period="5d", interval="5m"):
    """Fetch data using NSEPython library"""
    try:
        from nsepythonserver import equity_intraday, equity_history
        from datetime import datetime, timedelta

        symbol_clean = symbol.replace('.NS', '')

        # For intraday data, use equity_intraday
        # For daily data, use equity_history
        if interval in ["1m", "5m", "15m", "30m", "60m"]:
            # Intraday data
            df = equity_intraday(symbol_clean, "EQ")

            if df is None or df.empty:
                return None

            # equity_intraday returns: timestamp, open, high, low, close, volume
            clean_df = pd.DataFrame()

            if 'timestamp' in df.columns:
                clean_df['Date'] = pd.to_datetime(df['timestamp'], unit='s')
            elif 'Timestamp' in df.columns:
                clean_df['Date'] = pd.to_datetime(df['Timestamp'], unit='s')

            for col in ['open', 'high', 'low', 'close', 'volume']:
                if col in df.columns:
                    clean_df[col.capitalize()] = pd.to_numeric(df[col], errors='coerce')

            return clean_df
        else:
            # Daily data
            end_date = get_ist_now().strftime('%d-%m-%Y')
            days_map = {"1d": 1, "5d": 5, "10d": 10, "30d": 30, "90d": 90}
            days = days_map.get(period, 5)
            start_date = (get_ist_now() - timedelta(days=days)).strftime('%d-%m-%Y')

            df = equity_history(symbol_clean, "EQ", start_date, end_date)

            if df is None or df.empty:
                return None

            clean_df = pd.DataFrame()

            if 'CH_TIMESTAMP' in df.columns:
                clean_df['Date'] = pd.to_datetime(df['CH_TIMESTAMP'])

            col_map = {
                'Open': ['CH_OPENING_PRICE', 'OPEN', 'open'],
                'High': ['CH_TRADE_HIGH_PRICE', 'HIGH', 'high'],
                'Low': ['CH_TRADE_LOW_PRICE', 'LOW', 'low'],
                'Close': ['CH_CLOSING_PRICE', 'CLOSE', 'close'],
                'Volume': ['CH_TOT_TRADED_QTY', 'VOLUME', 'volume']
            }

            for target_col, possible_names in col_map.items():
                for name in possible_names:
                    if name in df.columns:
                        clean_df[target_col] = pd.to_numeric(df[name], errors='coerce')
                        break

            return clean_df
    except ImportError:
        st.warning("NSEPython not installed. Install with: pip install nsepythonserver")
        return None
    except Exception as e:
        st.error(f"NSEPython Error for {symbol}: {e}")
        return None

# ============================================================
# STREAMLIT CLOUD COMPATIBLE PATHS
# ============================================================
TEMP_DIR = tempfile.gettempdir()
DATA_FILE = os.path.join(TEMP_DIR, "scanner_data.json")

# ============================================================
# PASSWORD PROTECTION
# ============================================================
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

# ============================================================
# DATA PERSISTENCE
# ============================================================
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

# ============================================================
# LOGIN PAGE
# ============================================================
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

# ============================================================
# MAIN APP
# ============================================================
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

st.markdown('<p class="main-header">Independent Sector Scanner</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Nifty Independent | Sector-Based | Stock-Specific Strength</p>', unsafe_allow_html=True)

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

st.sidebar.header("Scanner Settings")

# ============================================================
# DATA SOURCE SELECTION
# ============================================================
st.sidebar.subheader("Data Source")
data_source = st.sidebar.radio(
    "Select Data Provider",
    [
        "Yahoo Finance (Free, 15min delay)",
        "NSEPython (Free, NSE Direct)",
        "Dhan API (Real-time, requires API key)"
    ]
)

dhan_access_token = ""
if "NSEPython" in data_source:
    st.sidebar.markdown("---")
    st.sidebar.markdown("### NSEPython Setup")
    st.sidebar.info("NSEPython fetches data directly from NSE India. No API key needed!")
    st.sidebar.caption("Install: pip install nsepythonserver")
    dhan_access_token = ""

elif "Dhan" in data_source:
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Dhan API Setup")

    # Step 1: Generate Token
    st.sidebar.markdown("**Step 1:** [Click here to generate token](https://web.dhan.co/dhanhq)")
    st.sidebar.caption("Login → DhanHQ Trading APIs → Generate Access Token → Copy")

    # Step 2: Paste Token
    st.sidebar.markdown("**Step 2:** Paste your token below")
    dhan_access_token = st.sidebar.text_input(
        "Dhan Access Token",
        type="password",
        placeholder="Paste token here and press Enter",
        help="Token expires in 24 hours. Generate a new one daily."
    )

    # Show token status
    if dhan_access_token:
        st.sidebar.success("Token saved for this session!")
        st.sidebar.caption("Token will be lost if you refresh the page. That's normal.")
    else:
        st.sidebar.warning("Please paste your Dhan Access Token above")

    st.sidebar.markdown("---")
    st.sidebar.info("Token expires every 24 hours. Generate a new one each morning before market opens.")


stock_options = {
    "Nifty 50": ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS", "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS", "LT.NS", "AXISBANK.NS", "ASIANPAINT.NS", "MARUTI.NS", "TITAN.NS", "SUNPHARMA.NS", "BAJFINANCE.NS", "WIPRO.NS", "ULTRACEMCO.NS", "NESTLEIND.NS", "POWERGRID.NS", "NTPC.NS", "TATASTEEL.NS", "M&M.NS", "HCLTECH.NS", "TECHM.NS", "INDUSINDBK.NS", "GRASIM.NS", "ADANIENT.NS", "CIPLA.NS", "SBILIFE.NS", "BAJAJFINSV.NS", "BRITANNIA.NS", "APOLLOHOSP.NS", "ONGC.NS", "EICHERMOT.NS", "TATAMOTORS.NS", "DIVISLAB.NS", "HDFCLIFE.NS", "COALINDIA.NS", "JSWSTEEL.NS", "HEROMOTOCO.NS", "BPCL.NS", "DRREDDY.NS", "ADANIPORTS.NS", "HINDALCO.NS", "UPL.NS", "SHREECEM.NS", "BAJAJ-AUTO.NS", "TATACONSUM.NS"],
    "Nifty Next 50": ["BERGEPAINT.NS", "CHOLAFIN.NS", "DABUR.NS", "GODREJCP.NS", "HAVELLS.NS", "ICICIPRULI.NS", "INDIGO.NS", "JINDALSTEL.NS", "LICI.NS", "LODHA.NS", "MCDOWELL-N.NS", "MOTHERSON.NS", "NAUKRI.NS", "PIDILITIND.NS", "POLYCAB.NS", "SAMMAANCAP.NS", "SIEMENS.NS", "SRF.NS", "TORNTPHARM.NS", "TVSMOTOR.NS", "ABB.NS", "ACC.NS", "AMBUJACEM.NS", "AUROPHARMA.NS", "BANDHANBNK.NS", "BANKBARODA.NS", "BEL.NS", "BHEL.NS", "CANBK.NS", "COLPAL.NS", "CONCOR.NS", "CUMMINSIND.NS", "DMART.NS", "GAIL.NS", "GODREJPROP.NS", "HAL.NS", "HINDPETRO.NS", "IDBI.NS", "IDFCFIRSTB.NS", "INDUSTOWER.NS", "IOB.NS", "IRCTC.NS", "JUBLFOOD.NS", "L&TFH.NS", "LUPIN.NS", "MARICO.NS", "MUTHOOTFIN.NS", "NMDC.NS", "OBEROIRLTY.NS", "PFC.NS"],
    "Nifty Midcap 100": ["ABBOTINDIA.NS", "ALKEM.NS", "APLAPOLLO.NS", "ASTRAL.NS", "ATUL.NS", "BATAINDIA.NS", "BHARATFORG.NS", "BIKAJI.NS", "BLUESTARCO.NS", "BSOFT.NS", "CGPOWER.NS", "CHAMBLFERT.NS", "COFORGE.NS", "COROMANDEL.NS", "CREDITACC.NS", "CROMPTON.NS", "CYIENT.NS", "DALBHARAT.NS", "DEEPAKNTR.NS", "DELHIVERY.NS", "DIXON.NS", "ESCORTS.NS", "EXIDEIND.NS", "FEDERALBNK.NS", "GLAND.NS", "GLAXO.NS", "GLENMARK.NS", "GNFC.NS", "GODREJIND.NS", "GUJGASLTD.NS", "HAPPSTMNDS.NS", "HINDCOPPER.NS", "HINDZINC.NS", "HUDCO.NS", "IIFL.NS", "INDIAMART.NS", "INDIANB.NS", "IPCALAB.NS", "JBCHEPHARM.NS", "JSL.NS", "KEI.NS", "KPITTECH.NS", "LALPATHLAB.NS", "LAURUSLABS.NS", "LINDEINDIA.NS", "LTTS.NS", "M&MFIN.NS", "MANAPPURAM.NS", "MAXHEALTH.NS", "METROBRAND.NS"],
    "Bank Nifty": ["HDFCBANK.NS", "ICICIBANK.NS", "KOTAKBANK.NS", "AXISBANK.NS", "SBIN.NS", "INDUSINDBK.NS", "BANDHANBNK.NS", "FEDERALBNK.NS", "IDFCFIRSTB.NS", "PNB.NS", "BANKBARODA.NS", "CANBK.NS", "UNIONBANK.NS", "AUBANK.NS", "RBLBANK.NS"],
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

st.sidebar.subheader("Accuracy Mode")
accuracy_mode = st.sidebar.selectbox("Select Mode", ["Conservative (80%+)", "Balanced (70-80%)", "Aggressive (60-70%)"])
min_accuracy = {"Conservative (80%+)": 80, "Balanced (70-80%)": 70, "Aggressive (60-70%)": 60}[accuracy_mode]

st.sidebar.subheader("Advanced Filters")
use_sector = st.sidebar.checkbox("Sector Strength Filter", value=True)
use_oi = st.sidebar.checkbox("OI Buildup Analysis", value=True)
use_news = st.sidebar.checkbox("News Sentiment", value=True)
use_multi_tf = st.sidebar.checkbox("Multi-Timeframe", value=True)
use_vwap = st.sidebar.checkbox("VWAP", value=True)
use_atr_sl = st.sidebar.checkbox("Smart ATR SL", value=True)
use_pa = st.sidebar.checkbox("Price Action", value=True)

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
- Nifty Independent
- Sector Based
- Expected Win Rate: {min_accuracy}-{min_accuracy+10}%""")

@st.cache_data(ttl=300)
def fetch_data(symbol, period="5d", interval="5m", data_source="Yahoo Finance", access_token=""):
    try:
        # Use NSEPython if selected
        if "NSEPython" in data_source:
            df = fetch_nsepython_data(symbol, period, interval)
            if df is not None and not df.empty:
                return df
            else:
                st.warning(f"NSEPython failed for {symbol}, falling back to Yahoo Finance")

        # Use Dhan API if selected and token is provided
        if "Dhan" in data_source and access_token:
            security_id = get_dhan_security_id(symbol)
            if security_id:
                # Map interval
                interval_map = {"1m": "1", "5m": "5", "15m": "15", "30m": "25", "60m": "60"}
                dhan_interval = interval_map.get(interval, "5")

                # Calculate from/to dates based on period
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

        # Fallback to Yahoo Finance
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
        if (last['Close'] > last['Open'] and prev['Close'] > prev['Open'] and prev2['Close'] > prev2['Open'] and last['Close'] > prev['Close'] > prev2['Close']):
            patterns.append(("Three White Soldiers", 3))
        if (last['Close'] < last['Open'] and prev['Close'] < prev['Open'] and prev2['Close'] < prev2['Open'] and last['Close'] < prev['Close'] < prev2['Close']):
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

def analyze_orb_ultimate(symbol, sector_perf, orb_mins=15):
    df_5m = fetch_data(symbol, period="5d", interval="5m", data_source=data_source, access_token=dhan_access_token)
    df_15m = fetch_data(symbol, period="10d", interval="15m", data_source=data_source, access_token=dhan_access_token)
    df_daily = fetch_data(symbol, period="30d", interval="1d", data_source=data_source, access_token=dhan_access_token)
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
    filters_passed = 1
    total_filters = 1
    filter_details = []
    filter_details.append(("ORB Breakout", True, f"Price broke {base_signal}"))
    total_filters += 1
    try:
        avg_volume = df_today['Volume'].rolling(window=5).mean().iloc[-1]
        volume_ratio = current_candle['Volume'] / avg_volume if avg_volume > 0 else 0
        volume_pass = volume_ratio >= 1.3
        if volume_pass:
            filters_passed += 1
        filter_details.append((f"{'Pass' if volume_pass else 'Fail'} Volume", volume_pass, f"{volume_ratio:.1f}x"))
    except:
        filter_details.append(("Fail Volume", False, "Error"))
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
        filter_details.append((f"{'Pass' if vwap_pass else 'Fail'} VWAP", vwap_pass, f"Rs{vwap:.2f}"))
    else:
        filter_details.append(("Fail VWAP", False, "Error"))
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
    filter_details.append((f"{'Pass' if rsi_pass else 'Fail'} RSI", rsi_pass, f"{rsi:.1f}"))
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
                filter_details.append((f"{'Pass' if tf_pass else 'Fail'} 15m TF", tf_pass, f"H:Rs{tf_high:.0f}"))
            else:
                filter_details.append(("Fail 15m TF", False, "No data"))
        except:
            filter_details.append(("Fail 15m TF", False, "Error"))
    total_filters += 1
    pa_signal, pa_strength = detect_price_action(df_today)
    if (base_signal == "BUY" and pa_signal == "BULLISH") or (base_signal == "SELL" and pa_signal == "BEARISH"):
        filters_passed += 1
        pa_pass = True
    else:
        pa_pass = False
    filter_details.append((f"{'Pass' if pa_pass else 'Fail'} Price Action", pa_pass, f"{pa_signal}"))
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
        filter_details.append((f"{'Pass' if ema_pass else 'Fail'} EMA20", ema_pass, f"Rs{ema20:.2f}"))
    else:
        filter_details.append(("Fail EMA20", False, "Error"))
    if df_daily is not None and len(df_daily) >= 2:
        total_filters += 1
        try:
            prev_day = df_daily.iloc[-2]
            prev_high = prev_day['High']
            prev_low = prev_day['Low']
            if base_signal == "BUY" and current_price > prev_high:
                filters_passed += 1
                prev_pass = True
                prev_detail = f"Above Rs{prev_high:.2f}"
            elif base_signal == "SELL" and current_price < prev_low:
                filters_passed += 1
                prev_pass = True
                prev_detail = f"Below Rs{prev_low:.2f}"
            else:
                prev_pass = False
                prev_detail = f"H:Rs{prev_high:.0f} L:Rs{prev_low:.0f}"
            filter_details.append((f"{'Pass' if prev_pass else 'Fail'} Prev Day", prev_pass, prev_detail))
        except:
            filter_details.append(("Fail Prev Day", False, "Error"))
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
            else:
                sector_pass = False
        else:
            if sector_trend in ["STRONG_DOWN", "DOWN"]:
                filters_passed += 1
                sector_pass = True
            else:
                sector_pass = False
        filter_details.append((f"{'Pass' if sector_pass else 'Fail'} Sector ({sector})", sector_pass, f"{sector_change:+.2f}%"))
    else:
        filter_details.append(("Sector", False, "N/A"))
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
        'sector': sector,
        'sector_change': sector_perf.get(sector, {}).get('change', 0) if sector_perf else 0,
        'day_high': round(df_today['High'].max(), 2),
        'day_low': round(df_today['Low'].min(), 2),
        'rsi': round(rsi, 1),
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
    if accuracy >= 85:
        if combined > 0.5:
            return "STRONG BUY", combined, oi_signal, oi_buildup, news_impact
        elif combined < -0.5:
            return "STRONG SELL", combined, oi_signal, oi_buildup, news_impact
    elif accuracy >= 70:
        if combined > 0:
            return "BUY", combined, oi_signal, oi_buildup, news_impact
        elif combined < 0:
            return "SELL", combined, oi_signal, oi_buildup, news_impact
    return "NEUTRAL", combined, oi_signal, oi_buildup, news_impact

def display_results(results, sector_perf):
    if not results:
        st.warning("No signals found.")
        st.info("Market hours: 9:15 AM - 3:30 PM IST")
        return
    strong_buy = len([r for r in results if "STRONG BUY" in r['final_signal']])
    buy = len([r for r in results if r['final_signal'] == "BUY"])
    strong_sell = len([r for r in results if "STRONG SELL" in r['final_signal']])
    sell = len([r for r in results if r['final_signal'] == "SELL"])
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f'<div class="metric-card"><h3>STRONG BUY</h3><h1>{strong_buy}</h1></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="metric-card"><h3>BUY</h3><h1>{buy}</h1></div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="metric-card"><h3>SELL</h3><h1>{sell}</h1></div>', unsafe_allow_html=True)
    with col4:
        st.markdown(f'<div class="metric-card"><h3>STRONG SELL</h3><h1>{strong_sell}</h1></div>', unsafe_allow_html=True)
    st.markdown("---")
    results = sorted(results, key=lambda x: x['accuracy'], reverse=True)
    for row in results:
        sig = row['final_signal']
        acc = row['accuracy']
        if "STRONG BUY" in sig:
            card_class = "strong-buy"
        elif sig == "BUY":
            card_class = "buy"
        elif "STRONG SELL" in sig:
            card_class = "strong-sell"
        elif sig == "SELL":
            card_class = "sell"
        else:
            card_class = "neutral"
        if acc >= 85:
            acc_class = "acc-90"
        elif acc >= 75:
            acc_class = "acc-80"
        else:
            acc_class = "acc-70"
        with st.expander(f"{sig} **{row['symbol']}** | Rs{row['current_price']} | {acc}%"):
            st.markdown(f'<div class="signal-card {card_class}"><h2>{sig}</h2></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="accuracy-badge {acc_class}">{acc}% ({row["filters_passed"]}/{row["total_filters"]})</div>', unsafe_allow_html=True)
            if row.get('sector'):
                st.markdown(f'<div class="filter-box"><b>Sector: {row["sector"]}</b> | Change: {row.get("sector_change", 0):+.2f}%</div>', unsafe_allow_html=True)
            if row.get('news_impact') and row['news_impact'] != "NO DATA":
                news_sentiment = "POSITIVE" if row['news_impact'] == "SUPPORTS" else ("NEGATIVE" if row['news_impact'] == "CONTRADICTS" else "NEUTRAL")
                news_class = "news-positive" if news_sentiment == "POSITIVE" else ("news-negative" if news_sentiment == "NEGATIVE" else "news-neutral")
                st.markdown(f'<div class="{news_class}"><b>News Impact: {row["news_impact"]}</b></div>', unsafe_allow_html=True)
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown(f'<div class="filter-box"><b>Trade</b><br>Entry: <b>Rs{row["entry_price"]}</b><br>SL: <span style="color:red">Rs{row["stop_loss"]}</span><br>Target: <span style="color:green">Rs{row["target"]}</span><br>Risk: Rs{row["risk"]} ({row["risk_percent"]}%)<br>R:R = 1:{risk_reward}</div>', unsafe_allow_html=True)
            with col2:
                st.markdown(f'<div class="filter-box"><b>Tech</b><br>RSI: {row.get("rsi", "N/A")}<br>VWAP: Rs{row["vwap"] if row.get("vwap") else "N/A"}<br>ATR: Rs{row.get("atr", "N/A")}<br>EMA20: Rs{row["ema20"] if row.get("ema20") else "N/A"}</div>', unsafe_allow_html=True)
            with col3:
                if row.get('oi_signal') and row['oi_signal'] != "NEUTRAL":
                    st.markdown(f'<div class="filter-box"><b>OI</b><br>{row.get("oi_buildup", "N/A")}<br>Signal: {row["oi_signal"]}</div>', unsafe_allow_html=True)
            st.markdown("---")
            st.markdown("**Filters:**")
            cols = st.columns(4)
            filter_details = row.get('filter_details', [])
            for i, item in enumerate(filter_details):
                with cols[i % 4]:
                    if isinstance(item, list) and len(item) >= 3:
                        filter_name, passed, detail = item[0], item[1], item[2]
                    elif isinstance(item, tuple) and len(item) >= 3:
                        filter_name, passed, detail = item[0], item[1], item[2]
                    else:
                        continue
                    color = "green" if passed else "red"
                    st.markdown(f'<p style="color:{color}; font-weight:bold;">{filter_name}</p><small>{detail}</small>', unsafe_allow_html=True)
    st.markdown("---")
    df_export = pd.DataFrame([{k: v for k, v in r.items() if k not in ['oi_data', 'news_data', 'filter_details']} for r in results])
    csv = df_export.to_csv(index=False)
    st.download_button(label="Download Signals", data=csv, file_name=f"sector_scanner_{get_ist_now().strftime('%Y%m%d_%H%M')}.csv", mime="text/csv")

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
    st.subheader("Scanning (Nifty Independent)...")
    sector_perf = get_sector_performance() if use_sector else {}
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
                final_signal, confidence, oi_signal, oi_buildup, news_impact = get_final_signal(orb_result['signal'], orb_result['accuracy'], oi_data, news_data)
                if news_impact == "CONTRADICTS" and use_news:
                    continue
                if "BUY" in final_signal or "SELL" in final_signal:
                    result = {**orb_result, 'final_signal': final_signal, 'confidence': round(abs(confidence) * 100, 1), 'oi_signal': oi_signal, 'oi_buildup': oi_buildup, 'news_impact': news_impact, 'oi_data': oi_data, 'news_data': news_data}
                    results.append(result)
    progress_bar.empty()
    status_text.empty()
    settings = {'accuracy_mode': accuracy_mode, 'min_accuracy': min_accuracy, 'orb_minutes': orb_minutes, 'risk_reward': risk_reward, 'min_price': min_price, 'max_price': max_price, 'use_sector': use_sector, 'use_oi': use_oi, 'use_news': use_news}
    if results:
        save_scan_data(results, sector_perf, stock_list, settings)
        st.success(f"Scan complete! {len(results)} signals found. Data saved automatically.")
    else:
        save_scan_data([], sector_perf, stock_list, settings)
    display_results(results, sector_perf)

else:
    st.info("Welcome! Click SCAN NOW in the sidebar to start scanning. Your scan results will be automatically saved even if your PC goes to sleep!")

with st.expander("Why Nifty Independent?"):
    st.markdown("""
    ### Nifty Independent Kyun?

    **Example:**
    ```
    Date: 15 Jan 2024
    Nifty: +0.5% (Bullish)
    IT Sector: -2.5% (Bearish)
    INFY: -3% (Strong Sell Signal)
    Result: INFY sell kiya -> Profit
    Agar Nifty dekhke buy kiya -> Loss
    ```

    **Sector Rotation:**
    - Nifty UP + IT DOWN = IT stocks avoid
    - Nifty DOWN + Pharma UP = Pharma buy

    **Stock Specific:**
    - Company news dominates
    - Sector momentum matters
    - Nifty just background noise

    ### Sector Strength Filter

    | Sector Trend | BUY Signal | SELL Signal |
    |-------------|-----------|-------------|
    | STRONG_UP | Pass | Fail |
    | UP | Pass | Fail |
    | NEUTRAL | Fail | Fail |
    | DOWN | Fail | Pass |
    | STRONG_DOWN | Fail | Pass |
    """)

st.markdown("---")
st.markdown("""
<div style="text-align: center; color: gray; font-size: 12px;">
<b>Disclaimer:</b> Educational purposes only. Not financial advice. 
<br><b>Nifty Independent | Sector Based | Stock-Specific Analysis</b>
<br><b>Secure Login Enabled | Auto-Save Enabled</b>
</div>
""", unsafe_allow_html=True)
