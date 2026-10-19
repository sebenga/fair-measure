"""Scoring tables stored as data, referenced from a preset's result_config by key.

Combined-events points follow the World Athletics (formerly IAAF) formulas:
track  points = floor(A * (B - T) ** C), T in seconds
field  points = floor(A * (M - B) ** C), M in centimetres for jumps, metres for throws
VERIFY the coefficients against the current World Athletics scoring tables.
"""

from __future__ import annotations

COMBINED_EVENT_TABLES: dict[str, list[dict]] = {
    "decathlon": [
        {"key": "100m", "label": "100 m", "kind": "track", "a": "25.4347", "b": "18", "c": "1.81"},
        {
            "key": "long_jump",
            "label": "Long jump",
            "kind": "field",
            "unit": "cm",
            "a": "0.14354",
            "b": "220",
            "c": "1.4",
        },
        {
            "key": "shot_put",
            "label": "Shot put",
            "kind": "field",
            "unit": "m",
            "a": "51.39",
            "b": "1.5",
            "c": "1.05",
        },
        {
            "key": "high_jump",
            "label": "High jump",
            "kind": "field",
            "unit": "cm",
            "a": "0.8465",
            "b": "75",
            "c": "1.42",
        },
        {"key": "400m", "label": "400 m", "kind": "track", "a": "1.53775", "b": "82", "c": "1.81"},
        {
            "key": "110m_hurdles",
            "label": "110 m hurdles",
            "kind": "track",
            "a": "5.74352",
            "b": "28.5",
            "c": "1.92",
        },
        {
            "key": "discus",
            "label": "Discus throw",
            "kind": "field",
            "unit": "m",
            "a": "12.91",
            "b": "4",
            "c": "1.1",
        },
        {
            "key": "pole_vault",
            "label": "Pole vault",
            "kind": "field",
            "unit": "cm",
            "a": "0.2797",
            "b": "100",
            "c": "1.35",
        },
        {
            "key": "javelin",
            "label": "Javelin throw",
            "kind": "field",
            "unit": "m",
            "a": "10.14",
            "b": "7",
            "c": "1.08",
        },
        {
            "key": "1500m",
            "label": "1500 m",
            "kind": "track",
            "a": "0.03768",
            "b": "480",
            "c": "1.85",
        },
    ],
    "heptathlon": [
        {
            "key": "100m_hurdles",
            "label": "100 m hurdles",
            "kind": "track",
            "a": "9.23076",
            "b": "26.7",
            "c": "1.835",
        },
        {
            "key": "high_jump",
            "label": "High jump",
            "kind": "field",
            "unit": "cm",
            "a": "1.84523",
            "b": "75",
            "c": "1.348",
        },
        {
            "key": "shot_put",
            "label": "Shot put",
            "kind": "field",
            "unit": "m",
            "a": "56.0211",
            "b": "1.5",
            "c": "1.05",
        },
        {
            "key": "200m",
            "label": "200 m",
            "kind": "track",
            "a": "4.99087",
            "b": "42.5",
            "c": "1.81",
        },
        {
            "key": "long_jump",
            "label": "Long jump",
            "kind": "field",
            "unit": "cm",
            "a": "0.188807",
            "b": "210",
            "c": "1.41",
        },
        {
            "key": "javelin",
            "label": "Javelin throw",
            "kind": "field",
            "unit": "m",
            "a": "15.9803",
            "b": "3.8",
            "c": "1.04",
        },
        {"key": "800m", "label": "800 m", "kind": "track", "a": "0.11193", "b": "254", "c": "1.88"},
    ],
}
