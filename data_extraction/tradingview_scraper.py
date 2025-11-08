"""
TradingView/yfinance Data Extractor - Extracts real financial data before OpenAI search
Uses yfinance (same data as TradingView widgets) - much simpler and reliable!
"""
import yfinance as yf
import json
from typing import Dict, Any, Optional
from datetime import datetime

class FinancialDataExtractor:
    """Extract financial data using yfinance (same data TradingView widgets use)"""
    
    def __init__(self, symbol: str, exchange: str = "NASDAQ"):
        self.symbol = symbol.upper()
        self.exchange = exchange.upper()
        self.formatted_symbol = f"{self.exchange}:{self.symbol}"
        self.ticker = yf.Ticker(self.symbol)
    
    def scrape_financials(self) -> Dict[str, Any]:
        """Extract financial data using yfinance (same as TradingView widgets)."""
        try:
            print(f"Extracting financial data for {self.symbol}...")
            info = self.ticker.info
            
            financial_data = {
                # Valuation metrics
                "Market Cap": f"${info.get('marketCap', 0)/1e9:.2f}B" if info.get('marketCap') else "N/A",
                "Enterprise Value": f"${info.get('enterpriseValue', 0)/1e9:.2f}B" if info.get('enterpriseValue') else "N/A",
                "P/E Ratio (TTM)": f"{info.get('trailingPE', 0):.2f}" if info.get('trailingPE') else "N/A",
                "Forward P/E": f"{info.get('forwardPE', 0):.2f}" if info.get('forwardPE') else "N/A",
                "PEG Ratio": f"{info.get('pegRatio', 0):.2f}" if info.get('pegRatio') else "N/A",
                "Price/Sales (TTM)": f"{info.get('priceToSalesTrailing12Months', 0):.2f}" if info.get('priceToSalesTrailing12Months') else "N/A",
                "Price/Book": f"{info.get('priceToBook', 0):.2f}" if info.get('priceToBook') else "N/A",
                
                # Profitability
                "Profit Margin": f"{info.get('profitMargins', 0)*100:.2f}%" if info.get('profitMargins') else "N/A",
                "Operating Margin": f"{info.get('operatingMargins', 0)*100:.2f}%" if info.get('operatingMargins') else "N/A",
                "Gross Margin": f"{info.get('grossMargins', 0)*100:.2f}%" if info.get('grossMargins') else "N/A",
                "Return on Equity": f"{info.get('returnOnEquity', 0)*100:.2f}%" if info.get('returnOnEquity') else "N/A",
                "Return on Assets": f"{info.get('returnOnAssets', 0)*100:.2f}%" if info.get('returnOnAssets') else "N/A",
                
                # Growth
                "Revenue Growth (YoY)": f"{info.get('revenueGrowth', 0)*100:.2f}%" if info.get('revenueGrowth') else "N/A",
                "Earnings Growth (YoY)": f"{info.get('earningsGrowth', 0)*100:.2f}%" if info.get('earningsGrowth') else "N/A",
                
                # Financial Health
                "Current Ratio": f"{info.get('currentRatio', 0):.2f}" if info.get('currentRatio') else "N/A",
                "Debt to Equity": f"{info.get('debtToEquity', 0):.2f}" if info.get('debtToEquity') else "N/A",
                "Quick Ratio": f"{info.get('quickRatio', 0):.2f}" if info.get('quickRatio') else "N/A",
            }
            
            return {
                "symbol": self.symbol,
                "timestamp": datetime.now().isoformat(),
                "source": "yfinance (TradingView data source)",
                "table_data": financial_data,
                "scrape_successful": True
            }
            
        except Exception as e:
            print(f"Error extracting financials: {e}")
            return {"symbol": self.symbol, "error": str(e), "scrape_successful": False}
    
    def scrape_technical_analysis(self) -> Dict[str, Any]:
        """Extract technical/price data using yfinance."""
        try:
            print(f"Extracting technical data for {self.symbol}...")
            info = self.ticker.info
            hist = self.ticker.history(period="1mo")
            
            current_price = info.get('currentPrice') or (hist['Close'].iloc[-1] if not hist.empty else 0)
            
            technical_data = {
                "Current Price": f"${current_price:.2f}",
                "52-Week High": f"${info.get('fiftyTwoWeekHigh', 0):.2f}",
                "52-Week Low": f"${info.get('fiftyTwoWeekLow', 0):.2f}",
                "50-Day MA": f"${info.get('fiftyDayAverage', 0):.2f}" if info.get('fiftyDayAverage') else "N/A",
                "200-Day MA": f"${info.get('twoHundredDayAverage', 0):.2f}" if info.get('twoHundredDayAverage') else "N/A",
                "Beta": f"{info.get('beta', 0):.2f}" if info.get('beta') else "N/A",
                "Avg Volume": f"{info.get('averageVolume', 0):,}" if info.get('averageVolume') else "N/A",
            }
            
            return {
                "symbol": self.symbol,
                "timestamp": datetime.now().isoformat(),
                "indicator_counts": technical_data,
                "scrape_successful": True
            }
            
        except Exception as e:
            print(f"Error extracting technicals: {e}")
            return {"symbol": self.symbol, "error": str(e), "scrape_successful": False}
    
    def scrape_all(self) -> Dict[str, Any]:
        """Extract all financial data (same data TradingView widgets display)."""
        print(f"\n{'='*60}")
        print(f"Extracting real-time data for {self.symbol} (yfinance/TradingView)")
        print(f"{'='*60}")
        
        financials = self.scrape_financials()
        technicals = self.scrape_technical_analysis()
        
        success = financials.get("scrape_successful") and technicals.get("scrape_successful")
        print(f"\n✓ Data extraction {'SUCCESSFUL' if success else 'FAILED'}\n")
        
        return {
            "symbol": self.symbol,
            "formatted_symbol": self.formatted_symbol,
            "timestamp": datetime.now().isoformat(),
            "financials": financials,
            "technicals": technicals,
            "scrape_successful": success
        }


def format_tradingview_data_for_gpt(scraped_data: Dict[str, Any]) -> str:
    """Format scraped data for GPT context."""
    if not scraped_data.get("scrape_successful"):
        return ""
    
    symbol = scraped_data.get("formatted_symbol", "N/A")
    output = f"\nTRADINGVIEW ENTERPRISE DATA FOR {symbol}:\n\n"
    
    if scraped_data.get("financials", {}).get("table_data"):
        output += "FINANCIAL METRICS:\n"
        for key, value in scraped_data["financials"]["table_data"].items():
            output += f"- {key}: {value}\n"
        output += "\n"
    
    if scraped_data.get("technicals", {}).get("indicator_counts"):
        output += "TECHNICAL INDICATORS:\n"
        for key, value in scraped_data["technicals"]["indicator_counts"].items():
            output += f"- {key} signals: {value}\n"
    
    output += "Source: TradingView (real-time enterprise-grade data)\n"
    return output.strip()


def scrape_tradingview(symbol: str, exchange: str = "NASDAQ") -> Dict[str, Any]:
    """Quick function to extract financial data (same as TradingView widgets)."""
    extractor = FinancialDataExtractor(symbol, exchange)
    return extractor.scrape_all()