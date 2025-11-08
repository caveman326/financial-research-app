#!/usr/bin/env python3
"""
Utility functions for the financial research app.

Uses OpenAI Responses API with web_search tool per latest OpenAI documentation.
"""

import os
import sys
from typing import Any, Dict, Optional, List
from datetime import datetime, timedelta
import time
import json
import asyncio
import random
import requests

import pandas as pd
import numpy as np
from dotenv import load_dotenv
import streamlit.components.v1 as components

# Fix Windows console encoding issues with emoji/unicode
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        pass  # If reconfigure not available, continue anyway

load_dotenv(override=False)


# =====================================================================
# PERPLEXITY HELPER - Circuit Breaker & Retry Logic
# =====================================================================

class PerplexityCircuitBreaker:
    """Circuit breaker for Perplexity API calls to handle failures gracefully"""
    
    def __init__(self, failure_threshold: int = 3, timeout_duration: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout_duration = timeout_duration
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    def is_open(self) -> bool:
        """Check if circuit breaker is open (blocking calls)"""
        if self.state == "OPEN":
            if self._should_attempt_reset():
                self.state = "HALF_OPEN"
                return False
            return True
        return False
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to try again"""
        if self.last_failure_time:
            elapsed = datetime.now() - self.last_failure_time
            return elapsed >= timedelta(seconds=self.timeout_duration)
        return False
    
    def record_success(self):
        """Record successful API call"""
        self.failure_count = 0
        self.state = "CLOSED"
    
    def record_failure(self):
        """Record failed API call"""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            print(f"[WARNING] Circuit breaker OPEN after {self.failure_count} failures")


def perplexity_request_with_retry(
    api_key: str,
    model: str,
    messages: List[Dict],
    search_mode: Optional[str] = None,
    search_after_date_filter: Optional[str] = None,
    return_images: bool = False,
    return_related_questions: bool = False,
    web_search_options: Optional[Dict[str, str]] = None,
    max_retries: int = 5,
    timeout: int = 120
) -> Dict[str, Any]:
    """
    Make Perplexity API request using requests library (per official documentation).
    
    Implements best practices from Perplexity documentation:
    - Uses requests.post() directly for Perplexity-specific parameters
    - Exponential backoff with jitter
    - Handles rate limits gracefully
    - Circuit breaker pattern for reliability
    - Supports web_search_options for search_context_size (low/medium/high)
    """
    
    url = "https://api.perplexity.ai/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    for attempt in range(max_retries):
        try:
            # Build request payload per Perplexity documentation
            payload = {
                "model": model,
                "messages": messages
            }
            
            # Add optional Perplexity-specific parameters
            if search_mode:
                payload["search_mode"] = search_mode
            if search_after_date_filter:
                payload["search_after_date_filter"] = search_after_date_filter
            if return_images:
                payload["return_images"] = return_images
            if return_related_questions:
                payload["return_related_questions"] = return_related_questions
            if web_search_options:
                payload["web_search_options"] = web_search_options
            
            # Make API call using requests
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=timeout
            )
            
            # Check for success
            if response.status_code == 200:
                response_json = response.json()
                
                # Store debug info in session if available
                try:
                    import streamlit as st
                    if hasattr(st, 'session_state') and 'debug_api_calls' in st.session_state:
                        st.session_state.debug_api_calls.append({
                            'timestamp': datetime.utcnow().isoformat(),
                            'request': {
                                'model': model,
                                'search_mode': search_mode,
                                'search_after_date_filter': search_after_date_filter,
                                'prompt': messages[0]['content']  # Show full prompt, no truncation
                            },
                            'response': {
                                'content': response_json['choices'][0]['message']['content'],
                                'citations': response_json.get('citations', [])
                            }
                        })
                except Exception:
                    # Silently ignore if streamlit session_state is not available
                    pass
                
                return response_json
            elif response.status_code == 429:  # Rate limited
                if attempt < max_retries - 1:
                    delay = (2 ** attempt) + random.uniform(0, 1)
                    print(f"[WARNING] Rate limited (429). Retrying in {delay:.2f} seconds (attempt {attempt + 1}/{max_retries})...")
                    time.sleep(delay)
                    continue
                else:
                    raise Exception(f"Rate limit exceeded after {max_retries} retries")
            else:
                response.raise_for_status()
            
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                delay = (2 ** attempt) + random.uniform(0, 1)
                print(f"[WARNING] Request timeout. Retrying in {delay:.2f} seconds (attempt {attempt + 1}/{max_retries})...")
                time.sleep(delay)
                continue
            else:
                raise Exception(f"Request timeout after {max_retries} retries")
                
        except requests.exceptions.RequestException as e:
            error_str = str(e).lower()
            if ("rate" in error_str or "429" in error_str) and attempt < max_retries - 1:
                delay = (2 ** attempt) + random.uniform(0, 1)
                print(f"[WARNING] Rate limited. Retrying in {delay:.2f} seconds (attempt {attempt + 1}/{max_retries})...")
                time.sleep(delay)
                continue
            else:
                raise e
    
    raise Exception(f"Max retries ({max_retries}) exceeded for Perplexity API call")


# Initialize circuit breaker
_perplexity_circuit_breaker = PerplexityCircuitBreaker()


# =====================================================================
# HELPER FUNCTIONS
# =====================================================================

def sanitize_and_validate_html(html: str) -> str:
    """
    Sanitize and validate HTML to ensure it renders properly in Streamlit.
    Removes code fences, wrappers, indentation, and validates structure.
    """
    import re
    import os
    
    debug = os.getenv('DEBUG_HTML', 'false').lower() == 'true'
    
    try:
        # 1. Remove code fences
        code_fence_match = re.search(r'```(?:html)?\s*\n?(.*?)\n?```', html, re.DOTALL)
        if code_fence_match:
            if debug:
                print("[DEBUG] Extracting HTML from code fence")
            html = code_fence_match.group(1).strip()
        else:
            html = re.sub(r'```html\n?', '', html)
            html = re.sub(r'```\n?', '', html)
            html = html.replace('```html', '').replace('```', '')
        
        # 2. Strip <pre><code>, <pre>, <code> wrappers
        html = re.sub(r'<pre><code>(.*?)</code></pre>', r'\1', html, flags=re.DOTALL)
        html = re.sub(r'<pre>(.*?)</pre>', r'\1', html, flags=re.DOTALL)
        html = re.sub(r'<code>(.*?)</code>', r'\1', html, flags=re.DOTALL)
        
        # 3. CRITICAL: Dedent lines starting with whitespace before tags
        # This prevents Streamlit's Markdown renderer from treating indented HTML as code blocks
        html = re.sub(r'^[ \t]+(?=<)', '', html, flags=re.MULTILINE)
        
        # 4. Remove report-container wrapper if present (app.py adds it)
        if '<div class="report-container">' in html:
            if debug:
                print("[DEBUG] Removing report-container wrapper")
            container_match = re.search(
                r'<div class="report-container">\s*(.*?)\s*</div>\s*$',
                html,
                re.DOTALL
            )
            if container_match:
                html = container_match.group(1).strip()
            else:
                # Fallback: just remove the opening tag
                html = html.replace('<div class="report-container">', '', 1)
        
        # 5. Normalize stray trailing quotes after closing tags
        html = re.sub(r'</div>"\s*$', '</div>', html)
        
        # 6. Trim whitespace
        html = html.strip()
        
        # 7. Validate it starts with <div
        if not html.startswith('<div'):
            if debug:
                print(f"[DEBUG] HTML doesn't start with <div, searching...")
            start_idx = html.find('<div')
            if start_idx > 0:
                html = html[start_idx:]
        
        # 8. Validate structure - should start with section div
        if not html.startswith('<div class="section">'):
            if debug:
                preview = html[:min(100, len(html))].replace('\n', ' ')
                print(f"[DEBUG] Warning: doesn't start with section div. First 100: {preview}")
        
        # 9. Balance div tags
        open_divs = len(re.findall(r'<div\b', html))
        close_divs = len(re.findall(r'</div>', html))
        
        if open_divs > close_divs:
            if debug:
                print(f"[DEBUG] Unclosed divs: {open_divs - close_divs}, appending closing tags")
            html += '</div>' * (open_divs - close_divs)
        elif close_divs > open_divs:
            # Too many closing tags - try to trim extras from end
            if debug:
                print(f"[DEBUG] Extra closing divs: {close_divs - open_divs}")
            # Remove excess </div> from end
            for _ in range(close_divs - open_divs):
                last_close = html.rfind('</div>')
                if last_close > 0:
                    html = html[:last_close] + html[last_close + 6:]
        
        # 10. Final cleanup
        html = html.rstrip('`').strip()
        
        if debug:
            print(f"[DEBUG] Sanitized HTML: {len(html)} chars, {open_divs} divs")
            print(f"[DEBUG] First 120 chars: {html[:120].replace(chr(10), ' ')}")
        
        return html
        
    except Exception as e:
        print(f"[ERROR] HTML sanitization failed: {e}")
        return html  # Return as-is if sanitization fails


def generate_report_with_perplexity(
    company_name: str,
    sec_data: str,
    market_data: str,  # Will be empty - already included in deep research
    earnings_quotes: Optional[str],  # Will be empty - already included in deep research
    api_key: str
) -> str:
    """
    Generate report using sonar-reasoning-pro for advanced analysis.

    This function receives comprehensive research data and uses advanced reasoning
    to generate a structured HTML report with financial health score.
    """

    print("[Call 2/2] Using sonar-reasoning-pro for report generation...")

    comprehensive_prompt = f"""You are an expert financial analyst creating a financial health score report.

You will receive comprehensive research data about {company_name} and must analyze it to generate a financial health score report.

COMPANY: {company_name}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 COMPREHENSIVE RESEARCH DATA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{sec_data}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 YOUR TASK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Using the comprehensive research data above, perform deep reasoning and analysis to:

Calculate financial health score (0-100) based on:

**Financial Strength (0-30 points):**
- Cash vs debt ratio
- If burning cash: runway (cash ÷ annual burn)
- CRITICAL: Burning >$100M/year ≠ "rock solid"

**Profitability (0-30 points):**
- Is EBITDA positive?
- NET margin (not gross margin!)
- CRITICAL: Negative net margin = unprofitable = low score
- FCF positive or negative?
- Margin trends

**Growth (0-20 points):**
- Revenue growth vs peers
- Accelerating or decelerating?
- Profitable growth > unprofitable growth

**Momentum (0-15 points):**
- Earnings beats/misses
- Guidance changes
- Margin expansion/contraction

**Red Flags (-5 each):**
- Going concern
- Cash burn with <2yr runway
- Shrinking margins + slowing growth

**Step 2: Generate 5 Verdicts**

5 concise bullets using REAL numbers:
1. Balance sheet (actual cash/debt/burn figures)
2. Growth (actual revenue growth %)
3. Profitability (NET margin, not gross!)
4. Momentum (earnings, guidance)
5. Risk/opportunity

**Rules:**
- ✓ = positive (class="positive")
- ✗ = negative (class="negative")  
- ⚠ = warning (class="warning")
- Be honest - unprofitable companies can't claim "strong margins"
- Cash burners aren't "rock solid"

**Writing Style:**
Use punchy, valuable copy. Every word should provide value to the reader's time or context.

Think like a trader reading Bloomberg Terminal at 6am:
- Cut the fluff - no "management aims to", "consensus sees", "amid"
- Use active verbs - "burning", "printing", "bleeding", "stalled", "accelerating"
- Lead with numbers - "$51B cash vs $21B debt" not "strong liquidity with..."
- Skip obvious stuff - don't say "no signs of distress" if numbers are good
- No redundant parentheses summaries
- Avoid empty words: "meaningful", "substantial", "significant"

**Step 3: Output HTML**

<div class="health-report">
<div class="company-header">
<div class="company-name">{company_name.upper()}</div>
</div>
<div class="health-score-display">
<div class="score-label">FINANCIAL HEALTH SCORE</div>
<div class="score-value">
<span class="score-number">XX</span>
<span class="score-max">/100</span>
<span class="score-indicator">🟢/🟡/🟠/🔴</span>
</div>
</div>
<div class="key-points">
<div class="points-header">THE 5 THINGS YOU NEED TO KNOW:</div>
<div class="point-item positive">
<span class="point-icon">✓</span>
<div class="point-text">First verdict</div>
</div>
... (4 more verdicts)
</div>
</div>

**Score Guide:**
- 80-100: 🟢 (green)
- 60-79: 🟡 (yellow)
- 40-59: 🟠 (orange)
- 0-39: 🔴 (red)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔴 CRITICAL 🔴
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Pure HTML only (no markdown, code blocks, backticks)
2. Use REAL numbers from SEC data above
3. Realistic scores (unprofitable burners = 30-50, not 100)
4. Start with <div class="health-report"> (no wrapper)
5. Use NET margin for profitability, NOT gross margin
"""

    try:
        response = perplexity_request_with_retry(
            api_key=api_key,
            model="sonar-reasoning-pro",  # Using sonar-reasoning-pro for advanced multi-step reasoning
            messages=[{"role": "user", "content": comprehensive_prompt}],
            max_retries=3,
            timeout=180  # Reasoning can take longer
        )
        
        # sonar-reasoning-pro may output <think> tags, extract the actual content
        raw_content = response['choices'][0]['message']['content']

        # Remove <think> sections if present
        import re
        # Remove content between <think> and </think> tags
        html_report = re.sub(r'<think>.*?</think>', '', raw_content, flags=re.DOTALL)
        html_report = html_report.strip()

        call2_sources = response.get('citations', [])
        
        html_report = sanitize_and_validate_html(html_report)
        
        print(f"[OK] Report generated: {len(html_report)} chars, {len(call2_sources)} market sources")
        return html_report, call2_sources
        
    except Exception as e:
        print(f"[ERROR] Perplexity report generation failed: {e}")
        return f"<div>Error generating report: {str(e)}</div>", []


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "y", "on")

def _dedupe_by_url(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out = []
    for it in items:
        # Handle both dict and string sources
        if isinstance(it, dict):
            url = (it.get("url") or "").strip()
        elif isinstance(it, str):
            url = it.strip()
            it = {"url": url, "title": "Source"}
        else:
            continue

        if url and url not in seen:
            seen.add(url)
            out.append(it)
    return out


def gather_perplexity_data(company_name: str, api_key: str, progress_callback=None) -> Dict[str, Any]:
    """
    Gather comprehensive financial data using sonar-deep-research.

    This function uses Perplexity's deep research model to autonomously search,
    read, and evaluate sources for comprehensive financial analysis.

    Returns:
        dict with keys: sec_data, market_data, earnings_quotes, all_sources, sector, industry
    """

    if progress_callback:
        progress_callback(1, "Deep research in progress...")

    print("[Call 1/2] Using sonar-deep-research for comprehensive data gathering...")

    # Single comprehensive research query for sonar-deep-research
    research_prompt = f"""Conduct comprehensive financial research on {company_name} (US-listed company).

Your research should cover:

1. **SEC Filings Data** (from latest 10-Q, 10-K):
   - Total revenue (last quarter and year-over-year)
   - Net income and profit margins
   - Total cash and cash equivalents
   - Total debt (short-term + long-term)
   - Operating cash flow and free cash flow
   - Key business segments and their revenue
   - Any going concern warnings or material risks

2. **Market Data** (real-time):
   - Current stock price and market capitalization
   - 52-week high/low
   - Analyst ratings and consensus price targets
   - Industry sector and classification

3. **Recent Earnings & Management Commentary**:
   - Latest earnings call quotes from CEO/CFO
   - Forward guidance or outlook statements
   - Recent strategic announcements

4. **Recent News** (last 30 days):
   - Major developments
   - Competitive dynamics
   - Market sentiment

**CRITICAL**: Use actual numbers from SEC filings and recent financial data. Be specific with dollar amounts, percentages, and timeframes.

Format your findings clearly with section headers and cite your sources."""

    try:
        response = perplexity_request_with_retry(
            api_key=api_key,
            model="sonar-deep-research",
            messages=[{"role": "user", "content": research_prompt}],
            max_retries=3,
            timeout=180  # Deep research can take longer
        )

        research_content = response['choices'][0]['message']['content']
        sources = response.get('citations', [])

        print(f"[OK] Deep research complete: {len(research_content)} chars, {len(sources)} sources")

        # Extract sector and industry from the research (simplified)
        # We'll let the AI determine this from the research
        sector = "Technology"  # Default, will be overridden by AI analysis
        industry = "Software"  # Default, will be overridden by AI analysis

        return {
            'sec_data': research_content,  # Deep research includes SEC data
            'market_data': '',  # Already included in deep research
            'earnings_quotes': '',  # Already included in deep research
            'all_sources': sources,
            'sector': sector,
            'industry': industry
        }

    except Exception as e:
        print(f"[ERROR] Deep research failed: {e}")
        raise


def identify_business_model(sector: str, industry: str) -> Dict[str, str]:
    """
    Identify business model based on sector and industry.
    Simplified version - the AI will handle this in the report generation.
    """
    return {
        'business_model': f"{sector} - {industry}",
        'section_6_metric': "Key Performance Indicator"
    }


# =====================================================================
# REPORT GENERATION
# =====================================================================


def generate_financial_report_with_perplexity(company_name: str, progress_callback=None) -> Dict[str, Any]:
    """
    Generate equity research report using PURE Perplexity (no OpenAI).
    
    Implementation:
    - Passes 1-4: Perplexity searches for data (SEC + market + earnings)
    - Pass 5: Perplexity generates HTML report from its own search results
    
    Benefits vs OpenAI hybrid:
    - 10x cheaper (no GPT-5 costs)
    - Faster (fewer API calls)
    - Simpler (single provider)
    """
    
    # STEP 1: Validate API key
    print(f"\n{'='*60}")
    print(f"GENERATING REPORT FOR {company_name}")
    print(f"{'='*60}\n")
    
    perplexity_api_key = os.getenv("PERPLEXITY_API_KEY")
    if not perplexity_api_key:
        return {
            "report": "Error: PERPLEXITY_API_KEY not found in environment variables",
            "sources": [],
            "citations": [],
            "success": False
        }
    
    # Check circuit breaker
    if _perplexity_circuit_breaker.is_open():
        return {
            "report": "Error: Perplexity service temporarily unavailable (circuit breaker open). Please try again in a minute.",
            "sources": [],
            "citations": [],
            "success": False
        }
    
    try:
        # STEP 2: Gather data from Perplexity (4 searches)
        start_time = time.time()
        
        perplexity_data = gather_perplexity_data(company_name, perplexity_api_key, progress_callback)
        
        # Record successful searches
        _perplexity_circuit_breaker.record_success()
        
        search_time = time.time() - start_time
        print(f"[OK] Data gathering complete: {search_time:.1f}s")
        
        # STEP 3: Identify business model
        business_model_info = identify_business_model(
            sector=perplexity_data['sector'],
            industry=perplexity_data['industry']
        )
        print(f"[i] Business model: {business_model_info['business_model']}")
        print(f"[i] Section 6 metric: {business_model_info['section_6_metric']}")
        
        # STEP 4: Generate HTML report using Perplexity
        if progress_callback:
            progress_callback(2, "Analyzing and generating report...")
        
        report_start = time.time()
        
        report_html, call2_sources = generate_report_with_perplexity(
            company_name=company_name,
            sec_data=perplexity_data['sec_data'],
            market_data=perplexity_data['market_data'],
            earnings_quotes=perplexity_data['earnings_quotes'],
            api_key=perplexity_api_key
        )
        
        report_time = time.time() - report_start
        total_time = time.time() - start_time
        
        print(f"[OK] Report generated: {report_time:.1f}s")
        print(f"[OK] Total time: {total_time:.1f}s")
        
        # Combine sources from both calls
        sources = perplexity_data['all_sources']  # Call 1 SEC sources
        sources.extend(call2_sources)  # Add Call 2 market sources
        
        # Deduplicate sources
        sources = _dedupe_by_url(sources)
        
        num_sec = sum(1 for s in sources if isinstance(s, dict) and 'sec.gov' in s.get('url', ''))
        print(f"[OK] Sources: {len(sources)} total ({num_sec} from SEC)")
        
        return {
            "report": report_html,
            "sources": sources,
            "citations": [],
            "success": True,
            "model_used": "Perplexity Deep Research (sonar-deep-research + sonar-reasoning-pro)",
            "search_used": True
        }
        
    except Exception as e:
        print(f"[ERROR] Report generation failed: {e}")
        _perplexity_circuit_breaker.record_failure()
        
        import traceback
        print(traceback.format_exc())
        
        return {
            "report": f"Report generation error: {str(e)}",
            "sources": [],
            "citations": [],
            "success": False
        }


# ============================================================================
# TRADINGVIEW WIDGETS
# ============================================================================

from tradingview_widgets import (
    generate_technical_analysis_widget,
    generate_stock_financials_widget,
    generate_stock_chart_widget
)

def render_technical_analysis_widget(symbol: str) -> bool:
    try:
        widget_html = generate_technical_analysis_widget(
            symbol=symbol,
            display_mode="single",
            width="100%",
            height=400,
            is_transparent=True
        )
        components.html(widget_html, height=450)
        return True
    except Exception as e:
        print(f"Error rendering technical analysis widget for {symbol}: {e}")
        return False

def render_financials_widget(symbol: str) -> bool:
    try:
        widget_html = generate_stock_financials_widget(
            symbol=symbol,
            display_mode="regular",
            width="100%",
            height=400
        )
        components.html(widget_html, height=450)
        return True
    except Exception as e:
        print(f"Error rendering financials widget for {symbol}: {e}")
        return False

def render_stock_chart_widget(symbol: str) -> bool:
    try:
        widget_html = generate_stock_chart_widget(
            symbol=symbol,
            height=500,
            hide_side_toolbar=True,
            hide_top_toolbar=False
        )
        components.html(widget_html, height=550)
        return True
    except Exception as e:
        print(f"Error rendering stock chart widget for {symbol}: {e}")
        return False
