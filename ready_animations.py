"""
Whimsical stick-figure animations for Chairside Ready Alert.

Triggered randomly on the SENDING workstation after a few qualifying outgoing
Ready messages — a small reward for the staff using the app. The figure
appears to emerge from behind the Ready button, wanders to a random spot on
the app's main window, performs a brief whimsical act, and returns behind
the button. Pure cosmetic feature; no networking, no persistence beyond a
per-animation on/off flag in the existing config file.

Architecture (so the picker preview is pixel-identical to production):

  - StickFigureOverlay manages a transparent Tk Toplevel that floats above
    the parent window. Cross-platform: Windows uses -transparentcolor,
    macOS uses -transparent, fallback is an opaque overlay matching the
    parent's background color.
  - AnimationPlayer drives a ~30fps frame loop via root.after(), calling
    the chosen animation's draw_fn(canvas, t, w, h, button_x, button_y)
    each frame. t is normalized 0..1; button_x/y are the Ready button's
    center in overlay-canvas coordinates.
  - ANIMATIONS is a registry mapping each animation's stable id to its
    (name, duration_ms, draw_fn) tuple. Both the picker and the main app
    iterate this dict; there is no separate "production" animation set.
  - AnimationTrigger is a tiny in-memory state machine: it counts
    qualifying outgoing Ready sends (a send only qualifies if at least
    10 minutes have elapsed since the previous qualifying one) and fires
    after a randomly chosen target in [4, 8].
  - Config helpers (_user_data_dir, load_animation_prefs,
    save_animation_prefs) read and write the SAME config file the main
    app uses (chairside_ready_alert_config.json), under the
    "animation_preferences" key. Atomic temp+rename writes.

The stick figure is built from a single helper, draw_figure_pose, that
takes joint angles in world-space degrees (0=right, 90=down, 180=left,
270=up). All animations stick to this convention so the visual style is
uniform.

Run the picker separately:
    python3 ready_animation_picker.py
"""

from __future__ import annotations

import json
import math
import os
import random
import sys
import time
import tkinter as tk
from typing import Callable, Optional


# ---------------------------------------------------------------------------
# Config helpers — must match the main app's user-data dir / config file.
# Duplicated rather than imported so the picker stays usable as a stand-alone
# script even when the main app's module has issues (e.g., missing deps).
# ---------------------------------------------------------------------------

CONFIG_FILE = "chairside_ready_alert_config.json"


def _user_data_dir() -> str:
    if sys.platform == "darwin":
        return os.path.expanduser(
            "~/Library/Application Support/ChairsideReadyAlert"
        )
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return os.path.join(base, "ChairsideReadyAlert")
    # Linux / other — best-effort
    return os.path.expanduser("~/.local/share/chairside-ready-alert")


def _config_path() -> str:
    return os.path.join(_user_data_dir(), CONFIG_FILE)


