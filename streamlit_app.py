# dashboard.py

import streamlit as st
import sqlite3
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import numpy as np

# 페이지 설정
st.set_page_config(
    page_title="Bitcoin Trading Dashboard",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 커스텀 CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #1e1e1e;
        padding: 20px;
        border-radius: 10px;
        text-align: center;
        color: white;
    }
    .metric-label {
        font-size: 0.9rem;
        color: #888;
        margin-bottom: 10px;
    }
    .metric-value {
        font-size: 2rem;
        font-weight: bold;
    }
    .positive {
        color: #00ff00;
    }
    .negative {
        color: #ff0000;
    }
    .neutral {
        color: #ffaa00;
    }
</style>
""", unsafe_allow_html=True)

# 데이터베이스 연결
DB_FILE = "trading_history.db"

@st.cache_data(ttl=5)
def load_trades():
    """거래 내역 로드"""
    try:
        conn = sqlite3.connect(DB_FILE)
        df = pd.read_sql_query("SELECT * FROM trades ORDER BY timestamp DESC", conn)
        conn.close()
        return df
    except Exception as e:
        return pd.DataFrame()

@st.cache_data(ttl=5)
def load_ai_analysis():
    """AI 분석 내역 로드"""
    try:
        conn = sqlite3.connect(DB_FILE)
        df = pd.read_sql_query("SELECT * FROM ai_analysis ORDER BY timestamp DESC", conn)
        conn.close()
        return df
    except Exception as e:
        return pd.DataFrame()

def calculate_performance_metrics(df_trades):
    """성과 지표 계산"""
    if len(df_trades) == 0:
        return {
            'total_return': 0.0,
            'sharpe_ratio': 0.0,
            'win_rate': 0.0,
            'profit_factor': 0.0,
            'max_drawdown': 0.0,
            'total_trades': 0,
            'avg_profit_loss': 0.0,
            'avg_holding_time': 0.0
        }
    
    # 손익이 있는 거래만 필터
    closed_trades = df_trades[df_trades['status'] == 'CLOSED'].copy()
    
    if len(closed_trades) == 0:
        metrics = {
            'total_return': 0.0,
            'sharpe_ratio': 0.0,
            'win_rate': 0.0,
            'profit_factor': 0.0,
            'max_drawdown': 0.0,
            'total_trades': len(df_trades),
            'avg_profit_loss': 0.0,
            'avg_holding_time': 0.0
        }
    else:
        # 승률
        winning_trades = closed_trades[closed_trades['profit_loss'] > 0]
        win_rate = len(winning_trades) / len(closed_trades) * 100 if len(closed_trades) > 0 else 0
        
        # 총 수익률
        total_return = closed_trades['profit_loss_percentage'].sum() if 'profit_loss_percentage' in closed_trades else 0
        
        # Sharpe Ratio (간단 계산)
        if 'profit_loss_percentage' in closed_trades and len(closed_trades) > 1:
            returns = closed_trades['profit_loss_percentage']
            sharpe_ratio = (returns.mean() / returns.std()) * np.sqrt(252) if returns.std() != 0 else 0
        else:
            sharpe_ratio = 0
        
        # Profit Factor
        gross_profit = winning_trades['profit_loss'].sum() if len(winning_trades) > 0 else 0
        losing_trades = closed_trades[closed_trades['profit_loss'] < 0]
        gross_loss = abs(losing_trades['profit_loss'].sum()) if len(losing_trades) > 0 else 0
        profit_factor = gross_profit / gross_loss if gross_loss != 0 else 0
        
        # Max Drawdown (간단 계산)
        if 'profit_loss' in closed_trades:
            cumulative_pnl = closed_trades.sort_values('timestamp')['profit_loss'].cumsum()
            running_max = cumulative_pnl.expanding().max()
            drawdown = (cumulative_pnl - running_max) / running_max.abs()
            max_drawdown = drawdown.min() * 100 if len(drawdown) > 0 else 0
        else:
            max_drawdown = 0
        
        # 평균 손익
        avg_profit_loss = closed_trades['profit_loss'].mean()
        
        # 평균 보유 시간
        if 'exit_timestamp' in closed_trades:
            closed_trades['entry_time'] = pd.to_datetime(closed_trades['timestamp'])
            closed_trades['exit_time'] = pd.to_datetime(closed_trades['exit_timestamp'])
            closed_trades['holding_time'] = (closed_trades['exit_time'] - closed_trades['entry_time']).dt.total_seconds() / 3600
            avg_holding_time = closed_trades['holding_time'].mean()
        else:
            avg_holding_time = 0
        
        metrics = {
            'total_return': total_return,
            'sharpe_ratio': sharpe_ratio,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'max_drawdown': max_drawdown,
            'total_trades': len(df_trades),
            'avg_profit_loss': avg_profit_loss,
            'avg_holding_time': avg_holding_time
        }
    
    return metrics

def get_current_btc_price():
    """현재 BTC 가격 (임시 - 최근 거래에서 추출)"""
    df_trades = load_trades()
    if len(df_trades) > 0:
        return df_trades.iloc[0]['entry_price']
    return 0

def get_current_position():
    """현재 포지션 상태"""
    df_trades = load_trades()
    open_trades = df_trades[df_trades['status'] == 'OPEN']
    
    if len(open_trades) > 0:
        latest = open_trades.iloc[0]
        return {
            'has_position': True,
            'direction': latest['direction'],
            'entry_price': latest['entry_price'],
            'position_size': latest['position_size_usdt'],
            'leverage': latest['leverage']
        }
    
    return {'has_position': False}

# ==================== 사이드바 ====================
with st.sidebar:
    st.markdown("## Bitcoin Trading Bot")
    st.markdown("---")
    
    # 기간 선택
    st.markdown("### 기간 선택")
    time_period = st.selectbox(
        "",
        ["전체", "최근 24시간", "최근 7일", "최근 30일"],
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    
    # 필터
    st.markdown("### 필터")
    
    show_long = st.checkbox("Long", value=True)
    show_short = st.checkbox("Short", value=True)
    
    st.markdown("---")
    
    # 통계 요약
    st.markdown("### 최근 24시간")
    df_trades = load_trades()
    
    if len(df_trades) > 0:
        df_trades['timestamp'] = pd.to_datetime(df_trades['timestamp'])
        last_24h = df_trades[df_trades['timestamp'] >= datetime.now() - timedelta(hours=24)]
        
        st.metric("거래 수", len(last_24h))
        
        if len(last_24h) > 0:
            avg_leverage = last_24h['leverage'].mean()
            st.metric("평균 레버리지", f"{avg_leverage:.1f}x")
    else:
        st.info("데이터 없음")
    
    st.markdown("---")
    
    # 새로고침
    if st.button("🔄 새로고침", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    
    st.markdown("---")
    st.caption("자동 새로고침: 5초")

# ==================== 메인 영역 ====================

# 타이틀
st.markdown('<h1 class="main-header">Bitcoin Trading Dashboard</h1>', unsafe_allow_html=True)

# 데이터 로드
df_trades = load_trades()
df_analysis = load_ai_analysis()

# 기간 필터 적용
if time_period != "전체" and len(df_trades) > 0:
    df_trades['timestamp'] = pd.to_datetime(df_trades['timestamp'])
    
    if time_period == "최근 24시간":
        cutoff = datetime.now() - timedelta(hours=24)
    elif time_period == "최근 7일":
        cutoff = datetime.now() - timedelta(days=7)
    elif time_period == "최근 30일":
        cutoff = datetime.now() - timedelta(days=30)
    
    df_trades = df_trades[df_trades['timestamp'] >= cutoff]

# 방향 필터
direction_filter = []
if show_long:
    direction_filter.append('LONG')
if show_short:
    direction_filter.append('SHORT')

if len(direction_filter) > 0 and len(df_trades) > 0:
    df_trades = df_trades[df_trades['direction'].isin(direction_filter)]

# 성과 지표 계산
metrics = calculate_performance_metrics(df_trades)

# ==================== KPI 카드 (상단) ====================
st.markdown("### 📊 주요 성과 지표")

col1, col2, col3, col4 = st.columns(4)

with col1:
    total_return = metrics['total_return']
    return_class = "positive" if total_return > 0 else "negative" if total_return < 0 else "neutral"
    
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Total Return</div>
        <div class="metric-value {return_class}">{total_return:.2f}%</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    sharpe = metrics['sharpe_ratio']
    sharpe_class = "positive" if sharpe > 1 else "neutral" if sharpe > 0 else "negative"
    
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Sharpe Ratio</div>
        <div class="metric-value {sharpe_class}">{sharpe:.2f}</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    win_rate = metrics['win_rate']
    wr_class = "positive" if win_rate > 60 else "neutral" if win_rate > 40 else "negative"
    
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Win Rate</div>
        <div class="metric-value {wr_class}">{win_rate:.1f}%</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    pf = metrics['profit_factor']
    pf_class = "positive" if pf > 2 else "neutral" if pf > 1 else "negative"
    
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Profit Factor</div>
        <div class="metric-value {pf_class}">{pf:.2f}</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# ==================== 두 번째 줄 KPI ====================
col5, col6, col7, col8 = st.columns(4)

with col5:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Max Drawdown</div>
        <div class="metric-value negative">{metrics['max_drawdown']:.2f}%</div>
    </div>
    """, unsafe_allow_html=True)

