"""
Stock Chart Widget Generator

Generates HTML for TradingView Advanced Chart widgets
that display interactive price charts with technical indicators.
"""

import json
from typing import List, Dict, Literal, Union


def generate_stock_chart_widget(
    symbol: str,
    interval: str = "D",
    timezone: str = "Etc/UTC",
    theme: Literal["light", "dark"] = "light",
    style: str = "1",
    width: Union[int, str] = "100%",
    height: Union[int, str] = 500,
    hide_volume: bool = False,
    hide_side_toolbar: bool = False,
    hide_top_toolbar: bool = False,
    allow_symbol_change: bool = True,
    comparison_symbols: List[Dict[str, str]] = None,
    with_date_ranges: bool = True,
    calendar: bool = False,
    support_host: str = "https://www.tradingview.com"
) -> str:
    """
    Generate HTML for TradingView Advanced Chart widget.
    
    Args:
        symbol: Stock symbol (e.g., "AAPL", "NASDAQ:AAPL")
        interval: Chart interval (1, 3, 5, 15, 30, 60, 120, 180, 240, D, W, M)
        timezone: Chart timezone
        theme: Chart theme
        style: Chart style (1=bars, 2=candles, 3=line, etc.)
        width: Widget width
        height: Widget height
        hide_volume: Whether to hide volume
        hide_side_toolbar: Whether to hide side toolbar
        hide_top_toolbar: Whether to hide top toolbar
        allow_symbol_change: Whether to allow symbol changes
        comparison_symbols: List of symbols to compare
        with_date_ranges: Whether to show date range selector
        calendar: Whether to show calendar
        support_host: TradingView host URL
        
    Returns:
        HTML string containing the TradingView Advanced Chart widget
    """
    
    # Remove any existing exchange prefix (e.g., "NYSE:OXY" -> "OXY")
    # TradingView auto-redirects to correct exchange
    if ":" in symbol:
        symbol = symbol.split(":")[1]
    
    symbol = symbol.upper()
    
    if comparison_symbols is None:
        comparison_symbols = []
    
    widget_config = {
        "autosize": True,
        "symbol": symbol,
        "interval": interval,
        "timezone": timezone,
        "theme": theme,
        "style": style,
        "locale": "en",
        "toolbar_bg": "#f1f3f6",
        "enable_publishing": False,
        "hide_volume": hide_volume,
        "hide_side_toolbar": hide_side_toolbar,
        "hide_top_toolbar": hide_top_toolbar,
        "allow_symbol_change": allow_symbol_change,
        "compareSymbols": comparison_symbols,
        "withdateranges": with_date_ranges,
        "calendar": calendar,
        "support_host": support_host
    }
    
    widget_html = f"""
    <!-- TradingView Advanced Chart Widget BEGIN -->
    <div class="tradingview-widget-container" style="width: 100%; height: {height}px;">
        <div class="tradingview-widget-container__widget" style="height: calc(100% - 32px); width: 100%;"></div>
        <div class="tradingview-widget-copyright">
            <a href="https://www.tradingview.com/symbols/{symbol}/" 
               rel="noopener nofollow" target="_blank">
                <span class="blue-text">{symbol} chart</span>
            </a>
            <span class="trademark"> by TradingView</span>
        </div>
        <script type="text/javascript" 
                src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js" 
                async>
        {json.dumps(widget_config, indent=2)}
        </script>
    </div>
    <!-- TradingView Advanced Chart Widget END -->
    """
    
    return widget_html


def generate_simple_chart_widget(symbol: str) -> str:
    """
    Generate a simple chart widget for reports.
    
    Args:
        symbol: Stock symbol
        
    Returns:
        HTML string for simple chart widget
    """
    return generate_stock_chart_widget(
        symbol=symbol,
        height=400,
        hide_side_toolbar=True,
        hide_top_toolbar=True,
        allow_symbol_change=False,
        with_date_ranges=False
    )


def generate_comparison_chart_widget(symbol: str, comparison_symbols: List[str]) -> str:
    """
    Generate a chart widget with comparison symbols.
    
    Args:
        symbol: Primary stock symbol
        comparison_symbols: List of symbols to compare
        
    Returns:
        HTML string for comparison chart widget
    """
    # Format comparison symbols
    formatted_comparisons = [
        {"symbol": comp_symbol, "position": "SameScale"} 
        for comp_symbol in comparison_symbols
    ]
    
    return generate_stock_chart_widget(
        symbol=symbol,
        height=500,
        style="2",  # Candlestick style for comparison
        hide_volume=False,
        comparison_symbols=formatted_comparisons,
        hide_side_toolbar=False,
        hide_top_toolbar=False
    )
