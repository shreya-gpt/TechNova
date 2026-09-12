"""
Weather & Environmental Data Module
------------------------------------
Backend module for the AI-powered Landslide Risk Intelligence and Early
Warning Platform (North Eastern Region of India).

Responsible for collecting, validating, transforming and serving
environmental data (rainfall, soil moisture, temperature, humidity,
forecasts, antecedent rainfall, anomalies, and quality metadata) to the
downstream AI / Risk Engine.

This module produces environmental EVIDENCE, not a final landslide
probability. Final risk scoring is performed by a separate Risk Engine
module that fuses this environmental vector with terrain, geology,
satellite and infrastructure data.
"""

__version__ = "0.1.0"
