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
    QLineEdit, QMessageBox
)
from PySide6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve, QRect, QSize,
    QParallelAnimationGroup, QSequentialAnimationGroup,
    Signal, QObject, QPoint, QRectF, QThread, Property
)
from PySide6.QtGui import (
    QPainter, QPixmap, QColor, QFont, QFontMetrics, QPen, QBrush,
    QLinearGradient, QRadialGradient, QPainterPath, QIcon,
    QTransform, QCursor, QMovie
)

# ---------------------------------------------------------------------------
# PATHS
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
SAVE_FILE   = BASE_DIR / "savegame.json"
CONFIG_FILE = BASE_DIR / "config.json"

# ---------------------------------------------------------------------------
# UI SCALE  — set in main() from screen detection + user preference
# ---------------------------------------------------------------------------
APP_SCALE: float = 1.0   # mutable module-level; updated before any widget is built

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

FONT_TITLE  = "Georgia"
FONT_BODY   = "Helvetica Neue"
FONT_MONO   = "Courier New"

# ---------------------------------------------------------------------------
# GAME CONSTANTS  (all tunable)
# ---------------------------------------------------------------------------
AUTOSAVE_INTERVAL_MS = 15_000

RESOURCES = {
    "oakLog":    {"name": "Oak Logs",     "sprite": "oakLog.png",    "value": 2,   "xp_skill": "woodChopping"},
    "ironOre":   {"name": "Iron Ore",     "sprite": "ironOre.png",   "value": 5,   "xp_skill": "ironMining"},
    "stoneChunk":{"name": "Stone Chunks", "sprite": "stoneChunk.png","value": 3,   "xp_skill": "stoneMining"},
    "oakPlank":  {"name": "Oak Planks",   "sprite": "oakPlank.png",  "value": 6,   "xp_skill": "woodRefining"},
    "ironIngot": {"name": "Iron Ingots",  "sprite": "ironIngot.png", "value": 15,  "xp_skill": "ironRefining"},
    "stoneBrick":{"name": "Stone Bricks", "sprite": "stoneBrick.png","value": 8,   "xp_skill": "stoneRefining"},
}

RESOURCE_NODES = {
    "tree":       {"name": "Oak Tree",     "sprite": "oakTree.png",     "yields": "oakLog",    "base_chance": 0.5, "unlock_cost": 0, "xp_per_hit": 4,  "xp_skill": "woodChopping"},
    "rock":       {"name": "Rock Deposit", "sprite": "stoneDeposit.png", "yields": "stoneChunk","base_chance": 0.5, "unlock_cost": 0, "xp_per_hit": 4,  "xp_skill": "stoneMining"},
    "oreDeposit": {"name": "Iron Deposit", "sprite": "ironDeposit.png", "yields": "ironOre",   "base_chance": 0.4, "unlock_cost": 0, "xp_per_hit": 6,  "xp_skill": "ironMining",
                   "skill_req": ("stoneMining", 10)},
}

REFINING_STATIONS = {
    "sawmill": {
        "name": "Sawmill",
        "sprite": "sawmill.png",
        "frames": 36, "frame_w": 640, "frame_h": 640,
        "frame_delay": 100,
        "recipe": {"input": "oakLog", "output": "oakPlank", "ratio": 2, "time_per_unit": 3.0},
        "xp_skill": "woodRefining", "xp_per_output": 8,
    },
    "forge": {
        "name": "Forge",
        "sprite": "forge.png",
        "frames": 16, "frame_w": 414, "frame_h": 508,
        "frame_delay": 100,
        "recipe": {"input": "ironOre", "output": "ironIngot", "ratio": 2, "time_per_unit": 5.0},
        "xp_skill": "ironRefining", "xp_per_output": 12,
    },
    "masonBench": {
        "name": "Mason Bench",
        "sprite": "masonBench.png",
        "frames": 1, "frame_w": 256, "frame_h": 256,
        "frame_delay": 0,
        "recipe": {"input": "stoneChunk", "output": "stoneBrick", "ratio": 2, "time_per_unit": 4.0},
        "xp_skill": "stoneRefining", "xp_per_output": 8,
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
        "desc": "Better axes increase wood gathered per click and chopping odds.",
        "base_cost": 60,  "cost_mult": 2.2, "max_tier": 10,
        "gather_delta": 0.10,   # +10% gather amount per tier
        "chance_delta": 0.03,   # +3% base chance per tier
        "node": "tree",
    },
    {
        "id": "pickaxe",  "name": "Pickaxe",         "icon": "⛏",
        "sprite": "pickaxeT{tier}.png",  # tiered: pickaxeT1.png – pickaxeT10.png
        "desc": "Better pickaxes improve stone/ore output and mining success.",
        "base_cost": 80,  "cost_mult": 2.2, "max_tier": 10,
        "gather_delta": 0.10,
        "chance_delta": 0.03,
        "node": "rock",           # applies to rock and oreDeposit
    },
    {
        "id": "merchant_stall", "name": "Merchant Stall", "icon": "🏪",
        "sprite": "marketStall.png",  # static
        "desc": "Better stalls increase sell price of all goods.",
        "base_cost": 150, "cost_mult": 2.2, "max_tier": 10,
        "sell_delta": 0.08,       # +8% sell multiplier per tier
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
    "fairyDust":     {"name": "Fairy Dust",      "sprite": "fairyDust.png",     "value": 30,  "sellable": True,  "desc": "Shimmering magical dust"},
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
BASE_SPECIAL_CHANCE = 0.005   # 0.5% per strike base
SPECIAL_CHANCE_PER_LEVEL = 0.0006  # +0.06% per skill level (100 * 0.0006 = 6% max)

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
        {"level":  5, "desc": "+1.5% sell price (passive)"},
        {"level": 10, "desc": "+3% sell price (passive)"},
        {"level": 20, "desc": "+6% sell price (passive)"},
        {"level": 50, "desc": "+15% sell price (passive)"},
        {"level": 100,"desc": "MAX — +30% sell price (passive)"},
    ],
}

# Harvest Spirit buff duration in seconds
HARVEST_SPIRIT_DURATION = 30
HARVEST_SPIRIT_GATHER_BONUS = 1.5   # 1.5x gather amount
HARVEST_SPIRIT_CHANCE_BONUS = 0.25  # +25% success chance additive

XP_TABLE = [0] + [int(100 * (lvl ** 1.6)) for lvl in range(1, 100)]

