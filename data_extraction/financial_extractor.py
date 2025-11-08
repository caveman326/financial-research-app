"""
Financial Data Extractor

Extracts financial metrics and fundamental data for use in GPT analysis.
This module provides structured financial data that would typically come from
TradingView's financials widget.
"""

from typing import Dict, Any, Optional
import random
from datetime import datetime, timedelta


def extract_financial_metrics(symbol: str) -> Dict[str, Any]:
    """
    Extract financial metrics for a symbol.
    
    Note: This is a simulation of financial data extraction.
    In production, this would integrate with TradingView's API or
    financial data providers to get real metrics.
    
    Args:
        symbol: Stock symbol
        
    Returns:
        Dictionary containing financial metrics
    """
    
    # Simulate realistic financial metrics
    # In production, this would come from actual financial data
    
    # Generate market cap (in billions)
    market_cap = round(random.uniform(50, 3000), 2)
    
    # Generate share price
    share_price = round(random.uniform(50, 500), 2)
    
    # Calculate shares outstanding
    shares_outstanding = round((market_cap * 1e9) / share_price / 1e6, 2)  # in millions
    
    financial_data = {
        "symbol": symbol,
        "timestamp": datetime.now().isoformat(),
        "market_data": {
            "market_cap": f"${market_cap}B",
            "market_cap_raw": market_cap * 1e9,
            "share_price": f"${share_price}",
            "shares_outstanding": f"{shares_outstanding}M",
            "52_week_high": round(share_price * random.uniform(1.1, 1.5), 2),
            "52_week_low": round(share_price * random.uniform(0.6, 0.9), 2),
            "volume": f"{random.randint(10, 100)}M",
            "avg_volume": f"{random.randint(15, 80)}M"
        },
        "valuation_metrics": {
            "pe_ratio": round(random.uniform(15, 35), 2),
            "forward_pe": round(random.uniform(12, 30), 2),
            "peg_ratio": round(random.uniform(0.8, 2.5), 2),
            "price_to_book": round(random.uniform(2, 8), 2),
            "price_to_sales": round(random.uniform(3, 15), 2),
            "enterprise_value": f"${round(market_cap * random.uniform(1.1, 1.3), 2)}B"
        },
        "profitability": {
            "gross_margin": f"{round(random.uniform(35, 75), 1)}%",
            "operating_margin": f"{round(random.uniform(15, 35), 1)}%",
            "net_margin": f"{round(random.uniform(10, 25), 1)}%",
            "roe": f"{round(random.uniform(15, 35), 1)}%",
            "roa": f"{round(random.uniform(8, 20), 1)}%",
            "roic": f"{round(random.uniform(12, 28), 1)}%"
        },
        "financial_health": {
            "debt_to_equity": round(random.uniform(0.2, 1.5), 2),
            "current_ratio": round(random.uniform(1.2, 3.0), 2),
            "quick_ratio": round(random.uniform(0.8, 2.5), 2),
            "cash_per_share": f"${round(random.uniform(5, 50), 2)}",
            "total_cash": f"${round(random.uniform(10, 200), 2)}B"
        },
        "growth_metrics": {
            "revenue_growth_yoy": f"{round(random.uniform(-5, 25), 1)}%",
            "earnings_growth_yoy": f"{round(random.uniform(-10, 30), 1)}%",
            "revenue_growth_qoq": f"{round(random.uniform(-2, 8), 1)}%",
            "earnings_growth_qoq": f"{round(random.uniform(-5, 15), 1)}%"
        },
        "dividend_info": {
            "dividend_yield": f"{round(random.uniform(0, 4), 2)}%",
            "dividend_per_share": f"${round(random.uniform(0, 8), 2)}",
            "payout_ratio": f"{round(random.uniform(20, 60), 1)}%",
            "ex_dividend_date": (datetime.now() - timedelta(days=random.randint(1, 90))).strftime("%Y-%m-%d")
        }
    }
    
    return financial_data


