import ccxt
import os
import math
import time
import requests
import pandas as pd
import json
import sqlite3
from dotenv import load_dotenv
load_dotenv()
from openai import OpenAI
from datetime import datetime


# 1. 현재 IP 확인
try:
    current_ip = requests.get('https://api.ipify.org', timeout=5).text
    print(f"✓ 현재 IP: {current_ip}")
    print(f"  → Binance API 설정에서 이 IP가 화이트리스트에 있는지 확인하세요!\n")
except Exception as e:
    print(f"✗ IP 확인 실패: {e}\n")
    
# 바이낸스 세팅
api_key = os.getenv("BINANCE_API_KEY")
secret = os.getenv("BINANCE_SECRET_KEY")
exchange = ccxt.binance({
    'apiKey': api_key,
    'secret': secret,
    'enableRateLimit': True,
    'options': {
        'defaultType': 'future',
        'adjustForTimeDifference': True
    }
})

if api_key and secret:
    print(f"✓ API Key: {api_key[:10]}...")
    print(f"✓ Secret: {secret[:10]}...\n")
else:
    print("✗ API 키가 .env 파일에서 로드되지 않았습니다!\n")
    
symbol = "BTC/USDT"
client = OpenAI()

# SerpApi 설정
SERPAPI_KEY = os.getenv("SERPAPI_KEY")

# ==================== 데이터베이스 설정 ====================
DB_FILE = "trading_history.db"

def init_database():
    """데이터베이스 초기화 및 테이블 생성"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # 거래 내역 테이블
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        direction TEXT NOT NULL,
        entry_price REAL NOT NULL,
        position_size_usdt REAL NOT NULL,
        btc_amount REAL NOT NULL,
        leverage INTEGER NOT NULL,
        stop_loss_price REAL NOT NULL,
        stop_loss_percentage REAL NOT NULL,
        take_profit_price REAL NOT NULL,
        take_profit_percentage REAL NOT NULL,
        risk_reward_ratio REAL,
        available_balance REAL,
        conviction_level REAL,
        reasoning TEXT,
        status TEXT DEFAULT 'OPEN',
        exit_price REAL,
        exit_timestamp TEXT,
        profit_loss REAL,
        profit_loss_percentage REAL
    )
    ''')
    
    # AI 분석 내역 테이블
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS ai_analysis (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        current_price REAL NOT NULL,
        available_balance REAL NOT NULL,
        direction TEXT NOT NULL,
        position_size_fraction REAL,
        recommended_leverage INTEGER,
        stop_loss_percentage REAL,
        take_profit_percentage REAL,
        reasoning TEXT,
        action_taken TEXT,
        market_condition TEXT
    )
    ''')
    
    conn.commit()
    conn.close()
    print("✓ Database initialized: trading_history.db\n")

def save_trade_to_db(trade_data):
    """거래 내역을 데이터베이스에 저장"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT INTO trades (
        timestamp, direction, entry_price, position_size_usdt, btc_amount,
        leverage, stop_loss_price, stop_loss_percentage, take_profit_price,
        take_profit_percentage, risk_reward_ratio, available_balance, 
        conviction_level, reasoning, status
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        trade_data['timestamp'],
        trade_data['direction'],
        trade_data['entry_price'],
        trade_data['position_size_usdt'],
        trade_data['btc_amount'],
        trade_data['leverage'],
        trade_data['stop_loss_price'],
        trade_data['stop_loss_percentage'],
        trade_data['take_profit_price'],
        trade_data['take_profit_percentage'],
        trade_data['risk_reward_ratio'],
        trade_data['available_balance'],
        trade_data.get('conviction_level', 0),
        trade_data['reasoning'],
        'OPEN'
    ))
    
    conn.commit()
    trade_id = cursor.lastrowid
    conn.close()
    
    print(f"✓ Trade saved to database (ID: {trade_id})")
    return trade_id