PRESTIGE_BASE_COST = 5000
PRESTIGE_COST_MULTIPLIER = 1.8

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
    for lvl in range(len(XP_TABLE)-1, 0, -1):
        if xp >= XP_TABLE[lvl]:
            return lvl
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
    prestige_bonuses: dict = field(default_factory=lambda: {"resource_gain": 0, "gold_gain": 0, "xp_gain": 0})

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
        gs.prestige_bonuses = d.get("prestige_bonuses", {"resource_gain": 0, "gold_gain": 0, "xp_gain": 0})
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
        skill_map = {"tree": "woodChopping", "rock": "stoneMining", "oreDeposit": "ironMining"}
        skill_id = skill_map.get(node_id, "")
        base = RESOURCE_NODES[node_id]["base_chance"]
        prestige_bonus = self.prestige_bonuses.get("resource_gain", 0) * 0.05
        skill_bonus = self._skill_level(skill_id) * 0.003 if skill_id else 0.0
        # Tool bonus (axe for tree; pickaxe for rock/oreDeposit)
        tool_id = "axe" if node_id == "tree" else "pickaxe"
        tool_tier = self.tool_tiers.get(tool_id, 0)
        tool_chance = next((t["chance_delta"] for t in TOOL_UPGRADES if t["id"] == tool_id), 0) * tool_tier
        spirit_bonus = HARVEST_SPIRIT_CHANCE_BONUS if self.spirit_remaining() > 0 else 0.0
        return min(base + prestige_bonus + skill_bonus + tool_chance + spirit_bonus, 0.97)

    def get_effective_gather_amount(self, node_id: str) -> int:
        """Base amount is 1; tool tiers and runic runes increase it."""
        skill_map = {"tree": "woodChopping", "rock": "stoneMining", "oreDeposit": "ironMining"}
        skill_id = skill_map.get(node_id, "")
        tool_id = "axe" if node_id == "tree" else "pickaxe"
        tool_tier = self.tool_tiers.get(tool_id, 0)
        tool_def = next((t for t in TOOL_UPGRADES if t["id"] == tool_id), {})
        # Each tier gives +gather_delta fraction; floor to get extra whole items
        tool_bonus_frac = tool_def.get("gather_delta", 0) * tool_tier
        runic_gather_tier = self.runic_tiers.get("rune_gather", 0)
        base = 1 + runic_gather_tier  # rune of abundance adds 1 per tier
        spirit_mult = HARVEST_SPIRIT_GATHER_BONUS if self.spirit_remaining() > 0 else 1.0
        # tool_bonus_frac adds fractional chance for an extra item
        extra = int(tool_bonus_frac) + (1 if random.random() < (tool_bonus_frac % 1.0) else 0)
        return max(1, int((base + extra) * spirit_mult))

    def get_crit_chance(self, node_id: str) -> float:
        skill_map = {"tree": "woodChopping", "rock": "stoneMining", "oreDeposit": "ironMining"}
        skill_id = skill_map.get(node_id, "")
        level = self._skill_level(skill_id) if skill_id else 1
        runic_crit_tier = self.runic_tiers.get("rune_crit", 0)
        base_crit = BASE_CRIT_CHANCE + runic_crit_tier * 0.05
        return min(base_crit + level * CRIT_CHANCE_PER_LEVEL, 0.75)

    def get_special_item_chance(self, node_id: str) -> float:
        skill_map = {"tree": "woodChopping", "rock": "stoneMining", "oreDeposit": "ironMining"}
        skill_id = skill_map.get(node_id, "")
        level = self._skill_level(skill_id) if skill_id else 1
        return min(BASE_SPECIAL_CHANCE + level * SPECIAL_CHANCE_PER_LEVEL, 0.30)

    def roll_special_item(self, node_id: str) -> Optional[str]:
        """Return a special item id if the player hits the special drop, else None."""
        chance = self.get_special_item_chance(node_id)
        if random.random() >= chance:
            return None
        is_mining = node_id in ("rock", "oreDeposit")
        if is_mining:
            # Mining: Runic Shard or Geode (60/40)
            return "runicShard" if random.random() < 0.60 else "geode"
        else:
            # Chopping: Harvest Spirit / Fairy Dust / Runic Shard (20/40/40)
            r = random.random()
            if r < 0.20:
                return "harvestSpirit"
            elif r < 0.60:
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
        prestige_bonus = 1 + self.prestige_bonuses.get("gold_gain", 0) * 0.10
        trading_bonus = 1 + self._skill_level("trading") * 0.003
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
        skill_map = {"sawmill": "woodRefining", "forge": "ironRefining", "masonBench": "stoneRefining"}
        tool_map = {"sawmill": "sawmill_tool", "forge": "forge_tool", "masonBench": "mason_bench"}
        skill_id = skill_map.get(station_id, "")
        skill_bonus = self._skill_level(skill_id) * 0.004 if skill_id else 0.0
        tool_id = tool_map.get(station_id, "")
        tool_tier = self.tool_tiers.get(tool_id, 0)
        tool_def = next((t for t in TOOL_UPGRADES if t["id"] == tool_id), {})
        tool_bonus = tool_def.get("refine_delta", 0) * tool_tier
        return 1.0 * (1 + skill_bonus + tool_bonus)

    # ------------------------------------------------------------------
    # XP
    # ------------------------------------------------------------------
    def get_effective_xp(self, base_xp: float) -> float:
        prestige_bonus = 1 + self.prestige_bonuses.get("xp_gain", 0) * 0.10
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

    def can_prestige(self) -> bool:
        return self.gold >= self.prestige_cost()

    def do_prestige(self):
        if not self.can_prestige():
            return False
        self.gold = 0
        for k in self.skills:
            self.skills[k] = SkillState()
        self.inventory = {k: 0 for k in RESOURCES}
        self.special_items = {k: 0 for k in SPECIAL_ITEMS}
        self.tool_tiers.clear()
        # runic_tiers intentionally NOT cleared — permanent
        self.prestige_tier += 1
        self.prestige_coins += 1
        return True

    def spend_prestige_coin(self, bonus_type: str) -> bool:
        if self.prestige_coins <= 0:
            return False
        if bonus_type not in self.prestige_bonuses:
            return False
        self.prestige_coins -= 1
        self.prestige_bonuses[bonus_type] += 1
        return True

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
    def __init__(self):
        self._sfx_volume = 0.8
        self._music_volume = 0.5
        self._sounds: dict = {}
        try:
            from PySide6.QtMultimedia import QSoundEffect, QMediaPlayer, QAudioOutput
            self._QSoundEffect = QSoundEffect
            self._available = True
            self._load_sounds()
        except Exception:
            self._available = False

    def _load_sounds(self):
        if not self._available:
            return
        for name, filename in [("chop", "chop.mp3"), ("mine", "mine.mp3")]:
            path = BASE_DIR / filename
            if path.exists():
                try:
                    from PySide6.QtMultimedia import QSoundEffect
                    from PySide6.QtCore import QUrl
                    s = QSoundEffect()
                    s.setSource(QUrl.fromLocalFile(str(path)))
                    s.setVolume(self._sfx_volume)
                    self._sounds[name] = s
                except Exception as e:
                    print(f"Audio load error {name}: {e}")

    def play(self, name: str):
        if not self._available:
            return
        s = self._sounds.get(name)
        if s:
            s.setVolume(self._sfx_volume)
            s.play()

    def set_sfx_volume(self, v: float):
        self._sfx_volume = max(0.0, min(1.0, v))
        for s in self._sounds.values():
            s.setVolume(self._sfx_volume)

    def set_music_volume(self, v: float):
        self._music_volume = max(0.0, min(1.0, v))


AUDIO = AudioManager()

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
    xp_changed = Signal(str, int)      # skill, new_xp
    node_hit = Signal(str, bool)       # node_id, success
    refine_complete = Signal(str, int) # station_id, amount
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
    f = QFont(name, max(1, int(pt * APP_SCALE)))
    f.setBold(bold)
    f.setItalic(italic)
    return f


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
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._next_frame)
        if frames:
            self.setFixedSize(frames[0].size())

    def set_frames(self, frames: list[QPixmap], delay_ms: int = 100):
        self._frames = frames
        self._delay = delay_ms
        self._current = 0
        if frames:
            self.setFixedSize(frames[0].size())
        self.update()

    def play(self, loop: bool | None = None):
        if loop is not None:
            self._loop = loop
        self._current = 0
        self._playing = True
        self._timer.start(self._delay)

    def stop(self):
        self._playing = False
        self._timer.stop()

    def _next_frame(self):
        if not self._frames:
            return
        self._current += 1
        if self._current >= len(self._frames):
            if self._loop:
                self._current = 0
            else:
                self._current = len(self._frames) - 1
                self.stop()
                self.animation_done.emit()
        self.update()

    def paintEvent(self, event):
        if not self._frames:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
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
# SWIPE CONTAINER  (swipe left/right to navigate items)
# ---------------------------------------------------------------------------
class SwipeContainer(QWidget):
    index_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: list[QWidget] = []
        self._index = 0
        self._drag_start: Optional[QPoint] = None
        self._drag_threshold = 60
        self.setMouseTracking(True)

        self._layout = QStackedWidget(self)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._layout)

        # dot indicators
        self._dot_bar = QWidget(self)
        self._dot_layout = QHBoxLayout(self._dot_bar)
        self._dot_layout.setAlignment(Qt.AlignCenter)
        self._dot_layout.setSpacing(8)
        outer.addWidget(self._dot_bar)
        outer.setAlignment(self._dot_bar, Qt.AlignHCenter)

    def add_item(self, w: QWidget):
        self._items.append(w)
        self._layout.addWidget(w)
        self._rebuild_dots()

    def clear_items(self):
        while self._items:
            w = self._items.pop()
            self._layout.removeWidget(w)
            w.deleteLater()
        self._rebuild_dots()

    def _rebuild_dots(self):
        for i in reversed(range(self._dot_layout.count())):
            self._dot_layout.itemAt(i).widget().deleteLater()
        for i in range(len(self._items)):
            dot = QLabel("●")
            dot.setFont(scaled_font(FONT_BODY, 8))
            self._dot_layout.addWidget(dot)
        self._update_dots()

    def _update_dots(self):
        for i in range(self._dot_layout.count()):
            dot = self._dot_layout.itemAt(i).widget()
            if dot:
                active = (i == self._index)
                dot.setStyleSheet(f"color: {PALETTE['accent'] if active else PALETTE['text_dim']};")

    def go_to(self, idx: int):
        if not self._items:
            return
        idx = max(0, min(idx, len(self._items)-1))
        self._index = idx
        self._layout.setCurrentIndex(idx)
        self._update_dots()
        self.index_changed.emit(idx)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_start = e.position().toPoint()

    def mouseReleaseEvent(self, e):
        if self._drag_start is None:
            return
        delta = e.position().toPoint().x() - self._drag_start.x()
        if abs(delta) > self._drag_threshold:
            if delta < 0:
                self.go_to(self._index + 1)
            else:
                self.go_to(self._index - 1)
        self._drag_start = None


