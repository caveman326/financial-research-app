"""
Widget Utilities

Utility functions for TradingView widget integration,
including symbol validation and data extraction.
"""

import re
import requests
from typing import Optional, Dict, Any
import time


def validate_symbol(symbol: str) -> bool:
    """
    Validate if a symbol is properly formatted for TradingView.
    
    Args:
        symbol: Stock symbol to validate
        
    Returns:
        True if symbol is valid, False otherwise
    """
    if not symbol or not isinstance(symbol, str):
        return False
    
    # Remove whitespace and convert to uppercase
    symbol = symbol.strip().upper()
    
    # Basic symbol validation (letters, numbers, dots, colons)
    if not re.match(r'^[A-Z0-9:.]+$', symbol):
        return False
    
    # Check length (reasonable limits)
    if len(symbol) < 1 or len(symbol) > 20:
        return False
    
    return True


def format_symbol_for_tradingview(symbol: str, exchange: Optional[str] = None) -> str:
    """
    Format a symbol for TradingView widgets.
    
    Args:
        symbol: Stock symbol
        exchange: Optional exchange prefix (e.g., "NASDAQ", "NYSE")
        
    Returns:
        Properly formatted symbol for TradingView
    """
    if not validate_symbol(symbol):
        raise ValueError(f"Invalid symbol: {symbol}")
    
    symbol = symbol.strip().upper()
    
    # If symbol already has exchange prefix, return as-is
    if ":" in symbol:
        return symbol
    
    # If exchange is specified, use it
    if exchange:
        return f"{exchange.upper()}:{symbol}"
    
    # Default to NASDAQ for common US stocks
    # This is a simple heuristic - in production, you might want
    # to use a symbol lookup service
    return f"NASDAQ:{symbol}"


def extract_symbol_data(symbol: str) -> Dict[str, Any]:
    """
    Extract basic information about a symbol for widget configuration.
    
    Args:
        symbol: Stock symbol
        
    Returns:
        Dictionary containing symbol information
    """
    formatted_symbol = format_symbol_for_tradingview(symbol)
    
    # Split exchange and symbol
    if ":" in formatted_symbol:
        exchange, ticker = formatted_symbol.split(":", 1)
    else:
        exchange = "NASDAQ"
        ticker = formatted_symbol
    
    return {
        "original_symbol": symbol,
        "formatted_symbol": formatted_symbol,
        "exchange": exchange,
        "ticker": ticker,
        "tradingview_url": f"https://www.tradingview.com/symbols/{formatted_symbol}/",
        "technicals_url": f"https://www.tradingview.com/symbols/{formatted_symbol}/technicals/",
        "financials_url": f"https://www.tradingview.com/symbols/{formatted_symbol}/financials-overview/"
    }


def generate_widget_id(widget_type: str, symbol: str) -> str:
    """
    Generate a unique ID for a widget instance.
    
    Args:
        widget_type: Type of widget (e.g., "technical_analysis", "financials")
        symbol: Stock symbol
        
    Returns:
        Unique widget ID
    """
    timestamp = str(int(time.time()))
    clean_symbol = re.sub(r'[^A-Z0-9]', '', symbol.upper())
    return f"tradingview_{widget_type}_{clean_symbol}_{timestamp}"


def create_widget_container_html(widget_content: str, widget_id: str, custom_css: str = "") -> str:
    """
    Wrap widget content in a container with optional custom CSS.
    
    Args:
        widget_content: The widget HTML content
        widget_id: Unique widget ID
        custom_css: Optional custom CSS for the container
        
    Returns:
        Complete HTML with container and styling
    """
    container_html = f"""
    <div id="{widget_id}" class="tradingview-widget-wrapper">
        <style>
        #{widget_id} {{
            margin: 10px 0;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            {custom_css}
        }}
        #{widget_id} .tradingview-widget-container {{
            width: 100%;
            height: 100%;
        }}
        </style>
        {widget_content}
    </div>
    """
    return container_html


def get_common_symbols() -> Dict[str, str]:
    """
    Get a dictionary of common stock symbols and their full names.
    
    Returns:
        Dictionary mapping symbols to company names
    """
    return {
        "AAPL": "Apple Inc.",
        "MSFT": "Microsoft Corporation",
        "GOOGL": "Alphabet Inc.",
        "AMZN": "Amazon.com Inc.",
        "TSLA": "Tesla Inc.",
        "META": "Meta Platforms Inc.",
        "NVDA": "NVIDIA Corporation",
        "NFLX": "Netflix Inc.",
        "AMD": "Advanced Micro Devices Inc.",
        "INTC": "Intel Corporation",
        "CRM": "Salesforce Inc.",
        "ORCL": "Oracle Corporation",
        "ADBE": "Adobe Inc.",
        "PYPL": "PayPal Holdings Inc.",
        "UBER": "Uber Technologies Inc.",
        "SPOT": "Spotify Technology S.A.",
        "ZOOM": "Zoom Video Communications Inc.",
        "SQ": "Block Inc.",
        "SHOP": "Shopify Inc.",
        "ROKU": "Roku Inc."
    }


def suggest_symbol_corrections(symbol: str) -> list:
    """
    Suggest corrections for potentially misspelled symbols.
    
    Args:
        symbol: Input symbol that might be misspelled
        
    Returns:
        List of suggested corrections
    """
    common_symbols = get_common_symbols()
    symbol_upper = symbol.upper()
    
    suggestions = []
    
    # Exact match
    if symbol_upper in common_symbols:
        return [symbol_upper]
    
    # Partial matches
    for sym in common_symbols:
        if symbol_upper in sym or sym in symbol_upper:
            suggestions.append(sym)
    
    # Fuzzy matching (simple implementation)
    for sym in common_symbols:
        if len(set(symbol_upper) & set(sym)) >= min(len(symbol_upper), len(sym)) * 0.6:
            suggestions.append(sym)
    
    return list(set(suggestions))[:5]  # Return top 5 unique suggestions