def _read_full_config() -> dict:
    try:
        with open(_config_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_full_config(data: dict) -> None:
    path = _config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def load_animation_prefs() -> dict:
    """Read animation_preferences from the shared config file. Returns {}
    if the file doesn't exist or has no preferences yet — caller treats
    missing keys as 'enabled' by default."""
    prefs = _read_full_config().get("animation_preferences", {})
    return prefs if isinstance(prefs, dict) else {}


def save_animation_prefs(prefs: dict) -> None:
    """Atomically write animation_preferences to the shared config file,
    preserving all other top-level keys. Tolerant of a missing file."""
    data = _read_full_config()
    data["animation_preferences"] = prefs
    _write_full_config(data)


def load_animation_character() -> str:
    """Read the user's chosen stick-figure character id. Falls back to
    'plain' (the default character) when the key is missing or unknown."""
    char_id = _read_full_config().get("animation_character", "plain")
    if not isinstance(char_id, str) or char_id not in CHARACTERS:
        return "plain"
    return char_id


def save_animation_character(char_id: str) -> None:
    """Write the chosen character id to the shared config file."""
    if char_id not in CHARACTERS:
        char_id = "plain"
    data = _read_full_config()
    data["animation_character"] = char_id
    _write_full_config(data)


# ---------------------------------------------------------------------------
# Stick figure drawing primitives.
# All angles in WORLD-SPACE degrees: 0=right, 90=down, 180=left, 270=up.
# This matches Tk canvas coordinates (Y increases downward).
# ---------------------------------------------------------------------------

STROKE = 3
COLOR = "#000000"

# Skeleton segment lengths (at scale=1.0)
LEN_BODY = 32
LEN_UPPER_ARM = 18
LEN_FOREARM = 17
LEN_UPPER_LEG = 22
LEN_LOWER_LEG = 20
HEAD_R = 10


def _project(x: float, y: float, length: float, angle_deg: float) -> tuple[float, float]:
    """Endpoint of a segment starting at (x, y), going `length` pixels in
    direction `angle_deg` (world-space)."""
    rad = math.radians(angle_deg)
    return x + length * math.cos(rad), y + length * math.sin(rad)


def _segment(canvas: tk.Canvas, x1, y1, x2, y2, *, stroke=STROKE, color=COLOR):
    canvas.create_line(
        x1, y1, x2, y2,
        fill=color, width=stroke, capstyle="round",
    )


def _circle(canvas: tk.Canvas, cx, cy, r, *, stroke=STROKE, color=COLOR, fill=""):
    canvas.create_oval(
        cx - r, cy - r, cx + r, cy + r,
        outline=color, width=stroke, fill=fill,
    )


# ---------------------------------------------------------------------------
# Face: every character gets eyes + a smile drawn on the head, oriented so
# the face sits on the side of the head opposite the neck (i.e., "forward").
# When the figure rotates during a cartwheel or lies down to sleep, the face
# rotates with the body. Drawn by draw_figure_pose just before the per-
# character decoration so things like glasses overlay the eye dots correctly.
# ---------------------------------------------------------------------------


def _draw_face(canvas, head_x, head_y, head_r, body_angle, *, scale, stroke, color):
    """Two eye dots and a smile arc on the head."""
    # Eye positions: slightly toward the top of the head (along body_angle)
    # and symmetrical on either side of the body axis.
    up_x, up_y = _project(0, 0, head_r * 0.18, body_angle)
    eye_center_x = head_x + up_x
    eye_center_y = head_y + up_y
    eye_offset = head_r * 0.36
    eye_r = max(1.4, head_r * 0.13 * scale)
    for side in (+1, -1):
        ex, ey = _project(
            eye_center_x, eye_center_y, eye_offset, body_angle + 90 * side,
        )
        canvas.create_oval(
            ex - eye_r, ey - eye_r, ex + eye_r, ey + eye_r,
            outline=color, fill=color, width=0,
        )
    # Smile: a smooth three-point arc curving toward the chin (i.e., toward
    # the body, opposite body_angle). Tk's create_arc is screen-axis aligned
    # which wouldn't rotate with the figure, so we approximate the curve
    # with create_line(smooth=True) through three control points.
    down_x, down_y = _project(0, 0, head_r * 0.28, (body_angle + 180) % 360)
    mouth_cx = head_x + down_x
    mouth_cy = head_y + down_y
    smile_half_w = head_r * 0.34
    smile_depth = head_r * 0.18
    left = _project(mouth_cx, mouth_cy, smile_half_w, body_angle + 90)
    right = _project(mouth_cx, mouth_cy, smile_half_w, body_angle - 90)
    bot = _project(mouth_cx, mouth_cy, smile_depth, (body_angle + 180) % 360)
    canvas.create_line(
        left[0], left[1], bot[0], bot[1], right[0], right[1],
        fill=color, width=max(1, stroke - 1),
        smooth=True, capstyle="round",
    )


# ---------------------------------------------------------------------------
# Character decorations — drawn on top of the bare stick figure (and on top
# of the face) to give it personality. Each function takes the head position,
# head radius, body angle (so decorations rotate correctly during cartwheels
# etc.), and the same scale/stroke/color as the base figure.
# ---------------------------------------------------------------------------


def _decor_plain(canvas, head_x, head_y, head_r, body_angle, *, scale, stroke, color):
    """No decoration — the unadorned base stick figure."""
    return


def _decor_wavy_hair(canvas, head_x, head_y, head_r, body_angle, *, scale, stroke, color):
    """Three wavy strands streaming away from the top of the head in the
    body_angle direction (so when standing they go up; when cartwheeling
    they whip around with the figure)."""
    strand_count = 5
    wave_len = 22 * scale
    wave_amp = 7 * scale
    steps = 7
    for i in range(strand_count):
        offset_deg = (i - (strand_count - 1) / 2) * 14
        start_x, start_y = _project(head_x, head_y, head_r * 0.6, body_angle + offset_deg)
        pts = []
        for j in range(steps + 1):
            d = (j / steps) * wave_len
            wave_off = wave_amp * math.sin(j * 1.3 + i * 0.6)
            tip_x, tip_y = _project(start_x, start_y, d, body_angle + offset_deg)
            tip_x, tip_y = _project(tip_x, tip_y, wave_off, body_angle + offset_deg + 90)
            pts.append((tip_x, tip_y))
        flat = [c for pt in pts for c in pt]
        canvas.create_line(
            *flat,
            fill=color, width=max(1, stroke - 1),
            smooth=True, capstyle="round",
        )


def _decor_top_hat(canvas, head_x, head_y, head_r, body_angle, *, scale, stroke, color):
    """A cylindrical top hat that sits on top of the head, oriented with the
    body axis."""
    brim_half = head_r * 1.2
    hat_h = head_r * 1.7
    top_half = head_r * 0.85
    # Brim line: perpendicular to body_angle, at the top of the head
    base_x, base_y = _project(head_x, head_y, head_r * 0.85, body_angle)
    bl_x, bl_y = _project(base_x, base_y, brim_half, body_angle + 90)
    br_x, br_y = _project(base_x, base_y, brim_half, body_angle - 90)
    canvas.create_line(bl_x, bl_y, br_x, br_y, fill=color, width=stroke, capstyle="round")
    # Sides + top of the cylinder
    top_x, top_y = _project(base_x, base_y, hat_h, body_angle)
    side_l_b = _project(base_x, base_y, top_half, body_angle + 90)
    side_r_b = _project(base_x, base_y, top_half, body_angle - 90)
    side_l_t = _project(top_x, top_y, top_half, body_angle + 90)
    side_r_t = _project(top_x, top_y, top_half, body_angle - 90)
    canvas.create_line(side_l_b[0], side_l_b[1], side_l_t[0], side_l_t[1],
                       fill=color, width=stroke, capstyle="round")
    canvas.create_line(side_r_b[0], side_r_b[1], side_r_t[0], side_r_t[1],
                       fill=color, width=stroke, capstyle="round")
    canvas.create_line(side_l_t[0], side_l_t[1], side_r_t[0], side_r_t[1],
                       fill=color, width=stroke, capstyle="round")


def _decor_mohawk(canvas, head_x, head_y, head_r, body_angle, *, scale, stroke, color):
    """Three spikes radiating away from the head along the body axis — like
    an upturned-fan look. Rotates with the figure."""
    for i, (offset_deg, height_mul) in enumerate(
        ((-20, 0.9), (-7, 1.4), (7, 1.4), (20, 0.9)),
    ):
        base_x, base_y = _project(head_x, head_y, head_r, body_angle + offset_deg)
        tip_x, tip_y = _project(
            base_x, base_y, head_r * 1.4 * height_mul,
            body_angle + offset_deg * 0.4,   # spikes lean slightly outward
        )
        canvas.create_line(
            base_x, base_y, tip_x, tip_y,
            fill=color, width=stroke, capstyle="round",
        )


def _decor_glasses(canvas, head_x, head_y, head_r, body_angle, *, scale, stroke, color):
    """Two small spectacle lenses on the head, perpendicular to the body axis
    (so they read as eyes on the face)."""
    eye_offset = head_r * 0.45
    lens_r = head_r * 0.32
    lx, ly = _project(head_x, head_y, eye_offset, body_angle + 90)
    rx, ry = _project(head_x, head_y, eye_offset, body_angle - 90)
    sw = max(1, stroke - 1)
    canvas.create_oval(lx - lens_r, ly - lens_r, lx + lens_r, ly + lens_r,
                       outline=color, width=sw, fill="")
    canvas.create_oval(rx - lens_r, ry - lens_r, rx + lens_r, ry + lens_r,
                       outline=color, width=sw, fill="")
    # Bridge between the two lenses
    canvas.create_line(lx, ly, rx, ry, fill=color, width=sw)


def _decor_beard(canvas, head_x, head_y, head_r, body_angle, *, scale, stroke, color):
    """A triangular beard hanging from the chin (the side of the head closer
    to the body)."""
    beard_dir = (body_angle + 180) % 360
    tip_x, tip_y = _project(head_x, head_y, head_r * 2.2, beard_dir)
    base_x, base_y = _project(head_x, head_y, head_r * 0.85, beard_dir)
    edge_l = _project(base_x, base_y, head_r * 0.8, beard_dir + 90)
    edge_r = _project(base_x, base_y, head_r * 0.8, beard_dir - 90)
    canvas.create_line(edge_l[0], edge_l[1], tip_x, tip_y,
                       fill=color, width=stroke, capstyle="round", smooth=True)
    canvas.create_line(edge_r[0], edge_r[1], tip_x, tip_y,
                       fill=color, width=stroke, capstyle="round", smooth=True)
    # A few short whisker lines
    for off in (-0.4, 0.0, 0.4):
        mid_x, mid_y = _project(head_x, head_y, head_r * 1.4, beard_dir)
        whisk_x, whisk_y = _project(mid_x, mid_y, head_r * 0.5, beard_dir + off * 40)
        canvas.create_line(mid_x, mid_y, whisk_x, whisk_y,
                           fill=color, width=max(1, stroke - 1), capstyle="round")


def _decor_bow_tie(canvas, head_x, head_y, head_r, body_angle, *, scale, stroke, color):
    """A small bow tie at the neck — the position just past the chin toward
    the body. Two triangles joined at a centre knot."""
    # Tie sits at the chin (head edge closest to body)
    chin_x, chin_y = _project(head_x, head_y, head_r, (body_angle + 180) % 360)
    # Two triangles flanking a small central oval
    half_w = head_r * 1.2
    half_h = head_r * 0.45
    # Left wing
    lp1 = _project(chin_x, chin_y, half_w, body_angle + 90)
    lp_top = _project(lp1[0], lp1[1], half_h, body_angle)
    lp_bot = _project(lp1[0], lp1[1], half_h, (body_angle + 180) % 360)
    # Right wing
    rp1 = _project(chin_x, chin_y, half_w, body_angle - 90)
    rp_top = _project(rp1[0], rp1[1], half_h, body_angle)
    rp_bot = _project(rp1[0], rp1[1], half_h, (body_angle + 180) % 360)
    sw = max(1, stroke - 1)
    canvas.create_polygon(
        chin_x, chin_y, lp_top[0], lp_top[1], lp_bot[0], lp_bot[1],
        outline=color, width=sw, fill="",
    )
    canvas.create_polygon(
        chin_x, chin_y, rp_top[0], rp_top[1], rp_bot[0], rp_bot[1],
        outline=color, width=sw, fill="",
    )
    knot_r = head_r * 0.18
    canvas.create_oval(
        chin_x - knot_r, chin_y - knot_r, chin_x + knot_r, chin_y + knot_r,
        outline=color, width=sw, fill="",
    )


def _decor_sunglasses(canvas, head_x, head_y, head_r, body_angle, *, scale, stroke, color):
    """Solid sunglasses: filled circular lenses + a bridge across the nose."""
    up_x, up_y = _project(0, 0, head_r * 0.18, body_angle)
    eye_center_x = head_x + up_x
    eye_center_y = head_y + up_y
    eye_offset = head_r * 0.40
    lens_r = head_r * 0.32
    for side in (+1, -1):
        cx, cy = _project(eye_center_x, eye_center_y, eye_offset, body_angle + 90 * side)
        canvas.create_oval(
            cx - lens_r, cy - lens_r, cx + lens_r, cy + lens_r,
            outline=color, fill=color, width=1,
        )
    # Bridge between the lenses (perpendicular to body axis)
    bridge_y = head_r * 0.05
    lb = _project(eye_center_x, eye_center_y, eye_offset - lens_r, body_angle + 90)
    rb = _project(eye_center_x, eye_center_y, eye_offset - lens_r, body_angle - 90)
    canvas.create_line(lb[0], lb[1], rb[0], rb[1],
                       fill=color, width=stroke, capstyle="round")


def _decor_pigtails(canvas, head_x, head_y, head_r, body_angle, *, scale, stroke, color):
    """Two pigtail bunches on either side of the head, each made of four
    short strokes fanning outward and slightly downward."""
    for side in (+1, -1):
        anchor = _project(head_x, head_y, head_r * 0.95, body_angle + 90 * side)
        for j in range(4):
            offset_deg = (j - 1.5) * 10
            # Pigtails fall slightly toward the body (away from body_angle).
            tip = _project(
                anchor[0], anchor[1], head_r * 1.4,
                body_angle + 90 * side + 18 * side + offset_deg,
            )
            canvas.create_line(
                anchor[0], anchor[1], tip[0], tip[1],
                fill=color, width=stroke, capstyle="round",
            )


def _decor_curly(canvas, head_x, head_y, head_r, body_angle, *, scale, stroke, color):
    """Tight curls along the top of the head — five small unfilled circles."""
    curl_r = head_r * 0.20
    for angle_off in (-55, -28, 0, 28, 55):
        cx, cy = _project(head_x, head_y, head_r * 1.05, body_angle + angle_off)
        canvas.create_oval(
            cx - curl_r, cy - curl_r, cx + curl_r, cy + curl_r,
            outline=color, width=max(1, stroke - 1), fill="",
        )


def _decor_baseball_cap(canvas, head_x, head_y, head_r, body_angle, *, scale, stroke, color):
    """Baseball cap: domed crown over the top of the head plus a brim
    sticking out to one side (the 'forward' direction of the face)."""
    # Dome: a smooth polyline approximation of the upper half-circle of the
    # head. Drawing as a smoothed line means it rotates cleanly.
    n_pts = 10
    points = []
    for i in range(n_pts + 1):
        t = i / n_pts
        angle = body_angle + (t - 0.5) * 170
        pos = _project(head_x, head_y, head_r * 1.08, angle)
        points.append(pos)
    flat = [c for p in points for c in p]
    canvas.create_line(*flat, fill=color, width=stroke, smooth=True, capstyle="round")
    # Brim: small triangular wedge pointing to one side ("front of head")
    brim_dir = body_angle + 80
    brim_anchor = _project(head_x, head_y, head_r * 0.95, brim_dir)
    t1 = _project(brim_anchor[0], brim_anchor[1], head_r * 0.9, brim_dir)
    t2 = _project(brim_anchor[0], brim_anchor[1], head_r * 0.4, brim_dir - 20)
    canvas.create_line(brim_anchor[0], brim_anchor[1], t1[0], t1[1],
                       fill=color, width=stroke, capstyle="round")
    canvas.create_line(t1[0], t1[1], t2[0], t2[1],
                       fill=color, width=stroke, capstyle="round")


def _decor_wizard_hat(canvas, head_x, head_y, head_r, body_angle, *, scale, stroke, color):
    """Tall pointy wizard hat with a small star on the side."""
    # Brim line perpendicular to body axis
    brim_pos = _project(head_x, head_y, head_r * 0.85, body_angle)
    brim_half = head_r * 1.3
    bl = _project(brim_pos[0], brim_pos[1], brim_half, body_angle + 90)
    br = _project(brim_pos[0], brim_pos[1], brim_half, body_angle - 90)
    canvas.create_line(bl[0], bl[1], br[0], br[1],
                       fill=color, width=stroke, capstyle="round")
    # Triangle from the brim to the tip
    tri_half = head_r * 0.75
    base_l = _project(brim_pos[0], brim_pos[1], tri_half, body_angle + 90)
    base_r = _project(brim_pos[0], brim_pos[1], tri_half, body_angle - 90)
    tip = _project(brim_pos[0], brim_pos[1], head_r * 2.4, body_angle)
    canvas.create_polygon(
        base_l[0], base_l[1], tip[0], tip[1], base_r[0], base_r[1],
        outline=color, width=stroke, fill="",
    )
    # Star (4-point cross) near the tip
    star_center = _project(tip[0], tip[1], head_r * 0.5, (body_angle + 180) % 360)
    star_r = head_r * 0.18
    sw = max(1, stroke - 1)
    s1 = _project(star_center[0], star_center[1], star_r, body_angle)
    s2 = _project(star_center[0], star_center[1], star_r, (body_angle + 180) % 360)
    s3 = _project(star_center[0], star_center[1], star_r, body_angle + 90)
    s4 = _project(star_center[0], star_center[1], star_r, body_angle - 90)
    canvas.create_line(s1[0], s1[1], s2[0], s2[1], fill=color, width=sw, capstyle="round")
    canvas.create_line(s3[0], s3[1], s4[0], s4[1], fill=color, width=sw, capstyle="round")


def _decor_cowboy_hat(canvas, head_x, head_y, head_r, body_angle, *, scale, stroke, color):
    """Cowboy hat: wide brim that curls up at the sides + short rounded crown."""
    # Wide brim with subtle curl-up at the edges
    brim_pos = _project(head_x, head_y, head_r * 0.85, body_angle)
    brim_half = head_r * 1.5
    n = 9
    points = []
    for i in range(n + 1):
        t = i / n
        side_amount = (t - 0.5) * 2 * brim_half
        pos = _project(brim_pos[0], brim_pos[1], side_amount, body_angle + 90)
        # Edges curl UP (toward body_angle direction), middle stays flat
        curl = max(0.0, abs(t - 0.5) - 0.30) * head_r * 0.8
        up_off = _project(0, 0, curl, body_angle)
        points.append((pos[0] + up_off[0], pos[1] + up_off[1]))
    flat = [c for p in points for c in p]
    canvas.create_line(*flat, fill=color, width=stroke, smooth=True, capstyle="round")
    # Crown: rounded dome
    crown_half = head_r * 0.75
    crown_top_offset = head_r * 0.7
    cl = _project(brim_pos[0], brim_pos[1], crown_half, body_angle + 90)
    cr = _project(brim_pos[0], brim_pos[1], crown_half, body_angle - 90)
    crown_top = _project(brim_pos[0], brim_pos[1], crown_top_offset, body_angle)
    ctl = _project(crown_top[0], crown_top[1], crown_half * 0.65, body_angle + 90)
    ctr = _project(crown_top[0], crown_top[1], crown_half * 0.65, body_angle - 90)
    canvas.create_line(
        cl[0], cl[1], ctl[0], ctl[1], ctr[0], ctr[1], cr[0], cr[1],
        fill=color, width=stroke, smooth=True, capstyle="round",
    )


def _decor_mustache(canvas, head_x, head_y, head_r, body_angle, *, scale, stroke, color):
    """Handlebar mustache between the eyes and the smile."""
    # Position: just above the smile, below the eye line
    pos_x, pos_y = _project(head_x, head_y, head_r * 0.06, (body_angle + 180) % 360)
    half_w = head_r * 0.42
    # Two curls — one on each side, each a smooth 3-point line ending with
    # a small upward flick away from the body.
    for side in (+1, -1):
        outer = _project(pos_x, pos_y, half_w, body_angle + 90 * side)
        # Flick up (toward body_angle) at the end
        flick = _project(outer[0], outer[1], head_r * 0.18, body_angle)
        canvas.create_line(
            pos_x, pos_y, outer[0], outer[1], flick[0], flick[1],
            fill=color, width=stroke, smooth=True, capstyle="round",
        )


def _decor_crown(canvas, head_x, head_y, head_r, body_angle, *, scale, stroke, color):
    """Royal crown: zigzag of three peaks across the top of the head."""
    base_pos = _project(head_x, head_y, head_r * 0.7, body_angle)
    base_half = head_r * 1.0
    peak_h = head_r * 0.7
    n_peaks = 3
    # 2*n_peaks + 1 points: alternating bottom-of-valley and top-of-peak
    points = []
    for i in range(2 * n_peaks + 1):
        t = i / (2 * n_peaks)
        side_amount = (t - 0.5) * 2 * base_half
        pt = _project(base_pos[0], base_pos[1], side_amount, body_angle + 90)
        if i % 2 == 0:
            points.append(pt)  # at the base
        else:
            tip = _project(pt[0], pt[1], peak_h, body_angle)
            points.append(tip)
    flat = [c for p in points for c in p]
    canvas.create_line(*flat, fill=color, width=stroke, capstyle="round")
    # Small jewel (filled circle) on the middle peak
    middle_peak = points[n_peaks]  # the middle peak index
    jewel_r = head_r * 0.10
    canvas.create_oval(
        middle_peak[0] - jewel_r, middle_peak[1] - jewel_r,
        middle_peak[0] + jewel_r, middle_peak[1] + jewel_r,
        outline=color, fill=color, width=0,
    )


def _decor_bunny_ears(canvas, head_x, head_y, head_r, body_angle, *, scale, stroke, color):
    """Two long curved bunny ears extending up from the head."""
    for side in (-1, +1):
        # Ear anchor: on top of the head, slightly to the side
        anchor = _project(head_x, head_y, head_r * 0.7, body_angle + 18 * side)
        outer_mid = _project(anchor[0], anchor[1], head_r * 1.0, body_angle + 22 * side)
        outer_tip = _project(outer_mid[0], outer_mid[1], head_r * 1.0, body_angle + 6 * side)
        # Inner side comes from a slightly different head anchor and meets the same tip
        inner_anchor = _project(head_x, head_y, head_r * 0.85, body_angle + 5 * side)
        inner_mid = _project(inner_anchor[0], inner_anchor[1], head_r * 0.9, body_angle)
        # Draw outer + tip + back along inner side as one smooth polyline
        canvas.create_line(
            anchor[0], anchor[1],
            outer_mid[0], outer_mid[1],
            outer_tip[0], outer_tip[1],
            inner_mid[0], inner_mid[1],
            inner_anchor[0], inner_anchor[1],
            fill=color, width=stroke, smooth=True, capstyle="round",
        )


def _decor_headphones(canvas, head_x, head_y, head_r, body_angle, *, scale, stroke, color):
    """Headphones: a band across the top of the head and two ear cups on
    either side."""
    # Band: smooth arc over the top of the head
    n = 7
    points = []
    for i in range(n + 1):
        t = i / n
        angle = body_angle + (t - 0.5) * 130
        pos = _project(head_x, head_y, head_r * 1.05, angle)
        points.append(pos)
    flat = [c for p in points for c in p]
    canvas.create_line(*flat, fill=color, width=stroke, smooth=True, capstyle="round")
    # Ear cups on either side of the head, perpendicular to body axis
    cup_r = head_r * 0.32
    for side in (-1, +1):
        cup_pos = _project(head_x, head_y, head_r * 0.92, body_angle + 90 * side)
        canvas.create_oval(
            cup_pos[0] - cup_r, cup_pos[1] - cup_r,
            cup_pos[0] + cup_r, cup_pos[1] + cup_r,
            outline=color, width=stroke, fill="",
        )


# Registry of characters. The key is the stable id used in the config file.
# Renaming a key is a breaking change for the user's saved preference.
CHARACTERS: dict = {
    "plain":         {"name": "Plain (no extras)", "draw_extra": _decor_plain},
    "wavy_hair":     {"name": "Wavy hair",          "draw_extra": _decor_wavy_hair},
    "curly":         {"name": "Curly hair",         "draw_extra": _decor_curly},
    "pigtails":      {"name": "Pigtails",           "draw_extra": _decor_pigtails},
    "mohawk":        {"name": "Mohawk",             "draw_extra": _decor_mohawk},
    "bunny_ears":    {"name": "Bunny ears",         "draw_extra": _decor_bunny_ears},
    "top_hat":       {"name": "Top hat",            "draw_extra": _decor_top_hat},
    "baseball_cap":  {"name": "Baseball cap",       "draw_extra": _decor_baseball_cap},
    "cowboy_hat":    {"name": "Cowboy hat",         "draw_extra": _decor_cowboy_hat},
    "wizard_hat":    {"name": "Wizard hat",         "draw_extra": _decor_wizard_hat},
    "crown":         {"name": "Crown",              "draw_extra": _decor_crown},
    "headphones":    {"name": "Headphones",         "draw_extra": _decor_headphones},
    "glasses":       {"name": "Glasses",            "draw_extra": _decor_glasses},
    "sunglasses":    {"name": "Sunglasses",         "draw_extra": _decor_sunglasses},
    "mustache":      {"name": "Mustache",           "draw_extra": _decor_mustache},
    "beard":         {"name": "Long beard",         "draw_extra": _decor_beard},
    "bow_tie":       {"name": "Bow tie",            "draw_extra": _decor_bow_tie},
}


# Module-level state: which character the renderer should apply. The player
# (and the picker) sets this once before each animation starts; every call
# to draw_figure_pose during that animation reads from here. Single-threaded
# Tk + at-most-one-animation-at-a-time means we don't need a lock.
_current_character_id: str = "plain"


def set_character(char_id: str) -> None:
    """Set the character whose decorations will be applied to subsequent
    draw_figure_pose calls. Unknown ids fall back to 'plain'."""
    global _current_character_id
    _current_character_id = char_id if char_id in CHARACTERS else "plain"


def get_character() -> str:
    """Return the currently active character id."""
    return _current_character_id


def draw_figure_pose(
    canvas: tk.Canvas,
    hip_x: float,
    hip_y: float,
    *,
    body_angle: float = 270.0,          # hip → neck direction. 270=up (default)
    left_arm: tuple[float, float] = (90.0, 90.0),   # (upper-arm dir, forearm dir)
    right_arm: tuple[float, float] = (90.0, 90.0),
    left_leg: tuple[float, float] = (90.0, 90.0),   # (upper-leg dir, lower-leg dir)
    right_leg: tuple[float, float] = (90.0, 90.0),
    head_r: float = HEAD_R,
    scale: float = 1.0,
    stroke: float = STROKE,
    color: str = COLOR,
):
    """Draw a stick figure at (hip_x, hip_y). Angles are absolute world-space
    degrees in the convention noted at the top of this section. All segment
    lengths scale uniformly with `scale`. Returns nothing — caller is expected
    to canvas.delete('all') between frames to clear the previous pose."""
    body_len = LEN_BODY * scale
    ua = LEN_UPPER_ARM * scale
    fa = LEN_FOREARM * scale
    ul = LEN_UPPER_LEG * scale
    ll = LEN_LOWER_LEG * scale
    hr = head_r * scale

    # Body (hip → neck)
    neck_x, neck_y = _project(hip_x, hip_y, body_len, body_angle)
    _segment(canvas, hip_x, hip_y, neck_x, neck_y, stroke=stroke, color=color)

    # Head: extends beyond neck in the same direction as the body
    head_x, head_y = _project(neck_x, neck_y, hr + 2, body_angle)
    _circle(canvas, head_x, head_y, hr, stroke=stroke, color=color)

    # Arms from neck (treated as a single shoulder anchor point — the visual
    # difference of separating shoulders is negligible at this scale)
    for upper_angle, lower_angle in (left_arm, right_arm):
        elbow_x, elbow_y = _project(neck_x, neck_y, ua, upper_angle)
        hand_x, hand_y = _project(elbow_x, elbow_y, fa, lower_angle)
        _segment(canvas, neck_x, neck_y, elbow_x, elbow_y, stroke=stroke, color=color)
        _segment(canvas, elbow_x, elbow_y, hand_x, hand_y, stroke=stroke, color=color)

    # Legs from hip
    for upper_angle, lower_angle in (left_leg, right_leg):
        knee_x, knee_y = _project(hip_x, hip_y, ul, upper_angle)
        foot_x, foot_y = _project(knee_x, knee_y, ll, lower_angle)
        _segment(canvas, hip_x, hip_y, knee_x, knee_y, stroke=stroke, color=color)
        _segment(canvas, knee_x, knee_y, foot_x, foot_y, stroke=stroke, color=color)

    # Face first: every character gets eyes + a smile on the head. The face
    # rotates with body_angle so cartwheels look right.
    try:
        _draw_face(canvas, head_x, head_y, hr, body_angle,
                   scale=scale, stroke=stroke, color=color)
    except Exception:
        pass

    # Apply the active character's decoration on top (hair, hat, glasses,
    # beard, etc.). Decoration draws AFTER the face so that things like
    # glasses correctly cover the eye dots underneath.
    decorator = CHARACTERS.get(_current_character_id, CHARACTERS["plain"])["draw_extra"]
    try:
        decorator(canvas, head_x, head_y, hr, body_angle,
                  scale=scale, stroke=stroke, color=color)
    except Exception:
        # Never let a malformed decoration crash an animation frame.
        pass

    return head_x, head_y, hr  # useful for animations that draw things near the head


# Convenience: smooth easing for "ease-in-out" segments inside animations
def _ease_in_out(t: float) -> float:
    """Cubic ease-in-out. t in [0, 1] -> output in [0, 1]."""
    if t < 0.5:
        return 4.0 * t * t * t
    return 1.0 - ((-2.0 * t + 2.0) ** 3) / 2.0


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


# Walking gait: returns a tuple (left_leg, right_leg, left_arm, right_arm)
# of joint-angle tuples for a single phase of walking. `phase` is a continuous
# value (radians). `intensity` scales how much the limbs swing.
def _walk_pose(phase: float, intensity: float = 1.0):
    swing = math.sin(phase) * 22 * intensity
    arm_swing = math.sin(phase) * 18 * intensity
    left_leg = (90 - swing, 90 - swing * 0.6)
    right_leg = (90 + swing, 90 + swing * 0.6)
    left_arm = (90 + arm_swing, 90 + arm_swing * 0.7)
    right_arm = (90 - arm_swing, 90 - arm_swing * 0.7)
    return left_leg, right_leg, left_arm, right_arm


# ---------------------------------------------------------------------------
# Phase + walk helpers — used by every animation to slice the [0, 1] global
# time into named segments and to draw the figure walking from A to B.
# ---------------------------------------------------------------------------


def _phase(t: float, t_start: float, t_end: float):
    """If t falls inside [t_start, t_end], return a local 0..1 value within
    that phase. Otherwise return None. Lets each animation be structured as a
    flat sequence of `if local is not None: …` blocks instead of nested ifs."""
    if t < t_start or t > t_end:
        return None
    if t_end <= t_start:
        return 1.0
    return (t - t_start) / (t_end - t_start)


def _walk(canvas, from_xy, to_xy, local_t, *, gait_speed: float = 18.0):
    """Draw a walking figure transitioning from from_xy to to_xy as local_t
    goes 0→1. Eased; the legs and arms swing at gait_speed (radians per
    full local_t)."""
    fx, fy = from_xy
    tx, ty = to_xy
    eased = _ease_in_out(local_t)
    hx = _lerp(fx, tx, eased)
    hy = _lerp(fy, ty, eased)
    # Arrange the gait phase so opposite limbs swing alternately and the
    # phase increments smoothly across a walk (instead of resetting per call).
    gait_phase = local_t * gait_speed
    ll, rl, la, ra = _walk_pose(gait_phase)
    draw_figure_pose(
        canvas, hx, hy,
        left_leg=ll, right_leg=rl,
        left_arm=la, right_arm=ra,
    )


# ---------------------------------------------------------------------------
# Button mask: drawn on top of the figure every frame, this replicates the
# Ready button visually so figure parts that overlap the button get hidden.
# When the figure is well clear of the button, the mask still draws (just
# looks like the button itself, which is what we want — the user can't tell
# the mask apart from the real button underneath).
# Drives the peek-out and peek-back-in effects: as the figure slides between
# fully-hidden (hip on button center) and fully-visible (hip well outside the
# button rectangle), more or less of it appears from beside the button edge.
# ---------------------------------------------------------------------------


def _draw_button_mask(canvas: tk.Canvas, button: dict) -> None:
    """Draw a button-shaped mask: a rounded rectangle in the button's color
    plus its label text. Sits above anything drawn earlier in the same frame."""
    x, y, w, h = button["x"], button["y"], button["w"], button["h"]
    color = button.get("color", "#2563eb")
    text_color = button.get("text_color", "#ffffff")
    label = button.get("label", "Ready")
    radius = button.get("radius", 10)
    x0, y0 = x - w / 2, y - h / 2
    x1, y1 = x + w / 2, y + h / 2
    r = min(radius, w / 2, h / 2)
    # Rounded rectangle as a smoothed polygon (same shape primitive
    # chairside_ready_alert.RoundedButton uses).
    pts = [
        x0 + r, y0,  x1 - r, y0,  x1, y0,  x1, y0 + r,
        x1, y1 - r,  x1, y1,  x1 - r, y1,  x0 + r, y1,
        x0, y1,     x0, y1 - r,  x0, y0 + r,  x0, y0,
    ]
    canvas.create_polygon(pts, smooth=True, fill=color, outline="")
    canvas.create_text(
        x, y, text=label, fill=text_color,
        font=_button_label_font(int(h)),
    )


def _button_label_font(button_h: int) -> tuple:
    """Pick a plausible bold font for the button label given the button's
    rendered height. The exact font doesn't have to match the main app
    pixel-perfect — what matters is that the mask reads as a 'button' to the
    eye while the figure is peeking from behind it."""
    if sys.platform == "win32":
        family = "Segoe UI"
    else:
        family = "Helvetica"
    size = max(10, min(18, int(button_h * 0.40)))
    return (family, size, "bold")


def _emerge_position(button: dict, side: int, hidden_amount: float):
    """Return the hip (x, y) for the figure at a given emergence amount.

    `side`: +1 = emerge from the button's right edge, -1 = emerge from its left.
    `hidden_amount`: 1.0 = hip at button center (figure fully behind mask),
                     0.0 = hip well clear of the button, figure fully visible.
    """
    bx, by = button["x"], button["y"]
    bw = button["w"]
    # Fully-visible offset is the button's half-width plus a little air so the
    # figure isn't kissing the button edge.
    clear_offset = bw / 2 + 30
    hidden_offset = 0  # right on top of the button center
    target_offset = _lerp(clear_offset, hidden_offset, hidden_amount)
    return (bx + side * target_offset, by)


def _pick_emerge_side(button: dict, canvas_w: int) -> int:
    """Pick the side of the button with more room for the figure to wander to.
    +1 for right side, -1 for left. Helps avoid figures walking off-screen on
    narrow window widths."""
    bx = button["x"]
    return +1 if bx < canvas_w / 2 else -1


# ---------------------------------------------------------------------------
# The overlay window and the per-animation player.
# ---------------------------------------------------------------------------


class StickFigureOverlay:
    """A transparent Tk Toplevel that floats above the parent window. The
    canvas inside is where animations draw. Hidden when no animation is
    running. Picker and main app both instantiate this exactly the same
    way — that's what guarantees visual fidelity between them."""

    def __init__(self, parent: tk.Misc):
        self.parent = parent
        self.overlay = tk.Toplevel(parent)
        self.overlay.overrideredirect(True)        # no chrome
        self.overlay.attributes("-topmost", True)
        # Try to make the overlay click-through so the user can keep
        # interacting with the app underneath. Best-effort per platform.
        self._bg_color = self._setup_transparency()
        self.canvas = tk.Canvas(
            self.overlay,
            bg=self._bg_color,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(fill="both", expand=True)
        self.overlay.withdraw()

    def _setup_transparency(self) -> str:
        """Pick a background color that the OS will render as transparent
        (so only the stick figure strokes are visible) and apply the
        platform-specific window attributes. Returns the chosen bg color
        for the canvas to use."""
        try:
            if sys.platform == "win32":
                # Magenta is uncommon in UIs — safe as a transparency key.
                self.overlay.attributes("-transparentcolor", "magenta")
                return "magenta"
            if sys.platform == "darwin":
                # Aqua Tk supports -transparent on the window itself.
                # When set, the bg color "systemTransparent" renders as
                # see-through. If the attribute isn't supported we fall
                # through to the opaque fallback.
                self.overlay.attributes("-transparent", True)
                return "systemTransparent"
        except tk.TclError:
            pass
        # Fallback: opaque overlay matching the parent's bg color so it at
        # least visually blends with the app's main background. Stick
        # figure strokes will still be visible.
        try:
            bg = self.parent.cget("bg")  # type: ignore[arg-type]
        except Exception:
            bg = "#f0f4ff"
        return bg or "#f0f4ff"

    def show(self, x: int, y: int, w: int, h: int) -> None:
        self.overlay.geometry(f"{w}x{h}+{x}+{y}")
        self.overlay.deiconify()
        self.overlay.lift()
        try:
            self.overlay.attributes("-topmost", True)
        except tk.TclError:
            pass

    def hide(self) -> None:
        try:
            self.overlay.withdraw()
        except tk.TclError:
            pass

    def clear(self) -> None:
        try:
            self.canvas.delete("all")
        except tk.TclError:
            pass

    def destroy(self) -> None:
        try:
            self.overlay.destroy()
        except tk.TclError:
            pass


class AnimationPlayer:
    """Drives a single animation through its frames. One player can replay
    different animations sequentially; only one animation runs at a time."""

    FRAME_MS = 33  # ~30fps

    def __init__(
        self,
        root: tk.Misc,
        overlay: StickFigureOverlay,
        on_complete: Optional[Callable[[], None]] = None,
    ):
        self.root = root
        self.overlay = overlay
        self.on_complete = on_complete
        self._anim_id: Optional[str] = None
        self._start_time: float = 0.0
        self._button: dict = {}
        self._after_id: Optional[str] = None
        self._running = False

    @property
    def running(self) -> bool:
        return self._running

    def play(self, anim_id: str, button: dict) -> None:
        """Play `anim_id` with `button` describing the Ready button's position,
        size, and color. The button dict's required keys are:
            x, y       — center, in overlay-canvas coordinates
            w, h       — button width / height in pixels
            color      — fill color (matches the button's rendered color)
            text_color — label color
            label      — text rendered on the button (default 'Ready')
            radius     — corner radius (default 10)
        """
        if anim_id not in ANIMATIONS:
            return
        self.stop()  # cancel any in-flight animation
        self._anim_id = anim_id
        self._button = dict(button)
        self._start_time = time.monotonic()
        self._running = True
        self._tick()

    def stop(self) -> None:
        self._running = False
        if self._after_id is not None:
            try:
                self.root.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None
        self.overlay.clear()

    def _tick(self) -> None:
        if not self._running or self._anim_id is None:
            return
        anim = ANIMATIONS[self._anim_id]
        elapsed_ms = (time.monotonic() - self._start_time) * 1000.0
        duration = float(anim["duration_ms"])
        t = min(1.0, elapsed_ms / duration)

        canvas = self.overlay.canvas
        try:
            canvas.delete("all")
            w = canvas.winfo_width()
            h = canvas.winfo_height()
            # 1. Animation draws the figure at its current pose/position.
            anim["draw_fn"](canvas, t, w, h, self._button)
            # 2. Player draws the button-mask on top so any figure parts that
            #    overlap the button get visually clipped. This is what
            #    produces the "peek out from behind the button" effect during
            #    the emerge phase and the matching "peek back in" effect at
            #    the end. When the figure is far from the button, the mask
            #    just looks like the button itself.
            _draw_button_mask(canvas, self._button)
        except tk.TclError:
            self.stop()
            return

        if t >= 1.0:
            self._running = False
            self.overlay.clear()
            if self.on_complete:
                try:
                    self.on_complete()
                except Exception:
                    pass
            return

        try:
            self._after_id = self.root.after(self.FRAME_MS, self._tick)
        except tk.TclError:
            self.stop()


def play_animation(
    anim_id: str,
    parent_window: tk.Misc,
    button_widget: tk.Misc,
    on_complete: Optional[Callable[[], None]] = None,
    character: Optional[str] = None,
) -> Optional[AnimationPlayer]:
    """Top-level convenience: create an overlay sized to the parent window,
    compute the button's position in overlay coordinates, play the animation,
    tear the overlay down when done. Returns the AnimationPlayer so the caller
    can .stop() it early if needed.

    parent_window: a tk.Tk or tk.Toplevel — the window the figure will appear
                   to be moving over.
    button_widget: the widget whose center is "behind the button" for
                   emergence/return. Typically the Ready button.
    character:     character id from CHARACTERS. If None, leaves the current
                   character setting alone (the caller may have set it
                   already via set_character() or load_animation_character()).
    """
    if anim_id not in ANIMATIONS:
        return None

    if character is not None:
        set_character(character)

    try:
        parent_window.update_idletasks()
        button_widget.update_idletasks()
    except tk.TclError:
        return None

    try:
        px = parent_window.winfo_rootx()      # type: ignore[attr-defined]
        py = parent_window.winfo_rooty()      # type: ignore[attr-defined]
        pw = parent_window.winfo_width()      # type: ignore[attr-defined]
        ph = parent_window.winfo_height()     # type: ignore[attr-defined]

        btn_w = int(button_widget.winfo_width())      # type: ignore[attr-defined]
        btn_h = int(button_widget.winfo_height())     # type: ignore[attr-defined]
        bx_screen = button_widget.winfo_rootx() + btn_w // 2  # type: ignore[attr-defined]
        by_screen = button_widget.winfo_rooty() + btn_h // 2  # type: ignore[attr-defined]
    except tk.TclError:
        return None

    overlay = StickFigureOverlay(parent_window)
    overlay.show(px, py, pw, ph)

    # Translate button center from screen → overlay-canvas coordinates.
    button_x = bx_screen - px
    button_y = by_screen - py

    # Pull the button's color + label off the widget so the mask can match.
    # RoundedButton (chairside_ready_alert) stores these as _bg / _fg / _text;
    # MockReadyButton (picker) does the same. If a widget doesn't expose them
    # we fall back to the Modern Blue defaults — better to have a slightly
    # mismatched mask than no animation at all.
    btn_color = getattr(button_widget, "_bg", "#2563eb")
    btn_text_color = getattr(button_widget, "_fg", "#ffffff")
    btn_label = getattr(button_widget, "_text", "Ready")
    btn_radius = getattr(button_widget, "_r", 10)

    button_info = {
        "x": button_x,
        "y": button_y,
        "w": btn_w,
        "h": btn_h,
        "color": btn_color,
        "text_color": btn_text_color,
        "label": btn_label,
        "radius": btn_radius,
    }

    def _done() -> None:
        overlay.hide()
        overlay.destroy()
        if on_complete:
            try:
                on_complete()
            except Exception:
                pass

    player = AnimationPlayer(parent_window, overlay, on_complete=_done)
    player.play(anim_id, button_info)
    return player


# ---------------------------------------------------------------------------
# The 10 animations. Each `draw_anim_*` has the signature
#   def draw_anim_xxx(canvas, t, w, h, button):
# where `t` is [0, 1] global time, w/h are the overlay canvas dimensions,
# and `button` is the dict described on AnimationPlayer.play().
#
# Each animation is structured as a sequence of named phases via _phase().
# Every animation begins with a peek-out from beside the button and ends
# with a matching peek-in. Between, the figure visits 2-3 different
# locations in the window, doing something whimsical at each. Durations
# vary (6-15s) so back-to-back triggers don't feel repetitive.
#
# Coordinate convention: the figure's "hip" is its drawing anchor. The
# button mask is drawn on top by the player every frame, so figure parts
# that overlap the button rectangle disappear behind it — this is what
# produces the side-peek emerge / hide effect.
# ---------------------------------------------------------------------------


def _emerge(canvas, button, local_t, side):
    """Standardized 'figure peeks out from beside the button' phase.
    local_t 0..1: 0 = hip at button center (figure mostly behind mask),
                  1 = hip well outside the button rectangle (figure visible).
    Body leans slightly toward the button while emerging — like the figure
    is shy / spying / peeking — then straightens out by the end."""
    eased = _ease_in_out(local_t)
    hidden_amount = 1.0 - eased
    hx, hy = _emerge_position(button, side, hidden_amount)
    # Lean toward the button at the start; straighten by the end.
    lean = 15 * (1.0 - eased) * (-side)
    body_angle = 270 + lean
    # Limbs hang naturally with a slight tilt
    arm_off = 4 * (1 - eased) * (-side)
    draw_figure_pose(
        canvas, hx, hy,
        body_angle=body_angle,
        left_arm=(90 + arm_off, 90 + arm_off),
        right_arm=(90 - arm_off, 90 - arm_off),
    )


def _hide_back(canvas, button, local_t, side):
    """Standardized 'figure peeks back behind the button' phase. Reverse of
    _emerge: local_t 0..1 transitions hip from fully-visible (1) to
    button-center (0)."""
    eased = _ease_in_out(local_t)
    hidden_amount = eased
    hx, hy = _emerge_position(button, side, hidden_amount)
    lean = 15 * eased * (-side)
    body_angle = 270 + lean
    arm_off = 4 * eased * (-side)
    draw_figure_pose(
        canvas, hx, hy,
        body_angle=body_angle,
        left_arm=(90 + arm_off, 90 + arm_off),
        right_arm=(90 - arm_off, 90 - arm_off),
    )


# ---- Animation 1: Surprise — short, two-spot "what was that?!" ----
# Total ~7s. Visits two spots; does a different reaction at each.
def draw_anim_surprise(canvas, t, w, h, button):
    side = _pick_emerge_side(button, w)
    edge_xy = _emerge_position(button, side, 0.0)
    spot1 = (edge_xy[0] + side * 60, button["y"] - 20)
    spot2 = (edge_xy[0] + side * 180, button["y"] + 40)

    if (l := _phase(t, 0.00, 0.10)) is not None:
        _emerge(canvas, button, l, side); return
    if (l := _phase(t, 0.10, 0.18)) is not None:
        _walk(canvas, edge_xy, spot1, l); return
    if (l := _phase(t, 0.18, 0.40)) is not None:
        # Reaction A: hands fly up, "!" above head
        jiggle = math.sin(l * 14) * 1.5
        draw_figure_pose(
            canvas, spot1[0], spot1[1] + jiggle,
            left_arm=(280, 290), right_arm=(260, 250),
        )
        head_y = spot1[1] - LEN_BODY - HEAD_R * 2 - 6
        canvas.create_line(spot1[0], head_y - 22, spot1[0], head_y - 4,
                           fill=COLOR, width=STROKE, capstyle="round")
        canvas.create_oval(spot1[0] - 2, head_y - 1, spot1[0] + 2, head_y + 3,
                           outline=COLOR, fill=COLOR, width=STROKE)
        return
    if (l := _phase(t, 0.40, 0.50)) is not None:
        _walk(canvas, spot1, spot2, l); return
    if (l := _phase(t, 0.50, 0.78)) is not None:
        # Reaction B: hands on cheeks (bent arms), small hop
        hop = math.sin(l * 8) * 4
        draw_figure_pose(
            canvas, spot2[0], spot2[1] - hop,
            left_arm=(150, 240), right_arm=(30, 300),
        )
        # Two question marks above
        for off in (-12, 12):
            qx = spot2[0] + off
            qy = spot2[1] - LEN_BODY - HEAD_R * 2 - 6
            canvas.create_arc(qx - 5, qy - 8, qx + 5, qy + 2,
                              start=200, extent=200, style="arc",
                              outline=COLOR, width=STROKE)
            canvas.create_oval(qx - 1, qy + 8, qx + 1, qy + 10,
                               outline=COLOR, fill=COLOR, width=STROKE)
        return
    if (l := _phase(t, 0.78, 0.92)) is not None:
        _walk(canvas, spot2, edge_xy, l); return
    if (l := _phase(t, 0.92, 1.00)) is not None:
        _hide_back(canvas, button, l, side); return


# ---- Animation 2: Newspaper — long, two-spot, lots of reading ----
# Total ~13s. Reads sitting at one spot, then reads standing at another.
def draw_anim_newspaper(canvas, t, w, h, button):
    side = _pick_emerge_side(button, w)
    edge_xy = _emerge_position(button, side, 0.0)
    spot1 = (edge_xy[0] + side * 110, max(button["y"] + 60, h * 0.55))
    spot2 = (edge_xy[0] + side * 230, button["y"] - 30)

    if (l := _phase(t, 0.00, 0.06)) is not None:
        _emerge(canvas, button, l, side); return
    if (l := _phase(t, 0.06, 0.15)) is not None:
        _walk(canvas, edge_xy, spot1, l); return
    if (l := _phase(t, 0.15, 0.52)) is not None:
        # Sit cross-legged, read newspaper, head pans slowly L↔R
        head_pan = math.sin(l * 5) * 7
        sit_y = spot1[1] + 20
        draw_figure_pose(
            canvas, spot1[0], sit_y,
            body_angle=270,
            left_leg=(170, 110), right_leg=(10, 70),
            left_arm=(20, 350), right_arm=(160, 190),
        )
        # Held newspaper rectangle in front
        nx1 = spot1[0] - 28 + head_pan * 0.2
        ny1 = sit_y - LEN_BODY - 5
        nx2 = spot1[0] + 28 + head_pan * 0.2
        ny2 = sit_y - LEN_BODY + 22
        canvas.create_rectangle(nx1, ny1, nx2, ny2,
                                outline=COLOR, width=STROKE, fill="")
        for i in range(3):
            ly = ny1 + 6 + i * 6
            canvas.create_line(nx1 + 4, ly, nx2 - 4, ly,
                               fill=COLOR, width=1)
        return
    if (l := _phase(t, 0.52, 0.60)) is not None:
        _walk(canvas, spot1, spot2, l); return
    if (l := _phase(t, 0.60, 0.86)) is not None:
        # Standing read, paper held up at face level
        head_pan = math.sin(l * 6) * 6
        draw_figure_pose(
            canvas, spot2[0], spot2[1],
            left_arm=(280, 200), right_arm=(260, 340),
        )
        # Newspaper in front of face
        nx1 = spot2[0] - 24 + head_pan * 0.2
        ny1 = spot2[1] - LEN_BODY - HEAD_R * 2 - 12
        nx2 = spot2[0] + 24 + head_pan * 0.2
        ny2 = spot2[1] - LEN_BODY + 6
        canvas.create_rectangle(nx1, ny1, nx2, ny2,
                                outline=COLOR, width=STROKE, fill="")
        for i in range(3):
            ly = ny1 + 7 + i * 7
            canvas.create_line(nx1 + 4, ly, nx2 - 4, ly,
                               fill=COLOR, width=1)
        return
    if (l := _phase(t, 0.86, 0.94)) is not None:
        _walk(canvas, spot2, edge_xy, l); return
    if (l := _phase(t, 0.94, 1.00)) is not None:
        _hide_back(canvas, button, l, side); return


# ---- Animation 3: Stretches — three-spot routine ----
# Total ~11s. Toes / overhead reach / side-twist at three different spots.
def draw_anim_stretches(canvas, t, w, h, button):
    side = _pick_emerge_side(button, w)
    edge_xy = _emerge_position(button, side, 0.0)
    spot1 = (edge_xy[0] + side * 70,  h * 0.65)
    spot2 = (edge_xy[0] + side * 180, h * 0.50)
    spot3 = (edge_xy[0] + side * 290, h * 0.65)

    if (l := _phase(t, 0.00, 0.05)) is not None:
        _emerge(canvas, button, l, side); return
    if (l := _phase(t, 0.05, 0.13)) is not None:
        _walk(canvas, edge_xy, spot1, l); return
    if (l := _phase(t, 0.13, 0.30)) is not None:
        # Touch toes
        bend = _ease_in_out(min(1.0, l * 1.5))
        body = _lerp(270, 200, bend)
        arm = _lerp(90, 130, bend)
        draw_figure_pose(canvas, spot1[0], spot1[1],
                         body_angle=body,
                         left_arm=(arm, arm), right_arm=(arm, arm))
        return
    if (l := _phase(t, 0.30, 0.38)) is not None:
        _walk(canvas, spot1, spot2, l); return
    if (l := _phase(t, 0.38, 0.55)) is not None:
        # Overhead reach
        rise = _ease_in_out(min(1.0, l * 1.5))
        arm = _lerp(140, 270, rise)
        draw_figure_pose(canvas, spot2[0], spot2[1],
                         left_arm=(arm, arm), right_arm=(arm, arm))
        return
    if (l := _phase(t, 0.55, 0.63)) is not None:
        _walk(canvas, spot2, spot3, l); return
    if (l := _phase(t, 0.63, 0.86)) is not None:
        # Side twist: lean L/R over a 3-cycle wave
        twist_phase = l * 3 * math.pi * 2
        lean = math.sin(twist_phase) * 18
        draw_figure_pose(canvas, spot3[0], spot3[1],
                         body_angle=270 + lean,
                         left_arm=(180, 180), right_arm=(0, 0))
        return
    if (l := _phase(t, 0.86, 0.94)) is not None:
        _walk(canvas, spot3, edge_xy, l); return
    if (l := _phase(t, 0.94, 1.00)) is not None:
        _hide_back(canvas, button, l, side); return


# ---- Animation 4: Horse ride — gallop out, rear up, gallop back ----
# Total ~9s. The figure walks a few steps before mounting at spot1.
def draw_anim_horse(canvas, t, w, h, button):
    side = _pick_emerge_side(button, w)
    edge_xy = _emerge_position(button, side, 0.0)
    mount = (edge_xy[0] + side * 70, max(h * 0.6, button["y"] + 20))
    far = (edge_xy[0] + side * (w * 0.40), max(h * 0.6, button["y"] + 20))

    def _draw_horse(x, y, dir_x, gait_phase, *, rear=0.0):
        body_y = y + 14
        # Body oval, leans up when rearing
        rear_lift = rear * 12
        canvas.create_oval(x - 32, body_y + 10 - rear_lift,
                           x + 32, body_y + 28 - rear_lift,
                           outline=COLOR, width=STROKE, fill="")
        # Head
        head_x = x + dir_x * 30
        head_y = body_y + (8 - rear * 18)
        canvas.create_oval(head_x - 7, head_y, head_x + 7, head_y + 12,
                           outline=COLOR, width=STROKE, fill="")
        canvas.create_line(x + dir_x * 20, body_y + 12,
                           head_x, head_y + 6,
                           fill=COLOR, width=STROKE, capstyle="round")
        # Tail
        tail_x = x - dir_x * 30
        canvas.create_line(tail_x, body_y + 14, tail_x - dir_x * 12,
                           body_y + 6, fill=COLOR, width=STROKE,
                           capstyle="round")
        # Legs — rear up: front legs lift
        for i, offset in enumerate((-20, -8, 8, 20)):
            is_front = offset > 0 if dir_x > 0 else offset < 0
            leg_lift = (12 if (rear > 0.3 and is_front) else 0)
            leg_swing = math.sin(gait_phase + i * 1.4) * 6
            canvas.create_line(
                x + offset, body_y + 26 - leg_lift,
                x + offset + leg_swing, body_y + 44 - leg_lift,
                fill=COLOR, width=STROKE, capstyle="round",
            )

    if (l := _phase(t, 0.00, 0.05)) is not None:
        _emerge(canvas, button, l, side); return
    if (l := _phase(t, 0.05, 0.10)) is not None:
        _walk(canvas, edge_xy, mount, l); return
    if (l := _phase(t, 0.10, 0.45)) is not None:
        # Gallop outward
        eased = _ease_in_out(l)
        x = _lerp(mount[0], far[0], eased)
        gait = t * 30
        bounce = abs(math.sin(t * 30)) * 8
        _draw_horse(x, mount[1] - bounce, side, gait, rear=0.0)
        draw_figure_pose(
            canvas, x, mount[1] - bounce + 4,
            body_angle=270 + side * 10,
            left_arm=(60 if side > 0 else 120, 70 if side > 0 else 110),
            right_arm=(60 if side > 0 else 120, 70 if side > 0 else 110),
            left_leg=(40, 130), right_leg=(140, 50),
            scale=0.7,
        )
        return
    if (l := _phase(t, 0.45, 0.55)) is not None:
        # Rear up at far side
        rear_amt = _ease_in_out(l)
        if l > 0.5:
            rear_amt = _ease_in_out(1 - l) * 2  # peak in middle
            rear_amt = min(1.0, rear_amt)
        gait = t * 8
        _draw_horse(far[0], mount[1], side, gait, rear=rear_amt)
        draw_figure_pose(
            canvas, far[0], mount[1] + 4 - rear_amt * 8,
            body_angle=270 + side * (10 + rear_amt * 20),
            left_arm=(280, 290), right_arm=(260, 250),
            left_leg=(40, 130), right_leg=(140, 50),
            scale=0.7,
        )
        return
    if (l := _phase(t, 0.55, 0.92)) is not None:
        eased = _ease_in_out(l)
        x = _lerp(far[0], mount[0], eased)
        gait = t * 30
        bounce = abs(math.sin(t * 30)) * 8
        _draw_horse(x, mount[1] - bounce, -side, gait, rear=0.0)
        draw_figure_pose(
            canvas, x, mount[1] - bounce + 4,
            body_angle=270 - side * 10,
            left_arm=(60 if -side > 0 else 120, 70),
            right_arm=(60 if -side > 0 else 120, 70),
            left_leg=(40, 130), right_leg=(140, 50),
            scale=0.7,
        )
        return
    if (l := _phase(t, 0.92, 1.00)) is not None:
        _hide_back(canvas, button, l, side); return


# ---- Animation 5: Jumping jacks — two-spot workout ----
# Total ~10s. Several jacks at spot 1, walk over, more jacks at spot 2.
def draw_anim_jacks(canvas, t, w, h, button):
    side = _pick_emerge_side(button, w)
    edge_xy = _emerge_position(button, side, 0.0)
    spot1 = (edge_xy[0] + side * 100, h * 0.55)
    spot2 = (edge_xy[0] + side * 230, h * 0.55)

    def _jack(canvas, x, y, l_in_phase, cycles):
        jack_phase = l_in_phase * cycles * math.pi
        opened = (math.sin(jack_phase) + 1.0) * 0.5
        bounce = opened * -10
        leg_l = _lerp(90, 60, opened)
        leg_r = _lerp(90, 120, opened)
        arm_l = _lerp(90, 290, opened)
        arm_r = _lerp(90, 250, opened)
        draw_figure_pose(
            canvas, x, y + bounce,
            left_arm=(arm_l, arm_l), right_arm=(arm_r, arm_r),
            left_leg=(leg_l, leg_l), right_leg=(leg_r, leg_r),
        )

    if (l := _phase(t, 0.00, 0.05)) is not None:
        _emerge(canvas, button, l, side); return
    if (l := _phase(t, 0.05, 0.13)) is not None:
        _walk(canvas, edge_xy, spot1, l); return
    if (l := _phase(t, 0.13, 0.42)) is not None:
        _jack(canvas, spot1[0], spot1[1], l, 4); return
    if (l := _phase(t, 0.42, 0.50)) is not None:
        _walk(canvas, spot1, spot2, l); return
    if (l := _phase(t, 0.50, 0.86)) is not None:
        _jack(canvas, spot2[0], spot2[1], l, 5); return
    if (l := _phase(t, 0.86, 0.94)) is not None:
        _walk(canvas, spot2, edge_xy, l); return
    if (l := _phase(t, 0.94, 1.00)) is not None:
        _hide_back(canvas, button, l, side); return


# ---- Animation 6: Sleep — long single-spot nap with floating Zs ----
# Total ~14s. Yawn before laying down, several Zs while asleep.
def draw_anim_sleep(canvas, t, w, h, button):
    side = _pick_emerge_side(button, w)
    edge_xy = _emerge_position(button, side, 0.0)
    bed = (edge_xy[0] + side * 200, h * 0.70)

    if (l := _phase(t, 0.00, 0.05)) is not None:
        _emerge(canvas, button, l, side); return
    if (l := _phase(t, 0.05, 0.15)) is not None:
        _walk(canvas, edge_xy, bed, l); return
    if (l := _phase(t, 0.15, 0.22)) is not None:
        # Yawn: both arms up, head tilted slightly back
        rise = _ease_in_out(l)
        arm = _lerp(140, 270, rise)
        body = _lerp(270, 265, rise)
        draw_figure_pose(canvas, bed[0], bed[1],
                         body_angle=body,
                         left_arm=(arm, arm), right_arm=(arm, arm))
        return
    if (l := _phase(t, 0.22, 0.28)) is not None:
        # Lay down: body angle rotates from vertical to horizontal
        angle = _lerp(270, 180 if side > 0 else 0, _ease_in_out(l))
        hip_y = _lerp(bed[1], bed[1] + 30, _ease_in_out(l))
        draw_figure_pose(canvas, bed[0], hip_y,
                         body_angle=angle,
                         left_arm=(angle, angle), right_arm=(angle, angle),
                         left_leg=(angle, angle), right_leg=(angle, angle))
        return
    if (l := _phase(t, 0.28, 0.80)) is not None:
        # Sleeping: horizontal body, Zs floating up
        angle = 180 if side > 0 else 0
        hip_y = bed[1] + 30
        draw_figure_pose(canvas, bed[0], hip_y,
                         body_angle=angle,
                         left_arm=(angle, angle), right_arm=(angle, angle),
                         left_leg=(angle, angle), right_leg=(angle, angle))
        # Head position: end of body line from hip
        head_x = bed[0] + (LEN_BODY + HEAD_R + 2) * (1 if side > 0 else -1)
        head_y = hip_y
        for i in range(3):
            z_local = (l * 1.6 - i * 0.32) % 1.0
            if z_local < 0.05:
                continue
            zx = head_x + (1 if side > 0 else -1) * (12 + z_local * 26)
            zy = head_y - 12 - z_local * 60
            size = 9 + i * 2
            fade = max(0.05, 1 - z_local)
            stroke = max(1, int(STROKE * fade + 0.5))
            canvas.create_line(zx, zy, zx + size, zy,
                               fill=COLOR, width=stroke)
            canvas.create_line(zx + size, zy, zx, zy + size,
                               fill=COLOR, width=stroke)
            canvas.create_line(zx, zy + size, zx + size, zy + size,
                               fill=COLOR, width=stroke)
        return
    if (l := _phase(t, 0.80, 0.87)) is not None:
        # Wake / stand: rotate body back to vertical
        target_angle = 180 if side > 0 else 0
        angle = _lerp(target_angle, 270, _ease_in_out(l))
        hip_y = _lerp(bed[1] + 30, bed[1], _ease_in_out(l))
        draw_figure_pose(canvas, bed[0], hip_y,
                         body_angle=angle,
                         left_arm=(angle, angle), right_arm=(angle, angle),
                         left_leg=(angle, angle), right_leg=(angle, angle))
        return
    if (l := _phase(t, 0.87, 0.94)) is not None:
        _walk(canvas, bed, edge_xy, l); return
    if (l := _phase(t, 0.94, 1.00)) is not None:
        _hide_back(canvas, button, l, side); return


# ---- Animation 7: Lifts weights — two-spot reps with travel between ----
# Total ~11s. Picks up at spot 1, several presses, walks to spot 2 with the
# bar overhead, more presses, then drops + wipes brow.
def draw_anim_weights(canvas, t, w, h, button):
    side = _pick_emerge_side(button, w)
    edge_xy = _emerge_position(button, side, 0.0)
    spot1 = (edge_xy[0] + side * 110, h * 0.55)
    spot2 = (edge_xy[0] + side * 240, h * 0.55)

    def _press(canvas, x, y, opened):
        body_lean = _lerp(20, 0, opened)
        squat = _lerp(15, 0, opened)
        arm = _lerp(120, 290, opened)
        leg_l = _lerp(70, 90, opened)
        leg_r = _lerp(110, 90, opened)
        hy = y + squat
        draw_figure_pose(
            canvas, x, hy,
            body_angle=270 - body_lean,
            left_arm=(arm, arm), right_arm=(arm, arm),
            left_leg=(leg_l, leg_l), right_leg=(leg_r, leg_r),
        )
        # Barbell at the hands' overhead position
        bar_x = x
        # Empirical: hands at this distance from neck along arm angle
        neck_x, neck_y = _project(x, hy, LEN_BODY, 270 - body_lean)
        hand_x, hand_y = _project(neck_x, neck_y,
                                  LEN_UPPER_ARM + LEN_FOREARM, arm)
        canvas.create_line(hand_x - 28, hand_y, hand_x + 28, hand_y,
                           fill=COLOR, width=STROKE + 1, capstyle="round")
        canvas.create_oval(hand_x - 34, hand_y - 6,
                           hand_x - 24, hand_y + 6,
                           outline=COLOR, width=STROKE, fill="")
        canvas.create_oval(hand_x + 24, hand_y - 6,
                           hand_x + 34, hand_y + 6,
                           outline=COLOR, width=STROKE, fill="")

    if (l := _phase(t, 0.00, 0.05)) is not None:
        _emerge(canvas, button, l, side); return
    if (l := _phase(t, 0.05, 0.13)) is not None:
        _walk(canvas, edge_xy, spot1, l); return
    if (l := _phase(t, 0.13, 0.42)) is not None:
        rep_phase = l * 3 * math.pi
        opened = (math.sin(rep_phase) + 1.0) * 0.5
        _press(canvas, spot1[0], spot1[1], opened); return
    if (l := _phase(t, 0.42, 0.52)) is not None:
        # Walk between with arms locked overhead (carrying the bar)
        eased = _ease_in_out(l)
        x = _lerp(spot1[0], spot2[0], eased)
        gait = l * 12
        ll, rl, _, _ = _walk_pose(gait, intensity=0.6)
        draw_figure_pose(canvas, x, spot1[1],
                         left_arm=(290, 290), right_arm=(290, 290),
                         left_leg=ll, right_leg=rl)
        # Barbell carried overhead
        neck_x, neck_y = _project(x, spot1[1], LEN_BODY, 270)
        hand_x, hand_y = _project(neck_x, neck_y,
                                  LEN_UPPER_ARM + LEN_FOREARM, 290)
        canvas.create_line(hand_x - 28, hand_y, hand_x + 28, hand_y,
                           fill=COLOR, width=STROKE + 1, capstyle="round")
        canvas.create_oval(hand_x - 34, hand_y - 6,
                           hand_x - 24, hand_y + 6,
                           outline=COLOR, width=STROKE, fill="")
        canvas.create_oval(hand_x + 24, hand_y - 6,
                           hand_x + 34, hand_y + 6,
                           outline=COLOR, width=STROKE, fill="")
        return
    if (l := _phase(t, 0.52, 0.82)) is not None:
        rep_phase = l * 3 * math.pi
        opened = (math.sin(rep_phase) + 1.0) * 0.5
        _press(canvas, spot2[0], spot2[1], opened); return
    if (l := _phase(t, 0.82, 0.88)) is not None:
        # Wipe brow — one hand near head
        draw_figure_pose(canvas, spot2[0], spot2[1],
                         left_arm=(220, 280), right_arm=(80, 90))
        return
    if (l := _phase(t, 0.88, 0.94)) is not None:
        _walk(canvas, spot2, edge_xy, l); return
    if (l := _phase(t, 0.94, 1.00)) is not None:
        _hide_back(canvas, button, l, side); return


# ---- Animation 8: Little dance — three-spot tour with different moves ----
# Total ~12s. Side-step at spot 1, kick-line at spot 2, spin at spot 3.
def draw_anim_dance(canvas, t, w, h, button):
    side = _pick_emerge_side(button, w)
    edge_xy = _emerge_position(button, side, 0.0)
    spot1 = (edge_xy[0] + side * 90,  h * 0.55)
    spot2 = (edge_xy[0] + side * 200, h * 0.65)
    spot3 = (edge_xy[0] + side * 310, h * 0.55)

    if (l := _phase(t, 0.00, 0.05)) is not None:
        _emerge(canvas, button, l, side); return
    if (l := _phase(t, 0.05, 0.13)) is not None:
        _walk(canvas, edge_xy, spot1, l); return
    if (l := _phase(t, 0.13, 0.34)) is not None:
        # Side-step + arm waves
        beat = math.sin(l * 6 * math.pi)
        off = beat * 22
        arm = math.sin(l * 6 * math.pi + 1.0) * 60
        bounce = -abs(beat) * 5
        draw_figure_pose(
            canvas, spot1[0] + off, spot1[1] + bounce,
            left_arm=(90 + arm, 90 + arm * 0.6),
            right_arm=(90 - arm, 90 - arm * 0.6),
        )
        return
    if (l := _phase(t, 0.34, 0.42)) is not None:
        _walk(canvas, spot1, spot2, l); return
    if (l := _phase(t, 0.42, 0.62)) is not None:
        # Kick-line: alternating leg lifts
        kick = math.sin(l * 5 * math.pi)
        leg_lift = max(0, kick) * 35
        opposite = max(0, -kick) * 35
        draw_figure_pose(
            canvas, spot2[0], spot2[1],
            left_arm=(60, 60), right_arm=(120, 120),
            left_leg=(90 - leg_lift, 90 - leg_lift * 0.8),
            right_leg=(90 + opposite, 90 + opposite * 0.8),
        )
        return
    if (l := _phase(t, 0.62, 0.70)) is not None:
        _walk(canvas, spot2, spot3, l); return
    if (l := _phase(t, 0.70, 0.88)) is not None:
        # Spin: horizontal squish to fake rotation around vertical axis
        spin = (l - 0.5) * 4
        squish = abs(math.cos(spin * math.pi))
        draw_figure_pose(
            canvas, spot3[0], spot3[1],
            left_arm=(180, 180), right_arm=(0, 0),
            scale=max(0.25, squish),
        )
        return
    if (l := _phase(t, 0.88, 0.94)) is not None:
        _walk(canvas, spot3, edge_xy, l); return
    if (l := _phase(t, 0.94, 1.00)) is not None:
        _hide_back(canvas, button, l, side); return


# ---- Animation 9: Cartwheels — fast, big lateral travel ----
# Total ~8s. Two full cartwheels out, recovery, two cartwheels back.
def draw_anim_cartwheel(canvas, t, w, h, button):
    side = _pick_emerge_side(button, w)
    edge_xy = _emerge_position(button, side, 0.0)
    launch = (edge_xy[0] + side * 50, h * 0.55)
    far = (edge_xy[0] + side * (w * 0.36), h * 0.55)

    if (l := _phase(t, 0.00, 0.05)) is not None:
        _emerge(canvas, button, l, side); return
    if (l := _phase(t, 0.05, 0.10)) is not None:
        _walk(canvas, edge_xy, launch, l); return
    if (l := _phase(t, 0.10, 0.45)) is not None:
        eased = l   # near-linear cartwheel pace
        x = _lerp(launch[0], far[0], eased)
        rot = l * 4 * math.pi * side
        body_angle = (270 + math.degrees(rot)) % 360
        arm = body_angle
        leg = (body_angle + 180) % 360
        draw_figure_pose(canvas, x, launch[1],
                         body_angle=body_angle,
                         left_arm=(arm, arm), right_arm=(arm, arm),
                         left_leg=(leg, leg), right_leg=(leg, leg))
        return
    if (l := _phase(t, 0.45, 0.55)) is not None:
        # Recover at far side — stand with hands on hips, slight bounce
        bounce = math.sin(l * 6) * 2
        draw_figure_pose(canvas, far[0], far[1] + bounce,
                         left_arm=(150, 240), right_arm=(30, 300))
        return
    if (l := _phase(t, 0.55, 0.90)) is not None:
        x = _lerp(far[0], launch[0], l)
        rot = l * 4 * math.pi * (-side)
        body_angle = (270 + math.degrees(rot)) % 360
        arm = body_angle
        leg = (body_angle + 180) % 360
        draw_figure_pose(canvas, x, launch[1],
                         body_angle=body_angle,
                         left_arm=(arm, arm), right_arm=(arm, arm),
                         left_leg=(leg, leg), right_leg=(leg, leg))
        return
    if (l := _phase(t, 0.90, 0.95)) is not None:
        _walk(canvas, launch, edge_xy, l); return
    if (l := _phase(t, 0.95, 1.00)) is not None:
        _hide_back(canvas, button, l, side); return


# ---- Animation 10: Yoga — three poses at three spots ----
# Total ~13s. Tree → Warrior II → Mountain (reach up). Long holds, slow
# transitions; the figure breathes (subtle vertical bob) during each hold.
def draw_anim_yoga(canvas, t, w, h, button):
    side = _pick_emerge_side(button, w)
    edge_xy = _emerge_position(button, side, 0.0)
    spot1 = (edge_xy[0] + side * 100, h * 0.55)
    spot2 = (edge_xy[0] + side * 220, h * 0.55)
    spot3 = (edge_xy[0] + side * 340, h * 0.55)

    if (l := _phase(t, 0.00, 0.05)) is not None:
        _emerge(canvas, button, l, side); return
    if (l := _phase(t, 0.05, 0.13)) is not None:
        _walk(canvas, edge_xy, spot1, l); return
    if (l := _phase(t, 0.13, 0.32)) is not None:
        # Tree pose
        breath = math.sin(l * 4) * 2
        draw_figure_pose(canvas, spot1[0], spot1[1] + breath,
                         left_leg=(90, 90),
                         right_leg=(150, 60),
                         left_arm=(270, 270), right_arm=(270, 270))
        return
    if (l := _phase(t, 0.32, 0.40)) is not None:
        _walk(canvas, spot1, spot2, l); return
    if (l := _phase(t, 0.40, 0.62)) is not None:
        # Warrior II: legs wide, arms out
        breath = math.sin(l * 4) * 2
        draw_figure_pose(canvas, spot2[0], spot2[1] + breath,
                         left_leg=(120, 120), right_leg=(60, 60),
                         left_arm=(180, 180), right_arm=(0, 0))
        return
    if (l := _phase(t, 0.62, 0.70)) is not None:
        _walk(canvas, spot2, spot3, l); return
    if (l := _phase(t, 0.70, 0.88)) is not None:
        # Mountain / sun-salutation reach: both arms straight up
        breath = math.sin(l * 4) * 3
        draw_figure_pose(canvas, spot3[0], spot3[1] + breath,
                         left_arm=(270, 270), right_arm=(270, 270))
        return
    if (l := _phase(t, 0.88, 0.94)) is not None:
        _walk(canvas, spot3, edge_xy, l); return
    if (l := _phase(t, 0.94, 1.00)) is not None:
        _hide_back(canvas, button, l, side); return




# ---------------------------------------------------------------------------
# Registry — keep in iteration order so the picker lists them stably.
# Each entry's key is the stable id used in the config file's preferences
# dict. Renaming a key is a breaking change for user preferences.
# ---------------------------------------------------------------------------

ANIMATIONS: dict = {
    "surprise":  {"name": "Surprised!",        "duration_ms": 7000,  "draw_fn": draw_anim_surprise},
    "newspaper": {"name": "Reads the paper",   "duration_ms": 13000, "draw_fn": draw_anim_newspaper},
    "stretches": {"name": "Stretches",         "duration_ms": 11000,  "draw_fn": draw_anim_stretches},
    "horse":     {"name": "Horse ride",        "duration_ms": 9000, "draw_fn": draw_anim_horse},
    "jacks":     {"name": "Jumping jacks",     "duration_ms": 10000, "draw_fn": draw_anim_jacks},
    "sleep":     {"name": "Power nap",         "duration_ms": 14000, "draw_fn": draw_anim_sleep},
    "weights":   {"name": "Lifts weights",     "duration_ms": 11000, "draw_fn": draw_anim_weights},
    "dance":     {"name": "Little dance",      "duration_ms": 12000, "draw_fn": draw_anim_dance},
    "cartwheel": {"name": "Cartwheels",        "duration_ms": 8000,  "draw_fn": draw_anim_cartwheel},
    "yoga":      {"name": "Yoga tree pose",    "duration_ms": 13000, "draw_fn": draw_anim_yoga},
}


# ---------------------------------------------------------------------------
# Trigger state machine — used by the main app only. Per-session memory.
# ---------------------------------------------------------------------------


class AnimationTrigger:
    """Decides when an outgoing Ready should fire an animation.

    A send only 'qualifies' if at least MIN_SPACING_SEC has elapsed since the
    previous qualifying send. Rapid clicks all collapse into a single
    qualifying send — preventing someone from triggering the bonus by
    spamming the Ready button. Once the qualifying-send count reaches a
    randomly chosen target in [MIN_COUNT, MAX_COUNT], an animation fires
    and the counter resets with a fresh random target.

    State is in-memory only. App restart starts the counter fresh — which is
    fine for a cosmetic feature and prevents persistence-based gaming."""

    MIN_SPACING_SEC = 10 * 60
    MIN_COUNT = 4
    MAX_COUNT = 8

    def __init__(self, rng: Optional[random.Random] = None):
        self._rng = rng or random.Random()
        self._last_qualifying_monotonic: float = -float("inf")
        self._qualifying_count: int = 0
        self._target: int = self._pick_target()

    def _pick_target(self) -> int:
        return self._rng.randint(self.MIN_COUNT, self.MAX_COUNT)

    def on_ready_sent(self) -> bool:
        """Call once per outgoing Ready broadcast. Returns True if the caller
        should fire an animation now."""
        now = time.monotonic()
        if now - self._last_qualifying_monotonic < self.MIN_SPACING_SEC:
            return False  # too soon since last qualifying send
        self._last_qualifying_monotonic = now
        self._qualifying_count += 1
        if self._qualifying_count >= self._target:
            self._qualifying_count = 0
            self._target = self._pick_target()
            return True
        return False


# ---------------------------------------------------------------------------
# Convenience for the main app's "fire a random enabled animation" path.
# ---------------------------------------------------------------------------


def pick_random_enabled_animation(
    prefs: Optional[dict] = None,
    rng: Optional[random.Random] = None,
) -> Optional[str]:
    """Return a random animation id from the set that the user has enabled,
    or None if all are disabled (or no prefs file exists and the default
    'all enabled' set is somehow empty)."""
    if prefs is None:
        prefs = load_animation_prefs()
    if rng is None:
        rng = random
    enabled = [
        aid for aid in ANIMATIONS
        if prefs.get(aid, True)   # default to enabled when key missing
    ]
    if not enabled:
        return None
    return rng.choice(enabled)