# ---------------------------------------------------------------------------
# ANIMATED NUMBER LABEL
# ---------------------------------------------------------------------------
class AnimatedNumber(QLabel):
    def __init__(self, value: float = 0, fmt="{:.0f}", parent=None):
        super().__init__(parent)
        self._value = value
        self._fmt = fmt
        self._update_text()

    def set_value(self, v: float, animate=True):
        old = self._value
        self._value = v
        if animate and abs(v - old) > 0.5:
            eff = QGraphicsOpacityEffect(self)
            self.setGraphicsEffect(eff)
            anim = QPropertyAnimation(eff, b"opacity")
            anim.setDuration(200)
            anim.setStartValue(0.3)
            anim.setEndValue(1.0)
            anim.start(QPropertyAnimation.DeleteWhenStopped)
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
    """Rising floating text notification — fades in, floats up, fades out (~1.5s)."""
    def __init__(self, text: str, color: str, parent: QWidget,
                 cx: int = -1, cy: int = -1):
        super().__init__(text, parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setFont(scaled_font(FONT_BODY, 13, bold=True))
        self.setStyleSheet(f"color: {color}; background: transparent; border: none;")
        self.adjustSize()
        if cx < 0:
            cx = parent.width() // 2
        if cy < 0:
            cy = parent.height() // 2 - 20
        sx = cx - self.width() // 2
        sy = cy - self.height() // 2
        self.move(sx, sy)
        self.show()
        self.raise_()

        eff = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(eff)

        self._pos_anim = QPropertyAnimation(self, b"pos", self)
        self._pos_anim.setDuration(1500)
        self._pos_anim.setStartValue(QPoint(sx, sy))
        self._pos_anim.setEndValue(QPoint(sx, sy - 80))
        self._pos_anim.setEasingCurve(QEasingCurve.OutCubic)

        self._opa_anim = QPropertyAnimation(eff, b"opacity", self)
        self._opa_anim.setDuration(1500)
        self._opa_anim.setKeyValueAt(0.0, 0.0)
        self._opa_anim.setKeyValueAt(0.12, 1.0)
        self._opa_anim.setKeyValueAt(0.65, 1.0)
        self._opa_anim.setKeyValueAt(1.0, 0.0)

        self._grp = QParallelAnimationGroup(self)
        self._grp.addAnimation(self._pos_anim)
        self._grp.addAnimation(self._opa_anim)
        self._grp.finished.connect(self.deleteLater)
        self._grp.start()


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
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._fade_out)
        self._anim: Optional[QPropertyAnimation] = None

    def show_message(self, msg: str, color: str = None):
        self.setText(msg)
        if color:
            self.setStyleSheet(self.styleSheet().replace(
                f"color: {PALETTE['accent']}", f"color: {color}"
            ))
        self.adjustSize()
        # center in parent
        if self.parent():
            pw = self.parent().width()
            self.move((pw - self.width()) // 2, 60)
        eff = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(eff)
        self.show()
        anim = QPropertyAnimation(eff, b"opacity")
        anim.setDuration(250)
        anim.setStartValue(0)
        anim.setEndValue(1)
        anim.start(QPropertyAnimation.DeleteWhenStopped)
        self._timer.start(2000)

    def _fade_out(self):
        eff = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(eff)
        anim = QPropertyAnimation(eff, b"opacity")
        anim.setDuration(400)
        anim.setStartValue(1)
        anim.setEndValue(0)
        anim.finished.connect(self.hide)
        anim.start(QPropertyAnimation.DeleteWhenStopped)


# ---------------------------------------------------------------------------
# HEADER BAR
# ---------------------------------------------------------------------------
class HeaderBar(QWidget):
    settings_clicked = Signal()

    def __init__(self, state: GameState, parent=None):
        super().__init__(parent)
        self._state = state
        self.setFixedHeight(64)
        self.setStyleSheet(f"background: {PALETTE['bg_mid']}; border-bottom: 1px solid {PALETTE['border']};")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(20, 0, 20, 0)

        # Title
        title = QLabel("⚒ CraftIdle")
        title.setFont(scaled_font(FONT_TITLE, 18, bold=True))
        title.setStyleSheet(f"color: {PALETTE['accent']}; background: transparent; border: none;")

        # Gold
        self._gold_lbl = AnimatedNumber(state.gold, fmt="🪙 {:.0f}")
        self._gold_lbl.setFont(scaled_font(FONT_BODY, 13, bold=True))
        self._gold_lbl.setStyleSheet(f"color: {PALETTE['gold']}; background: transparent; border: none;")

        # Prestige
        self._prestige_lbl = QLabel()
        self._prestige_lbl.setFont(scaled_font(FONT_BODY, 12))
        self._prestige_lbl.setStyleSheet(f"color: {PALETTE['prestige']}; background: transparent; border: none;")

        # Settings cog
        cog = QPushButton("⚙")
        cog.setFont(scaled_font(FONT_BODY, 18))
        cog.setFixedSize(44, 44)
        cog.setCursor(QCursor(Qt.PointingHandCursor))
        cog.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {PALETTE['text_muted']};
                border: none;
                border-radius: 22px;
            }}
            QPushButton:hover {{ color: {PALETTE['accent']}; }}
        """)
        cog.clicked.connect(self.settings_clicked)

        lay.addWidget(title)
        lay.addStretch()
        lay.addWidget(self._prestige_lbl)
        lay.addSpacing(12)
        lay.addWidget(self._gold_lbl)
        lay.addSpacing(8)
        lay.addWidget(cog)

        BUS.gold_changed.connect(self._refresh)

    def _refresh(self):
        self._gold_lbl.set_value(self._state.gold)
        if self._state.prestige_tier > 0:
            self._prestige_lbl.setText(f"✦ Tier {self._state.prestige_tier}  💜{self._state.prestige_coins}")
        else:
            self._prestige_lbl.setText("")


# ---------------------------------------------------------------------------
# NAV BAR
# ---------------------------------------------------------------------------
class NavBar(QWidget):
    tab_changed = Signal(int)

    TABS = [
        ("⛏", "Gather"),
        ("🔥", "Refine"),
        ("🎒", "Items"),
        ("⬆", "Upgrades"),
        ("✦", "Prestige"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(80)
        self.setStyleSheet(f"background: {PALETTE['bg_mid']}; border-top: 1px solid {PALETTE['border']};")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self._buttons: list[QPushButton] = []
        self._active = 0
        for i, (icon, label) in enumerate(self.TABS):
            btn = QPushButton(f"{icon}\n{label}")
            btn.setFont(scaled_font(FONT_BODY, 10))
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, idx=i: self._select(idx))
            self._buttons.append(btn)
            lay.addWidget(btn)
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
                    font-size: 9pt;
                    padding: 4px;
                }}
                QPushButton:hover {{
                    background: #202436;
                    color: {PALETTE['text_primary']};
                }}
            """)

    def set_active(self, idx: int):
        self._select(idx)


