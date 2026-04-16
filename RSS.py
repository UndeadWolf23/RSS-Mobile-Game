"""
CraftIdle - A mobile-style crafting and resource management game.
Built with PySide6. Targets 19.5:9 aspect ratio (e.g. 3120x1440).
"""

import sys
import json
import os
import random
import time
import math
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QStackedWidget, QScrollArea,
    QSlider, QDialog, QGraphicsOpacityEffect, QSizePolicy,
    QFrame, QGridLayout, QSpinBox, QProgressBar, QGraphicsDropShadowEffect,
    QLineEdit, QMessageBox, QScroller, QScrollerProperties
)
from PySide6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve, QRect, QSize,
    QParallelAnimationGroup, QSequentialAnimationGroup,
    Signal, QObject, QPoint, QRectF, QThread, Property, QEvent
)
from PySide6.QtGui import (
    QPainter, QPixmap, QColor, QFont, QFontMetrics, QPen, QBrush,
    QLinearGradient, QRadialGradient, QPainterPath, QIcon,
    QTransform, QCursor, QMovie, QFontDatabase
)

# ---------------------------------------------------------------------------
# PATHS
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
SAVE_FILE   = BASE_DIR / "savegame.json"
CONFIG_FILE = BASE_DIR / "config.json"

# HTML snippet for embedding the coin image inside QLabel rich text
_coin_uri = (BASE_DIR / "coin.png").as_uri()
COIN_HTML = f'<img src="{_coin_uri}" width="32" height="32" style="vertical-align:middle">&nbsp;'
COIN_SMALL_HTML = f'<img src="{_coin_uri}" width="18" height="18" style="vertical-align:middle">'

# ---------------------------------------------------------------------------
# UI SCALE  — set in main() from screen detection + user preference
# ---------------------------------------------------------------------------
APP_SCALE: float = 1.0   # mutable module-level; updated before any widget is built
BASE_FONT_SCALE: float = 1.18  # global font size nudge — makes all text larger

def sz(n: int) -> int:
    """Scale a pixel value by APP_SCALE."""
    return max(1, int(n * APP_SCALE))

def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_config(cfg: dict):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass

# ---------------------------------------------------------------------------
# DESIGN TOKENS
# ---------------------------------------------------------------------------
PALETTE = {
    "bg_dark":      "#0D0F14",
    "bg_mid":       "#141720",
    "bg_light":     "#1C2030",
    "bg_card":      "#1E2235",
    "accent":       "#E8A44A",
    "accent2":      "#5EC4B6",
    "accent3":      "#C45E8A",
    "text_primary": "#EAE6DC",
    "text_muted":   "#7A7F96",
    "text_dim":     "#484D63",
    "gold":         "#F0C040",
    "xp_color":     "#72C4E8",
    "success":      "#6ECB8A",
    "danger":       "#E86A5E",
    "border":       "#2A2F48",
    "prestige":     "#C87FFF",
}

FONT_TITLE  = "Skranji"
FONT_BODY   = "Skranji"
FONT_MONO   = "Courier New"

# ---------------------------------------------------------------------------
# GAME CONSTANTS  (all tunable)
# ---------------------------------------------------------------------------
AUTOSAVE_INTERVAL_MS = 15_000

# Set to True by _do_reset_game() so closeEvent skips save after a reset
_RESET_PENDING: bool = False

RESOURCES = {
    # --- Tier 1 (base) ---
    "oakLog":          {"name": "Oak Logs",          "sprite": "oakLog.png",          "value": 2,    "xp_skill": "woodChopping"},
    "ironOre":         {"name": "Iron Ore",          "sprite": "ironOre.png",         "value": 5,    "xp_skill": "ironMining"},
    "stoneChunk":      {"name": "Stone Chunks",      "sprite": "stoneChunk.png",      "value": 3,    "xp_skill": "stoneMining"},
    "oakPlank":        {"name": "Oak Planks",        "sprite": "oakPlank.png",        "value": 6,    "xp_skill": "woodRefining"},
    "ironIngot":       {"name": "Iron Ingots",       "sprite": "ironIngot.png",       "value": 15,   "xp_skill": "ironRefining"},
    "stoneBrick":      {"name": "Stone Bricks",      "sprite": "stoneBrick.png",      "value": 8,    "xp_skill": "stoneRefining"},
    # --- Tier 2 (prestige 1-2) ---
    "pineLog":         {"name": "Pine Logs",         "sprite": "pineLog.png",         "value": 8,    "xp_skill": "woodChopping",  "prestige_req": 1},
    "pinePlank":       {"name": "Pine Planks",       "sprite": "pinePlank.png",       "value": 22,   "xp_skill": "woodRefining",  "prestige_req": 1},
    "amethystChunk":   {"name": "Amethyst Chunks",   "sprite": "amethystChunk.png",   "value": 12,   "xp_skill": "stoneMining",   "prestige_req": 2},
    "amethystCrystal": {"name": "Amethyst Crystals", "sprite": "amethystCrystal.png", "value": 35,   "xp_skill": "stoneRefining", "prestige_req": 2},
    "titaniteOre":     {"name": "Titanite Ore",      "sprite": "titaniteOre.png",     "value": 25,   "xp_skill": "ironMining",    "prestige_req": 2},
    "titaniteIngot":   {"name": "Titanite Ingots",   "sprite": "titaniteIngot.png",   "value": 70,   "xp_skill": "ironRefining",  "prestige_req": 2},
    # --- Tier 3 (prestige 3-7) ---
    "spruceLog":       {"name": "Spruce Logs",       "sprite": "spruceLog.png",       "value": 20,   "xp_skill": "woodChopping",  "prestige_req": 3},
    "sprucePlank":     {"name": "Spruce Planks",     "sprite": "sprucePlank.png",     "value": 55,   "xp_skill": "woodRefining",  "prestige_req": 3},
    "obsidianChunk":   {"name": "Obsidian Chunks",   "sprite": "obsidianChunk.png",   "value": 40,   "xp_skill": "stoneMining",   "prestige_req": 5},
    "obsidianCore":    {"name": "Obsidian Cores",    "sprite": "obsidianCore.png",    "value": 110,  "xp_skill": "stoneRefining", "prestige_req": 5},
    "frosteelOre":     {"name": "Frosteel Ore",      "sprite": "frosteelOre.png",     "value": 60,   "xp_skill": "ironMining",    "prestige_req": 7},
    "frosteelIngot":   {"name": "Frosteel Ingots",   "sprite": "frosteelIngot.png",   "value": 160,  "xp_skill": "ironRefining",  "prestige_req": 7},
}

RESOURCE_NODES = {
    # Row 0 — base tier (always accessible or skill-gated)
    "tree":            {"name": "Oak Tree",        "sprite": "oakTree.png",        "yields": "oakLog",       "base_chance": 0.60, "unlock_cost": 0, "xp_per_hit": 6,  "xp_skill": "woodChopping"},
    "rock":            {"name": "Rock Deposit",    "sprite": "stoneDeposit.png",  "yields": "stoneChunk",   "base_chance": 0.50, "unlock_cost": 0, "xp_per_hit": 6,  "xp_skill": "stoneMining"},
    "oreDeposit":      {"name": "Iron Deposit",    "sprite": "ironDeposit.png",   "yields": "ironOre",      "base_chance": 0.40, "unlock_cost": 0, "xp_per_hit": 9,  "xp_skill": "ironMining"},
    # Row 1 — prestige tier 1-2
    "pineTree":        {"name": "Pine Tree",        "sprite": "pineTree.png",       "yields": "pineLog",      "base_chance": 0.50, "unlock_cost": 0, "xp_per_hit": 10, "xp_skill": "woodChopping",  "prestige_req": 1},
    "amethystDeposit": {"name": "Amethyst Vein",   "sprite": "amethystDeposit.png","yields": "amethystChunk","base_chance": 0.45, "unlock_cost": 0, "xp_per_hit": 15, "xp_skill": "stoneMining",   "prestige_req": 2},
    "titaniteDeposit": {"name": "Titanite Deposit","sprite": "titaniteDeposit.png","yields": "titaniteOre",  "base_chance": 0.40, "unlock_cost": 0, "xp_per_hit": 18, "xp_skill": "ironMining",    "prestige_req": 2},
    # Row 2 — prestige tier 3-7
    "spruceTree":      {"name": "Spruce Tree",      "sprite": "spruceTree.png",     "yields": "spruceLog",    "base_chance": 0.50, "unlock_cost": 0, "xp_per_hit": 24, "xp_skill": "woodChopping",  "prestige_req": 3},
    "obsidianDeposit": {"name": "Obsidian Vein",   "sprite": "obsidianDeposit.png","yields": "obsidianChunk","base_chance": 0.40, "unlock_cost": 0, "xp_per_hit": 36, "xp_skill": "stoneMining",   "prestige_req": 5},
    "frosteelDeposit": {"name": "Frosteel Deposit","sprite": "frosteelDeposit.png","yields": "frosteelOre",  "base_chance": 0.35, "unlock_cost": 0, "xp_per_hit": 48, "xp_skill": "ironMining",    "prestige_req": 7},
}

# 3×3 navigation grid: row 0 = base, row 1 = prestige 1-2, row 2 = prestige 3-7.
# Swipe left/right = navigate columns. Swipe up/down = navigate rows.
RESOURCE_NODE_GRID = [
    ["tree",       "rock",            "oreDeposit"],       # row 0 — base
    ["pineTree",   "amethystDeposit", "titaniteDeposit"],  # row 1 — prestige 1-2
    ["spruceTree", "obsidianDeposit", "frosteelDeposit"],  # row 2 — prestige 3-7
]

REFINING_STATIONS = {
    # --- Tier 1 base stations ---
    "sawmill": {
        "name": "Sawmill",
        "sprite": "sawmill.png",
        "frames": 36, "frame_w": 640, "frame_h": 640,
        "frame_delay": 100,
        "recipe": {"input": "oakLog", "output": "oakPlank", "ratio": 2, "time_per_unit": 3.0},
        "recipes": [
            {"label": "Oak",    "input": "oakLog",    "output": "oakPlank",    "ratio": 2, "time_per_unit": 3.0, "prestige_req": 0, "xp_per_output": 12},
            {"label": "Pine",   "input": "pineLog",   "output": "pinePlank",   "ratio": 2, "time_per_unit": 3.5, "prestige_req": 1, "xp_per_output": 18},
            {"label": "Spruce", "input": "spruceLog", "output": "sprucePlank", "ratio": 2, "time_per_unit": 4.0, "prestige_req": 3, "xp_per_output": 28},
        ],
        "xp_skill": "woodRefining", "xp_per_output": 12,
        "tool_id": "sawmill_tool",
    },
    "masonBench": {
        "name": "Mason Bench",
        "sprite": "masonBench.png",
        "frames": 1, "frame_w": 256, "frame_h": 256,
        "frame_delay": 0,
        "recipe": {"input": "stoneChunk", "output": "stoneBrick", "ratio": 2, "time_per_unit": 4.0},
        "recipes": [
            {"label": "Stone",    "input": "stoneChunk",    "output": "stoneBrick",     "ratio": 2, "time_per_unit": 4.0, "prestige_req": 0, "xp_per_output": 12},
            {"label": "Amethyst", "input": "amethystChunk", "output": "amethystCrystal", "ratio": 2, "time_per_unit": 5.0, "prestige_req": 2, "xp_per_output": 22},
            {"label": "Obsidian", "input": "obsidianChunk", "output": "obsidianCore",    "ratio": 2, "time_per_unit": 6.0, "prestige_req": 5, "xp_per_output": 38},
        ],
        "xp_skill": "stoneRefining", "xp_per_output": 12,
        "tool_id": "mason_bench",
    },
    "forge": {
        "name": "Forge",
        "sprite": "forge.png",
        "frames": 16, "frame_w": 414, "frame_h": 508,
        "frame_delay": 100,
        "recipe": {"input": "ironOre", "output": "ironIngot", "ratio": 2, "time_per_unit": 5.0},
        "recipes": [
            {"label": "Iron",     "input": "ironOre",     "output": "ironIngot",     "ratio": 2, "time_per_unit": 5.0, "prestige_req": 0, "xp_per_output": 18},
            {"label": "Titanite", "input": "titaniteOre", "output": "titaniteIngot",  "ratio": 2, "time_per_unit": 6.5, "prestige_req": 2, "xp_per_output": 28},
            {"label": "Frosteel", "input": "frosteelOre", "output": "frosteelIngot",  "ratio": 2, "time_per_unit": 8.0, "prestige_req": 7, "xp_per_output": 48},
        ],
        "xp_skill": "ironRefining", "xp_per_output": 18,
        "tool_id": "forge_tool",
    },
}

SKILLS = {
    "woodChopping":  {"name": "Wood Chopping",  "color": "#6ECB8A", "icon": "🌲"},
    "stoneMining":   {"name": "Stone Mining",   "color": "#A8A8C8", "icon": "⛏"},
    "ironMining":    {"name": "Iron Mining",    "color": "#C0A878", "icon": "⚒"},
    "woodRefining":  {"name": "Wood Refining",  "color": "#E8D44A", "icon": "🪚"},
    "stoneRefining": {"name": "Stone Refining", "color": "#8898B8", "icon": "🔨"},
    "ironRefining":  {"name": "Iron Refining",  "color": "#E88A4A", "icon": "🔥"},
    "trading":       {"name": "Item Selling",   "color": "#72C4E8", "icon": "💰"},
}

# ---------------------------------------------------------------------------
# TOOL UPGRADES  (10 tiers each, affect refine speed / gather amount)
# Tool tier also determines if higher-level nodes can be accessed (future)
# ---------------------------------------------------------------------------
TOOL_UPGRADES = [
    {
        "id": "axe",      "name": "Axe",            "icon": "🪓",
        "sprite": "axeT{tier}.png",  # tiered: axeT1.png – axeT10.png
        "desc": "Better axes add +1 resource per tier on each successful chop.",
        "base_cost": 60,  "cost_mult": 2.2, "max_tier": 10,
        "gather_flat": 1,       # +1 resource per tier (flat)
        "node": "tree",
    },
    {
        "id": "pickaxe",  "name": "Pickaxe",         "icon": "⛏",
        "sprite": "pickaxeT{tier}.png",  # tiered: pickaxeT1.png – pickaxeT10.png
        "desc": "Better pickaxes add +1 resource per tier on each successful mine.",
        "base_cost": 80,  "cost_mult": 2.2, "max_tier": 10,
        "gather_flat": 1,       # +1 resource per tier (flat)
        "node": "rock",           # applies to rock and oreDeposit
    },
    {
        "id": "merchant_stall", "name": "Merchant Stall", "icon": "🏪",
        "sprite": "marketStall.png",  # static
        "desc": "Better stalls greatly increase sell price of all goods. +15% per tier.",
        "base_cost": 150, "cost_mult": 2.2, "max_tier": 10,
        "sell_delta": 0.15,       # +15% sell multiplier per tier
        "node": None,
    },
    {
        "id": "mason_bench", "name": "Masonry Bench", "icon": "🪨",
        "sprite": "masonBench.png",  # static
        "desc": "Better bench speeds up stone refining.",
        "base_cost": 200, "cost_mult": 2.2, "max_tier": 10,
        "refine_delta": 0.10,     # +10% refine speed per tier
        "station": "masonBench",
    },
    {
        "id": "sawmill_tool",  "name": "Sawmill",     "icon": "🪚",
        "sprite": "sawmill.png",  # animated sprite sheet
        "sprite_frames": 36, "sprite_fw": 640, "sprite_fh": 640, "sprite_delay": 100,
        "desc": "Better sawmill speeds up wood refining.",
        "base_cost": 200, "cost_mult": 2.2, "max_tier": 10,
        "refine_delta": 0.10,
        "station": "sawmill",
    },
    {
        "id": "forge_tool",    "name": "Forge",       "icon": "🔥",
        "sprite": "forge.png",  # animated sprite sheet
        "sprite_frames": 16, "sprite_fw": 414, "sprite_fh": 508, "sprite_delay": 100,
        "desc": "Better forge speeds up iron smelting.",
        "base_cost": 250, "cost_mult": 2.2, "max_tier": 10,
        "refine_delta": 0.10,
        "station": "forge",
    },
]

# ---------------------------------------------------------------------------
# SPECIAL ITEMS
# ---------------------------------------------------------------------------
SPECIAL_ITEMS = {
    # From mining (rock + oreDeposit)
    "runicShard":    {"name": "Runic Shard",    "sprite": "runicShard.png",    "value": 0,   "sellable": False, "desc": "Combine for permanent upgrades"},
    "geode":         {"name": "Geode",           "sprite": "geodeStatic.png",   "value": 0,   "sellable": False, "desc": "Open to discover gems inside"},
    # Gems from geode (sellable)
    "sapphire":      {"name": "Sapphire",        "sprite": "sapphire.png",      "value": 50,  "sellable": True,  "desc": "A gleaming blue gemstone"},
    "ruby":          {"name": "Ruby",            "sprite": "ruby.png",          "value": 120, "sellable": True,  "desc": "A deep red gemstone"},
    "emerald":       {"name": "Emerald",         "sprite": "emerald.png",       "value": 200, "sellable": True,  "desc": "A vivid green gemstone"},
    "diamond":       {"name": "Diamond",         "sprite": "diamond.png",       "value": 500, "sellable": True,  "desc": "The rarest gemstone"},
    # From wood chopping
    "harvestSpirit": {"name": "Harvest Spirit",  "sprite": "harvestSpirit.png", "value": 0,   "sellable": False, "desc": "Consume to boost harvesting for 30s"},
    "fairyDust":     {"name": "Fairy Dust",      "sprite": "fairyDust.png",     "value": 90,  "sellable": True,  "desc": "Shimmering magical dust"},
    # runicShard appears in both mining and chopping drops
}

# Rarity table for geode contents — cumulative weights
GEODE_LOOT = [
    ("sapphire", 50),
    ("ruby",     30),
    ("emerald",  15),
    ("diamond",   5),
]

# Runic Forge permanent upgrades (not reset by prestige)
RUNIC_UPGRADES = [
    {
        "id": "rune_gather",  "name": "Rune of Abundance",
        "desc": "Permanently gather +1 extra resource per successful click.",
        "cost_shards": 10, "max_tier": 5,
    },
    {
        "id": "rune_crit",    "name": "Rune of Fortune",
        "desc": "Permanently +5% critical chance on gather.",
        "cost_shards": 15, "max_tier": 5,
    },
    {
        "id": "rune_xp",      "name": "Rune of Wisdom",
        "desc": "Permanently +10% XP from all actions.",
        "cost_shards": 20, "max_tier": 3,
    },
    {
        "id": "rune_sell",    "name": "Rune of Commerce",
        "desc": "Permanently +10% sell price on all goods.",
        "cost_shards": 25, "max_tier": 3,
    },
]

# ---------------------------------------------------------------------------
# SKILL THRESHOLDS  — every 5 levels, bonuses to gather odds, crit, specials
# ---------------------------------------------------------------------------
# Base special-item chance (very low; scales via skill level)
BASE_SPECIAL_CHANCE = 0.02    # 2% base chance per strike
SPECIAL_CHANCE_PER_LEVEL = 0.0011  # +0.11% per skill level (max +11% at lv 100 = 13% total)

# Crit multiplier on resource amount
CRIT_MULTIPLIER = 2
BASE_CRIT_CHANCE = 0.02         # 2% base crit
CRIT_CHANCE_PER_LEVEL = 0.001   # +0.1% per skill level  (100 * 0.001 = 10% max)

SKILL_THRESHOLDS = {
    "woodChopping": [
        {"level":  5, "desc": "+1.5% gather chance  •  +0.5% crit  •  +0.3% special item"},
        {"level": 10, "desc": "+3% gather chance  •  +1% crit  •  Unlocks Iron Deposit access"},
        {"level": 15, "desc": "+4.5% gather chance  •  +1.5% crit  •  +0.9% special item"},
        {"level": 20, "desc": "+6% gather chance  •  +2% crit  •  +1.2% special item"},
        {"level": 25, "desc": "+7.5% gather chance  •  +2.5% crit  •  +1.5% special item"},
        {"level": 30, "desc": "+9% gather  •  +3% crit  •  +1.8% special"},
        {"level": 40, "desc": "+12% gather  •  +4% crit  •  +2.4% special"},
        {"level": 50, "desc": "+15% gather  •  +5% crit  •  +3% special"},
        {"level": 75, "desc": "+22.5% gather  •  +7.5% crit  •  +4.5% special"},
        {"level": 100,"desc": "MAX — +30% gather  •  +10% crit  •  +6% special"},
    ],
    "stoneMining": [
        {"level":  5, "desc": "+1.5% gather chance  •  +0.5% crit  •  +0.3% special item"},
        {"level": 10, "desc": "+3% gather chance  •  +1% crit  •  +0.6% special item"},
        {"level": 15, "desc": "+4.5% gather chance  •  +1.5% crit  •  +0.9% special"},
        {"level": 20, "desc": "+6% gather  •  +2% crit  •  +1.2% special"},
        {"level": 25, "desc": "+7.5% gather  •  +2.5% crit  •  +1.5% special"},
        {"level": 50, "desc": "+15% gather  •  +5% crit  •  +3% special"},
        {"level": 75, "desc": "+22.5% gather  •  +7.5% crit  •  +4.5% special"},
        {"level": 100,"desc": "MAX — +30% gather  •  +10% crit  •  +6% special"},
    ],
    "ironMining": [
        {"level":  5, "desc": "+1.5% gather chance  •  +0.5% crit  •  +0.3% special item"},
        {"level": 10, "desc": "+3% gather  •  +1% crit  •  +0.6% special"},
        {"level": 15, "desc": "+4.5% gather  •  +1.5% crit  •  +0.9% special"},
        {"level": 20, "desc": "+6% gather  •  +2% crit  •  +1.2% special"},
        {"level": 25, "desc": "+7.5% gather  •  +2.5% crit  •  +1.5% special"},
        {"level": 50, "desc": "+15% gather  •  +5% crit  •  +3% special"},
        {"level": 100,"desc": "MAX — +30% gather  •  +10% crit  •  +6% special"},
    ],
    "woodRefining": [
        {"level":  5, "desc": "+2% refine speed (passive)"},
        {"level": 10, "desc": "+4% refine speed (passive)"},
        {"level": 20, "desc": "+8% refine speed (passive)"},
        {"level": 50, "desc": "+20% refine speed (passive)"},
        {"level": 100,"desc": "MAX — +40% refine speed (passive)"},
    ],
    "stoneRefining": [
        {"level":  5, "desc": "+2% refine speed (passive)"},
        {"level": 10, "desc": "+4% refine speed (passive)"},
        {"level": 20, "desc": "+8% refine speed (passive)"},
        {"level": 50, "desc": "+20% refine speed (passive)"},
        {"level": 100,"desc": "MAX — +40% refine speed (passive)"},
    ],
    "ironRefining": [
        {"level":  5, "desc": "+2% refine speed (passive)"},
        {"level": 10, "desc": "+4% refine speed (passive)"},
        {"level": 20, "desc": "+8% refine speed (passive)"},
        {"level": 50, "desc": "+20% refine speed (passive)"},
        {"level": 100,"desc": "MAX — +40% refine speed (passive)"},
    ],
    "trading": [
        {"level":  5, "desc": "+4% sell price (passive)"},
        {"level": 10, "desc": "+8% sell price (passive)"},
        {"level": 20, "desc": "+16% sell price (passive)"},
        {"level": 50, "desc": "+40% sell price (passive)"},
        {"level": 100,"desc": "MAX — +80% sell price (passive)"},
    ],
}

# Harvest Spirit buff duration in seconds
HARVEST_SPIRIT_DURATION = 30
HARVEST_SPIRIT_GATHER_BONUS = 1.5   # 1.5x gather amount
HARVEST_SPIRIT_CHANCE_BONUS = 0.25  # +25% success chance additive

XP_TABLE = [0] + [int(100 * (lvl ** 1.6)) for lvl in range(1, 101)]

PRESTIGE_BASE_COST = 5000
PRESTIGE_COST_MULTIPLIER = 1.8

PRESTIGE_BONUS_DEFS = [
    {
        "id": "resource_gain",
        "label": "⛏ Resource Gain",
        "desc": "+12% gather chance and +10% resource amount per stack.",
    },
    {
        "id": "gold_gain",
        "label": "Gold Gain",
        "desc": "+18% gold from selling per stack.",
    },
    {
        "id": "xp_gain",
        "label": "⬆ XP Gain",
        "desc": "+15% XP from all actions per stack.",
    },
    {
        "id": "refine_speed",
        "label": "🔥 Refining Mastery",
        "desc": "+15% refining speed per stack.",
    },
    {
        "id": "special_find",
        "label": "✨ Fortune",
        "desc": "+1.2% special-item chance per stack.",
    },
    {
        "id": "crit_boost",
        "label": "⚡ Critical Fortune",
        "desc": "+2% critical chance and +10% crit yield per stack.",
    },
]


def default_prestige_bonuses() -> dict:
    return {bonus["id"]: 0 for bonus in PRESTIGE_BONUS_DEFS}

STRIKE_FRAMES = 9
STRIKE_W, STRIKE_H = 64, 47
STRIKE_DELAY = 20

# ---------------------------------------------------------------------------
# XP UTILITIES
# ---------------------------------------------------------------------------
def xp_for_level(level: int) -> int:
    if level <= 0: return 0
    return XP_TABLE[min(level, len(XP_TABLE)-1)]

def level_from_xp(xp: int) -> int:
    for lvl in range(99, 0, -1):  # XP_TABLE[99] is the threshold to reach level 100 (max)
        if xp >= XP_TABLE[lvl]:
            return lvl + 1
    return 1

# ---------------------------------------------------------------------------
# GAME STATE
# ---------------------------------------------------------------------------
@dataclass
class SkillState:
    xp: int = 0

    @property
    def level(self) -> int:
        return level_from_xp(self.xp)

    @property
    def xp_to_next(self) -> int:
        lvl = self.level
        if lvl >= len(XP_TABLE)-1:
            return 0
        return XP_TABLE[lvl] - self.xp

    @property
    def xp_in_level(self) -> int:
        lvl = self.level
        if self.xp < XP_TABLE[lvl]:
            # Pre-threshold (fallback level): show progress toward this level's threshold
            prev = XP_TABLE[lvl - 1] if lvl > 0 else 0
            return self.xp - prev
        # Normal: progress within this level toward the next
        return self.xp - XP_TABLE[lvl]

    @property
    def xp_needed_for_level(self) -> int:
        lvl = self.level
        if lvl >= len(XP_TABLE) - 1:
            return 1
        if self.xp < XP_TABLE[lvl]:
            # Pre-threshold: XP needed to actually reach this level
            prev = XP_TABLE[lvl - 1] if lvl > 0 else 0
            return XP_TABLE[lvl] - prev
        # Normal: XP range from current level threshold to next level threshold
        return XP_TABLE[lvl + 1] - XP_TABLE[lvl]


