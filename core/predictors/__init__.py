"""
OpenClaw Tiered Prediction Engine
=================================
Three-tier lice forecasting:
  1. Short-term (1-2 weeks): Stige-style GLM with infestation pressure
  2. Medium-term (2-6 weeks): Prophet + LSTM ensemble
  3. Long-term (seasonal): Traffic-light classifier + dispersal proxy
"""