# ---------------------------------------------------------------------------
# SETTINGS DIALOG
# ---------------------------------------------------------------------------
class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.setMinimumWidth(360)
        self.setStyleSheet(f"""
            QDialog {{
                background: {PALETTE['bg_mid']};
                border: 1px solid {PALETTE['border']};
                border-radius: 16px;
            }}
        """)
        lay = QVBoxLayout(self)
        lay.setSpacing(20)
        lay.setContentsMargins(30, 30, 30, 30)

        title = QLabel("⚙ Settings")
        title.setFont(scaled_font(FONT_TITLE, 16, bold=True))
        title.setStyleSheet(f"color: {PALETTE['accent']}; border: none; background: transparent;")
        lay.addWidget(title)

        self._add_slider(lay, "🎵 Music Volume", 0, 100, int(AUDIO._music_volume * 100),
                         lambda v: AUDIO.set_music_volume(v / 100))
        self._add_slider(lay, "🔊 SFX Volume", 0, 100, int(AUDIO._sfx_volume * 100),
                         lambda v: AUDIO.set_sfx_volume(v / 100))

        # UI Scale slider (50 % – 150 %)
        cfg = load_config()
        init_scale = int(cfg.get("ui_scale", APP_SCALE) * 100)
        self._add_slider(lay, "🔍 UI Scale", 50, 150, init_scale,
                         self._on_scale_changed)

        note = QLabel("UI scale change takes effect on next launch.")
        note.setFont(scaled_font(FONT_BODY, 9))
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {PALETTE['text_dim']}; border: none; background: transparent;")
        lay.addWidget(note)

        # Button row: Close | Exit App
        btn_row = QHBoxLayout()

        close = QPushButton("Close")
        close.setFont(scaled_font(FONT_BODY, 12))
        close.setCursor(QCursor(Qt.PointingHandCursor))
        close.setStyleSheet(f"""
            QPushButton {{
                background: {PALETTE['bg_light']};
                color: {PALETTE['text_primary']};
                border: 1px solid {PALETTE['border']};
                border-radius: 10px;
                padding: 10px;
            }}
            QPushButton:hover {{ background: {PALETTE['bg_card']}; }}
        """)
        close.clicked.connect(self.accept)

        exit_btn = QPushButton("✕  Exit Game")
        exit_btn.setFont(scaled_font(FONT_BODY, 12))
        exit_btn.setCursor(QCursor(Qt.PointingHandCursor))
        exit_btn.setStyleSheet(f"""
            QPushButton {{
                background: {PALETTE['danger']};
                color: white;
                border: none;
                border-radius: 10px;
                padding: 10px;
            }}
            QPushButton:hover {{ background: #C05040; }}
        """)
        exit_btn.clicked.connect(QApplication.instance().quit)

        btn_row.addWidget(close)
        btn_row.addWidget(exit_btn)
        lay.addLayout(btn_row)

    def _on_scale_changed(self, value: int):
        cfg = load_config()
        cfg["ui_scale"] = value / 100
        save_config(cfg)

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
# PAGE: GATHER
# ---------------------------------------------------------------------------
class GatherPage(QWidget):
    def __init__(self, state: GameState, parent=None):
        super().__init__(parent)
        self._state = state
        self._strike_frames = load_sprite_sheet("strike.png", STRIKE_W, STRIKE_H, STRIKE_FRAMES)
        self._building_ui()

    def _building_ui(self):
        self.setStyleSheet(f"background: {PALETTE['bg_dark']};")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

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

        self._swipe = SwipeContainer(self)
        root.addWidget(self._swipe, stretch=1)

        self._node_cards: dict[str, "_NodeCard"] = {}
        self._refresh_nodes()

        BUS.inventory_changed.connect(self._refresh_gold_hint)
        BUS.xp_changed.connect(lambda *_: self.refresh())
        BUS.spirit_changed.connect(lambda rem: self.refresh())

    def _refresh_nodes(self):
        self._swipe.clear_items()
        self._node_cards.clear()
        for node_id, node_def in RESOURCE_NODES.items():
            card = _NodeCard(node_id, node_def, self._state, self._strike_frames, self)
            self._swipe.add_item(card)
            self._node_cards[node_id] = card

    def _refresh_gold_hint(self):
        pass  # future: highlight unlockable nodes

    def refresh(self):
        for card in self._node_cards.values():
            card.refresh()