@dataclass
class GameState:
    gold: float = 0.0
    inventory: dict = field(default_factory=lambda: {k: 0 for k in RESOURCES})
    # Special items (not resources, tracked separately)
    special_items: dict = field(default_factory=lambda: {k: 0 for k in SPECIAL_ITEMS})
    skills: dict = field(default_factory=lambda: {k: SkillState() for k in SKILLS})
    unlocked_nodes: list = field(default_factory=lambda: ["tree", "rock"])
    # Tool tiers (reset by prestige)
    tool_tiers: dict = field(default_factory=dict)   # tool_id -> tier count (0-10)
    # Runic forge tiers (PERMANENT — not reset by prestige)
    runic_tiers: dict = field(default_factory=dict)  # runic_id -> tier count
    prestige_tier: int = 0
    prestige_coins: int = 0
    prestige_bonuses: dict = field(default_factory=default_prestige_bonuses)

    # Harvest Spirit active state (runtime only, not saved)
    _spirit_active: bool = field(default=False, init=False, repr=False, compare=False)
    _spirit_end_time: float = field(default=0.0, init=False, repr=False, compare=False)

    def to_dict(self) -> dict:
        return {
            "gold": self.gold,
            "inventory": self.inventory,
            "special_items": self.special_items,
            "skills": {k: v.xp for k, v in self.skills.items()},
            "unlocked_nodes": self.unlocked_nodes,
            "tool_tiers": self.tool_tiers,
            "runic_tiers": self.runic_tiers,
            "prestige_tier": self.prestige_tier,
            "prestige_coins": self.prestige_coins,
            "prestige_bonuses": self.prestige_bonuses,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "GameState":
        gs = cls()
        gs.gold = d.get("gold", 0.0)
        raw_inv = d.get("inventory", {})
        gs.inventory = {k: raw_inv.get(k, 0) for k in RESOURCES}
        raw_special = d.get("special_items", {})
        gs.special_items = {k: raw_special.get(k, 0) for k in SPECIAL_ITEMS}
        raw_skills = d.get("skills", {})
        for k in SKILLS:
            gs.skills[k] = SkillState(xp=raw_skills.get(k, 0))
        gs.unlocked_nodes = d.get("unlocked_nodes", ["tree", "rock"])
        gs.tool_tiers = d.get("tool_tiers", {})
        gs.runic_tiers = d.get("runic_tiers", {})
        gs.prestige_tier = d.get("prestige_tier", 0)
        gs.prestige_coins = d.get("prestige_coins", 0)
        loaded_bonuses = d.get("prestige_bonuses", {})
        gs.prestige_bonuses = default_prestige_bonuses()
        for key, value in loaded_bonuses.items():
            if key in gs.prestige_bonuses:
                gs.prestige_bonuses[key] = value
        return gs

    def save(self):
        try:
            with open(SAVE_FILE, "w") as f:
                json.dump(self.to_dict(), f, indent=2)
        except Exception as e:
            print(f"Save error: {e}")

    @classmethod
    def load(cls) -> "GameState":
        if SAVE_FILE.exists():
            try:
                with open(SAVE_FILE) as f:
                    return cls.from_dict(json.load(f))
            except Exception as e:
                print(f"Load error: {e}")
        return cls()

    # ------------------------------------------------------------------
    # Skill level helpers
    # ------------------------------------------------------------------
    def _skill_level(self, skill_id: str) -> int:
        return self.skills.get(skill_id, SkillState()).level

    # ------------------------------------------------------------------
    # Harvest Spirit buff
    # ------------------------------------------------------------------
    def activate_spirit(self):
        """Consume one Harvest Spirit and activate the buff."""
        if self.special_items.get("harvestSpirit", 0) <= 0:
            return False
        self.special_items["harvestSpirit"] -= 1
        self._spirit_active = True
        self._spirit_end_time = time.time() + HARVEST_SPIRIT_DURATION
        return True

    def spirit_remaining(self) -> float:
        """Seconds remaining on Harvest Spirit buff, 0 if inactive."""
        if not self._spirit_active:
            return 0.0
        remaining = self._spirit_end_time - time.time()
        if remaining <= 0:
            self._spirit_active = False
            return 0.0
        return remaining

    # ------------------------------------------------------------------
    # Effective stats — gather
    # ------------------------------------------------------------------
    def get_effective_chance(self, node_id: str) -> float:
        node_def = RESOURCE_NODES.get(node_id, {})
        skill_id = node_def.get("xp_skill", "")
        base = node_def.get("base_chance", 0.5)
        prestige_bonus = self.prestige_bonuses.get("resource_gain", 0) * 0.12
        skill_bonus = self._skill_level(skill_id) * 0.003 if skill_id else 0.0
        spirit_bonus = HARVEST_SPIRIT_CHANCE_BONUS if self.spirit_remaining() > 0 else 0.0
        return min(base + prestige_bonus + skill_bonus + spirit_bonus, 0.97)

    def get_effective_gather_amount(self, node_id: str) -> int:
        """Base amount is 1; tool tiers add a flat +1 per tier; runic runes and prestige increase it."""
        _wood_skill = RESOURCE_NODES.get(node_id, {}).get("xp_skill", "")
        tool_id = "axe" if "woodChopping" in _wood_skill else "pickaxe"
        tool_tier = self.tool_tiers.get(tool_id, 0)
        runic_gather_tier = self.runic_tiers.get("rune_gather", 0)
        base = 1 + tool_tier + runic_gather_tier + self.prestige_bonuses.get("resource_gain", 0) * 0.10
        spirit_mult = HARVEST_SPIRIT_GATHER_BONUS if self.spirit_remaining() > 0 else 1.0
        return max(1, int(base * spirit_mult))

    def get_crit_chance(self, node_id: str) -> float:
        skill_id = RESOURCE_NODES.get(node_id, {}).get("xp_skill", "")
        level = self._skill_level(skill_id) if skill_id else 1
        runic_crit_tier = self.runic_tiers.get("rune_crit", 0)
        base_crit = BASE_CRIT_CHANCE + runic_crit_tier * 0.05 + self.prestige_bonuses.get("crit_boost", 0) * 0.02
        return min(base_crit + level * CRIT_CHANCE_PER_LEVEL, 0.75)

    def get_crit_multiplier(self) -> float:
        return CRIT_MULTIPLIER + self.prestige_bonuses.get("crit_boost", 0) * 0.10

    def get_special_item_chance(self, node_id: str) -> float:
        skill_id = RESOURCE_NODES.get(node_id, {}).get("xp_skill", "")
        level = self._skill_level(skill_id) if skill_id else 1
        prestige_bonus = self.prestige_bonuses.get("special_find", 0) * 0.012
        return min(BASE_SPECIAL_CHANCE + level * SPECIAL_CHANCE_PER_LEVEL + prestige_bonus, 0.45)

    def roll_special_item(self, node_id: str) -> Optional[str]:
        """Return a special item id if the player hits the special drop, else None."""
        chance = self.get_special_item_chance(node_id)
        if random.random() >= chance:
            return None
        skill_id = RESOURCE_NODES.get(node_id, {}).get("xp_skill", "")
        is_mining = "Mining" in skill_id
        if is_mining:
            # Amethyst gets 2× geode chance (0.71 vs 0.55)
            if node_id == "amethystDeposit":
                return "geode" if random.random() < 0.71 else "runicShard"
            # Mining: Geode more common than Runic Shard (55/45)
            return "geode" if random.random() < 0.55 else "runicShard"
        else:
            # Chopping: Harvest Spirit / Fairy Dust / Runic Shard (35/30/35)
            r = random.random()
            if r < 0.35:
                return "harvestSpirit"
            elif r < 0.65:
                return "fairyDust"
            else:
                return "runicShard"

    def open_geode(self) -> Optional[str]:
        """Remove one geode, return the gem item id."""
        if self.special_items.get("geode", 0) <= 0:
            return None
        self.special_items["geode"] -= 1
        total = sum(w for _, w in GEODE_LOOT)
        roll = random.uniform(0, total)
        cumul = 0
        for item_id, weight in GEODE_LOOT:
            cumul += weight
            if roll < cumul:
                self.special_items[item_id] = self.special_items.get(item_id, 0) + 1
                return item_id
        return "sapphire"

    # ------------------------------------------------------------------
    # Effective stats — sell
    # ------------------------------------------------------------------
    def get_effective_sell_price(self, resource_id: str) -> float:
        if resource_id in RESOURCES:
            base = RESOURCES[resource_id]["value"]
        else:
            base = SPECIAL_ITEMS.get(resource_id, {}).get("value", 0)
        prestige_bonus = 1 + self.prestige_bonuses.get("gold_gain", 0) * 0.18
        trading_bonus = 1 + self._skill_level("trading") * 0.008
        # Merchant stall tool bonus
        stall_tier = self.tool_tiers.get("merchant_stall", 0)
        stall_tool = next((t for t in TOOL_UPGRADES if t["id"] == "merchant_stall"), {})
        stall_bonus = 1 + stall_tool.get("sell_delta", 0) * stall_tier
        # Runic commerce
        rune_sell_tier = self.runic_tiers.get("rune_sell", 0)
        rune_bonus = 1 + rune_sell_tier * 0.10
        return base * prestige_bonus * trading_bonus * stall_bonus * rune_bonus

    # ------------------------------------------------------------------
    # Effective stats — refine speed
    # ------------------------------------------------------------------
    def get_effective_refine_speed(self, station_id: str) -> float:
        station_def = REFINING_STATIONS.get(station_id, {})
        skill_id = station_def.get("xp_skill", "")
        skill_bonus = self._skill_level(skill_id) * 0.004 if skill_id else 0.0
        tool_id = station_def.get("tool_id", "")
        tool_tier = self.tool_tiers.get(tool_id, 0)
        tool_def = next((t for t in TOOL_UPGRADES if t["id"] == tool_id), {})
        tool_bonus = tool_def.get("refine_delta", 0) * tool_tier
        prestige_bonus = self.prestige_bonuses.get("refine_speed", 0) * 0.15
        return 1.0 * (1 + skill_bonus + tool_bonus + prestige_bonus)

    # ------------------------------------------------------------------
    # XP
    # ------------------------------------------------------------------
    def get_effective_xp(self, base_xp: float) -> float:
        prestige_bonus = 1 + self.prestige_bonuses.get("xp_gain", 0) * 0.15
        rune_xp_tier = self.runic_tiers.get("rune_xp", 0)
        rune_bonus = 1 + rune_xp_tier * 0.10
        return base_xp * prestige_bonus * rune_bonus

    def add_xp(self, skill: str, amount: float) -> tuple:
        """Returns (effective_xp_added: int, did_level_up: bool)."""
        if skill not in self.skills:
            return 0, False
        old_level = self.skills[skill].level
        effective = int(self.get_effective_xp(amount))
        self.skills[skill].xp += effective
        return effective, self.skills[skill].level > old_level

    # ------------------------------------------------------------------
    # Prestige
    # ------------------------------------------------------------------
    def prestige_cost(self) -> int:
        return int(PRESTIGE_BASE_COST * (PRESTIGE_COST_MULTIPLIER ** self.prestige_tier))

    def prestige_cost_for_tier(self, tier: int) -> int:
        return int(PRESTIGE_BASE_COST * (PRESTIGE_COST_MULTIPLIER ** tier))

    def can_prestige(self) -> bool:
        return self.gold >= self.prestige_cost()

    def max_consecutive_prestiges(self) -> int:
        total_gold = int(self.gold)
        tier = self.prestige_tier
        count = 0
        while total_gold >= self.prestige_cost_for_tier(tier):
            total_gold -= self.prestige_cost_for_tier(tier)
            tier += 1
            count += 1
        return count

    def total_prestige_cost(self, count: int) -> int:
        if count <= 0:
            return 0
        return sum(self.prestige_cost_for_tier(self.prestige_tier + offset) for offset in range(count))

    def coins_for_prestige_count(self, count: int) -> int:
        """Return how many prestige coins are earned for a given prestige count.
        Scales linearly: the Nth prestige earns N coins (1st=1, 2nd=2, 3rd=3 …)."""
        return sum(max(1, self.prestige_tier + offset + 1) for offset in range(count))

    def do_prestige(self, count: int = 1):
        if count <= 0:
            return False
        total_cost = self.total_prestige_cost(count)
        if self.gold < total_cost:
            return False
        self.gold = 0
        for k in self.skills:
            self.skills[k] = SkillState()
        self.inventory = {k: 0 for k in RESOURCES}
        self.special_items = {k: 0 for k in SPECIAL_ITEMS}
        self.tool_tiers.clear()
        # runic_tiers intentionally NOT cleared — permanent
        earned_coins = self.coins_for_prestige_count(count)
        self.prestige_tier += count
        self.prestige_coins += earned_coins
        return True

    def spend_prestige_coin(self, bonus_type: str) -> bool:
        if self.prestige_coins <= 0:
            return False
        if bonus_type not in self.prestige_bonuses:
            return False
        self.prestige_coins -= 1
        self.prestige_bonuses[bonus_type] += 1
        return True

    def spend_prestige_coins(self, bonus_type: str, count: int) -> int:
        """Spend up to `count` prestige coins on bonus_type. Returns amount spent."""
        if count <= 0 or bonus_type not in self.prestige_bonuses:
            return 0
        actually = min(count, self.prestige_coins)
        if actually <= 0:
            return 0
        self.prestige_coins -= actually
        self.prestige_bonuses[bonus_type] += actually
        return actually

    # ------------------------------------------------------------------
    # Tool upgrade helpers
    # ------------------------------------------------------------------
    def get_tool_tier(self, tool_id: str) -> int:
        return self.tool_tiers.get(tool_id, 0)

    def get_tool_cost(self, tool_id: str) -> int:
        tool = next((t for t in TOOL_UPGRADES if t["id"] == tool_id), None)
        if not tool:
            return 0
        tier = self.tool_tiers.get(tool_id, 0)
        return int(tool["base_cost"] * (tool["cost_mult"] ** tier))

    def apply_tool_upgrade(self, tool_id: str) -> bool:
        tool = next((t for t in TOOL_UPGRADES if t["id"] == tool_id), None)
        if not tool:
            return False
        current = self.tool_tiers.get(tool_id, 0)
        if current >= tool["max_tier"]:
            return False
        cost = self.get_tool_cost(tool_id)
        if self.gold < cost:
            return False
        self.gold -= cost
        self.tool_tiers[tool_id] = current + 1
        return True

    # ------------------------------------------------------------------
    # Runic forge helpers (permanent upgrades using Runic Shards)
    # ------------------------------------------------------------------
    def get_runic_tier(self, runic_id: str) -> int:
        return self.runic_tiers.get(runic_id, 0)

    def get_runic_cost(self, runic_id: str) -> int:
        rup = next((r for r in RUNIC_UPGRADES if r["id"] == runic_id), None)
        if not rup:
            return 0
        tier = self.runic_tiers.get(runic_id, 0)
        # each tier costs cost_shards more
        return rup["cost_shards"] + tier * rup["cost_shards"]

    def apply_runic_upgrade(self, runic_id: str) -> bool:
        rup = next((r for r in RUNIC_UPGRADES if r["id"] == runic_id), None)
        if not rup:
            return False
        current = self.runic_tiers.get(runic_id, 0)
        if current >= rup["max_tier"]:
            return False
        cost = self.get_runic_cost(runic_id)
        if self.special_items.get("runicShard", 0) < cost:
            return False
        self.special_items["runicShard"] -= cost
        self.runic_tiers[runic_id] = current + 1
        return True


# ---------------------------------------------------------------------------
# AUDIO
# ---------------------------------------------------------------------------
class AudioManager:
    """
    Manages SFX playback for node interactions.

    Uses QMediaPlayer (supports MP3) with a pooled architecture so spam
    clicks are handled without audio stutter.  Each sound category
    ("chop", "mine") has 4 variant files.  We pre-allocate a pool of
    QMediaPlayer+QAudioOutput pairs per variant; on play() a random
    variant is chosen and an idle player from that variant's pool is
    used.  A per-category concurrent cap prevents audio soup on extreme
    spam.  Must be instantiated AFTER QApplication exists.
    """

    # QMediaPlayer instances per variant file (allows that many overlapping
    # plays of the exact same clip without interrupting each other).
    _POOL_SIZE = 3
    # Hard cap: if this many players across a category are already playing,
    # skip the new play entirely — the user's ears are saturated.
    _MAX_CONCURRENT = 4
    # Do not trigger the same category faster than this. This avoids hammering
    # the media backend when clicks arrive far faster than humans can perceive.
    _MIN_INTERVAL_S = 0.045
    # Bounded backlog per category. If the player clicks faster than this can
    # drain, extra requests are dropped so audio catches up almost immediately
    # after input stops instead of continuing for seconds.
    _MAX_PENDING_PER_CATEGORY = 2

    # Maps category -> variant filenames
    _CATEGORY_FILES: dict[str, list[str]] = {
        "chop": [f"chop{i}.mp3"   for i in range(1, 5)],
        "mine": [f"mining{i}.mp3" for i in range(1, 5)],
    }

    def __init__(self):
        self._sfx_volume: float = 0.35
        self._music_volume: float = 0.5
        self._available: bool = False
        # pools[category][variant_index] = [(QMediaPlayer, QAudioOutput), ...]
        self._pools: dict[str, list[list]] = {}
        self._last_play_at: dict[str, float] = {}
        self._pending_requests: dict[str, int] = {}
        self._drain_timer = QTimer()
        self._drain_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._drain_timer.setSingleShot(False)
        self._drain_timer.setInterval(15)
        self._drain_timer.timeout.connect(self._drain_requests)
        # Background music
        self._bgm_player = None
        self._bgm_output = None
        self._bgm_fade_anim = None
        try:
            from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput  # noqa: F401
            self._available = True
            self._load_pools()
            self._load_bgm()
        except Exception as exc:
            print(f"[Audio] QtMultimedia unavailable: {exc}")

    def _load_pools(self) -> None:
        from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
        from PySide6.QtCore import QUrl

        for category, files in self._CATEGORY_FILES.items():
            variant_pools: list[list] = []
            for filename in files:
                path = BASE_DIR / filename
                pool: list = []
                if path.exists():
                    url = QUrl.fromLocalFile(str(path))
                    for _ in range(self._POOL_SIZE):
                        try:
                            player = QMediaPlayer()
                            audio_out = QAudioOutput()
                            audio_out.setVolume(self._sfx_volume)
                            player.setAudioOutput(audio_out)
                            player.setSource(url)
                            pool.append((player, audio_out))
                        except Exception as e:
                            print(f"[Audio] load error {filename}: {e}")
                else:
                    print(f"[Audio] file not found: {path}")
                variant_pools.append(pool)
            self._pools[category] = variant_pools

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def play(self, category: str) -> None:
        """Queue a bounded SFX request for *category* ("chop" or "mine")."""
        if not self._available:
            return
        if category not in self._pools:
            return
        pending = self._pending_requests.get(category, 0)
        if pending >= self._MAX_PENDING_PER_CATEGORY:
            return
        self._pending_requests[category] = pending + 1
        if not self._drain_timer.isActive():
            self._drain_timer.start()

    def _drain_requests(self) -> None:
        if not any(self._pending_requests.values()):
            self._drain_timer.stop()
            return

        # Try to service one queued request per tick in a stable category order.
        for category in self._CATEGORY_FILES:
            if self._pending_requests.get(category, 0) <= 0:
                continue
            if self._try_play_now(category):
                self._pending_requests[category] -= 1
                break

        if not any(self._pending_requests.values()):
            self._drain_timer.stop()

    def _try_play_now(self, category: str) -> bool:
        """Attempt one immediate play. Returns True only if a sound started."""
        variant_pools = self._pools.get(category)
        if not variant_pools:
            return False

        now = time.perf_counter()
        if now - self._last_play_at.get(category, 0.0) < self._MIN_INTERVAL_S:
            return False

        from PySide6.QtMultimedia import QMediaPlayer as _QMP
        _playing = _QMP.PlaybackState.PlayingState

        # Enforce a hard concurrent cap to prevent audio soup
        total_playing = sum(
            1 for pool in variant_pools
            for (player, _) in pool
            if player.playbackState() == _playing
        )
        if total_playing >= self._MAX_CONCURRENT:
            return False

        # Build a list of (variant_pool, idle_player, audio_out) tuples
        # Only include variants that have at least one genuinely idle slot.
        candidates: list[tuple] = []
        for pool in variant_pools:
            for (p, ao) in pool:
                if p.playbackState() != _playing:
                    candidates.append((p, ao))
                    break   # one idle slot per variant is enough to make it eligible

        if not candidates:
            return False   # all slots busy — try again next drain tick

        # Pick a random eligible variant, then grab its first idle slot
        player, audio_out = random.choice(candidates)
        self._last_play_at[category] = now
        player.play()
        return True

    def _load_bgm(self) -> None:
        from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
        from PySide6.QtCore import QUrl
        path = BASE_DIR / "soundtrack.mp3"
        if not path.exists():
            print(f"[Audio] BGM not found: {path}")
            return
        try:
            self._bgm_player = QMediaPlayer()
            self._bgm_output = QAudioOutput()
            self._bgm_output.setVolume(0.0)  # silent until start_bgm fades in
            self._bgm_player.setAudioOutput(self._bgm_output)
            self._bgm_player.setSource(QUrl.fromLocalFile(str(path)))
            self._bgm_player.setLoops(QMediaPlayer.Infinite)
        except Exception as e:
            print(f"[Audio] BGM load error: {e}")
            self._bgm_player = None
            self._bgm_output = None

    def start_bgm(self) -> None:
        """Start the background music and fade in to the current music volume."""
        if not self._available or self._bgm_player is None or self._bgm_output is None:
            return
        self._bgm_player.play()
        self._bgm_fade_anim = QPropertyAnimation(self._bgm_output, b"volume")
        self._bgm_fade_anim.setDuration(2000)
        self._bgm_fade_anim.setStartValue(0.0)
        self._bgm_fade_anim.setEndValue(self._music_volume)
        self._bgm_fade_anim.setEasingCurve(QEasingCurve.InOutQuad)
        self._bgm_fade_anim.start()

    def set_sfx_volume(self, v: float) -> None:
        self._sfx_volume = max(0.0, min(1.0, v))
        for variant_pools in self._pools.values():
            for pool in variant_pools:
                for (_, audio_out) in pool:
                    audio_out.setVolume(self._sfx_volume)

    def set_music_volume(self, v: float) -> None:
        self._music_volume = max(0.0, min(1.0, v))
        if self._bgm_output is not None:
            # If a fade-in is still in progress, stop it and snap to the
            # user-chosen level immediately.
            if self._bgm_fade_anim is not None and self._bgm_fade_anim.state() != QPropertyAnimation.Stopped:
                self._bgm_fade_anim.stop()
            self._bgm_output.setVolume(self._music_volume)


# Placeholder — replaced with a real instance in main() after QApplication exists.
AUDIO: "AudioManager" = None  # type: ignore

# ---------------------------------------------------------------------------
# SPRITE SHEET LOADER
# ---------------------------------------------------------------------------
def load_sprite_sheet(filename: str, frame_w: int, frame_h: int, frames: int) -> list[QPixmap]:
    path = BASE_DIR / filename
    if not path.exists():
        return []
    src = QPixmap(str(path))
    result = []
    cols = src.width() // frame_w
    for i in range(frames):
        col = i % cols
        row = i // cols
        x, y = col * frame_w, row * frame_h
        result.append(src.copy(x, y, frame_w, frame_h))
    return result

def load_image(filename: str) -> Optional[QPixmap]:
    path = BASE_DIR / filename
    if not path.exists():
        return None
    return QPixmap(str(path))

# ---------------------------------------------------------------------------
# SIGNAL BUS
# ---------------------------------------------------------------------------
class SignalBus(QObject):
    inventory_changed = Signal()
    gold_changed = Signal()
    prestige_changed = Signal()
    xp_changed = Signal(str, int)      # skill, new_xp
    node_hit = Signal(str, bool)       # node_id, success
    refine_complete = Signal(str, int) # station_id, amount
    refine_started  = Signal(str, float) # station_id, total_duration_secs
    save_triggered = Signal()
    page_changed = Signal(int)
    spirit_changed = Signal(float)     # seconds_remaining (0 = expired)
    level_up = Signal(str, int)        # skill_id, new_level
    gold_delta = Signal(float)         # positive=earn, negative=spend
    shard_delta = Signal(int)          # positive=earn, negative=spend

BUS = SignalBus()

# ---------------------------------------------------------------------------
# STYLE HELPERS
# ---------------------------------------------------------------------------
def hex_color(key: str) -> str:
    return PALETTE.get(key, "#FFFFFF")

def qss_card(bg="#1E2235", border="#2A2F48", radius=16) -> str:
    return f"""
        background: {bg};
        border: 1px solid {border};
        border-radius: {radius}px;
    """

def make_shadow(widget, blur=24, color="#000000", opacity=180, offset=(0, 4)):
    eff = QGraphicsDropShadowEffect(widget)
    eff.setBlurRadius(blur)
    c = QColor(color)
    c.setAlpha(opacity)
    eff.setColor(c)
    eff.setOffset(*offset)
    widget.setGraphicsEffect(eff)

def scaled_font(name: str, pt: float, bold=False, italic=False) -> QFont:
    f = QFont(name, max(1, int(pt * APP_SCALE * BASE_FONT_SCALE)))
    f.setBold(bold)
    f.setItalic(italic)
    return f


def fmt_number(n: float) -> str:
    """Return a compact notation string for large numbers.
    Examples: 999 -> '999', 1500 -> '1.50K', 12300 -> '12.3K',
              1_500_000 -> '1.50M', 2_300_000_000 -> '2.30B', etc.
    """
    n = float(n)
    if n < 0:
        return f"-{fmt_number(-n)}"
    for threshold, suffix in (
        (1e15, "Q"), (1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")
    ):
        if n >= threshold:
            val = n / threshold
            if val >= 100:
                return f"{int(val)}{suffix}"
            elif val >= 10:
                return f"{val:.1f}{suffix}"
            else:
                return f"{val:.2f}{suffix}"
    return f"{int(n):,}"


def _setup_touch_scroll(sa: QScrollArea) -> None:
    """Configure a QScrollArea for touch/drag scrolling with hidden scrollbars."""
    sa.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    sa.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    QScroller.grabGesture(sa.viewport(), QScroller.ScrollerGestureType.LeftMouseButtonGesture)
    scroller = QScroller.scroller(sa.viewport())
    props = scroller.scrollerProperties()
    props.setScrollMetric(
        QScrollerProperties.ScrollMetric.VerticalOvershootPolicy,
        QScrollerProperties.OvershootPolicy.OvershootAlwaysOff,
    )
    props.setScrollMetric(
        QScrollerProperties.ScrollMetric.HorizontalOvershootPolicy,
        QScrollerProperties.OvershootPolicy.OvershootAlwaysOff,
    )
    props.setScrollMetric(QScrollerProperties.ScrollMetric.DragStartDistance, 0.003)
    props.setScrollMetric(QScrollerProperties.ScrollMetric.DecelerationFactor, 0.2)
    scroller.setScrollerProperties(props)


# ---------------------------------------------------------------------------
# ANIMATED SPRITE WIDGET
# ---------------------------------------------------------------------------
class SpriteWidget(QWidget):
    animation_done = Signal()

    def __init__(self, frames: list[QPixmap], delay_ms: int = 100,
                 loop: bool = True, parent=None):
        super().__init__(parent)
        self._frames = frames
        self._delay = delay_ms
        self._loop = loop
        self._current = 0
        self._playing = False
        self._anim_start: float = 0.0  # perf_counter timestamp when play() was called
        # Poll at 8 ms — faster than one OS tick so we always catch the right frame
        # even when the OS timer resolution is coarser than _delay.
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.setSingleShot(False)
        self._timer.setInterval(8)
        self._timer.timeout.connect(self._tick)
        if frames:
            self.setFixedSize(frames[0].size())

    def set_frames(self, frames: list[QPixmap], delay_ms: int = 100):
        self._timer.stop()
        self._frames = frames
        self._delay = delay_ms
        self._current = 0
        self._playing = False
        if frames:
            self.setFixedSize(frames[0].size())
        self.update()

    def play(self, loop: bool | None = None):
        if loop is not None:
            self._loop = loop
        self._timer.stop()
        self._current = 0
        self._playing = True
        self._anim_start = time.perf_counter()
        self._timer.start()
        self.update()

    def stop(self):
        self._playing = False
        self._timer.stop()

    def _tick(self):
        if not self._frames or not self._playing:
            return
        total_ms = len(self._frames) * self._delay
        elapsed_ms = (time.perf_counter() - self._anim_start) * 1000.0
        if not self._loop and elapsed_ms >= total_ms:
            self._current = len(self._frames) - 1
            self.stop()
            self.update()
            self.animation_done.emit()
        else:
            frame = int((elapsed_ms % total_ms) / self._delay) if self._loop \
                else min(int(elapsed_ms / self._delay), len(self._frames) - 1)
            if frame != self._current:
                self._current = frame
                self.update()

    def paintEvent(self, event):
        if not self._frames:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform, False)
        px = self._frames[self._current]
        p.drawPixmap(self.rect(), px)


# ---------------------------------------------------------------------------
# PLACEHOLDER SPRITE (drawn when PNG is missing)
# ---------------------------------------------------------------------------
def make_placeholder(w: int, h: int, label: str, color: str = "#3A4060") -> QPixmap:
    px = QPixmap(w, h)
    px.fill(Qt.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor(color))
    p.setPen(QPen(QColor("#5A6080"), 2))
    p.drawRoundedRect(4, 4, w-8, h-8, 12, 12)
    p.setPen(QColor(PALETTE["text_muted"]))
    p.setFont(scaled_font(FONT_BODY, 10))
    p.drawText(QRect(0, 0, w, h), Qt.AlignCenter, label)
    p.end()
    return px


# ---------------------------------------------------------------------------
# SWIPE CONTAINER  (swipe left/right, and optionally up/down in grid mode)
# ---------------------------------------------------------------------------
class SwipeContainer(QWidget):
    """
    A paged swipe widget.  When cols=1 (default) it works as a single-row
    left/right carousel with dot indicators.  When cols>1 items are arranged
    in a grid (row-major) and both horizontal AND vertical swipes work, with
    a matching grid of dot indicators.
    """
    index_changed = Signal(int)

    def __init__(self, cols: int = 1, parent=None):
        super().__init__(parent)
        self._items: list[QWidget] = []
        self._index = 0
        self._row = 0
        self._col = 0
        self._cols = max(1, cols)
        self._dots_2d: list[list] = []   # [row][col] -> QLabel or None
        self._drag_start: Optional[QPoint] = None
        self._drag_threshold = 55
        self.setMouseTracking(True)

        self._layout = QStackedWidget(self)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._layout)

        # Dot indicator bar (grid layout when cols>1, horizontal otherwise)
        self._dot_bar = QWidget(self)
        if self._cols > 1:
            self._dot_grid = QGridLayout(self._dot_bar)
            self._dot_grid.setAlignment(Qt.AlignCenter)
            self._dot_grid.setHorizontalSpacing(10)
            self._dot_grid.setVerticalSpacing(4)
        else:
            self._dot_grid = QHBoxLayout(self._dot_bar)
            self._dot_grid.setAlignment(Qt.AlignCenter)
            self._dot_grid.setSpacing(8)
        outer.addWidget(self._dot_bar)
        outer.setAlignment(self._dot_bar, Qt.AlignHCenter)

    # ------------------------------------------------------------------
    def add_item(self, w: QWidget):
        self._items.append(w)
        self._layout.addWidget(w)
        self._rebuild_dots()

    def clear_items(self):
        while self._items:
            w = self._items.pop()
            self._layout.removeWidget(w)
            w.deleteLater()
        self._index = 0
        self._row = 0
        self._col = 0
        self._rebuild_dots()

    def _num_rows(self) -> int:
        if not self._items:
            return 1
        return math.ceil(len(self._items) / self._cols)

    def _rebuild_dots(self):
        # Clear all widgets from the layout
        while self._dot_grid.count():
            item = self._dot_grid.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        self._dots_2d = []

        if self._cols > 1:
            rows = self._num_rows()
            for r in range(rows):
                row_dots = []
                for c in range(self._cols):
                    idx = r * self._cols + c
                    dot = QLabel("●")
                    dot.setFont(scaled_font(FONT_BODY, 14))
                    dot.setAlignment(Qt.AlignCenter)
                    if idx < len(self._items):
                        self._dot_grid.addWidget(dot, r, c)
                        row_dots.append(dot)
                    else:
                        dot.deleteLater()
                        row_dots.append(None)
                self._dots_2d.append(row_dots)
        else:
            for i in range(len(self._items)):
                dot = QLabel("●")
                dot.setFont(scaled_font(FONT_BODY, 24))
                self._dot_grid.addWidget(dot)
        self._update_dots()

    def _update_dots(self):
        if self._cols > 1:
            for r, row in enumerate(self._dots_2d):
                for c, dot in enumerate(row):
                    if dot:
                        active = (r == self._row and c == self._col)
                        dot.setStyleSheet(
                            f"color: {PALETTE['accent'] if active else PALETTE['text_dim']};"
                        )
        else:
            for i in range(self._dot_grid.count()):
                dot = self._dot_grid.itemAt(i).widget()
                if dot:
                    active = (i == self._index)
                    dot.setStyleSheet(f"color: {PALETTE['accent'] if active else PALETTE['text_dim']};")

    def go_to(self, idx: int):
        if not self._items:
            return
        idx = max(0, min(idx, len(self._items) - 1))
        self._index = idx
        if self._cols > 1:
            self._row = idx // self._cols
            self._col = idx % self._cols
        self._layout.setCurrentIndex(idx)
        self._update_dots()
        self.index_changed.emit(idx)

    def go_to_rc(self, row: int, col: int):
        """Navigate to a specific (row, col) in grid mode."""
        if not self._items:
            return
        rows = self._num_rows()
        row = max(0, min(row, rows - 1))
        col = max(0, min(col, self._cols - 1))
        idx = row * self._cols + col
        if idx < len(self._items):
            self.go_to(idx)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_start = e.position().toPoint()

    def mouseReleaseEvent(self, e):
        if self._drag_start is None:
            return
        dx = e.position().toPoint().x() - self._drag_start.x()
        dy = e.position().toPoint().y() - self._drag_start.y()
        self._drag_start = None

        if self._cols > 1 and abs(dy) > abs(dx) and abs(dy) > self._drag_threshold:
            # Vertical swipe — navigate rows
            if dy < 0:
                self.go_to_rc(self._row + 1, self._col)
            else:
                self.go_to_rc(self._row - 1, self._col)
        elif abs(dx) > self._drag_threshold:
            # Horizontal swipe — navigate columns
            if self._cols > 1:
                if dx < 0:
                    self.go_to_rc(self._row, self._col + 1)
                else:
                    self.go_to_rc(self._row, self._col - 1)
            else:
                if dx < 0:
                    self.go_to(self._index + 1)
                else:
                    self.go_to(self._index - 1)


