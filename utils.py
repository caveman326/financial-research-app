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
import yfinance as yf
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
# EQUITY RESEARCH SYSTEM PROMPT - V2 HEALTH CHECKER
# =====================================================================
EQUITY_RESEARCH_SYSTEM_PROMPT = """You are creating a FUNDAMENTAL HEALTH SCORE report.

Your ONLY job: Format the data into clean HTML. The scores and verdicts are ALREADY CALCULATED for you.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔴 CRITICAL OUTPUT REQUIREMENTS 🔴
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Output PURE HTML ONLY
   ❌ NO markdown syntax (no #, **, -, etc.)
   ❌ NO code blocks (no ```)
   ❌ NO backticks anywhere
   ❌ NO indentation before tags (start at column 0)

2. Start with: <div class="health-report">
   ❌ DO NOT add any wrapper divs
   ❌ DO NOT add <div class="report-container">

3. Follow the EXACT structure shown below

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HTML STRUCTURE (copy this exactly)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<div class="health-report">
<div class="company-header">
<div class="company-name">COMPANY NAME IN ALL CAPS</div>
</div>
<div class="health-score-display">
<div class="score-label">FUNDAMENTAL HEALTH</div>
<div class="score-value">
<span class="score-number">40</span>
<span class="score-max">/100</span>
<span class="score-indicator">🔴</span>
</div>
</div>
<div class="key-points">
<div class="points-header">THE 5 THINGS YOU NEED TO KNOW:</div>
<div class="point-item positive">
<span class="point-icon">✓</span>
<div class="point-text">First verdict here</div>
</div>
<div class="point-item negative">
<span class="point-icon">✗</span>
<div class="point-text">Second verdict here</div>
</div>
<div class="point-item negative">
<span class="point-icon">✗</span>
<div class="point-text">Third verdict here</div>
</div>
<div class="point-item negative">
<span class="point-icon">✗</span>
<div class="point-text">Fourth verdict here</div>
</div>
<div class="point-item warning">
<span class="point-icon">⚠</span>
<div class="point-text">Fifth verdict here</div>
</div>
</div>
</div>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INSTRUCTIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

The user will give you:
1. Company name
2. Score (0-100)
3. Indicator emoji (🟢 🟡 🟠 🔴)
4. Five pre-written verdicts

Your job is to:
1. Insert the company name (make it ALL CAPS)
2. Insert the score and indicator
3. Insert the 5 verdicts into the bullet points
4. Set the correct CSS class for each point (positive/negative/warning)
5. Set the correct icon (✓ ✗ ⚠) based on the verdict

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CSS CLASS RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<div class="point-item positive">   ← Use when verdict starts with ✓
<span class="point-icon">✓</span>

<div class="point-item negative">   ← Use when verdict starts with ✗
<span class="point-icon">✗</span>

<div class="point-item warning">    ← Use when verdict starts with ⚠
<span class="point-icon">⚠</span>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT YOU MUST NOT DO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

❌ DO NOT rewrite the verdicts - use them EXACTLY as given
❌ DO NOT add explanations beyond the 5 verdicts
❌ DO NOT add extra sections
❌ DO NOT change the wording of verdicts
❌ DO NOT use markdown formatting
❌ DO NOT wrap in code blocks
❌ DO NOT add indentation before HTML tags
❌ DO NOT add a report-container wrapper

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXAMPLE INPUT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Company: Tesla Inc.
Score: 40
Indicator: 🔴

Verdicts:
1. ✓ Cash position is strong: $24B cash, low debt, won't go bankrupt
2. ✗ Growth is terrible: Revenue up only 3% (tech average is 15%)
3. ✗ Profit margins collapsed: Makes 3¢ per $1 sold, margins shrinking
4. ✗ Getting worse: Growth slowing, missed earnings, guidance lowered
5. ⚠ Red flags: margins collapsing, momentum declining

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXAMPLE OUTPUT (what you should produce)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<div class="health-report">
<div class="company-header">
<div class="company-name">TESLA INC.</div>
</div>
<div class="health-score-display">
<div class="score-label">FUNDAMENTAL HEALTH</div>
<div class="score-value">
<span class="score-number">40</span>
<span class="score-max">/100</span>
<span class="score-indicator">🔴</span>
</div>
</div>
<div class="key-points">
<div class="points-header">THE 5 THINGS YOU NEED TO KNOW:</div>
<div class="point-item positive">
<span class="point-icon">✓</span>
<div class="point-text">Cash position is strong: $24B cash, low debt, won't go bankrupt</div>
</div>
<div class="point-item negative">
<span class="point-icon">✗</span>
<div class="point-text">Growth is terrible: Revenue up only 3% (tech average is 15%)</div>
</div>
<div class="point-item negative">
<span class="point-icon">✗</span>
<div class="point-text">Profit margins collapsed: Makes 3¢ per $1 sold, margins shrinking</div>
</div>
<div class="point-item negative">
<span class="point-icon">✗</span>
<div class="point-text">Getting worse: Growth slowing, missed earnings, guidance lowered</div>
</div>
<div class="point-item warning">
<span class="point-icon">⚠</span>
<div class="point-text">Red flags: margins collapsing, momentum declining</div>
</div>
</div>
</div>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FINAL CHECKS BEFORE SUBMITTING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Before you output, verify ALL of these:

✓ Starts with: <div class="health-report">
✓ Company name is ALL CAPS
✓ Score number is correct
✓ Indicator emoji is correct (🟢 🟡 🟠 🔴)
✓ Exactly 5 point-item divs
✓ Each point has correct class (positive/negative/warning)
✓ Each point has correct icon (✓ ✗ ⚠)
✓ All verdict text used EXACTLY as given (no changes)
✓ No markdown artifacts (no ```, no #, no *)
✓ No indentation before tags
✓ All <div> tags properly closed
✓ No wrapper divs added

If even ONE fails, your output is WRONG. Fix it.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

This is educational analysis, not investment advice.
"""

