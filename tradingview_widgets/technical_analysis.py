"""
Technical Analysis Widget Generator

Generates HTML for TradingView Technical Analysis widgets
that can be embedded in Streamlit applications.
"""

import json
from typing import Literal, Union


def generate_technical_analysis_widget(
    symbol: str,
    interval: str = "1m",
    display_mode: Literal["single", "multiple"] = "single",
    color_theme: Literal["light", "dark"] = "light",
    is_transparent: bool = False,
    width: Union[int, str] = 425,
    height: Union[int, str] = 450,
    show_interval_tabs: bool = True
) -> str:
    """
    Generate HTML for TradingView Technical Analysis widget.
    
    Args:
        symbol: Stock symbol (e.g., "AAPL", "NASDAQ:AAPL")
        interval: Time interval for analysis (1m, 5m, 15m, 1h, 4h, 1D, 1W, 1M)
        display_mode: Display mode - "single" for summary gauge, "multiple" for detailed view
        color_theme: Widget color theme
        is_transparent: Whether to use transparent background
        width: Widget width in pixels or percentage
        height: Widget height in pixels
        show_interval_tabs: Whether to show interval selection tabs
        
    Returns:
        HTML string containing the TradingView Technical Analysis widget
    """
    
    # Remove any existing exchange prefix (e.g., "NYSE:OXY" -> "OXY")
    # TradingView auto-redirects to correct exchange
    if ":" in symbol:
        symbol = symbol.split(":")[1]
    
    symbol = symbol.upper()
    
    widget_config = {
        "colorTheme": color_theme,
        "displayMode": display_mode,
        "isTransparent": is_transparent,
        "locale": "en",
        "interval": interval,
        "disableInterval": False,
        "width": width,
        "height": height,
        "symbol": symbol,
        "showIntervalTabs": show_interval_tabs
    }
    
    widget_html = f"""
    <!-- TradingView Technical Analysis Widget BEGIN -->
    <div class="tradingview-widget-container" style="width: 100%; height: {height}px;">
        <div class="tradingview-widget-container__widget"></div>
        <div class="tradingview-widget-copyright">
            <a href="https://www.tradingview.com/symbols/{symbol}/technicals/" 
               rel="noopener nofollow" target="_blank">
                <span class="blue-text">{symbol} technical analysis</span>
            </a>
            <span class="trademark"> by TradingView</span>
        </div>
        <script type="text/javascript" 
                src="https://s3.tradingview.com/external-embedding/embed-widget-technical-analysis.js" 
                async>
        {json.dumps(widget_config, indent=2)}
        </script>
    </div>
    <!-- TradingView Technical Analysis Widget END -->
    """
    
    return widget_html


def generate_technical_analysis_summary_widget(symbol: str) -> str:
    """
    Generate a compact technical analysis summary widget for reports.
    
    Args:
        symbol: Stock symbol
        
    Returns:
        HTML string for compact technical analysis widget
    """
    return generate_technical_analysis_widget(
        symbol=symbol,
        display_mode="single",
        width="100%",
        height=300,
        show_interval_tabs=False,
        is_transparent=True
    )


def generate_technical_analysis_detailed_widget(symbol: str) -> str:
    """
    Generate a detailed technical analysis widget with multiple gauges.
    
    Args:
        symbol: Stock symbol
        
    Returns:
        HTML string for detailed technical analysis widget
    """
    return generate_technical_analysis_widget(
        symbol=symbol,
        display_mode="multiple",
        width="100%",
        height=500,
        show_interval_tabs=True,
        is_transparent=False
    )