# ---------------------------------------------------------------------------
# ANIMATED NUMBER LABEL
# ---------------------------------------------------------------------------
class AnimatedNumber(QLabel):
    def __init__(self, value: float = 0, fmt="{:.0f}", parent=None):
        super().__init__(parent)
        self._value = value
        self._fmt = fmt
        # Persistent effect + animation — reused every update, never re-created
        self._eff = QGraphicsOpacityEffect(self)
        self._eff.setOpacity(1.0)
        self.setGraphicsEffect(self._eff)
        self._flash_anim = QPropertyAnimation(self._eff, b"opacity", self)
        self._flash_anim.setDuration(200)
        self._flash_anim.setStartValue(0.3)
        self._flash_anim.setEndValue(1.0)
        self._update_text()

    def set_value(self, v: float, animate=True):
        old = self._value
        self._value = v
        if animate and abs(v - old) > 0.5:
            self._flash_anim.stop()
            self._eff.setOpacity(0.3)
            self._flash_anim.start()
        self._update_text()

    def _update_text(self):
        self.setText(self._fmt.format(self._value))


# ---------------------------------------------------------------------------
# TOAST NOTIFICATION
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# FLOATING TEXT  (rising "+X XP" / "+X🪙" notification)
# ---------------------------------------------------------------------------
class FloatingText(QLabel):
    """
    Reusable rising text notification.  Instead of being created and
    destroyed on every click, instances are recycled via a per-parent pool
    (see spawn_floating_text()).  Each instance owns its QGraphicsOpacityEffect
    and both QPropertyAnimations permanently — they are just re-targeted on
    each reuse, avoiding repeated alloc/dealloc under spam-click conditions.
    """

    # Hard cap on how many FloatingText labels may exist simultaneously per
    # parent window.  If the pool is fully active, new spawns are dropped.
    _MAX_POOL = 8

    # Class-level pool: parent_widget -> [FloatingText, ...]
    _pool: dict = {}

    @classmethod
    def spawn(cls, text: str, color: str, parent: QWidget,
              cx: int = -1, cy: int = -1) -> None:
        """Acquire an idle instance from the pool (or create one if needed)
        and play the rise animation.  Safe to call at any rate."""
        pid = id(parent)
        pool = cls._pool.setdefault(pid, [])

        # Register a one-time cleanup when the parent is destroyed so the
        # pool dict doesn't hold dead widget references indefinitely.
        if len(pool) == 0:
            try:
                parent.destroyed.connect(lambda: cls._pool.pop(pid, None))
            except Exception:
                pass

        # Find an idle (hidden) instance
        instance = None
        for ft in pool:
            if ft.isHidden():
                instance = ft
                break

        # Create a new slot if under the cap
        if instance is None:
            if len(pool) >= cls._MAX_POOL:
                return   # pool saturated — silently drop
            instance = cls(parent)
            pool.append(instance)

        instance._play(text, color, cx, cy)

    # ------------------------------------------------------------------
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setFont(scaled_font(FONT_BODY, 13, bold=True))

        self._eff = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._eff)

        self._pos_anim = QPropertyAnimation(self, b"pos", self)
        self._pos_anim.setDuration(1500)
        self._pos_anim.setEasingCurve(QEasingCurve.OutCubic)

        self._opa_anim = QPropertyAnimation(self._eff, b"opacity", self)
        self._opa_anim.setDuration(1500)
        self._opa_anim.setKeyValueAt(0.0,  0.0)
        self._opa_anim.setKeyValueAt(0.12, 1.0)
        self._opa_anim.setKeyValueAt(0.65, 1.0)
        self._opa_anim.setKeyValueAt(1.0,  0.0)

        self._grp = QParallelAnimationGroup(self)
        self._grp.addAnimation(self._pos_anim)
        self._grp.addAnimation(self._opa_anim)
        self._grp.finished.connect(self.hide)
        self.hide()

    def _play(self, text: str, color: str, cx: int, cy: int) -> None:
        # Stop any in-progress animation before reusing
        self._grp.stop()
        self._eff.setOpacity(0.0)

        self.setText(text)
        self.setStyleSheet(f"color: {color}; background: transparent; border: none;")
        self.adjustSize()

        p = self.parent()
        if cx < 0:
            cx = p.width() // 2
        if cy < 0:
            cy = p.height() // 2 - 20

        sx = cx - self.width() // 2
        sy = cy - self.height() // 2
        self.move(sx, sy)
        self.show()
        self.raise_()

        self._pos_anim.setStartValue(QPoint(sx, sy))
        self._pos_anim.setEndValue(QPoint(sx, sy - 80))
        self._grp.start()


def spawn_floating_text(text: str, color: str, parent: QWidget,
                        cx: int = -1, cy: int = -1) -> None:
    """Convenience wrapper — use this everywhere instead of FloatingText(...)."""
    FloatingText.spawn(text, color, parent, cx, cy)


# ---------------------------------------------------------------------------
# LEVEL-UP TOAST
# ---------------------------------------------------------------------------
class LevelUpToast(QFrame):
    """Animated level-up notification — slides in, holds 2s, fades out."""
    def __init__(self, skill_id: str, new_level: int, parent: QWidget):
        super().__init__(parent)
        skill_def = SKILLS.get(skill_id, {"name": skill_id, "color": PALETTE["accent"], "icon": "⬆"})
        color = skill_def["color"]
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setStyleSheet(f"""
            QFrame {{
                background: {PALETTE['bg_card']};
                border: 2px solid {color};
                border-radius: 20px;
            }}
        """)
        make_shadow(self, blur=40, color=color, opacity=180)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(30, 18, 30, 18)
        lay.setSpacing(4)
        lay.setAlignment(Qt.AlignCenter)

        badge = QLabel(f"{skill_def['icon']}  LEVEL UP!")
        badge.setFont(scaled_font(FONT_TITLE, 11, bold=True))
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet(f"color: {color}; background: transparent; border: none;")
        lay.addWidget(badge)

        name_lbl = QLabel(skill_def["name"])
        name_lbl.setFont(scaled_font(FONT_BODY, 11))
        name_lbl.setAlignment(Qt.AlignCenter)
        name_lbl.setStyleSheet(f"color: {PALETTE['text_muted']}; background: transparent; border: none;")
        lay.addWidget(name_lbl)

        lvl_lbl = QLabel(f"Level {new_level}")
        lvl_lbl.setFont(scaled_font(FONT_TITLE, 22, bold=True))
        lvl_lbl.setAlignment(Qt.AlignCenter)
        lvl_lbl.setStyleSheet(f"color: {color}; background: transparent; border: none;")
        lay.addWidget(lvl_lbl)

        self.setMinimumWidth(240)
        self.adjustSize()

        if parent:
            px = (parent.width() - self.width()) // 2
            py = (parent.height() - self.height()) // 2
        else:
            px, py = 60, 300

        self.move(px, py - 50)
        self.show()
        self.raise_()

        self._eff = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._eff)

        # Slide in from above + fade in (280ms)
        self._pos_in = QPropertyAnimation(self, b"pos", self)
        self._pos_in.setDuration(280)
        self._pos_in.setStartValue(QPoint(px, py - 50))
        self._pos_in.setEndValue(QPoint(px, py))
        self._pos_in.setEasingCurve(QEasingCurve.OutBack)

        self._opa_in = QPropertyAnimation(self._eff, b"opacity", self)
        self._opa_in.setDuration(200)
        self._opa_in.setStartValue(0.0)
        self._opa_in.setEndValue(1.0)

        self._grp_in = QParallelAnimationGroup(self)
        self._grp_in.addAnimation(self._pos_in)
        self._grp_in.addAnimation(self._opa_in)
        self._grp_in.finished.connect(self._start_hold)
        self._grp_in.start()

    def _start_hold(self):
        self._hold = QTimer(self)
        self._hold.setSingleShot(True)
        self._hold.setInterval(2000)
        self._hold.timeout.connect(self._start_fadeout)
        self._hold.start()

    def _start_fadeout(self):
        self._opa_out = QPropertyAnimation(self._eff, b"opacity", self)
        self._opa_out.setDuration(500)
        self._opa_out.setStartValue(1.0)
        self._opa_out.setEndValue(0.0)
        self._opa_out.finished.connect(self.deleteLater)
        self._opa_out.start()