WEB_SEARCH_OVERRIDES = """CRITICAL WEB SEARCH INSTRUCTIONS:
- You MUST use the Web Search tool to gather current data. Prefer primary sources (SEC filings, earnings releases, 8-Ks), then company IR, then reputable financial media.
- Every numeric claim must be grounded in a source you can cite.
- Use inline markdown links when the tool returns a URL; otherwise rely on url_citation annotations.
- Follow the 6-SECTION SNAPSHOT structure above. HARD LIMIT: 250 words maximum.
- Use emojis and visual indicators.
- Include direct CEO/CFO quotes ONLY if available (otherwise omit Section 4 entirely).
- NEVER show error messages like "unavailable" or "not provided in sources" to user.
- If you cannot find specific data, skip that section entirely rather than showing an error.
"""


# =====================================================================
# HELPER FUNCTIONS
# =====================================================================

def validate_html_report(html_content: str) -> tuple[bool, str]:
    """Validate that report is proper HTML with required structure.
    
    Args:
        html_content: The generated HTML report
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    issues = []
    
    # Check it starts with HTML
    if not html_content.strip().startswith('<'):
        issues.append("Output doesn't start with HTML tag (starts with markdown?)")
    
    # Check for report container wrapper
    if 'class="report-container"' not in html_content:
        issues.append("Missing report-container wrapper")
    
    # Check for critical CSS classes
    required_classes = ['one-liner', 'metrics-grid', 'threat-level']
    for cls in required_classes:
        if f'class="{cls}"' not in html_content:
            issues.append(f"Missing required class: {cls}")
    
    # Check for markdown artifacts
    if '```' in html_content:
        issues.append("Contains markdown code blocks (```)")
    
    if html_content.strip().startswith('#'):
        issues.append("Starts with markdown header (#)")
    
    # Check word count (strip HTML tags)
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        text_only = soup.get_text()
        word_count = len(text_only.split())
        if word_count > 350:  # Flexible limit
            issues.append(f"Word count high: {word_count} words (consider trimming for scannability)")
    except Exception as e:
        # Don't fail if BeautifulSoup not available
        pass
    
    return (len(issues) == 0, "; ".join(issues) if issues else "")


def calculate_stability_score(financials: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate Stability score (0-100) based on balance sheet strength.
    
    Returns:
        dict with 'score', 'grade', 'explanation'
    """
    score = 0
    details = []
    
    # Extract key metrics (with safe defaults)
    cash = financials.get('cash', 0)
    total_debt = financials.get('total_debt', 0)
    quarterly_burn = financials.get('quarterly_burn', 0)  # Negative if burning cash
    current_assets = financials.get('current_assets', 0)
    current_liabilities = financials.get('current_liabilities', 1)  # Avoid division by zero
    ebitda = financials.get('ebitda', 1)
    
    # 1. Cash Runway (25 points max)
    if quarterly_burn < 0:  # Burning cash
        quarters_runway = cash / abs(quarterly_burn) if quarterly_burn != 0 else 0
        if quarters_runway > 8:
            score += 25
            details.append("10+ quarters of cash runway")
        elif quarters_runway > 4:
            score += 20
            details.append(f"{int(quarters_runway)} quarters runway")
        elif quarters_runway > 2:
            score += 10
            details.append(f"Only {int(quarters_runway)} quarters runway ⚠")
        else:
            score += 0
            details.append(f"CRITICAL: <2 quarters runway 🔴")
    else:  # Cash flow positive
        score += 25
        details.append("Cash flow positive (no burn)")
    
    # 2. Debt Level (25 points max)
    if ebitda > 0:
        debt_to_ebitda = total_debt / ebitda
        if debt_to_ebitda < 2:
            score += 25
            details.append(f"Low debt ({debt_to_ebitda:.1f}x EBITDA)")
        elif debt_to_ebitda < 3:
            score += 20
            details.append(f"Moderate debt ({debt_to_ebitda:.1f}x EBITDA)")
        elif debt_to_ebitda < 5:
            score += 10
            details.append(f"High debt ({debt_to_ebitda:.1f}x EBITDA) ⚠")
        else:
            score += 0
            details.append(f"CRITICAL: Very high debt ({debt_to_ebitda:.1f}x) 🔴")
    else:
        score += 15  # Can't calculate, give partial credit
    
    # 3. Current Ratio (20 points max)
    current_ratio = current_assets / current_liabilities if current_liabilities > 0 else 0
    if current_ratio > 2:
        score += 20
        details.append(f"Strong liquidity (current ratio {current_ratio:.1f})")
    elif current_ratio > 1.5:
        score += 15
        details.append(f"Good liquidity ({current_ratio:.1f})")
    elif current_ratio > 1:
        score += 10
        details.append(f"Adequate liquidity ({current_ratio:.1f})")
    else:
        score += 0
        details.append(f"Poor liquidity ({current_ratio:.1f}) 🔴")
    
    # 4. Net Cash Position (30 points max - IMPORTANT)
    net_cash = cash - total_debt
    if net_cash > 0:
        score += 30
        details.append(f"Net cash positive (${net_cash/1e9:.1f}B)")
    elif net_cash > -total_debt * 0.5:
        score += 15
        details.append("Debt manageable vs cash")
    else:
        score += 5
        details.append("High net debt position ⚠")
    
    # Convert to grade
    if score >= 90:
        grade = "A+"
    elif score >= 85:
        grade = "A"
    elif score >= 80:
        grade = "B+"
    elif score >= 75:
        grade = "B"
    elif score >= 70:
        grade = "C+"
    elif score >= 65:
        grade = "C"
    elif score >= 60:
        grade = "D"
    else:
        grade = "F"
    
    return {
        'score': min(score, 100),
        'grade': grade,
        'details': details,
        'explanation': f"Balance sheet strength: {', '.join(details[:2])}"
    }


