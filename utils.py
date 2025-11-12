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


def get_random_api_key():
    """Randomly select an API key from available keys"""
    keys = []
    
    # Collect all PERPLEXITY_API_KEY_* variables
    for i in range(1, 11):  # Check up to 10 keys
        key = os.getenv(f"PERPLEXITY_API_KEY_{i}")
        if key:
            keys.append(key)
    
    # Fallback to single key if no numbered keys found
    if not keys:
        fallback = os.getenv("PERPLEXITY_API_KEY")
        if fallback:
            return fallback
        return ""
    
    selected_key = random.choice(keys)
    print(f"[INFO] Using API key #{keys.index(selected_key) + 1} of {len(keys)} available keys")
    return selected_key


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
    - Supports search_mode parameter for specialized searches (e.g., "sec" for SEC filings)
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
    market_data: str,  # Will be None - we get it in Call 2
    earnings_quotes: Optional[str],  # Will be None
    api_key: str
) -> str:
    """
    Generate report in Call 2, which:
    1. Receives SEC data from Call 1
    2. Searches for market data and earnings
    3. Analyzes everything holistically
    4. Generates HTML report
    """
    
    print("[Call 2/2] Gathering market data, analyzing, and generating report...")
    
    comprehensive_prompt = f"""You are a financial analyst creating a CONCISE financial health score report.

COMPANY: {company_name}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 SEC FILING DATA (ALREADY PROVIDED - DO NOT RE-SEARCH)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{sec_data}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 YOUR TASK - FOLLOW THIS FORMAT EXACTLY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**STEP 1: Search for MOST RECENT Market Data (Last 30 Days)**

CRITICAL: Use the MOST RECENT data available. Check the current date and prioritize 2025 data over 2024 data.

Search Yahoo Finance, Bloomberg, MarketWatch for:

**Balance Sheet Data (LATEST QUARTER AVAILABLE):**
- Cash and cash equivalents (most recent quarter - Q3 2025 or later if available)
- Total debt (short-term + long-term, latest quarter)
- Current ratio (latest)
- Debt-to-equity ratio (latest)

**Market Data (CURRENT, NOT HISTORICAL):**
- Current stock price and 52-week range (today's data)
- Market cap (current)
- Analyst price targets and ratings (last 30 days)
- Recent news or catalysts (last 30 days only)

**Use SEC data above for:**
- Revenue, net income, margins (already extracted)
- Business description and trends

If SEC data says "See financial sites for balance sheet", search Yahoo Finance for cash/debt figures.

**STEP 2: Calculate Health Score (0-100)**

Scoring rubric (MUST total 0-100 before penalties):

Financial Strength (0-30 points):
- 25-30: Cash > 2x debt, positive FCF, no burn concerns
- 15-24: Cash > debt, manageable burn, 2+ year runway
- 5-14: Cash < debt but serviceable, or high burn with <2yr runway
- 0-4: Liquidity crisis, going concern risk

Profitability (0-30 points):
- 25-30: Net margin >10%, strong FCF, consistent EBITDA
- 15-24: Net margin 3-10%, positive FCF, positive EBITDA
- 5-14: Breakeven to small losses, negative FCF but improving
- 0-4: Large losses, severe cash burn, no path to profitability

Growth (0-20 points):
- 15-20: Revenue growing >15% YoY, accelerating
- 10-14: Revenue growing 5-15% YoY, stable
- 5-9: Revenue flat or slightly declining (<5%)
- 0-4: Revenue declining >10% YoY

Momentum (0-15 points):
- 12-15: Beat earnings, raised guidance, expanding margins
- 8-11: Met expectations, maintained guidance, stable margins
- 4-7: Slight miss, lowered guidance, margins compressing
- 0-3: Major miss, cut guidance, margins collapsing

Other Factors (0-5 points):
- Market position, competitive moat, management quality

Penalties (subtract from total):
- Going concern warning: -10
- Material weakness in controls: -5
- Cash burn with <1yr runway: -10
- Regulatory crisis: -5 to -15

SCORING RULES:
1. Must show your math: "30 + 18 + 12 + 8 + 3 - 5 = 66"
2. Be harsh on unprofitable companies (<50)
3. Be generous with profitable growers (>70)
4. Never give >90 unless truly exceptional

**STEP 3: Write EXACTLY 5 Bullets**

Each bullet must:
- Use icon: ✓ (positive), ✗ (negative), or ⚠ (warning)
- Include REAL NUMBERS from the data
- Be ONE SENTENCE, punchy and direct
- No fluff words like "meaningful", "substantial", "amid"

Required bullets (in order):
1. Balance sheet → "$XXB cash vs $XXB debt, [status/burn info]"
2. Growth → "Revenue [grew/shrank] XX% YoY to $XXB in [MOST RECENT QUARTER]—[trend]"
3. Profitability → "Net margin at XX% and [positive/negative] free cash flow—[status]"
4. Momentum → "[Beat/Missed] [MOST RECENT QUARTER] earnings; guidance [raised/cut/maintained], [margin trend]"
5. Risk → "[Key risk or opportunity with specific impact]"

CRITICAL: Use the MOST RECENT QUARTER available in your search results. If current date is in 2025, you should be using Q1/Q2/Q3 2025 data, NOT Q4 2024 annual data.

**WRITING STYLE RULES - SOUND HUMAN, NOT AI:**

✓ DO THIS:
- Lead with numbers: "$14B cash vs $3B debt, but burning $2B/quarter"
- Use simple verbs: "shrank", "crashed", "burning", "bleeding", "stalled"
- Show implications: "two quarters of burn would halve liquidity"
- Be direct: "unprofitable" not "suboptimal profitability dynamics"
- Active voice: "Revenue fell 15%" not "A decline in revenue was observed"

✗ NEVER DO THIS:
- Jargon: "amid headwinds", "robust dynamics", "meaningful trajectory"
- Obscure metrics: "Altman Z-score", "DSO", "working capital efficiency", "ROIC"
- Hedging: "appears to suggest", "potentially indicates", "may exhibit"
- Consultant-speak: "optimization", "leverage expansion", "operational dynamics"
- Percentage jargon: "basis points" (just say "from 5.2% to 7.8%")
- Empty words: "robust", "significant", "meaningful", "substantial", "considerable"
- Academic terms: "liquidity dynamics", "margin trajectory", "revenue optimization"

✗ NEVER USE FINANCIAL ACRONYMS - ALWAYS TRANSLATE TO PLAIN LANGUAGE:
- "ROTCE" → say "return on equity" or "returns to shareholders"
- "NII" → say "interest income" or "lending profit"
- "EBITDA" → say "operating profit"
- "FCF" → spell out "free cash flow" (never use acronym alone)
- "ARPU" → say "revenue per customer"
- "CET1" → say "core capital"
- "NIM" → say "lending margin"
- "NCO" → say "credit losses"
- "YTD" → spell out "year-to-date" (never use acronym alone)
- "LTV/CAC" → say "customer value vs acquisition cost"
- "RWA" → say "risk-weighted assets"

Exception: Q1/Q2/Q3/Q4 and YoY are acceptable (universally known).

GOOD EXAMPLES:
✓ "$18B cash vs $7B debt, generating $6B operating cash flow—balance sheet rock solid"
✓ "Revenue shrank 11% YoY to $22B in Q2—automotive down 15%, growth stalled"
✓ "Net margin at 5.3% and positive free cash flow—profitable but margins compressed from 8.1% to 5.3%"

BAD EXAMPLES (AI-SOUNDING):
✗ "The firm exhibits robust liquidity dynamics with an Altman Z-score of 3.2"
✗ "Operational leverage optimization has driven margin expansion amid headwinds"
✗ "Revenue trajectory appears to suggest decelerating momentum dynamics"

GOOD EXAMPLES - BANK SPECIFIC:
✓ "Return on equity 15.4%—generating strong returns for shareholders"
✓ "Interest income up 6% YoY to $14.2B—core lending business growing steadily"
✓ "Core capital ratio 12.1% vs regulatory minimum 10.5%—balance sheet rock solid"

BAD EXAMPLES - BANK JARGON (AI-SOUNDING):
✗ "ROTCE expanded 140 basis points to 15.4% amid NIM compression dynamics"
✗ "CET1 ratio robust at 12.1% despite RWA optimization headwinds"
✗ "NII trajectory reflects deposit beta sensitivity to rate normalization"

**STEP 4: FINAL QUALITY REVIEW (Do this BEFORE outputting HTML)**

Before you output the HTML, verify:

DATE CHECK:
- What is today's date? (You have access to current date)
- What quarter did I use in my bullets? (Q1/Q2/Q3/Q4 and year)
- Is this the MOST RECENT quarter available?
- If today is in 2025 and I used Q4 2024 data, STOP and search for Q1/Q2/Q3 2025 data instead

QUALITY CHECK:
- Do all 5 bullets use REAL NUMBERS from the data?
- Are quarters/years consistent across all bullets?
- Did I avoid acronyms (ROTCE, NII, YTD, FCF without spelling out)?
- Is each bullet ONE sentence?
- Did I use plain language, not jargon?

If ANY check fails, FIX IT before outputting HTML.

**STEP 5: Output HTML (Only After Review)**

<div class="health-report">
<div class="company-header">
<div class="company-name">{company_name.upper()}</div>
</div>
<div class="health-score-display">
<div class="score-label">FINANCIAL HEALTH SCORE</div>
<div class="score-value">
<span class="score-number">XX</span>
<span class="score-max">/100</span>
<span class="score-indicator">🟢</span>
</div>
<!-- Score calculation: Financial(XX) + Profitability(XX) + Growth(XX) + Momentum(XX) + Other(X) - Penalties(X) = XX -->
</div>
<div class="key-points">
<div class="points-header">5 Key Insights from Latest SEC Filings:</div>
<div class="point-item positive">
<span class="point-icon">✓</span>
<div class="point-text">$XXB cash vs $XXB debt...</div>
</div>
<div class="point-item negative">
<span class="point-icon">✗</span>
<div class="point-text">Revenue shrank XX% YoY...</div>
</div>
<div class="point-item warning">
<span class="point-icon">⚠</span>
<div class="point-text">Net margin at XX%...</div>
</div>
<div class="point-item positive">
<span class="point-icon">✓</span>
<div class="point-text">Beat QX earnings...</div>
</div>
<div class="point-item warning">
<span class="point-icon">⚠</span>
<div class="point-text">Risk assessment...</div>
</div>
</div>
</div>

Score indicator emojis:
- 80-100: 🟢 (green)
- 60-79: 🟡 (yellow)  
- 40-59: 🟠 (orange)
- 0-39: 🔴 (red)

Point classes:
- Use class="positive" for ✓ bullets
- Use class="negative" for ✗ bullets
- Use class="warning" for ⚠ bullets

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔴 CRITICAL REQUIREMENTS 🔴
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ MANDATORY HTML OUTPUT ⚠️
YOU MUST OUTPUT THE HTML STRUCTURE ABOVE NO MATTER WHAT!
- NEVER output plain text explanations
- NEVER say "I cannot complete this" or "Missing critical data"
- NEVER explain why you can't do something
- If data is missing, use "N/A" or estimates with "~" prefix
- If you only have partial data, use what you have and estimate the rest

1. Output ONLY the HTML structure shown above - no extra sections
2. EXACTLY 5 bullet points - no more, no less
3. Each bullet = ONE sentence with real numbers (or "~$X" for estimates)
4. No tables, no additional commentary, no explanatory paragraphs
5. Pure HTML only (no markdown, no code blocks, no backticks)
6. Start with <div class="health-report"> and end with </div>
7. Use NET margin for profitability, NOT gross margin
8. Be brutally honest - unprofitable burners get low scores (30-50)
9. EVEN WITH MISSING DATA, OUTPUT THE HTML FORMAT!
"""

    try:
        response = perplexity_request_with_retry(
            api_key=api_key,
            model="sonar-reasoning-pro",  # Using sonar-reasoning-pro for advanced reasoning and report writing
            messages=[{"role": "user", "content": comprehensive_prompt}],
            web_search_options={"search_context_size": "high"},  # Maximum reasoning for comprehensive analysis
            max_retries=3
        )
        
        html_report = response['choices'][0]['message']['content']
        call2_sources = response.get('citations', [])
        
        # Check if response is actually HTML
        if not html_report.strip().startswith('<div class="health-report">'):
            print(f"[ERROR] Response is not HTML format. Got: {html_report[:200]}...")
            # Create a fallback HTML report with limited data
            html_report = f"""<div class="health-report">
<div class="company-header">
<div class="company-name">{company_name.upper()}</div>
</div>
<div class="health-score-display">
<div class="score-label">FINANCIAL HEALTH SCORE</div>
<div class="score-value">
<span class="score-number">N/A</span>
<span class="score-max">/100</span>
<span class="score-indicator">⚠️</span>
</div>
</div>
<div class="key-points">
<div class="points-header">5 Key Insights from Latest SEC Filings:</div>
<div class="point-item warning">
<span class="point-icon">⚠</span>
<div class="point-text">Insufficient financial data available to calculate metrics.</div>
</div>
<div class="point-item warning">
<span class="point-icon">⚠</span>
<div class="point-text">SEC filing data extraction incomplete for {company_name}.</div>
</div>
<div class="point-item warning">
<span class="point-icon">⚠</span>
<div class="point-text">Unable to determine cash position and debt levels.</div>
</div>
<div class="point-item warning">
<span class="point-icon">⚠</span>
<div class="point-text">Revenue and profitability metrics not available.</div>
</div>
<div class="point-item warning">
<span class="point-icon">⚠</span>
<div class="point-text">Please verify company ticker and try again.</div>
</div>
</div>
</div>"""
        
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


