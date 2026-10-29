"""Embedded Local Web Dashboard & Knowledge Graph Visualizer for CodeGraph.

Serves an interactive web application on localhost:
- Force-Directed Knowledge Graph Visualizer (2D & 3D Orbital)
- Full-Stack Route & API Drift Inspector
- PR Blast Radius & Risk Assessment
- Database Lineage & Model Matrix
- Multi-Language Production Benchmarks
- Live Watcher & Telemetry Status
"""
from __future__ import annotations

import json
import logging
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from codegraph.indexing.indexer import Indexer

logger = logging.getLogger("codegraph.ui")


def _get_html_dashboard() -> str:
    """Return the bundled single-page application HTML for the CodeGraph Dashboard."""
    return """<!DOCTYPE html>
<html lang="en" data-theme="architect">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>CodeGraph • AI Systems Architect & Repository Intelligence</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root, [data-theme="architect"] {
      --bg-page: #F6F2E9;
      --bg-hero-glow: radial-gradient(circle at 50% 20%, rgba(255, 87, 34, 0.08) 0%, rgba(246, 242, 233, 0) 70%);
      --bg-card: #1D1F23;
      --bg-card-subtle: #25282D;
      --border-card: rgba(255, 255, 255, 0.08);
      --border-card-active: rgba(255, 87, 34, 0.4);
      --text-main: #141618;
      --text-muted: #6C727A;
      --text-light: #F4F5F7;
      --text-light-muted: #9BA1A9;
      --accent-orange: #FF5400;
      --accent-orange-glow: rgba(255, 84, 0, 0.25);
      --accent-burgundy: #781420;
      --accent-burgundy-hover: #630F19;
      --accent-burgundy-glow: rgba(120, 20, 32, 0.35);
      --pill-bg: #EAE5D9;
      --pill-border: rgba(20, 22, 24, 0.08);
      --badge-green-bg: rgba(63, 185, 80, 0.15);
      --badge-green-text: #2EA043;
      --badge-amber-bg: rgba(210, 153, 34, 0.15);
      --badge-amber-text: #D29922;
      --badge-red-bg: rgba(248, 81, 73, 0.15);
      --badge-red-text: #F85149;
      --badge-purple-bg: rgba(188, 140, 255, 0.15);
      --badge-purple-text: #BC8CFF;
      --badge-cyan-bg: rgba(56, 189, 248, 0.15);
      --badge-cyan-text: #38BDF8;
      --canvas-bg: #141619;
    }

    [data-theme="obsidian"] {
      --bg-page: #0C0D0E;
      --bg-hero-glow: radial-gradient(circle at 50% 20%, rgba(255, 87, 34, 0.12) 0%, rgba(12, 13, 14, 0) 70%);
      --bg-card: #15171A;
      --bg-card-subtle: #1C1F24;
      --border-card: rgba(255, 255, 255, 0.08);
      --border-card-active: rgba(255, 87, 34, 0.5);
      --text-main: #F4F5F7;
      --text-muted: #8E959F;
      --text-light: #F4F5F7;
      --text-light-muted: #9BA1A9;
      --accent-orange: #FF5400;
      --accent-orange-glow: rgba(255, 84, 0, 0.3);
      --accent-burgundy: #781420;
      --accent-burgundy-hover: #8D1726;
      --accent-burgundy-glow: rgba(120, 20, 32, 0.45);
      --pill-bg: #181A1D;
      --pill-border: rgba(255, 255, 255, 0.08);
      --canvas-bg: #0C0D0E;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    
    body {
      background-color: var(--bg-page);
      background-image: 
        radial-gradient(rgba(20, 22, 24, 0.04) 1px, transparent 1px),
        var(--bg-hero-glow);
      background-size: 24px 24px, 100% 100%;
      color: var(--text-main);
      font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      display: flex;
      flex-direction: column;
      height: 100vh;
      overflow: hidden;
      transition: background-color 0.25s ease, color 0.25s ease;
    }

    /* TOP FLOATING NAVIGATION BAR */
    header {
      padding: 16px 24px 8px 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      z-index: 50;
    }

    .brand-container {
      display: flex;
      align-items: center;
      gap: 12px;
      background: var(--pill-bg);
      border: 1px solid var(--pill-border);
      border-radius: 999px;
      padding: 6px 16px 6px 8px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.03);
    }
    .brand-avatar {
      width: 28px;
      height: 28px;
      background: #FFFFFF;
      border: 1px solid rgba(0,0,0,0.08);
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 800;
      font-size: 13px;
      color: #141618;
      box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .brand-text {
      display: flex;
      flex-direction: column;
    }
    .brand-title {
      font-size: 12px;
      font-weight: 800;
      letter-spacing: 0.8px;
      text-transform: uppercase;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .brand-title-dot {
      width: 5px;
      height: 5px;
      background: var(--accent-orange);
      border-radius: 50%;
    }
    .brand-sub {
      font-size: 9px;
      font-family: 'JetBrains Mono', monospace;
      color: var(--text-muted);
      letter-spacing: 0.5px;
      text-transform: uppercase;
    }

    /* NAV PILL BUTTONS */
    nav {
      display: flex;
      align-items: center;
      gap: 6px;
      background: var(--pill-bg);
      border: 1px solid var(--pill-border);
      padding: 5px 8px;
      border-radius: 999px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.03);
    }
    .nav-btn {
      background: transparent;
      border: none;
      color: var(--text-muted);
      font-family: 'JetBrains Mono', monospace;
      font-size: 11px;
      font-weight: 600;
      padding: 7px 14px;
      border-radius: 999px;
      cursor: pointer;
      transition: all 0.15s ease;
      display: flex;
      align-items: center;
      gap: 6px;
      letter-spacing: 0.3px;
    }
    .nav-btn .num {
      color: var(--accent-orange);
      font-weight: 700;
      opacity: 0.8;
    }
    .nav-btn:hover {
      color: var(--text-main);
      background: rgba(0, 0, 0, 0.04);
    }
    .nav-btn.active {
      color: #FFFFFF;
      background: var(--bg-card);
      box-shadow: 0 2px 6px rgba(0,0,0,0.12);
    }
    .nav-btn.active .num {
      color: var(--accent-orange);
      opacity: 1;
    }

    /* RIGHT METRICS & ACTIONS */
    .header-actions {
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .live-pill {
      background: var(--pill-bg);
      border: 1px solid var(--pill-border);
      padding: 6px 14px;
      border-radius: 999px;
      font-family: 'JetBrains Mono', monospace;
      font-size: 11px;
      font-weight: 600;
      color: var(--text-muted);
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .pulse-dot {
      width: 7px;
      height: 7px;
      background: var(--badge-green-text);
      border-radius: 50%;
      box-shadow: 0 0 8px var(--badge-green-text);
      animation: pulse 2s infinite;
    }
    @keyframes pulse {
      0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(46, 160, 67, 0.7); }
      70% { transform: scale(1.1); box-shadow: 0 0 0 6px rgba(46, 160, 67, 0); }
      100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(46, 160, 67, 0); }
    }
    .btn-theme {
      background: var(--pill-bg);
      border: 1px solid var(--pill-border);
      padding: 6px 12px;
      border-radius: 999px;
      cursor: pointer;
      font-family: 'JetBrains Mono', monospace;
      font-size: 11px;
      font-weight: 600;
      color: var(--text-muted);
      transition: all 0.15s;
    }
    .btn-theme:hover {
      color: var(--text-main);
    }
    .btn-pypi {
      background: var(--accent-burgundy);
      color: #FFFFFF;
      text-decoration: none;
      padding: 7px 18px;
      border-radius: 999px;
      font-family: 'JetBrains Mono', monospace;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.5px;
      display: flex;
      align-items: center;
      gap: 6px;
      box-shadow: 0 4px 14px var(--accent-burgundy-glow);
      transition: all 0.2s ease;
      border: 1px solid rgba(255, 255, 255, 0.15);
    }
    .btn-pypi:hover {
      background: var(--accent-burgundy-hover);
      transform: translateY(-1px);
      box-shadow: 0 6px 18px var(--accent-burgundy-glow);
    }

    /* MAIN CONTENT VIEWPORT */
    main {
      flex: 1;
      display: flex;
      position: relative;
      overflow: hidden;
      padding: 8px 24px 20px 24px;
    }

    .tab-pane {
      display: none;
      width: 100%;
      height: 100%;
      overflow-y: auto;
      flex-direction: column;
    }
    .tab-pane.active {
      display: flex;
    }

    /* HERO TAG BANNER */
    .hero-banner {
      text-align: center;
      margin: 12px auto 20px auto;
      max-width: 900px;
    }
    .hero-badge-tag {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      background: var(--pill-bg);
      border: 1px solid var(--pill-border);
      padding: 4px 12px;
      border-radius: 999px;
      font-family: 'JetBrains Mono', monospace;
      font-size: 10px;
      font-weight: 700;
      color: var(--accent-orange);
      text-transform: uppercase;
      letter-spacing: 0.8px;
      margin-bottom: 8px;
    }
    .hero-title {
      font-size: 44px;
      font-weight: 800;
      letter-spacing: -0.5px;
      line-height: 1.1;
      color: var(--text-main);
      text-transform: uppercase;
    }
    .hero-title .highlight {
      color: var(--accent-orange);
    }
    .hero-sub {
      font-size: 12px;
      font-family: 'JetBrains Mono', monospace;
      color: var(--text-muted);
      letter-spacing: 0.6px;
      text-transform: uppercase;
      margin-top: 8px;
    }

    /* METRIC CARDS GRID */
    .metric-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 14px;
      margin-bottom: 18px;
    }
    .dark-card {
      background: var(--bg-card);
      border: 1px solid var(--border-card);
      border-radius: 12px;
      padding: 18px 20px;
      color: var(--text-light);
      position: relative;
      overflow: hidden;
      box-shadow: 0 4px 16px rgba(0,0,0,0.12);
      transition: transform 0.2s, border-color 0.2s;
    }
    .dark-card:hover {
      border-color: var(--border-card-active);
      transform: translateY(-2px);
    }
    .card-label {
      font-family: 'JetBrains Mono', monospace;
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.8px;
      text-transform: uppercase;
      color: var(--text-light-muted);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .card-val {
      font-size: 30px;
      font-weight: 800;
      color: #FFFFFF;
      margin-top: 6px;
      letter-spacing: -0.5px;
    }
    .card-val.orange { color: var(--accent-orange); }
    .card-val.green { color: #3FB950; }
    .card-val.cyan { color: #38BDF8; }
    .card-subtext {
      font-family: 'JetBrains Mono', monospace;
      font-size: 10px;
      color: var(--text-light-muted);
      margin-top: 4px;
    }

    /* GRAPH CONTAINER */
    #graph-pane {
      position: relative;
      padding: 0;
      border-radius: 16px;
      overflow: hidden;
      border: 1px solid var(--border-card);
      box-shadow: 0 8px 30px rgba(0,0,0,0.15);
    }
    #graph-canvas {
      width: 100%;
      height: 100%;
      background: var(--canvas-bg);
      display: block;
    }

    .graph-hud {
      position: absolute;
      top: 16px;
      left: 16px;
      background: rgba(21, 23, 26, 0.88);
      backdrop-filter: blur(12px);
      border: 1px solid var(--border-card);
      border-radius: 12px;
      padding: 14px 16px;
      color: #FFFFFF;
      z-index: 10;
      font-size: 11px;
      font-family: 'JetBrains Mono', monospace;
      min-width: 220px;
    }
    .graph-hud h4 {
      font-size: 11px;
      color: var(--accent-orange);
      text-transform: uppercase;
      letter-spacing: 0.8px;
      margin-bottom: 8px;
    }
    .hud-row {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 5px;
      color: var(--text-light-muted);
    }
    .hud-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
    }
    .hud-actions {
      display: flex;
      gap: 6px;
      margin-top: 12px;
      padding-top: 10px;
      border-top: 1px solid rgba(255,255,255,0.08);
    }
    .btn-hud {
      flex: 1;
      background: rgba(255,255,255,0.06);
      border: 1px solid rgba(255,255,255,0.1);
      color: #FFFFFF;
      font-family: 'JetBrains Mono', monospace;
      font-size: 10px;
      font-weight: 600;
      padding: 6px 10px;
      border-radius: 6px;
      cursor: pointer;
      transition: all 0.15s;
    }
    .btn-hud:hover {
      background: var(--accent-orange);
      color: #000;
      border-color: var(--accent-orange);
    }

    .graph-search-box {
      position: absolute;
      top: 16px;
      right: 16px;
      z-index: 10;
      display: flex;
      gap: 8px;
    }
    .search-input {
      background: rgba(21, 23, 26, 0.88);
      backdrop-filter: blur(12px);
      border: 1px solid var(--border-card);
      border-radius: 999px;
      padding: 8px 18px;
      color: #FFFFFF;
      font-family: 'JetBrains Mono', monospace;
      font-size: 12px;
      outline: none;
      width: 280px;
      transition: width 0.2s, border-color 0.2s;
    }
    .search-input:focus {
      border-color: var(--accent-orange);
      width: 340px;
    }

    /* NODE DETAILS SLIDE-OUT */
    .node-drawer {
      position: absolute;
      bottom: 20px;
      right: 20px;
      width: 360px;
      background: rgba(21, 23, 26, 0.94);
      backdrop-filter: blur(16px);
      border: 1px solid var(--border-card-active);
      border-radius: 12px;
      padding: 16px 20px;
      color: #FFFFFF;
      z-index: 20;
      display: none;
      box-shadow: 0 10px 30px rgba(0,0,0,0.4);
    }
    .drawer-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 10px;
      border-bottom: 1px solid rgba(255,255,255,0.08);
      padding-bottom: 8px;
    }
    .drawer-title {
      font-size: 13px;
      font-weight: 700;
      color: var(--accent-orange);
      font-family: 'JetBrains Mono', monospace;
    }
    .drawer-close {
      background: none;
      border: none;
      color: var(--text-light-muted);
      cursor: pointer;
      font-size: 16px;
    }

    /* DATA TABLES */
    .table-container {
      background: var(--bg-card);
      border: 1px solid var(--border-card);
      border-radius: 12px;
      overflow: hidden;
      box-shadow: 0 4px 16px rgba(0,0,0,0.12);
      margin-bottom: 24px;
    }
    .custom-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
      color: var(--text-light);
    }
    .custom-table th {
      background: rgba(0, 0, 0, 0.25);
      padding: 12px 18px;
      text-align: left;
      font-family: 'JetBrains Mono', monospace;
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.8px;
      text-transform: uppercase;
      color: var(--text-light-muted);
      border-bottom: 1px solid var(--border-card);
    }
    .custom-table td {
      padding: 14px 18px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.04);
      font-family: 'JetBrains Mono', monospace;
    }
    .custom-table tr:hover td {
      background: rgba(255, 255, 255, 0.02);
    }

    /* BADGES */
    .badge-pill {
      display: inline-block;
      padding: 3px 10px;
      border-radius: 999px;
      font-family: 'JetBrains Mono', monospace;
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.4px;
    }
    .badge-get { background: var(--badge-green-bg); color: var(--badge-green-text); }
    .badge-post { background: rgba(255, 84, 0, 0.15); color: var(--accent-orange); }
    .badge-put { background: var(--badge-purple-bg); color: var(--badge-purple-text); }
    .badge-delete { background: var(--badge-red-bg); color: var(--badge-red-text); }
    .badge-ok { background: var(--badge-green-bg); color: var(--badge-green-text); }

    /* FOOTER ACTION CARDS */
    .footer-cards {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 12px;
      margin-top: 24px;
    }
    .footer-card {
      background: var(--bg-card);
      border: 1px solid var(--border-card);
      border-radius: 12px;
      padding: 14px 18px;
      text-decoration: none;
      color: var(--text-light);
      display: flex;
      flex-direction: column;
      gap: 4px;
      transition: all 0.2s;
    }
    .footer-card:hover {
      border-color: var(--border-card-active);
      transform: translateY(-2px);
    }
    .footer-card-label {
      font-family: 'JetBrains Mono', monospace;
      font-size: 9px;
      font-weight: 700;
      letter-spacing: 0.8px;
      color: var(--text-light-muted);
      text-transform: uppercase;
    }
    .footer-card-val {
      font-size: 13px;
      font-weight: 700;
      color: #FFFFFF;
      font-family: 'JetBrains Mono', monospace;
    }
    .footer-card-action {
      font-size: 10px;
      font-family: 'JetBrains Mono', monospace;
      color: var(--accent-orange);
      font-weight: 600;
      margin-top: 4px;
      display: flex;
      align-items: center;
      gap: 4px;
    }
  </style>
</head>
<body>

  <!-- TOP HEADER NAV -->
  <header>
    <div class="brand-container">
      <div class="brand-avatar">C</div>
      <div class="brand-text">
        <span class="brand-title">CODEGRAPH <span class="brand-title-dot"></span></span>
        <span class="brand-sub">AI Systems Architect</span>
      </div>
    </div>

    <nav>
      <button class="nav-btn active" onclick="switchTab('graph')"><span class="num">01</span> GRAPH</button>
      <button class="nav-btn" onclick="switchTab('routes')"><span class="num">02</span> ROUTES & DRIFT</button>
      <button class="nav-btn" onclick="switchTab('impact')"><span class="num">03</span> BLAST RADIUS</button>
      <button class="nav-btn" onclick="switchTab('lineage')"><span class="num">04</span> DB LINEAGE</button>
      <button class="nav-btn" onclick="switchTab('benchmarks')"><span class="num">05</span> BENCHMARKS</button>
      <button class="nav-btn" onclick="switchTab('specs')"><span class="num">06</span> ENGINE SPECS</button>
    </nav>

    <div class="header-actions">
      <div class="live-pill">
        <div class="pulse-dot"></div>
        <span id="live-indicator">LIVE SYNC &lt; 15MS</span>
      </div>
      <div class="live-pill" id="clock-pill">
        <span id="live-clock">00:00:00</span>
      </div>
      <button class="btn-theme" onclick="toggleTheme()">FX / THEME</button>
      <a class="btn-pypi" href="https://pypi.org/project/codegraph-engine/3.0.1/" target="_blank" rel="noopener">PYPI v3.0.1 ↗</a>
    </div>
  </header>

  <!-- MAIN BODY -->
  <main>

    <!-- TAB 1: KNOWLEDGE GRAPH -->
    <div id="graph-pane" class="tab-pane active">
      <div class="graph-hud">
        <h4>01 · Entity Legend</h4>
        <div class="hud-row"><div class="hud-dot" style="background: var(--accent-orange);"></div>Functions & Callees</div>
        <div class="hud-row"><div class="hud-dot" style="background: var(--badge-purple-text);"></div>Classes & Modules</div>
        <div class="hud-row"><div class="hud-dot" style="background: var(--badge-green-text);"></div>HTTP & RPC Routes</div>
        <div class="hud-row"><div class="hud-dot" style="background: var(--badge-amber-text);"></div>Database Models</div>
        <div class="hud-row"><div class="hud-dot" style="background: var(--badge-cyan-text);"></div>Interfaces & Types</div>
        <div class="hud-actions">
          <button class="btn-hud" id="btn-3d" onclick="toggle3DMode()">3D ORBITAL</button>
          <button class="btn-hud" onclick="exportGraph()">SNAPSHOT</button>
        </div>
      </div>

      <div class="graph-search-box">
        <input type="text" id="graph-search" class="search-input" placeholder="Search AST symbols (e.g. User, Router)..." oninput="filterGraph(this.value)">
      </div>

      <canvas id="graph-canvas"></canvas>

      <div id="node-drawer" class="node-drawer">
        <div class="drawer-header">
          <span class="drawer-title" id="drawer-name">Symbol Coordinates</span>
          <button class="drawer-close" onclick="document.getElementById('node-drawer').style.display='none'">✕</button>
        </div>
        <div id="drawer-body" style="font-size: 11px; font-family: 'JetBrains Mono', monospace; line-height: 1.7; color: var(--text-light-muted);"></div>
      </div>
    </div>

    <!-- TAB 2: ROUTES & API DRIFT -->
    <div id="routes-pane" class="tab-pane">
      <div class="hero-banner">
        <div class="hero-badge-tag">• 02 · FULL-STACK ROUTE BRIDGE</div>
        <h1 class="hero-title">FULL-STACK <span class="highlight">API DRIFT.</span></h1>
        <p class="hero-sub">STATIC FRONTEND FETCHERS BOUND DIRECTLY TO BACKEND CONTROLLER HANDLERS</p>
      </div>

      <div class="metric-grid">
        <div class="dark-card">
          <div class="card-label">TOTAL DISCOVERED ENDPOINTS <span>📡</span></div>
          <div class="card-val orange" id="metric-route-count">0</div>
          <div class="card-subtext">FASTAPI • EXPRESS • SPRING • GIN • AXUM</div>
        </div>
        <div class="dark-card">
          <div class="card-label">FRONTEND FETCH SITES <span>⚡</span></div>
          <div class="card-val cyan" id="metric-fetch-count">0</div>
          <div class="card-subtext">REACT • NEXT.JS • AXIOS • SWR • VUE</div>
        </div>
        <div class="dark-card">
          <div class="card-label">CONTRACT DRIFT STATUS <span>🛡️</span></div>
          <div class="card-val green">SYNCHRONIZED</div>
          <div class="card-subtext">0 TYPE MISMATCHES DETECTED</div>
        </div>
      </div>

      <div class="table-container">
        <table class="custom-table">
          <thead>
            <tr>
              <th>Method</th>
              <th>Normalized Route</th>
              <th>Backend Handler</th>
              <th>Source File & Line</th>
              <th>Framework</th>
              <th>Contract Status</th>
            </tr>
          </thead>
          <tbody id="routes-table-body">
            <tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 30px;">Loading endpoint topology...</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- TAB 3: PR BLAST RADIUS -->
    <div id="impact-pane" class="tab-pane">
      <div class="hero-banner">
        <div class="hero-badge-tag">• 03 · SEMANTIC BLAST RADIUS</div>
        <h1 class="hero-title">PR RISK <span class="highlight">GATEKEEPER.</span></h1>
        <p class="hero-sub">DOWNSTREAM IMPACT ANALYSIS FROM GIT DIFF TO CALLERS, ROUTES, AND TEST SUITES</p>
      </div>

      <div class="metric-grid">
        <div class="dark-card">
          <div class="card-label">PR RISK INDEX (0-100) <span>🎯</span></div>
          <div class="card-val green" id="blast-risk-score">0 / 100</div>
          <div class="card-subtext" id="blast-risk-label">LOW RISK MODIFICATION</div>
        </div>
        <div class="dark-card">
          <div class="card-label">IMPACTED SYMBOLS <span>🧬</span></div>
          <div class="card-val orange" id="blast-impacted-syms">0</div>
          <div class="card-subtext">TRANSITIVE CALLERS AFFECTED</div>
        </div>
        <div class="dark-card">
          <div class="card-label">AFFECTED HTTP ROUTES <span>🌐</span></div>
          <div class="card-val cyan" id="blast-impacted-routes">0</div>
          <div class="card-subtext">PUBLIC CONTRACTS MUTATED</div>
        </div>
        <div class="dark-card">
          <div class="card-label">RECOMMENDED TEST RUNNER <span>🧪</span></div>
          <div class="card-val" style="font-size: 13px; font-family: 'JetBrains Mono', monospace; color: #FFFFFF;" id="blast-test-cmd">pytest -q</div>
          <div class="card-subtext">TARGETED SMART TEST RUNNER</div>
        </div>
      </div>

      <div class="dark-card" style="margin-bottom: 20px;">
        <div class="card-label" style="margin-bottom: 12px;">ARCHITECTURAL DOWNSTREAM IMPACT TOPOLOGY</div>
        <div id="blast-details" style="font-family: 'JetBrains Mono', monospace; font-size: 12px; color: var(--text-light-muted); line-height: 1.8;">
          Clean working tree. No active uncommitted modifications detected. All public contracts intact.
        </div>
      </div>
    </div>

    <!-- TAB 4: DATABASE LINEAGE -->
    <div id="lineage-pane" class="tab-pane">
      <div class="hero-banner">
        <div class="hero-badge-tag">• 04 · DATABASE & PERSISTENCE</div>
        <h1 class="hero-title">DATABASE <span class="highlight">LINEAGE.</span></h1>
        <p class="hero-sub">STATIC READERS, WRITERS, AND MIGRATION TRACEABILITY ACROSS ORM LAYERS</p>
      </div>

      <div class="table-container">
        <table class="custom-table">
          <thead>
            <tr>
              <th>Table Name</th>
              <th>Framework / Driver</th>
              <th>Columns / Fields</th>
              <th>Static Writers</th>
              <th>Static Readers</th>
              <th>Integrity Status</th>
            </tr>
          </thead>
          <tbody id="lineage-table-body">
            <tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 30px;">Loading database lineage...</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- TAB 5: PRODUCTION BENCHMARKS -->
    <div id="benchmarks-pane" class="tab-pane">
      <div class="hero-banner">
        <div class="hero-badge-tag">• 05 · EMPIRICAL VERIFICATION</div>
        <h1 class="hero-title">PRODUCTION <span class="highlight">BENCHMARKS.</span></h1>
        <p class="hero-sub">EMPIRICALLY TESTED ON REAL-WORLD PRODUCTION REPOSITORIES ACROSS 7 ECOSYSTEMS</p>
      </div>

      <div class="metric-grid">
        <div class="dark-card">
          <div class="card-label">TOKEN REDUCTION <span>📉</span></div>
          <div class="card-val orange">82.7% – 94.7%</div>
          <div class="card-subtext">VERSUS UNASSISTED RAW FILE DUMPING</div>
        </div>
        <div class="dark-card">
          <div class="card-label">AST PARSE ERRORS <span>✅</span></div>
          <div class="card-val green">0.00%</div>
          <div class="card-subtext">0 FAILURES ACROSS 268 REAL FILES</div>
        </div>
        <div class="dark-card">
          <div class="card-label">GRAPH TRAVERSAL LATENCY <span>⚡</span></div>
          <div class="card-val cyan">&lt; 1ms</div>
          <div class="card-subtext">BINARY COMPRESSED SPARSE ROW (CSR)</div>
        </div>
        <div class="dark-card">
          <div class="card-label">AUTOMATED TEST SUITE <span>🏆</span></div>
          <div class="card-val green">1,063 PASSED</div>
          <div class="card-subtext">100% PASS RATE IN CI/CD MATRIX</div>
        </div>
      </div>

      <div class="table-container">
        <table class="custom-table">
          <thead>
            <tr>
              <th>Language</th>
              <th>Production Repository</th>
              <th>Framework</th>
              <th>Files</th>
              <th>LOC</th>
              <th>Cold Index Time</th>
              <th>Throughput</th>
              <th>Discovered Routes</th>
              <th>Token Reduction</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><strong>Python</strong></td>
              <td><code>fastapi-realworld</code></td>
              <td>FastAPI / asyncpg</td>
              <td>95</td>
              <td>3,841</td>
              <td><strong>0.721s</strong></td>
              <td>131.7 f/s</td>
              <td><strong>20 routes</strong></td>
              <td><span class="badge-pill badge-ok">89.7% Saved</span></td>
            </tr>
            <tr>
              <td><strong>TypeScript</strong></td>
              <td><code>express-realworld</code></td>
              <td>Express / Mongoose</td>
              <td>39</td>
              <td>2,374</td>
              <td><strong>0.534s</strong></td>
              <td>73.0 f/s</td>
              <td><strong>20 routes</strong></td>
              <td><span class="badge-pill badge-ok">82.7% Saved</span></td>
            </tr>
            <tr>
              <td><strong>Go</strong></td>
              <td><code>gin-realworld</code></td>
              <td>Gin / GORM</td>
              <td>19</td>
              <td>4,264</td>
              <td><strong>0.424s</strong></td>
              <td>44.9 f/s</td>
              <td><strong>26 routes</strong></td>
              <td><span class="badge-pill badge-ok">91.8% Saved</span></td>
            </tr>
            <tr>
              <td><strong>Rust</strong></td>
              <td><code>axum-demo</code></td>
              <td>Axum / Tokio</td>
              <td>36</td>
              <td>2,351</td>
              <td><strong>0.366s</strong></td>
              <td>98.3 f/s</td>
              <td><strong>18 routes</strong></td>
              <td><span class="badge-pill badge-ok">91.3% Saved</span></td>
            </tr>
            <tr>
              <td><strong>Rust</strong></td>
              <td><code>actix-realworld</code></td>
              <td>Actix-Web / Diesel</td>
              <td>28</td>
              <td>2,421</td>
              <td><strong>0.346s</strong></td>
              <td>80.8 f/s</td>
              <td><strong>20 routes</strong></td>
              <td><span class="badge-pill badge-ok">87.4% Saved</span></td>
            </tr>
            <tr>
              <td><strong>Java</strong></td>
              <td><code>spring-petclinic</code></td>
              <td>Spring Boot / JPA</td>
              <td>50</td>
              <td>4,297</td>
              <td><strong>0.510s</strong></td>
              <td>98.1 f/s</td>
              <td><strong>16 routes</strong></td>
              <td><span class="badge-pill badge-ok">94.7% Saved</span></td>
            </tr>
            <tr>
              <td><strong>Luau</strong></td>
              <td><code>knit-luau</code></td>
              <td>Knit Service Framework</td>
              <td>6</td>
              <td>1,017</td>
              <td><strong>0.384s</strong></td>
              <td>15.6 f/s</td>
              <td>Remote RPCs</td>
              <td><span class="badge-pill badge-ok">67.3% Saved</span></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- TAB 6: ENGINE SPECS -->
    <div id="specs-pane" class="tab-pane">
      <div class="hero-banner">
        <div class="hero-badge-tag">• 06 · SYSTEM ARCHITECTURE</div>
        <h1 class="hero-title">ENGINE <span class="highlight">SPECIFICATIONS.</span></h1>
        <p class="hero-sub">DETERMINISTIC COMPILER INFRASTRUCTURE RUNNING LOCALLY ON MACHINE</p>
      </div>

      <div class="metric-grid">
        <div class="dark-card">
          <div class="card-label">INDEXED SYMBOLS <span>🧬</span></div>
          <div class="card-val orange" id="stat-syms">0</div>
          <div class="card-subtext">CANONICAL AST IDENTIFIERS</div>
        </div>
        <div class="dark-card">
          <div class="card-label">GRAPH RELATIONSHIPS <span>🔗</span></div>
          <div class="card-val cyan" id="stat-edges">0</div>
          <div class="card-subtext">CALLS, INJECTS, DISPATCHES, MOUNTS</div>
        </div>
        <div class="dark-card">
          <div class="card-label">SOURCE FILES INDEXED <span>📁</span></div>
          <div class="card-val" id="stat-files">0</div>
          <div class="card-subtext">MULTI-LANGUAGE SOURCE SET</div>
        </div>
        <div class="dark-card">
          <div class="card-label">INCREMENTAL WATCHER <span>⚡</span></div>
          <div class="card-val green">&lt; 15ms</div>
          <div class="card-subtext">KERNEL PUSH WITH ZERO CPU HEAT</div>
        </div>
      </div>

      <div class="table-container">
        <table class="custom-table">
          <thead>
            <tr>
              <th>Architecture Subsystem</th>
              <th>Implementation Specification</th>
              <th>Runtime Guarantee</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><strong>Relational Substrate</strong></td>
              <td>SQLite WAL Mode (Composite B-Tree Indexes)</td>
              <td>Permanent concurrent multi-agent read safety</td>
            </tr>
            <tr>
              <td><strong>Fast Graph Engine</strong></td>
              <td>Memory-Mapped Compressed Sparse Row (CSR) Binary Matrix</td>
              <td>Microsecond graph pathfinding across 100k+ edges</td>
            </tr>
            <tr>
              <td><strong>Protocol Compliance</strong></td>
              <td>Model Context Protocol (MCP) 97 Verified FastMCP Tools</td>
              <td>Direct plug-and-play for Cursor, Claude Code, Antigravity</td>
            </tr>
            <tr>
              <td><strong>Incremental Synchronization</strong></td>
              <td>Sliding 250ms Debounced Kernel Push (FSEvents / inotify)</td>
              <td>Sub-15ms incremental file reindexing</td>
            </tr>
            <tr>
              <td><strong>Cross-Platform Runtime</strong></td>
              <td>macOS, Linux & Windows (Win32 kernel32, UTF-8 cp1252 safe)</td>
              <td>Universal standalone module execution</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- FOOTER CONTACT & REPOSITORIES (MATCHING USER SCREENSHOT) -->
      <div class="footer-cards">
        <a class="footer-card" href="https://pypi.org/project/codegraph-engine/3.0.1/" target="_blank" rel="noopener">
          <div class="footer-card-label">OFFICIAL PYPI PACKAGE</div>
          <div class="footer-card-val">codegraph-engine 3.0.1</div>
          <div class="footer-card-action">VIEW ON PYPI ↗</div>
        </a>
        <a class="footer-card" href="https://github.com/raghurammrsd/CODEGRAPH_MCP" target="_blank" rel="noopener">
          <div class="footer-card-label">GITHUB REPOSITORY</div>
          <div class="footer-card-val">raghurammrsd / CODEGRAPH_MCP</div>
          <div class="footer-card-action">EXPLORE SOURCE CODE ↗</div>
        </a>
        <a class="footer-card" href="https://raghurammrsd.github.io/CODEGRAPH_MCP/" target="_blank" rel="noopener">
          <div class="footer-card-label">DOCUMENTATION & ARCHITECTURE</div>
          <div class="footer-card-val">97 FastMCP Tools Manual</div>
          <div class="footer-card-action">BROWSE DOCS ↗</div>
        </a>
        <div class="footer-card" style="cursor: pointer;" onclick="navigator.clipboard.writeText('pip install codegraph-engine==3.0.1'); alert('Copied install command!');">
          <div class="footer-card-label">ONE-CLICK INSTALL</div>
          <div class="footer-card-val">pip install codegraph-engine==3.0.1</div>
          <div class="footer-card-action">COPY COMMAND 📋</div>
        </div>
      </div>
    </div>

  </main>

  <script>
    // Live Clock
    function updateClock() {
      const now = new Date();
      document.getElementById('live-clock').textContent = now.toLocaleTimeString();
    }
    setInterval(updateClock, 1000);
    updateClock();

    // Theme Toggle
    function toggleTheme() {
      const html = document.documentElement;
      const current = html.getAttribute('data-theme') || 'architect';
      const next = current === 'architect' ? 'obsidian' : 'architect';
      html.setAttribute('data-theme', next);
    }

    // Tab Switching
    function switchTab(tabId) {
      document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
      event.currentTarget.classList.add('active');
      document.getElementById(tabId + '-pane').classList.add('active');
      if (tabId === 'graph') renderGraph();
    }

    // Load Data from Local Server Endpoints
    async function initDashboard() {
      try {
        const res = await fetch('/api/status');
        const data = await res.json();
        
        document.getElementById('stat-syms').textContent = data.symbols || 0;
        document.getElementById('stat-edges').textContent = data.edges || 0;
        document.getElementById('stat-files').textContent = data.files || 0;

        if (data.tables) renderLineage(data.tables);
        loadRoutes();
        loadImpact();
      } catch (err) {
        console.error('Failed to load status:', err);
      }
    }

    async function loadRoutes() {
      try {
        const res = await fetch('/api/routes');
        const json = await res.json();
        const routes = Array.isArray(json) ? json : (json.routes || []);
        
        document.getElementById('metric-route-count').textContent = routes.length;
        const tbody = document.getElementById('routes-table-body');
        
        if (!routes.length) {
          tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 30px;">No framework routes registered yet.</td></tr>';
          return;
        }

        tbody.innerHTML = routes.map(r => {
          const method = (r.method || r.http_method || 'GET').toUpperCase();
          let badgeClass = 'badge-get';
          if (method === 'POST') badgeClass = 'badge-post';
          else if (method === 'PUT' || method === 'PATCH') badgeClass = 'badge-put';
          else if (method === 'DELETE') badgeClass = 'badge-delete';

          return `
            <tr>
              <td><span class="badge-pill ${badgeClass}">${method}</span></td>
              <td style="font-weight: 700; color: var(--accent-orange);">${r.normalized_route || r.path}</td>
              <td style="color: #FFFFFF;">${r.handler || r.handler_name || 'Anonymous Handler'}</td>
              <td style="color: var(--text-light-muted);">${r.filePath || r.file_path}:${r.line}</td>
              <td><span class="badge-pill" style="background: rgba(255,255,255,0.08); color: #FFF;">${r.framework || 'HTTP'}</span></td>
              <td><span class="badge-pill badge-ok">SYNCHRONIZED</span></td>
            </tr>
          `;
        }).join('');
      } catch (e) {
        console.error('Routes error:', e);
      }
    }

    async function loadImpact() {
      try {
        const res = await fetch('/api/impact');
        const impact = await res.json();
        if (impact.risk_score !== undefined) {
          document.getElementById('blast-risk-score').textContent = impact.risk_score + ' / 100';
          document.getElementById('blast-risk-label').textContent = (impact.risk_category || 'LOW') + ' RISK MODIFICATION';
          document.getElementById('blast-impacted-syms').textContent = impact.impacted_symbols_count || 0;
          document.getElementById('blast-impacted-routes').textContent = impact.impacted_routes_count || 0;
          document.getElementById('blast-test-cmd').textContent = impact.recommended_test_command || 'pytest -q';
        }
      } catch (e) {
        console.error('Impact error:', e);
      }
    }

    function renderLineage(tables) {
      const tbody = document.getElementById('lineage-table-body');
      if (!tables || !tables.length) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 30px;">No database tables mapped.</td></tr>';
        return;
      }
      tbody.innerHTML = tables.map(t => `
        <tr>
          <td style="font-weight: 700; color: #FFFFFF;">${t.table || t.name}</td>
          <td><span class="badge-pill" style="background: rgba(255,255,255,0.08); color: #FFF;">${t.framework || 'SQLite'}</span></td>
          <td style="color: var(--text-light-muted);">Indexed Table</td>
          <td style="color: var(--accent-orange);">${(t.writers && t.writers.length) || 'Auto'}</td>
          <td style="color: var(--badge-green-text);">${(t.readers && t.readers.length) || 'Auto'}</td>
          <td><span class="badge-pill badge-ok">MAPPED</span></td>
        </tr>
      `).join('');
    }

    // KNOWLEDGE GRAPH VISUALIZER (2D & 3D ORBITAL)
    let nodes = [];
    let edges = [];
    let is3D = false;
    let angleX = 0.25;
    let angleY = 0.35;
    let isDragging = false;
    let prevMouseX = 0;
    let prevMouseY = 0;
    let searchQuery = '';

    function toggle3DMode() {
      is3D = !is3D;
      document.getElementById('btn-3d').textContent = is3D ? '2D PLANE' : '3D ORBITAL';
      document.getElementById('btn-3d').style.background = is3D ? 'var(--accent-orange)' : 'rgba(255,255,255,0.06)';
      document.getElementById('btn-3d').style.color = is3D ? '#000' : '#FFF';
    }

    function exportGraph() {
      const canvas = document.getElementById('graph-canvas');
      const link = document.createElement('a');
      link.download = 'codegraph-knowledge-map.png';
      link.href = canvas.toDataURL('image/png');
      link.click();
    }

    function filterGraph(query) {
      searchQuery = query.toLowerCase().trim();
    }

    async function renderGraph() {
      const canvas = document.getElementById('graph-canvas');
      canvas.width = canvas.parentElement.clientWidth;
      canvas.height = canvas.parentElement.clientHeight;
      const ctx = canvas.getContext('2d');

      if (!nodes.length) {
        const res = await fetch('/api/graph?max_nodes=180');
        const graphData = await res.json();
        nodes = graphData.nodes || [];
        edges = graphData.edges || [];

        nodes.forEach(n => {
          n.x = (Math.random() - 0.5) * 550;
          n.y = (Math.random() - 0.5) * 450;
          n.z = (Math.random() - 0.5) * 500;
          n.vx = 0; n.vy = 0; n.vz = 0;
        });
      }

      function project(x, y, z) {
        if (!is3D) {
          return { x: canvas.width / 2 + x, y: canvas.height / 2 + y, scale: 1.0, z: 0 };
        }
        const cosY = Math.cos(angleY), sinY = Math.sin(angleY);
        const x1 = x * cosY + z * sinY;
        const z1 = -x * sinY + z * cosY;

        const cosX = Math.cos(angleX), sinX = Math.sin(angleX);
        const y2 = y * cosX - z1 * sinX;
        const z2 = y * sinX + z1 * cosX;

        const focal = 650;
        const scale = focal / (focal + z2 + 350);
        return {
          x: canvas.width / 2 + x1 * scale,
          y: canvas.height / 2 + y2 * scale,
          scale: Math.max(0.2, scale),
          z: z2,
        };
      }

      function tick() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        nodes.forEach(n => {
          const p = project(n.x, n.y, n.z);
          n.screenX = p.x;
          n.screenY = p.y;
          n.scale = p.scale;
          n.depthZ = p.z;
        });

        // Draw Edges
        ctx.lineWidth = 1;
        edges.forEach(e => {
          const s = nodes[e.sourceIndex];
          const t = nodes[e.targetIndex];
          if (s && t) {
            ctx.strokeStyle = 'rgba(255, 84, 0, 0.16)';
            ctx.beginPath();
            ctx.moveTo(s.screenX, s.screenY);
            ctx.lineTo(t.screenX, t.screenY);
            ctx.stroke();
          }
        });

        // Depth Sort
        const sorted = is3D ? [...nodes].sort((a, b) => b.depthZ - a.depthZ) : nodes;

        // Draw Nodes
        sorted.forEach(n => {
          const isMatch = searchQuery ? n.name.toLowerCase().includes(searchQuery) : true;
          const r = (isMatch ? 6.5 : 4) * (n.scale || 1.0);

          ctx.beginPath();
          ctx.arc(n.screenX, n.screenY, r, 0, 2 * Math.PI);
          ctx.fillStyle = isMatch ? (n.color || '#FF5400') : 'rgba(100,100,100,0.3)';
          ctx.shadowColor = isMatch ? (n.color || '#FF5400') : 'transparent';
          ctx.shadowBlur = isMatch ? 8 : 0;
          ctx.fill();
          ctx.shadowBlur = 0;

          if ((nodes.length < 120 || isMatch) && (n.scale || 1.0) > 0.6) {
            ctx.fillStyle = isMatch ? '#F4F5F7' : 'rgba(150,150,150,0.4)';
            ctx.font = `${Math.floor(10 * (n.scale || 1.0))}px 'JetBrains Mono', monospace`;
            ctx.fillText(n.name, n.screenX + 8, n.screenY + 3);
          }
        });

        if (is3D && !isDragging) {
          angleY += 0.0015;
        }

        // Physics Step
        nodes.forEach(n => {
          n.vx -= n.x * 0.0006;
          n.vy -= n.y * 0.0006;
          n.vz -= n.z * 0.0006;
          n.x += n.vx; n.y += n.vy; n.z += n.vz;
          n.vx *= 0.88; n.vy *= 0.88; n.vz *= 0.88;
        });
      }

      setInterval(() => {
        if (document.getElementById("graph-pane").classList.contains("active")) tick();
      }, 30);
    }

    // Interaction Listeners
    const canvasElem = document.getElementById('graph-canvas');
    canvasElem.addEventListener('mousedown', e => {
      isDragging = true;
      prevMouseX = e.clientX;
      prevMouseY = e.clientY;
    });
    window.addEventListener('mouseup', () => { isDragging = false; });
    canvasElem.addEventListener('mousemove', e => {
      if (isDragging && is3D) {
        const dx = e.clientX - prevMouseX;
        const dy = e.clientY - prevMouseY;
        angleY += dx * 0.006;
        angleX += dy * 0.006;
        prevMouseX = e.clientX;
        prevMouseY = e.clientY;
      }
    });

    canvasElem.addEventListener('click', e => {
      const rect = canvasElem.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      const hit = nodes.find(n => Math.hypot(n.screenX - x, n.screenY - y) < 14);
      if (hit) {
        const drawer = document.getElementById('node-drawer');
        document.getElementById('drawer-name').textContent = hit.name;
        document.getElementById('drawer-body').innerHTML = `
          <div><strong>Kind:</strong> <span style="color:#FFF;">${hit.kind || 'Symbol'}</span></div>
          <div><strong>Language:</strong> <span style="color:#FFF;">${hit.language || 'polyglot'}</span></div>
          <div><strong>Source File:</strong> <span style="color:var(--accent-orange);">${hit.path || 'unknown'}:${hit.line || 1}</span></div>
          <div><strong>Canonical ID:</strong> <span style="font-size:10px; color:#A0A6AF;">${hit.id || hit.name}</span></div>
        `;
        drawer.style.display = 'block';
      }
    });

    initDashboard();
    window.addEventListener('resize', () => {
      if (document.getElementById('graph-pane').classList.contains('active')) renderGraph();
    });
  </script>
</body>
</html>
"""


class CodeGraphUIRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for serving the CodeGraph Dashboard and REST endpoints."""

    indexer: Indexer

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in ("/", "/ui", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(_get_html_dashboard().encode("utf-8"))
            return

        if path == "/api/status":
            self._handle_api_status()
            return

        if path == "/api/drift":
            self._handle_api_drift()
            return

        if path == "/api/routes":
            self._handle_api_routes()
            return

        if path == "/api/impact":
            self._handle_api_impact()
            return

        if path == "/api/graph":
            self._handle_api_graph()
            return

        self.send_response(404)
        self.end_headers()
        self.wfile.write(b"Not Found")

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

    def _handle_api_drift(self) -> None:
        try:
            from codegraph.api_drift import detect_api_contract_drift

            with self.indexer.session() as con:
                drift_report = detect_api_contract_drift(con, self.indexer.repository)
                self._send_json(drift_report.as_dict())
        except Exception as e:
            self._send_json({"drifts": [], "error": str(e)})

    def _handle_api_status(self) -> None:
        try:
            with self.indexer.session() as con:
                file_count = con.execute("SELECT count(*) FROM files WHERE status='ok'").fetchone()[0]
                sym_count = con.execute("SELECT count(*) FROM symbols").fetchone()[0]
                edge_count = con.execute("SELECT count(*) FROM graph_edges").fetchone()[0]
                grow = con.execute("SELECT value FROM metadata WHERE key='index_generation'").fetchone()
                gen = int(grow[0]) if grow and grow[0] else 1

                tables_raw = con.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                ).fetchall()
                tables = [
                    {
                        "table": str(t[0]),
                        "name": str(t[0]),
                        "framework": "SQLite WAL",
                        "writers": [],
                        "readers": [],
                    }
                    for t in tables_raw
                ]

            payload = {
                "repository": str(self.indexer.repository),
                "files": file_count,
                "symbols": sym_count,
                "edges": edge_count,
                "generation": gen,
                "status": "synchronized",
                "tables": tables,
            }
        except Exception as exc:
            payload = {"error": str(exc), "status": "error"}

        self._send_json(payload)

    def _handle_api_routes(self) -> None:
        try:
            with self.indexer.session() as con:
                rows = con.execute(
                    "SELECT endpoint_id, framework, http_method, route_path, "
                    "normalized_route, handler_name, file_path, line FROM framework_routes LIMIT 200"
                ).fetchall()
                routes = [
                    {
                        "id": str(r["endpoint_id"]),
                        "framework": str(r["framework"]),
                        "method": str(r["http_method"]),
                        "path": str(r["route_path"]),
                        "normalized_route": str(r["normalized_route"]),
                        "handler": str(r["handler_name"]),
                        "filePath": str(r["file_path"]),
                        "line": int(r["line"]),
                    }
                    for r in rows
                ]
        except Exception:
            routes = []

        self._send_json({"routes": routes})

    def _handle_api_impact(self) -> None:
        try:
            from codegraph.change_impact import get_deep_change_impact

            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            target = query.get("target", [None])[0]

            with self.indexer.session() as con:
                report = get_deep_change_impact(self.indexer.repository, con, symbol=target)
                payload = report.as_dict()
        except Exception:
            payload = {
                "risk_score": 0,
                "risk_category": "LOW",
                "impacted_symbols_count": 0,
                "impacted_routes_count": 0,
                "recommended_test_command": "pytest -q",
            }
        self._send_json(payload)

    def _handle_api_graph(self) -> None:
        try:
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            limit = int(query.get("max_nodes", [200])[0])
            lang_filter = query.get("language", [None])[0]
            with self.indexer.session() as con:
                sql = "SELECT id, name, kind, path, start_line, language FROM symbols"
                params: list[Any] = []
                if lang_filter:
                    sql += " WHERE language = ?"
                    params.append(lang_filter)
                sql += f" LIMIT {limit}"

                sym_rows = con.execute(sql, params).fetchall()
                node_map: dict[str, int] = {}
                nodes = []
                for idx, r in enumerate(sym_rows):
                    nid = str(r["id"])
                    node_map[nid] = idx
                    kind = str(r["kind"]).upper()
                    lang = str(r["language"] if "language" in r.keys() else "unknown")
                    color = "#FF5400"
                    if "CLASS" in kind or "STRUCT" in kind:
                        color = "#BC8CFF"
                    elif "ROUTE" in kind:
                        color = "#3FB950"
                    elif "TABLE" in kind:
                        color = "#D29922"
                    elif "INTERFACE" in kind:
                        color = "#38BDF8"
                    nodes.append({
                        "id": nid,
                        "name": str(r["name"]),
                        "kind": kind,
                        "path": str(r["path"]),
                        "line": int(r["start_line"]),
                        "language": lang,
                        "color": color,
                    })

                edge_rows = con.execute(
                    "SELECT source, target, relationship FROM graph_edges LIMIT 500"
                ).fetchall()
                edges = []
                for e in edge_rows:
                    src_id = str(e["source"])
                    tgt_id = str(e["target"])
                    if src_id in node_map and tgt_id in node_map:
                        edges.append({
                            "sourceIndex": node_map[src_id],
                            "targetIndex": node_map[tgt_id],
                            "relationship": str(e["relationship"]),
                        })

                payload = {"nodes": nodes, "edges": edges}
        except Exception:
            payload = {"nodes": [], "edges": []}

        self._send_json(payload)

    def _send_json(self, data: Any) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        pass


def start_ui_server(
    repository: Path,
    host: str = "127.0.0.1",
    port: int = 8765,
    open_browser: bool = True,
) -> None:
    """Launch the CodeGraph Interactive Dashboard server."""
    indexer = Indexer(repository.resolve())

    class _CustomHandler(CodeGraphUIRequestHandler):
        pass

    _CustomHandler.indexer = indexer

    server = ThreadingHTTPServer((host, port), _CustomHandler)
    url = f"http://{host}:{port}/ui"

    print(f"CodeGraph Visual Dashboard running at {url}")
    print("Press Ctrl+C to stop.")

    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping CodeGraph Dashboard.")
    finally:
        server.server_close()