def calculate_growth_score(financials: Dict[str, Any], sector: str = "") -> Dict[str, Any]:
    """
    Calculate Growth score (0-100) with sector adjustment.
    
    Returns:
        dict with 'score', 'grade', 'explanation', 'sector_context'
    """
    score = 0
    details = []
    
    # Extract metrics
    revenue_growth_yoy = financials.get('revenue_growth_yoy', 0)
    revenue_growth_trend = financials.get('revenue_growth_trend', 'stable')  # 'accelerating', 'stable', 'decelerating'
    gross_margin_trend = financials.get('gross_margin_trend', 'stable')
    ocf_growth = financials.get('ocf_growth', 0)
    
    # Sector benchmarks
    sector_benchmarks = {
        'Technology': 15,
        'Software': 25,
        'Consumer': 8,
        'Retail': 8,
        'Industrials': 5,
        'Financial': 6,
        'Healthcare': 10,
        'default': 10
    }
    
    sector_avg = sector_benchmarks.get(sector, sector_benchmarks['default'])
    
    # 1. Revenue Growth Rate (40 points max, sector-adjusted)
    if revenue_growth_yoy > sector_avg * 1.5:
        score += 40
        details.append(f"Strong growth ({revenue_growth_yoy:.1f}% vs {sector_avg}% sector avg)")
    elif revenue_growth_yoy > sector_avg:
        score += 30
        details.append(f"Above sector average ({revenue_growth_yoy:.1f}%)")
    elif revenue_growth_yoy > sector_avg * 0.5:
        score += 20
        details.append(f"Moderate growth ({revenue_growth_yoy:.1f}%)")
    elif revenue_growth_yoy > 0:
        score += 10
        details.append(f"Slow growth ({revenue_growth_yoy:.1f}%)")
    else:
        score += 0
        details.append(f"Declining revenue ({revenue_growth_yoy:.1f}%) 🔴")
    
    # 2. Growth Trend (25 points max)
    if revenue_growth_trend == 'accelerating':
        score += 25
        details.append("Growth accelerating ✓")
    elif revenue_growth_trend == 'stable':
        score += 15
        details.append("Growth steady")
    else:
        score -= 10
        details.append("Growth decelerating ⚠")
    
    # 3. Quality indicators (35 points max)
    # OCF growing faster than revenue
    if ocf_growth > revenue_growth_yoy:
        score += 15
        details.append("Cash flow growing faster than sales ✓")
    
    # Margin expansion
    if gross_margin_trend == 'expanding':
        score += 10
        details.append("Margins expanding ✓")
    elif gross_margin_trend == 'stable':
        score += 5
    else:
        score -= 5
        details.append("Margins compressing ⚠")
    
    # Organic growth bonus
    score += 10  # Assume organic unless told otherwise
    
    score = max(0, min(score, 100))  # Clamp to 0-100
    
    # Convert to grade
    if score >= 90:
        grade = "A+"
    elif score >= 85:
        grade = "A"
    elif score >= 80:
        grade = "B+"
    elif score >= 75:
        grade = "B"
    elif score >= 70:
        grade = "C+"
    elif score >= 65:
        grade = "C"
    elif score >= 60:
        grade = "D"
    else:
        grade = "F"
    
    # Sector context explanation
    if revenue_growth_yoy < sector_avg:
        sector_context = f"{sector} companies average {sector_avg}% growth. This company at {revenue_growth_yoy:.1f}% = BELOW sector average."
    else:
        sector_context = f"{sector} companies average {sector_avg}% growth. This company at {revenue_growth_yoy:.1f}% = ABOVE sector average."
    
    return {
        'score': score,
        'grade': grade,
        'details': details,
        'explanation': f"Revenue growing {revenue_growth_yoy:.1f}% YoY, {revenue_growth_trend}",
        'sector_context': sector_context
    }