def save_ai_analysis_to_db(analysis_data):
    """AI 분석 내역을 데이터베이스에 저장"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT INTO ai_analysis (
        timestamp, current_price, available_balance, direction,
        position_size_fraction, recommended_leverage, stop_loss_percentage,
        take_profit_percentage, reasoning, action_taken, market_condition
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        analysis_data['timestamp'],
        analysis_data['current_price'],
        analysis_data['available_balance'],
        analysis_data['direction'],
        analysis_data.get('position_size_fraction'),
        analysis_data.get('recommended_leverage'),
        analysis_data.get('stop_loss_percentage'),
        analysis_data.get('take_profit_percentage'),
        analysis_data.get('reasoning'),
        analysis_data['action_taken'],
        analysis_data.get('market_condition', '')
    ))
    
    conn.commit()
    conn.close()

def get_historical_performance():
    """과거 거래 성과 분석 데이터 가져오기"""
    conn = sqlite3.connect(DB_FILE)
    
    # 최근 20개 거래 내역
    recent_trades = pd.read_sql_query('''
        SELECT * FROM trades 
        ORDER BY timestamp DESC 
        LIMIT 20
    ''', conn)
    
    # 최근 10개 AI 분석 내역
    recent_analysis = pd.read_sql_query('''
        SELECT * FROM ai_analysis 
        ORDER BY timestamp DESC 
        LIMIT 10
    ''', conn)
    
    # 통계 계산
    stats = {}
    
    if len(recent_trades) > 0:
        # 방향별 통계
        direction_counts = recent_trades['direction'].value_counts().to_dict()
        
        # 평균 레버리지
        avg_leverage = recent_trades['leverage'].mean()
        
        # 평균 리스크/보상 비율
        avg_rr = recent_trades['risk_reward_ratio'].mean()
        
        # 평균 포지션 크기
        avg_position_size = recent_trades['position_size_usdt'].mean()
        
        stats = {
            'total_trades': len(recent_trades),
            'direction_distribution': direction_counts,
            'avg_leverage': round(avg_leverage, 2),
            'avg_risk_reward': round(avg_rr, 2),
            'avg_position_size': round(avg_position_size, 2)
        }
    
    conn.close()
    
    return {
        'recent_trades': recent_trades.to_dict(orient='records') if len(recent_trades) > 0 else [],
        'recent_analysis': recent_analysis.to_dict(orient='records') if len(recent_analysis) > 0 else [],
        'statistics': stats
    }

def print_trade_statistics():
    """거래 통계 출력"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # 총 거래 수
    cursor.execute('SELECT COUNT(*) FROM trades')
    total_trades = cursor.fetchone()[0]
    
    # 방향별 통계
    cursor.execute('SELECT direction, COUNT(*) FROM trades GROUP BY direction')
    direction_stats = cursor.fetchall()
    
    # 평균 레버리지
    cursor.execute('SELECT AVG(leverage) FROM trades')
    avg_leverage = cursor.fetchone()[0]
    
    conn.close()
    
    print("\n" + "="*50)
    print("📊 TRADING STATISTICS")
    print("="*50)
    print(f"Total Trades: {total_trades}")
    for direction, count in direction_stats:
        print(f"  {direction}: {count} trades")
    if avg_leverage:
        print(f"Average Leverage: {avg_leverage:.1f}x")
    print("="*50 + "\n")

# ==================== 기존 함수들 ====================

def get_available_balance():
    """사용 가능한 USDT 잔고 조회"""
    try:
        balance = exchange.fetch_balance()
        usdt_free = balance['USDT']['free']
        return usdt_free
    except Exception as e:
        print(f"Error fetching balance: {e}")
        return 0

def fetch_multi_timeframe_data():
    """타임프레임별 데이터 수집"""
    timeframes = {
        "15m": {"timeframe": "15m", "limit": 96},
        "1h": {"timeframe": "1h", "limit": 48},
        "4h": {"timeframe": "4h", "limit": 30},
    }    
    multi_tf_data = {}    
    for tf_name, tf_params in timeframes.items():
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe=tf_params["timeframe"], limit=tf_params["limit"])
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')            
            multi_tf_data[tf_name] = df
            print(f"✓ Collected {tf_name} data: {len(df)} candles")
        except Exception as e:
            print(f"Error fetching {tf_name} data: {e}")            
    return multi_tf_data           

