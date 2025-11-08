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