# ---------------------------------------------------------------------------
# TOAST  (brief message at top of screen)
# ---------------------------------------------------------------------------
class Toast(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setWordWrap(False)
        self.setStyleSheet(f"""
            background: {PALETTE['bg_light']};
            color: {PALETTE['accent']};
            border: 1px solid {PALETTE['accent']};
            border-radius: 20px;
            padding: 8px 24px;
            font-family: '{FONT_BODY}';
            font-size: 13px;
        """)
        make_shadow(self, blur=20)
        self.hide()
        # Persistent effect and animations — never recreated
        self._eff = QGraphicsOpacityEffect(self)
        self._eff.setOpacity(0.0)
        self.setGraphicsEffect(self._eff)
        self._anim_in = QPropertyAnimation(self._eff, b"opacity", self)
        self._anim_in.setDuration(250)
        self._anim_in.setStartValue(0.0)
        self._anim_in.setEndValue(1.0)
        self._anim_out = QPropertyAnimation(self._eff, b"opacity", self)
        self._anim_out.setDuration(400)
        self._anim_out.setStartValue(1.0)
        self._anim_out.setEndValue(0.0)
        self._anim_out.finished.connect(self.hide)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._fade_out)

    def show_message(self, msg: str, color: str = None):
        self.setText(msg)
        if color:
            self.setStyleSheet(self.styleSheet().replace(
                f"color: {PALETTE['accent']}", f"color: {color}"
            ))
        self.adjustSize()
        if self.parent():
            pw = self.parent().width()
            self.move((pw - self.width()) // 2, 60)
        self._anim_out.stop()
        self._eff.setOpacity(0.0)
        self.show()
        self._anim_in.start()
        self._timer.start(2000)

    def _fade_out(self):
        self._anim_in.stop()
        self._anim_out.start()


# ---------------------------------------------------------------------------
# REFINE HUD  (live per-station progress shown in the header)
# ---------------------------------------------------------------------------
class _RefineHUD(QWidget):
    """
    Three-row compact progress display — one row per refining station.
    Invisible (opacity 0) when nothing is refining; fades in when any
    station starts and fades back out when all finish.
    """
    def __init__(self, state: GameState, parent=None):
        super().__init__(parent)
        self._state = state
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self._active: dict = {}  # station_id -> (start_time, duration)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 4)
        lay.setSpacing(4)

        self._bars: dict = {}  # station_id -> QProgressBar
        for station_id, station_def in REFINING_STATIONS.items():
            skill   = station_def.get("xp_skill", "")
            bar_clr = SKILLS.get(skill, {}).get("color", PALETTE["accent"])

            row_w = QWidget()
            row_w.setStyleSheet("background: transparent;")
            row_l = QHBoxLayout(row_w)
            row_l.setContentsMargins(0, 0, 0, 0)
            row_l.setSpacing(6)

            icon_lbl = QLabel(SKILLS.get(skill, {}).get("icon", ""))
            icon_lbl.setFont(scaled_font(FONT_BODY, 11))
            icon_lbl.setFixedWidth(sz(20))
            icon_lbl.setStyleSheet("background: transparent; border: none;")

            name_lbl = QLabel(station_def["name"])
            name_lbl.setFont(scaled_font(FONT_BODY, 9, bold=True))
            name_lbl.setStyleSheet(f"color: {PALETTE['text_muted']}; background: transparent; border: none;")
            name_lbl.setFixedWidth(sz(68))

            bar = QProgressBar()
            bar.setRange(0, 1000)
            bar.setValue(0)
            bar.setTextVisible(False)
            bar.setFixedHeight(sz(5))
            bar.setStyleSheet(f"""
                QProgressBar {{ background: rgba(255,255,255,18); border: none; border-radius: {sz(2)}px; }}
                QProgressBar::chunk {{ background: {bar_clr}; border-radius: {sz(2)}px; }}
            """)

            row_l.addWidget(icon_lbl)
            row_l.addWidget(name_lbl)
            row_l.addWidget(bar, stretch=1)
            lay.addWidget(row_w)
            self._bars[station_id] = bar

        self.setMinimumWidth(sz(280))

        # Fade effect
        self._eff = QGraphicsOpacityEffect(self)
        self._eff.setOpacity(0.0)
        self.setGraphicsEffect(self._eff)
        self._anim = QPropertyAnimation(self._eff, b"opacity", self)
        self._anim.setDuration(400)
        self._anim.setEasingCurve(QEasingCurve.InOutQuad)

        self._poll = QTimer(self)
        self._poll.setInterval(80)
        self._poll.timeout.connect(self._tick)

        BUS.refine_started.connect(self._on_started)
        BUS.refine_complete.connect(self._on_complete)

    def _on_started(self, station_id: str, duration: float):
        self._active[station_id] = (time.time(), max(duration, 0.001))
        if not self._poll.isActive():
            self._poll.start()
        self._fade_to(1.0)

    def _on_complete(self, station_id: str, _amount: int):
        self._active.pop(station_id, None)
        bar = self._bars.get(station_id)
        if bar:
            bar.setValue(0)
        if not self._active:
            self._poll.stop()
            self._fade_to(0.0)

    def _tick(self):
        now = time.time()
        for sid, (start, dur) in list(self._active.items()):
            pct = min((now - start) / dur, 1.0)
            bar = self._bars.get(sid)
            if bar:
                bar.setValue(int(pct * 1000))

    def _fade_to(self, target: float):
        self._anim.stop()
        self._anim.setStartValue(float(self._eff.opacity()))
        self._anim.setEndValue(target)
        self._anim.start()


# ---------------------------------------------------------------------------
# HEADER BAR
# ---------------------------------------------------------------------------
class HeaderBar(QWidget):
    settings_clicked = Signal()

    def __init__(self, state: GameState, parent=None):
        super().__init__(parent)
        self._state = state
        self.setFixedHeight(sz(88))
        self.setStyleSheet(f"background: {PALETTE['bg_mid']}; border-bottom: 1px solid {PALETTE['border']};")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 0, 16, 0)

        # Dynamic refining HUD (replaces static title)
        self._refine_hud = _RefineHUD(state, self)

        # Gold — compound widget: coin icon + animated number
        _gold_widget = QWidget()
        _gold_widget.setStyleSheet("background: transparent;")
        _gold_hlay = QHBoxLayout(_gold_widget)
        _gold_hlay.setContentsMargins(0, 0, 0, 0)
        _gold_hlay.setSpacing(5)
        _coin_icon_lbl = QLabel()
        _coin_icon_lbl.setStyleSheet("background: transparent; border: none;")
        _coin_px = load_image("coin.png")
        if _coin_px:
            _coin_icon_lbl.setPixmap(_coin_px.scaled(sz(56), sz(56), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        _gold_hlay.addWidget(_coin_icon_lbl)
        self._gold_lbl = AnimatedNumber(state.gold, fmt="{:.0f}")
        self._gold_lbl.setFont(scaled_font(FONT_BODY, 15, bold=True))
        self._gold_lbl.setStyleSheet(f"color: {PALETTE['gold']}; background: transparent; border: none;")
        _gold_hlay.addWidget(self._gold_lbl)
        self._gold_widget = _gold_widget

        # Prestige composite widget (image icon + tier text + coin image + count)
        self._prestige_widget = QWidget()
        self._prestige_widget.setStyleSheet("background: transparent;")
        _pw_lay = QHBoxLayout(self._prestige_widget)
        _pw_lay.setContentsMargins(0, 0, 0, 0)
        _pw_lay.setSpacing(4)
        self._prestige_icon_lbl = QLabel()
        self._prestige_icon_lbl.setStyleSheet("background: transparent; border: none;")
        _ppx = load_image("prestigeStatic.png")
        if _ppx:
            self._prestige_icon_lbl.setPixmap(_ppx.scaled(sz(42), sz(42), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self._prestige_tier_lbl = QLabel()
        self._prestige_tier_lbl.setFont(scaled_font(FONT_BODY, 16, bold=True))
        self._prestige_tier_lbl.setStyleSheet(f"color: {PALETTE['prestige']}; background: transparent; border: none;")
        self._prestige_coin_icon_lbl = QLabel()
        self._prestige_coin_icon_lbl.setStyleSheet("background: transparent; border: none;")
        _cpx = load_image("prestigeCoinStatic.png")
        if _cpx:
            self._prestige_coin_icon_lbl.setPixmap(_cpx.scaled(sz(42), sz(42), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self._prestige_coins_count_lbl = QLabel()
        self._prestige_coins_count_lbl.setFont(scaled_font(FONT_BODY, 16, bold=True))
        self._prestige_coins_count_lbl.setStyleSheet(f"color: {PALETTE['prestige']}; background: transparent; border: none;")
        _pw_lay.addWidget(self._prestige_icon_lbl)
        _pw_lay.addWidget(self._prestige_tier_lbl)
        _pw_lay.addSpacing(6)
        _pw_lay.addWidget(self._prestige_coin_icon_lbl)
        _pw_lay.addWidget(self._prestige_coins_count_lbl)
        self._prestige_widget.hide()

        # Settings cog button — uses cog.png if available
        cog = QPushButton()
        cog.setFixedSize(sz(72), sz(72))
        cog.setCursor(QCursor(Qt.PointingHandCursor))
        cog.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,12);
                border: none;
                border-radius: {sz(36)}px;
            }}
            QPushButton:hover   {{ background: rgba(255,255,255,22); }}
            QPushButton:pressed {{ background: rgba(255,255,255,32); }}
        """)
        _cog_px = load_image("cog.png")
        if _cog_px:
            cog.setIcon(QIcon(_cog_px.scaled(sz(52), sz(52), Qt.KeepAspectRatio, Qt.SmoothTransformation)))
            cog.setIconSize(QSize(sz(52), sz(52)))
        else:
            cog.setText("⚙")
            cog.setFont(scaled_font(FONT_BODY, 28))
        cog.clicked.connect(self.settings_clicked)

        lay.addWidget(self._refine_hud)
        lay.addStretch()
        lay.addWidget(self._prestige_widget)
        lay.addSpacing(12)
        lay.addWidget(self._gold_widget)
        lay.addSpacing(8)
        lay.addWidget(cog)

        BUS.gold_changed.connect(self._refresh)
        BUS.prestige_changed.connect(self._refresh)
        self._refresh()

    def _refresh(self):
        self._gold_lbl.set_value(self._state.gold)
        if self._state.prestige_tier > 0:
            self._prestige_tier_lbl.setText(f"Tier {self._state.prestige_tier}")
            self._prestige_coins_count_lbl.setText(str(self._state.prestige_coins))
            self._prestige_widget.show()
        else:
            self._prestige_widget.hide()


# ---------------------------------------------------------------------------
# NAV BAR
# ---------------------------------------------------------------------------
class NavBar(QWidget):
    tab_changed = Signal(int)

    TABS = [
        ("", "Gather"),
        ("", "Refine"),
        ("", "Items"),
        ("", "Upgrades"),
        ("", "Prestige"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(sz(144))
        self.setStyleSheet(f"background: {PALETTE['bg_mid']}; border-top: 1px solid {PALETTE['border']};")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self._buttons: list[QPushButton] = []
        self._active = 0
        for i, (icon, label) in enumerate(self.TABS):
            btn = QPushButton(label)
            btn.setFont(scaled_font(FONT_BODY, 11))
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, idx=i: self._select(idx))
            self._buttons.append(btn)
            lay.addWidget(btn)
        # Set image icons for all tabs
        _nav_icons = [
            ("pickaxeT3.png", 0, sz(58)),
            ("forgeStatic.png", 1, sz(47)),
            ("items.png", 2, sz(47)),
            ("upgrades.png", 3, sz(47)),
            ("prestigeStatic.png", 4, sz(47)),
        ]
        for filename, idx, icon_sz in _nav_icons:
            _px = load_image(filename)
            if _px:
                _scaled = _px.scaled(icon_sz, icon_sz, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self._buttons[idx].setIcon(QIcon(_scaled))
                self._buttons[idx].setIconSize(QSize(icon_sz, icon_sz))
        self._update_styles()

    def _select(self, idx: int):
        self._active = idx
        self._update_styles()
        self.tab_changed.emit(idx)

    def _update_styles(self):
        for i, btn in enumerate(self._buttons):
            active = (i == self._active)
            btn.setChecked(active)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {'#252A3D' if active else 'transparent'};
                    color: {PALETTE['accent'] if active else PALETTE['text_muted']};
                    border: none;
                    border-top: 2px solid {'#E8A44A' if active else 'transparent'};
                    font-family: '{FONT_BODY}';
                    font-size: {int(17 * APP_SCALE)}pt;
                    padding: 4px;
                }}
                QPushButton:hover {{
                    background: #202436;
                    color: {PALETTE['text_primary']};
                }}
            """)

    def set_active(self, idx: int):
        self._select(idx)

    def paintEvent(self, event):
        """Paint background then overlay a strong shadow band at the top edge."""
        super().paintEvent(event)
        p = QPainter(self)
        # Strong shadow strip at top — fades downward, making navbar pop from content
        shadow_h = min(self.height(), sz(36))
        grad = QLinearGradient(0, 0, 0, shadow_h)
        grad.setColorAt(0.0, QColor(0, 0, 0, 210))
        grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.fillRect(QRect(0, 0, self.width(), shadow_h), grad)
        p.end()


# ---------------------------------------------------------------------------
# SETTINGS OVERLAY  (floating card — like the prestige confirm window)
# ---------------------------------------------------------------------------
class SettingsOverlay(QWidget):
    def __init__(self, state: GameState, parent=None):
        super().__init__(parent)
        self._state = state
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setStyleSheet("background: rgba(0,0,0,0);")
        self.hide()

        # Full-coverage dim backdrop
        _backdrop = QWidget(self)
        _backdrop.setStyleSheet("background: rgba(0,0,0,160); border-radius: 0px;")
        _backdrop_lay = QVBoxLayout(_backdrop)
        _backdrop_lay.setContentsMargins(0, 0, 0, 0)
        _backdrop_lay.setAlignment(Qt.AlignCenter)
        self._backdrop = _backdrop

        # Centered card — single flat layout, no scroll/button-bar split
        _card = QFrame(_backdrop)
        _card.setFixedWidth(sz(390))
        _card.setStyleSheet(f"""
            QFrame {{
                background: {PALETTE['bg_mid']};
                border: 2px solid {PALETTE['border']};
                border-radius: 20px;
            }}
        """)
        make_shadow(_card, blur=40, color="#000000", opacity=180)
        lay = QVBoxLayout(_card)
        lay.setContentsMargins(sz(22), sz(18), sz(22), sz(18))
        lay.setSpacing(sz(10))

        # Title + version row
        _title_row = QHBoxLayout()
        _title_row.setSpacing(6)
        title = QLabel("⚙  Settings")
        title.setFont(scaled_font(FONT_TITLE, 14, bold=True))
        title.setStyleSheet(f"color: {PALETTE['accent']}; background: transparent; border: none;")
        _ver_lbl = QLabel("Version 0.6.78 ALPHA")
        _ver_lbl.setFont(scaled_font(FONT_MONO, 8))
        _ver_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        _ver_lbl.setStyleSheet(f"color: {PALETTE['text_dim']}; background: transparent; border: none;")
        _title_row.addWidget(title)
        _title_row.addStretch()
        _title_row.addWidget(_ver_lbl)
        lay.addLayout(_title_row)

        init_music = int((AUDIO._music_volume if AUDIO else 0.5) * 100)
        init_sfx   = int((AUDIO._sfx_volume   if AUDIO else 0.8) * 100)
        self._add_slider(lay, "🎵 Music", 0, 100, init_music, self._on_music_changed)
        self._add_slider(lay, "🔊 SFX",   0, 100, init_sfx,   self._on_sfx_changed)
        cfg = load_config()
        init_scale = int(cfg.get("ui_scale", APP_SCALE) * 100)
        self._add_slider(lay, "🔍 UI Scale", 50, 150, init_scale, self._on_scale_changed)

        note = QLabel("UI scale change takes effect on next launch.")
        note.setFont(scaled_font(FONT_BODY, 8))
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {PALETTE['text_dim']}; border: none; background: transparent;")
        lay.addWidget(note)

        # Special thanks credit (compact horizontal)
        _credit_frame = QFrame()
        _credit_frame.setStyleSheet(f"""
            QFrame {{
                background: rgba(255,255,255,6);
                border: 1px solid {PALETTE['border']};
                border-radius: 8px;
            }}
        """)
        _credit_lay = QHBoxLayout(_credit_frame)
        _credit_lay.setContentsMargins(10, 6, 10, 6)
        _credit_lay.setSpacing(6)
        _credit_hdr = QLabel("Special Thanks to:")
        _credit_hdr.setFont(scaled_font(FONT_BODY, 8, bold=True))
        _credit_hdr.setStyleSheet(f"color: {PALETTE['text_muted']}; background: transparent; border: none;")
        _credit_lbl = QLabel("RPG Music Maker — Travis Savoie")
        _credit_lbl.setFont(scaled_font(FONT_BODY, 9))
        _credit_lbl.setStyleSheet(f"color: {PALETTE['text_primary']}; background: transparent; border: none;")
        _credit_lay.addWidget(_credit_hdr)
        _credit_lay.addWidget(_credit_lbl)
        _credit_lay.addStretch()
        lay.addWidget(_credit_frame)

        debug_gold_btn = QPushButton("Debug: +5,000 Gold")
        debug_gold_btn.setFont(scaled_font(FONT_BODY, 10, bold=True))
        debug_gold_btn.setCursor(QCursor(Qt.PointingHandCursor))
        debug_gold_btn.setFixedHeight(sz(36))
        debug_gold_btn.setStyleSheet(f"""
            QPushButton {{
                background: {PALETTE['accent2']};
                color: {PALETTE['bg_dark']};
                border: none; border-radius: 8px; padding: 4px;
            }}
            QPushButton:hover {{ background: #4EB4A6; }}
        """)
        debug_gold_btn.clicked.connect(self._add_debug_gold)
        lay.addWidget(debug_gold_btn)

        reset_btn = QPushButton("🗑  Reset Game")
        reset_btn.setFont(scaled_font(FONT_BODY, 10, bold=True))
        reset_btn.setCursor(QCursor(Qt.PointingHandCursor))
        reset_btn.setFixedHeight(sz(36))
        reset_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {PALETTE['danger']};
                border: 1px solid {PALETTE['danger']};
                border-radius: 8px; padding: 4px;
            }}
            QPushButton:hover {{ background: rgba(232,106,94,18); }}
        """)
        lay.addWidget(reset_btn)

        self._reset_confirm = QFrame()
        self._reset_confirm.setStyleSheet(f"""
            QFrame {{
                background: rgba(232,106,94,18);
                border: 1px solid {PALETTE['danger']};
                border-radius: 8px;
            }}
        """)
        _rc_lay = QVBoxLayout(self._reset_confirm)
        _rc_lay.setContentsMargins(10, 8, 10, 8)
        _rc_lay.setSpacing(6)
        _warn_lbl = QLabel("⚠  Erase ALL progress? Gold, skills, inventory,\nprestige — everything. There is NO undo.")
        _warn_lbl.setFont(scaled_font(FONT_BODY, 9, bold=True))
        _warn_lbl.setWordWrap(True)
        _warn_lbl.setAlignment(Qt.AlignCenter)
        _warn_lbl.setStyleSheet(f"color: {PALETTE['danger']}; background: transparent; border: none;")
        _rc_lay.addWidget(_warn_lbl)
        _rc_btns = QHBoxLayout()
        _rc_btns.setSpacing(6)
        _rc_cancel = QPushButton("Cancel")
        _rc_cancel.setFont(scaled_font(FONT_BODY, 10))
        _rc_cancel.setCursor(QCursor(Qt.PointingHandCursor))
        _rc_cancel.setFixedHeight(sz(32))
        _rc_cancel.setStyleSheet(f"""
            QPushButton {{
                background: {PALETTE['bg_light']};
                color: {PALETTE['text_primary']};
                border: 1px solid {PALETTE['border']};
                border-radius: 6px; padding: 4px;
            }}
            QPushButton:hover {{ background: {PALETTE['bg_card']}; }}
        """)
        _rc_cancel.clicked.connect(lambda: self._reset_confirm.hide())
        _rc_go = QPushButton("Yes, Reset Everything")
        _rc_go.setFont(scaled_font(FONT_BODY, 10, bold=True))
        _rc_go.setCursor(QCursor(Qt.PointingHandCursor))
        _rc_go.setFixedHeight(sz(32))
        _rc_go.setStyleSheet(f"""
            QPushButton {{
                background: {PALETTE['danger']};
                color: white; border: none;
                border-radius: 6px; padding: 4px;
            }}
            QPushButton:hover {{ background: #C05040; }}
        """)
        _rc_go.clicked.connect(self._do_reset_game)
        _rc_btns.addWidget(_rc_cancel)
        _rc_btns.addWidget(_rc_go)
        _rc_lay.addLayout(_rc_btns)
        self._reset_confirm.hide()
        lay.addWidget(self._reset_confirm)
        reset_btn.clicked.connect(lambda: self._reset_confirm.setVisible(not self._reset_confirm.isVisible()))

        # Close | Exit — same section, no divider
        _btn_row = QHBoxLayout()
        _btn_row.setSpacing(10)
        close = QPushButton("Close")
        close.setFont(scaled_font(FONT_BODY, 11))
        close.setFixedHeight(sz(40))
        close.setCursor(QCursor(Qt.PointingHandCursor))
        close.setStyleSheet(f"""
            QPushButton {{
                background: {PALETTE['bg_light']};
                color: {PALETTE['text_primary']};
                border: 1px solid {PALETTE['border']};
                border-radius: 10px; padding: 6px;
            }}
            QPushButton:hover {{ background: {PALETTE['bg_card']}; }}
        """)
        close.clicked.connect(self.hide)
        exit_btn = QPushButton("✕  Exit Game")
        exit_btn.setFont(scaled_font(FONT_BODY, 11))
        exit_btn.setFixedHeight(sz(40))
        exit_btn.setCursor(QCursor(Qt.PointingHandCursor))
        exit_btn.setStyleSheet(f"""
            QPushButton {{
                background: {PALETTE['danger']};
                color: white; border: none;
                border-radius: 10px; padding: 6px;
            }}
            QPushButton:hover {{ background: #C05040; }}
        """)
        exit_btn.clicked.connect(QApplication.instance().quit)
        _btn_row.addWidget(close)
        _btn_row.addWidget(exit_btn)
        lay.addLayout(_btn_row)

        _backdrop_lay.addWidget(_card)

        _self_lay = QVBoxLayout(self)
        _self_lay.setContentsMargins(0, 0, 0, 0)
        _self_lay.addWidget(_backdrop)

    def showEvent(self, event):
        super().showEvent(event)
        if self.parent():
            self.setGeometry(self.parent().rect())

    def _on_music_changed(self, value: int):
        v = value / 100
        if AUDIO:
            AUDIO.set_music_volume(v)
        cfg = load_config()
        cfg["music_volume"] = v
        save_config(cfg)

    def _on_sfx_changed(self, value: int):
        v = value / 100
        if AUDIO:
            AUDIO.set_sfx_volume(v)
        cfg = load_config()
        cfg["sfx_volume"] = v
        save_config(cfg)

    def _on_scale_changed(self, value: int):
        cfg = load_config()
        cfg["ui_scale"] = value / 100
        save_config(cfg)

    def _add_debug_gold(self):
        self._state.gold += 5000
        BUS.gold_changed.emit()
        BUS.gold_delta.emit(5000.0)

    def _do_reset_game(self):
        global _RESET_PENDING
        _RESET_PENDING = True
        try:
            if SAVE_FILE.exists():
                SAVE_FILE.unlink()
        except Exception:
            pass
        # Relaunch so the player immediately gets a fresh game
        import subprocess
        subprocess.Popen([sys.executable] + sys.argv)
        QApplication.instance().quit()

    def _add_slider(self, parent_lay, label: str, lo: int, hi: int, val: int, callback):
        row = QHBoxLayout()
        lbl = QLabel(label)
        lbl.setFont(scaled_font(FONT_BODY, 11))
        lbl.setStyleSheet(f"color: {PALETTE['text_primary']}; border: none; background: transparent;")
        lbl.setMinimumWidth(140)
        sl = QSlider(Qt.Horizontal)
        sl.setRange(lo, hi)
        sl.setValue(val)
        sl.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                background: {PALETTE['bg_light']};
                height: 6px; border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: {PALETTE['accent']};
                width: 18px; height: 18px;
                margin: -6px 0; border-radius: 9px;
            }}
            QSlider::sub-page:horizontal {{
                background: {PALETTE['accent']};
                border-radius: 3px;
            }}
        """)
        val_lbl = QLabel(str(val))
        val_lbl.setFixedWidth(36)
        val_lbl.setFont(scaled_font(FONT_MONO, 10))
        val_lbl.setStyleSheet(f"color: {PALETTE['text_muted']}; border: none; background: transparent;")
        sl.valueChanged.connect(lambda v: (callback(v), val_lbl.setText(str(v))))
        row.addWidget(lbl)
        row.addWidget(sl)
        row.addWidget(val_lbl)
        parent_lay.addLayout(row)


# ---------------------------------------------------------------------------
# PARALLAX BACKGROUND
# ---------------------------------------------------------------------------
class ParallaxBackground(QWidget):
    """
    Four-layer parallax background.  Layer 0 (backdrop1.png) is the farthest
    and moves least; layer 3 (backdrop4.png) is the nearest and moves most.

    Driving the parallax:
      • call set_drag(dx, dy) while the user is dragging to nudge the offset
      • call reset_drag()     when the drag ends to spring back to centre
    An ambient sinusoidal drift is always active on top of the drag offset.
    All interpolation happens in a 60 fps tick so the motion is silky smooth.
    """

    # Fraction of the "input offset" applied to each layer (0 = no movement).
    _FACTORS  = [0.0, 0.15, 0.42, 0.85]
    # Max drag input in pixels (clamped before multiplying by factor).
    _MAX_DRAG = 36
    # Extra canvas padding so scaled layers never expose an edge at max offset.
    # Must be >= _MAX_DRAG * max(_FACTORS) = 36 * 0.85 ≈ 31 → use 40 for safety.
    _PAD      = 40

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)

        # Original (un-scaled) pixmaps
        self._pixmaps: list[QPixmap] = []
        for i in range(1, 5):
            px = load_image(f"backdrop{i}.png")
            self._pixmaps.append(px if px is not None else QPixmap())

        # Cache of pixmaps scaled to (w + 2*PAD, h + 2*PAD) — rebuilt on resize
        self._scaled: list[QPixmap] = []

        # Drag-driven target offset (input-space, clamped to ±_MAX_DRAG)
        self._drag_x: float = 0.0
        self._drag_y: float = 0.0
        # Current smoothed offset that chases the target
        self._cur_x: float = 0.0
        self._cur_y: float = 0.0
        # Ambient oscillation phase counter (incremented each tick by ~0.016 s)
        self._t: float = 0.0

        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(16)          # ≈ 60 fps
        self._tick_timer.timeout.connect(self._tick)
        self._tick_timer.start()

    # ------------------------------------------------------------------
    # Public API called by _ParallaxMouseTracker
    # ------------------------------------------------------------------

    def set_drag(self, dx: float, dy: float) -> None:
        """Update the drag-driven target offset (clamped)."""
        m = self._MAX_DRAG
        self._drag_x = max(-m, min(m, dx))
        self._drag_y = max(-m, min(m, dy))

    def reset_drag(self) -> None:
        """Release drag — layers spring back to the ambient centre."""
        self._drag_x = 0.0
        self._drag_y = 0.0

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _tick(self) -> None:
        self._t += 0.016
        # Gentle sinusoidal ambient drift (±4 px on the nearest layer)
        ambient_x = math.sin(self._t * 0.28) * 4.0
        ambient_y = math.cos(self._t * 0.18) * 2.0
        target_x = self._drag_x + ambient_x
        target_y = self._drag_y + ambient_y
        # Ease current offset toward target (lerp factor 0.07 ≈ 45 ms half-life)
        self._cur_x += (target_x - self._cur_x) * 0.07
        self._cur_y += (target_y - self._cur_y) * 0.07
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rebuild_cache()

    def _rebuild_cache(self) -> None:
        w, h = self.width(), self.height()
        if w == 0 or h == 0:
            self._scaled = []
            return
        pad = self._PAD
        tw, th = w + pad * 2, h + pad * 2
        self._scaled = []
        for px in self._pixmaps:
            if px.isNull():
                self._scaled.append(QPixmap())
            else:
                self._scaled.append(
                    px.scaled(tw, th,
                              Qt.KeepAspectRatioByExpanding,
                              Qt.SmoothTransformation)
                )

    def paintEvent(self, event):
        if not self._scaled:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        w, h = self.width(), self.height()
        pad = self._PAD
        # Static vertical nudges per layer (positive = down, negative = up)
        _NUDGE_Y = [0, 0, -260, 0]
        for i, spx in enumerate(self._scaled):
            if spx.isNull():
                continue
            factor = self._FACTORS[i]
            ox = int(self._cur_x * factor)
            oy = int(self._cur_y * factor)
            # Centre the oversized layer and apply the parallax shift + static nudge
            draw_x = (w - spx.width())  // 2 + ox
            draw_y = (h - spx.height()) // 2 + oy + _NUDGE_Y[i]
            p.drawPixmap(draw_x, draw_y, spx)
        # Dark tint over all layers to improve foreground contrast
        p.fillRect(0, 0, w, h, QColor(0, 0, 0, 110))
        p.end()


class _ParallaxMouseTracker(QObject):
    """
    Application-level event filter that drives ParallaxBackground from mouse
    drag gestures anywhere in the window.  Returns False so it never consumes
    events — all normal widget interaction is unaffected.
    """

    def __init__(self, parallax: ParallaxBackground, parent=None):
        super().__init__(parent)
        self._parallax = parallax
        self._origin: Optional[QPoint] = None

    def eventFilter(self, obj, event) -> bool:
        t = event.type()
        if t == QEvent.Type.MouseButtonPress:
            self._origin = event.globalPosition().toPoint()
        elif t == QEvent.Type.MouseMove and self._origin is not None:
            delta = event.globalPosition().toPoint() - self._origin
            self._parallax.set_drag(delta.x() * 0.55, delta.y() * 0.38)
        elif t == QEvent.Type.MouseButtonRelease:
            self._origin = None
            self._parallax.reset_drag()
        return False   # never consume


# ---------------------------------------------------------------------------
# PAGE: GATHER
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# SNOW PARTICLE EFFECT  — background of GatherPage
# ---------------------------------------------------------------------------
class SnowWidget(QWidget):
    """
    Lightweight snow particle overlay. Runs at 25 fps using parallel arrays
    (no per-flake objects). Transparent to mouse events so the gather page
    works normally underneath.
    """
    _COUNT   = 48     # number of snowflakes
    _TICK_MS = 40     # update interval (~25 fps)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        # Load 18 frames from the 9×9-per-frame spritesheet
        raw = load_sprite_sheet("snowflake.png", 9, 9, 18)
        # Pre-scale each frame to three sizes for variety; scale with
        # SmoothTransformation once up-front so paintEvent stays cheap.
        self._frames: list[QPixmap] = []
        sizes = [sz(9), sz(14), sz(18)]
        for px in raw:
            for s in sizes:
                self._frames.append(
                    px.scaled(s, s, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )
        n = self._COUNT
        self._x   = [0.0] * n
        self._y   = [0.0] * n
        self._vy  = [0.0] * n   # fall speed (px/tick)
        self._vx  = [0.0] * n   # horizontal drift (px/tick)
        self._fi  = [0]   * n   # frame index into self._frames
        self._op  = [1.0] * n   # opacity 0.0-1.0

        self._timer = QTimer(self)
        self._timer.setInterval(self._TICK_MS)
        self._timer.timeout.connect(self._tick)

    # ------------------------------------------------------------------
    def _init_flake(self, i: int, full_height: bool = False) -> None:
        w = max(self.width(), 200)
        h = max(self.height(), 400)
        self._x[i]  = random.uniform(0, w)
        self._y[i]  = random.uniform(0, h) if full_height else random.uniform(-20, 0)
        self._vy[i] = random.uniform(0.6, 2.2)
        self._vx[i] = random.uniform(-0.4, 0.4)
        self._fi[i] = random.randrange(len(self._frames)) if self._frames else 0
        self._op[i] = random.uniform(0.35, 0.75)

    def showEvent(self, event):
        for i in range(self._COUNT):
            self._init_flake(i, full_height=True)
        self._timer.start()

    def hideEvent(self, event):
        self._timer.stop()

    # ------------------------------------------------------------------
    def _tick(self) -> None:
        w = self.width()
        h = self.height()
        if w == 0 or h == 0:
            return
        for i in range(self._COUNT):
            self._y[i] += self._vy[i]
            self._x[i] += self._vx[i]
            if self._y[i] > h + 20 or self._x[i] < -20 or self._x[i] > w + 20:
                self._init_flake(i)
        self.update()

    # ------------------------------------------------------------------
    def paintEvent(self, event) -> None:
        if not self._frames:
            return
        p = QPainter(self)
        for i in range(self._COUNT):
            fr = self._frames[self._fi[i]]
            p.setOpacity(self._op[i])
            p.drawPixmap(
                int(self._x[i]) - fr.width() // 2,
                int(self._y[i]) - fr.height() // 2,
                fr,
            )
        p.setOpacity(1.0)
        p.end()


class GatherPage(QWidget):
    def __init__(self, state: GameState, parent=None):
        super().__init__(parent)
        self._state = state
        self._strike_frames = load_sprite_sheet("strike.png", STRIKE_W, STRIKE_H, STRIKE_FRAMES)
        self._building_ui()

    def _building_ui(self):
        self.setStyleSheet("background: transparent;")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Snow background — kept here for resizeEvent; actual rendering done
        # by _snow_overlay in MainWindow which paints above all page content.
        self._snow = SnowWidget(self)
        self._snow.hide()  # hidden; MainWindow's overlay handles display

        title = QLabel("Resource Nodes")
        title.setFont(scaled_font(FONT_TITLE, 15, bold=True))
        title.setStyleSheet(f"color: {PALETTE['text_primary']}; padding: 16px 20px 8px; background: transparent; border: none;")
        root.addWidget(title)

        # Harvest Spirit timer bar (hidden until spirit is active)
        self._spirit_timer = HarvestSpiritTimer(self._state, self)
        hlay = QHBoxLayout()
        hlay.setContentsMargins(16, 0, 16, 4)
        hlay.addWidget(self._spirit_timer)
        root.addLayout(hlay)

        self._swipe = SwipeContainer(cols=3, parent=self)
        root.addWidget(self._swipe, stretch=1)

        self._node_cards: dict[str, "_NodeCard"] = {}
        self._refresh_nodes()

        BUS.inventory_changed.connect(self._refresh_gold_hint)
        BUS.xp_changed.connect(lambda *_: self.refresh())
        BUS.spirit_changed.connect(lambda rem: self.refresh())
        BUS.prestige_changed.connect(self.refresh)

    def _refresh_nodes(self):
        self._swipe.clear_items()
        self._node_cards.clear()
        # Add cards in grid row-major order so the 3x3 layout is correct
        for row in RESOURCE_NODE_GRID:
            for node_id in row:
                node_def = RESOURCE_NODES[node_id]
                card = _NodeCard(node_id, node_def, self._state, self._strike_frames, self)
                self._swipe.add_item(card)
                self._node_cards[node_id] = card

    def _refresh_gold_hint(self):
        pass  # future: highlight unlockable nodes

    def refresh(self):
        if not self.isVisible():
            return
        for card in self._node_cards.values():
            card.refresh()


# ---------------------------------------------------------------------------
# LOCK OVERLAY  — full-card blocked-content widget
# ---------------------------------------------------------------------------
class _LockOverlay(QWidget):
    """
    Translucent overlay placed on top of a card widget when content is locked
    behind a prestige tier or tool tier requirement.  Because it covers the
    entire parent, it absorbs all mouse events so locked content is not
    interactive.
    """
    def __init__(self, message: str, color: str = None, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: rgba(13, 15, 20, 218); border-radius: 0px;")
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(16)
        lay.setContentsMargins(24, 24, 24, 24)

        lock_lbl = QLabel()
        lock_px = load_image("locked.png")
        if lock_px:
            lock_lbl.setPixmap(lock_px.scaled(sz(200), sz(200), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            lock_lbl.setText("🔒")
            lock_lbl.setFont(scaled_font(FONT_BODY, 48))
        lock_lbl.setAlignment(Qt.AlignCenter)
        lock_lbl.setStyleSheet("background: transparent; border: none;")
        make_shadow(lock_lbl, blur=90, color="#000000", opacity=255, offset=(0, 8))
        lay.addWidget(lock_lbl)

        msg_lbl = QLabel(message)
        msg_lbl.setFont(scaled_font(FONT_TITLE, 38, bold=True))
        msg_lbl.setAlignment(Qt.AlignCenter)
        msg_lbl.setWordWrap(True)
        msg_lbl.setStyleSheet(
            f"color: {color or PALETTE['prestige']}; background: rgba(0,0,0,180); border-radius: 12px; padding: 8px 18px; border: none;"
        )
        make_shadow(msg_lbl, blur=70, color="#000000", opacity=255, offset=(0, 4))
        lay.addWidget(msg_lbl)


# ---------------------------------------------------------------------------
# BOUNCING SPRITE  — timer-driven, layout-invisible bounce animation
# ---------------------------------------------------------------------------
class _BouncingSprite(QWidget):
    """
    Draws a sprite pixmap with a vertical offset in paintEvent.
    The widget geometry never changes, so the layout manager is never involved
    and refresh() calls on the parent card cannot interfere with the animation.

    Animation is elapsed-time-based: bounce() records perf_counter() and the
    offset is computed by sampling a normalised curve at the current time
    position.  This runs at the correct speed regardless of OS timer resolution
    (Windows coarsens QTimer intervals to ~15.6 ms by default).
    """
    # Normalised (0‥1) y-offset curve sampled at t=0..1 over _BOUNCE_MS
    _CURVE: list[float] = [0.0, -1.0, -0.88, -0.60, -0.28, 0.12, 0.06, -0.01, 0.0]
    _MAX_PX: int  = 14      # peak pixel displacement
    _BOUNCE_MS: float = 110  # total animation duration in ms
    _POLL_MS: int = 8        # timer poll interval (faster than one OS tick)

    def __init__(self, w: int, h: int, parent=None):
        super().__init__(parent)
        self.setFixedSize(w, h)
        self.setAttribute(Qt.WA_OpaquePaintEvent, False)
        self._pixmap: Optional[QPixmap] = None
        self._offset_y: int = 0
        self._bounce_start: float = -1.0  # negative = idle

        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.setInterval(self._POLL_MS)
        self._timer.setSingleShot(False)
        self._timer.timeout.connect(self._tick)

    def set_pixmap(self, px: QPixmap) -> None:
        self._pixmap = px
        self.update()

    def bounce(self) -> None:
        """Start (or immediately restart) the bounce animation."""
        self._bounce_start = time.perf_counter()
        if not self._timer.isActive():
            self._timer.start()
        self.update()

    def _tick(self) -> None:
        if self._bounce_start < 0:
            self._timer.stop()
            return
        elapsed_ms = (time.perf_counter() - self._bounce_start) * 1000.0
        if elapsed_ms >= self._BOUNCE_MS:
            self._offset_y = 0
            self._bounce_start = -1.0
            self._timer.stop()
        else:
            t = elapsed_ms / self._BOUNCE_MS           # 0..1
            n = len(self._CURVE) - 1
            fi = t * n
            i = min(int(fi), n - 1)
            frac = fi - i
            v = self._CURVE[i] * (1.0 - frac) + self._CURVE[i + 1] * frac
            self._offset_y = int(v * self._MAX_PX)
        self.update()

    def paintEvent(self, event) -> None:
        if not self._pixmap:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        x = (self.width()  - self._pixmap.width())  // 2
        y = (self.height() - self._pixmap.height()) // 2 + self._offset_y
        # Soft circular shadow beneath the sprite
        cx = self.width() // 2
        cy = y + self._pixmap.height() - 10
        rx, ry = int(self._pixmap.width() * 0.45), int(self._pixmap.height() * 0.12)
        shadow_grad = QRadialGradient(cx, cy, rx)
        shadow_grad.setColorAt(0.0, QColor(0, 0, 0, 80))
        shadow_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setBrush(shadow_grad)
        p.setPen(Qt.NoPen)
        p.drawEllipse(cx - rx, cy - ry, rx * 2, ry * 2)
        p.drawPixmap(x, y, self._pixmap)


class _NodeCard(QWidget):
    _MAX_PENDING_FX = 3

    def __init__(self, node_id: str, node_def: dict, state: GameState,
                 strike_frames: list, parent=None):
        super().__init__(parent)
        self._node_id = node_id
        self._node_def = node_def
        self._state = state
        self._strike_frames = strike_frames
        # Prestige-gated nodes bypass the unlock-click mechanic; the _LockOverlay handles visual blocking.
        _prestige_req = node_def.get("prestige_req", 0)
        _unlock_cost = node_def.get("unlock_cost", 0)
        _skill_req = node_def.get("skill_req")
        if _prestige_req > 0 or (_unlock_cost == 0 and not _skill_req):
            # Free node or prestige-only-gated — never needs the unlock button
            self._locked = False
        else:
            self._locked = node_id not in state.unlocked_nodes
        self._pending_fx_count: int = 0
        self._pending_sound: Optional[str] = None
        self._pending_inventory_emit = False
        self._pending_refresh = False
        self._pending_xp_skill: Optional[str] = None
        self._pending_xp_value: int = 0
        self._pending_level_up: Optional[tuple[str, int]] = None
        self._pending_float_xp: int = 0
        self._pending_float_color: Optional[str] = None
        self._pending_feedback: Optional[tuple[str, str]] = None
        self._pending_special_feedback: Optional[str] = None
        self._pending_shard_delta: int = 0
        self._flush_timer = QTimer(self)
        self._flush_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._flush_timer.setSingleShot(False)
        self._flush_timer.setInterval(33)
        self._flush_timer.timeout.connect(self._flush_pending_ui)
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setAlignment(Qt.AlignCenter)
        root.setSpacing(20)
        root.setContentsMargins(30, 30, 30, 30)

        # Node sprite — custom bouncing widget (layout geometry never changes)
        sprite_px = load_image(self._node_def["sprite"])
        self._bounce_sprite = _BouncingSprite(sz(499), sz(499))
        if sprite_px:
            self._bounce_sprite.set_pixmap(
                sprite_px.scaled(sz(437), sz(437), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        else:
            self._bounce_sprite.set_pixmap(make_placeholder(sz(437), sz(437), self._node_def["name"]))

        # Strike overlay — child of the bouncing sprite so it moves with it
        strike_w = STRIKE_W * 3
        strike_h = STRIKE_H * 3
        self._strike = SpriteWidget(self._strike_frames, STRIKE_DELAY, loop=False,
                                    parent=self._bounce_sprite)
        self._strike.setFixedSize(strike_w, strike_h)
        self._strike.move(self._bounce_sprite.width()  // 2 - strike_w // 2,
                          self._bounce_sprite.height() // 2 - strike_h // 2)
        self._strike.hide()
        self._strike.animation_done.connect(self._strike.hide)

        root.addWidget(self._bounce_sprite, alignment=Qt.AlignCenter)

        # Name
        name_lbl = QLabel(self._node_def["name"])
        name_lbl.setFont(scaled_font(FONT_TITLE, 20, bold=True))
        name_lbl.setAlignment(Qt.AlignCenter)
        name_lbl.setStyleSheet(f"color: {PALETTE['text_primary']}; background: transparent; border: none;")
        _shadow_name = QGraphicsDropShadowEffect(name_lbl)
        _shadow_name.setBlurRadius(18); _shadow_name.setOffset(0, 2); _shadow_name.setColor(QColor(0, 0, 0, 255))
        name_lbl.setGraphicsEffect(_shadow_name)
        root.addWidget(name_lbl)

        # Skill XP bar
        self._skill_id = self._node_def.get("xp_skill", "")
        if self._skill_id in SKILLS:
            _scolor = SKILLS[self._skill_id]["color"]
            self._xp_hdr = QLabel()
            self._xp_hdr.setFont(scaled_font(FONT_MONO, 9))
            self._xp_hdr.setAlignment(Qt.AlignCenter)
            self._xp_hdr.setStyleSheet(
                f"color: {_scolor}; background: transparent; border: none;"
            )
            _shadow_xp = QGraphicsDropShadowEffect(self._xp_hdr)
            _shadow_xp.setBlurRadius(16); _shadow_xp.setOffset(0, 1); _shadow_xp.setColor(QColor(0, 0, 0, 240))
            self._xp_hdr.setGraphicsEffect(_shadow_xp)
            self._xp_bar_node = QProgressBar()
            self._xp_bar_node.setRange(0, 100)
            self._xp_bar_node.setValue(0)
            self._xp_bar_node.setTextVisible(False)
            self._xp_bar_node.setFixedHeight(6)
            self._xp_bar_node.setStyleSheet(f"""
                QProgressBar {{ background: {PALETTE['bg_light']}; border: none; border-radius: 3px; }}
                QProgressBar::chunk {{ background: {_scolor}; border-radius: 3px; }}
            """)
            _xp_wrap = QWidget()
            _xp_wrap.setStyleSheet("background: rgba(0,0,0,135); border-radius: 10px;")
            _xp_wlay = QVBoxLayout(_xp_wrap)
            _xp_wlay.setContentsMargins(14, 8, 14, 8)
            _xp_wlay.setSpacing(4)
            _xp_wlay.addWidget(self._xp_hdr)
            _xp_wlay.addWidget(self._xp_bar_node)
            root.addWidget(_xp_wrap)

        # Yields info
        yields_id = self._node_def["yields"]
        yields_name = RESOURCES[yields_id]["name"]
        self._chance_lbl = QLabel()
        self._chance_lbl.setAlignment(Qt.AlignCenter)
        self._chance_lbl.setFont(scaled_font(FONT_BODY, 13))
        self._chance_lbl.setStyleSheet(f"color: {PALETTE['text_primary']}; background: rgba(0,0,0,130); border-radius: 10px; padding: 5px 14px; border: none;")
        _shadow_chance = QGraphicsDropShadowEffect(self._chance_lbl)
        _shadow_chance.setBlurRadius(18); _shadow_chance.setOffset(0, 1); _shadow_chance.setColor(QColor(0, 0, 0, 240))
        self._chance_lbl.setGraphicsEffect(_shadow_chance)
        root.addWidget(self._chance_lbl)

        # Count
        self._count_lbl = QLabel()
        self._count_lbl.setAlignment(Qt.AlignCenter)
        self._count_lbl.setFont(scaled_font(FONT_MONO, 26, bold=True))
        self._count_lbl.setStyleSheet(f"color: {PALETTE['accent2']}; background: transparent; border: none;")
        _shadow_count = QGraphicsDropShadowEffect(self._count_lbl)
        _shadow_count.setBlurRadius(8); _shadow_count.setOffset(0, 1); _shadow_count.setColor(QColor(0, 0, 0, 180))
        self._count_lbl.setGraphicsEffect(_shadow_count)
        root.addWidget(self._count_lbl)

        # Feedback label
        self._feedback = QLabel("")
        self._feedback.setAlignment(Qt.AlignCenter)
        self._feedback.setFont(scaled_font(FONT_BODY, 13, bold=True))
        self._feedback.setStyleSheet(f"color: {PALETTE['success']}; background: transparent; border: none;")
        self._feedback.setFixedHeight(30)
        root.addWidget(self._feedback)
        # Single reusable timer — restarting it cancels any pending clear
        self._feedback_timer = QTimer(self)
        self._feedback_timer.setSingleShot(True)
        self._feedback_timer.timeout.connect(lambda: self._feedback.setText(""))

        # Action button
        if self._locked:
            skill_req = self._node_def.get("skill_req")
            unlock_cost = self._node_def["unlock_cost"]
            if skill_req:
                req_skill_id, req_lvl = skill_req
                skill_name = SKILLS[req_skill_id]["name"]
                btn_text = f"🔒 {skill_name} Lv {req_lvl}"
            elif unlock_cost > 0:
                btn_text = f"🔒 Unlock — {unlock_cost}G"
            else:
                btn_text = "🔒 Locked"
            self._action_btn = QPushButton(btn_text)
            self._action_btn.clicked.connect(self._try_unlock)
        else:
            self._action_btn = QPushButton(f"Strike {self._node_def['name']}")
            self._action_btn.clicked.connect(self._on_strike)

        self._action_btn.setFont(scaled_font(FONT_BODY, 14, bold=True))
        self._action_btn.setFixedHeight(sz(88))
        self._action_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._style_btn()
        self._btn_shadow = QGraphicsDropShadowEffect(self._action_btn)
        self._btn_shadow.setBlurRadius(16)
        self._btn_shadow.setColor(QColor(0, 0, 0, 100))
        self._btn_shadow.setOffset(0, 4)
        self._action_btn.setGraphicsEffect(self._btn_shadow)
        root.addWidget(self._action_btn)

        # Prestige lock overlay — covers card when prestige_req > current tier
        prestige_req = self._node_def.get("prestige_req", 0)
        if prestige_req > 0:
            self._prestige_overlay = _LockOverlay(
                f"Requires Prestige {prestige_req}",
                PALETTE["prestige"],
                self,
            )
        else:
            self._prestige_overlay = None

        self.refresh()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._prestige_overlay is not None:
            self._prestige_overlay.setGeometry(0, 0, self.width(), self.height())
            if self._prestige_overlay.isVisible():
                self._prestige_overlay.raise_()

    def _update_prestige_lock(self):
        if self._prestige_overlay is None:
            return
        locked = self._node_def.get("prestige_req", 0) > self._state.prestige_tier
        self._prestige_overlay.setVisible(locked)
        if locked:
            self._prestige_overlay.setGeometry(0, 0, self.width(), self.height())
            self._prestige_overlay.raise_()

    def _style_btn(self):
        if self._locked:
            col = PALETTE["text_dim"]
            bg = PALETTE["bg_light"]
            pressed = PALETTE["bg_card"]
        else:
            col = "#E8F4FF"
            bg = "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #5A9EE0, stop:0.55 #2E6ABE, stop:1 #1A4A96)"
            pressed = "#0E3272"
        self._action_btn.setStyleSheet(f"""
            QPushButton {{
                background: {bg};
                color: {col};
                border: 1px solid {'#6AAEDD' if not self._locked else PALETTE['border']};
                border-radius: 14px;
                font-family: '{FONT_BODY}';
                font-size: {int(14 * APP_SCALE)}pt;
                font-weight: bold;
                letter-spacing: 1px;
            }}
            QPushButton:pressed {{
                background: {pressed};
            }}
        """)

    def refresh(self):
        self._update_prestige_lock()
        yields_id = self._node_def["yields"]
        yields_name = RESOURCES[yields_id]["name"]
        chance = self._state.get_effective_chance(self._node_id)
        crit = self._state.get_crit_chance(self._node_id)
        special = self._state.get_special_item_chance(self._node_id)
        spirit_rem = self._state.spirit_remaining()
        spirit_str = f"  🌿 {spirit_rem:.0f}s" if spirit_rem > 0 else ""
        self._chance_lbl.setText(
            f"Yields: {yields_name}  •  {int(chance*100)}% chance  •  ⚡{int(crit*100)}% crit  •  ✨{special*100:.1f}% special{spirit_str}"
        )
        count = self._state.inventory.get(yields_id, 0)
        self._count_lbl.setText(f"{count:,}")
        # Update lock button text to reflect current skill progress
        if self._locked:
            skill_req = self._node_def.get("skill_req")
            unlock_cost = self._node_def["unlock_cost"]
            if skill_req:
                req_skill_id, req_lvl = skill_req
                cur_lvl = self._state.skills.get(req_skill_id, SkillState()).level
                skill_name = SKILLS[req_skill_id]["name"]
                if cur_lvl >= req_lvl:
                    if unlock_cost > 0:
                        self._action_btn.setText(f"\U0001f512 Unlock \u2014 {unlock_cost}\U0001fa99")
                    else:
                        self._action_btn.setText(f"Unlock {self._node_def['name']}")
                else:
                    self._action_btn.setText(f"\U0001f512 {skill_name} Lv {req_lvl} ({cur_lvl}/{req_lvl})")
        # XP bar update
        if hasattr(self, "_xp_bar_node") and self._skill_id in SKILLS:
            sk = self._state.skills.get(self._skill_id, SkillState())
            pct = int(sk.xp_in_level / max(sk.xp_needed_for_level, 1) * 100)
            self._xp_bar_node.setValue(pct)
            icon = SKILLS[self._skill_id]["icon"]
            if sk.level >= 100:
                self._xp_hdr.setText(f"{icon} {SKILLS[self._skill_id]['name']}  —  Lv MAX")
            else:
                self._xp_hdr.setText(
                    f"{icon} {SKILLS[self._skill_id]['name']}  •  Lv {sk.level}"
                    f"  •  {sk.xp_in_level:,}/{sk.xp_needed_for_level:,} XP"
                )
        # Gather button tooltip + spirit glow (updated every refresh)
        if not self._locked:
            gather_amt = self._state.get_effective_gather_amount(self._node_id)
            self._action_btn.setToolTip(
                f"Success: {int(chance*100)}%  •  Gather: +{gather_amt}  •  Crit: {int(crit*100)}%  •  Special: {special*100:.1f}%"
            )
            if spirit_rem > 0:
                self._btn_shadow.setBlurRadius(22)
                _sc = QColor(PALETTE["success"])
                _sc.setAlpha(200)
                self._btn_shadow.setColor(_sc)
                self._btn_shadow.setOffset(0, 0)
            else:
                self._btn_shadow.setBlurRadius(16)
                self._btn_shadow.setColor(QColor(0, 0, 0, 100))
                self._btn_shadow.setOffset(0, 4)

    def _on_strike(self):
        if self._locked:
            return
        if self._prestige_overlay is not None and self._prestige_overlay.isVisible():
            return
        node_def = self._node_def
        sound = "chop" if self._node_id == "tree" else "mine"
        self._pending_sound = sound
        self._pending_fx_count = min(self._pending_fx_count + 1, self._MAX_PENDING_FX)

        chance = self._state.get_effective_chance(self._node_id)
        success = random.random() < chance
        if success:
            yields_id = node_def["yields"]
            amount = self._state.get_effective_gather_amount(self._node_id)
            # Critical hit?
            crit = random.random() < self._state.get_crit_chance(self._node_id)
            if crit:
                amount = max(1, int(round(amount * self._state.get_crit_multiplier())))
            self._state.inventory[yields_id] = self._state.inventory.get(yields_id, 0) + amount
            skill = node_def.get("xp_skill") or RESOURCES[yields_id]["xp_skill"]
            xp = node_def.get("xp_per_hit", 4) * amount
            eff_xp, leveled = self._state.add_xp(skill, xp)
            self._pending_inventory_emit = True
            self._pending_xp_skill = skill
            self._pending_xp_value = self._state.skills[skill].xp
            skill_color = SKILLS.get(skill, {}).get("color", PALETTE["accent"])
            if self._pending_float_color not in (None, skill_color):
                self._pending_float_xp = 0
            self._pending_float_color = skill_color
            self._pending_float_xp += eff_xp
            if leveled:
                self._pending_level_up = (skill, self._state.skills[skill].level)
            res_name = RESOURCES[yields_id]["name"]
            if crit:
                self._pending_feedback = (f"⚡ CRIT! +{amount} {res_name}", PALETTE["gold"])
            else:
                self._pending_feedback = (f"+{amount} {res_name}", PALETTE["success"])

            # Special item drop?
            special = self._state.roll_special_item(self._node_id)
            if special:
                self._state.special_items[special] = self._state.special_items.get(special, 0) + 1
                sname = SPECIAL_ITEMS[special]["name"]
                self._pending_inventory_emit = True
                if special == "runicShard":
                    self._pending_shard_delta += 1
                self._pending_special_feedback = sname
        else:
            self._pending_feedback = ("Miss!", PALETTE["text_muted"])

        BUS.node_hit.emit(self._node_id, success)
        self._pending_refresh = True
        self._schedule_flush()

    def _schedule_flush(self):
        if not self._flush_timer.isActive():
            self._flush_timer.start()

    def _has_pending_work(self) -> bool:
        return any([
            self._pending_fx_count > 0,
            self._pending_sound is not None,
            self._pending_inventory_emit,
            self._pending_refresh,
            self._pending_xp_skill is not None,
            self._pending_level_up is not None,
            self._pending_float_xp > 0,
            self._pending_feedback is not None,
            self._pending_special_feedback is not None,
            self._pending_shard_delta > 0,
        ])

    def _flush_pending_ui(self):
        if self._pending_sound:
            AUDIO.play(self._pending_sound)
            self._pending_sound = None

        if self._pending_fx_count > 0:
            self._bounce_sprite.bounce()
            if self._strike_frames:
                self._strike.show()
                self._strike.play(loop=False)
            self._pending_fx_count -= 1

        if self._pending_inventory_emit:
            BUS.inventory_changed.emit()
            self._pending_inventory_emit = False

        if self._pending_xp_skill is not None:
            BUS.xp_changed.emit(self._pending_xp_skill, self._pending_xp_value)
            self._pending_xp_skill = None
            self._pending_xp_value = 0

        if self._pending_shard_delta:
            BUS.shard_delta.emit(self._pending_shard_delta)
            self._pending_shard_delta = 0

        if self._pending_float_xp > 0 and self._pending_float_color is not None:
            self._spawn_float(f"+{self._pending_float_xp} XP", self._pending_float_color)
            self._pending_float_xp = 0
            self._pending_float_color = None

        if self._pending_feedback:
            text, color = self._pending_feedback
            self._show_feedback(text, color)
            self._pending_feedback = None

        if self._pending_special_feedback:
            sname = self._pending_special_feedback
            QTimer.singleShot(600, lambda s=sname: self._show_feedback(f"✨ {s}!", PALETTE["accent"]))
            self._pending_special_feedback = None

        if self._pending_level_up:
            skill_id, level = self._pending_level_up
            BUS.level_up.emit(skill_id, level)
            self._pending_level_up = None

        if self._pending_refresh:
            self.refresh()
            self._pending_refresh = False

        if not self._has_pending_work():
            self._flush_timer.stop()

    def _spawn_float(self, text: str, color: str):
        """Spawn a floating text notification centered over this card."""
        win = self.window()
        pt = self.mapTo(win, self.rect().center())
        spawn_floating_text(text, color, win, cx=pt.x(), cy=pt.y())

    def _try_unlock(self):
        skill_req = self._node_def.get("skill_req")
        if skill_req:
            req_skill_id, req_lvl = skill_req
            cur_lvl = self._state.skills.get(req_skill_id, SkillState()).level
            if cur_lvl < req_lvl:
                skill_name = SKILLS[req_skill_id]["name"]
                self._show_feedback(f"Need {skill_name} Lv {req_lvl}", PALETTE["danger"])
                return
        cost = self._node_def["unlock_cost"]
        if cost > 0 and self._state.gold < cost:
            self._show_feedback(f"Need {cost}G", PALETTE["danger"])
            return
        self._state.gold -= cost
        self._state.unlocked_nodes.append(self._node_id)
        self._locked = False
        self._action_btn.setText(f"Strike {self._node_def['name']}")
        self._action_btn.clicked.disconnect()
        self._action_btn.clicked.connect(self._on_strike)
        self._style_btn()
        BUS.gold_changed.emit()
        if cost > 0:
            BUS.gold_delta.emit(-float(cost))
        self.refresh()

    def _show_feedback(self, text: str, color: str):
        self._feedback.setText(text)
        self._feedback.setStyleSheet(f"color: {color}; background: transparent; border: none; font-size: {int(13 * APP_SCALE)}pt; font-weight: bold;")
        # Restart the timer — this cancels any previously scheduled clear
        self._feedback_timer.start(1000)


# ---------------------------------------------------------------------------
# PAGE: REFINE
# ---------------------------------------------------------------------------
class RefinePage(QWidget):
    def __init__(self, state: GameState, parent=None):
        super().__init__(parent)
        self._state = state
        self.setStyleSheet("background: transparent;")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        title = QLabel("Refining Stations")
        title.setFont(scaled_font(FONT_TITLE, 15, bold=True))
        title.setStyleSheet(f"color: {PALETTE['text_primary']}; padding: 16px 20px 8px; background: transparent; border: none;")
        root.addWidget(title)

        self._swipe = SwipeContainer(parent=self)
        root.addWidget(self._swipe, stretch=1)

        for station_id, station_def in REFINING_STATIONS.items():
            card = _StationCard(station_id, station_def, state, self)
            self._swipe.add_item(card)

    def refresh(self):
        for i in range(self._swipe._layout.count()):
            w = self._swipe._layout.widget(i)
            if isinstance(w, _StationCard):
                w.refresh()

    def cancel_all_refining(self):
        for i in range(self._swipe._layout.count()):
            w = self._swipe._layout.widget(i)
            if isinstance(w, _StationCard):
                w.cancel_refining()


class _StationCard(QWidget):
    def __init__(self, station_id: str, station_def: dict, state: GameState, parent=None):
        super().__init__(parent)
        self._station_id = station_id
        self._station_def = station_def
        self._state = state
        self._refining = False
        self._refine_timer: Optional[QTimer] = None
        self._refine_start = 0.0
        self._refine_duration = 0.0
        self._refine_amount = 0
        self._refine_produced = 0
        self._selected_mat: str = ""   # label of currently selected recipe
        self._mat_btns: dict = {}      # label -> QPushButton
        self._active_recipe: Optional[dict] = None  # recipe in progress (for _finish_refine)
        self._setup_ui()

    # ------------------------------------------------------------------
    # Material selection helpers
    # ------------------------------------------------------------------
    def _current_recipe(self) -> dict:
        """Return the recipe dict that is currently selected."""
        recipes = self._station_def.get("recipes")
        if not recipes:
            return self._station_def["recipe"]
        unlocked = [r for r in recipes if r.get("prestige_req", 0) <= self._state.prestige_tier]
        if not unlocked:
            return recipes[0]
        for r in unlocked:
            if r["label"] == self._selected_mat:
                return r
        # Fall back to first unlocked if selected material not available
        self._selected_mat = unlocked[0]["label"]
        return unlocked[0]

    def _select_material(self, label: str):
        if self._refining:
            return
        self._selected_mat = label
        self._refresh_material_selector()
        self._refresh_recipe_display()

    def _refresh_material_selector(self):
        """Show/style material buttons based on current prestige unlock state."""
        recipes = self._station_def.get("recipes")
        if not recipes or not self._mat_btns:
            return
        unlocked_labels = {r["label"] for r in recipes if r.get("prestige_req", 0) <= self._state.prestige_tier}
        if self._selected_mat not in unlocked_labels:
            first = next((r["label"] for r in recipes if r.get("prestige_req", 0) <= self._state.prestige_tier), "")
            self._selected_mat = first
        for label, btn in self._mat_btns.items():
            if label in unlocked_labels:
                btn.show()
                active = (label == self._selected_mat)
                if active:
                    btn.setStyleSheet(f"""
                        QPushButton {{
                            background: {PALETTE['accent']};
                            color: {PALETTE['bg_dark']};
                            border: none;
                            border-radius: 14px;
                            font-weight: bold;
                        }}
                    """)
                else:
                    btn.setStyleSheet(f"""
                        QPushButton {{
                            background: {PALETTE['bg_light']};
                            color: {PALETTE['text_primary']};
                            border: 1px solid {PALETTE['border']};
                            border-radius: 14px;
                        }}
                        QPushButton:pressed {{ background: {PALETTE['bg_card']}; }}
                    """)
            else:
                btn.hide()
        self._refresh_recipe_display()

    def _refresh_recipe_display(self):
        """Update recipe info labels when selection changes."""
        if not hasattr(self, "_recipe_lbl"):
            return
        recipe = self._current_recipe()
        in_name = RESOURCES[recipe["input"]]["name"]
        out_name = RESOURCES[recipe["output"]]["name"]
        self._recipe_lbl.setText(f"{recipe['ratio']} {in_name}  →  1 {out_name}")
        self._make_lbl.setText(f"Make {out_name}:")
        self._update_needs()
        inv = self._state.inventory.get(recipe["input"], 0)
        self._inventory_lbl.setText(f"Have: {inv:,} {in_name}")

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        root.setSpacing(16)
        root.setContentsMargins(24, 24, 24, 24)

        # Sprite
        frames_n = self._station_def["frames"]
        fw = self._station_def["frame_w"]
        fh = self._station_def["frame_h"]
        fd = self._station_def["frame_delay"]
        frames = load_sprite_sheet(self._station_def["sprite"], fw, fh, frames_n) if frames_n > 1 else []

        if frames:
            self._sprite = SpriteWidget(frames, fd, loop=True, parent=self)
            scaled_frames = [f.scaled(sz(240), sz(240), Qt.KeepAspectRatio, Qt.SmoothTransformation) for f in frames]
            self._sprite.set_frames(scaled_frames, fd)
        else:
            self._sprite = QLabel()
            self._sprite.setFixedSize(sz(240), sz(240))
            px = load_image(self._station_def["sprite"])
            if px:
                self._sprite.setPixmap(px.scaled(sz(240), sz(240), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                ph = make_placeholder(sz(240), sz(240), self._station_def["name"])
                self._sprite.setPixmap(ph)
            self._sprite.setAlignment(Qt.AlignCenter)

        root.addWidget(self._sprite, alignment=Qt.AlignCenter)

        name_lbl = QLabel(self._station_def["name"])
        name_lbl.setFont(scaled_font(FONT_TITLE, 19, bold=True))
        name_lbl.setAlignment(Qt.AlignCenter)
        name_lbl.setStyleSheet(f"color: {PALETTE['text_primary']}; background: transparent; border: none;")
        _shadow_name = QGraphicsDropShadowEffect(name_lbl)
        _shadow_name.setBlurRadius(18); _shadow_name.setOffset(0, 2); _shadow_name.setColor(QColor(0, 0, 0, 255))
        name_lbl.setGraphicsEffect(_shadow_name)
        root.addWidget(name_lbl)

        # Material selector — pill buttons, one per recipe, hidden until prestige unlocks
        _recipes = self._station_def.get("recipes", [])
        if len(_recipes) > 1:
            # Initialise selected_mat to first recipe label
            if not self._selected_mat:
                self._selected_mat = _recipes[0]["label"]
            _mat_container = QWidget()
            _mat_container.setStyleSheet("background: transparent;")
            _mat_lay = QHBoxLayout(_mat_container)
            _mat_lay.setContentsMargins(0, 0, 0, 0)
            _mat_lay.setSpacing(sz(10))
            _mat_lay.setAlignment(Qt.AlignCenter)
            for _r in _recipes:
                _lbl = _r["label"]
                _btn = QPushButton(_lbl)
                _btn.setFont(scaled_font(FONT_BODY, 13, bold=True))
                _btn.setFixedHeight(sz(64))
                _btn.setMinimumWidth(sz(90))
                _btn.setCursor(QCursor(Qt.PointingHandCursor))
                _btn.clicked.connect(lambda _chk=False, _l=_lbl: self._select_material(_l))
                self._mat_btns[_lbl] = _btn
                _mat_lay.addWidget(_btn)
            root.addWidget(_mat_container)
            # Apply initial styles after buttons are registered
            self._refresh_material_selector()

        # Resolve starting recipe (after selector initialised)
        recipe = self._current_recipe()
        in_name = RESOURCES[recipe["input"]]["name"]
        out_name = RESOURCES[recipe["output"]]["name"]

        # Dark info pill wrapping recipe summary labels
        _info_wrap = QWidget()
        _info_wrap.setStyleSheet("background: rgba(0,0,0,130); border-radius: 12px;")
        _info_wlay = QVBoxLayout(_info_wrap)
        _info_wlay.setContentsMargins(18, 10, 18, 10)
        _info_wlay.setSpacing(4)

        self._recipe_lbl = QLabel(f"{recipe['ratio']} {in_name}  →  1 {out_name}")
        self._recipe_lbl.setAlignment(Qt.AlignCenter)
        self._recipe_lbl.setFont(scaled_font(FONT_BODY, 12))
        self._recipe_lbl.setStyleSheet(f"color: {PALETTE['accent2']}; background: transparent; border: none;")
        _shadow_recipe = QGraphicsDropShadowEffect(self._recipe_lbl)
        _shadow_recipe.setBlurRadius(12); _shadow_recipe.setOffset(0, 1); _shadow_recipe.setColor(QColor(0, 0, 0, 220))
        self._recipe_lbl.setGraphicsEffect(_shadow_recipe)
        _info_wlay.addWidget(self._recipe_lbl)

        self._make_lbl = QLabel(f"Make {out_name}:")
        self._make_lbl.setFont(scaled_font(FONT_BODY, 12, bold=True))
        self._make_lbl.setAlignment(Qt.AlignCenter)
        self._make_lbl.setStyleSheet(f"color: {PALETTE['text_primary']}; background: transparent; border: none;")
        _shadow_make = QGraphicsDropShadowEffect(self._make_lbl)
        _shadow_make.setBlurRadius(12); _shadow_make.setOffset(0, 1); _shadow_make.setColor(QColor(0, 0, 0, 200))
        self._make_lbl.setGraphicsEffect(_shadow_make)
        _info_wlay.addWidget(self._make_lbl)
        root.addWidget(_info_wrap)

        def _picker_btn(text: str, w: int = sz(68)) -> QPushButton:
            b = QPushButton(text)
            b.setFont(scaled_font(FONT_BODY, 18, bold=True))
            b.setFixedSize(w, sz(68))
            b.setCursor(QCursor(Qt.PointingHandCursor))
            b.setStyleSheet(f"""
                QPushButton {{
                    background: {PALETTE['bg_light']};
                    color: {PALETTE['text_primary']};
                    border: 1px solid {PALETTE['border']};
                    border-radius: 12px;
                }}
                QPushButton:pressed {{ background: {PALETTE['accent']}; color: {PALETTE['bg_dark']}; }}
            """)
            return b

        self._minus10_btn = _picker_btn("-10", sz(78))
        self._minus_btn   = _picker_btn("−")
        self._spinbox = QSpinBox()
        self._spinbox.setRange(1, 9999)
        self._spinbox.setValue(1)
        self._spinbox.setAlignment(Qt.AlignCenter)
        self._spinbox.setFixedSize(sz(100), sz(68))
        self._spinbox.setFont(scaled_font(FONT_MONO, 18, bold=True))
        self._spinbox.setStyleSheet(f"""
            QSpinBox {{
                background: {PALETTE['bg_light']};
                color: {PALETTE['text_primary']};
                border: 1px solid {PALETTE['border']};
                border-radius: 12px;
                padding: 4px 8px;
            }}
            QSpinBox::up-button, QSpinBox::down-button {{ width: 0; }}
        """)
        self._plus_btn    = _picker_btn("+")
        self._plus10_btn  = _picker_btn("+10", sz(78))
        self._plus100_btn = _picker_btn("+100", sz(90))
        self._max_btn = QPushButton("Max")
        self._max_btn.setFont(scaled_font(FONT_BODY, 13, bold=True))
        self._max_btn.setFixedSize(sz(76), sz(68))
        self._max_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._max_btn.setStyleSheet(f"""
            QPushButton {{
                background: {PALETTE['accent2']};
                color: {PALETTE['bg_dark']};
                border: none; border-radius: 12px; font-weight: bold;
            }}
            QPushButton:pressed {{ background: #4EB4A6; }}
        """)
        # Prevent virtual keyboard on mobile — value changes via buttons only
        self._spinbox.lineEdit().setReadOnly(True)
        self._spinbox.lineEdit().setFocusPolicy(Qt.NoFocus)
        self._minus100_btn.clicked.connect(lambda: self._spinbox.setValue(max(1, self._spinbox.value() - 100)))
        self._minus10_btn.clicked.connect( lambda: self._spinbox.setValue(max(1, self._spinbox.value() - 10)))
        self._minus_btn.clicked.connect(   lambda: self._spinbox.setValue(max(1, self._spinbox.value() - 1)))
        self._plus_btn.clicked.connect(    lambda: self._spinbox.setValue(self._spinbox.value() + 1))
        self._plus10_btn.clicked.connect(  lambda: self._spinbox.setValue(self._spinbox.value() + 10))
        self._plus100_btn.clicked.connect( lambda: self._spinbox.setValue(self._spinbox.value() + 100))
        self._max_btn.clicked.connect(self._set_max)

        picker_row = QHBoxLayout()
        picker_row.setAlignment(Qt.AlignCenter)
        picker_row.setSpacing(6)
        picker_row.addWidget(self._minus100_btn)
        picker_row.addWidget(self._minus10_btn)
        picker_row.addWidget(self._minus_btn)
        picker_row.addWidget(self._spinbox)
        picker_row.addWidget(self._plus_btn)
        picker_row.addWidget(self._plus10_btn)
        picker_row.addWidget(self._plus100_btn)
        picker_row.addWidget(self._max_btn)
        root.addLayout(picker_row)

        # Live "Requires X input" label — updates with spinbox
        self._needs_lbl = QLabel()
        self._needs_lbl.setAlignment(Qt.AlignCenter)
        self._needs_lbl.setFont(scaled_font(FONT_BODY, 11, bold=True))
        self._needs_lbl.setStyleSheet(f"color: {PALETTE['text_muted']}; background: rgba(0,0,0,110); border-radius: 8px; padding: 4px 12px; border: none;")
        _shadow_needs = QGraphicsDropShadowEffect(self._needs_lbl)
        _shadow_needs.setBlurRadius(10); _shadow_needs.setOffset(0, 1); _shadow_needs.setColor(QColor(0, 0, 0, 200))
        self._needs_lbl.setGraphicsEffect(_shadow_needs)
        root.addWidget(self._needs_lbl)

        self._inventory_lbl = QLabel()
        self._inventory_lbl.setAlignment(Qt.AlignCenter)
        self._inventory_lbl.setFont(scaled_font(FONT_BODY, 11))
        self._inventory_lbl.setStyleSheet(f"color: {PALETTE['text_primary']}; background: rgba(0,0,0,110); border-radius: 8px; padding: 4px 12px; border: none;")
        _shadow_inv = QGraphicsDropShadowEffect(self._inventory_lbl)
        _shadow_inv.setBlurRadius(10); _shadow_inv.setOffset(0, 1); _shadow_inv.setColor(QColor(0, 0, 0, 200))
        self._inventory_lbl.setGraphicsEffect(_shadow_inv)
        root.addWidget(self._inventory_lbl)

        self._spinbox.valueChanged.connect(self._update_needs)

        # Progress bar
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(12)
        self._progress.setStyleSheet(f"""
            QProgressBar {{
                background: {PALETTE['bg_light']};
                border: none;
                border-radius: 6px;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {PALETTE['accent']}, stop:1 {PALETTE['accent2']});
                border-radius: 6px;
            }}
        """)
        self._progress.hide()
        root.addWidget(self._progress)

        self._status_lbl = QLabel("")
        self._status_lbl.setAlignment(Qt.AlignCenter)
        self._status_lbl.setFont(scaled_font(FONT_BODY, 11, bold=True))
        self._status_lbl.setStyleSheet(f"color: {PALETTE['accent']}; background: rgba(0,0,0,110); border-radius: 8px; padding: 4px 12px; border: none;")
        _shadow_status = QGraphicsDropShadowEffect(self._status_lbl)
        _shadow_status.setBlurRadius(10); _shadow_status.setOffset(0, 1); _shadow_status.setColor(QColor(0, 0, 0, 200))
        self._status_lbl.setGraphicsEffect(_shadow_status)
        root.addWidget(self._status_lbl)

        self._refine_btn = QPushButton("Start Refining")
        self._refine_btn.setFont(scaled_font(FONT_BODY, 13, bold=True))
        self._refine_btn.setFixedHeight(sz(72))
        self._refine_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._refine_btn.setStyleSheet(f"""
            QPushButton {{
                background: {PALETTE['accent2']};
                color: {PALETTE['bg_dark']};
                border: none;
                border-radius: 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background: #4EB4A6; }}
            QPushButton:disabled {{ background: {PALETTE['text_dim']}; color: {PALETTE['bg_mid']}; }}
        """)
        self._refine_btn.clicked.connect(self._start_refine)
        root.addWidget(self._refine_btn)

        self._progress_timer = QTimer(self)
        self._progress_timer.setInterval(50)
        self._progress_timer.timeout.connect(self._update_progress)

        BUS.inventory_changed.connect(self.refresh)
        BUS.gold_changed.connect(self._update_lock)  # tool upgrades deduct gold
        BUS.prestige_changed.connect(self._refresh_material_selector)

        # Tool-tier lock overlay (visible when required tool tier not reached)
        tool_tier_req = self._station_def.get("tool_tier_req", 0)
        if tool_tier_req > 0:
            tool_name = self._station_def.get("tool_display_name", "Tool")
            self._lock_overlay = _LockOverlay(
                f"Requires {tool_name}\nTier {tool_tier_req}",
                PALETTE["accent"],
                self,
            )
        else:
            self._lock_overlay = None

        self.refresh()

        # Start sprite animation
        if isinstance(self._sprite, SpriteWidget):
            self._sprite.play()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._lock_overlay is not None:
            self._lock_overlay.setGeometry(0, 0, self.width(), self.height())
            if self._lock_overlay.isVisible():
                self._lock_overlay.raise_()

    def _update_lock(self):
        if self._lock_overlay is None:
            return
        tool_id = self._station_def.get("tool_id", "")
        req = self._station_def.get("tool_tier_req", 0)
        locked = self._state.get_tool_tier(tool_id) < req
        self._lock_overlay.setVisible(locked)
        if locked:
            self._lock_overlay.setGeometry(0, 0, self.width(), self.height())
            self._lock_overlay.raise_()

    def refresh(self):
        self._update_lock()
        if not self.isVisible():
            return
        recipe = self._current_recipe()
        inv = self._state.inventory.get(recipe["input"], 0)
        in_name = RESOURCES[recipe["input"]]["name"]
        self._inventory_lbl.setText(f"Have: {inv:,} {in_name}")
        self._update_needs()

    def _set_max(self):
        recipe = self._current_recipe()
        available = self._state.inventory.get(recipe["input"], 0)
        self._spinbox.setValue(max(1, available // recipe["ratio"]))

    def _update_needs(self):
        recipe = self._current_recipe()
        n = self._spinbox.value()
        needed = n * recipe["ratio"]
        available = self._state.inventory.get(recipe["input"], 0)
        in_name = RESOURCES[recipe["input"]]["name"]
        color = PALETTE["success"] if available >= needed else PALETTE["danger"]
        self._needs_lbl.setText(f"Requires {needed:,} {in_name}")
        self._needs_lbl.setStyleSheet(f"color: {color}; background: rgba(0,0,0,110); border-radius: 8px; padding: 4px 12px; border: none; font-weight: bold;")

    def _start_refine(self):
        if self._refining:
            return
        recipe = self._current_recipe()
        self._active_recipe = recipe   # snapshot so _finish_refine uses same recipe
        amount = self._spinbox.value()
        needed = amount * recipe["ratio"]
        available = self._state.inventory.get(recipe["input"], 0)
        if available < needed:
            self._status_lbl.setText(f"Need {needed} {RESOURCES[recipe['input']]['name']} (have {available})")
            return

        self._state.inventory[recipe["input"]] -= needed
        self._refining = True
        time_per = recipe["time_per_unit"] / self._state.get_effective_refine_speed(self._station_id)
        self._refine_duration = time_per * amount
        self._refine_start = time.time()
        self._refine_amount = amount
        BUS.refine_started.emit(self._station_id, self._refine_duration)
        out_name = RESOURCES[recipe["output"]]["name"]
        self._status_lbl.setText(f"Refining {amount} {out_name}…")
        self._refine_btn.setEnabled(False)
        self._progress.setValue(0)
        self._progress.show()
        self._progress_timer.start()
        BUS.inventory_changed.emit()

    def _update_progress(self):
        elapsed = time.time() - self._refine_start
        pct = min(elapsed / max(self._refine_duration, 0.001), 1.0)
        self._progress.setValue(int(pct * 100))
        if pct >= 1.0:
            self._finish_refine()

    def _finish_refine(self):
        self._progress_timer.stop()
        self._refining = False
        recipe = getattr(self, "_active_recipe", None) or self._current_recipe()
        output = recipe["output"]
        amount = self._refine_amount
        self._state.inventory[output] = self._state.inventory.get(output, 0) + amount
        skill = self._station_def["xp_skill"]
        xp = recipe.get("xp_per_output", self._station_def["xp_per_output"]) * amount
        eff_xp, leveled = self._state.add_xp(skill, xp)
        BUS.xp_changed.emit(skill, self._state.skills[skill].xp)
        BUS.inventory_changed.emit()
        BUS.refine_complete.emit(self._station_id, amount)
        # Floating XP notification
        skill_color = SKILLS.get(skill, {}).get("color", PALETTE["accent"])
        win = self.window()
        pt = self.mapTo(win, self.rect().center())
        FloatingText.spawn(f"+{eff_xp} XP", skill_color, win, cx=pt.x(), cy=pt.y())
        if leveled:
            BUS.level_up.emit(skill, self._state.skills[skill].level)
        out_name = RESOURCES[output]["name"]
        self._status_lbl.setText(f"Done! +{amount} {out_name}")
        self._status_lbl.setStyleSheet(f"color: {PALETTE['success']}; background: rgba(0,0,0,110); border-radius: 8px; padding: 4px 12px; border: none; font-weight: bold;")
        self._progress.hide()
        self._refine_btn.setEnabled(True)
        self.refresh()

    def cancel_refining(self):
        if not self._refining:
            return
        self._progress_timer.stop()
        self._refining = False
        self._refine_start = 0.0
        self._refine_duration = 0.0
        self._refine_amount = 0
        self._refine_produced = 0
        self._progress.hide()
        self._progress.setValue(0)
        self._status_lbl.setText("Refining cancelled.")
        self._refine_btn.setEnabled(True)


# ---------------------------------------------------------------------------
# GEODE DIALOG  — animated open + reveal
# ---------------------------------------------------------------------------
GEODE_FRAMES_N = 36
GEODE_W, GEODE_H = 576, 482
GEODE_DELAY = 12   # ms

class GeodeDialog(QDialog):
    def __init__(self, state: GameState, parent=None):
        super().__init__(parent)
        self._state = state
        self._phase = "idle"   # idle -> animating -> reveal -> done
        self._gem_id: Optional[str] = None
        self.setModal(True)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(520, 520)
        self.setStyleSheet("background: transparent;")

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(12)

        # Title
        title = QLabel("Opening Geode...")
        title.setFont(scaled_font(FONT_TITLE, 16, bold=True))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"color: {PALETTE['accent']}; background: transparent; border: none;")
        root.addWidget(title)
        self._title = title

        # Sprite area
        sprite_frame = QFrame()
        sprite_frame.setFixedSize(360, 360)
        sprite_frame.setStyleSheet(f"""
            background: {PALETTE['bg_card']};
            border: 2px solid {PALETTE['accent']};
            border-radius: 20px;
        """)
        make_shadow(sprite_frame, blur=30, opacity=200)
        sflay = QVBoxLayout(sprite_frame)
        sflay.setAlignment(Qt.AlignCenter)

        geode_frames = load_sprite_sheet("geode.png", GEODE_W, GEODE_H, GEODE_FRAMES_N)
        scaled_geode = [f.scaled(280, 280, Qt.KeepAspectRatio, Qt.SmoothTransformation) for f in geode_frames]

        if scaled_geode:
            self._geode_sprite = SpriteWidget(scaled_geode, GEODE_DELAY, loop=False, parent=sprite_frame)
            self._geode_sprite.animation_done.connect(self._on_anim_done)
            sflay.addWidget(self._geode_sprite)
        else:
            ph_px = load_image("geodeStatic.png")
            self._geode_lbl = QLabel()
            self._geode_lbl.setAlignment(Qt.AlignCenter)
            if ph_px:
                self._geode_lbl.setPixmap(ph_px.scaled(280, 280, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                self._geode_lbl.setPixmap(make_placeholder(280, 280, "Geode"))
            sflay.addWidget(self._geode_lbl)
            self._geode_sprite = None

        # Gem reveal label (hidden initially)
        self._gem_lbl = QLabel()
        self._gem_lbl.setAlignment(Qt.AlignCenter)
        self._gem_lbl.hide()
        sflay.addWidget(self._gem_lbl)

        root.addWidget(sprite_frame, alignment=Qt.AlignCenter)

        # Result text
        self._result_lbl = QLabel("")
        self._result_lbl.setFont(scaled_font(FONT_TITLE, 14, bold=True))
        self._result_lbl.setAlignment(Qt.AlignCenter)
        self._result_lbl.setStyleSheet(f"color: {PALETTE['gold']}; background: transparent; border: none;")
        root.addWidget(self._result_lbl)

        # Continue button
        self._continue_btn = QPushButton("Open Geode")
        self._continue_btn.setFont(scaled_font(FONT_BODY, 12, bold=True))
        self._continue_btn.setFixedHeight(46)
        self._continue_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._continue_btn.setStyleSheet(f"""
            QPushButton {{
                background: {PALETTE['accent']};
                color: {PALETTE['bg_dark']};
                border: none;
                border-radius: 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background: #C08030; }}
        """)
        self._continue_btn.clicked.connect(self._on_continue)
        root.addWidget(self._continue_btn)

        # "Open Again" button — visible only at reveal phase when player has more geodes
        self._open_again_btn = QPushButton("⟳  Open Again")
        self._open_again_btn.setFont(scaled_font(FONT_BODY, 12, bold=True))
        self._open_again_btn.setFixedHeight(46)
        self._open_again_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._open_again_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #5A9EE0, stop:0.55 #2E6ABE, stop:1 #1A4A96);
                color: #E8F4FF;
                border: 1px solid #6AAEDD;
                border-radius: 12px;
                font-weight: bold;
            }}
            QPushButton:pressed {{ background: #0E3272; }}
        """)
        self._open_again_btn.clicked.connect(self._on_open_again)
        self._open_again_btn.hide()
        root.addWidget(self._open_again_btn)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor(PALETTE["bg_mid"]))
        p.setPen(QPen(QColor(PALETTE["accent"]), 2))
        p.drawRoundedRect(self.rect().adjusted(4, 4, -4, -4), 24, 24)

    def _on_continue(self):
        if self._phase == "idle":
            if self._state.special_items.get("geode", 0) <= 0:
                self.reject()
                return
            self._phase = "animating"
            self._continue_btn.setEnabled(False)
            self._open_again_btn.hide()
            self._title.setText("Opening Geode...")
            self._gem_id = self._state.open_geode()
            if self._geode_sprite:
                self._geode_sprite.play(loop=False)
            else:
                # No animation frames — go straight to reveal
                self._on_anim_done()
        elif self._phase == "reveal":
            self._phase = "done"
            self._open_again_btn.hide()
            BUS.inventory_changed.emit()
            self.accept()

    def _on_anim_done(self):
        self._phase = "reveal"
        # Show gem
        if self._gem_id:
            gem_def = SPECIAL_ITEMS.get(self._gem_id, {})
            gem_name = gem_def.get("name", self._gem_id)
            gem_px = load_image(gem_def.get("sprite", ""))
            if self._geode_sprite:
                self._geode_sprite.hide()
            self._gem_lbl.show()
            if gem_px:
                self._gem_lbl.setPixmap(gem_px.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                self._gem_lbl.setPixmap(make_placeholder(200, 200, gem_name))
            self._title.setText("Geode Opened!")
            self._result_lbl.setText(f"Obtained {gem_name}!")
        self._continue_btn.setEnabled(True)
        self._continue_btn.setText("Continue")
        # Show "Open Again" if player still has geodes
        remaining = self._state.special_items.get("geode", 0)
        if remaining >= 1:
            self._open_again_btn.setText(f"⟳  Open Again  ({remaining} left)")
            self._open_again_btn.show()
        else:
            self._open_again_btn.hide()

    def _on_open_again(self):
        """Reset dialog state and immediately open another geode."""
        if self._state.special_items.get("geode", 0) <= 0:
            self._open_again_btn.hide()
            return
        # Reset to idle then trigger open
        self._phase = "idle"
        self._open_again_btn.hide()
        self._gem_lbl.hide()
        if self._geode_sprite:
            self._geode_sprite.show()
        self._on_continue()


# ---------------------------------------------------------------------------
# HARVEST SPIRIT TIMER  — shown on gather page when buff is active
# ---------------------------------------------------------------------------
class HarvestSpiritTimer(QWidget):
    def __init__(self, state: GameState, parent=None):
        super().__init__(parent)
        self._state = state
        self.setFixedHeight(36)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 0, 12, 0)
        lay.setSpacing(8)
        lbl = QLabel("🌿 Harvest Spirit")
        lbl.setFont(scaled_font(FONT_BODY, 11, bold=True))
        lbl.setStyleSheet(f"color: {PALETTE['success']}; background: transparent; border: none;")
        self._timer_lbl = QLabel("30s")
        self._timer_lbl.setFont(scaled_font(FONT_MONO, 11, bold=True))
        self._timer_lbl.setStyleSheet(f"color: {PALETTE['gold']}; background: transparent; border: none;")
        self._bar = QProgressBar()
        self._bar.setRange(0, HARVEST_SPIRIT_DURATION * 10)
        self._bar.setValue(0)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(8)
        self._bar.setStyleSheet(f"""
            QProgressBar {{ background: {PALETTE['bg_light']}; border: none; border-radius: 4px; }}
            QProgressBar::chunk {{ background: {PALETTE['success']}; border-radius: 4px; }}
        """)
        lay.addWidget(lbl)
        lay.addWidget(self._bar, stretch=1)
        lay.addWidget(self._timer_lbl)
        self.setStyleSheet(f"""
            background: {PALETTE['bg_card']};
            border: 1px solid {PALETTE['success']};
            border-radius: 12px;
        """)
        self.hide()

        self._tick = QTimer(self)
        self._tick.setInterval(100)
        self._tick.timeout.connect(self._update)

        BUS.spirit_changed.connect(self._on_spirit_changed)

    def _on_spirit_changed(self, remaining: float):
        if remaining > 0:
            self.show()
            self._tick.start()
        else:
            self._tick.stop()
            self.hide()

    def _update(self):
        rem = self._state.spirit_remaining()
        if rem <= 0:
            self._tick.stop()
            self.hide()
            BUS.spirit_changed.emit(0.0)
            return
        self._timer_lbl.setText(f"{int(rem)+1}s")
        self._bar.setValue(int(rem * 10))


# ---------------------------------------------------------------------------
# PAGE: ITEMS  (combined Inventory + Sell)
# ---------------------------------------------------------------------------
class ItemsPage(QWidget):
    """
    Combined inventory + market page.
    Resources tab: qty, value, spinbox + Sell button per row.
    Special Items tab: qty, desc, action button (Open/Use) + Sell button for sellable items.
    """
    def __init__(self, state: GameState, parent=None):
        super().__init__(parent)
        self._state = state
        self.setStyleSheet("background: transparent;")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header row ──────────────────────────────────────────────────
        hdr = QWidget()
        hdr.setFixedHeight(60)
        hdr.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {PALETTE['bg_mid']}, stop:1 {PALETTE['bg_dark']});
            border-bottom: 1px solid {PALETTE['border']};
        """)
        hlay = QHBoxLayout(hdr)
        hlay.setContentsMargins(16, 0, 16, 0)
        title_lbl = QLabel("Items")
        title_lbl.setFont(scaled_font(FONT_TITLE, 14, bold=True))
        title_lbl.setStyleSheet(f"color: {PALETTE['text_primary']}; background: transparent; border: none;")
        self._sell_all_btn = QPushButton("Sell All")
        self._sell_all_btn.setFont(scaled_font(FONT_BODY, 11, bold=True))
        self._sell_all_btn.setFixedHeight(38)
        self._sell_all_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._sell_all_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {PALETTE['gold']}, stop:1 #C8960C);
                color: {PALETTE['bg_dark']};
                border: none; border-radius: 12px; padding: 0 18px; font-weight: bold;
            }}
            QPushButton:pressed {{ background: #A07800; }}
        """)
        _sell_coin_px = load_image("coin.png")
        if _sell_coin_px:
            self._sell_all_btn.setIcon(QIcon(_sell_coin_px.scaled(sz(22), sz(22), Qt.KeepAspectRatio, Qt.SmoothTransformation)))
            self._sell_all_btn.setIconSize(QSize(sz(22), sz(22)))
        self._sell_all_btn.clicked.connect(self._sell_all_items)
        hlay.addWidget(title_lbl)
        hlay.addStretch()
        hlay.addWidget(self._sell_all_btn)
        root.addWidget(hdr)

        # ── Tab bar ──────────────────────────────────────────────────────
        tab_bar = QWidget()
        tab_bar.setFixedHeight(52)
        tab_bar.setStyleSheet(f"background: {PALETTE['bg_dark']}; border-bottom: 1px solid {PALETTE['border']};")
        tlay = QHBoxLayout(tab_bar)
        tlay.setContentsMargins(14, 8, 14, 8)
        tlay.setSpacing(8)

        def _tab_btn(label: str) -> QPushButton:
            b = QPushButton(label)
            b.setFont(scaled_font(FONT_BODY, 11, bold=True))
            b.setCheckable(True)
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            b.setCursor(QCursor(Qt.PointingHandCursor))
            return b

        self._tab_resources = _tab_btn("Resources")
        self._tab_special   = _tab_btn("Special Items")
        tlay.addWidget(self._tab_resources)
        tlay.addWidget(self._tab_special)
        root.addWidget(tab_bar)

        # ── Stacked content ──────────────────────────────────────────────
        self._content = QStackedWidget()
        self._content.setStyleSheet("background: transparent;")
        root.addWidget(self._content, stretch=1)

        # — Resources page —
        res_page = QWidget()
        res_page.setStyleSheet("background: transparent;")
        rp_lay = QVBoxLayout(res_page)
        rp_lay.setContentsMargins(0, 0, 0, 0)
        rp_lay.setSpacing(0)
        res_scroll = QScrollArea()
        res_scroll.setWidgetResizable(True)
        res_scroll.setStyleSheet("background: transparent; border: none;")
        _setup_touch_scroll(res_scroll)
        res_container = QWidget()
        res_container.setStyleSheet("background: transparent;")
        res_vlay = QVBoxLayout(res_container)
        res_vlay.setContentsMargins(14, 12, 14, 12)
        res_vlay.setSpacing(10)
        self._res_rows: dict[str, "_ItemRow"] = {}
        for res_id, res_def in RESOURCES.items():
            row = _ItemRow(res_id, res_def["name"], res_def.get("sprite", ""),
                           state, is_special=False, parent=res_container)
            res_vlay.addWidget(row)
            self._res_rows[res_id] = row
        res_vlay.addStretch()
        res_scroll.setWidget(res_container)
        rp_lay.addWidget(res_scroll)
        self._content.addWidget(res_page)  # index 0

        # — Special Items page —
        spec_page = QWidget()
        spec_page.setStyleSheet("background: transparent;")
        sp_lay = QVBoxLayout(spec_page)
        sp_lay.setContentsMargins(0, 0, 0, 0)
        sp_lay.setSpacing(0)
        spec_scroll = QScrollArea()
        spec_scroll.setWidgetResizable(True)
        spec_scroll.setStyleSheet("background: transparent; border: none;")
        _setup_touch_scroll(spec_scroll)
        spec_container = QWidget()
        spec_container.setStyleSheet("background: transparent;")
        spec_vlay = QVBoxLayout(spec_container)
        spec_vlay.setContentsMargins(14, 12, 14, 12)
        spec_vlay.setSpacing(10)
        self._spec_rows: dict[str, "_ItemRow"] = {}
        for item_id, item_def in SPECIAL_ITEMS.items():
            row = _ItemRow(item_id, item_def["name"], item_def.get("sprite", ""),
                           state, is_special=True, item_def=item_def, parent=spec_container)
            spec_vlay.addWidget(row)
            self._spec_rows[item_id] = row
        spec_vlay.addStretch()
        spec_scroll.setWidget(spec_container)
        sp_lay.addWidget(spec_scroll)
        self._content.addWidget(spec_page)  # index 1

        # Tab switching logic
        self._tab_resources.setChecked(True)
        self._content.setCurrentIndex(0)
        self._sell_all_btn.setVisible(True)
        self._update_tab_styles()

        self._tab_resources.clicked.connect(lambda: self._switch_tab(0))
        self._tab_special.clicked.connect(lambda: self._switch_tab(1))

        BUS.inventory_changed.connect(self.refresh)
        BUS.gold_changed.connect(self.refresh)

    def _switch_tab(self, idx: int):
        self._content.setCurrentIndex(idx)
        self._tab_resources.setChecked(idx == 0)
        self._tab_special.setChecked(idx == 1)
        # Hide Sell All on special tab (items are mixed sellable/non-sellable)
        self._sell_all_btn.setVisible(idx == 0)
        self._update_tab_styles()

    def _update_tab_styles(self):
        for btn, active in [(self._tab_resources, self._content.currentIndex() == 0),
                             (self._tab_special,   self._content.currentIndex() == 1)]:
            if active:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {PALETTE['accent']};
                        color: {PALETTE['bg_dark']};
                        border: none;
                        border-radius: 14px;
                        font-weight: bold;
                        padding: 0 12px;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {PALETTE['bg_light']};
                        color: {PALETTE['text_muted']};
                        border: 1px solid {PALETTE['border']};
                        border-radius: 14px;
                        font-weight: bold;
                        padding: 0 12px;
                    }}
                    QPushButton:hover {{ color: {PALETTE['text_primary']}; background: {PALETTE['bg_card']}; }}
                """)

    def _sell_all_items(self):
        old_trading_level = self._state.skills["trading"].level
        total_xp = 0
        total_earned = 0.0
        for res_id in RESOURCES:
            qty = self._state.inventory.get(res_id, 0)
            if qty > 0:
                price = self._state.get_effective_sell_price(res_id)
                earned = price * qty
                self._state.gold += earned
                total_earned += earned
                self._state.inventory[res_id] = 0
                xp_gain = int(self._state.get_effective_xp(2 * qty))
                self._state.skills["trading"].xp += xp_gain
                total_xp += xp_gain
        for item_id, item_def in SPECIAL_ITEMS.items():
            if item_def.get("sellable"):
                qty = self._state.special_items.get(item_id, 0)
                if qty > 0:
                    price = self._state.get_effective_sell_price(item_id)
                    earned = price * qty
                    self._state.gold += earned
                    total_earned += earned
                    self._state.special_items[item_id] = 0
                    xp_gain = int(self._state.get_effective_xp(3 * qty))
                    self._state.skills["trading"].xp += xp_gain
                    total_xp += xp_gain
        BUS.gold_changed.emit()
        BUS.inventory_changed.emit()
        if total_xp > 0:
            BUS.xp_changed.emit("trading", self._state.skills["trading"].xp)
        if total_earned > 0:
            BUS.gold_delta.emit(total_earned)
        new_trading_level = self._state.skills["trading"].level
        if new_trading_level > old_trading_level:
            BUS.level_up.emit("trading", new_trading_level)

    def refresh(self):
        if not self.isVisible():
            return
        for row in self._res_rows.values():
            row.refresh()
        for row in self._spec_rows.values():
            row.refresh()


class _ItemRow(QFrame):
    """
    Single row used on both tabs of ItemsPage.
    Resources: shows qty, price/each, spinbox + Sell button.
    Special items: shows qty, desc; sellable items get spinbox + Sell button;
                   geode gets an Open button; harvestSpirit gets a Use button.
    """
    def __init__(self, item_id: str, display_name: str, sprite: str,
                 state: GameState, is_special: bool = False,
                 item_def: dict = None, parent=None):
        super().__init__(parent)
        self._item_id = item_id
        self._state = state
        self._is_special = is_special
        self._item_def = item_def or {}
        self._sell_btn: Optional[QPushButton] = None
        self._spin: Optional[QSpinBox] = None

        self.setMinimumHeight(96)
        self.setStyleSheet(f"""
            QFrame {{
                background: {PALETTE['bg_card']};
                border: 1px solid {PALETTE['border']};
                border-radius: 16px;
            }}
        """)
        make_shadow(self, blur=14, opacity=90)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 14, 0)
        lay.setSpacing(0)

        # Left accent stripe — colour varies by item type
        stripe_color = (PALETTE["prestige"] if is_special else
                        PALETTE["accent2"] if item_id in ("oakLog", "oakPlank") else
                        PALETTE["accent"] if item_id in ("ironOre", "ironIngot") else
                        PALETTE["text_muted"])
        stripe = QFrame()
        stripe.setFixedWidth(5)
        stripe.setStyleSheet(f"background: {stripe_color}; border-top-left-radius: 16px; border-bottom-left-radius: 16px; border: none;")
        lay.addWidget(stripe)
        lay.addSpacing(12)

        # Icon
        px = load_image(sprite)
        icon = QLabel()
        icon.setFixedSize(sz(54), sz(54))
        if px:
            icon.setPixmap(px.scaled(sz(54), sz(54), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            ph = make_placeholder(sz(54), sz(54), item_id[:2].upper())
            icon.setPixmap(ph)
        icon.setStyleSheet("background: transparent; border: none;")
        lay.addWidget(icon)
        lay.addSpacing(10)

        # Info column
        info = QVBoxLayout()
        info.setSpacing(2)
        info.setContentsMargins(0, 10, 0, 10)
        name_lbl = QLabel(display_name)
        name_lbl.setFont(scaled_font(FONT_BODY, 12, bold=True))
        name_lbl.setStyleSheet(f"color: {PALETTE['text_primary']}; background: transparent; border: none;")
        self._qty_lbl = QLabel()
        self._qty_lbl.setFont(scaled_font(FONT_MONO, 14, bold=True))
        self._qty_lbl.setStyleSheet(f"color: {PALETTE['accent2']}; background: transparent; border: none;")
        self._sub_lbl = QLabel()
        self._sub_lbl.setFont(scaled_font(FONT_BODY, 9))
        self._sub_lbl.setStyleSheet(f"color: {PALETTE['text_muted']}; background: transparent; border: none;")
        self._sub_lbl.setWordWrap(True)
        info.addWidget(name_lbl)
        info.addWidget(self._qty_lbl)
        info.addWidget(self._sub_lbl)
        lay.addLayout(info, stretch=1)

        # Right-side controls
        if not is_special:
            # Resource row: price label + spinbox + All + Sell
            self._price_lbl = QLabel()
            self._price_lbl.setFont(scaled_font(FONT_MONO, 13, bold=True))
            self._price_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._price_lbl.setStyleSheet(f"color: {PALETTE['gold']}; background: transparent; border: none;")
            lay.addWidget(self._price_lbl)
            self._spin, all_btn, sell_btn = self._make_sell_controls(lay)
        else:
            sellable = self._item_def.get("sellable", False)
            if item_id == "geode":
                open_btn = QPushButton("Open")
                open_btn.setFont(scaled_font(FONT_BODY, 10, bold=True))
                open_btn.setFixedSize(70, 44)
                open_btn.setCursor(QCursor(Qt.PointingHandCursor))
                open_btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {PALETTE['accent']};
                        color: {PALETTE['bg_dark']};
                        border: none; border-radius: 10px; font-weight: bold;
                    }}
                    QPushButton:pressed {{ background: #C08030; }}
                    QPushButton:disabled {{ background: {PALETTE['text_dim']}; color: {PALETTE['bg_mid']}; }}
                """)
                open_btn.clicked.connect(self._open_geode)
                lay.addWidget(open_btn)
                self._action_btn = open_btn
            elif item_id == "harvestSpirit":
                use_btn = QPushButton("Use")
                use_btn.setFont(scaled_font(FONT_BODY, 10, bold=True))
                use_btn.setFixedSize(66, 44)
                use_btn.setCursor(QCursor(Qt.PointingHandCursor))
                use_btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {PALETTE['success']};
                        color: {PALETTE['bg_dark']};
                        border: none; border-radius: 10px; font-weight: bold;
                    }}
                    QPushButton:pressed {{ background: #50BB70; }}
                    QPushButton:disabled {{ background: {PALETTE['text_dim']}; color: {PALETTE['bg_mid']}; }}
                """)
                use_btn.clicked.connect(self._use_spirit)
                lay.addWidget(use_btn)
                self._action_btn = use_btn
            else:
                self._action_btn = None

            if sellable:
                self._price_lbl = QLabel()
                self._price_lbl.setFont(scaled_font(FONT_MONO, 13, bold=True))
                self._price_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self._price_lbl.setStyleSheet(f"color: {PALETTE['gold']}; background: transparent; border: none;")
                lay.addWidget(self._price_lbl)
                self._spin, all_btn, sell_btn = self._make_sell_controls(lay)
            else:
                self._price_lbl = None

        self.refresh()

    def _make_sell_controls(self, lay: QHBoxLayout):
        spin = QSpinBox()
        spin.setRange(1, 99999)
        spin.setValue(1)
        spin.setFixedWidth(60)
        spin.setFont(scaled_font(FONT_MONO, 10))
        spin.setStyleSheet(f"""
            QSpinBox {{
                background: {PALETTE['bg_light']};
                color: {PALETTE['text_primary']};
                border: 1px solid {PALETTE['border']};
                border-radius: 6px;
                padding: 2px 4px;
            }}
            QSpinBox::up-button, QSpinBox::down-button {{ width: 0; }}
        """)
        spin.lineEdit().setReadOnly(True)
        spin.lineEdit().setFocusPolicy(Qt.NoFocus)

        def _step_btn(text: str) -> QPushButton:
            b = QPushButton(text)
            b.setFont(scaled_font(FONT_BODY, 8, bold=True))
            b.setFixedSize(38, 36)
            b.setCursor(QCursor(Qt.PointingHandCursor))
            b.setStyleSheet(f"""
                QPushButton {{
                    background: {PALETTE['bg_light']};
                    color: {PALETTE['text_muted']};
                    border: 1px solid {PALETTE['border']};
                    border-radius: 6px;
                }}
                QPushButton:pressed {{ background: {PALETTE['bg_card']}; color: {PALETTE['text_primary']}; }}
            """)
            return b

        m100 = _step_btn("-100")
        m10  = _step_btn("-10")
        m1   = _step_btn("-1")
        p1   = _step_btn("+1")
        p10  = _step_btn("+10")
        p100 = _step_btn("+100")
        m100.clicked.connect(lambda: spin.setValue(max(1, spin.value() - 100)))
        m10.clicked.connect( lambda: spin.setValue(max(1, spin.value() - 10)))
        m1.clicked.connect(  lambda: spin.setValue(max(1, spin.value() - 1)))
        p1.clicked.connect(  lambda: spin.setValue(spin.value() + 1))
        p10.clicked.connect( lambda: spin.setValue(spin.value() + 10))
        p100.clicked.connect(lambda: spin.setValue(spin.value() + 100))

        for w in (m100, m10, m1):
            lay.addWidget(w)
        lay.addWidget(spin)
        for w in (p1, p10, p100):
            lay.addWidget(w)

        all_btn = QPushButton("All")
        all_btn.setFont(scaled_font(FONT_BODY, 9))
        all_btn.setFixedSize(44, 36)
        all_btn.setCursor(QCursor(Qt.PointingHandCursor))
        all_btn.setStyleSheet(f"""
            QPushButton {{
                background: {PALETTE['bg_light']};
                color: {PALETTE['text_muted']};
                border: 1px solid {PALETTE['border']};
                border-radius: 8px;
            }}
            QPushButton:pressed {{ color: {PALETTE['accent']}; }}
        """)
        all_btn.clicked.connect(lambda: (spin.setValue(max(1, self._get_qty())), self._sell()))
        lay.addWidget(all_btn)

        sell_btn = QPushButton("Sell")
        sell_btn.setFont(scaled_font(FONT_BODY, 10, bold=True))
        sell_btn.setFixedSize(58, 40)
        sell_btn.setCursor(QCursor(Qt.PointingHandCursor))
        sell_btn.setStyleSheet(f"""
            QPushButton {{
                background: {PALETTE['gold']};
                color: {PALETTE['bg_dark']};
                border: none; border-radius: 10px; font-weight: bold;
            }}
            QPushButton:pressed {{ background: #D8B030; }}
            QPushButton:disabled {{ background: {PALETTE['text_dim']}; color: {PALETTE['bg_mid']}; }}
        """)
        sell_btn.clicked.connect(self._sell)
        lay.addWidget(sell_btn)

        self._sell_btn = sell_btn
        return spin, all_btn, sell_btn

    def _get_qty(self) -> int:
        if self._is_special:
            return self._state.special_items.get(self._item_id, 0)
        return self._state.inventory.get(self._item_id, 0)

    def refresh(self):
        qty = self._get_qty()
        self._qty_lbl.setText(f"{qty:,}")

        if not self._is_special:
            price = self._state.get_effective_sell_price(self._item_id)
            self._sub_lbl.setText(f"{price:.1f} {COIN_HTML}each")
            if self._price_lbl:
                self._price_lbl.setText(f"{price:.1f} {COIN_HTML}")
            if self._spin:
                self._spin.setMaximum(max(1, qty))
            if self._sell_btn:
                self._sell_btn.setEnabled(qty > 0)
        else:
            self._sub_lbl.setText(self._item_def.get("desc", ""))
            if hasattr(self, "_action_btn") and self._action_btn:
                self._action_btn.setEnabled(qty > 0)
            if self._item_def.get("sellable"):
                price = self._state.get_effective_sell_price(self._item_id)
                if self._price_lbl:
                    self._price_lbl.setText(f"{price:.1f} {COIN_HTML}")
                if self._spin:
                    self._spin.setMaximum(max(1, qty))
                if self._sell_btn:
                    self._sell_btn.setEnabled(qty > 0)

    def _sell(self):
        if not self._spin:
            return
        amount = self._spin.value()
        qty = self._get_qty()
        amount = min(amount, qty)
        if amount <= 0:
            return
        price = self._state.get_effective_sell_price(self._item_id)
        earned = price * amount
        if self._is_special:
            self._state.special_items[self._item_id] = self._state.special_items.get(self._item_id, 0) - amount
        else:
            self._state.inventory[self._item_id] -= amount
        self._state.gold += earned
        xp_per = 3 if self._is_special else 2
        eff_xp, leveled = self._state.add_xp("trading", xp_per * amount)
        BUS.gold_changed.emit()
        BUS.inventory_changed.emit()
        BUS.xp_changed.emit("trading", self._state.skills["trading"].xp)
        BUS.gold_delta.emit(float(earned))
        if leveled:
            BUS.level_up.emit("trading", self._state.skills["trading"].level)

    def _open_geode(self):
        dlg = GeodeDialog(self._state, self.window())
        dlg.exec()
        self.refresh()

    def _use_spirit(self):
        if self._state.activate_spirit():
            BUS.inventory_changed.emit()
            BUS.spirit_changed.emit(float(HARVEST_SPIRIT_DURATION))
            self.refresh()


# ---------------------------------------------------------------------------
# SCROLL HINT  — animated chevron overlay for scrollable pages
# ---------------------------------------------------------------------------
class _ScrollHint(QWidget):
    """
    A small, non-interactive overlay that draws a pulsing/bobbing down-chevron
    at the bottom of a scroll area to hint that the content is scrollable.
    Fades away permanently once the user has scrolled a little.
    """
    def __init__(self, scroll_area: "QScrollArea", parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setFixedSize(sz(56), sz(48))

        self._eff = QGraphicsOpacityEffect(self)
        self._eff.setOpacity(0.75)
        self.setGraphicsEffect(self._eff)

        # Bob animation — two legs (down then up) in a sequential group so the
        # widget always stays within its intended bounds (no drift on loop).
        self._bob_down = QPropertyAnimation(self, b"pos", self)
        self._bob_down.setDuration(450)
        self._bob_down.setEasingCurve(QEasingCurve.InOutSine)
        self._bob_up = QPropertyAnimation(self, b"pos", self)
        self._bob_up.setDuration(450)
        self._bob_up.setEasingCurve(QEasingCurve.InOutSine)
        self._bob_grp = QSequentialAnimationGroup(self)
        self._bob_grp.addAnimation(self._bob_down)
        self._bob_grp.addAnimation(self._bob_up)
        self._bob_grp.setLoopCount(-1)  # infinite

        # Fade-out animation — played once when user scrolls
        self._fade = QPropertyAnimation(self._eff, b"opacity", self)
        self._fade.setDuration(350)
        self._fade.setStartValue(0.75)
        self._fade.setEndValue(0.0)
        self._fade.finished.connect(self.hide)

        self._gone = False

        # Watch the scrollbar
        sb = scroll_area.verticalScrollBar()
        sb.valueChanged.connect(self._on_scroll)
        sb.rangeChanged.connect(self._on_range)

    def _on_scroll(self, val: int) -> None:
        if not self._gone and val > 24:
            self._dismiss()

    def _on_range(self, _min: int, _max: int) -> None:
        # If content isn't actually scrollable, hide immediately
        if _max <= 0 and not self._gone:
            self._dismiss()

    def _dismiss(self) -> None:
        self._gone = True
        self._bob_grp.stop()
        self._fade.start()

    def start(self) -> None:
        """Call once the parent is laid out so geometry is known."""
        if self._gone:
            return
        self._reposition()
        self.show()
        self._bob_grp.start()

    def _reposition(self) -> None:
        if not self.parent():
            return
        pw = self.parent().width()
        ph = self.parent().height()
        x = (pw - self.width()) // 2
        y = ph - self.height() - sz(6)
        self.move(x, y)
        base = QPoint(x, y)
        tip  = QPoint(x, y + sz(6))
        self._bob_down.setStartValue(base)
        self._bob_down.setEndValue(tip)
        self._bob_up.setStartValue(tip)
        self._bob_up.setEndValue(base)

    def resizeEvent(self, event):
        super().resizeEvent(event)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        # Draw three stacked chevrons, each slightly more transparent than the one above
        cx = w // 2
        for row in range(3):
            alpha = 200 - row * 55
            y0 = sz(8) + row * sz(13)
            half = sz(10)
            tip = sz(7)
            pen = QPen(QColor(255, 255, 255, alpha), sz(2), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            p.setPen(pen)
            p.drawLine(cx - half, y0,       cx,          y0 + tip)
            p.drawLine(cx,        y0 + tip,  cx + half,   y0)
        p.end()


# ---------------------------------------------------------------------------
# PAGE: UPGRADES
# ---------------------------------------------------------------------------
class UpgradesPage(QWidget):
    """Combined Upgrades page: Tools section, Skills section, Runic Forge section."""

    def __init__(self, state: GameState, parent=None):
        super().__init__(parent)
        self._state = state
        self.setStyleSheet("background: transparent;")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header row ──────────────────────────────────────────────────
        hdr = QWidget()
        hdr.setFixedHeight(60)
        hdr.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {PALETTE['bg_mid']}, stop:1 {PALETTE['bg_dark']});
            border-bottom: 1px solid {PALETTE['border']};
        """)
        hlay = QHBoxLayout(hdr)
        hlay.setContentsMargins(16, 0, 16, 0)
        title_lbl = QLabel("Upgrades & Skills")
        title_lbl.setFont(scaled_font(FONT_TITLE, 14, bold=True))
        title_lbl.setStyleSheet(f"color: {PALETTE['text_primary']}; background: transparent; border: none;")
        self._gold_lbl = QLabel()
        self._gold_lbl.setFont(scaled_font(FONT_BODY, 12, bold=True))
        self._gold_lbl.setStyleSheet(f"color: {PALETTE['gold']}; background: transparent; border: none;")
        _shard_hdr_icon = QLabel()
        _shard_hdr_icon.setFixedSize(20, 20)
        _shard_hdr_icon.setStyleSheet("background: transparent; border: none;")
        _shpx = load_image("runicShard.png")
        if _shpx:
            _shard_hdr_icon.setPixmap(_shpx.scaled(20, 20, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self._shards_lbl = QLabel()
        self._shards_lbl.setFont(scaled_font(FONT_BODY, 12))
        self._shards_lbl.setStyleSheet(f"color: {PALETTE['accent2']}; background: transparent; border: none;")
        hlay.addWidget(title_lbl)
        hlay.addStretch()
        hlay.addWidget(_shard_hdr_icon)
        hlay.addWidget(self._shards_lbl)
        hlay.addSpacing(12)
        hlay.addWidget(self._gold_lbl)
        root.addWidget(hdr)

        # ── Scrollable content ──────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")
        _setup_touch_scroll(scroll)
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        vlay = QVBoxLayout(container)
        vlay.setSpacing(8)
        vlay.setContentsMargins(14, 14, 14, 14)
        scroll.setWidget(container)
        root.addWidget(scroll)

        # Scroll hint overlay — positioned over the bottom of the scroll area
        self._scroll_hint = _ScrollHint(scroll, self)
        QTimer.singleShot(120, self._scroll_hint.start)

        # ============================================================
        # SECTION 1: TOOLS
        # ============================================================
        vlay.addWidget(self._section_header("TOOLS", PALETTE["accent"]))
        self._tool_cards: dict[str, "_ToolCard"] = {}
        for tool in TOOL_UPGRADES:
            card = _ToolCard(tool, state, self)
            vlay.addWidget(card)
            self._tool_cards[tool["id"]] = card

        # ============================================================
        # SECTION 2: SKILLS
        # ============================================================
        vlay.addSpacing(sz(24))
        vlay.addWidget(self._section_header("SKILLS", PALETTE["xp_color"]))
        self._skill_cards: dict[str, "_SkillDetailCard"] = {}
        for skill_id, skill_def in SKILLS.items():
            card = _SkillDetailCard(skill_id, skill_def, state, self)
            vlay.addWidget(card)
            self._skill_cards[skill_id] = card

        # ============================================================
        # SECTION 3: RUNIC FORGE
        # ============================================================
        vlay.addSpacing(sz(24))
        vlay.addWidget(self._section_header("RUNES", PALETTE["prestige"]))
        self._rune_cards: dict[str, "_RunicCard"] = {}
        for rup in RUNIC_UPGRADES:
            card = _RunicCard(rup, state, self)
            vlay.addWidget(card)
            self._rune_cards[rup["id"]] = card

        vlay.addStretch()

        BUS.gold_changed.connect(self.refresh)
        BUS.xp_changed.connect(lambda *_: self.refresh())
        BUS.inventory_changed.connect(self.refresh)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_scroll_hint") and not self._scroll_hint._gone:
            self._scroll_hint._reposition()

    @staticmethod
    def _section_header(text: str, color: str) -> QWidget:
        frame = QFrame()
        frame.setFixedHeight(sz(44))
        frame.setStyleSheet(f"""
            QFrame {{
                background: {PALETTE['bg_light']};
                border-left: 3px solid {color};
                border-top: none; border-right: none; border-bottom: none;
                border-radius: 0px;
            }}
        """)
        lay = QHBoxLayout(frame)
        lay.setContentsMargins(14, 0, 14, 0)
        lbl = QLabel(text)
        lbl.setFont(scaled_font(FONT_TITLE, 12, bold=True))
        lbl.setStyleSheet(f"color: {PALETTE['text_primary']}; background: transparent; border: none;")
        make_shadow(lbl, blur=0, color="#000000", opacity=0, offset=(0, 0))
        lay.addWidget(lbl)
        return frame

    def refresh(self):
        if not self.isVisible():
            return
        self._gold_lbl.setText(f"{COIN_HTML}{self._state.gold:.0f}")
        shards = self._state.special_items.get("runicShard", 0)
        self._shards_lbl.setText(f"{shards} shards")
        for card in self._tool_cards.values():
            card.refresh()
        for card in self._skill_cards.values():
            card.refresh()
        for card in self._rune_cards.values():
            card.refresh()


def _btn_style(bg: str, fg: str, hover: str = "") -> str:
    hover_part = f"QPushButton:hover {{ background: {hover}; }}" if hover else ""
    return f"""
        QPushButton {{
            background: {bg};
            color: {fg};
            border: none;
            border-radius: 8px;
            font-weight: bold;
        }}
        {hover_part}
    """


class _ToolCard(QFrame):
    """Upgrade card for a single tool (10 tiers, costs gold)."""
    _ICON_SIZE = 52

    def __init__(self, tool: dict, state: GameState, parent=None):
        super().__init__(parent)
        self._tool = tool
        self._state = state
        self.setMinimumHeight(86)
        self.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {PALETTE['bg_card']}, stop:1 {PALETTE['bg_light']});
                border: 1px solid {PALETTE['border']};
                border-radius: 14px;
            }}
        """)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(12)

        # --- icon widget (animated SpriteWidget or static QLabel) ---
        n_frames = tool.get("sprite_frames", 0)
        if n_frames > 1:
            frames = load_sprite_sheet(
                tool["sprite"], tool["sprite_fw"], tool["sprite_fh"], n_frames
            )
            scaled = [f.scaled(self._ICON_SIZE, self._ICON_SIZE,
                               Qt.KeepAspectRatio, Qt.SmoothTransformation)
                      for f in frames]
            self._icon_widget: QWidget = SpriteWidget(scaled, tool["sprite_delay"],
                                                      loop=True, parent=self)
            self._icon_widget.setFixedSize(self._ICON_SIZE, self._ICON_SIZE)
            self._icon_widget.play()
            self._icon_is_sprite = False   # no tier swap needed
        else:
            self._icon_widget = QLabel(self)
            self._icon_widget.setFixedSize(self._ICON_SIZE, self._ICON_SIZE)
            self._icon_widget.setAlignment(Qt.AlignCenter)
            self._icon_widget.setStyleSheet("background: transparent; border: none;")
            self._icon_is_sprite = "{tier}" in tool.get("sprite", "")
        lay.addWidget(self._icon_widget)

        info = QVBoxLayout()
        info.setSpacing(1)
        name_lbl = QLabel(tool["name"])
        name_lbl.setFont(scaled_font(FONT_BODY, 11, bold=True))
        name_lbl.setStyleSheet(f"color: {PALETTE['text_primary']}; background: transparent; border: none;")
        desc_lbl = QLabel(tool["desc"])
        desc_lbl.setFont(scaled_font(FONT_BODY, 9))
        desc_lbl.setStyleSheet(f"color: {PALETTE['text_muted']}; background: transparent; border: none;")
        self._tier_lbl = QLabel()
        self._tier_lbl.setFont(scaled_font(FONT_MONO, 9))
        self._tier_lbl.setStyleSheet(f"color: {PALETTE['xp_color']}; background: transparent; border: none;")
        info.addWidget(name_lbl)
        info.addWidget(desc_lbl)
        info.addWidget(self._tier_lbl)
        lay.addLayout(info)
        lay.addStretch()

        right = QVBoxLayout()
        right.setSpacing(4)
        right.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._cost_lbl = QLabel()
        self._cost_lbl.setFont(scaled_font(FONT_MONO, 9, bold=True))
        self._cost_lbl.setAlignment(Qt.AlignRight)
        self._cost_lbl.setStyleSheet(f"color: {PALETTE['gold']}; background: transparent; border: none;")
        self._btn = QPushButton("Upgrade")
        self._btn.setFont(scaled_font(FONT_BODY, 10, bold=True))
        self._btn.setFixedSize(sz(96), sz(38))
        self._btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._btn.clicked.connect(self._buy)
        right.addWidget(self._cost_lbl)
        right.addWidget(self._btn)
        lay.addLayout(right)
        make_shadow(self, blur=10, opacity=70)
        self.refresh()

    def _update_icon(self, tier: int):
        """Update static icon label to reflect current tier."""
        if not isinstance(self._icon_widget, QLabel):
            return
        sprite_tmpl = self._tool.get("sprite", "")
        if self._icon_is_sprite:
            # tiered: replace {tier} with max(1, tier) so tier-0 shows T1
            filename = sprite_tmpl.replace("{tier}", str(max(1, tier)))
        else:
            filename = sprite_tmpl
        px = load_image(filename)
        if px:
            self._icon_widget.setPixmap(
                px.scaled(self._ICON_SIZE, self._ICON_SIZE,
                          Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        else:
            # fallback: emoji
            self._icon_widget.setText(self._tool["icon"])
            self._icon_widget.setFont(scaled_font(FONT_BODY, 22))

    def refresh(self):
        tid = self._tool["id"]
        tier = self._state.get_tool_tier(tid)
        max_tier = self._tool["max_tier"]
        cost = self._state.get_tool_cost(tid)
        is_maxed = tier >= max_tier
        self._tier_lbl.setText(f"Tier {tier} / {max_tier}")
        self._update_icon(tier)
        if is_maxed:
            self._cost_lbl.setText("MAXED")
            self._btn.setText("✓ Max")
            self._btn.setEnabled(False)
            self._btn.setStyleSheet(f"""
                QPushButton {{
                    background: {PALETTE['bg_light']};
                    color: {PALETTE['success']};
                    border: 1px solid {PALETTE['success']}55;
                    border-radius: 10px; font-weight: bold;
                }}
            """)
            self.setStyleSheet(f"""
                QFrame {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 {PALETTE['bg_card']}, stop:1 {PALETTE['bg_light']});
                    border: 1px solid {PALETTE['success']}66;
                    border-radius: 14px;
                }}
            """)
        elif self._state.gold >= cost:
            self._cost_lbl.setText(f"{COIN_HTML}{cost:,}")
            self._btn.setText("Upgrade ▲")
            self._btn.setEnabled(True)
            self._btn.setStyleSheet(f"""
                QPushButton {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 {PALETTE['accent']}, stop:1 #B07820);
                    color: {PALETTE['bg_dark']};
                    border: none; border-radius: 10px; font-weight: bold;
                }}
                QPushButton:pressed {{ background: #906010; }}
            """)
        else:
            self._cost_lbl.setText(f"{COIN_HTML}{cost:,}")
            self._btn.setText("Upgrade")
            self._btn.setEnabled(False)
            self._btn.setStyleSheet(f"""
                QPushButton {{
                    background: {PALETTE['bg_light']};
                    color: {PALETTE['text_dim']};
                    border: 1px solid {PALETTE['border']};
                    border-radius: 10px; font-weight: bold;
                }}
            """)

    def _buy(self):
        cost = self._state.get_tool_cost(self._tool["id"])
        if self._state.apply_tool_upgrade(self._tool["id"]):
            BUS.gold_changed.emit()
            BUS.gold_delta.emit(-float(cost))
            self.refresh()
            _orig_ss = self.styleSheet()
            self.setStyleSheet(
                f"QFrame {{ background: {PALETTE['bg_card']}; border: 2px solid {PALETTE['success']}; border-radius: 12px; }}"
            )
            QTimer.singleShot(450, lambda: self.setStyleSheet(_orig_ss))


class _SkillDetailCard(QFrame):
    """Expandable skill card showing level, XP bar, and milestone list."""
    def __init__(self, skill_id: str, skill_def: dict, state: GameState, parent=None):
        super().__init__(parent)
        self._skill_id = skill_id
        self._skill_def = skill_def
        self._state = state
        self._expanded = False
        color = skill_def["color"]
        self.setStyleSheet(f"""
            QFrame {{
                background: {PALETTE['bg_card']};
                border: 1px solid {PALETTE['border']};
                border-left: 3px solid {color};
                border-radius: 14px;
            }}
        """)
        make_shadow(self, blur=10, opacity=70)

        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(14, 10, 14, 10)
        self._root.setSpacing(6)

        # Header row
        header = QHBoxLayout()
        icon_lbl = QLabel(skill_def["icon"])
        icon_lbl.setFont(scaled_font(FONT_BODY, 18))
        icon_lbl.setFixedWidth(28)
        icon_lbl.setStyleSheet("background: transparent; border: none;")
        name_lbl = QLabel(skill_def["name"])
        name_lbl.setFont(scaled_font(FONT_BODY, 11, bold=True))
        name_lbl.setStyleSheet(f"color: {PALETTE['text_primary']}; background: transparent; border: none;")
        self._level_lbl = QLabel()
        self._level_lbl.setFont(scaled_font(FONT_TITLE, 12, bold=True))
        self._level_lbl.setStyleSheet(f"color: {skill_def['color']}; background: transparent; border: none;")
        self._expand_btn = QPushButton("▶")
        self._expand_btn.setFont(scaled_font(FONT_BODY, 10))
        self._expand_btn.setFixedSize(26, 26)
        self._expand_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._expand_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {PALETTE['text_dim']};
                border: none; border-radius: 4px;
            }}
            QPushButton:hover {{ color: {PALETTE['text_primary']}; }}
        """)
        self._expand_btn.clicked.connect(self._toggle)
        header.addWidget(icon_lbl)
        header.addWidget(name_lbl)
        header.addStretch()
        header.addWidget(self._level_lbl)
        header.addWidget(self._expand_btn)
        self._root.addLayout(header)

        # XP bar
        self._xp_bar = QProgressBar()
        self._xp_bar.setRange(0, 100)
        self._xp_bar.setValue(0)
        self._xp_bar.setTextVisible(False)
        self._xp_bar.setFixedHeight(8)
        self._xp_bar.setStyleSheet(f"""
            QProgressBar {{ background: {PALETTE['bg_light']}; border: none; border-radius: 4px; }}
            QProgressBar::chunk {{ background: {skill_def['color']}; border-radius: 4px; }}
        """)
        self._root.addWidget(self._xp_bar)
        self._xp_lbl = QLabel()
        self._xp_lbl.setFont(scaled_font(FONT_MONO, 8))
        self._xp_lbl.setStyleSheet(f"color: {PALETTE['text_dim']}; background: transparent; border: none;")
        self._root.addWidget(self._xp_lbl)

        # Milestones (collapsed by default)
        self._mile_widget = QWidget()
        self._mile_widget.setStyleSheet("background: transparent;")
        mile_lay = QVBoxLayout(self._mile_widget)
        mile_lay.setSpacing(3)
        mile_lay.setContentsMargins(0, 4, 0, 0)
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color: {PALETTE['border']}; background: {PALETTE['border']}; border: none; max-height: 1px;")
        mile_lay.addWidget(sep)
        self._milestone_rows: list[tuple] = []
        for threshold in SKILL_THRESHOLDS.get(skill_id, []):
            row = QHBoxLayout()
            badge = QLabel(f"Lv {threshold['level']}")
            badge.setFont(scaled_font(FONT_MONO, 8, bold=True))
            badge.setFixedWidth(42)
            badge.setAlignment(Qt.AlignCenter)
            dlbl = QLabel(threshold["desc"])
            dlbl.setFont(scaled_font(FONT_BODY, 8))
            dlbl.setWordWrap(True)
            row.addWidget(badge)
            row.addWidget(dlbl)
            row.addStretch()
            mile_lay.addLayout(row)
            self._milestone_rows.append((threshold["level"], badge, dlbl))
        self._root.addWidget(self._mile_widget)
        self._mile_widget.hide()

        self.refresh()

    def _toggle(self):
        self._expanded = not self._expanded
        self._mile_widget.setVisible(self._expanded)
        self._expand_btn.setText("▼" if self._expanded else "▶")

    def refresh(self):
        sk = self._state.skills.get(self._skill_id, SkillState())
        lvl = sk.level
        pct = int(sk.xp_in_level / max(sk.xp_needed_for_level, 1) * 100)
        self._xp_bar.setValue(pct)
        if lvl >= 100:
            self._level_lbl.setText("Lv 100 MAX")
            self._xp_lbl.setText(f"Total: {sk.xp:,} XP")
        else:
            self._level_lbl.setText(f"Lv {lvl}")
            self._xp_lbl.setText(f"{sk.xp_in_level:,} / {sk.xp_needed_for_level:,} XP")
        color = self._skill_def["color"]
        for req_lvl, badge, dlbl in self._milestone_rows:
            unlocked = lvl >= req_lvl
            if unlocked:
                badge.setStyleSheet(f"color: {color}; background: transparent; border: 1px solid {color}; border-radius: 3px;")
                dlbl.setStyleSheet(f"color: {PALETTE['text_primary']}; background: transparent; border: none;")
            else:
                badge.setStyleSheet(f"color: {PALETTE['text_dim']}; background: transparent; border: 1px solid {PALETTE['text_dim']}; border-radius: 3px;")
                dlbl.setStyleSheet(f"color: {PALETTE['text_dim']}; background: transparent; border: none;")


class _RunicCard(QFrame):
    """Upgrade card for a Runic Forge upgrade (costs Runic Shards, permanent)."""
    def __init__(self, rup: dict, state: GameState, parent=None):
        super().__init__(parent)
        self._rup = rup
        self._state = state
        self.setMinimumHeight(86)
        self.setStyleSheet(f"""
            QFrame {{
                background: {PALETTE['bg_card']};
                border: 1px solid {PALETTE['border']};
                border-left: 3px solid {PALETTE['prestige']};
                border-radius: 14px;
            }}
        """)
        make_shadow(self, blur=10, opacity=70)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(12)

        icon = QLabel()
        icon.setFixedSize(34, 34)
        icon.setStyleSheet("background: transparent; border: none;")
        _shard_px = load_image("runicShard.png")
        if _shard_px:
            icon.setPixmap(_shard_px.scaled(34, 34, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            icon.setText("🔮")
            icon.setFont(scaled_font(FONT_BODY, 20))
        lay.addWidget(icon)

        info = QVBoxLayout()
        info.setSpacing(1)
        name_lbl = QLabel(rup["name"])
        name_lbl.setFont(scaled_font(FONT_BODY, 11, bold=True))
        name_lbl.setStyleSheet(f"color: {PALETTE['prestige']}; background: transparent; border: none;")
        desc_lbl = QLabel(rup["desc"])
        desc_lbl.setFont(scaled_font(FONT_BODY, 9))
        desc_lbl.setStyleSheet(f"color: {PALETTE['text_muted']}; background: transparent; border: none;")
        self._tier_lbl = QLabel()
        self._tier_lbl.setFont(scaled_font(FONT_MONO, 9))
        self._tier_lbl.setStyleSheet(f"color: {PALETTE['accent2']}; background: transparent; border: none;")
        info.addWidget(name_lbl)
        info.addWidget(desc_lbl)
        info.addWidget(self._tier_lbl)
        lay.addLayout(info)
        lay.addStretch()

        right = QVBoxLayout()
        right.setSpacing(4)
        right.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._cost_lbl = QLabel()
        self._cost_lbl.setFont(scaled_font(FONT_MONO, 9, bold=True))
        self._cost_lbl.setAlignment(Qt.AlignRight)
        self._cost_lbl.setStyleSheet(f"color: {PALETTE['accent2']}; background: transparent; border: none;")
        self._btn = QPushButton("Forge")
        self._btn.setFont(scaled_font(FONT_BODY, 10, bold=True))
        self._btn.setFixedSize(sz(90), sz(38))
        self._btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._btn.clicked.connect(self._forge)
        right.addWidget(self._cost_lbl)
        right.addWidget(self._btn)
        lay.addLayout(right)
        self.refresh()

    def refresh(self):
        rid = self._rup["id"]
        tier = self._state.get_runic_tier(rid)
        max_tier = self._rup["max_tier"]
        cost = self._state.get_runic_cost(rid)
        shards = self._state.special_items.get("runicShard", 0)
        is_maxed = tier >= max_tier
        self._tier_lbl.setText(f"Tier {tier} / {max_tier}  (Permanent)")
        if is_maxed:
            self._cost_lbl.setText("MAXED")
            self._btn.setText("✓ Max")
            self._btn.setEnabled(False)
            self._btn.setStyleSheet(f"""
                QPushButton {{
                    background: {PALETTE['bg_light']};
                    color: {PALETTE['success']};
                    border: 1px solid {PALETTE['success']}55;
                    border-radius: 10px; font-weight: bold;
                }}
            """)
        elif shards >= cost:
            self._cost_lbl.setText(f"{cost} shards")
            self._btn.setText("⚒ Forge")
            self._btn.setEnabled(True)
            self._btn.setStyleSheet(f"""
                QPushButton {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 {PALETTE['prestige']}, stop:1 #9050C0);
                    color: white;
                    border: none; border-radius: 10px; font-weight: bold;
                }}
                QPushButton:pressed {{ background: #7030A0; }}
            """)
        else:
            self._cost_lbl.setText(f"{cost} shards")
            self._btn.setText("Forge")
            self._btn.setEnabled(False)
            self._btn.setStyleSheet(f"""
                QPushButton {{
                    background: {PALETTE['bg_light']};
                    color: {PALETTE['text_dim']};
                    border: 1px solid {PALETTE['border']};
                    border-radius: 10px; font-weight: bold;
                }}
            """)

    def _forge(self):
        cost = self._state.get_runic_cost(self._rup["id"])
        if self._state.apply_runic_upgrade(self._rup["id"]):
            BUS.inventory_changed.emit()
            BUS.shard_delta.emit(-cost)
            self.refresh()
            _orig_ss = self.styleSheet()
            self.setStyleSheet(
                f"QFrame {{ background: {PALETTE['bg_card']}; border: 2px solid {PALETTE['gold']}; border-radius: 12px; }}"
            )
            QTimer.singleShot(450, lambda: self.setStyleSheet(_orig_ss))


# ---------------------------------------------------------------------------
# PAGE: PRESTIGE
# ---------------------------------------------------------------------------
class PrestigePage(QWidget):
    def __init__(self, state: GameState, parent=None):
        super().__init__(parent)
        self._state = state
        self.setStyleSheet("background: transparent;")
        self._selected_prestige_count = 1
        self._coin_rows: list = []

        # Outer scroll so everything fits on small screens
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")
        _setup_touch_scroll(scroll)
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        root = QVBoxLayout(content)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)
        scroll.setWidget(content)
        outer.addWidget(scroll)

        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        title_row.setContentsMargins(0, 0, 0, 0)
        _title_px = load_image("prestigeStatic.png")
        if _title_px:
            t_ico = QLabel()
            t_ico.setPixmap(_title_px.scaled(sz(26), sz(26), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            t_ico.setStyleSheet("background: transparent; border: none;")
            title_row.addWidget(t_ico)
        title = QLabel("  Prestige")
        title.setFont(scaled_font(FONT_TITLE, 20, bold=True))
        title.setStyleSheet(f"color: {PALETTE['prestige']}; background: transparent; border: none;")
        title_row.addWidget(title)
        title_row.addStretch()
        root.addLayout(title_row)

        # ── Hero status card ───────────────────────────────────────────
        hero = QFrame()
        hero.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1A1032, stop:1 #261848);
                border: 2px solid {PALETTE['prestige']};
                border-radius: 20px;
            }}
        """)
        make_shadow(hero, blur=32, color=PALETTE["prestige"], opacity=90)
        hero_lay = QVBoxLayout(hero)
        hero_lay.setContentsMargins(20, 18, 20, 18)
        hero_lay.setSpacing(10)

        # Top row: tier label + coin badge
        tier_row = QHBoxLayout()
        tier_row.setSpacing(10)
        tier_icon_lbl = QLabel()
        _tier_ico_px = load_image("prestigeStatic.png")
        if _tier_ico_px:
            tier_icon_lbl.setPixmap(_tier_ico_px.scaled(sz(32), sz(32), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        tier_icon_lbl.setStyleSheet("background: transparent; border: none;")
        self._tier_lbl = QLabel()
        self._tier_lbl.setFont(scaled_font(FONT_TITLE, 22, bold=True))
        self._tier_lbl.setStyleSheet(f"color: {PALETTE['text_primary']}; background: transparent; border: none;")
        tier_row.addWidget(tier_icon_lbl)
        tier_row.addWidget(self._tier_lbl)
        tier_row.addStretch()

        # Coin badge pill
        coin_pill = QFrame()
        coin_pill.setStyleSheet(f"""
            QFrame {{
                background: {PALETTE['bg_dark']};
                border: 1px solid {PALETTE['gold']};
                border-radius: 14px;
            }}
        """)
        pill_lay = QHBoxLayout(coin_pill)
        pill_lay.setContentsMargins(12, 5, 12, 5)
        pill_lay.setSpacing(5)
        pill_icon = QLabel()
        _coin_pill_px = load_image("prestigeCoinStatic.png")
        if _coin_pill_px:
            pill_icon.setPixmap(_coin_pill_px.scaled(sz(24), sz(24), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        pill_icon.setStyleSheet("background: transparent; border: none;")
        self._coins_lbl = QLabel()
        self._coins_lbl.setFont(scaled_font(FONT_BODY, 13, bold=True))
        self._coins_lbl.setStyleSheet(f"color: {PALETTE['gold']}; background: transparent; border: none;")
        pill_coin_sub = QLabel("coins")
        pill_coin_sub.setFont(scaled_font(FONT_BODY, 10))
        pill_coin_sub.setStyleSheet(f"color: {PALETTE['text_muted']}; background: transparent; border: none;")
        pill_lay.addWidget(pill_icon)
        pill_lay.addWidget(self._coins_lbl)
        pill_lay.addWidget(pill_coin_sub)
        tier_row.addWidget(coin_pill)
        hero_lay.addLayout(tier_row)

        # Divider
        hdiv = QFrame()
        hdiv.setFrameShape(QFrame.HLine)
        hdiv.setStyleSheet(f"background: {PALETTE['border']}; border: none; max-height: 1px;")
        hero_lay.addWidget(hdiv)

        self._cost_lbl = QLabel()
        self._cost_lbl.setFont(scaled_font(FONT_BODY, 11))
        self._cost_lbl.setStyleSheet(f"color: {PALETTE['text_muted']}; background: transparent; border: none;")
        self._multi_hint_lbl = QLabel()
        self._multi_hint_lbl.setFont(scaled_font(FONT_BODY, 10, bold=True))
        self._multi_hint_lbl.setStyleSheet(f"color: {PALETTE['accent2']}; background: transparent; border: none;")
        hero_lay.addWidget(self._cost_lbl)
        hero_lay.addWidget(self._multi_hint_lbl)

        # Progress bar toward next prestige threshold
        self._next_bar = QProgressBar()
        self._next_bar.setRange(0, 100)
        self._next_bar.setValue(0)
        self._next_bar.setTextVisible(False)
        self._next_bar.setFixedHeight(sz(12))
        self._next_bar.setStyleSheet(f"""
            QProgressBar {{ background: {PALETTE['bg_light']}; border: none; border-radius: {sz(6)}px; }}
            QProgressBar::chunk {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #7020B8, stop:1 {PALETTE['prestige']}); border-radius: {sz(6)}px; }}
        """)
        hero_lay.addWidget(self._next_bar)
        root.addWidget(hero)

        # ── What resets / what persists ───────────────────────────────
        rp_row = QHBoxLayout()
        rp_row.setSpacing(10)

        reset_card = QFrame()
        reset_card.setStyleSheet(f"""
            QFrame {{
                background: {PALETTE['bg_card']};
                border: 1px solid #7A3030;
                border-radius: 14px;
            }}
        """)
        rc_lay = QVBoxLayout(reset_card)
        rc_lay.setContentsMargins(14, 12, 14, 12)
        rc_lay.setSpacing(4)
        r_title = QLabel("🔄  Resets")
        r_title.setFont(scaled_font(FONT_BODY, 10, bold=True))
        r_title.setStyleSheet(f"color: {PALETTE['danger']}; background: transparent; border: none;")
        rc_lay.addWidget(r_title)
        for item in ("Gold", "Skills & XP", "Inventory", "Tool Upgrades", "Active Refining"):
            lbl = QLabel(f"  • {item}")
            lbl.setFont(scaled_font(FONT_BODY, 9))
            lbl.setStyleSheet(f"color: {PALETTE['text_muted']}; background: transparent; border: none;")
            rc_lay.addWidget(lbl)

        persist_card = QFrame()
        persist_card.setStyleSheet(f"""
            QFrame {{
                background: {PALETTE['bg_card']};
                border: 1px solid #307A50;
                border-radius: 14px;
            }}
        """)
        pc_lay = QVBoxLayout(persist_card)
        pc_lay.setContentsMargins(14, 12, 14, 12)
        pc_lay.setSpacing(4)
        p_title = QLabel("✅  Persists")
        p_title.setFont(scaled_font(FONT_BODY, 10, bold=True))
        p_title.setStyleSheet(f"color: {PALETTE['success']}; background: transparent; border: none;")
        pc_lay.addWidget(p_title)
        for item in ("Prestige Tier", "Prestige Coins", "Prestige Bonuses", "Runic Upgrades"):
            lbl = QLabel(f"  • {item}")
            lbl.setFont(scaled_font(FONT_BODY, 9))
            lbl.setStyleSheet(f"color: {PALETTE['text_muted']}; background: transparent; border: none;")
            pc_lay.addWidget(lbl)

        rp_row.addWidget(reset_card)
        rp_row.addWidget(persist_card)
        root.addLayout(rp_row)

        # ── Prestige button ────────────────────────────────────────────
        self._prestige_btn = QPushButton("  Prestige Now")
        _prestige_btn_px = load_image("prestigeStatic.png")
        if _prestige_btn_px:
            self._prestige_btn.setIcon(QIcon(_prestige_btn_px))
            self._prestige_btn.setIconSize(QSize(sz(22), sz(22)))
        self._prestige_btn.setFont(scaled_font(FONT_TITLE, 15, bold=True))
        self._prestige_btn.setFixedHeight(60)
        self._prestige_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._prestige_btn.clicked.connect(self._do_prestige)
        root.addWidget(self._prestige_btn)

        # Pulsing glow on prestige button — active when the player can afford it
        self._prestige_glow_eff = QGraphicsDropShadowEffect(self._prestige_btn)
        self._prestige_glow_eff.setOffset(0, 0)
        _gc = QColor(PALETTE["prestige"])
        _gc.setAlpha(200)
        self._prestige_glow_eff.setColor(_gc)
        self._prestige_glow_eff.setBlurRadius(4)
        self._prestige_btn.setGraphicsEffect(self._prestige_glow_eff)
        _gfwd = QPropertyAnimation(self._prestige_glow_eff, b"blurRadius")
        _gfwd.setDuration(900)
        _gfwd.setStartValue(4)
        _gfwd.setEndValue(30)
        _gbck = QPropertyAnimation(self._prestige_glow_eff, b"blurRadius")
        _gbck.setDuration(900)
        _gbck.setStartValue(30)
        _gbck.setEndValue(4)
        self._glow_seq = QSequentialAnimationGroup(self)
        self._glow_seq.addAnimation(_gfwd)
        self._glow_seq.addAnimation(_gbck)
        self._glow_seq.setLoopCount(-1)
        self._glow_active = False

        # ── Coin spend section ─────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color: {PALETTE['border']}; background: {PALETTE['border']}; border: none; max-height: 1px;")
        root.addWidget(sep)

        coin_header_row = QHBoxLayout()
        _coin_hdr_px = load_image("prestigeCoinStatic.png")
        if _coin_hdr_px:
            _coin_hdr_ico = QLabel()
            _coin_hdr_ico.setPixmap(_coin_hdr_px.scaled(sz(18), sz(18), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            _coin_hdr_ico.setStyleSheet("background: transparent; border: none;")
            coin_header_row.addWidget(_coin_hdr_ico)
        coin_title_lbl = QLabel("  Spend Prestige Coins")
        coin_title_lbl.setFont(scaled_font(FONT_TITLE, 13, bold=True))
        coin_title_lbl.setStyleSheet(f"color: {PALETTE['text_primary']}; background: transparent; border: none;")
        coin_header_row.addWidget(coin_title_lbl)
        coin_header_row.addStretch()
        self._coins_avail_lbl = QLabel()
        self._coins_avail_lbl.setFont(scaled_font(FONT_BODY, 10))
        self._coins_avail_lbl.setStyleSheet(f"color: {PALETTE['text_muted']}; background: transparent; border: none;")
        coin_header_row.addWidget(self._coins_avail_lbl)
        root.addLayout(coin_header_row)

        for bonus in PRESTIGE_BONUS_DEFS:
            row = self._make_coin_row(bonus["id"], bonus["label"], bonus["desc"])
            root.addWidget(row)

        root.addStretch()
        BUS.gold_changed.connect(self.refresh)
        BUS.prestige_changed.connect(self.refresh)
        self.refresh()

        # ── Inline confirmation overlay (no separate window) ───────────
        self._confirm_overlay = QWidget(self)
        self._confirm_overlay.setStyleSheet("background: rgba(0,0,0,0);")
        self._confirm_overlay.hide()
        _ov_lay = QVBoxLayout(self._confirm_overlay)
        _ov_lay.setContentsMargins(0, 0, 0, 0)
        _ov_lay.setAlignment(Qt.AlignCenter)

        _card = QFrame(self._confirm_overlay)
        _card.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1A1032, stop:1 #261848);
                border: 2px solid {PALETTE['prestige']};
                border-radius: 20px;
            }}
        """)
        make_shadow(_card, blur=40, color=PALETTE["prestige"], opacity=120)
        _card_lay = QVBoxLayout(_card)
        _card_lay.setContentsMargins(sz(45), sz(38), sz(45), sz(38))
        _card_lay.setSpacing(sz(22))

        _conf_title = QLabel("Confirm Prestige")
        _conf_title.setFont(scaled_font(FONT_TITLE, 26, bold=True))
        _conf_title.setStyleSheet(f"color: {PALETTE['prestige']}; background: transparent; border: none;")
        _conf_title.setAlignment(Qt.AlignCenter)
        _card_lay.addWidget(_conf_title)

        self._conf_detail_lbl = QLabel()
        self._conf_detail_lbl.setFont(scaled_font(FONT_BODY, 18))
        self._conf_detail_lbl.setStyleSheet(f"color: {PALETTE['text_primary']}; background: transparent; border: none;")
        self._conf_detail_lbl.setAlignment(Qt.AlignCenter)
        self._conf_detail_lbl.setWordWrap(True)
        _card_lay.addWidget(self._conf_detail_lbl)

        _warn = QLabel("Resets: Gold · Skills · Inventory · Tools · Active Refining")
        _warn.setFont(scaled_font(FONT_BODY, 14))
        _warn.setStyleSheet(f"color: {PALETTE['danger']}; background: transparent; border: none;")
        _warn.setAlignment(Qt.AlignCenter)
        _warn.setWordWrap(True)
        _card_lay.addWidget(_warn)

        _btn_row = QHBoxLayout()
        _btn_row.setSpacing(sz(16))
        _cancel_btn = QPushButton("Cancel")
        _cancel_btn.setFont(scaled_font(FONT_BODY, 19, bold=True))
        _cancel_btn.setFixedHeight(sz(77))
        _cancel_btn.setCursor(QCursor(Qt.PointingHandCursor))
        _cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: {PALETTE['bg_light']};
                color: {PALETTE['text_primary']};
                border: 1px solid {PALETTE['border']};
                border-radius: 12px;
            }}
            QPushButton:hover {{ background: {PALETTE['bg_card']}; }}
        """)
        _cancel_btn.clicked.connect(lambda: self._confirm_overlay.hide())

        _go_btn = QPushButton("✓  Prestige!")
        _go_btn.setFont(scaled_font(FONT_TITLE, 21, bold=True))
        _go_btn.setFixedHeight(sz(77))
        _go_btn.setCursor(QCursor(Qt.PointingHandCursor))
        _go_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #7020B8, stop:1 #9848E0);
                color: white;
                border: none;
                border-radius: 12px;
            }}
            QPushButton:hover {{ background: #A060E0; }}
        """)
        _go_btn.clicked.connect(self._confirm_prestige)
        _btn_row.addWidget(_cancel_btn)
        _btn_row.addWidget(_go_btn)
        _card_lay.addLayout(_btn_row)

        _ov_lay.addWidget(_card)
        self._confirm_overlay.raise_()

    def _make_coin_row(self, bonus_id: str, label: str, desc: str) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background: {PALETTE['bg_card']};
                border: 1px solid {PALETTE['border']};
                border-radius: 14px;
            }}
        """)
        lay = QHBoxLayout(frame)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(12)

        info = QVBoxLayout()
        info.setSpacing(2)
        lbl = QLabel(label)
        lbl.setFont(scaled_font(FONT_BODY, 11, bold=True))
        lbl.setStyleSheet(f"color: {PALETTE['text_primary']}; background: transparent; border: none;")
        dlbl = QLabel(desc)
        dlbl.setFont(scaled_font(FONT_BODY, 9))
        dlbl.setWordWrap(True)
        dlbl.setStyleSheet(f"color: {PALETTE['text_muted']}; background: transparent; border: none;")
        info.addWidget(lbl)
        info.addWidget(dlbl)
        lay.addLayout(info, stretch=1)

        # Stack badge
        stack_badge = QFrame()
        stack_badge.setFixedSize(44, 36)
        stack_badge.setStyleSheet(f"""
            QFrame {{
                background: {PALETTE['bg_dark']};
                border: 1px solid {PALETTE['prestige']};
                border-radius: 10px;
            }}
        """)
        badge_lay = QVBoxLayout(stack_badge)
        badge_lay.setContentsMargins(0, 0, 0, 0)
        stacks_lbl = QLabel("0")
        stacks_lbl.setFont(scaled_font(FONT_MONO, 12, bold=True))
        stacks_lbl.setAlignment(Qt.AlignCenter)
        stacks_lbl.setStyleSheet(f"color: {PALETTE['prestige']}; background: transparent; border: none;")
        badge_lay.addWidget(stacks_lbl)
        lay.addWidget(stack_badge)

        # Quantity controls
        _qty_ctrl = QWidget()
        _qty_ctrl.setStyleSheet("background: transparent;")
        _qty_lay = QHBoxLayout(_qty_ctrl)
        _qty_lay.setContentsMargins(0, 0, 0, 0)
        _qty_lay.setSpacing(2)
        def _qbtn(txt: str) -> QPushButton:
            b = QPushButton(txt)
            b.setFont(scaled_font(FONT_BODY, 11, bold=True))
            b.setFixedSize(sz(26), sz(30))
            b.setCursor(QCursor(Qt.PointingHandCursor))
            b.setStyleSheet(f"""
                QPushButton {{
                    background: {PALETTE['bg_light']};
                    color: {PALETTE['text_muted']};
                    border: 1px solid {PALETTE['border']};
                    border-radius: 6px;
                }}
                QPushButton:pressed {{ background: {PALETTE['bg_card']}; }}
            """)
            return b
        _qty_minus = _qbtn("\u2212")
        _qty_spin = QSpinBox()
        _qty_spin.setRange(1, 9999)
        _qty_spin.setValue(1)
        _qty_spin.setFixedSize(sz(46), sz(30))
        _qty_spin.setAlignment(Qt.AlignCenter)
        _qty_spin.setFont(scaled_font(FONT_MONO, 9, bold=True))
        _qty_spin.setStyleSheet(f"""
            QSpinBox {{
                background: {PALETTE['bg_dark']};
                color: {PALETTE['prestige']};
                border: 1px solid {PALETTE['border']};
                border-radius: 6px;
                padding: 1px 2px;
            }}
            QSpinBox::up-button, QSpinBox::down-button {{ width: 0; }}
        """)
        _qty_spin.lineEdit().setReadOnly(True)
        _qty_spin.lineEdit().setFocusPolicy(Qt.NoFocus)
        _qty_plus = _qbtn("+")
        _qty_minus.clicked.connect(lambda: _qty_spin.setValue(max(1, _qty_spin.value() - 1)))
        _qty_plus.clicked.connect(lambda: _qty_spin.setValue(_qty_spin.value() + 1))
        _qty_lay.addWidget(_qty_minus)
        _qty_lay.addWidget(_qty_spin)
        _qty_lay.addWidget(_qty_plus)
        lay.addWidget(_qty_ctrl)

        btn = QPushButton("  Spend")
        _btn_coin_px = load_image("prestigeCoinStatic.png")
        if _btn_coin_px:
            btn.setIcon(QIcon(_btn_coin_px))
            btn.setIconSize(QSize(sz(16), sz(16)))
        btn.setFont(scaled_font(FONT_BODY, 10, bold=True))
        btn.setFixedSize(100, 36)
        btn.setCursor(QCursor(Qt.PointingHandCursor))
        btn.setStyleSheet(f"""
            QPushButton {{
                background: {PALETTE['prestige']};
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background: #A060E0; }}
            QPushButton:disabled {{ background: {PALETTE['text_dim']}; color: {PALETTE['bg_mid']}; }}
        """)
        btn.clicked.connect(lambda _=False, bid=bonus_id, qs=_qty_spin: self._spend_coin(bid, qs.value()))

        frame._stacks_lbl = stacks_lbl
        frame._qty_spin = _qty_spin
        frame._btn = btn
        frame._bonus_id = bonus_id
        lay.addWidget(btn)
        self._coin_rows.append(frame)
        return frame

    def _spend_coin(self, bonus_id: str, count: int = 1) -> None:
        spent = self._state.spend_prestige_coins(bonus_id, count)
        if spent > 0:
            self._state.save()
            BUS.prestige_changed.emit()

    def refresh(self):
        tier = self._state.prestige_tier
        coins = self._state.prestige_coins
        max_count = self._state.max_consecutive_prestiges()
        self._selected_prestige_count = max_count
        can = max_count >= 1
        cost = self._state.total_prestige_cost(max_count) if can else 0

        self._tier_lbl.setText(f"Tier  {tier}")
        self._coins_lbl.setText(str(coins))
        self._coins_avail_lbl.setText(f"{coins} available")

        # Progress bar toward next threshold
        # When the player can already afford prestiges, show progress toward
        # the first threshold they CANNOT yet reach (after exhausting all they can).
        if max_count > 0:
            spent = self._state.total_prestige_cost(max_count)
            remaining = max(0.0, self._state.gold - spent)
            next_tier_cost = self._state.prestige_cost_for_tier(self._state.prestige_tier + max_count)
            pct = min(100, int(remaining / max(1, next_tier_cost) * 100))
        else:
            next_cost = self._state.prestige_cost()
            pct = min(100, int(self._state.gold / max(1, next_cost) * 100))
        self._next_bar.setValue(pct)

        if can:
            earned = self._state.coins_for_prestige_count(max_count)
            self._cost_lbl.setText(
                f"Max prestige: {max_count}×  —  costs {fmt_number(cost)} {COIN_HTML}"
            )
            self._multi_hint_lbl.setText(
                f"⚡ Earn {earned} prestige coin{'s' if earned != 1 else ''}!"
            )
        else:
            self._cost_lbl.setText(
                f"Next prestige: {fmt_number(next_tier_cost if max_count > 0 else self._state.prestige_cost())} {COIN_HTML}  "
                f"(have {fmt_number(self._state.gold)})"
            )
            self._multi_hint_lbl.setText("")

        self._prestige_btn.setEnabled(can)
        self._prestige_btn.setText(f"  Prestige  {max_count}×" if can else "  Prestige")
        if can:
            btn_bg = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7020B8, stop:1 #9848E0)"
            btn_hover = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #5A10A0, stop:1 #7A38C8)"
        else:
            btn_bg = PALETTE["text_dim"]
            btn_hover = PALETTE["text_dim"]
        self._prestige_btn.setStyleSheet(f"""
            QPushButton {{
                background: {btn_bg};
                color: white;
                border: none;
                border-radius: 16px;
                font-family: '{FONT_TITLE}';
                font-size: {int(15 * APP_SCALE)}pt;
                font-weight: bold;
            }}
            QPushButton:hover {{ background: {btn_hover}; }}
        """)

        # Pulse glow when affordable, stop when not
        if can and not self._glow_active:
            self._glow_seq.start()
            self._glow_active = True
        elif not can and self._glow_active:
            self._glow_seq.stop()
            self._prestige_glow_eff.setBlurRadius(4)
            self._glow_active = False

        for frame in self._coin_rows:
            bid = frame._bonus_id
            frame._stacks_lbl.setText(str(self._state.prestige_bonuses.get(bid, 0)))
            frame._btn.setEnabled(coins > 0)
            frame._qty_spin.setMaximum(max(1, coins))

    def _adjust_prestige_count(self, delta: int):
        max_count = max(1, self._state.max_consecutive_prestiges())
        self._selected_prestige_count = max(1, min(self._selected_prestige_count + delta, max_count))
        self.refresh()

    def _select_max_prestige(self):
        self._selected_prestige_count = max(1, self._state.max_consecutive_prestiges())
        self.refresh()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_confirm_overlay"):
            self._confirm_overlay.setGeometry(0, 0, self.width(), self.height())

    def _do_prestige(self):
        count = self._state.max_consecutive_prestiges()
        if count <= 0:
            return
        cost = self._state.total_prestige_cost(count)
        earned_coins = self._state.coins_for_prestige_count(count)
        self._conf_pending_count = count
        self._conf_detail_lbl.setText(
            f"Prestige {count} time{'s' if count != 1 else ''}?\n\n"
            f"Cost: {fmt_number(cost)} Gold\n"
            f"Earn: {earned_coins} prestige coin{'s' if earned_coins != 1 else ''}"
        )
        self._confirm_overlay.setGeometry(0, 0, self.width(), self.height())
        self._confirm_overlay.raise_()
        self._confirm_overlay.show()

    def _confirm_prestige(self):
        self._confirm_overlay.hide()
        count = getattr(self, "_conf_pending_count", 0)
        if count <= 0:
            return
        win = self.window()
        if hasattr(win, "execute_prestige"):
            win.execute_prestige(count)



# ---------------------------------------------------------------------------
# PAGE: SKILLS
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# ODOMETER WIDGET  (used by prestige overlay)
# ---------------------------------------------------------------------------
class _TierOdometer(QWidget):
    """Draws a tier number that slides upward like an old clock when changed."""
    all_done = Signal()

    def __init__(self, value: int, font: QFont, color: str, parent=None):
        super().__init__(parent)
        self._current = str(value)
        self._next = str(value)
        self._font = font
        self._color = QColor(color)
        self._slide = 0.0
        self._pending = []
        self._running = False
        self._anim = QPropertyAnimation(self, b"slide", self)
        self._anim.setDuration(380)
        self._anim.setEasingCurve(QEasingCurve.InOutCubic)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.finished.connect(self._on_anim_done)
        self._recalc_size()

    def _recalc_size(self):
        fm = QFontMetrics(self._font)
        self.setFixedSize(fm.horizontalAdvance("000") + sz(12), fm.height())

    def _get_slide(self) -> float:
        return self._slide

    def _set_slide(self, v: float):
        self._slide = v
        self.update()

    slide = Property(float, _get_slide, _set_slide)

    def setDisplayFont(self, font: QFont):
        self._font = font
        self._recalc_size()
        self.update()

    def setDisplayColor(self, color: str):
        self._color = QColor(color)
        self.update()

    def advanceTo(self, value: int):
        self._pending.append(str(value))
        if not self._running:
            self._start_next()

    def _start_next(self):
        if not self._pending:
            self.all_done.emit()
            return
        self._next = self._pending.pop(0)
        self._slide = 0.0
        self._running = True
        self._anim.start()

    def _on_anim_done(self):
        self._current = self._next
        self._slide = 0.0
        self._running = False
        self._start_next()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.TextAntialiasing)
        painter.setFont(self._font)
        painter.setPen(self._color)
        painter.setClipRect(self.rect())
        h = self.height()
        w = self.width()
        # current slides up and out; next slides up from below
        y_cur = int(-self._slide * h)
        y_nxt = int((1.0 - self._slide) * h)
        flags = Qt.AlignCenter
        if self._slide < 1.0:
            painter.drawText(QRect(0, y_cur, w, h), flags, self._current)
        if self._slide > 0.0:
            painter.drawText(QRect(0, y_nxt, w, h), flags, self._next)
        painter.end()


# ---------------------------------------------------------------------------
# PRESTIGE ANIMATION OVERLAY
# ---------------------------------------------------------------------------
class PrestigeAnimOverlay(QWidget):
    """Full-window overlay: prestige animation + rolling tier counter."""

    def __init__(self, parent: QWidget, old_tier: int, new_tier: int):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self._old_tier = old_tier
        self._new_tier = new_tier
        self._dismissable = False
        self.setGeometry(parent.rect())
        self.setStyleSheet(
            "background: qlineargradient(x1:0, y1:0, x2:0, y2:1,"
            " stop:0 rgba(10,5,25,218), stop:1 rgba(38,15,70,218));"
        )

        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(sz(10))
        lay.setContentsMargins(sz(20), sz(30), sz(20), sz(30))

        # ── Sprite ────────────────────────────────────────────────────
        frames = load_sprite_sheet("prestige.png", 640, 640, 36)
        if frames:
            target = min(sz(260), parent.width() - sz(60))
            frames = [f.scaled(target, target, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                      for f in frames]
            self._sprite = SpriteWidget(frames, delay_ms=100, loop=False)
            self._sprite.setFixedSize(target, target)
            self._sprite.animation_done.connect(self._on_sprite_done)
            lay.addWidget(self._sprite, alignment=Qt.AlignCenter)
        else:
            self._sprite = None

        # ── Tier counter (odometer, rolls up from old to new) ───────────
        _tier_font = scaled_font(FONT_TITLE, 36, bold=True)
        _tier_row_w = QWidget()
        _tier_row_w.setStyleSheet("background: transparent;")
        _tier_row_lay = QHBoxLayout(_tier_row_w)
        _tier_row_lay.setContentsMargins(0, 0, 0, 0)
        _tier_row_lay.setSpacing(sz(10))
        _tier_row_lay.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)

        self._tier_prefix_lbl = QLabel("TIER")
        self._tier_prefix_lbl.setFont(_tier_font)
        self._tier_prefix_lbl.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self._tier_prefix_lbl.setStyleSheet(
            f"color: {PALETTE['accent']}; background: transparent; border: none;"
        )
        _tier_row_lay.addWidget(self._tier_prefix_lbl)

        self._tier_odm = _TierOdometer(old_tier, _tier_font, PALETTE["accent"], self)
        self._tier_odm.all_done.connect(self._finish_roll)
        _tier_row_lay.addWidget(self._tier_odm)

        lay.addWidget(_tier_row_w, alignment=Qt.AlignCenter)

        # Small context label when multi-prestiging
        if new_tier - old_tier > 1:
            multi_lbl = QLabel(f"+{new_tier - old_tier} prestiges")
            multi_lbl.setFont(scaled_font(FONT_BODY, 10))
            multi_lbl.setAlignment(Qt.AlignCenter)
            multi_lbl.setStyleSheet(
                f"color: {PALETTE['text_muted']}; background: transparent; border: none;"
            )
            lay.addWidget(multi_lbl)

        # Tap-to-dismiss hint (shown after roll completes)
        self._hint_lbl = QLabel("Tap anywhere to dismiss")
        self._hint_lbl.setFont(scaled_font(FONT_BODY, 9))
        self._hint_lbl.setAlignment(Qt.AlignCenter)
        self._hint_lbl.setStyleSheet(
            f"color: {PALETTE['text_dim']}; background: transparent; border: none;"
        )
        self._hint_lbl.hide()
        lay.addWidget(self._hint_lbl)

        # ── Animations ────────────────────────────────────────────────
        # Overlay fade-out
        self._eff = QGraphicsOpacityEffect(self)
        self._eff.setOpacity(1.0)
        self.setGraphicsEffect(self._eff)
        self._fade_anim = QPropertyAnimation(self._eff, b"opacity", self)
        self._fade_anim.setDuration(700)
        self._fade_anim.setStartValue(1.0)
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.finished.connect(self.deleteLater)

        self.show()
        self.raise_()
        if self._sprite:
            self._sprite.play(loop=False)
        else:
            QTimer.singleShot(300, self._on_sprite_done)

    def _on_sprite_done(self):
        def _queue():
            if self._new_tier > self._old_tier:
                for t in range(self._old_tier + 1, self._new_tier + 1):
                    self._tier_odm.advanceTo(t)
            else:
                self._finish_roll()
        QTimer.singleShot(150, _queue)

    def _finish_roll(self):
        """Called by _TierOdometer.all_done when the last slide finishes."""
        _final_font = scaled_font(FONT_TITLE, 44, bold=True)
        self._tier_prefix_lbl.setFont(_final_font)
        self._tier_prefix_lbl.setStyleSheet(
            f"color: {PALETTE['prestige']}; background: transparent; border: none;"
        )
        self._tier_odm.setDisplayFont(_final_font)
        self._tier_odm.setDisplayColor(PALETTE["prestige"])
        self._dismissable = True
        self._hint_lbl.show()
        # Auto-dismiss after 2 seconds
        QTimer.singleShot(2000, self._start_fade)

    def _start_fade(self):
        if not self._dismissable:
            return
        self._dismissable = False   # prevent double-trigger
        self._fade_anim.start()

    def mousePressEvent(self, event):
        if self._dismissable:
            self._start_fade()


# ---------------------------------------------------------------------------
# MAIN WINDOW
# ---------------------------------------------------------------------------
class MainWindow(QMainWindow):
    TARGET_W = 432
    TARGET_H = 936   # ≈ 19.5:9

    def __init__(self):
        super().__init__()
        self.setWindowTitle("CraftIdle")
        self._state = GameState.load()
        self.setStyleSheet(f"QMainWindow {{ background: {PALETTE['bg_dark']}; }}")
        self.resize(self.TARGET_W, self.TARGET_H)

        # Central widget
        central = QWidget()
        self._central = central
        central.setStyleSheet("background: transparent;")
        self.setCentralWidget(central)
        main_lay = QVBoxLayout(central)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(0)

        # Parallax background — manual child of central, sits below the layout
        self._parallax = ParallaxBackground(central)
        self._parallax.setGeometry(central.rect())
        self._parallax.lower()
        # Mouse tracker — observes all app events so drag works everywhere
        self._parallax_tracker = _ParallaxMouseTracker(self._parallax, self)
        QApplication.instance().installEventFilter(self._parallax_tracker)

        # Header
        self._header = HeaderBar(self._state, self)
        self._header.settings_clicked.connect(self._open_settings)
        main_lay.addWidget(self._header)

        # Page stack
        self._stack = QStackedWidget()
        self._stack.setStyleSheet("background: transparent;")
        main_lay.addWidget(self._stack, stretch=1)

        # Pages
        self._gather_page    = GatherPage(self._state, self)
        self._refine_page    = RefinePage(self._state, self)
        self._items_page     = ItemsPage(self._state, self)
        self._upgrades_page  = UpgradesPage(self._state, self)
        self._prestige_page  = PrestigePage(self._state, self)

        for page in [
            self._gather_page,
            self._refine_page,
            self._items_page,
            self._upgrades_page,
            self._prestige_page,
        ]:
            self._stack.addWidget(page)

        # Settings overlay — floats above everything as a centered card
        self._settings_overlay = SettingsOverlay(self._state, central)

        # Snow overlay — child of _stack so it paints above page content
        self._snow_overlay = SnowWidget(self._stack)
        self._snow_overlay.setGeometry(self._stack.rect())
        self._snow_overlay.raise_()
        self._snow_overlay.show()  # showEvent will start timer when visible

        # Nav
        self._nav = NavBar(self)
        self._nav.tab_changed.connect(self._switch_page)
        main_lay.addWidget(self._nav)

        # Toast
        self._toast = Toast(self)
        self._toast.raise_()

        # Autosave
        self._save_timer = QTimer(self)
        self._save_timer.setInterval(AUTOSAVE_INTERVAL_MS)
        self._save_timer.timeout.connect(self._autosave)
        self._save_timer.start()

        # Connect bus
        BUS.refine_complete.connect(lambda sid, amt: self._toast.show_message(f"✓ Refined {amt} items!", PALETTE["accent2"]))
        BUS.node_hit.connect(lambda nid, success: None)
        BUS.gold_changed.connect(self._header._refresh)
        BUS.xp_changed.connect(lambda s, x: self._refresh_upgrades_page())
        BUS.level_up.connect(self._show_level_up_toast)
        BUS.gold_delta.connect(self._spawn_gold_float)
        BUS.shard_delta.connect(self._spawn_shard_float)

    def _refresh_upgrades_page(self):
        if self._stack.currentWidget() is self._upgrades_page:
            self._upgrades_page.refresh()

    def execute_prestige(self, count: int):
        count = max(1, min(count, self._state.max_consecutive_prestiges()))
        if count <= 0:
            return False
        old_tier = self._state.prestige_tier
        self._refine_page.cancel_all_refining()
        if not self._state.do_prestige(count):
            return False
        self._state.save()
        BUS.gold_changed.emit()
        BUS.inventory_changed.emit()
        BUS.prestige_changed.emit()
        self._gather_page.refresh()
        self._refine_page.refresh()
        self._items_page.refresh()
        self._upgrades_page.refresh()
        self._prestige_page.refresh()
        PrestigeAnimOverlay(self, old_tier, self._state.prestige_tier)
        # Notify player of newly accessible resource nodes
        new_tier = self._state.prestige_tier
        unlocked_names = [
            nd["name"]
            for nid, nd in RESOURCE_NODES.items()
            if old_tier < nd.get("prestige_req", 0) <= new_tier
        ]
        if unlocked_names:
            QTimer.singleShot(
                2200,
                lambda names=unlocked_names: self._toast.show_message(
                    f"Unlocked: {', '.join(names)}!", PALETTE["success"]
                ),
            )
        return True

    def _switch_page(self, idx: int):
        self._stack.setCurrentIndex(idx)
        # Show snow overlay only on gather page (idx 0)
        if idx == 0:
            self._snow_overlay.show()
            self._snow_overlay.raise_()
        else:
            self._snow_overlay.hide()
        # Refresh the page being shown
        pages = [
            self._gather_page,
            self._refine_page,
            self._items_page,
            self._upgrades_page,
            self._prestige_page,
        ]
        if hasattr(pages[idx], "refresh"):
            pages[idx].refresh()

    def _open_settings(self):
        self._settings_overlay.setGeometry(self._central.rect())
        self._settings_overlay.raise_()
        self._settings_overlay.show()

    def _autosave(self):
        self._state.save()

    def _show_level_up_toast(self, skill_id: str, new_level: int):
        LevelUpToast(skill_id, new_level, self)

    def _spawn_gold_float(self, delta: float):
        text = f"{COIN_SMALL_HTML}+{int(delta):,}" if delta > 0 else f"{COIN_SMALL_HTML}{int(delta):,}"
        color = PALETTE["gold"] if delta > 0 else PALETTE["danger"]
        spawn_floating_text(text, color, self, cx=self.width() // 2, cy=100)

    def _spawn_shard_float(self, delta: int):
        if delta > 0:
            text = f"+{delta} shard" if delta == 1 else f"+{delta} shards"
        else:
            text = f"{delta} shards"
        color = PALETTE["accent2"] if delta > 0 else PALETTE["danger"]
        spawn_floating_text(text, color, self, cx=self.width() // 2, cy=100)

    def closeEvent(self, event):
        if not _RESET_PENDING:
            self._state.save()
        super().closeEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Keep parallax covering the full central widget area
        if hasattr(self, "_parallax"):
            self._parallax.setGeometry(self.centralWidget().rect())
        # Keep snow overlay covering the full stack area
        if hasattr(self, "_snow_overlay"):
            self._snow_overlay.setGeometry(self._stack.rect())
        # Reposition toast
        if hasattr(self, "_toast"):
            w = self._toast.width()
            self._toast.move((self.width() - w) // 2, 80)


# ---------------------------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------------------------
def main():
    app = QApplication(sys.argv)
    app.setApplicationName("CraftIdle")
    app.setStyle("Fusion")

    # Load custom fonts before any widgets are created
    for _font_file in ("Skranji-Bold.ttf", "Skranji-Regular.ttf"):
        _font_path = str(BASE_DIR / _font_file)
        QFontDatabase.addApplicationFont(_font_path)

    # -----------------------------------------------------------------------
    # Determine UI scale before any widgets are created
    # -----------------------------------------------------------------------
    global APP_SCALE
    cfg = load_config()
    screen = app.primaryScreen()
    if screen:
        avail = screen.availableSize()
        # auto-scale: fit the target layout into the available screen
        auto = min(avail.width() / MainWindow.TARGET_W,
                   avail.height() / MainWindow.TARGET_H)
        auto = max(0.5, min(auto, 1.0))   # clamp 50 % – 100 %
    else:
        auto = 1.0
    # User preference overrides auto (stored as 0.5–1.5); default = auto
    APP_SCALE = cfg.get("ui_scale", auto)

    # Global stylesheet
    app.setStyleSheet(f"""
        * {{
            font-family: '{FONT_BODY}';
        }}
        QScrollBar:vertical {{
            background: {PALETTE['bg_mid']};
            width: 6px;
            border-radius: 3px;
        }}
        QScrollBar::handle:vertical {{
            background: {PALETTE['border']};
            border-radius: 3px;
            min-height: 20px;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        QScrollBar:horizontal {{
            background: {PALETTE['bg_mid']};
            height: 6px;
        }}
        QScrollBar::handle:horizontal {{
            background: {PALETTE['border']};
            border-radius: 3px;
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
        QToolTip {{
            background: {PALETTE['bg_light']};
            color: {PALETTE['text_primary']};
            border: 1px solid {PALETTE['border']};
            border-radius: 6px;
            padding: 4px 8px;
        }}
    """)

    # Initialise audio AFTER QApplication so Qt multimedia objects are valid
    global AUDIO
    AUDIO = AudioManager()
    cfg_audio = load_config()
    AUDIO.set_sfx_volume(cfg_audio.get("sfx_volume", 0.35))
    AUDIO.set_music_volume(cfg_audio.get("music_volume", 0.5))
    AUDIO.start_bgm()

    win = MainWindow()
    # Show fullscreen / maximized on mobile-sized screens
    if screen and (screen.availableSize().width() < 500 or screen.availableSize().height() < 800):
        win.showMaximized()
    else:
        win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()