def fetch_bitcoin_news():
    """Google News API로 비트코인 뉴스 헤드라인 가져오기"""
    try:
        url = "https://serpapi.com/search.json"
        
        params = {
            "engine": "google_news",
            "q": "bitcoin",
            "gl": "us",
            "hl": "en",
            "api_key": SERPAPI_KEY
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        news_results = data.get("news_results", [])
        
        headlines = []
        for item in news_results[:10]:
            headline = {
                "title": item.get("title", ""),
                "date": item.get("date", "")
            }
            headlines.append(headline)
        
        print(f"✓ Fetched {len(headlines)} news headlines")
        return headlines
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching news: {e}")
        return []
    except Exception as e:
        print(f"Unexpected error in news fetch: {e}")
        return []

# ==================== 메인 프로그램 시작 ====================

# 데이터베이스 초기화
init_database()

print("\n=== Bitcoin AI Trading Bot Started ===")
print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("Trading Pair:", symbol)
print("Max Leverage: 20x (AI-optimized)")
print("Strategy: Kelly Criterion + Warren Buffett + Self-Learning")
print("Min Position: $100 USDT")
print("Database: trading_history.db")
print("==========================================\n")

# 시작 시 통계 출력
print_trade_statistics()
        
while True:
    try:
        # 현재 시간 및 가격 조회
        current_time = datetime.now().strftime('%H:%M:%S')
        current_timestamp = datetime.now().isoformat()
        current_price = exchange.fetch_ticker(symbol)['last']
        available_balance = get_available_balance()
        
        print(f"\n[{current_time}] Current BTC Price: ${current_price:,.2f}")
        print(f"Available Balance: ${available_balance:.2f} USDT")

        # 포지션 확인
        current_side = None
        amount = 0
        positions = exchange.fetch_positions([symbol])
        for position in positions:
            if position['symbol'] == 'BTC/USDT:USDT':
                amt = float(position['info']['positionAmt'])
                if amt > 0:
                    current_side = 'long'
                    amount = amt
                elif amt < 0:
                    current_side = 'short'
                    amount = abs(amt)
                    
        if current_side:
            print(f"Current Position: {current_side.upper()} {amount} BTC")
        else:
            # 포지션이 없을 경우, 남아있는 미체결 주문 취소
            try:
                open_orders = exchange.fetch_open_orders(symbol)
                if open_orders:
                    for order in open_orders:
                        exchange.cancel_order(order['id'], symbol)
                    print("✓ Cancelled remaining open orders")
                else:
                    print("✓ No open orders to cancel")
            except Exception as e:
                print(f"Error cancelling orders: {e}")
                
            time.sleep(5)
            print("\n🤖 Analyzing market for trading opportunity...")

            # === 데이터 수집 ===
            multi_tf_data = fetch_multi_timeframe_data()
            news_headlines = fetch_bitcoin_news()
            
            # === 과거 거래 성과 데이터 수집 ===
            historical_performance = get_historical_performance()
            print(f"✓ Loaded historical performance: {historical_performance['statistics'].get('total_trades', 0)} recent trades")
            
            # === AI 분석을 위한 데이터 준비 ===
            market_analysis = {
                "timestamp": current_timestamp,
                "current_price": current_price,
                "available_balance": available_balance,
                "timeframes": {},
                "news_sentiment": news_headlines,
                "historical_performance": historical_performance  # 과거 성과 데이터 추가
            }
            
            for tf_name, df in multi_tf_data.items():
                market_analysis["timeframes"][tf_name] = df.to_dict(orient="records")

            # === AI에게 분석 요청 (자기학습 시스템 포함) ===
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": """You are an advanced crypto trading AI with self-learning capabilities. You analyze multi-timeframe data, news sentiment, and YOUR OWN PAST TRADING PERFORMANCE to continuously improve your decision-making.

CORE INVESTMENT PRINCIPLES (Warren Buffett):
- Rule No.1: Never lose money.
- Rule No.2: Never forget rule No.1.

SELF-LEARNING PROCESS:

1. REVIEW YOUR PAST PERFORMANCE:
   * Analyze your recent_trades: What patterns led to success or failure?
   * Review your recent_analysis: Were your predictions accurate?
   * Examine your statistics: Are you overusing certain strategies?
   * Identify mistakes: Did you trade in unfavorable conditions?
   * Learn from patterns: Which market conditions suit your strategy best?

2. SELF-REFLECTION QUESTIONS:
   * Am I being too aggressive with leverage in volatile markets?
   * Did I respect my minimum conviction threshold (55%)?
   * Are my stop-loss levels too tight or too wide based on past trades?
   * Am I overtrading in similar market conditions?
   * What was my biggest mistake in recent trades, and how can I avoid it?

3. ADAPT YOUR STRATEGY:
   * If recent trades show high leverage failures → reduce leverage recommendation
   * If stop-losses are frequently hit prematurely → widen SL based on volatility
   * If you traded in low-conviction scenarios → be more selective
   * If certain market conditions consistently failed → avoid similar setups
   * If news sentiment analysis was wrong → adjust sentiment interpretation

4. CURRENT MARKET ANALYSIS:
   * Short-term trend (15m): Recent price action and momentum
   * Medium-term trend (1h): Intermediate market direction
   * Long-term trend (4h): Overall market bias
   * Volatility across timeframes
   * Key support/resistance levels
   * News sentiment: Bullish or bearish indicators

5. CONVICTION ASSESSMENT:
   * Based on current analysis AND past performance patterns
   * Probability of success (51-95%)
   * If similar past setups failed, LOWER your conviction
   * If similar past setups succeeded, maintain or raise conviction

6. KELLY CRITERION POSITION SIZING:
   * Formula: f* = (p - q) / b
   * p = probability of success (your conviction)
   * q = probability of failure (1 - p)
   * b = win/loss ratio
   * Apply Half-Kelly (50%) for safety

7. OPTIMAL LEVERAGE (Learn from past):
   * Review historical_performance statistics for avg_leverage
   * If past high leverage trades failed → use lower leverage
   * Low volatility + strong trend = higher leverage (up to 20x)
   * High volatility or uncertainty = lower leverage (1-3x)

8. STOP LOSS & TAKE PROFIT:
   * Learn from past trades: were SL/TP levels optimal?
   * Adjust based on current volatility
   * Set SL at technical invalidation level
   * Set TP at realistic technical target

9. RISK MANAGEMENT:
   * Never exceed Half-Kelly
   * Minimum 55% conviction to trade
   * If past performance shows consecutive losses → be MORE conservative
   * If uncertain, choose NO_POSITION

10. REASONING (CRITICAL - Show your learning):
   * Explain what you learned from past performance
   * State how past mistakes are influencing current decision
   * Justify why this setup is different from past failures (if any)
   * Describe your confidence level and why

RESPONSE FORMAT (JSON only):

{
  "direction": "LONG" or "SHORT" or "NO_POSITION",
  "recommended_position_size": [decimal 0.1-1.0],
  "recommended_leverage": [integer 1-20],
  "stop_loss_percentage": [decimal, e.g. 0.005],
  "take_profit_percentage": [decimal],
  "reasoning": "MUST include: (1) What you learned from past trades, (2) How past performance influences this decision, (3) Current market analysis, (4) Why you're confident or cautious"
}

IMPORTANT: 
- Do NOT use markdown code blocks (```json)
- Return ONLY the raw JSON object
- Your reasoning MUST reference your historical performance and learning
- Be honest about past mistakes and how they shape current decisions"""},
                    {"role": "user", "content": json.dumps(market_analysis)}
                ]
            )
            
            # AI 응답 파싱
            ai_response_text = response.choices[0].message.content.strip()
            
            # JSON 파싱 시도
            try:
                # 마크다운 코드 블록 제거
                if "```json" in ai_response_text:
                    ai_response_text = ai_response_text.split("```json")[1].split("```")[0].strip()
                elif "```" in ai_response_text:
                    ai_response_text = ai_response_text.split("```")[1].split("```")[0].strip()
                
                ai_decision = json.loads(ai_response_text)
                
                direction = ai_decision.get("direction", "NO_POSITION").upper()
                position_size_fraction = float(ai_decision.get("recommended_position_size", 0))
                leverage = int(ai_decision.get("recommended_leverage", 1))
                sl_percentage = float(ai_decision.get("stop_loss_percentage", 0.005))
                tp_percentage = float(ai_decision.get("take_profit_percentage", 0.005))
                reasoning = ai_decision.get("reasoning", "No reasoning provided")
                
            except json.JSONDecodeError as e:
                print(f"❌ JSON Parse Error: {e}")
                print(f"Raw response: {ai_response_text}")
                
                # 에러도 데이터베이스에 저장
                save_ai_analysis_to_db({
                    'timestamp': current_timestamp,
                    'current_price': current_price,
                    'available_balance': available_balance,
                    'direction': 'ERROR',
                    'reasoning': f"JSON Parse Error: {str(e)}",
                    'action_taken': 'SKIPPED'
                })
                
                print("→ Skipping this trading cycle")
                time.sleep(180)
                continue
            
            # === AI 분석 결과 출력 ===
            print("\n" + "="*70)
            print("🧠 AI SELF-LEARNING TRADING DECISION")
            print("="*70)
            print(f"Direction: {direction}")
            print(f"Position Size: {position_size_fraction:.1%} of capital")
            print(f"Leverage: {leverage}x")
            print(f"Stop Loss: {sl_percentage:.2%}")
            print(f"Take Profit: {tp_percentage:.2%}")
            print(f"\n📊 AI Reasoning (with Self-Learning):")
            print(f"{reasoning}")
            print("="*70 + "\n")
            
            # NO_POSITION이면 거래 안 함
            if direction == "NO_POSITION" or position_size_fraction <= 0:
                print("→ AI Decision: NO_POSITION (Insufficient edge or learned caution)")
                
                # AI 분석 저장
                save_ai_analysis_to_db({
                    'timestamp': current_timestamp,
                    'current_price': current_price,
                    'available_balance': available_balance,
                    'direction': direction,
                    'position_size_fraction': position_size_fraction,
                    'recommended_leverage': leverage,
                    'stop_loss_percentage': sl_percentage,
                    'take_profit_percentage': tp_percentage,
                    'reasoning': reasoning,
                    'action_taken': 'NO_TRADE',
                    'market_condition': 'Learning from past'
                })
                
                print("⏳ Waiting 3 minutes before next analysis...")
                time.sleep(180)
                continue
            
            # 포지션 크기 검증 (0.1 ~ 1.0)
            if position_size_fraction < 0.1:
                position_size_fraction = 0.1
            elif position_size_fraction > 1.0:
                position_size_fraction = 1.0
            
            # 레버리지 검증 (1~20배)
            if leverage < 1:
                leverage = 1
            elif leverage > 20:
                leverage = 20
            
            # 실제 투자 금액 계산
            position_size_usdt = available_balance * position_size_fraction
            
            # 최소 투자 금액 체크 ($100)
            if position_size_usdt < 100:
                print(f"⚠️  Position size ${position_size_usdt:.2f} below minimum $100")
                
                # AI 분석 저장
                save_ai_analysis_to_db({
                    'timestamp': current_timestamp,
                    'current_price': current_price,
                    'available_balance': available_balance,
                    'direction': direction,
                    'position_size_fraction': position_size_fraction,
                    'recommended_leverage': leverage,
                    'stop_loss_percentage': sl_percentage,
                    'take_profit_percentage': tp_percentage,
                    'reasoning': reasoning,
                    'action_taken': 'BELOW_MINIMUM',
                    'market_condition': 'Position too small'
                })
                
                print("⏳ Waiting 3 minutes before next analysis...")
                time.sleep(180)
                continue
            
            # 가용 잔고 확인
            if position_size_usdt > available_balance:
                print(f"⚠️  Requested ${position_size_usdt:.2f} exceeds balance ${available_balance:.2f}")
                position_size_usdt = available_balance * 0.95
                print(f"   Adjusted to ${position_size_usdt:.2f}")
            
            # BTC 수량 계산
            btc_amount = math.floor((position_size_usdt / current_price) * 1000) / 1000
            
            print(f"\n💰 Final Order Details:")
            print(f"   Investment: ${position_size_usdt:.2f} USDT ({position_size_fraction:.1%} of capital)")
            print(f"   BTC Amount: {btc_amount} BTC")
            print(f"   Leverage: {leverage}x")
            print(f"   Effective Exposure: ${position_size_usdt * leverage:,.2f}")
            print(f"   Stop Loss: {sl_percentage:.2%}")
            print(f"   Take Profit: {tp_percentage:.2%}")

            # 레버리지 설정
            exchange.set_leverage(leverage, symbol)
            print(f"\n✓ Leverage set to {leverage}x")

            # 포지션 진입 및 SL/TP 주문
            if direction == "LONG":
                order = exchange.create_market_buy_order(symbol, btc_amount)
                entry_price = current_price
                sl_price = round(entry_price * (1 - sl_percentage), 2)
                tp_price = round(entry_price * (1 + tp_percentage), 2)
                
                # SL/TP 주문 생성
                exchange.create_order(symbol, 'STOP_MARKET', 'sell', btc_amount, None, {'stopPrice': sl_price})
                exchange.create_order(symbol, 'TAKE_PROFIT_MARKET', 'sell', btc_amount, None, {'stopPrice': tp_price})
                
                print(f"\n{'='*70}")
                print(f"🟢 LONG POSITION OPENED")
                print(f"{'='*70}")
                print(f"Entry Price: ${entry_price:,.2f}")
                print(f"Position Size: ${position_size_usdt:.2f} USDT ({btc_amount} BTC)")
                print(f"Leverage: {leverage}x")
                print(f"Stop Loss: ${sl_price:,.2f} (-{sl_percentage:.2%})")
                print(f"Take Profit: ${tp_price:,.2f} (+{tp_percentage:.2%})")
                print(f"Risk/Reward: 1:{tp_percentage/sl_percentage:.2f}")
                print(f"{'='*70}\n")
                
                # 거래 내역 저장
                trade_data = {
                    'timestamp': current_timestamp,
                    'direction': 'LONG',
                    'entry_price': entry_price,
                    'position_size_usdt': position_size_usdt,
                    'btc_amount': btc_amount,
                    'leverage': leverage,
                    'stop_loss_price': sl_price,
                    'stop_loss_percentage': sl_percentage,
                    'take_profit_price': tp_price,
                    'take_profit_percentage': tp_percentage,
                    'risk_reward_ratio': tp_percentage / sl_percentage,
                    'available_balance': available_balance,
                    'conviction_level': position_size_fraction,
                    'reasoning': reasoning
                }
                save_trade_to_db(trade_data)
                
                # AI 분석 저장
                save_ai_analysis_to_db({
                    'timestamp': current_timestamp,
                    'current_price': current_price,
                    'available_balance': available_balance,
                    'direction': direction,
                    'position_size_fraction': position_size_fraction,
                    'recommended_leverage': leverage,
                    'stop_loss_percentage': sl_percentage,
                    'take_profit_percentage': tp_percentage,
                    'reasoning': reasoning,
                    'action_taken': 'TRADE_EXECUTED',
                    'market_condition': 'Learned confidence'
                })

            elif direction == "SHORT":
                order = exchange.create_market_sell_order(symbol, btc_amount)
                entry_price = current_price
                sl_price = round(entry_price * (1 + sl_percentage), 2)
                tp_price = round(entry_price * (1 - tp_percentage), 2)
                
                # SL/TP 주문 생성
                exchange.create_order(symbol, 'STOP_MARKET', 'buy', btc_amount, None, {'stopPrice': sl_price})
                exchange.create_order(symbol, 'TAKE_PROFIT_MARKET', 'buy', btc_amount, None, {'stopPrice': tp_price})
                
                print(f"\n{'='*70}")
                print(f"🔴 SHORT POSITION OPENED")
                print(f"{'='*70}")
                print(f"Entry Price: ${entry_price:,.2f}")
                print(f"Position Size: ${position_size_usdt:.2f} USDT ({btc_amount} BTC)")
                print(f"Leverage: {leverage}x")
                print(f"Stop Loss: ${sl_price:,.2f} (+{sl_percentage:.2%})")
                print(f"Take Profit: ${tp_price:,.2f} (-{tp_percentage:.2%})")
                print(f"Risk/Reward: 1:{tp_percentage/sl_percentage:.2f}")
                print(f"{'='*70}\n")
                
                # 거래 내역 저장
                trade_data = {
                    'timestamp': current_timestamp,
                    'direction': 'SHORT',
                    'entry_price': entry_price,
                    'position_size_usdt': position_size_usdt,
                    'btc_amount': btc_amount,
                    'leverage': leverage,
                    'stop_loss_price': sl_price,
                    'stop_loss_percentage': sl_percentage,
                    'take_profit_price': tp_price,
                    'take_profit_percentage': tp_percentage,
                    'risk_reward_ratio': tp_percentage / sl_percentage,
                    'available_balance': available_balance,
                    'conviction_level': position_size_fraction,
                    'reasoning': reasoning
                }
                save_trade_to_db(trade_data)
                
                # AI 분석 저장
                save_ai_analysis_to_db({
                    'timestamp': current_timestamp,
                    'current_price': current_price,
                    'available_balance': available_balance,
                    'direction': direction,
                    'position_size_fraction': position_size_fraction,
                    'recommended_leverage': leverage,
                    'stop_loss_percentage': sl_percentage,
                    'take_profit_percentage': tp_percentage,
                    'reasoning': reasoning,
                    'action_taken': 'TRADE_EXECUTED',
                    'market_condition': 'Learned confidence'
                })
            
            # 통계 업데이트 출력
            print_trade_statistics()
            
            # 포지션 진입 후 3분 대기
            print("⏳ Position opened. Waiting 3 minutes before next analysis...")
            time.sleep(180)

        time.sleep(1)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        time.sleep(5)