"""
Stock Financials Widget Generator

Generates HTML for TradingView Stock Financials widgets
that display comprehensive financial data for fundamental analysis.
"""

import json
from typing import Literal, Union


def generate_stock_financials_widget(
    symbol: str,
    display_mode: Literal["regular", "compact"] = "regular",
    color_theme: Literal["light", "dark"] = "light",
    is_transparent: bool = False,
    width: Union[int, str] = "100%",
    height: Union[int, str] = 400,
    large_chart_url: str = ""
) -> str:
    """
    Generate HTML for TradingView Stock Financials widget.
    
    Args:
        symbol: Stock symbol (e.g., "AAPL", "NASDAQ:AAPL")
        display_mode: Display mode - "regular" or "compact"
        color_theme: Widget color theme
        is_transparent: Whether to use transparent background
        width: Widget width in pixels or percentage
        height: Widget height in pixels
        large_chart_url: URL for large chart view
        
    Returns:
        HTML string containing the TradingView Stock Financials widget
    """
    
    # Ensure symbol is properly formatted
    if ":" not in symbol:
        symbol = f"NASDAQ:{symbol.upper()}"
    
    widget_config = {
        "isTransparent": is_transparent,
        "largeChartUrl": large_chart_url,
        "displayMode": display_mode,
        "width": width,
        "height": height,
        "colorTheme": color_theme,
        "symbol": symbol,
        "locale": "en"
    }
    
    widget_html = f"""
    <!-- TradingView Stock Financials Widget BEGIN -->
    <div class="tradingview-widget-container" style="width: 100%; height: {height}px;">
        <div class="tradingview-widget-container__widget"></div>
        <div class="tradingview-widget-copyright">
            <a href="https://www.tradingview.com/symbols/{symbol}/financials-overview/" 
               rel="noopener nofollow" target="_blank">
                <span class="blue-text">{symbol} financials</span>
            </a>
            <span class="trademark"> by TradingView</span>
        </div>
        <script type="text/javascript" 
                src="https://s3.tradingview.com/external-embedding/embed-widget-financials.js" 
                async>
        {json.dumps(widget_config, indent=2)}
        </script>
    </div>
    <!-- TradingView Stock Financials Widget END -->
    """
    
    return widget_html


def generate_compact_financials_widget(symbol: str) -> str:
    """
    Generate a compact financials widget for embedding in reports.
    
    Args:
        symbol: Stock symbol
        
    Returns:
        HTML string for compact financials widget
    """
    return generate_stock_financials_widget(
        symbol=symbol,
        display_mode="compact",
        width="100%",
        height=300,
        is_transparent=True
    )


def generate_detailed_financials_widget(symbol: str) -> str:
    """
    Generate a detailed financials widget for comprehensive analysis.
    
    Args:
        symbol: Stock symbol
        
    Returns:
        HTML string for detailed financials widget
    """
    return generate_stock_financials_widget(
        symbol=symbol,
        display_mode="regular",
        width="100%",
        height=500,
        is_transparent=False
    )