def get_financial_summary(symbol: str) -> str:
    """
    Get a formatted financial summary for GPT input.
    
    Args:
        symbol: Stock symbol
        
    Returns:
        Formatted string summary of financial metrics
    """
    
    data = extract_financial_metrics(symbol)
    
    summary = f"""
Financial Summary for {symbol}:

MARKET DATA:
- Market Cap: {data['market_data']['market_cap']}
- Share Price: {data['market_data']['share_price']}
- Shares Outstanding: {data['market_data']['shares_outstanding']}
- 52-Week Range: ${data['market_data']['52_week_low']} - ${data['market_data']['52_week_high']}
- Volume: {data['market_data']['volume']} (Avg: {data['market_data']['avg_volume']})

VALUATION METRICS:
- P/E Ratio: {data['valuation_metrics']['pe_ratio']}
- Forward P/E: {data['valuation_metrics']['forward_pe']}
- PEG Ratio: {data['valuation_metrics']['peg_ratio']}
- Price-to-Book: {data['valuation_metrics']['price_to_book']}
- Price-to-Sales: {data['valuation_metrics']['price_to_sales']}

PROFITABILITY:
- Gross Margin: {data['profitability']['gross_margin']}
- Operating Margin: {data['profitability']['operating_margin']}
- Net Margin: {data['profitability']['net_margin']}
- ROE: {data['profitability']['roe']}
- ROA: {data['profitability']['roa']}

FINANCIAL HEALTH:
- Debt-to-Equity: {data['financial_health']['debt_to_equity']}
- Current Ratio: {data['financial_health']['current_ratio']}
- Quick Ratio: {data['financial_health']['quick_ratio']}
- Cash per Share: {data['financial_health']['cash_per_share']}

GROWTH:
- Revenue Growth (YoY): {data['growth_metrics']['revenue_growth_yoy']}
- Earnings Growth (YoY): {data['growth_metrics']['earnings_growth_yoy']}

DIVIDEND:
- Dividend Yield: {data['dividend_info']['dividend_yield']}
- Dividend per Share: {data['dividend_info']['dividend_per_share']}

Data as of: {data['timestamp']}
"""
    
    return summary.strip()


def analyze_financial_health(symbol: str) -> str:
    """
    Analyze financial health and provide interpretation.
    
    Args:
        symbol: Stock symbol
        
    Returns:
        Financial health analysis
    """
    
    data = extract_financial_metrics(symbol)
    
    # Extract numeric values for analysis
    debt_to_equity = data['financial_health']['debt_to_equity']
    current_ratio = data['financial_health']['current_ratio']
    quick_ratio = data['financial_health']['quick_ratio']
    
    # Analyze debt levels
    if debt_to_equity < 0.3:
        debt_analysis = "Low debt levels indicate conservative financial management"
    elif debt_to_equity < 0.7:
        debt_analysis = "Moderate debt levels are manageable"
    else:
        debt_analysis = "High debt levels may indicate financial risk"
    
    # Analyze liquidity
    if current_ratio > 2.0:
        liquidity_analysis = "Strong liquidity position"
    elif current_ratio > 1.5:
        liquidity_analysis = "Adequate liquidity"
    else:
        liquidity_analysis = "Potential liquidity concerns"
    
    analysis = f"""
Financial Health Analysis for {symbol}:

DEBT ANALYSIS: {debt_analysis} (D/E: {debt_to_equity})
LIQUIDITY ANALYSIS: {liquidity_analysis} (Current Ratio: {current_ratio})

The company shows {"strong" if current_ratio > 2.0 and debt_to_equity < 0.5 else "moderate" if current_ratio > 1.5 and debt_to_equity < 1.0 else "concerning"} financial health metrics.
"""
    
    return analysis.strip()


def get_financial_context_for_gpt(symbol: str) -> str:
    """
    Get comprehensive financial context formatted for GPT analysis.
    
    Args:
        symbol: Stock symbol
        
    Returns:
        Comprehensive financial context for GPT
    """
    
    summary = get_financial_summary(symbol)
    health_analysis = analyze_financial_health(symbol)
    
    context = f"""
FUNDAMENTAL FINANCIAL DATA FOR {symbol}:

{summary}

{health_analysis}

This financial data should be used alongside technical analysis and market conditions to provide comprehensive investment insights. Consider the company's competitive position, industry trends, and macroeconomic factors when interpreting these metrics.
"""
    
    return context.strip()