class _NodeCard(QWidget):
    def __init__(self, node_id: str, node_def: dict, state: GameState,
                 strike_frames: list, parent=None):
        super().__init__(parent)
        self._node_id = node_id
        self._node_def = node_def
        self._state = state
        self._strike_frames = strike_frames
        self._locked = node_id not in state.unlocked_nodes
        self._setup_ui()
        self._press_anim: Optional[QPropertyAnimation] = None
        self._sprite_orig_geom: Optional[QRect] = None

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setAlignment(Qt.AlignCenter)
        root.setSpacing(20)
        root.setContentsMargins(30, 30, 30, 30)

        # Node sprite container
        self._sprite_container = QFrame()
        self._sprite_container.setFixedSize(250, 250)
        self._sprite_container.setStyleSheet("background: transparent; border: none;")

        inner = QVBoxLayout(self._sprite_container)
        inner.setAlignment(Qt.AlignCenter)

        sprite_px = load_image(self._node_def["sprite"])
        self._sprite_lbl = QLabel()
        self._sprite_lbl.setAlignment(Qt.AlignCenter)
        self._sprite_lbl.setStyleSheet("background: transparent; border: none;")
        if sprite_px:
            self._sprite_lbl.setPixmap(sprite_px.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            ph = make_placeholder(200, 200, self._node_def["name"])
            self._sprite_lbl.setPixmap(ph)
        inner.addWidget(self._sprite_lbl)

        # Strike overlay — rendered 3x larger for visibility
        strike_w = STRIKE_W * 3
        strike_h = STRIKE_H * 3
        self._strike = SpriteWidget(self._strike_frames, STRIKE_DELAY, loop=False, parent=self._sprite_container)
        self._strike.setFixedSize(strike_w, strike_h)
        self._strike.move(self._sprite_container.width() // 2 - strike_w // 2,
                          self._sprite_container.height() // 2 - strike_h // 2)
        self._strike.hide()
        self._strike.animation_done.connect(self._strike.hide)

        root.addWidget(self._sprite_container, alignment=Qt.AlignCenter)

        # Name
        name_lbl = QLabel(self._node_def["name"])
        name_lbl.setFont(scaled_font(FONT_TITLE, 17, bold=True))
        name_lbl.setAlignment(Qt.AlignCenter)
        name_lbl.setStyleSheet(f"color: {PALETTE['text_primary']}; background: transparent; border: none;")
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
            _xp_wrap.setStyleSheet("background: transparent;")
            _xp_wlay = QVBoxLayout(_xp_wrap)
            _xp_wlay.setContentsMargins(10, 0, 10, 0)
            _xp_wlay.setSpacing(4)
            _xp_wlay.addWidget(self._xp_hdr)
            _xp_wlay.addWidget(self._xp_bar_node)
            root.addWidget(_xp_wrap)

        # Yields info
        yields_id = self._node_def["yields"]
        yields_name = RESOURCES[yields_id]["name"]
        self._chance_lbl = QLabel()
        self._chance_lbl.setAlignment(Qt.AlignCenter)
        self._chance_lbl.setFont(scaled_font(FONT_BODY, 12))
        self._chance_lbl.setStyleSheet(f"color: {PALETTE['text_muted']}; background: transparent; border: none;")
        root.addWidget(self._chance_lbl)

        # Count
        self._count_lbl = QLabel()
        self._count_lbl.setAlignment(Qt.AlignCenter)
        self._count_lbl.setFont(scaled_font(FONT_MONO, 22, bold=True))
        self._count_lbl.setStyleSheet(f"color: {PALETTE['accent2']}; background: transparent; border: none;")
        root.addWidget(self._count_lbl)

        # Feedback label
        self._feedback = QLabel("")
        self._feedback.setAlignment(Qt.AlignCenter)
        self._feedback.setFont(scaled_font(FONT_BODY, 13, bold=True))
        self._feedback.setStyleSheet(f"color: {PALETTE['success']}; background: transparent; border: none;")
        self._feedback.setFixedHeight(30)
        root.addWidget(self._feedback)

        # Action button
        if self._locked:
            skill_req = self._node_def.get("skill_req")
            unlock_cost = self._node_def["unlock_cost"]
            if skill_req:
                req_skill_id, req_lvl = skill_req
                skill_name = SKILLS[req_skill_id]["name"]
                btn_text = f"🔒 {skill_name} Lv {req_lvl}"
            elif unlock_cost > 0:
                btn_text = f"🔒 Unlock — {unlock_cost}🪙"
            else:
                btn_text = "🔒 Locked"
            self._action_btn = QPushButton(btn_text)
            self._action_btn.clicked.connect(self._try_unlock)
        else:
            self._action_btn = QPushButton(f"Strike {self._node_def['name']}")
            self._action_btn.clicked.connect(self._on_strike)

        self._action_btn.setFont(scaled_font(FONT_BODY, 13, bold=True))
        self._action_btn.setFixedHeight(54)
        self._action_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._style_btn()
        make_shadow(self._action_btn, blur=16, opacity=100)
        root.addWidget(self._action_btn)

        self.refresh()

    def _style_btn(self):
        if self._locked:
            col = PALETTE["text_dim"]
            bg = PALETTE["bg_light"]
        else:
            col = PALETTE["bg_dark"]
            bg = PALETTE["accent"]
        self._action_btn.setStyleSheet(f"""
            QPushButton {{
                background: {bg};
                color: {col};
                border: none;
                border-radius: 12px;
                font-family: '{FONT_BODY}';
                font-size: 13pt;
                font-weight: bold;
            }}
            QPushButton:pressed {{
                background: {'#C08030' if not self._locked else PALETTE['bg_card']};
            }}
        """)

    def refresh(self):
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

    def _on_strike(self):
        if self._locked:
            return
        node_def = self._node_def
        sound = "chop" if self._node_id == "tree" else "mine"
        AUDIO.play(sound)

        # Animate button press
        self._animate_press()

        # Show strike
        if self._strike_frames:
            self._strike.show()
            self._strike.play(loop=False)

        chance = self._state.get_effective_chance(self._node_id)
        success = random.random() < chance
        if success:
            yields_id = node_def["yields"]
            amount = self._state.get_effective_gather_amount(self._node_id)
            # Critical hit?
            crit = random.random() < self._state.get_crit_chance(self._node_id)
            if crit:
                amount *= CRIT_MULTIPLIER
            self._state.inventory[yields_id] = self._state.inventory.get(yields_id, 0) + amount
            skill = node_def.get("xp_skill") or RESOURCES[yields_id]["xp_skill"]
            xp = node_def.get("xp_per_hit", 4) * amount
            eff_xp, leveled = self._state.add_xp(skill, xp)
            BUS.inventory_changed.emit()
            BUS.xp_changed.emit(skill, self._state.skills[skill].xp)
            skill_color = SKILLS.get(skill, {}).get("color", PALETTE["accent"])
            self._spawn_float(f"+{eff_xp} XP", skill_color)
            if leveled:
                BUS.level_up.emit(skill, self._state.skills[skill].level)
            res_name = RESOURCES[yields_id]["name"]
            if crit:
                self._show_feedback(f"⚡ CRIT! +{amount} {res_name}", PALETTE["gold"])
            else:
                self._show_feedback(f"+{amount} {res_name}", PALETTE["success"])

            # Special item drop?
            special = self._state.roll_special_item(self._node_id)
            if special:
                self._state.special_items[special] = self._state.special_items.get(special, 0) + 1
                sname = SPECIAL_ITEMS[special]["name"]
                BUS.inventory_changed.emit()
                if special == "runicShard":
                    BUS.shard_delta.emit(1)
                QTimer.singleShot(1100, lambda s=sname: self._show_feedback(f"✨ {s}!", PALETTE["accent"]))
        else:
            self._show_feedback("Miss!", PALETTE["text_muted"])

        BUS.node_hit.emit(self._node_id, success)
        self.refresh()

    def _spawn_float(self, text: str, color: str):
        """Spawn a floating text notification centered over this card."""
        win = self.window()
        pt = self.mapTo(win, self.rect().center())
        FloatingText(text, color, win, cx=pt.x(), cy=pt.y())

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
            self._show_feedback(f"Need {cost}🪙", PALETTE["danger"])
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
        self._feedback.setStyleSheet(f"color: {color}; background: transparent; border: none; font-size: 13pt; font-weight: bold;")
        QTimer.singleShot(1000, lambda: self._feedback.setText(""))

    def _animate_press(self):
        # Cancel any in-flight bounce and snap back to rest before starting a new one
        if self._press_anim is not None:
            self._press_anim.stop()
            self._press_anim = None
            if self._sprite_orig_geom is not None:
                self._sprite_container.setGeometry(self._sprite_orig_geom)
        # Capture resting geometry once (after first layout pass)
        if self._sprite_orig_geom is None:
            self._sprite_orig_geom = QRect(self._sprite_container.geometry())
        orig = QRect(self._sprite_orig_geom)  # defensive copy
        anim = QPropertyAnimation(self._sprite_container, b"geometry", self)
        anim.setDuration(180)
        anim.setKeyValueAt(0.0,  orig)
        anim.setKeyValueAt(0.30, QRect(orig.x(), orig.y() - 13, orig.width(), orig.height()))
        anim.setKeyValueAt(0.65, QRect(orig.x(), orig.y() +  5, orig.width(), orig.height()))
        anim.setKeyValueAt(1.0,  orig)
        anim.setEasingCurve(QEasingCurve.OutQuad)
        # Use identity check so a late-firing callback from a cancelled anim is a no-op
        def _on_done(_a=anim):
            if self._press_anim is _a:
                self._sprite_container.setGeometry(orig)
                self._press_anim = None
        anim.finished.connect(_on_done)
        self._press_anim = anim
        anim.start()  # no DeleteWhenStopped — self._press_anim owns it


# ---------------------------------------------------------------------------
# PAGE: REFINE
# ---------------------------------------------------------------------------
class RefinePage(QWidget):
    def __init__(self, state: GameState, parent=None):
        super().__init__(parent)
        self._state = state
        self.setStyleSheet(f"background: {PALETTE['bg_dark']};")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        title = QLabel("Refining Stations")
        title.setFont(scaled_font(FONT_TITLE, 15, bold=True))
        title.setStyleSheet(f"color: {PALETTE['text_primary']}; padding: 16px 20px 8px; background: transparent; border: none;")
        root.addWidget(title)

        self._swipe = SwipeContainer(self)
        root.addWidget(self._swipe, stretch=1)

        for station_id, station_def in REFINING_STATIONS.items():
            card = _StationCard(station_id, station_def, state, self)
            self._swipe.add_item(card)

    def refresh(self):
        for i in range(self._swipe._layout.count()):
            w = self._swipe._layout.widget(i)
            if isinstance(w, _StationCard):
                w.refresh()


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
        self._setup_ui()

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
            scaled_frames = [f.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation) for f in frames]
            self._sprite.set_frames(scaled_frames, fd)
        else:
            self._sprite = QLabel()
            self._sprite.setFixedSize(200, 200)
            px = load_image(self._station_def["sprite"])
            if px:
                self._sprite.setPixmap(px.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                ph = make_placeholder(200, 200, self._station_def["name"])
                self._sprite.setPixmap(ph)
            self._sprite.setAlignment(Qt.AlignCenter)

        root.addWidget(self._sprite, alignment=Qt.AlignCenter)

        name_lbl = QLabel(self._station_def["name"])
        name_lbl.setFont(scaled_font(FONT_TITLE, 16, bold=True))
        name_lbl.setAlignment(Qt.AlignCenter)
        name_lbl.setStyleSheet(f"color: {PALETTE['text_primary']}; background: transparent; border: none;")
        root.addWidget(name_lbl)

        recipe = self._station_def["recipe"]
        in_name = RESOURCES[recipe["input"]]["name"]
        out_name = RESOURCES[recipe["output"]]["name"]
        recipe_lbl = QLabel(f"{recipe['ratio']} {in_name}  →  1 {out_name}")
        recipe_lbl.setAlignment(Qt.AlignCenter)
        recipe_lbl.setFont(scaled_font(FONT_BODY, 12))
        recipe_lbl.setStyleSheet(f"color: {PALETTE['text_muted']}; background: transparent; border: none;")
        root.addWidget(recipe_lbl)

        # Touch-friendly output amount picker
        _recipe = self._station_def["recipe"]
        _out_name = RESOURCES[_recipe["output"]]["name"]
        make_lbl = QLabel(f"Make {_out_name}:")
        make_lbl.setFont(scaled_font(FONT_BODY, 12, bold=True))
        make_lbl.setAlignment(Qt.AlignCenter)
        make_lbl.setStyleSheet(f"color: {PALETTE['text_primary']}; background: transparent; border: none;")
        root.addWidget(make_lbl)

        def _picker_btn(text: str) -> QPushButton:
            b = QPushButton(text)
            b.setFont(scaled_font(FONT_BODY, 18, bold=True))
            b.setFixedSize(58, 58)
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

        self._minus_btn = _picker_btn("−")
        self._spinbox = QSpinBox()
        self._spinbox.setRange(1, 9999)
        self._spinbox.setValue(1)
        self._spinbox.setAlignment(Qt.AlignCenter)
        self._spinbox.setFixedSize(110, 58)
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
        self._plus_btn = _picker_btn("+")
        self._max_btn = QPushButton("Max")
        self._max_btn.setFont(scaled_font(FONT_BODY, 12, bold=True))
        self._max_btn.setFixedSize(66, 58)
        self._max_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._max_btn.setStyleSheet(f"""
            QPushButton {{
                background: {PALETTE['accent2']};
                color: {PALETTE['bg_dark']};
                border: none; border-radius: 12px; font-weight: bold;
            }}
            QPushButton:pressed {{ background: #4EB4A6; }}
        """)
        # Prevent virtual keyboard on mobile — value changes via ±/Max buttons only
        self._spinbox.lineEdit().setReadOnly(True)
        self._spinbox.lineEdit().setFocusPolicy(Qt.NoFocus)
        self._minus_btn.clicked.connect(lambda: self._spinbox.setValue(max(1, self._spinbox.value() - 1)))
        self._plus_btn.clicked.connect(lambda: self._spinbox.setValue(self._spinbox.value() + 1))
        self._max_btn.clicked.connect(self._set_max)

        picker_row = QHBoxLayout()
        picker_row.setAlignment(Qt.AlignCenter)
        picker_row.setSpacing(8)
        picker_row.addWidget(self._minus_btn)
        picker_row.addWidget(self._spinbox)
        picker_row.addWidget(self._plus_btn)
        picker_row.addWidget(self._max_btn)
        root.addLayout(picker_row)

        # Live "Requires X input" label — updates with spinbox
        self._needs_lbl = QLabel()
        self._needs_lbl.setAlignment(Qt.AlignCenter)
        self._needs_lbl.setFont(scaled_font(FONT_BODY, 11, bold=True))
        self._needs_lbl.setStyleSheet(f"color: {PALETTE['text_muted']}; background: transparent; border: none;")
        root.addWidget(self._needs_lbl)

        self._inventory_lbl = QLabel()
        self._inventory_lbl.setAlignment(Qt.AlignCenter)
        self._inventory_lbl.setFont(scaled_font(FONT_BODY, 11))
        self._inventory_lbl.setStyleSheet(f"color: {PALETTE['text_muted']}; background: transparent; border: none;")
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
        self._status_lbl.setFont(scaled_font(FONT_BODY, 11))
        self._status_lbl.setStyleSheet(f"color: {PALETTE['accent']}; background: transparent; border: none;")
        root.addWidget(self._status_lbl)

        self._refine_btn = QPushButton("Start Refining")
        self._refine_btn.setFont(scaled_font(FONT_BODY, 13, bold=True))
        self._refine_btn.setFixedHeight(62)
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
        self.refresh()

        # Start sprite animation
        if isinstance(self._sprite, SpriteWidget):
            self._sprite.play()

    def refresh(self):
        recipe = self._station_def["recipe"]
        inv = self._state.inventory.get(recipe["input"], 0)
        in_name = RESOURCES[recipe["input"]]["name"]
        self._inventory_lbl.setText(f"Have: {inv:,} {in_name}")
        self._update_needs()

    def _set_max(self):
        recipe = self._station_def["recipe"]
        available = self._state.inventory.get(recipe["input"], 0)
        self._spinbox.setValue(max(1, available // recipe["ratio"]))

    def _update_needs(self):
        recipe = self._station_def["recipe"]
        n = self._spinbox.value()
        needed = n * recipe["ratio"]
        available = self._state.inventory.get(recipe["input"], 0)
        in_name = RESOURCES[recipe["input"]]["name"]
        color = PALETTE["success"] if available >= needed else PALETTE["danger"]
        self._needs_lbl.setText(f"Requires {needed:,} {in_name}")
        self._needs_lbl.setStyleSheet(f"color: {color}; background: transparent; border: none; font-weight: bold;")

    def _start_refine(self):
        if self._refining:
            return
        recipe = self._station_def["recipe"]
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
        recipe = self._station_def["recipe"]
        output = recipe["output"]
        amount = self._refine_amount
        self._state.inventory[output] = self._state.inventory.get(output, 0) + amount
        skill = self._station_def["xp_skill"]
        xp = self._station_def["xp_per_output"] * amount
        eff_xp, leveled = self._state.add_xp(skill, xp)
        BUS.xp_changed.emit(skill, self._state.skills[skill].xp)
        BUS.inventory_changed.emit()
        BUS.refine_complete.emit(self._station_id, amount)
        # Floating XP notification
        skill_color = SKILLS.get(skill, {}).get("color", PALETTE["accent"])
        win = self.window()
        pt = self.mapTo(win, self.rect().center())
        FloatingText(f"+{eff_xp} XP", skill_color, win, cx=pt.x(), cy=pt.y())
        if leveled:
            BUS.level_up.emit(skill, self._state.skills[skill].level)
        out_name = RESOURCES[output]["name"]
        self._status_lbl.setText(f"Done! +{amount} {out_name}")
        self._progress.hide()
        self._refine_btn.setEnabled(True)
        self.refresh()


# ---------------------------------------------------------------------------
# GEODE DIALOG  — animated open + reveal
# ---------------------------------------------------------------------------
GEODE_FRAMES_N = 36
GEODE_W, GEODE_H = 576, 482
GEODE_DELAY = 3   # ms

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
            self._title.setText("Opening Geode...")
            self._gem_id = self._state.open_geode()
            if self._geode_sprite:
                self._geode_sprite.play(loop=False)
            else:
                # No animation frames — go straight to reveal
                self._on_anim_done()
        elif self._phase == "reveal":
            self._phase = "done"
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
            self._result_lbl.setText(f"Obtained {gem_name} — click to continue")
        self._continue_btn.setEnabled(True)
        self._continue_btn.setText("Continue")


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
        self.setStyleSheet(f"background: {PALETTE['bg_dark']};")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header row ──────────────────────────────────────────────────
        hdr = QWidget()
        hdr.setFixedHeight(52)
        hdr.setStyleSheet(f"background: {PALETTE['bg_mid']}; border-bottom: 1px solid {PALETTE['border']};")
        hlay = QHBoxLayout(hdr)
        hlay.setContentsMargins(16, 0, 16, 0)
        title_lbl = QLabel("Items")
        title_lbl.setFont(scaled_font(FONT_TITLE, 14, bold=True))
        title_lbl.setStyleSheet(f"color: {PALETTE['text_primary']}; background: transparent; border: none;")
        self._sell_all_btn = QPushButton("🪙 Sell All")
        self._sell_all_btn.setFont(scaled_font(FONT_BODY, 11, bold=True))
        self._sell_all_btn.setFixedHeight(36)
        self._sell_all_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._sell_all_btn.setStyleSheet(f"""
            QPushButton {{
                background: {PALETTE['gold']};
                color: {PALETTE['bg_dark']};
                border: none; border-radius: 10px; padding: 0 16px; font-weight: bold;
            }}
            QPushButton:pressed {{ background: #D8B030; }}
        """)
        self._sell_all_btn.clicked.connect(self._sell_all_items)
        hlay.addWidget(title_lbl)
        hlay.addStretch()
        hlay.addWidget(self._sell_all_btn)
        root.addWidget(hdr)

        # ── Tab bar ──────────────────────────────────────────────────────
        tab_bar = QWidget()
        tab_bar.setFixedHeight(44)
        tab_bar.setStyleSheet(f"background: {PALETTE['bg_mid']}; border-bottom: 1px solid {PALETTE['border']};")
        tlay = QHBoxLayout(tab_bar)
        tlay.setContentsMargins(12, 0, 12, 0)
        tlay.setSpacing(0)

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
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {'#252A3D' if active else 'transparent'};
                    color: {PALETTE['accent'] if active else PALETTE['text_muted']};
                    border: none;
                    border-bottom: 2px solid {'#E8A44A' if active else 'transparent'};
                    font-weight: bold;
                    border-radius: 0;
                    padding: 0 8px;
                }}
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

        self.setMinimumHeight(88)
        self.setStyleSheet(f"""
            QFrame {{
                background: {PALETTE['bg_card']};
                border: 1px solid {PALETTE['border']};
                border-radius: 14px;
            }}
        """)
        make_shadow(self, blur=10, opacity=80)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(12)

        # Icon
        px = load_image(sprite)
        icon = QLabel()
        icon.setFixedSize(48, 48)
        if px:
            icon.setPixmap(px.scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            ph = make_placeholder(48, 48, item_id[:2].upper())
            icon.setPixmap(ph)
        icon.setStyleSheet("background: transparent; border: none;")
        lay.addWidget(icon)

        # Info column
        info = QVBoxLayout()
        info.setSpacing(2)
        name_lbl = QLabel(display_name)
        name_lbl.setFont(scaled_font(FONT_BODY, 11, bold=True))
        name_lbl.setStyleSheet(f"color: {PALETTE['text_primary']}; background: transparent; border: none;")
        self._qty_lbl = QLabel()
        self._qty_lbl.setFont(scaled_font(FONT_MONO, 13, bold=True))
        self._qty_lbl.setStyleSheet(f"color: {PALETTE['accent']}; background: transparent; border: none;")
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
            self._price_lbl.setFont(scaled_font(FONT_MONO, 10))
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
                self._price_lbl.setFont(scaled_font(FONT_MONO, 10))
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
        spin.setFixedWidth(76)
        spin.setFont(scaled_font(FONT_MONO, 10))
        spin.setStyleSheet(f"""
            QSpinBox {{
                background: {PALETTE['bg_light']};
                color: {PALETTE['text_primary']};
                border: 1px solid {PALETTE['border']};
                border-radius: 6px;
                padding: 2px 4px;
            }}
        """)
        lay.addWidget(spin)

        all_btn = QPushButton("All")
        all_btn.setFont(scaled_font(FONT_BODY, 9))
        all_btn.setFixedSize(50, 40)
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
        sell_btn.setFixedSize(62, 44)
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
            self._sub_lbl.setText(f"{price:.1f}🪙 each")
            if self._price_lbl:
                self._price_lbl.setText(f"{price:.1f}🪙")
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
                    self._price_lbl.setText(f"{price:.1f}🪙")
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
# PAGE: UPGRADES
# ---------------------------------------------------------------------------
class UpgradesPage(QWidget):
    """Combined Upgrades page: Tools section, Skills section, Runic Forge section."""

    def __init__(self, state: GameState, parent=None):
        super().__init__(parent)
        self._state = state
        self.setStyleSheet(f"background: {PALETTE['bg_dark']};")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header row ──────────────────────────────────────────────────
        hdr = QWidget()
        hdr.setFixedHeight(52)
        hdr.setStyleSheet(f"background: {PALETTE['bg_mid']}; border-bottom: 1px solid {PALETTE['border']};")
        hlay = QHBoxLayout(hdr)
        hlay.setContentsMargins(16, 0, 16, 0)
        title_lbl = QLabel("⬆ Upgrades & Skills")
        title_lbl.setFont(scaled_font(FONT_TITLE, 14, bold=True))
        title_lbl.setStyleSheet(f"color: {PALETTE['text_primary']}; background: transparent; border: none;")
        self._gold_lbl = QLabel()
        self._gold_lbl.setFont(scaled_font(FONT_BODY, 12))
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
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        vlay = QVBoxLayout(container)
        vlay.setSpacing(8)
        vlay.setContentsMargins(14, 14, 14, 14)
        scroll.setWidget(container)
        root.addWidget(scroll)

        # ============================================================
        # SECTION 1: TOOLS
        # ============================================================
        vlay.addWidget(self._section_header("🛠 Tools", PALETTE["accent"]))
        self._tool_cards: dict[str, "_ToolCard"] = {}
        for tool in TOOL_UPGRADES:
            card = _ToolCard(tool, state, self)
            vlay.addWidget(card)
            self._tool_cards[tool["id"]] = card

        # ============================================================
        # SECTION 2: SKILLS
        # ============================================================
        vlay.addWidget(self._section_header("⭐ Skills", PALETTE["xp_color"]))
        self._skill_cards: dict[str, "_SkillDetailCard"] = {}
        for skill_id, skill_def in SKILLS.items():
            card = _SkillDetailCard(skill_id, skill_def, state, self)
            vlay.addWidget(card)
            self._skill_cards[skill_id] = card

        # ============================================================
        # SECTION 3: RUNIC FORGE
        # ============================================================
        vlay.addWidget(self._section_header("🔮 Runic Forge  (Permanent)", PALETTE["prestige"]))
        rune_desc = QLabel(
            "Combine Runic Shards into permanent upgrades. These are NOT reset by Prestige.\n"
            f"Runic Shards drop from mining and chopping (base {BASE_SPECIAL_CHANCE*100:.1f}% per strike, increases with skill level)."
        )
        rune_desc.setFont(scaled_font(FONT_BODY, 9))
        rune_desc.setWordWrap(True)
        rune_desc.setStyleSheet(f"color: {PALETTE['text_muted']}; background: transparent; border: none;")
        vlay.addWidget(rune_desc)
        self._rune_cards: dict[str, "_RunicCard"] = {}
        for rup in RUNIC_UPGRADES:
            card = _RunicCard(rup, state, self)
            vlay.addWidget(card)
            self._rune_cards[rup["id"]] = card

        vlay.addStretch()

        BUS.gold_changed.connect(self.refresh)
        BUS.xp_changed.connect(lambda *_: self.refresh())
        BUS.inventory_changed.connect(self.refresh)

    @staticmethod
    def _section_header(text: str, color: str) -> QWidget:
        lbl = QLabel(text)
        lbl.setFont(scaled_font(FONT_TITLE, 13, bold=True))
        lbl.setStyleSheet(f"""
            color: {color};
            background: transparent;
            border: none;
            padding: 10px 0 4px 0;
        """)
        return lbl

    def refresh(self):
        self._gold_lbl.setText(f"🪙 {self._state.gold:.0f}")
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
    _ICON_SIZE = 48

    def __init__(self, tool: dict, state: GameState, parent=None):
        super().__init__(parent)
        self._tool = tool
        self._state = state
        self.setMinimumHeight(80)
        self.setStyleSheet(f"""
            QFrame {{
                background: {PALETTE['bg_card']};
                border: 1px solid {PALETTE['border']};
                border-radius: 12px;
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
        self._btn.setFixedSize(90, 34)
        self._btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._btn.clicked.connect(self._buy)
        right.addWidget(self._cost_lbl)
        right.addWidget(self._btn)
        lay.addLayout(right)
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
            self._cost_lbl.setText("MAX")
            self._btn.setText("✓ Max")
            self._btn.setEnabled(False)
            self._btn.setStyleSheet(_btn_style(PALETTE["bg_light"], PALETTE["success"]))
        elif self._state.gold >= cost:
            self._cost_lbl.setText(f"🪙 {cost:,}")
            self._btn.setText("Upgrade")
            self._btn.setEnabled(True)
            self._btn.setStyleSheet(_btn_style(PALETTE["accent"], PALETTE["bg_dark"], "#C08030"))
        else:
            self._cost_lbl.setText(f"🪙 {cost:,}")
            self._btn.setText("Upgrade")
            self._btn.setEnabled(False)
            self._btn.setStyleSheet(_btn_style(PALETTE["text_dim"], PALETTE["bg_mid"]))

    def _buy(self):
        cost = self._state.get_tool_cost(self._tool["id"])
        if self._state.apply_tool_upgrade(self._tool["id"]):
            BUS.gold_changed.emit()
            BUS.gold_delta.emit(-float(cost))
            self.refresh()


class _SkillDetailCard(QFrame):
    """Expandable skill card showing level, XP bar, and milestone list."""
    def __init__(self, skill_id: str, skill_def: dict, state: GameState, parent=None):
        super().__init__(parent)
        self._skill_id = skill_id
        self._skill_def = skill_def
        self._state = state
        self._expanded = False
        self.setStyleSheet(f"""
            QFrame {{
                background: {PALETTE['bg_card']};
                border: 1px solid {PALETTE['border']};
                border-radius: 12px;
            }}
        """)

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
        self.setMinimumHeight(80)
        self.setStyleSheet(f"""
            QFrame {{
                background: {PALETTE['bg_card']};
                border: 1px solid {PALETTE['prestige']};
                border-radius: 12px;
            }}
        """)
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
        self._btn.setFixedSize(80, 34)
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
            self._cost_lbl.setText("MAX")
            self._btn.setText("✓ Max")
            self._btn.setEnabled(False)
            self._btn.setStyleSheet(_btn_style(PALETTE["bg_light"], PALETTE["success"]))
        elif shards >= cost:
            self._cost_lbl.setText(f"{cost} shards")
            self._btn.setText("Forge")
            self._btn.setEnabled(True)
            self._btn.setStyleSheet(_btn_style(PALETTE["prestige"], "white", "#A060E0"))
        else:
            self._cost_lbl.setText(f"{cost} shards")
            self._btn.setText("Forge")
            self._btn.setEnabled(False)
            self._btn.setStyleSheet(_btn_style(PALETTE["text_dim"], PALETTE["bg_mid"]))

    def _forge(self):
        cost = self._state.get_runic_cost(self._rup["id"])
        if self._state.apply_runic_upgrade(self._rup["id"]):
            BUS.inventory_changed.emit()
            BUS.shard_delta.emit(-cost)
            self.refresh()


# ---------------------------------------------------------------------------
# PAGE: PRESTIGE
# ---------------------------------------------------------------------------
class PrestigePage(QWidget):
    def __init__(self, state: GameState, parent=None):
        super().__init__(parent)
        self._state = state
        self.setStyleSheet(f"background: {PALETTE['bg_dark']};")
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(20)

        title = QLabel("✦ Prestige")
        title.setFont(scaled_font(FONT_TITLE, 18, bold=True))
        title.setStyleSheet(f"color: {PALETTE['prestige']}; background: transparent; border: none;")
        root.addWidget(title)

        info = QLabel(
            "Prestige resets your gold, skills, inventory, and upgrades.\n"
            "In return you gain a Prestige Tier and a Prestige Coin to spend\n"
            "on permanent bonuses that carry through all future runs."
        )
        info.setFont(scaled_font(FONT_BODY, 11))
        info.setWordWrap(True)
        info.setStyleSheet(f"color: {PALETTE['text_muted']}; background: transparent; border: none;")
        root.addWidget(info)

        # Status card
        self._status_card = QFrame()
        self._status_card.setStyleSheet(f"""
            QFrame {{
                background: {PALETTE['bg_card']};
                border: 1px solid {PALETTE['prestige']};
                border-radius: 16px;
                padding: 12px;
            }}
        """)
        status_lay = QVBoxLayout(self._status_card)
        status_lay.setSpacing(8)
        self._tier_lbl = QLabel()
        self._tier_lbl.setFont(scaled_font(FONT_TITLE, 14, bold=True))
        self._tier_lbl.setStyleSheet(f"color: {PALETTE['prestige']}; background: transparent; border: none;")
        self._coins_lbl = QLabel()
        self._coins_lbl.setFont(scaled_font(FONT_BODY, 12))
        self._coins_lbl.setStyleSheet(f"color: {PALETTE['gold']}; background: transparent; border: none;")
        self._cost_lbl = QLabel()
        self._cost_lbl.setFont(scaled_font(FONT_BODY, 11))
        self._cost_lbl.setStyleSheet(f"color: {PALETTE['text_muted']}; background: transparent; border: none;")
        status_lay.addWidget(self._tier_lbl)
        status_lay.addWidget(self._coins_lbl)
        status_lay.addWidget(self._cost_lbl)
        make_shadow(self._status_card, blur=20, color=PALETTE["prestige"], opacity=60)
        root.addWidget(self._status_card)

        # Prestige button
        self._prestige_btn = QPushButton("✦ Prestige Now")
        self._prestige_btn.setFont(scaled_font(FONT_TITLE, 14, bold=True))
        self._prestige_btn.setFixedHeight(56)
        self._prestige_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._prestige_btn.clicked.connect(self._do_prestige)
        root.addWidget(self._prestige_btn)

        # Coin spend section
        coin_title = QLabel("Spend Prestige Coins")
        coin_title.setFont(scaled_font(FONT_TITLE, 13, bold=True))
        coin_title.setStyleSheet(f"color: {PALETTE['text_primary']}; background: transparent; border: none;")
        root.addWidget(coin_title)

        for bonus_id, label, desc in [
            ("resource_gain", "⛏ Resource Gain", "+5% resource yield per stack"),
            ("gold_gain",     "🪙 Gold Gain",     "+10% gold from selling per stack"),
            ("xp_gain",       "⬆ XP Gain",        "+10% XP from all actions per stack"),
        ]:
            row = self._make_coin_row(bonus_id, label, desc)
            root.addWidget(row)

        root.addStretch()
        BUS.gold_changed.connect(self.refresh)
        self.refresh()

    def _make_coin_row(self, bonus_id: str, label: str, desc: str) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background: {PALETTE['bg_card']};
                border: 1px solid {PALETTE['border']};
                border-radius: 12px;
            }}
        """)
        lay = QHBoxLayout(frame)
        lay.setContentsMargins(16, 10, 16, 10)
        lay.setSpacing(12)

        info = QVBoxLayout()
        lbl = QLabel(label)
        lbl.setFont(scaled_font(FONT_BODY, 11, bold=True))
        lbl.setStyleSheet(f"color: {PALETTE['text_primary']}; background: transparent; border: none;")
        dlbl = QLabel(desc)
        dlbl.setFont(scaled_font(FONT_BODY, 9))
        dlbl.setStyleSheet(f"color: {PALETTE['text_muted']}; background: transparent; border: none;")
        info.addWidget(lbl)
        info.addWidget(dlbl)
        lay.addLayout(info)
        lay.addStretch()

        stacks_lbl = QLabel()
        stacks_lbl.setFont(scaled_font(FONT_MONO, 11, bold=True))
        stacks_lbl.setStyleSheet(f"color: {PALETTE['prestige']}; background: transparent; border: none;")
        stacks_lbl.setFixedWidth(40)
        stacks_lbl.setAlignment(Qt.AlignCenter)
        lay.addWidget(stacks_lbl)

        btn = QPushButton("Spend 💜")
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

        def spend(bid=bonus_id, sl=stacks_lbl):
            if self._state.spend_prestige_coin(bid):
                BUS.gold_changed.emit()
                sl.setText(str(self._state.prestige_bonuses[bid]))

        btn.clicked.connect(spend)

        # Store refs for refresh
        frame._stacks_lbl = stacks_lbl
        frame._btn = btn
        frame._bonus_id = bonus_id
        lay.addWidget(btn)

        self._coin_rows = getattr(self, "_coin_rows", [])
        self._coin_rows.append(frame)
        return frame

    def refresh(self):
        tier = self._state.prestige_tier
        coins = self._state.prestige_coins
        cost = self._state.prestige_cost()
        can = self._state.can_prestige()
        self._tier_lbl.setText(f"Prestige Tier: {tier}")
        self._coins_lbl.setText(f"Prestige Coins: {coins} 💜")
        self._cost_lbl.setText(f"Next prestige costs {cost:,}🪙  (you have {int(self._state.gold):,}🪙)")
        self._prestige_btn.setEnabled(can)
        self._prestige_btn.setStyleSheet(f"""
            QPushButton {{
                background: {'#9040D0' if can else PALETTE['text_dim']};
                color: white;
                border: none;
                border-radius: 14px;
                font-family: '{FONT_TITLE}';
                font-size: 14pt;
                font-weight: bold;
            }}
            QPushButton:hover {{ background: {'#7030B0' if can else PALETTE['text_dim']}; }}
        """)
        for frame in getattr(self, "_coin_rows", []):
            bid = frame._bonus_id
            frame._stacks_lbl.setText(str(self._state.prestige_bonuses.get(bid, 0)))
            frame._btn.setEnabled(coins > 0)

    def _do_prestige(self):
        cost = self._state.prestige_cost()
        reply = QMessageBox.question(
            self, "Confirm Prestige",
            f"Spend {cost:,}🪙 to prestige?\nThis resets gold, skills, inventory, and upgrades.\nYou'll gain 1 Prestige Coin.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            if self._state.do_prestige():
                BUS.gold_changed.emit()
                BUS.inventory_changed.emit()
                self.refresh()


# ---------------------------------------------------------------------------
# PAGE: SKILLS
# ---------------------------------------------------------------------------


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
        self.setCentralWidget(central)
        main_lay = QVBoxLayout(central)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(0)

        # Header
        self._header = HeaderBar(self._state, self)
        self._header.settings_clicked.connect(self._open_settings)
        main_lay.addWidget(self._header)

        # Page stack
        self._stack = QStackedWidget()
        self._stack.setStyleSheet(f"background: {PALETTE['bg_dark']};")
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
        BUS.xp_changed.connect(lambda s, x: self._upgrades_page.refresh())
        BUS.level_up.connect(self._show_level_up_toast)
        BUS.gold_delta.connect(self._spawn_gold_float)
        BUS.shard_delta.connect(self._spawn_shard_float)

    def _switch_page(self, idx: int):
        self._stack.setCurrentIndex(idx)
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
        dlg = SettingsDialog(self)
        dlg.exec()

    def _autosave(self):
        self._state.save()

    def _show_level_up_toast(self, skill_id: str, new_level: int):
        LevelUpToast(skill_id, new_level, self)

    def _spawn_gold_float(self, delta: float):
        text = f"+{int(delta):,}\U0001fa99" if delta > 0 else f"{int(delta):,}\U0001fa99"
        color = PALETTE["gold"] if delta > 0 else PALETTE["danger"]
        FloatingText(text, color, self, cx=self.width() // 2, cy=100)

    def _spawn_shard_float(self, delta: int):
        if delta > 0:
            text = f"+{delta} shard" if delta == 1 else f"+{delta} shards"
        else:
            text = f"{delta} shards"
        color = PALETTE["accent2"] if delta > 0 else PALETTE["danger"]
        FloatingText(text, color, self, cx=self.width() // 2, cy=100)

    def closeEvent(self, event):
        self._state.save()
        super().closeEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
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

    win = MainWindow()
    # Show fullscreen / maximized on mobile-sized screens
    if screen and (screen.availableSize().width() < 500 or screen.availableSize().height() < 800):
        win.showMaximized()
    else:
        win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()