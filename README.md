# Financial Research App

AI-powered equity research terminal built with Streamlit and Perplexity AI. Analyzes SEC filings, generates fundamental health scores, and provides real-time market data.

## Features

- 🔍 **SEC Filing Analysis** - Automated extraction from 10-Q, 10-K, and 8-K filings
- 📊 **Fundamental Health Scoring** - 0-100 score based on balance sheet, growth, profitability, momentum, and risk factors
- 📈 **TradingView Integration** - Live charts and financial metrics
- 🎯 **Real-Time Data** - Current market data, analyst ratings, and price targets
- ⚡ **Fast** - 2-call API architecture for efficient data retrieval

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure API Key

Copy `.env.example` to `.env` and add your API key:

```bash
# On Windows
copy .env.example .env

# Then edit .env and add your key:
PERPLEXITY_API_KEY=your_actual_api_key_here
```

Get your API key from: https://www.perplexity.ai/settings/api

**⚠️ NOTE:** This repo includes `.env` for Netlify deployment. Repo must remain PRIVATE.

### 3. Run the App

```bash
streamlit run app.py
```

The app will open in your browser at `http://localhost:8501`

## Usage

1. Enter a stock ticker (e.g., `AAPL`, `NVDA`, `TSLA`)
2. Click **GENERATE**
3. Wait 10-15 seconds for analysis
4. Review the fundamental health score and key insights

## Project Structure

```
complete-financial-research-app/
├── app.py                          # Main Streamlit application
├── utils.py                        # Core logic and API interactions
├── .env                            # API keys (DO NOT COMMIT)
├── requirements.txt                # Python dependencies
│
├── data_extraction/                # Data extraction utilities
│   ├── financial_extractor.py
│   ├── technical_extractor.py
│   └── tradingview_scraper.py
│
└── tradingview_widgets/            # TradingView widget generators
    ├── stock_chart.py
    ├── stock_financials.py
    ├── technical_analysis.py
    └── widget_utils.py
```

## Tech Stack

- **Frontend:** Streamlit
- **Data Source:** Perplexity AI (SEC search mode)
- **Market Data:** TradingView widgets
- **Language:** Python 3.11+

## Disclaimer

This tool provides financial analysis for educational and informational purposes only. It does not constitute investment advice. Always consult with a qualified financial advisor before making investment decisions.

## License

Private project - All rights reserved

