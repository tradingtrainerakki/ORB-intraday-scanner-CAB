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
def analyze_orb_ultimate(symbol, orb_mins=15, min_accuracy=60):
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

        # Min accuracy filter
        if accuracy < min_accuracy:
            return None

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
        orb_atr_pct = orb_data.get('atr_pct', 0) if orb_data else 0
        orb_qty_pct = orb_data.get('qty_pct', 100) if orb_data else 100

        # ===== SIMPLIFIED SCORING (Max Real Trades) =====
        score = 0

        # 1. OI Spurt Score (0-25) - Lower threshold for more signals
        if oi_pct > 3: score += 25
        elif oi_pct > 1.5: score += 20
        elif oi_pct > 0.5: score += 15
        elif oi_pct > 0: score += 10

        # 2. ORB Score (0-25) - Direction based
        if orb_signal == "BUY":
            if orb_accuracy >= 80: score += 25
            elif orb_accuracy >= 60: score += 20
            else: score += 10
        elif orb_signal == "SELL":
            if orb_accuracy >= 80: score += 0
            elif orb_accuracy >= 60: score += 5
            else: score += 10

        # 3. Technical Score (0-30) - Simple 3 checks
        if cp > vwap: score += 10
        if ema9 > ema21: score += 10
        if vol_ratio > 1.0: score += 10

        # 4. ATR/Volatility Bonus (0-10) - Calm stocks get bonus
        if orb_atr_pct < 1.0: score += 10
        elif orb_atr_pct < 1.5: score += 5

        # 5. Trend Alignment (0-10)
        if orb_signal == "BUY" and oi_interp in ["LONG BUILD", "SHORT COVER"]:
            score += 10
        elif orb_signal == "SELL" and oi_interp in ["SHORT BUILD", "LONG UNWIND"]:
            score += 10

        # ===== SIGNAL GENERATION (More Lenient) =====
        if score >= 70: signal = "STRONG BUY"
        elif score >= 50: signal = "BUY"
        elif score <= 30: signal = "STRONG SELL"
        elif score <= 45: signal = "SELL"
        else: signal = "WAIT"

        # ===== ATR-BASED SL/TARGET (Dynamic) =====
        if orb_data and orb_data.get('atr'):
            atr = orb_data['atr']
            if "BUY" in signal:
                sl = round(cp - (1.5 * atr), 2)
                tgt = round(cp + (3 * atr), 2)
            elif "SELL" in signal:
                sl = round(cp + (1.5 * atr), 2)
                tgt = round(cp - (3 * atr), 2)
            else:
                sl = "-"
                tgt = "-"
        else:
            if "BUY" in signal:
                sl = round(cp * 0.995, 2)
                tgt = round(cp * 1.02, 2)
            elif "SELL" in signal:
                sl = round(cp * 1.005, 2)
                tgt = round(cp * 0.98, 2)
            else:
                sl = "-"
                tgt = "-"

        return {
            "STOCK": ticker,
            "OI SPURT %": f"{'+' if oi_pct >= 0 else ''}{oi_pct:.2f}%",
            "OI SIGNAL": oi_interp,
            "ORB": f"{orb_signal} ({orb_accuracy}%)",
            "LTP": round(cp, 2),
            "CHG %": f"{'+' if chg >= 0 else ''}{chg}%",
            "SIGNAL": signal,
            "VWAP": "ABOVE" if cp > vwap else "BELOW",
            "EMA TREND": "BULLISH" if ema9 > ema21 else "BEARISH",
            "VOL RATIO": f"{vol_ratio}x",
            "ATR %": f"{orb_atr_pct}%",
            "QTY": f"{orb_qty_pct}%",
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

    if st.button("🚪 Logout", use_container_width=True):
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
                orb_data = analyze_orb_ultimate(ticker + ".NS", orb_minutes, min_accuracy)

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
                        VWAP: Rs{orb['vwap']}<br>
                        ATR: Rs{orb['atr']}<br>
                        ATR%: {orb['atr_pct']}%<br>
                        EMA20: Rs{orb['ema20']}<br>
                        Vol: {orb['volume_ratio']}x
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
""", unsafe_allow_html=True)
