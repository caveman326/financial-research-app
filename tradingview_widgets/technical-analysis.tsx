'use client'

import React, { useEffect, useRef, memo } from 'react'

interface TechnicalAnalysisProps {
  symbol: string
  interval?: string
  displayMode?: 'single' | 'multiple'
  colorTheme?: 'light' | 'dark'
  isTransparent?: boolean
  width?: number | string
  height?: number | string
  showIntervalTabs?: boolean
}

export default function TechnicalAnalysis({ 
  symbol,
  interval = '1m',
  displayMode = 'single',
  colorTheme = 'light',
  isTransparent = false,
  width = 425,
  height = 450,
  showIntervalTabs = true
}: TechnicalAnalysisProps) {
  const container = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!container.current) return
    
    // Clear any existing content
    container.current.innerHTML = ''
    
    const script = document.createElement('script')
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-technical-analysis.js'
    script.type = 'text/javascript'
    script.async = true
    script.innerHTML = JSON.stringify({
      colorTheme,
      displayMode,
      isTransparent,
      locale: 'en',
      interval,
      disableInterval: false,
      width,
      height,
      symbol,
      showIntervalTabs
    })
    
    container.current.appendChild(script)
  }, [symbol, interval, displayMode, colorTheme, isTransparent, width, height, showIntervalTabs])

  return (
    <div className="tradingview-widget-container" ref={container}>
      <div className="tradingview-widget-container__widget"></div>
      <div className="tradingview-widget-copyright">
        <a
          href={`https://www.tradingview.com/symbols/${symbol}/technicals/`}
          rel="noopener nofollow"
          target="_blank"
        >
          <span className="blue-text">{symbol} stock analysis</span>
        </a>
        <span className="trademark"> by TradingView</span>
      </div>
    </div>
  )
}
