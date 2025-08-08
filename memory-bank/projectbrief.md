# Project Brief

## Purpose
Build a real-time, AI-powered trading assistant that monitors 193+ crypto positions, aggregates market and account data, analyzes risk and technicals, and produces clear, actionable recommendations.

## Core Objectives
- Fetch open positions (Bybit read-only) and market data from specialized providers
- Multi-layered analysis: Technical, Sentiment, (optionally) Fundamentals/News
- AI decision synthesis with structured outputs: Hold/Exit/Add/Watch + confidence
- Sub-5s end-to-end latency for portfolio-scale analysis
- Secure, production-ready architecture; no sensitive data in logs

## Out of Scope (initial)
- Executing trades (advice only)
- Non-Bybit exchanges (future)
- Persistent secret storage without encryption

## Success Criteria
- Healthy backend with <5s analysis on 193+ positions
- Clear decision outputs per position with reasoning
- Robust error handling and rate-limit resilience
- Secure handling of API keys (env-based in dev; encrypted in prod)

## High-Level Users
- Portfolio holders needing continuous risk and opportunity assessment
- Power users wanting configurable analysis cadence and notifications

## Deliverables
- FastAPI backend exposing analysis and data endpoints
- Frontend dashboard for portfolio and per-position insights
- Notification hooks (Telegram/Discord/Email) after core analysis is stable