def calculate_profitability_score(financials: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate Profitability score (0-100) based on margins and cash generation.
    """
    score = 0
    details = []
    
    # Extract metrics
    gross_margin = financials.get('gross_margin', 0)
    fcf_margin = financials.get('fcf_margin', 0)
    net_margin = financials.get('net_margin', 0)
    roic = financials.get('roic', 0)
    
    # 1. Gross Margin (30 points max)
    if gross_margin > 60:
        score += 30
        details.append(f"Elite gross margin ({gross_margin:.1f}%)")
    elif gross_margin > 40:
        score += 20
        details.append(f"Strong margin ({gross_margin:.1f}%)")
    elif gross_margin > 20:
        score += 10
        details.append(f"Decent margin ({gross_margin:.1f}%)")
    else:
        score += 5
        details.append(f"Thin margin ({gross_margin:.1f}%) ⚠")
    
    # 2. FCF Margin (30 points max - CRITICAL)
    if fcf_margin > 20:
        score += 30
        details.append(f"Elite cash generation ({fcf_margin:.1f}% FCF margin)")
    elif fcf_margin > 10:
        score += 20
        details.append(f"Healthy cash flow ({fcf_margin:.1f}%)")
    elif fcf_margin > 5:
        score += 10
        details.append(f"Modest cash flow ({fcf_margin:.1f}%)")
    elif fcf_margin > 0:
        score += 5
        details.append("Cash flow positive but low")
    else:
        score += 0
        details.append("Burning cash 🔴")
    
    # 3. Net Margin (20 points max)
    if net_margin > 20:
        score += 20
        details.append(f"High profit margin ({net_margin:.1f}%)")
    elif net_margin > 10:
        score += 15
        details.append(f"Good profit ({net_margin:.1f}%)")
    elif net_margin > 5:
        score += 10
        details.append(f"Modest profit ({net_margin:.1f}%)")
    elif net_margin > 0:
        score += 5
    else:
        score += 0
        details.append("Unprofitable 🔴")
    
    # 4. ROIC (20 points max)
    if roic > 15:
        score += 20
        details.append(f"Strong ROIC ({roic:.1f}%)")
    elif roic > 10:
        score += 15
    elif roic > 5:
        score += 10
    else:
        score += 5
    
    score = min(score, 100)
    
    # Convert to grade
    if score >= 90:
        grade = "A+"
    elif score >= 85:
        grade = "A"
    elif score >= 80:
        grade = "B+"
    elif score >= 75:
        grade = "B"
    elif score >= 70:
        grade = "C+"
    elif score >= 65:
        grade = "C"
    elif score >= 60:
        grade = "D"
    else:
        grade = "F"
    
    return {
        'score': score,
        'grade': grade,
        'details': details,
        'explanation': f"Keeps {gross_margin:.0f}% of sales as gross profit, {fcf_margin:.0f}% as cash"
    }


def calculate_momentum_score(financials: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate Momentum score (0-100) - is it getting better or worse?
    """
    score = 50  # Start neutral
    details = []
    
    # Extract trend data
    revenue_growth_trend = financials.get('revenue_growth_trend', 'stable')
    margin_trend = financials.get('gross_margin_trend', 'stable')
    guidance = financials.get('guidance_trend', 'maintained')  # 'raised', 'maintained', 'lowered'
    earnings_beat = financials.get('earnings_beat', None)  # True/False/None
    
    # 1. Revenue acceleration (30 points swing)
    if revenue_growth_trend == 'accelerating':
        score += 30
        details.append("Revenue growth accelerating ✓")
    elif revenue_growth_trend == 'stable':
        score += 0
        details.append("Revenue growth steady")
    else:
        score -= 25
        details.append("Revenue growth slowing ⚠")
    
    # 2. Margin trend (25 points swing)
    if margin_trend == 'expanding':
        score += 25
        details.append("Margins improving ✓")
    elif margin_trend == 'stable':
        score += 0
    else:
        score -= 20
        details.append("Margins compressing ⚠")
    
    # 3. Guidance (20 points swing)
    if guidance == 'raised':
        score += 20
        details.append("Guidance raised ✓")
    elif guidance == 'maintained':
        score += 0
    else:
        score -= 20
        details.append("Guidance lowered ⚠")
    
    # 4. Earnings beat (25 points swing)
    if earnings_beat is True:
        score += 25
        details.append("Beat expectations ✓")
    elif earnings_beat is False:
        score -= 25
        details.append("Missed expectations ⚠")
    
    score = max(0, min(score, 100))  # Clamp to 0-100
    
    # Convert to grade
    if score >= 90:
        grade = "A+"
    elif score >= 85:
        grade = "A"
    elif score >= 80:
        grade = "B+"
    elif score >= 75:
        grade = "B"
    elif score >= 70:
        grade = "C+"
    elif score >= 65:
        grade = "C"
    elif score >= 60:
        grade = "D"
    else:
        grade = "F"
    
    return {
        'score': score,
        'grade': grade,
        'details': details,
        'explanation': " ".join(details[:2])
    }


def identify_business_model(sector: str = "", industry: str = "") -> Dict[str, Any]:
    """Identify the business model and return appropriate metrics to focus on.
    
    Args:
    - sector: Company sector (e.g., "Technology", "Retail")
    - industry: Company industry (e.g., "Software", "Specialty Retail")
    
    Returns:
    - business_model: SaaS, Retail, Manufacturing, Financial Services, etc.
    - key_metrics: List of metrics that matter for this business
    - red_flags_to_check: Specific red flags for this business model
    - section_6_metric: The ONE metric that matters most for Section 6
    """
    
    sector = (sector or "").lower()
    industry = (industry or "").lower()
    
    # SaaS / Software
    if any(term in sector or term in industry for term in ["software", "saas", "cloud", "technology"]):
        return {
            "business_model": "SaaS/Software",
            "key_metrics": [
                "Revenue Growth %",
                "Gross Margin %",
                "Free Cash Flow",
                "FCF Margin %",
                "Net Revenue Retention %",
                "CAC Payback Period (months)"
            ],
            "red_flags_to_check": [
                "SBC >20% of revenue",
                "CAC payback >18 months",
                "Net revenue retention <110%",
                "Deferred revenue declining",
                "Customer concentration >30%"
            ],
            "section_6_metric": "Net Revenue Retention",
            "section_6_explanation": "Existing customers spending X% more YoY = product is sticky"
        }
    
    # Retail / Consumer
    elif any(term in sector or term in industry for term in ["retail", "consumer", "apparel", "specialty retail"]):
        return {
            "business_model": "Retail/Consumer",
            "key_metrics": [
                "Revenue Growth %",
                "Gross Margin %",
                "Free Cash Flow",
                "FCF Margin %",
                "Same-Store Sales Growth %",
                "Inventory Turnover (days)"
            ],
            "red_flags_to_check": [
                "Same-store sales negative",
                "Inventory growing faster than sales",
                "Inventory days >90",
                "Gross margin compression >100 bps",
                "Store closures accelerating"
            ],
            "section_6_metric": "Same-Store Sales Growth",
            "section_6_explanation": "Existing locations growing = real demand, not just expansion"
        }
    
    # Manufacturing / Industrial
    elif any(term in sector or term in industry for term in ["manufacturing", "industrial", "materials", "chemicals", "aerospace", "defense"]):
        return {
            "business_model": "Manufacturing/Industrial",
            "key_metrics": [
                "Revenue Growth %",
                "Gross Margin %",
                "Free Cash Flow",
                "FCF Margin %",
                "Inventory Turnover",
                "Order Backlog Trend"
            ],
            "red_flags_to_check": [
                "ROIC < Cost of Capital",
                "Capacity utilization <75%",
                "Order backlog declining",
                "Capex >15% of revenue sustained",
                "Working capital ballooning"
            ],
            "section_6_metric": "Inventory Turnover",
            "section_6_explanation": "Higher turns = efficient operations and fresh demand"
        }
    
    # Financial Services
    elif any(term in sector or term in industry for term in ["financial", "bank", "insurance", "capital markets"]):
        return {
            "business_model": "Financial Services",
            "key_metrics": [
                "Revenue Growth %",
                "Net Interest Margin (NIM)",
                "Efficiency Ratio",
                "Return on Equity",
                "Non-Performing Loan Ratio",
                "Tangible Book Value Growth"
            ],
            "red_flags_to_check": [
                "NPL ratio >3%",
                "Efficiency ratio >60%",
                "NIM compressing >20 bps",
                "Loan loss reserves <2%",
                "Tangible book value declining"
            ],
            "section_6_metric": "Net Interest Margin",
            "section_6_explanation": "Spread between lending/borrowing rates = core profitability"
        }
    
    # Default: Generic
    else:
        return {
            "business_model": "General/Other",
            "key_metrics": [
                "Revenue Growth %",
                "Gross Margin %",
                "Free Cash Flow",
                "FCF Margin %",
                "Return on Equity",
                "Debt/EBITDA"
            ],
            "red_flags_to_check": [
                "Negative free cash flow",
                "Debt/EBITDA >4x",
                "ROE <10%",
                "Margins compressing",
                "Revenue growth decelerating"
            ],
            "section_6_metric": "Free Cash Flow Conversion",
            "section_6_explanation": "Converts X% of profit to actual cash = real earnings quality"
        }


def gather_perplexity_data(company_name: str, api_key: str, progress_callback=None) -> Dict[str, Any]:
    """
    Four-pass Perplexity search following official best practices for financial research.
    
    Pass 1A: SEC filings - Core financials (search_mode="sec")
    Pass 1B: SEC filings - Business context & risks (search_mode="sec")
    Pass 2: Current market data (generic web search)
    Pass 3: Earnings call transcript (generic web search with date filter)
    
    Returns:
    - sec_data: Combined financial and context data from SEC
    - market_data: Current price, valuation, analyst targets
    - earnings_quotes: CEO/CFO verbatim quotes (or None)
    - sector/industry: For business model detection
    - all_sources: Combined citations
    """
    
    # CALL 1: Comprehensive SEC Data (consolidating all SEC searches)
    if progress_callback:
        progress_callback(1, "Gathering SEC filing data...")
    print(f"[Call 1/2] Comprehensive SEC data for {company_name}...")
    
    sec_comprehensive_query = f"""Analyze {company_name}'s latest SEC filings (10-Q, 10-K, 8-K from 2024-2025).

**CRITICAL EXTRACTION REQUIREMENTS:**
You MUST extract EXACT DOLLAR AMOUNTS and PERCENTAGES from the financial statements.
Do NOT say "not visible", "not explicitly shown", or "refer to balance sheet" - the numbers ARE in the 10-Q/10-K.

Look in these specific sections:
- Balance Sheet (Consolidated Balance Sheets): Cash, Total Debt, Current Assets/Liabilities
- Income Statement (Consolidated Statements of Operations): Revenue, Net Income/Loss, Operating Income
- Cash Flow Statement: Operating Cash Flow, Free Cash Flow

If you see XBRL tags like "us-gaap_CashAndCashEquivalents", extract the actual dollar value.
Report as: "Cash: $571.6M" NOT "Cash figures are on the balance sheet"

Provide a comprehensive summary including:

**FINANCIALS (from 10-Q/10-K) - WITH ACTUAL DOLLAR AMOUNTS:**
- Cash and cash equivalents: $XXX.X million (extract from most recent balance sheet)
- Total debt (short-term + long-term): $XXX.X million
- Current assets: $XXX.X million
- Current liabilities: $XXX.X million
- Revenue (latest quarter): $XXX.X million
- Net income/loss (latest quarter): $XXX.X million or $(XXX.X) million
- EBITDA (last 12 months): Positive/negative and approximate amount
- Gross margin %: XX.X%
- Operating margin %: XX.X%
- Net profit margin %: XX.X%
- Operating cash flow (latest quarter or TTM): $XXX.X million or $(XXX.X) million
- Free cash flow and FCF margin %
- Revenue growth YoY %: Calculate from current vs year-ago quarter
- Revenue trend: accelerating/stable/decelerating (based on sequential quarters)
- If burning cash: quarterly burn rate in $M
- ROIC %: If calculable

**BUSINESS CONTEXT:**
- Business description (plain English - what do they sell?)
- Industry sector classification
- Top 3 material risk factors from Risk Factors section (be specific with details)
- Any customer concentration (>10% revenue from one customer?)

**RECENT EVENTS (from 8-Ks last 90 days):**
- Material events, acquisitions, debt issuances, etc.
- Latest earnings: beat or miss?
- Latest guidance: raised, maintained, or lowered?
- Margin trends: expanding, stable, or contracting?

**RED FLAGS:**
- Going concern warnings
- Audit issues
- Liquidity concerns
- Material weaknesses

Extract ALL numbers from the actual financial statements. Be thorough and specific.

**FINAL REQUIREMENT:**
At the end of your response, list all SEC filings you referenced under a "SOURCES USED:" section.
Format each as: Filing Type | Date | Full URL

Example:
SOURCES USED:
- 10-Q Q1 2025 | March 31, 2025 | https://www.sec.gov/Archives/edgar/data/1838359/000155837025002499/rgti-20250331x10q.htm
- 10-K FY2024 | Dec 31, 2024 | https://www.sec.gov/Archives/edgar/data/1838359/000155837025001234/rgti-20241231x10k.htm"""

    sec_response = perplexity_request_with_retry(
        api_key=api_key,
        model="sonar-pro",  # Using sonar-pro for high-quality SEC analysis
        messages=[{"role": "user", "content": sec_comprehensive_query}],
        search_mode="sec",
        search_after_date_filter="1/1/2024",
        web_search_options={"search_context_size": "high"},  # Maximum reasoning for complex SEC extraction
        max_retries=5
    )
    
    sec_data = sec_response['choices'][0]['message']['content']
    
    # Extract citations from API metadata or parse from response text
    sec_sources = sec_response.get('citations', [])
    
    if len(sec_sources) == 0:
        # API didn't return citations - parse URLs from response text
        import re
        urls = re.findall(r'https://www\.sec\.gov/[^\s\)\]]+', sec_data)
        sec_sources = [{'url': url, 'title': 'SEC Filing'} for url in urls]
        print(f"[OK] Extracted {len(sec_sources)} SEC citations from response text")
    else:
        print(f"[OK] Got {len(sec_sources)} citations from API metadata")
    
    print(f"[OK] SEC data: {len(sec_data)} chars from {len(sec_sources)} filings")
    
    # Extract sector/industry from SEC data for business model detection
    sec_lower = sec_data.lower()
    sector_match = "Technology"  # Default
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
    
    # CALL 2 will happen in generate_report_with_perplexity()
    # It receives sec_data and does market search + earnings + analysis + HTML generation
    
    return {
        "sec_data": sec_data,
        "market_data": None,  # Not needed - Call 2 searches for this
        "earnings_quotes": None,  # Not needed - Call 2 searches for this
        "sector": sector_match,
        "industry": industry_match,
        "all_sources": sec_sources
    }


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
    
    comprehensive_prompt = f"""You are an expert financial analyst creating a fundamental health score report.

COMPANY: {company_name}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 SEC FILING DATA (ALREADY PROVIDED - DO NOT RE-SEARCH)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{sec_data}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 YOUR TASK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Step 1: Search ONLY for Market & Earnings Data (NOT SEC Filings)**

You already have complete SEC data above. Do NOT search SEC filings again.

Now search ONLY financial news sites for:
1. Current stock price and market cap for {company_name}
   - Sources: Yahoo Finance, Bloomberg, MarketWatch, Google Finance
2. Analyst ratings and price targets
   - Sources: MarketBeat, TipRanks, analyst reports
3. Recent earnings call quotes from CEO/CFO about outlook
   - Sources: Seeking Alpha transcripts, earnings call websites
4. Recent news or developments (last 30 days)
   - Sources: Reuters, Bloomberg, CNBC

**CRITICAL SEARCH CONSTRAINTS:**
- DO search: Yahoo Finance, Bloomberg, MarketWatch, Seeking Alpha, Reuters, CNBC
- DO NOT search: SEC.gov, SEC filings, 10-Q, 10-K, 8-K (we already have this data)

Focus your search on real-time market data and recent analyst commentary.

**Step 2: Analyze Holistically**

Calculate fundamental health score (0-100) based on:

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

**Step 3: Generate 5 Verdicts**

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

**Step 4: Output HTML**

<div class="health-report">
<div class="company-header">
<div class="company-name">{company_name.upper()}</div>
</div>
<div class="health-score-display">
<div class="score-label">FUNDAMENTAL HEALTH</div>
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
            model="sonar-pro",  # Using sonar-pro for high-quality analysis
            messages=[{"role": "user", "content": comprehensive_prompt}],
            web_search_options={"search_context_size": "high"},  # Maximum reasoning for comprehensive analysis
            max_retries=3
        )
        
        html_report = response['choices'][0]['message']['content']
        call2_sources = response.get('citations', [])
        
        html_report = sanitize_and_validate_html(html_report)
        
        print(f"[OK] Report generated: {len(html_report)} chars, {len(call2_sources)} market sources")
        return html_report, call2_sources
        
    except Exception as e:
        print(f"[ERROR] Perplexity report generation failed: {e}")
        return f"<div>Error generating report: {str(e)}</div>", []


def extract_urls_from(text: str) -> List[Dict[str, str]]:
    """Extract unique URLs from text and return as list of dicts."""
    import re
    urls = re.findall(r'https?://[^\s\)]+', text or "")
    seen, out = set(), []
    for u in urls:
        if u not in seen:
            seen.add(u)
            title = u.split("/")[2] if "://" in u else u
            out.append({"url": u, "title": title})
    return out


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

def _extract_sources_and_citations(resp: Any) -> Dict[str, List[Dict[str, str]]]:
    """Extract sources and citations from Responses API output."""
    sources: List[Dict[str, str]] = []
    citations: List[Dict[str, str]] = []

    try:
        output_items = getattr(resp, "output", None) or []
        for item in output_items:
            item_type = getattr(item, "type", None) or (isinstance(item, dict) and item.get("type"))
            if item_type in ("web_search_call", "tool_call"):
                action = getattr(item, "action", None) or (isinstance(item, dict) and item.get("action"))
                if action:
                    srcs = getattr(action, "sources", None) or (isinstance(action, dict) and action.get("sources"))
                    if srcs:
                        for s in srcs:
                            if isinstance(s, dict):
                                url = s.get("url", "")
                                title = s.get("title", url or "Source")
                            else:
                                url = str(s)
                                title = url
                            if url:
                                sources.append({"url": url, "title": title})
            if item_type == "message":
                contents = getattr(item, "content", None) or []
                for c in contents:
                    c_type = getattr(c, "type", None) or (isinstance(c, dict) and c.get("type"))
                    if c_type != "output_text":
                        continue
                    text_piece = getattr(c, "text", None) or (isinstance(c, dict) and c.get("text")) or ""
                    anns = getattr(c, "annotations", None) or (isinstance(c, dict) and c.get("annotations")) or []
                    for a in anns:
                        a_type = getattr(a, "type", None) or (isinstance(a, dict) and a.get("type"))
                        if a_type == "url_citation":
                            url = getattr(a, "url", None) or (isinstance(a, dict) and a.get("url")) or ""
                            title = getattr(a, "title", None) or (isinstance(a, dict) and a.get("title")) or "Source"
                            start = getattr(a, "start_index", 0) or (isinstance(a, dict) and a.get("start_index")) or 0
                            end = getattr(a, "end_index", 0) or (isinstance(a, dict) and a.get("end_index")) or 0
                            span = text_piece[start:end] if (0 <= start < end <= len(text_piece)) else ""
                            if url:
                                citations.append({"url": url, "title": title, "text": span})
    except Exception:
        pass

    return {
        "sources": _dedupe_by_url(sources),
        "citations": _dedupe_by_url(citations)
    }


# =====================================================================
# GPT-5 WRITER FUNCTIONS
# =====================================================================

def clean_financial_report(report_text: str) -> str:
    """DEPRECATED: Minimal cleanup only. Root cause of formatting issues should be fixed in prompts/data extraction.
    
    This function now only fixes the most egregious formatting artifacts.
    The extensive regex operations were a symptom of deeper issues that have been addressed.
    """
    # Only fix obvious encoding/formatting artifacts
    report_text = report_text.replace("∣", "|")  # Broken pipe character
    report_text = report_text.replace("–", "-")  # Em-dash to regular dash
    
    return report_text


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
            "model_used": "Pure Perplexity (sonar-pro)",
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


def _attempt_concat_text_from_output(resp: Any) -> str:
    """Try to concatenate text segments from message.content[] if output_text is empty."""
    try:
        pieces: List[str] = []
        output_items = getattr(resp, "output", None) or []
        for item in output_items:
            if (getattr(item, "type", None) or (isinstance(item, dict) and item.get("type"))) != "message":
                continue
            contents = getattr(item, "content", None) or (isinstance(item, dict) and item.get("content")) or []
            for c in contents:
                ctype = getattr(c, "type", None) or (isinstance(c, dict) and c.get("type"))
                if ctype == "output_text":
                    text_piece = getattr(c, "text", None) or (isinstance(c, dict) and c.get("text")) or ""
                    if text_piece:
                        pieces.append(text_piece)
        return "\n".join(pieces).strip()
    except Exception:
        return ""


# =====================================================================
# yfinance data helpers (optional, not used by web search path)
# =====================================================================

def get_stock_chart(symbol: str) -> Optional[Dict[str, Any]]:
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1y")
        if hist.empty:
            return None
        chart_data = []
        for date, row in hist.iterrows():
            chart_data.append({
                "date": date.strftime("%Y-%m-%d"),
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": int(row["Volume"])
            })
        return {"symbol": symbol, "period": "1y", "data": chart_data}
    except Exception as e:
        print(f"Error fetching stock chart for {symbol}: {e}")
        return None

def get_stock_insights(symbol: str) -> Optional[Dict[str, Any]]:
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        news = ticker.news[:5] if hasattr(ticker, 'news') and ticker.news else []
        recommendations = None
        try:
            recommendations = ticker.recommendations
            if recommendations is not None and not recommendations.empty:
                recommendations = recommendations.tail(10).to_dict('records')
        except Exception:
            pass
        return {
            "symbol": symbol,
            "company_name": info.get("longName", symbol),
            "sector": info.get("sector", "N/A"),
            "industry": info.get("industry", "N/A"),
            "business_summary": info.get("longBusinessSummary", "N/A"),
            "market_cap": info.get("marketCap", "N/A"),
            "enterprise_value": info.get("enterpriseValue", "N/A"),
            "pe_ratio": info.get("trailingPE", "N/A"),
            "forward_pe": info.get("forwardPE", "N/A"),
            "peg_ratio": info.get("pegRatio", "N/A"),
            "price_to_book": info.get("priceToBook", "N/A"),
            "price_to_sales": info.get("priceToSalesTrailing12Months", "N/A"),
            "dividend_yield": info.get("dividendYield", "N/A"),
            "beta": info.get("beta", "N/A"),
            "52_week_high": info.get("fiftyTwoWeekHigh", "N/A"),
            "52_week_low": info.get("fiftyTwoWeekLow", "N/A"),
            "average_volume": info.get("averageVolume", "N/A"),
            "news": news,
            "recommendations": recommendations
        }
    except Exception as e:
        print(f"Error fetching stock insights for {symbol}: {e}")
        return None

# Removed yfinance-dependent functions (get_stock_sec_filing, get_stock_holders, 
# calculate_financial_ratios, get_growth_metrics, get_analyst_data, build_compact_payload)
# Now using pure Perplexity for all financial data


def convert_markdown_to_pdf(markdown_content: str, file_path: str) -> bool:
    try:
        import markdown as md
        from weasyprint import HTML
        disclaimer = """

---

## Disclaimer

This financial analysis report is provided for informational and educational purposes only.
"""
        full_content = markdown_content + disclaimer
        html_content = md.markdown(full_content, extensions=['tables', 'fenced_code'])
        styled_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                @page {{ size: A4; margin: 2cm; }}
                body {{ font-family: 'Helvetica', 'Arial', sans-serif; line-height: 1.6; color: #333; font-size: 11pt; }}
                h1 {{ color: #1a1a1a; border-bottom: 3px solid #0066cc; padding-bottom: 10px; margin-top: 30px; font-size: 24pt; }}
                h2 {{ color: #0066cc; border-bottom: 2px solid #ccc; padding-bottom: 5px; margin-top: 25px; font-size: 18pt; }}
                table {{ border-collapse: collapse; width: 100%; margin: 15px 0; font-size: 10pt; }}
                table th {{ background-color: #0066cc; color: white; padding: 10px; text-align: left; font-weight: bold; }}
                table td {{ border: 1px solid #ddd; padding: 8px; }}
                table tr:nth-child(even) {{ background-color: #f9f9f9; }}
            </style>
        </head>
        <body>{html_content}</body>
        </html>
        """
        HTML(string=styled_html).write_pdf(file_path)
        return os.path.exists(file_path) and os.path.getsize(file_path) > 0
    except Exception as e:
        print(f"Error in PDF conversion: {e}")
        return False


# ============================================================================
# TRADINGVIEW WIDGETS
# ============================================================================

from tradingview_widgets import (
    generate_technical_analysis_widget,
    generate_stock_financials_widget,
    generate_stock_chart_widget
)

from data_extraction import (
    get_technical_context_for_gpt,
    get_financial_context_for_gpt
)

def get_tradingview_technical_analysis(symbol: str) -> Optional[str]:
    try:
        return get_technical_context_for_gpt(symbol)
    except Exception as e:
        print(f"Error getting technical analysis for {symbol}: {e}")
        return None

def get_tradingview_financial_data(symbol: str) -> Optional[str]:
    try:
        return get_financial_context_for_gpt(symbol)
    except Exception as e:
        print(f"Error getting financial data for {symbol}: {e}")
        return None

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
