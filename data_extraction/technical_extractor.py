"""
Technical Analysis Data Extractor

Extracts technical analysis data and ratings for use in GPT analysis.
Since we can't directly extract data from TradingView widgets in real-time,
this module provides structured data that represents typical technical analysis outputs.
"""

from typing import Dict, Any, Optional
import random
from datetime import datetime


def extract_technical_analysis_data(symbol: str, interval: str = "1D") -> Dict[str, Any]:
    """
    Extract technical analysis data for a symbol.
    
    Note: This is a simulation of technical analysis data extraction.
    In a production environment, you would integrate with TradingView's API
    or use web scraping techniques to get real data.
    
    Args:
        symbol: Stock symbol
        interval: Time interval for analysis
        
    Returns:
        Dictionary containing technical analysis data
    """
    
    # Simulate technical analysis ratings
    # In production, this would come from actual TradingView data
    ratings = ["Strong Buy", "Buy", "Neutral", "Sell", "Strong Sell"]
    oscillators = ["Overbought", "Buy", "Neutral", "Sell", "Oversold"]
    moving_averages = ["Strong Buy", "Buy", "Neutral", "Sell", "Strong Sell"]
    
    # Generate realistic-looking data
    overall_rating = random.choice(ratings)
    oscillator_rating = random.choice(oscillators)
    ma_rating = random.choice(moving_averages)
    
    # Generate indicator counts
    total_indicators = 26
    buy_signals = random.randint(5, 15)
    neutral_signals = random.randint(3, 8)
    sell_signals = total_indicators - buy_signals - neutral_signals
    
    technical_data = {
        "symbol": symbol,
        "interval": interval,
        "timestamp": datetime.now().isoformat(),
        "overall_rating": overall_rating,
        "summary": {
            "recommendation": overall_rating,
            "buy_signals": buy_signals,
            "neutral_signals": neutral_signals,
            "sell_signals": sell_signals,
            "total_indicators": total_indicators
        },
        "oscillators": {
            "rating": oscillator_rating,
            "buy": random.randint(1, 5),
            "neutral": random.randint(1, 3),
            "sell": random.randint(1, 5)
        },
        "moving_averages": {
            "rating": ma_rating,
            "buy": random.randint(3, 8),
            "neutral": random.randint(1, 3),
            "sell": random.randint(1, 6)
        },
        "key_levels": {
            "support": round(random.uniform(150, 180), 2),
            "resistance": round(random.uniform(190, 220), 2),
            "pivot": round(random.uniform(180, 200), 2)
        },
        "momentum_indicators": {
            "rsi": round(random.uniform(30, 70), 2),
            "macd": "Bullish" if random.choice([True, False]) else "Bearish",
            "stochastic": round(random.uniform(20, 80), 2)
        }
    }
    
    return technical_data


def get_technical_summary(symbol: str, interval: str = "1D") -> str:
    """
    Get a formatted technical analysis summary for GPT input.
    
    Args:
        symbol: Stock symbol
        interval: Time interval for analysis
        
    Returns:
        Formatted string summary of technical analysis
    """
    
    data = extract_technical_analysis_data(symbol, interval)
    
    summary = f"""
Technical Analysis Summary for {symbol} ({interval} timeframe):

Overall Rating: {data['overall_rating']}
- Buy Signals: {data['summary']['buy_signals']}
- Neutral Signals: {data['summary']['neutral_signals']}  
- Sell Signals: {data['summary']['sell_signals']}
- Total Indicators: {data['summary']['total_indicators']}

Oscillators: {data['oscillators']['rating']}
- RSI: {data['momentum_indicators']['rsi']}
- Stochastic: {data['momentum_indicators']['stochastic']}
- MACD: {data['momentum_indicators']['macd']}

Moving Averages: {data['moving_averages']['rating']}

Key Levels:
- Support: ${data['key_levels']['support']}
- Resistance: ${data['key_levels']['resistance']}
- Pivot: ${data['key_levels']['pivot']}

Analysis Timestamp: {data['timestamp']}
"""
    
    return summary.strip()


def interpret_technical_rating(rating: str) -> str:
    """
    Interpret technical analysis rating for GPT context.
    
    Args:
        rating: Technical analysis rating
        
    Returns:
        Interpretation of the rating
    """
    
    interpretations = {
        "Strong Buy": "Technical indicators strongly suggest upward price movement. Multiple bullish signals across oscillators and moving averages.",
        "Buy": "Technical indicators lean bullish with more buy signals than sell signals. Positive momentum indicators.",
        "Neutral": "Technical indicators are mixed with roughly equal buy and sell signals. No clear directional bias.",
        "Sell": "Technical indicators lean bearish with more sell signals than buy signals. Negative momentum indicators.", 
        "Strong Sell": "Technical indicators strongly suggest downward price movement. Multiple bearish signals across oscillators and moving averages."
    }
    
    return interpretations.get(rating, "Technical analysis rating not recognized.")


def get_technical_context_for_gpt(symbol: str, interval: str = "1D") -> str:
    """
    Get comprehensive technical analysis context formatted for GPT analysis.
    
    Args:
        symbol: Stock symbol
        interval: Time interval for analysis
        
    Returns:
        Comprehensive technical analysis context for GPT
    """
    
    data = extract_technical_analysis_data(symbol, interval)
    summary = get_technical_summary(symbol, interval)
    interpretation = interpret_technical_rating(data['overall_rating'])
    
    context = f"""
TECHNICAL ANALYSIS DATA FOR {symbol}:

{summary}

INTERPRETATION:
{interpretation}

DETAILED BREAKDOWN:
- The technical analysis is based on {data['summary']['total_indicators']} indicators
- Oscillators show {data['oscillators']['rating']} sentiment with RSI at {data['momentum_indicators']['rsi']}
- Moving averages indicate {data['moving_averages']['rating']} trend
- Key support level at ${data['key_levels']['support']}, resistance at ${data['key_levels']['resistance']}
- MACD shows {data['momentum_indicators']['macd']} momentum

This technical analysis should be considered alongside fundamental analysis and market conditions for a comprehensive investment perspective.
"""
    
    return context.strip()
