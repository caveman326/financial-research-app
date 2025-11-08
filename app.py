import streamlit as st
import utils
import json
import pandas as pd
from datetime import datetime
import time

# Page configuration
st.set_page_config(
    page_title="Equity Research",
    page_icon="■",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Minimal Bloomberg-style CSS
st.markdown("""
<style>
    /* Remove all Streamlit default styling */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Force black background everywhere */
    .stApp {
        background-color: #000000;
    }
    
    [data-testid="stAppViewContainer"] {
        background-color: #000000;
    }
    
    [data-testid="stHeader"] {
        background-color: #000000;
    }
    
    /* All text white by default - LARGER SIZE */
    .stApp, .stMarkdown, p, span, div, label {
        color: #FFFFFF !important;
        font-family: 'Courier New', monospace;
        font-size: 1.4rem;
    }
    
    /* Headers - subtle, not flashy */
    h1, h2, h3 {
        color: #FFFFFF !important;
        font-family: 'Courier New', monospace;
        font-weight: 400;
        letter-spacing: 0.05em;
    }
    
    h1 {
        font-size: 2.2rem;
        margin-bottom: 0.8rem;
        border-bottom: 2px solid #FFAA00;
        padding-bottom: 0.8rem;
        letter-spacing: 0.2em;
    }
    
    h2 {
        font-size: 1.5rem;
    }
    
    h3 {
        font-size: 1.2rem;
    }
    
    /* Input field - minimal border */
    .stTextInput > div > div > input {
        background-color: #000000;
        color: #FFFFFF;
        border: 2px solid #333333;
        border-radius: 0;
        font-family: 'Courier New', monospace;
        font-size: 1.2rem;
        padding: 0.85rem;
        transition: all 0.3s ease;
    }

    .stTextInput > div > div > input:focus {
        border: 2px solid #FFAA00;
        box-shadow: 0 0 12px rgba(255, 170, 0, 0.3);
    }
    
    .stTextInput > label {
        color: #999999 !important;
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        font-family: 'Courier New', monospace;
    }
    
    /* Button - minimal */
    .stButton > button {
        background-color: #000000;
        color: #FFFFFF;
        border: 2px solid #FFFFFF;
        border-radius: 0;
        padding: 0.85rem 3.5rem;
        font-family: 'Courier New', monospace;
        font-size: 1.1rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.15em;
        white-space: nowrap;
        transition: all 0.3s ease;
        box-shadow: 0 2px 4px rgba(255, 255, 255, 0.1);
        min-width: 160px;
    }

    .stButton > button:hover {
        background-color: #FFAA00;
        color: #000000;
        border: 2px solid #FFAA00;
        box-shadow: 0 4px 12px rgba(255, 170, 0, 0.4);
        transform: translateY(-1px);
    }
    
    .stButton > button:active {
        background-color: #CCCCCC;
    }
    
    .stButton > button:disabled {
        opacity: 0.3;
        cursor: not-allowed;
    }
    
    /* Info boxes - subtle */
    .stAlert {
        background-color: #000000;
        border: 1px solid #333333;
        border-left: 3px solid #666666;
        color: #CCCCCC;
        border-radius: 0;
        padding: 1rem;
        font-family: 'Courier New', monospace;
        font-size: 0.85rem;
    }
    
    /* Success message */
    .stSuccess {
        background-color: #000000;
        border: 1px solid #00FF00;
        color: #00FF00;
        border-radius: 0;
        padding: 0.5rem 1rem;
        font-family: 'Courier New', monospace;
        font-size: 0.85rem;
    }
    
    /* Error message */
    .stError {
        background-color: #000000;
        border: 1px solid #FF0000;
        color: #FF0000;
        border-radius: 0;
        padding: 0.5rem 1rem;
        font-family: 'Courier New', monospace;
        font-size: 0.85rem;
    }
    
    /* Warning */
    .stWarning {
        background-color: #000000;
        border: 1px solid #FFFF00;
        color: #FFFF00;
        border-radius: 0;
        padding: 0.5rem 1rem;
        font-family: 'Courier New', monospace;
        font-size: 0.85rem;
    }
    
    /* Expander - minimal */
    .streamlit-expanderHeader {
        background-color: #000000;
        color: #999999 !important;
        border: 1px solid #333333;
        border-radius: 0;
        font-family: 'Courier New', monospace;
        font-size: 0.85rem;
    }
    
    .streamlit-expanderContent {
        background-color: #000000;
        border: 1px solid #333333;
        border-top: none;
        border-radius: 0;
    }
    
    /* Spinner */
    .stSpinner > div {
        border-color: #FFFFFF transparent transparent transparent;
    }
    
    /* Progress text container */
    .progress-text {
        color: #999999;
        font-family: 'Courier New', monospace;
        font-size: 0.85rem;
        padding: 1rem;
        border: 1px solid #333333;
        margin: 1rem 0;
    }
    
    /* Report container - TERMINAL STYLE (not white card) */
    .report-container {
        max-width: 1200px;  /* Wider - use full space */
        background: #0a0a0a;  /* Dark, not black - subtle */
        padding: 2.5rem;
        margin: 2rem auto;
        font-family: 'Courier New', monospace;  /* Match terminal */
        font-size: 1.3rem;
        line-height: 2.2;
        border: 1px solid #333333;  /* Subtle border */
        border-left: 3px solid #FFAA00;  /* Bloomberg orange accent */
    }
    
    /* All text in report stays WHITE */
    .report-container,
    .report-container * {
        color: #FFFFFF !important;
        font-family: 'Courier New', monospace !important;
    }
    
    /* Section spacing */
    .section {
        margin-bottom: 2.5rem;
        padding-bottom: 2rem;
        border-bottom: 1px solid #222222;
    }
    
    .section:last-child {
        border-bottom: none;
    }
    
    /* Section headers - terminal style */
    .section-header {
        font-size: 0.85rem;
        font-weight: 700;
        color: #999999 !important;
        text-transform: uppercase;
        letter-spacing: 0.15em;
        margin-bottom: 1.2rem;
        border-bottom: 1px solid #222222;
        padding-bottom: 0.4rem;
    }
    
    /* Section 1: Company Overview - READABLE FORMAT */
    .one-liner {
        padding: 2rem;
        background: #111111;
        border-left: 3px solid #FFAA00;
        margin-bottom: 2rem;
    }
    
    .one-liner .company-name {
        font-size: 1.6rem;
        font-weight: 700;
        color: #FFAA00 !important;
        margin-bottom: 1.5rem;
        letter-spacing: 0.1em;
        padding-bottom: 0.5rem;
        border-bottom: 1px solid #333333;
    }
    
    .one-liner .info-line {
        margin-bottom: 1.2rem;
        display: block;
        line-height: 1.8;
    }
    
    .one-liner .info-label {
        display: block;
        color: #999999 !important;
        font-weight: 700;
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.15em;
        margin-bottom: 0.5rem;
    }
    
    .one-liner .info-text {
        display: block;
        color: #FFFFFF !important;
        font-size: 1.2rem;
        line-height: 1.9;
        padding-left: 1rem;
        border-left: 2px solid #333333;
    }
    
    /* Section 2: Metrics Grid */
    .metrics-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);  /* 4 columns across */
        gap: 1rem;
        margin-bottom: 2rem;
    }
    
    .metric-card {
        background: #111111;
        padding: 1rem;
        border: 1px solid #222222;
        border-left: 2px solid #333333;
    }
    
    .metric-label {
        font-size: 0.8rem;
        color: #666666 !important;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.6rem;
    }
    
    .metric-value {
        font-size: 2.2rem;
        font-weight: 700;
        color: #FFFFFF !important;
        margin-bottom: 0.4rem;
        font-family: 'Courier New', monospace !important;
    }
    
    .metric-status {
        font-size: 0.95rem;
        color: #00FF00 !important;  /* Terminal green */
    }
    
    .metric-status.warning {
        color: #FFAA00 !important;  /* Terminal orange */
    }
    
    .metric-context {
        font-size: 0.85rem;
        color: #999999 !important;
        margin-top: 0.4rem;
        font-style: italic;
        line-height: 1.5;
    }
    
    /* Section 3: Threat Level */
    .threat-level {
        display: flex;
        flex-direction: column;
        gap: 0.8rem;
    }
    
    .threat-item {
        display: flex;
        align-items: flex-start;
        gap: 1rem;
        padding: 0.8rem;
        background: #111111;
        border: 1px solid #222222;
    }
    
    .threat-indicator {
        font-size: 1.5rem;
        line-height: 1;
    }
    
    .threat-content {
        flex: 1;
    }
    
    .threat-label {
        font-weight: 700;
        color: #FFFFFF !important;
        margin-bottom: 0.4rem;
        font-size: 0.95rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    .threat-detail {
        font-size: 1.2rem;
        color: #CCCCCC !important;
        line-height: 1.8;
    }
    
    /* Section 4: Management Quote */
    .management-quote {
        padding: 1.5rem;
        background: #111111;
        border-left: 3px solid #666666;
        font-style: italic;
        font-size: 1.3rem;
        line-height: 2.0;
        color: #CCCCCC !important;
    }
    
    /* Section 5: Revenue Breakdown - FIXED */
    .revenue-breakdown {
        display: flex;
        flex-direction: column;
        gap: 0.8rem;
    }
    
    .revenue-item {
        display: flex;
        align-items: center;
        gap: 1rem;
    }
    
    .revenue-label {
        min-width: 180px;
        font-size: 0.95rem;
        color: #FFFFFF !important;
        font-weight: 600;
    }
    
    .revenue-bar-container {
        flex: 1;
        height: 32px;
        background: #111111;
        border: 1px solid #222222;
        position: relative;
        overflow: hidden;
    }
    
    .revenue-bar {
        height: 100%;
        background: #FFAA00;  /* Bloomberg orange */
        transition: width 0.3s ease;
    }
    
    .revenue-growth {
        min-width: 90px;
        text-align: right;
        font-size: 0.95rem;
        font-weight: 700;
        font-family: 'Courier New', monospace !important;
    }
    
    .revenue-growth.positive {
        color: #00FF00 !important;
    }
    
    .revenue-growth.negative {
        color: #FF0000 !important;
    }
    
    /* Section 6: Key Metric */
    .key-metric {
        padding: 2rem;
        background: #111111;
        border: 1px solid #333333;
        border-left: 3px solid #FFAA00;
        text-align: center;
    }
    
    .key-metric-label {
        font-size: 0.85rem;
        color: #666666 !important;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-bottom: 1rem;
    }
    
    .key-metric-value {
        font-size: 3.5rem;
        font-weight: 700;
        color: #FFAA00 !important;  /* Orange highlight */
        margin-bottom: 1rem;
        line-height: 1;
        font-family: 'Courier New', monospace !important;
    }
    
    .key-metric-explanation {
        font-size: 1.3rem;
        color: #CCCCCC !important;
        line-height: 2.0;
    }
    
    /* Mobile Responsive */
    @media (max-width: 640px) {
        .report-container {
            font-size: 1.0rem;
            padding: 1.5rem;
        }
        
        .metrics-grid {
            grid-template-columns: repeat(2, 1fr);
        }
        
        .metric-value {
            font-size: 1.8rem;
        }
        
        .key-metric-value {
            font-size: 2.5rem;
        }
        
        .company-name {
            font-size: 1.3rem !important;
        }
    }
    
    /* Center content with max width */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1400px;
        margin: 0 auto;
    }
    
    /* Markdown in report */
    .report-container h1,
    .report-container h2,
    .report-container h3 {
        border-bottom: 1px solid #333333;
        padding-bottom: 0.3rem;
        margin-top: 1.5rem;
        margin-bottom: 1rem;
        font-weight: 600;
    }
    
    .report-container table {
        border-collapse: collapse;
        width: 100%;
        margin: 1rem 0;
    }
    
    .report-container th,
    .report-container td {
        border: 1px solid #333333;
        padding: 0.5rem;
        text-align: left;
    }
    
    .report-container th {
        background-color: #111111;
        font-weight: 400;
    }
    
    .report-container strong {
        color: #FFFFFF;
        font-weight: 600;
    }
    
    .report-container code {
        background-color: #111111;
        border: 1px solid #333333;
        padding: 0.2rem 0.4rem;
        font-family: 'Courier New', monospace;
    }
    
    /* TradingView Widgets - Match terminal style */
    iframe {
        border: 1px solid #333333 !important;
        background-color: #000000 !important;
    }
    
    /* Widget containers */
    .tradingview-widget-container {
        background-color: #000000 !important;
        border: 1px solid #333333 !important;
    }
    
    /* ===== V2.1 HEALTH CHECKER - CREDIT SCORE FORMAT ===== */
    
    .health-report {
        max-width: 800px;
        margin: 0 auto;
        padding: 0;
    }
    
    /* Company Header */
    .company-header {
        text-align: center;
        padding: 2.5rem 0 1.5rem 0;
        border-bottom: 2px solid #FFAA00;
        margin-bottom: 2.5rem;
        background: linear-gradient(180deg, #0a0a0a 0%, #000000 100%);
    }

    .company-name {
        font-size: 2.4rem;
        font-weight: 700;
        color: #FFAA00 !important;
        letter-spacing: 0.15em;
        text-shadow: 0 2px 8px rgba(255, 170, 0, 0.3);
    }
    
    /* Score Display */
    .health-score-display {
        text-align: center;
        padding: 3.5rem 0;
        background: linear-gradient(135deg, #0a0a0a 0%, #1a1a1a 100%);
        border: 1px solid #333333;
        border-left: 4px solid #FFAA00;
        margin-bottom: 3rem;
        box-shadow: 0 4px 12px rgba(255, 170, 0, 0.1);
    }
    
    .score-label {
        font-size: 1.0rem;
        color: #FFAA00 !important;
        text-transform: uppercase;
        letter-spacing: 0.2em;
        margin-bottom: 1.5rem;
        font-weight: 700;
    }
    
    .score-value {
        display: flex;
        align-items: baseline;
        justify-content: center;
        gap: 0.5rem;
    }
    
    .score-number {
        font-size: 5rem;
        font-weight: 700;
        color: #FFFFFF !important;
        line-height: 1;
    }
    
    .score-max {
        font-size: 2rem;
        color: #666666 !important;
    }
    
    .score-indicator {
        font-size: 3rem;
        margin-left: 1rem;
    }
    
    /* Key Points */
    .key-points {
        background: linear-gradient(135deg, #0a0a0a 0%, #151515 100%);
        padding: 2.5rem;
        border: 1px solid #333333;
        border-left: 4px solid #666666;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
    }
    
    .points-header {
        font-size: 1.0rem;
        color: #FFAA00 !important;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.15em;
        margin-bottom: 2rem;
        padding-bottom: 1rem;
        border-bottom: 1px solid #222222;
    }
    
    .point-item {
        display: flex;
        align-items: flex-start;
        gap: 1rem;
        padding: 1.5rem 0;
        border-bottom: 1px solid #1a1a1a;
    }
    
    .point-item:last-child {
        border-bottom: none;
    }
    
    .point-icon {
        font-size: 1.8rem;
        line-height: 1;
        margin-top: 0.1rem;
        min-width: 1.8rem;
    }
    
    .point-item.positive .point-icon {
        color: #00FF00 !important;
    }
    
    .point-item.negative .point-icon {
        color: #FF0000 !important;
    }
    
    .point-item.warning .point-icon {
        color: #FFAA00 !important;
    }
    
    .point-text {
        flex: 1;
        color: #FFFFFF !important;
        font-size: 1.5rem;
        line-height: 2.0;
    }
    
    /* Mobile */
    @media (max-width: 640px) {
        .score-number {
            font-size: 3.5rem !important;
        }
        
        .score-max {
            font-size: 1.5rem !important;
        }
        
        .score-indicator {
            font-size: 2rem !important;
        }
        
        .company-name {
            font-size: 1.5rem !important;
        }
        
        .point-text {
            font-size: 1rem !important;
        }
    }
</style>
""", unsafe_allow_html=True)

# Minimal header
st.markdown("# EQUITY RESEARCH TERMINAL")
st.markdown("---")

# Disclaimer - minimal
with st.expander("DISCLAIMER"):
    st.markdown("""
    This Financial Health Score is a proprietary analytical tool based on publicly available SEC filings. It is not investment advice, not affiliated with credit rating agencies, and is for informational purposes only. Consult a financial adviser before making investment decisions.
    """)

st.markdown("---")

# Input
company_name = st.text_input(
    "TICKER SYMBOL",
    placeholder="AAPL",
    help="Enter US-listed stock ticker"
)

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if pd.isna(obj):
            return None
        if isinstance(obj, (pd.Timestamp, datetime)):
            return obj.isoformat()
        if isinstance(obj, (pd.Series, pd.DataFrame)):
            return obj.to_dict()
        return super().default(obj)

if 'report_generated' not in st.session_state:
    st.session_state.report_generated = False

# Initialize debug storage
if 'debug_api_calls' not in st.session_state:
    st.session_state.debug_api_calls = []

col1, col2, col3 = st.columns([1, 1, 4])
with col1:
    generate_button = st.button("GENERATE", use_container_width=True)

if generate_button:
    if company_name:
        try:
            # Clear previous debug data
            st.session_state.debug_api_calls = []
            
            # Create progress tracking
            if 'progress_steps' not in st.session_state:
                st.session_state.progress_steps = []
            st.session_state.progress_steps = []
            
            progress_container = st.empty()
            start_time = time.time()
            
            # Define progress callback function
            def update_progress(step: int, message: str):
                # Mark previous steps as complete
                for i in range(len(st.session_state.progress_steps)):
                    if st.session_state.progress_steps[i]['step'] < step:
                        st.session_state.progress_steps[i]['status'] = 'complete'
                
                # Add or update current step
                current_exists = False
                for i in range(len(st.session_state.progress_steps)):
                    if st.session_state.progress_steps[i]['step'] == step:
                        st.session_state.progress_steps[i]['status'] = 'running'
                        current_exists = True
                        break
                
                if not current_exists:
                    st.session_state.progress_steps.append({
                        'step': step,
                        'message': message,
                        'status': 'running'
                    })
                
                # Display all steps
                progress_html = ""
                for item in st.session_state.progress_steps:
                    icon = "✓" if item['status'] == 'complete' else "⏳"
                    color = "#00FF00" if item['status'] == 'complete' else "#FFAA00"
                    progress_html += f'<div style="color: {color}; font-family: \'Courier New\', monospace; padding: 0.3rem 0;">{icon} [{item["step"]}/2] {item["message"]}</div>'
                
                progress_container.markdown(progress_html, unsafe_allow_html=True)
            
            # Use Pure Perplexity for search + report generation (with progress updates)
            result = utils.generate_financial_report_with_perplexity(
                company_name,
                progress_callback=update_progress
            )
            gen_time = time.time() - start_time
            
            # Mark all steps complete
            for item in st.session_state.progress_steps:
                item['status'] = 'complete'
            
            # Final display with all checkmarks
            final_html = ""
            for item in st.session_state.progress_steps:
                final_html += f'<div style="color: #00FF00; font-family: \'Courier New\', monospace; padding: 0.3rem 0;">✓ [{item["step"]}/2] {item["message"]}</div>'
            progress_container.markdown(final_html, unsafe_allow_html=True)
            
            # Give user a moment to see completion, then clear
            time.sleep(0.5)
            progress_container.empty()
            
            if result["success"] and result["report"]:
                st.session_state.report_generated = True
                st.session_state.report_content = result["report"]
                st.session_state.company_ticker = company_name
                st.session_state.sources = result.get("sources", [])
                st.session_state.citations = result.get("citations", [])
                
                # Success message
                num_sources = len(result.get("sources", []))
                st.success(f"✓ COMPLETE • {len(result['report'].split())} WORDS • {gen_time:.1f}s TOTAL • {num_sources} SOURCES")
                
                # Show sources
                if num_sources > 0:
                    st.info(f"📰 DATA SOURCES: {num_sources} web pages analyzed with real-time data")
            else:
                st.error(f"ERROR: {result.get('report', 'Unknown error')}")
        except Exception as e:
            st.error(f"ERROR: {str(e)}")
            with st.expander("DEBUG"):
                import traceback
                st.code(traceback.format_exc())
    else:
        st.warning("ENTER TICKER SYMBOL")

if st.session_state.report_generated:
    st.markdown("---")

    # Download button - disabled
    # col1, col2, col3 = st.columns([1, 1, 4])
    # with col1:
    #     # Save as markdown file instead (WeasyPrint requires GTK3 runtime on Windows)
    #     md_file_path = f"{company_name}_report.md"
    #     st.download_button(
    #         label="DOWNLOAD MD",
    #         data=st.session_state.report_content,
    #         file_name=md_file_path,
    #         mime="text/markdown",
    #         use_container_width=True,
    #         help="Download as Markdown (PDF requires GTK3 runtime on Windows)"
    #     )

    # Sources section - show web search sources
    if 'sources' in st.session_state and len(st.session_state.sources) > 0:
        with st.expander("📰 VIEW DATA SOURCES", expanded=False):
            st.markdown(f"**{len(st.session_state.sources)} sources analyzed:**")
            for i, source in enumerate(st.session_state.sources, 1):
                if isinstance(source, dict):
                    st.markdown(f"{i}. [{source.get('title', 'Source')}]({source.get('url', '#')})")
                else:
                    st.markdown(f"{i}. {source}")
    
    # Citations section - show inline citations
    if 'citations' in st.session_state and len(st.session_state.citations) > 0:
        with st.expander("🔗 VIEW CITATIONS", expanded=False):
            st.markdown(f"**{len(st.session_state.citations)} citations in report:**")
            for i, citation in enumerate(st.session_state.citations, 1):
                st.markdown(f"{i}. [{citation.get('title', 'Citation')}]({citation.get('url', '#')})")
                if citation.get('text'):
                    st.caption(f"Referenced: \"{citation['text'][:100]}...\"")
    
    # Debug section - disabled
    # if 'debug_api_calls' in st.session_state and len(st.session_state.debug_api_calls) > 0:
    #     with st.expander("🔍 DEBUG: RAW PERPLEXITY API CALLS", expanded=False):
    #         st.markdown(f"**{len(st.session_state.debug_api_calls)} API calls made:**")
    #
    #         for i, call in enumerate(st.session_state.debug_api_calls, 1):
    #             st.markdown(f"### Call {i}: {call['timestamp']}")
    #
    #             st.markdown("**REQUEST:**")
    #             st.json(call['request'])
    #
    #             st.markdown("**RESPONSE:**")
    #             st.code(call['response']['content'], language='text')
    #
    #             if call['response'].get('citations'):
    #                 st.markdown(f"**CITATIONS ({len(call['response']['citations'])}):**")
    #                 for j, citation in enumerate(call['response']['citations'], 1):
    #                     st.markdown(f"{j}. {citation}")
    #
    #             st.markdown("---")
    
    st.markdown("---")
    
    # Report display - render HTML with styling
    # Apply sanitizer as final guard to ensure clean HTML
    from utils import sanitize_and_validate_html
    sanitized_html = sanitize_and_validate_html(st.session_state.report_content)
    
    st.markdown(
        f'<div class="report-container">{sanitized_html}</div>',
        unsafe_allow_html=True
    )
    
    # TradingView Widgets Section - Bloomberg Style
    if 'company_ticker' in st.session_state:
        st.markdown("---")
        st.markdown("# LIVE MARKET DATA")
        st.markdown("---")
        
        # Financial Metrics Widget
        with st.expander("FINANCIAL METRICS", expanded=False):
            try:
                utils.render_financials_widget(st.session_state.company_ticker)
            except Exception as e:
                st.error(f"WIDGET ERROR: {str(e)}")