# =====================================================================
# DATA GATHERING
# =====================================================================

def gather_perplexity_data(company_name: str, api_key: str, progress_callback=None) -> Dict[str, Any]:
    """
    Gather SEC data from Perplexity for financial research.

    Returns:
    - sec_data: Financial and context data from SEC
    - sector/industry: For business model detection
    - all_sources: Combined citations
    """

    # CALL 1: Comprehensive SEC Data
    if progress_callback:
        progress_callback(1, "Gathering SEC filing data...")
    print(f"[Call 1/2] Comprehensive SEC data for {company_name}...")

    sec_comprehensive_query = f"""Find {company_name}'s OWN recent SEC filing where {company_name} is the FILER (not third-party mentions).

For US companies: Search for 10-Q (quarterly) or 10-K (annual) filings.
For foreign companies (ADRs): Search for 20-F (annual) or 6-K (current report) filings.

Search for SEC filings filed BY {company_name}, not filings that just mention {company_name}.

**FROM THE FILING TEXT, FIND AND REPORT:**

**1. REVENUE (Income Statement - REQUIRED):**
- Total revenue for most recent quarter: $X.XB
- Total revenue for year-ago quarter: $X.XB
- Calculate YoY growth: X.X%
- Format: "Revenue Q[X] 20XX: $X.XB vs Q[X] 20XX: $X.XB (+/-X.X% YoY)"

**2. PROFITABILITY (Income Statement - REQUIRED):**
- Net income for most recent quarter: $X.XB
- Operating income: $X.XB (if mentioned)
- Calculate net margin: (Net income / Revenue) × 100
- Format: "Net income Q[X] 20XX: $X.XB (X.X% margin)"

**3. CASH FLOW (if mentioned in filing summary):**
- Operating cash flow: $X.XB
- Free cash flow: $X.XB (if stated)
- Capital expenditures: $X.XB (if stated)

**4. BUSINESS CONTEXT:**
- What does the company do? (1 sentence)
- Industry sector
- Key trends: Is revenue accelerating or decelerating quarter-over-quarter?
- Are margins expanding or contracting?
- Major risks mentioned in Risk Factors section (top 2-3)
- Recent guidance changes: raised, lowered, or maintained?

**5. EARNINGS PERFORMANCE:**
- Did they beat or miss analyst expectations? (if mentioned)
- Any going concern warnings or liquidity issues flagged?

**6. BALANCE SHEET NOTE:**
If cash/debt figures aren't clearly visible in the search results, write:
"Balance sheet: Not extracted from SEC search - see Call 2 for cash/debt data"

**CRITICAL REQUIREMENTS:**
1. Revenue and net income are MANDATORY - extract from income statement
2. Calculate YoY percentages accurately: ((Current - Prior) / Prior) × 100
3. Use actual dollar amounts from filing, not estimates
4. If a metric truly isn't findable, say "Not mentioned in filing"

**FORMAT EXAMPLE:**
Revenue Q2 2025: $22.5B vs Q2 2024: $25.5B (-11.8% YoY)
Net income Q2 2025: $1.2B (5.3% margin)
Operating cash flow: $4.7B
Balance sheet: Not extracted - see Call 2

**SOURCES USED:**
- List all SEC filing URLs referenced"""

    sec_response = perplexity_request_with_retry(
        api_key=api_key,
        model="sonar-reasoning-pro",  # Using sonar-reasoning-pro for SEC data extraction with reasoning
        messages=[{"role": "user", "content": sec_comprehensive_query}],
        web_search_options={"search_context_size": "high"},  # High context for comprehensive SEC data extraction
        max_retries=5
    )

    sec_data = sec_response['choices'][0]['message']['content']
    
    # Strip <think> tags if present (sonar-reasoning-pro sometimes exposes internal reasoning)
    import re
    sec_data = re.sub(r'<think>.*?</think>', '', sec_data, flags=re.DOTALL).strip()
    
    # Check if Call 1 returned insufficient data
    if len(sec_data) < 500 or "cannot" in sec_data.lower() or "not available" in sec_data.lower() or "missing critical data" in sec_data.lower():
        print(f"[WARNING] Call 1 may have insufficient data (only {len(sec_data)} chars). Response preview: {sec_data[:200]}...")
        # Retry once with a more specific prompt for companies with limited data
        if "cannot" in sec_data.lower() or len(sec_data) < 300:
            print("[RETRY] Attempting Call 1 again with broader search...")
            sec_comprehensive_query_retry = sec_comprehensive_query + "\n\nIMPORTANT: Search more broadly. Try variations of the company name. Look for ANY recent financial data about this company from SEC filings, earnings reports, or financial statements. Include investor presentations if needed."
            sec_response_retry = perplexity_request_with_retry(
                api_key=api_key,
                model="sonar-reasoning-pro",
                messages=[{"role": "user", "content": sec_comprehensive_query_retry}],
                web_search_options={"search_context_size": "high"},
                max_retries=2
            )
            if sec_response_retry and 'choices' in sec_response_retry:
                sec_data_retry = sec_response_retry['choices'][0]['message']['content']
                sec_data_retry = re.sub(r'<think>.*?</think>', '', sec_data_retry, flags=re.DOTALL).strip()
                if len(sec_data_retry) > len(sec_data):
                    print(f"[OK] Retry successful: {len(sec_data_retry)} chars")
                    sec_data = sec_data_retry
                    sec_response = sec_response_retry

    # Extract citations from API metadata or parse from response text
    sec_sources = sec_response.get('citations', [])

    if len(sec_sources) == 0:
        # API didn't return citations - parse URLs from response text
        urls = re.findall(r'https://www\.sec\.gov/[^\s\)\]]+', sec_data)
        sec_sources = [{'url': url, 'title': 'SEC Filing'} for url in urls]
        print(f"[OK] Extracted {len(sec_sources)} SEC citations from response text")
    else:
        print(f"[OK] Got {len(sec_sources)} citations from API metadata")

    print(f"[OK] SEC data: {len(sec_data)} chars from {len(sec_sources)} filings")

    # Extract sector/industry from SEC data (for informational purposes)
    sec_lower = sec_data.lower()
    sector_match = ""
    industry_match = ""

    if "software" in sec_lower or "saas" in sec_lower or "cloud" in sec_lower:
        sector_match = "Technology"
        industry_match = "Software"
    elif "retail" in sec_lower or "consumer" in sec_lower:
        sector_match = "Consumer"
        industry_match = "Retail"
    elif "manufacturing" in sec_lower or "industrial" in sec_lower:
        sector_match = "Industrials"
        industry_match = "Manufacturing"
    elif "bank" in sec_lower or "financial services" in sec_lower:
        sector_match = "Financial"
        industry_match = "Banking"
    elif "oil" in sec_lower or "energy" in sec_lower or "mining" in sec_lower or "petroleum" in sec_lower or "gas" in sec_lower:
        sector_match = "Energy"
        industry_match = "Oil & Gas"
    elif "healthcare" in sec_lower or "pharmaceutical" in sec_lower or "biotech" in sec_lower or "medical" in sec_lower:
        sector_match = "Healthcare"
        industry_match = "Healthcare"
    elif "telecom" in sec_lower or "communication" in sec_lower:
        sector_match = "Communication"
        industry_match = "Telecommunications"

    return {
        "sec_data": sec_data,
        "market_data": None,
        "earnings_quotes": None,
        "sector": sector_match,
        "industry": industry_match,
        "all_sources": sec_sources
    }


# =====================================================================
# REPORT GENERATION
# =====================================================================


def generate_financial_report_with_perplexity(company_name: str, progress_callback=None) -> Dict[str, Any]:
    """
    Generate equity research report using PURE Perplexity (no OpenAI).

    Implementation:
    - Call 1: sonar-reasoning-pro with SEC search mode for data extraction with reasoning
    - Call 2: sonar-reasoning-pro with high context for analysis and HTML report generation

    Benefits vs OpenAI hybrid:
    - 10x cheaper (no GPT-5 costs)
    - Faster (fewer API calls)
    - Simpler (single provider)
    - Consistent reasoning model across both calls
    """
    
    # STEP 1: Validate API key
    print(f"\n{'='*60}")
    print(f"GENERATING REPORT FOR {company_name}")
    print(f"{'='*60}\n")
    
    perplexity_api_key = get_random_api_key()
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
        
        # STEP 3: Generate HTML report using Perplexity
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
            "model_used": "Pure Perplexity (sonar-reasoning-pro x2)",
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