with col6:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Total Trades</div>
        <div class="metric-value neutral">{metrics['total_trades']}</div>
    </div>
    """, unsafe_allow_html=True)

with col7:
    avg_pnl = metrics['avg_profit_loss']
    avg_pnl_class = "positive" if avg_pnl > 0 else "negative"
    
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Avg Profit/Loss</div>
        <div class="metric-value {avg_pnl_class}">{avg_pnl:.2f} USDT</div>
    </div>
    """, unsafe_allow_html=True)

with col8:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Avg Holding Time</div>
        <div class="metric-value neutral">{metrics['avg_holding_time']:.1f}h</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# ==================== 현재 상태 ====================
st.markdown("### 💼 현재 상태")

col_status1, col_status2 = st.columns(2)

with col_status1:
    btc_price = get_current_btc_price()
    
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Current BTC Price</div>
        <div class="metric-value neutral">${btc_price:,.2f}</div>
    </div>
    """, unsafe_allow_html=True)

with col_status2:
    position = get_current_position()
    
    if position['has_position']:
        direction_color = "positive" if position['direction'] == 'LONG' else "negative"
        
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Current Position</div>
            <div class="metric-value {direction_color}">{position['direction']}</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Current Position</div>
            <div class="metric-value neutral">NO POSITION</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("---")

# ==================== 차트 섹션 ====================
st.markdown("### 📈 Bitcoin Price Chart & Trade Entries")

if len(df_trades) > 0:
    # 가격 차트 + 거래 진입점
    fig = go.Figure()
    
    # BTC 가격 라인 (임시 - 실제로는 OHLCV 데이터 필요)
    df_trades_sorted = df_trades.sort_values('timestamp')
    
    fig.add_trace(go.Scatter(
        x=df_trades_sorted['timestamp'],
        y=df_trades_sorted['entry_price'],
        mode='lines',
        name='BTC Price',
        line=dict(color='#888', width=2)
    ))
    
    # LONG 진입점
    df_long = df_trades_sorted[df_trades_sorted['direction'] == 'LONG']
    fig.add_trace(go.Scatter(
        x=df_long['timestamp'],
        y=df_long['entry_price'],
        mode='markers',
        name='Long Entry',
        marker=dict(
            size=12,
            color='green',
            symbol='triangle-up',
            line=dict(width=2, color='white')
        )
    ))
    
    # SHORT 진입점
    df_short = df_trades_sorted[df_trades_sorted['direction'] == 'SHORT']
    fig.add_trace(go.Scatter(
        x=df_short['timestamp'],
        y=df_short['entry_price'],
        mode='markers',
        name='Short Entry',
        marker=dict(
            size=12,
            color='red',
            symbol='triangle-down',
            line=dict(width=2, color='white')
        )
    ))
    
    fig.update_layout(
        title="Bitcoin Price & Trading Points",
        xaxis_title="Time",
        yaxis_title="Price (USDT)",
        height=500,
        hovermode='x unified',
        template='plotly_dark'
    )
    
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("거래 데이터가 없습니다.")

st.markdown("---")

# ==================== 거래 테이블 ====================
st.markdown("### 📋 최근 거래 내역")

if len(df_trades) > 0:
    display_df = df_trades[[
        'timestamp', 'direction', 'entry_price', 'position_size_usdt',
        'leverage', 'stop_loss_percentage', 'take_profit_percentage', 'status'
    ]].head(20).copy()
    
    # 컬럼명 변경
    display_df.columns = ['시간', '방향', '진입가', '포지션(USDT)', '레버리지', 'SL%', 'TP%', '상태']
    
    # 포맷팅
    display_df['진입가'] = display_df['진입가'].apply(lambda x: f"${x:,.2f}")
    display_df['포지션(USDT)'] = display_df['포지션(USDT)'].apply(lambda x: f"${x:,.2f}")
    display_df['레버리지'] = display_df['레버리지'].apply(lambda x: f"{x}x")
    display_df['SL%'] = display_df['SL%'].apply(lambda x: f"{x:.2%}")
    display_df['TP%'] = display_df['TP%'].apply(lambda x: f"{x:.2%}")
    
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        height=400
    )
else:
    st.info("거래 데이터가 없습니다.")

# 푸터
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: gray;'>🤖 Bitcoin AI Trading Bot | Kelly Criterion + Warren Buffett + Self-Learning</div>",
    unsafe_allow_html=True
)
