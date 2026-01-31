import ccxt
import os
import math
import time
import pandas as pd
import requests
from dotenv import load_dotenv
load_dotenv()
from openai import OpenAI
from datetime import datetime

# SerpApi 설정
SERPAPI_KEY = os.getenv("SERPAPI_KEY")


def fetch_bitcoin_news():
    """Google News API로 비트코인 뉴스 헤드라인 가져오기 (title, date만)"""
    try:
        # SerpApi Google News 엔드포인트
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
        
        # 뉴스 결과 파싱
        news_results = data.get("news_results", [])
        
        # 상위 10개 헤드라인의 title과 date만 추출
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

print(fetch_bitcoin_news())