#!/usr/bin/env python3

import requests
import subprocess
import re
import sys
import json
import sqlite3
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import os
import time
from datetime import datetime
import locale
import pathlib
import argparse
import asyncio
import shutil
import threading
import difflib

try:
    from textual.app import App, ComposeResult
    from textual.widgets import Static, ListView, ListItem, Label, Input
    from textual.containers import Container, Horizontal, VerticalScroll
    from textual.reactive import reactive
    from textual.message import Message
    from textual.screen import Screen
    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False

HEADERS_BASE = {
    "user-agent": "Mozilla/5.0 (X11; Linux x86_64; rv:134.0) Gecko/20100101 Firefox/134.0",
    "accept-language": "en-US,en;q=0.5",
    "connection": "keep-alive"
}

MENU_ITEMS = [
    ("Recherche d'anime", "search"),
    ("Historique", "history"),
    ("Planning", "planning"),
    ("À venir", "upcoming")
]


FALLBACK_DOMAIN = "anime-sama.to"

KITTY_COVER_ID = 1337

# OP/ED timestamps are fetched from the AniSkip API (https://api.aniskip.com),
# an approach inspired by ani-skip (https://github.com/synacktraa/ani-skip).
_SKIP_OP_LUA = r"""
local options = require("mp.options")
local assdraw = require("mp.assdraw")

local o = {
    duration = 90,
    key = "s",
    show_duration = 150,
    text = "Skip OP \xc2\xbb",
    text_ed = "Skip ED \xc2\xbb",
    auto = true,
    op_start = 0,
    op_end = 0,
    ed_start = 0,
    ed_end = 0,
}
options.read_options(o, "skip_op")

local OP_KEYWORDS = { "op", "opening", "intro", "générique" }

local function has_known_segments()
    return (o.op_end > o.op_start) or (o.ed_end > o.ed_start)
end

local function known_segment(pos)
    if o.op_end > o.op_start and pos >= o.op_start and pos < o.op_end then
        return "op"
    end
    if o.ed_end > o.ed_start and pos >= o.ed_start and pos < o.ed_end then
        return "ed"
    end
    return nil
end

local function jump_to(target, message)
    local duration = mp.get_property_number("duration")
    if duration and target > duration - 0.5 then
        target = math.max(duration - 0.5, 0)
    end
    mp.set_property_number("time-pos", target)
    mp.osd_message(message .. " \xe2\x8f\xad")
end

local function is_op_chapter(title)
    if not title then
        return false
    end
    title = title:lower()
    for _, kw in ipairs(OP_KEYWORDS) do
        if title:find(kw, 1, true) then
            return true
        end
    end
    return false
end

local function current_chapter_is_op(pos, duration)
    local chapters = mp.get_property_native("chapter-list")
    if not chapters or #chapters == 0 then
        return false
    end
    for i, ch in ipairs(chapters) do
        local ch_end = chapters[i + 1] and chapters[i + 1].time or duration
        if pos >= ch.time and (not ch_end or pos < ch_end) then
            return is_op_chapter(ch.title)
        end
    end
    return false
end

local function skip_op()
    local pos = mp.get_property_number("time-pos")
    local duration = mp.get_property_number("duration")
    if not pos then
        return
    end
    local seg = known_segment(pos)
    if seg == "op" then
        jump_to(o.op_end, "Opening skipped")
        return
    elseif seg == "ed" then
        jump_to(o.ed_end, "Ending skipped")
        return
    end
    local chapters = mp.get_property_native("chapter-list")
    if chapters and #chapters > 0 then
        for i, ch in ipairs(chapters) do
            local ch_end = chapters[i + 1] and chapters[i + 1].time or duration
            if pos >= ch.time and (not ch_end or pos < ch_end) then
                if is_op_chapter(ch.title) then
                    if chapters[i + 1] then
                        mp.set_property_number("time-pos", chapters[i + 1].time)
                    elseif duration then
                        mp.set_property_number("time-pos", math.max(duration - 1, 0))
                    end
                    mp.osd_message("Opening skipped \xe2\x8f\xad")
                    return
                end
                break
            end
        end
    end
    jump_to(pos + o.duration, ("Skip +%ds"):format(o.duration))
end

local skipped = { op = false, ed = false }

local function auto_skip(_, pos)
    if not o.auto or not pos then
        return
    end
    local seg = known_segment(pos)
    if seg and not skipped[seg] then
        skipped[seg] = true
        if seg == "op" then
            jump_to(o.op_end, "Opening skipped")
        else
            jump_to(o.ed_end, "Ending skipped")
        end
    end
end

local overlay = mp.create_osd_overlay("ass")
local btn = { x = 0, y = 0, w = 0, h = 0, visible = false, hover = false, label = o.text }
local click_section_enabled = false

local function set_click_section(on)
    if on == click_section_enabled then
        return
    end
    click_section_enabled = on
    if on then
        mp.commandv("enable-section", "skip_op_click", "allow-hide-cursor+allow-vo-dragging")
    else
        mp.commandv("disable-section", "skip_op_click")
    end
end

local function render()
    if not btn.visible then
        overlay:remove()
        return
    end
    local osd_w = mp.get_property_number("osd-width") or 0
    local osd_h = mp.get_property_number("osd-height") or 0
    if osd_w <= 0 or osd_h <= 0 then
        osd_w = mp.get_property_number("width") or 0
        osd_h = mp.get_property_number("height") or 0
    end
    if osd_w <= 0 or osd_h <= 0 then
        overlay:remove()
        return
    end
    local fs = math.max(18, osd_h * 0.035)
    btn.h = fs * 1.9
    btn.w = fs * 5.4
    btn.x = osd_w - btn.w - osd_w * 0.04
    btn.y = osd_h * 0.70

    local bg_color = btn.hover and "&H50E0E0E0&" or "&H50282828&"
    local border_color = btn.hover and "&H00FFFFFF&" or "&H00AAAAAA&"
    local text_color = btn.hover and "&H00282828&" or "&H00FFFFFF&"

    local a = assdraw.ass_new()
    a:pos(0, 0)
    a:append(("{\\1c%s\\1a&H00&\\bord1.5\\3c%s\\3a&H00&\\p1}"):format(bg_color, border_color))
    a:draw_start()
    a:round_rect_cw(btn.x, btn.y, btn.x + btn.w, btn.y + btn.h, fs * 0.5)
    a:draw_stop()
    a:append("{\\p0}")
    a:new_event()
    a:an(5)
    a:pos(btn.x + btn.w / 2, btn.y + btn.h / 2 - fs * 0.08)
    a:append(("{\\fs%f\\bord0\\shad0\\1c%s\\b1}%s"):format(fs, text_color, btn.label))
    overlay.data = a.text
    overlay:update()
end

local function mouse_over_button()
    local m = mp.get_property_native("mouse-pos")
    if not m or not m.x then
        return false
    end
    return m.x >= btn.x and m.x <= btn.x + btn.w and m.y >= btn.y and m.y <= btn.y + btn.h
end

local function update_visibility()
    local pos = mp.get_property_number("time-pos")
    local duration = mp.get_property_number("duration")
    local should = false
    if pos then
        if has_known_segments() then
            local seg = known_segment(pos)
            should = seg ~= nil
            btn.label = seg == "ed" and o.text_ed or o.text
        else
            should = (o.show_duration <= 0 or pos < o.show_duration)
                or current_chapter_is_op(pos, duration)
            btn.label = o.text
        end
    end
    btn.visible = should
    set_click_section(should)
    render()
end

local function on_click()
    if btn.visible and mouse_over_button() then
        skip_op()
        return
    end
    set_click_section(false)
    mp.commandv("keypress", "MBTN_LEFT")
    mp.add_timeout(0.1, function()
        if btn.visible then
            set_click_section(true)
        end
    end)
end

mp.commandv("define-section", "skip_op_click",
    "MBTN_LEFT script-binding " .. mp.get_script_name() .. "/click", "default")
mp.add_key_binding(nil, "click", on_click)

mp.observe_property("mouse-pos", "native", function(_, m)
    if not btn.visible or not m or not m.x then
        return
    end
    local hover = m.x >= btn.x and m.x <= btn.x + btn.w and m.y >= btn.y and m.y <= btn.y + btn.h
    if hover ~= btn.hover then
        btn.hover = hover
        render()
    end
end)

mp.observe_property("time-pos", "number", update_visibility)
mp.observe_property("time-pos", "number", auto_skip)
mp.observe_property("chapter-list", "native", update_visibility)
mp.observe_property("osd-dimensions", "native", function()
    if btn.visible then
        render()
    end
end)
mp.register_event("file-loaded", function()
    skipped.op = false
    skipped.ed = false
    update_visibility()
end)

mp.add_key_binding(o.key, "skip_op", skip_op)
"""


def _cache_dir():
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.join(pathlib.Path.home(), "AppData", "Local")
        return os.path.join(base, "animesama", "cache")
    if sys.platform == "darwin":
        return os.path.join(pathlib.Path.home(), "Library", "Caches", "animesama")
    base = os.environ.get("XDG_CACHE_HOME") or os.path.join(pathlib.Path.home(), ".cache")
    return os.path.join(base, "animesama")


def _get_skip_op_script_path():
    try:
        cache = _cache_dir()
        os.makedirs(cache, exist_ok=True)
        path = os.path.join(cache, "skip_op.lua")
        content = _SKIP_OP_LUA.strip() + "\n"
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
        else:
            with open(path, "r", encoding="utf-8") as f:
                if f.read() != content:
                    with open(path, "w", encoding="utf-8") as fw:
                        fw.write(content)
        return path
    except OSError:
        return None


def _load_json_cache(name):
    try:
        with open(os.path.join(_cache_dir(), name), "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save_json_cache(name, data):
    try:
        os.makedirs(_cache_dir(), exist_ok=True)
        with open(os.path.join(_cache_dir(), name), "w", encoding="utf-8") as f:
            json.dump(data, f)
    except OSError:
        pass


def _skip_queries(anime_name, saison=None):
    name = re.sub(r'\s+', ' ', anime_name or '').strip()
    name = re.sub(r'\s*[-:]\s*(vostfr|vf)$', '', name, flags=re.IGNORECASE)
    queries = []
    match = re.search(r'saison\s*(\d+)', saison or '', re.IGNORECASE)
    if match and int(match.group(1)) > 1:
        n = int(match.group(1))
        ordinal = {1: "1st", 2: "2nd", 3: "3rd"}.get(n, f"{n}th")
        queries.append(f"{name} Season {n}")
        queries.append(f"{name} {ordinal} Season")
    queries.append(name)
    return queries


def _title_matches(query, title):
    def norm(text):
        return re.sub(r'[^a-z0-9]+', ' ', (text or '').lower()).strip()
    q, t = norm(query), norm(title)
    if not q or not t:
        return False
    if q in t or t in q:
        return True
    return difflib.SequenceMatcher(None, q, t).ratio() >= 0.7


def _resolve_mal_ids(query):
    try:
        resp = requests.get(
            "https://myanimelist.net/search/prefix.json",
            params={"type": "anime", "keyword": query},
            headers=HEADERS_BASE, timeout=5
        )
        data = resp.json()
        for category in data.get("categories", []):
            if category.get("type") == "anime":
                return [
                    item["id"] for item in category.get("items", [])
                    if _title_matches(query, item.get("name"))
                    or item.get("es_score", 0) >= 1.0
                ][:5]
    except Exception:
        pass
    return []


def _fetch_aniskip_times(mal_id, episode):
    try:
        resp = requests.get(
            f"https://api.aniskip.com/v1/skip-times/{mal_id}/{episode}",
            params={"types": ["op", "ed"]}, timeout=5
        )
        data = resp.json()
        if not data.get("found"):
            return None
        times = {}
        for result in data.get("results", []):
            interval = result.get("interval", {})
            start = interval.get("start_time")
            end = interval.get("end_time")
            if start is not None and end is not None:
                times[f"{result.get('skip_type')}_start"] = float(start)
                times[f"{result.get('skip_type')}_end"] = float(end)
        return times or None
    except Exception:
        return None


def _get_skip_times(anime_name, episode, saison=None):
    if not anime_name or episode is None:
        return None
    ep_match = re.search(r'(\d+)', str(episode))
    if not ep_match:
        return None
    ep = int(ep_match.group(1))
    cache_key = f"{anime_name}|{saison or ''}|{ep}".lower()
    cache = _load_json_cache("skip_times.json")
    if cache_key in cache:
        return cache[cache_key]
    for query in _skip_queries(anime_name, saison):
        for mal_id in _resolve_mal_ids(query):
            times = _fetch_aniskip_times(mal_id, ep)
            if times:
                cache[cache_key] = times
                _save_json_cache("skip_times.json", cache)
                return times
    cache[cache_key] = None
    _save_json_cache("skip_times.json", cache)
    return None


def _format_skip_times(times):
    def fmt(seconds):
        m, s = divmod(int(seconds), 60)
        return f"{m:02d}:{s:02d}"
    parts = []
    if "op_start" in times:
        parts.append(f"OP {fmt(times['op_start'])} → {fmt(times['op_end'])}")
    if "ed_start" in times:
        parts.append(f"ED {fmt(times['ed_start'])} → {fmt(times['ed_end'])}")
    return " · ".join(parts)


def _mpv_command(video_url, anime_name=None, episode=None, saison=None, status_cb=None):
    cmd = ['mpv', video_url, '--fullscreen']
    skip_script = _get_skip_op_script_path()
    if skip_script:
        cmd.append(f'--scripts-append={skip_script}')
        if anime_name and status_cb:
            status_cb("Recherche des timestamps OP/ED (AniSkip)…")
        times = _get_skip_times(anime_name, episode, saison)
        if times:
            opts = ",".join(f"skip_op-{key}={value:.3f}" for key, value in times.items())
            cmd.append(f'--script-opts={opts}')
            if status_cb:
                status_cb(f"Timestamps trouvés : {_format_skip_times(times)} — skip automatique activé")
    return cmd

def _kitty_dbg(msg):
    if not os.environ.get("ANIMESAMA_KITTY_DEBUG"):
        return
    try:
        with open("/tmp/animesama_kitty_debug.log", "a") as f:
            f.write(str(msg) + "\n")
    except OSError:
        pass

def _supports_kitty_graphics():
    term = os.environ.get("TERM", "")
    if "kitty" in term:
        return True
    if os.environ.get("KITTY_WINDOW_ID"):
        return True
    prog = os.environ.get("TERM_PROGRAM", "").lower()
    return prog in ("ghostty", "wezterm", "konsole")

def resolve_final_domain(domain):
    try:
        resp = requests.head(f"https://{domain}", headers=HEADERS_BASE, timeout=5, allow_redirects=True)
        final = urlparse(resp.url).hostname
        return final if final else domain
    except requests.RequestException:
        return domain

def get_current_domain_name():
    resolved = None
    try:
        response = requests.get("https://anime-sama.pw/", headers=HEADERS_BASE, timeout=5)
        soup = BeautifulSoup(response.text, 'html.parser')
        for tag in soup.find_all(['button', 'a']):
            text = tag.get_text(strip=True)
            if 'anime-sama' in text and '.' in text and 'pw' not in text:
                resolved = text
                break
            href = tag.get('href')
            if href and 'anime-sama' in href and 'pw' not in href:
                match = re.search(r'https?://([^/]+)', href)
                if match:
                    resolved = match.group(1)
                    break
    except Exception:
        pass

    if resolved:
        final = resolve_final_domain(resolved)
        if final != resolved:
            resolved = final

    if not resolved:
        resolved = FALLBACK_DOMAIN

    return resolved


DOMAIN = FALLBACK_DOMAIN
IS_DOMAIN_AVAILABLE = True
_domain_lock = threading.Lock()
_domain_resolved = False

def check_domain_access():
    try:
        response = requests.head(f"https://{DOMAIN}", headers=HEADERS_BASE, timeout=5, allow_redirects=True)
        return response.status_code == 200
    except requests.RequestException:
        return False

def ensure_domain(check_availability=False):
    global DOMAIN, IS_DOMAIN_AVAILABLE, _domain_resolved
    if _domain_resolved:
        return
    with _domain_lock:
        if _domain_resolved:
            return
        try:
            resolved = get_current_domain_name()
            if resolved:
                DOMAIN = resolved
        except Exception:
            pass
        if check_availability:
            IS_DOMAIN_AVAILABLE = check_domain_access()
        _domain_resolved = True

def get_db_path():
    db_dir = os.path.expanduser("~/.local/share/animesama-cli")
    os.makedirs(db_dir, exist_ok=True)
    return os.path.join(db_dir, "history.db")

def init_db():
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        anime_name TEXT NOT NULL,
        episode TEXT NOT NULL,
        saison TEXT NOT NULL,
        url TEXT NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    conn.commit()
    conn.close()

def add_to_history(anime_name, episode, saison, url, debug=False):
    try:
        init_db()
        conn = sqlite3.connect(get_db_path())
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM history WHERE anime_name = ? AND saison = ?", 
            (anime_name, saison)
        )
        existing_entry = cursor.fetchone()
        if existing_entry:
            cursor.execute(
                "UPDATE history SET episode = ?, timestamp = CURRENT_TIMESTAMP WHERE id = ?",
                (episode, existing_entry[0])
            )
            if debug:
                print("[DEBUG] Historique mis à jour avec succès")
            else:
                print("✓ Historique mis à jour avec succès")
        else:
            cursor.execute(
                "INSERT INTO history (anime_name, episode, saison, url) VALUES (?, ?, ?, ?)",
                (anime_name, episode, saison, url)
            )
            if debug:
                print("[DEBUG] Ajouté à l'historique avec succès")
            else:
                print("✓ Ajouté à l'historique avec succès")
        conn.commit()
        conn.close()
    except Exception as e:
        if debug:
            print(f"[DEBUG] Erreur lors de l'ajout à l'historique: {e}")
        else:
            print(f"✗ Erreur lors de l'ajout à l'historique")

def get_history_entries():
    db_path = get_db_path()
    if not os.path.exists(db_path):
        return []
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, anime_name, episode, saison, url FROM history ORDER BY timestamp DESC")
    entries = cursor.fetchall()
    conn.close()
    return entries

def delete_history_entry(entry_id):
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute("DELETE FROM history WHERE id = ?", (entry_id,))
    conn.commit()
    conn.close()

def get_seasons(html_content):
    seasons = []
    pattern = r'panneauAnime\("([^"]+)",\s*"([^"]+)"\)'
    soup = BeautifulSoup(html_content, 'html.parser')
    season_buttons = soup.find_all('button', {'onclick': True})
    season_divs = soup.find_all('div', class_=lambda x: x and 'saison' in x.lower())
    matches = re.findall(pattern, html_content)
    if not matches:
        return []
    for name, path in matches:
        if "film" not in name.lower() and name.lower() != "nom":
            seasons.append({
                'name': name,
                'url': path
            })
    return seasons

def get_episode_list(url):
    url = url.replace('https://', '')
    headers = {
        "host": DOMAIN,
        "user-agent": "Mozilla/5.0 (X11; Linux x86_64; rv:134.0) Gecko/134.0",
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "accept-language": "en-US,en;q=0.5",
        "connection": "keep-alive",
        "upgrade-insecure-requests": "1",
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "same-origin",
        "sec-fetch-user": "?1"
    }
    try:
        response = requests.get(f"https://{url}", headers=headers)
        content = response.text
        pattern = r'episodes\.js\?filever=(\d+)'
        match = re.search(pattern, content)
        if match:
            filever = match.group(1)
            return filever
        return None
    except Exception as e:
        print(f"Erreur lors de la requête : {str(e)}")
        return None

class AnimeDownloader:
    def __init__(self, debug=False):
        self.session = requests.Session()
        self.session.headers.update(HEADERS_BASE)
        self.debug = debug

    def debug_print(self, *args, **kwargs):
        if self.debug:
            print("[DEBUG]", *args, **kwargs)

    def get_anime_episode(self, complete_url, filever):
        complete_url = complete_url.replace('https://', '')
        url = f"https://{complete_url}/episodes.js"
        try:
            response = self.session.get(url, params={"filever": filever}, timeout=15)
            response.raise_for_status()
            content = response.text
            embed_links = {}
            matches = re.finditer(r"var eps\d+\s*=\s*\[([^\]]+)\]", content)
            for ep_var_match in matches:
                urls_block = ep_var_match.group(1)
                vid_urls = re.findall(r"'([^']+)'", urls_block)
                for i, vid_url in enumerate(vid_urls, 1):
                    embed_links.setdefault(str(i), [])
                    if vid_url not in embed_links[str(i)]:
                        embed_links[str(i)].append(vid_url)
            return embed_links
        except requests.RequestException as e:
            print(f"Erreur lors de la récupération des épisodes : {e}")
            return {}

    def resolve_video_url(self, video_ids):
        if isinstance(video_ids, str):
            video_ids = [video_ids]
        for video_id in video_ids:
            video_url = self.get_video_url(video_id)
            if video_url:
                return video_url
            print(f"Provider inaccessible, essai du suivant... ({video_id})")
        return None

    def get_video_url(self, video_id):
        try:
            print(f"Tentative de recuperation de la video...")

            if 'sibnet.ru' in video_id:
                vid_match = re.search(r'videoid=(\d+)', video_id)
                if vid_match:
                    return self._get_sibnet_url(vid_match.group(1))

            if 'vidmoly.to' in video_id:
                video_id = video_id.replace('vidmoly.to', 'vidmoly.biz')
            video_id = video_id.replace('vidmoly.net', 'vidmoly.biz')

            response = self.session.get(video_id, headers={
                **HEADERS_BASE,
                "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "referer": f"https://{DOMAIN}/",
            }, timeout=15)
            response.raise_for_status()
            html_content = response.text

            match = re.search(r"file:\s*'([^']+\.m3u8[^']*)'", html_content)
            if match:
                m3u8_url = match.group(1).replace('&amp;', '&')
                print(f"URL m3u8 trouvee.")
                return m3u8_url

            match = re.search(r'sources:\s*\[\s*\{\s*file:\s*"([^"]+)"', html_content)
            if match:
                m3u8_url = match.group(1).replace('&amp;', '&')
                print(f"URL m3u8 trouvee.")
                return m3u8_url

            match = re.search(r'(https?://[^\s"\']+\.mp4[^\s"\']*)', html_content)
            if match:
                mp4_url = match.group(1).replace('&amp;', '&')
                print(f"URL mp4 directe trouvee.")
                return mp4_url

            for unpacked in self._unpack_embed_scripts(html_content):
                match = re.search(r'(https?://[^\s"\'\\]+\.m3u8[^\s"\'\\]*)', unpacked)
                if match:
                    print(f"URL m3u8 trouvee (script packe).")
                    return match.group(1).replace('&amp;', '&')
                match = re.search(r'(https?://[^\s"\'\\]+\.mp4[^\s"\'\\]*)', unpacked)
                if match:
                    print(f"URL mp4 trouvee (script packe).")
                    return match.group(1).replace('&amp;', '&')

            print(f"Erreur : aucun flux video trouve dans l'embed ({len(html_content)} octets)")
            return None
        except requests.RequestException as e:
            print(f"Erreur lors de la recuperation de l'URL video : {e}")
            return None

    def _unpack_embed_scripts(self, html_content):
        pattern = r"eval\(function\(p,a,c,k,e,d\).*?\}\('(.*?)',\s*(\d+),\s*(\d+),\s*'(.*?)'\.split\('\|'\)"
        unpacked_pages = []
        for match in re.finditer(pattern, html_content, re.DOTALL):
            try:
                p, a, c = match.group(1), int(match.group(2)), int(match.group(3))
                k = match.group(4).split('|')
                digits = "0123456789abcdefghijklmnopqrstuvwxyz"

                def enc(num):
                    head = "" if num < a else enc(num // a)
                    r = num % a
                    return head + (chr(r + 29) if r > 35 else digits[r])

                table = {enc(i): k[i] for i in range(c) if i < len(k) and k[i]}
                unpacked = re.sub(r"\b\w+\b", lambda m: table.get(m.group(0), m.group(0)), p)
                unpacked_pages.append(unpacked)
            except Exception:
                continue
        return unpacked_pages

    def _get_sibnet_url(self, video_id):
        try:
            url = "https://video.sibnet.ru/shell.php"
            response = self.session.get(url, params={"videoid": video_id}, timeout=15)
            response.raise_for_status()
            html_content = response.text
            match = re.search(r'player\.src\(\[\{src: "/v/([^/]+)/', html_content)
            if match:
                video_hash = match.group(1)
                url_sibnet = f"https://video.sibnet.ru/v/{video_hash}/{video_id}.mp4"
                headers_sibnet = {
                    **HEADERS_BASE,
                    "range": "bytes=0-",
                    "accept-encoding": "identity",
                    "referer": "https://video.sibnet.ru/",
                }
                response_sibnet = self.session.get(url_sibnet, headers=headers_sibnet, allow_redirects=False, timeout=15)
                if response_sibnet.status_code == 302:
                    print(f"URL sibnet trouvee.")
                    return response_sibnet.headers['Location']
                else:
                    print(f"Status code sibnet inattendu : {response_sibnet.status_code}")
            else:
                print("Pattern sibnet non trouve dans le HTML")
            return None
        except requests.RequestException as e:
            print(f"Erreur sibnet : {e}")
            return None
        except requests.RequestException as e:
            print(f"Erreur lors de la récupération de l'URL vidéo : {e}")
            return None

    def get_catalogue(self, query="", vf=False): 
        try:
            url = f"https://{DOMAIN}/catalogue/"
            headers = {
                "host": DOMAIN,
                "connection": "keep-alive",
                "sec-ch-ua": "\"Not A(Brand\";v=\"8\", \"Chromium\";v=\"132\", \"Google Chrome\";v=\"132\"",
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": "\"Windows\"",
                "upgrade-insecure-requests": "1",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
                "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "sec-fetch-site": "same-origin",
                "sec-fetch-mode": "navigate",
                "sec-fetch-user": "?1",
                "sec-fetch-dest": "document",
                "referer": f"https://{DOMAIN}/catalogue/",
                "accept-language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7"
            }
            querystring = {"search": query, "type[]": "Anime"}
            if vf:
                querystring["langue[]"] = "VF"
            self.debug_print(f"Envoi requête GET vers: {url}")
            self.debug_print(f"Headers: {headers}")
            self.debug_print(f"Querystring: {querystring}")
            response = self.session.get(url, headers=headers, params=querystring)
            response.raise_for_status()
            self.debug_print(f"Status code: {response.status_code}")
            self.debug_print(f"Réponse brute: {response.text}")
            soup = BeautifulSoup(response.text, 'html.parser')
            animes = []
            urls = []
            seen_urls = set()
            for card in soup.find_all('a', href=True):
                href = card['href']
                if '/catalogue/' not in href or href in seen_urls:
                    continue
                if href == '/catalogue/' or href == '/catalogue':
                    continue
                titre_tag = card.find('h2', class_='card-title')
                if not titre_tag:
                    titre_tag = card.find('h1', class_='text-white font-bold uppercase text-md line-clamp-2')
                if titre_tag:
                    titre = titre_tag.text.strip()
                    if titre:
                        seen_urls.add(href)
                        animes.append(titre)
                        urls.append(href)
            if vf:
                urls = [link.replace("vostfr", "vf") for link in urls]
            self.debug_print(f"Nombre de titres trouvés: {len(animes)}")
            self.debug_print(f"Titres trouvés: {animes}")
            return animes, urls
        except requests.RequestException as e:
            print(f"Erreur lors de la récupération du catalogue : {e}")
            self.debug_print(f"Exception complète: {str(e)}")
            return [], []

def display_history(full_check=False):
    init_db()
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute("SELECT id, anime_name, episode, saison, url FROM history ORDER BY timestamp DESC")
    history_entries = cursor.fetchall()
    conn.close()
    if not history_entries:
        print("Aucun historique trouvé.")
        return
    print("\nHistorique :")
    for i, entry in enumerate(history_entries, 1):
        entry_id, anime_name, episode, saison, url = entry
        is_last = False
        match = re.search(r'(\d+)$', episode)
        if match and full_check:
            current_ep = int(match.group(1))
            filever = get_episode_list(url)
            if filever:
                episodes = AnimeDownloader(debug=False).get_anime_episode(url, filever)
                if episodes:
                    ep_keys_int = [int(e) for e in episodes.keys() if e.isdigit()]
                    if ep_keys_int and current_ep == max(ep_keys_int):
                        is_last = True
        line = f"{i}. {anime_name} - {episode} - {saison}"
        if is_last:
            line += " - Dernier épisode"
        print(line)
    print("0. Retour")
    choix = input("Numéro à relire, ou 'd' suivi du numéro pour supprimer (ex: d2), ou 0 pour retour : ").strip()
    if choix == "0":
        return
    if choix.startswith('d') and choix[1:].isdigit():
        idx = int(choix[1:]) - 1
        if 0 <= idx < len(history_entries):
            entry_id = history_entries[idx][0]
            conn = sqlite3.connect(get_db_path())
            cursor = conn.cursor()
            cursor.execute("DELETE FROM history WHERE id = ?", (entry_id,))
            conn.commit()
            conn.close()
            print("Entrée supprimée.")
        else:
            print("Numéro invalide.")
        return
    if choix.isdigit():
        idx = int(choix) - 1
        if 0 <= idx < len(history_entries):
            entry = history_entries[idx]
            anime_name, episode, saison, url = entry[1:5]
            print(f"Lecture de {anime_name} - {episode} - {saison}")
            match = re.search(r'(\d+)$', episode)
            if match:
                current_ep = int(match.group(1))
            else:
                print("Impossible de déterminer l'épisode courant.")
                return
            filever = get_episode_list(url)
            if not filever:
                print("Impossible de récupérer la liste des épisodes.")
                return
            downloader = AnimeDownloader(debug=False)
            episodes = downloader.get_anime_episode(url, filever)
            if not episodes:
                print("Aucun épisode trouvé.")
                return
            ep_keys = list(episodes.keys())
            ep_keys_int = [int(e) for e in ep_keys if e.isdigit()]
            ep_keys_int.sort()
            next_ep = None
            for ep in ep_keys_int:
                if ep > current_ep:
                    next_ep = ep
                    break
            if next_ep is None:
                print(f"Vous avez déjà vu le dernier épisode : {anime_name} - Episode {current_ep} - {saison} - Dernier épisode (déjà vu)")
                return
            video_ids = episodes[str(next_ep)]
            print(f"Récupération de l'épisode {next_ep}...")
            video_url = downloader.resolve_video_url(video_ids)
            if not video_url:
                print("Impossible de récupérer l'URL de la vidéo.")
                return
            if video_url.startswith('//'):
                video_url = 'https:' + video_url
            print(f"Lecture de la vidéo avec mpv...")
            try:
                subprocess.run(_mpv_command(video_url, anime_name, next_ep, saison, status_cb=print), check=True)
                add_to_history(
                    anime_name=anime_name,
                    episode=f"Episode {next_ep}",
                    saison=saison,
                    url=url,
                    debug=False
                )
            except FileNotFoundError:
                print("Erreur : mpv n'est pas installé. Installe-le d'abord (sudo apt install mpv / yay -S mpv / mpv.io sur Windows).")
            except Exception as e:
                print(f"Erreur lors de la lecture : {e}")
        else:
            print("Numéro invalide.")
        return
    print("Entrée non reconnue.")

def _is_scan_url(url):
    parts = [p for p in url.strip().split('/') if p]
    return len(parts) >= 3 and parts[2].lower().startswith('scan')

def afficher_planning():
    print("\n--- Planning des animes (texte) ---")
    url = f"https://{DOMAIN}/planning/"
    headers = HEADERS_BASE.copy()
    response = requests.get(url, headers=headers)
    html_content = response.text
    day_pattern = r'<h2 class="titreJours[^>]*>([^<]+)</h2>'
    days = re.findall(day_pattern, html_content)
    planning = {day.strip(): [] for day in days}
    day_sections = re.split(day_pattern, html_content)
    for i in range(1, len(day_sections), 2):
        current_day = day_sections[i].strip()
        day_content = day_sections[i + 1]
        if current_day in planning:
            cards = re.findall(
                r'<a href="(/catalogue/[^"]+)"[^>]*>.*?<h3[^>]*>([^<]+)</h3>',
                day_content, re.DOTALL
            )
            if not cards:
                cards = re.findall(
                    r'<a href="(/catalogue/[^"]+)"[^>]*>.*?<img[^>]*alt="([^"]*)"',
                    day_content, re.DOTALL
                )
            for card_url, card_title in cards:
                if _is_scan_url(card_url):
                    continue
                planning[current_day].append((card_title.strip(), card_url.strip(), "", ""))
    days_list = list(planning.keys())
    for i, day in enumerate(days_list, 1):
        print(f"{i}. {day}")
    print("0. Retour")
    choix = input("Numéro du jour : ").strip()
    if choix == "0":
        return
    if not choix.isdigit() or int(choix) < 1 or int(choix) > len(days_list):
        print("Numéro invalide.")
        return
    selected_day = days_list[int(choix)-1]
    animes = planning[selected_day]
    if not animes:
        print("Aucun anime ce jour.")
        return
    for i, (title, url, time, version) in enumerate(animes, 1):
        print(f"{i}. {title}")
    print("0. Retour")
    choix = input("Numéro de l'anime : ").strip()
    if choix == "0":
        return
    if not choix.isdigit() or int(choix) < 1 or int(choix) > len(animes):
        print("Numéro invalide.")
        return
    selected_anime = animes[int(choix)-1]
    anime_url = f"https://{DOMAIN}{selected_anime[1]}"
    print(f"URL de la saison : {anime_url}")
    afficher_episodes_saison(anime_url, selected_anime[0], "")

def display_upcoming():
    print("\n--- Prochains épisodes à sortir (texte) ---")
    url = "https://animecountdown.com/upcoming"
    headers = HEADERS_BASE.copy()
    response = requests.get(url, headers=headers)
    html_content = response.text
    soup = BeautifulSoup(html_content, 'html.parser')
    anime_list = soup.find_all('a', class_='countdown-content-trending-item')
    display_items = []
    for anime in anime_list:
        anime_title = anime.find('countdown-content-trending-item-title').text.strip()
        anime_episode = anime.find('countdown-content-trending-item-desc').text.strip()
        display_items.append(f"{anime_title} - {anime_episode}")
    for i, item in enumerate(display_items, 1):
        print(f"{i}. {item}")
    print("0. Retour")
    input("Appuyez sur entrée pour revenir au menu principal.")

def display_help():
    help_text = """
Usage: anime [OPTIONS] [SEARCH_TERM]

Options:
    -h, --help      Affiche ce message d'aide
    -c, --continue  Affiche l'historique des animes regardés
    -f, --full      Active la vérification des derniers épisodes dans l'historique
    --vf            Recherche uniquement les animes en version française (VF)
    --debug         Active le mode debug pour plus d'informations
    -p, --planing   Affiche le planning des animes par jour
    -up, --upcoming Affiche les prochains épisodes à sortir
    -t, --textual   Force l'utilisation de l'interface TUI (même comportement par défaut)
    --cli           Force l'utilisation de l'interface en ligne de commande traditionnelle
    -cf, --check-final  Historique avec vérification du dernier épisode

Information:
    L'historique est stocké localement dans ~/.local/share/animesama-cli/history.db
    Par défaut, l'interface utilisateur Textual (TUI) est utilisée si disponible.

Examples:
    anime                  # Lance l'interface TUI (ou CLI si Textual n'est pas installé)
    anime --cli            # Force l'utilisation de l'interface CLI traditionnelle
    anime naruto           # Recherche directement "naruto" (dans l'interface par défaut)
    anime --cli naruto     # Recherche "naruto" en utilisant l'interface CLI
    anime -c               # Affiche l'historique
    anime -cf              # Affiche l'historique avec vérification des derniers épisodes
    anime --vf naruto      # Recherche "naruto" uniquement en VF
    anime --debug naruto   # Recherche "naruto" avec le mode debug
    anime -p               # Affiche le planning des animes par jour
    anime -up              # Affiche les prochains épisodes à sortir
    """
    print(help_text)

def afficher_episodes_saison(url, anime_name, version):
    filever = get_episode_list(url)
    if not filever:
        print("Impossible de récupérer la liste des épisodes.")
        return
    episodes = AnimeDownloader(debug=False).get_anime_episode(url, filever)
    if not episodes:
        print("Aucun épisode trouvé.")
        return
    print("\nÉpisodes :")
    ep_keys = list(episodes.keys())
    for i, ep in enumerate(ep_keys, 1):
        print(f"{i}. Episode {ep}")
    idx = input("Numéro de l'épisode à regarder : ").strip()
    if not idx.isdigit() or int(idx) < 1 or int(idx) > len(ep_keys):
        print("Sélection invalide.")
        return
    selected_ep = ep_keys[int(idx) - 1]
    video_ids = episodes[selected_ep]
    print(f"Récupération de l'épisode {selected_ep}...")
    video_url = AnimeDownloader(debug=False).resolve_video_url(video_ids)
    if not video_url:
        print("Impossible de récupérer l'URL de la vidéo.")
        return
    if video_url.startswith('//'):
        video_url = 'https:' + video_url
    print(f"Lecture de la vidéo avec mpv...")
    try:
        subprocess.run(_mpv_command(video_url, anime_name, selected_ep, version, status_cb=print), check=True)
        saison = version
        url_lower = url.lower()
        if "saison" not in version.lower():
            match = re.search(r'/saison(\d+)', url_lower)
            if match:
                saison = f"Saison {match.group(1)}"
            elif "/oav" in url_lower or "/ova" in url_lower:
                saison = "OAV"
            elif "/film" in url_lower:
                saison = "Film"
            elif "/special" in url_lower:
                saison = "Special"
            else:
                saison = version
        if "vostfr" in url.lower():
            version_str = "VOSTFR"
        elif re.search(r'/vf/?', url.lower()):
            version_str = "VF"
        else:
            version_str = ""
        if version_str and version_str.lower() not in saison.lower():
            saison = f"{saison} - {version_str}"
        add_to_history(
            anime_name=anime_name,
            episode=f"Episode {selected_ep}",
            saison=saison,
            url=url,
            debug=False
        )
    except FileNotFoundError:
        print("Erreur : mpv n'est pas installé. Installe-le d'abord (sudo apt install mpv / yay -S mpv / mpv.io sur Windows).")
    except Exception as e:
        print(f"Erreur lors de la lecture : {e}")

def cli_main(args):
    if args.help:
        display_help()
        return

    ensure_domain()

    if args.planing:
        afficher_planning()
        return
    
    if args.upcoming:
        display_upcoming()
        return
    
    if args.continuer:
        display_history(args.full)
        return
    
    if not args.query:
        print("\nAnime-sama CLI (inspiré de ani-cli)")
        print("1. Recherche d'anime")
        print("2. Historique")
        print("3. Planning")
        print("4. À venir")
        print("5. Quitter")
        choix = input("Choix : ").strip()
        if choix == "1":
            query = input("Recherche : ").strip()
            if not query:
                print("Aucune recherche.")
                return
            args.query = [query]
        elif choix == "2":
            display_history(False)
            return
        elif choix == "3":
            afficher_planning()
            return
        elif choix == "4":
            display_upcoming()
            return
        else:
            print("Bye !")
            return
    
    query = " ".join(args.query)
    print(f"Recherche de : {query}")
    downloader = AnimeDownloader(debug=args.debug)
    animes, urls = downloader.get_catalogue(query, vf=args.vf)

    if not animes:
        print("Aucun anime trouvé.")
        return
    
    print("\nRésultats :")
    for i, anime in enumerate(animes, 1):
        print(f"{i}. {anime}")
    
    idx = input("Numéro de l'anime à sélectionner : ").strip()
    if not idx.isdigit() or int(idx) < 1 or int(idx) > len(animes):
        print("Sélection invalide.")
        return
    
    selected_anime = int(idx) - 1
    anime_url = urls[selected_anime]
    print(f"URL de l'anime : {anime_url}")
    response = requests.get(anime_url, headers=HEADERS_BASE)
    seasons = get_seasons(response.text)
    
    if not seasons:
        print("Aucune saison trouvée.")
        return
    
    print("\nSaisons :")
    for i, season in enumerate(seasons, 1):
        print(f"{i}. {season['name']}")
    
    idx = input("Numéro de la saison à sélectionner : ").strip()
    if not idx.isdigit() or int(idx) < 1 or int(idx) > len(seasons):
        print("Sélection invalide.")
        return
    
    selected_season = int(idx) - 1
    season_url = anime_url.rstrip('/') + '/' + seasons[selected_season]['url'].lstrip('/')
    if args.vf:
        season_url = season_url.replace("vostfr", "vf")
        print(f"URL corrigée pour la VF : {season_url}")
    
    print(f"URL de la saison : {season_url}")
    filever = get_episode_list(season_url)
    if not filever:
        print("Impossible de récupérer la liste des épisodes.")
        return
    
    episodes = downloader.get_anime_episode(season_url, filever)
    if not episodes:
        print("Aucun épisode trouvé.")
        return
    
    print("\nÉpisodes :")
    ep_keys = list(episodes.keys())
    for i, ep in enumerate(ep_keys, 1):
        print(f"{i}. Episode {ep}")
    
    idx = input("Numéro de l'épisode à regarder : ").strip()
    if not idx.isdigit() or int(idx) < 1 or int(idx) > len(ep_keys):
        print("Sélection invalide.")
        return
    
    selected_ep = ep_keys[int(idx) - 1]
    video_ids = episodes[selected_ep]
    print(f"Récupération de l'épisode {selected_ep}...")
    video_url = downloader.resolve_video_url(video_ids)
    
    if not video_url:
        print("Impossible de récupérer l'URL de la vidéo.")
        return
    
    if video_url.startswith('//'):
        video_url = 'https:' + video_url
    
    print(f"Lecture de la vidéo avec mpv...")
    try:
        subprocess.run(_mpv_command(video_url, animes[selected_anime], selected_ep, seasons[selected_season]['name'], status_cb=print), check=True)
        saison = seasons[selected_season]['name']
        if "saison" not in saison.lower():
            match = re.search(r'/saison(\d+)', season_url, re.IGNORECASE)
            if match:
                saison = f"Saison {match.group(1)}"
            else:
                saison = seasons[selected_season]['name']
        
        if "vostfr" in season_url.lower():
            version_str = "VOSTFR"
        elif re.search(r'/vf/?', season_url.lower()):
            version_str = "VF"
        else:
            version_str = ""
        
        if version_str and version_str.lower() not in saison.lower():
            saison = f"{saison} - {version_str}"
        
        add_to_history(
            anime_name=animes[selected_anime],
            episode=f"Episode {selected_ep}",
            saison=saison,
            url=season_url,
            debug=args.debug
        )
    except FileNotFoundError:
        print("Erreur : mpv n'est pas installé. Installe-le d'abord (sudo apt install mpv / yay -S mpv / mpv.io sur Windows).")
    except Exception as e:
        print(f"Erreur lors de la lecture : {e}")

EMBEDDED_CSS = r"""
$as-bg: #08080c;
$as-panel: #0f1119;
$as-border: #2a2d35;
$as-text: #ddd8ea;
$as-muted: #6b6577;
$as-primary: #6ea8fe;
$as-lavender: #8db8ff;
$as-green: #86d6a2;
$as-red: #e06c75;

Screen {
    background: $as-bg;
    color: $as-text;
}

#app-grid {
    layout: horizontal;
    height: 1fr;
}

#sidebar {
    width: 24;
    height: 100%;
    padding: 1 2 0 2;
    background: $as-bg;
}

#logo {
    color: $as-primary;
    text-style: bold;
    padding-bottom: 1;
    width: 100%;
}

#domain-status {
    color: $as-muted;
    padding-bottom: 1;
    width: 100%;
}

#nav, #lang-nav {
    background: transparent;
    border: none;
    height: auto;
    margin: 0;
    padding: 0;
}

#nav > ListItem, #lang-nav > ListItem {
    padding: 0 1;
    background: transparent;
    color: $as-muted;
    border-left: tall transparent;
}

#nav > ListItem.-highlight, #lang-nav > ListItem.-highlight {
    background: $as-panel;
    color: $as-primary;
    text-style: bold;
    border-left: tall $as-primary;
}

#content {
    width: 1fr;
    height: 100%;
    padding: 1 2 0 1;
    background: $as-bg;
}

SearchPane, HistoryPane, PlanningPane, UpcomingPane {
    border: round $as-border;
    background: $as-panel;
    padding: 0 1;
    height: 100%;
}

SearchPane:focus-within, HistoryPane:focus-within, PlanningPane:focus-within, UpcomingPane:focus-within {
    border: round $as-primary;
}

#search-input {
    height: 3;
    margin: 1 1 0 1;
    padding: 0 2;
    background: $as-bg;
    color: $as-text;
    border: round $as-border;
}

#search-input:focus {
    border: round $as-primary;
}

#search-input > .input--placeholder {
    color: $as-muted;
}

#search-result {
    color: $as-muted;
    padding: 1 2 0 2;
    height: auto;
}

ListView {
    background: transparent;
    border: none;
    margin: 0 1 1 1;
    padding: 0;
    height: 1fr;
}

#nav {
    height: auto;
    max-height: 100%;
    margin-top: 1;
}

#lang-nav {
    layout: horizontal;
    height: auto;
    margin-top: 1;
}

#lang-nav > ListItem {
    width: auto;
    padding: 0 1;
    border-left: none;
}

#lang-nav > ListItem.-highlight {
    border-left: none;
}

#sep {
    color: $as-border;
    width: 100%;
    height: 1;
    margin-top: 1;
}

#results-zone, #planning-zone {
    height: 1fr;
    margin-top: 1;
}

Column {
    width: 1fr;
    height: 100%;
    border: round $as-border;
    background: $as-bg;
    margin-right: 1;
}

Column.narrow {
    width: 16;
}

Column:focus-within {
    border: round $as-primary;
}

Column ListView {
    margin: 0;
    height: 1fr;
}

Column ListView > ListItem {
    height: auto;
}

Column ListView > ListItem > Label {
    width: 100%;
}

* {
    scrollbar-color: $as-primary 40%;
    scrollbar-color-hover: $as-primary 60%;
    scrollbar-color-active: $as-primary;
    scrollbar-background: $as-bg;
}

ListView > ListItem {
    padding: 0 1;
    background: transparent;
    color: $as-text;
}

ListView > ListItem.-highlight {
    background: $as-primary 20%;
    color: $as-text;
    text-style: bold;
}

ListView:focus > ListItem.-highlight {
    background: $as-primary 35%;
    color: $as-text;
    text-style: bold;
}

#status-bar {
    dock: bottom;
    height: 1;
    padding: 0 2;
    color: $as-muted;
    background: $as-bg;
}

#screen-title {
    width: 100%;
    padding: 1 2 0 2;
    text-style: bold;
    color: $as-text;
    background: transparent;
}

#screen-subtitle {
    width: 100%;
    padding: 0 2 1 2;
    color: $as-muted;
    background: transparent;
}

#screen-help {
    dock: bottom;
    width: 100%;
    height: 1;
    padding: 0 2;
    color: $as-muted;
    background: transparent;
}

#empty {
    width: 100%;
    padding: 2 3;
    content-align: center middle;
    color: $as-muted;
}

#info-slide {
    layout: horizontal;
    height: 1fr;
    overflow-x: auto;
}

#info-body, .info-side {
    width: 50%;
    height: 100%;
    padding: 0 2;
}

#info-body > Label, .info-side > Label {
    width: 100%;
}

.info-side {
    border-left: solid $as-border;
}

#info-cover {
    width: 100%;
    content-align: center top;
}

#info-grid {
    layout: grid;
    grid-size: 2;
    grid-gutter: 1 2;
    height: auto;
    width: 100%;
}

.info-cell {
    height: auto;
    width: 100%;
}

.info-alt {
    text-style: italic;
}

.info-section {
    color: $as-primary;
    text-style: bold;
    padding-top: 1;
}

#info-synopsis {
    color: $as-text;
    padding-bottom: 1;
}
"""


if TEXTUAL_AVAILABLE:
    NAV_ITEMS = [
        ("Recherche", "search"),
        ("Historique", "history"),
        ("Planning", "planning"),
        ("À venir", "upcoming"),
    ]
    NAV_INDEX = {action: i for i, (_, action) in enumerate(NAV_ITEMS)}
    LANG_ITEMS = ["VOSTFR", "VF"]

    HINT_COMMON = "[bold #8db8ff]tab[/] naviguer   [bold #8db8ff]échap[/] retour   [bold #8db8ff]ctrl+q[/] quitter"
    HINTS = {
        "search": f"[bold #8db8ff]entrée[/] rechercher / ouvrir   [bold #8db8ff]i[/] infos   {HINT_COMMON}",
        "history": f"[bold #8db8ff]entrée[/] reprendre   [bold #8db8ff]i[/] infos   [bold #8db8ff]d[/] supprimer   {HINT_COMMON}",
        "planning": f"[bold #8db8ff]entrée[/] ouvrir   [bold #8db8ff]i[/] infos   [bold #8db8ff]← →[/] naviguer   {HINT_COMMON}",
        "upcoming": HINT_COMMON,
    }

    ANIME_HEADERS = {
        "user-agent": "Mozilla/5.0 (X11; Linux x86_64; rv:134.0) Gecko/20100101 Firefox/134.0",
        "accept-language": "en-US,en;q=0.5",
        "connection": "keep-alive"
    }

    def _version_for_url(url):
        low = url.lower()
        if "vostfr" in low:
            return "VOSTFR"
        if "/vf" in low:
            return "VF"
        return ""

    def _version_tag(url):
        v = _version_for_url(url)
        if not v:
            low = url.lower()
            if "/vkr" in low:
                v = "VKR"
            elif "/va" in low:
                v = "VA"
        colors = {"VOSTFR": "#86d6a2", "VF": "#6ea8fe"}
        color = colors.get(v, "#6b6577")
        return f"  [{color}]{v}[/]" if v else ""

    def _season_tag(url):
        low = url.lower()
        match = re.search(r'/saison(\d+)(hs)?', low)
        if match:
            saison = f"Saison {match.group(1)}"
            if match.group(2):
                saison += " HS"
            return f"  [#6b6577]{saison}[/]"
        if "/kai" in low:
            return "  [#6b6577]Kai[/]"
        if "/oav" in low or "/ova" in low:
            return "  [#6b6577]OAV[/]"
        if "/film" in low:
            return "  [#6b6577]Film[/]"
        return ""

    def _fetch_seasons(anime_url):
        try:
            response = requests.get(anime_url, headers=ANIME_HEADERS)
            return get_seasons(response.text)
        except Exception:
            return []

    class HalfBlockImage:
        def __init__(self, image):
            if image.height % 2:
                image = image.crop((0, 0, image.width, image.height - 1))
            self.image = image

        def __rich_console__(self, console, options):
            from rich.segment import Segment
            from rich.style import Style
            px = self.image.load()
            w, h = self.image.size
            for y in range(0, h, 2):
                for x in range(w):
                    yield Segment("▄", Style(color=f"rgb{px[x, y]}", bgcolor=f"rgb{px[x, y + 1]}"))
                yield Segment("\n")

        def __rich_measure__(self, console, options):
            from rich.measure import Measurement
            w, _ = self.image.size
            return Measurement(w, w)

    def _anime_page_url(url):
        match = re.search(r'((?:https?://[^/]+)?/catalogue/[^/]+)', url)
        if not match:
            return None
        path = match.group(1)
        if path.startswith('http'):
            return path + '/'
        return f"https://{DOMAIN}{path}/"

    def _fetch_anime_info(anime_url):
        info = {"title": "", "alt_titles": "", "genres": [], "synopsis": "", "seasons": [], "cover": "", "details": []}
        try:
            response = requests.get(anime_url, headers=ANIME_HEADERS, timeout=15)
        except Exception:
            return None
        soup = BeautifulSoup(response.text, 'html.parser')
        h1 = soup.find('h1')
        if h1:
            info["title"] = h1.get_text(strip=True)
        alt = soup.find('h2', class_=lambda c: c and 'clamp-alters' in c)
        if alt:
            info["alt_titles"] = alt.get_text(strip=True)
        wrap = soup.find('div', class_='genres-wrap')
        if wrap:
            info["genres"] = [g.get_text(strip=True) for g in wrap.find_all('span', class_='genre-pill')]
        syn = soup.find(class_=lambda c: c and 'synopsis' in str(c).lower())
        if syn:
            info["synopsis"] = syn.get_text(' ', strip=True)
        cover = soup.find('img', id='coverOeuvre')
        if cover and cover.get('src'):
            info["cover"] = cover['src']
        else:
            og = soup.find('meta', property='og:image')
            if og and og.get('content'):
                info["cover"] = og['content']
        grid = soup.find('div', class_='info-grid')
        if grid:
            for lbl in grid.find_all('span', class_='info-lbl'):
                key = lbl.get_text(strip=True)
                if not key:
                    continue
                val_tag = lbl.find_next_sibling(['span', 'div'], class_='info-val')
                if not val_tag:
                    continue
                val = val_tag.get_text(' ', strip=True).replace('Voir plus', '').strip(' ,')
                if val and val != '?':
                    info["details"].append((key, val))
        info["seasons"] = get_seasons(response.text)
        return info

    def _show_anime_info(pane, url, title=""):
        page_url = _anime_page_url(url)
        if not page_url:
            pane.app.set_status("[#e06c75]Impossible de trouver la page de l'anime.[/]")
            return
        pane.app.set_status("Chargement des infos…")
        info = _fetch_anime_info(page_url)
        pane.app.reset_status()
        if not info:
            pane.app.set_status("[#e06c75]Impossible de charger les infos de l'anime.[/]")
            return
        pane.app.push_screen(AnimeInfoScreen(info, title))

    def _focused_anime_url(pane):
        focused = pane.app.focused
        if not isinstance(focused, ListView) or not isinstance(focused.parent, Column):
            return None, ""
        col = focused.parent
        idx = focused.index
        if col.kind in ("results", "animes", "versions"):
            if idx is None or idx < 0 or idx >= len(col.entries):
                return None, ""
            payload = col.entries[idx][1]
            if col.kind == "versions":
                return payload, col.meta.get("anime_name", "")
            return payload[1], payload[0]
        if col.kind in ("seasons", "episodes"):
            url = col.meta.get("season_url")
            if url:
                return url, col.meta.get("anime_name", "")
        return None, ""


    class Column(Static):
        def __init__(self, title, kind, entries, meta=None, classes=None):
            super().__init__(classes=classes)
            self.col_title = title
            self.kind = kind
            self.entries = entries
            self.meta = meta or {}

        def compose(self) -> ComposeResult:
            self.list_view = ListView(*[ListItem(Label(f" {label}")) for label, _ in self.entries])
            yield self.list_view

        def on_mount(self):
            self.border_title = self.col_title
            if self.entries:
                self.list_view.index = 0
            self.list_view.focus()


    def _mount_column(zone, anchor_col, column):
        children = list(zone.children)
        if anchor_col is not None and anchor_col in children:
            for later in children[children.index(anchor_col) + 1:]:
                later.remove()
        zone.mount(column)

    def _open_anime(pane, zone, anchor_col, anime_name, anime_url, vf=False):
        seasons = _fetch_seasons(anime_url)
        if not seasons:
            pane.app.set_status("[#e06c75]Aucune saison trouvée.[/]")
            return
        if vf:
            vf_seasons = [dict(s, url=s['url'].replace('vostfr', 'vf')) for s in seasons]
            _open_seasons(pane, zone, anchor_col, f"{anime_name} (VF)", anime_url, vf_seasons, anime_name)
            return
        versions = {}
        for season in seasons:
            low = season['url'].lower()
            if 'vostfr' in low:
                versions.setdefault('VOSTFR', []).append(season)
            elif 'vf' in low:
                versions.setdefault('VF', []).append(season)
            else:
                versions.setdefault('AUTRE', []).append(season)
        main_versions = [v for v in versions if v in ("VOSTFR", "VF")]
        if len(main_versions) > 1:
            entries = []
            for label in main_versions:
                version_url = anime_url.rstrip('/') + '/' + versions[label][0]['url'].split('/')[0] + '/' + label.lower()
                entries.append((label, version_url))
            _mount_column(zone, anchor_col, Column(
                anime_name, "versions", entries,
                meta={"anime_name": anime_name}
            ))
        else:
            label = list(versions.keys())[0] if len(versions) == 1 else ""
            title = f"{anime_name} ({label})" if label else anime_name
            _open_seasons(pane, zone, anchor_col, title, anime_url, seasons, anime_name)

    def _open_seasons_for_version(pane, zone, anchor_col, label, version_url):
        seasons = _fetch_seasons(version_url)
        anime_name = anchor_col.meta.get("anime_name", label)
        _open_seasons(pane, zone, anchor_col, label, version_url, seasons, anime_name)

    def _open_seasons(pane, zone, anchor_col, title, base_url, seasons, anime_name):
        if not seasons:
            pane.app.set_status("[#e06c75]Aucune saison trouvée.[/]")
            return
        entries = [
            (s['name'], base_url.rstrip('/') + '/' + s['url'].lstrip('/'))
            for s in seasons
        ]
        _mount_column(zone, anchor_col, Column(
            title, "seasons", entries,
            meta={"anime_name": anime_name}
        ))

    def _open_episodes(pane, zone, anchor_col, anime_name, season_name, season_url):
        filever = get_episode_list(season_url)
        episodes = AnimeDownloader().get_anime_episode(season_url, filever) if filever else {}
        if not episodes:
            pane.app.set_status("[#e06c75]Aucun épisode trouvé.[/]")
            return
        entries = [(f"Épisode {ep}", (ep, vids)) for ep, vids in episodes.items()]
        _mount_column(zone, anchor_col, Column(
            season_name or anime_name, "episodes", entries,
            meta={"anime_name": anime_name, "season_url": season_url}
        ))

    def _play_episode(pane, anime_name, ep, saison, url, video_ids):
        app = pane.app
        if not shutil.which("mpv"):
            app.set_status("[#e06c75]mpv n'est pas installé. Installe-le d'abord : sudo apt install mpv (Debian/Ubuntu), yay -S mpv (Arch), ou via le site mpv.io sur Windows.[/]")
            return False
        app.set_status(f"Récupération de l'épisode {ep}…")
        video_url = AnimeDownloader().resolve_video_url(video_ids)
        if not video_url:
            app.set_status("[#e06c75]Impossible de récupérer l'URL de la vidéo.[/]")
            return False
        if video_url.startswith('//'):
            video_url = 'https:' + video_url
        app.set_status(f"Lecture de l'épisode {ep} avec mpv…")
        mpv_cmd = _mpv_command(video_url, anime_name, ep, saison, status_cb=app.set_status)
        try:
            with app.suspend():
                print(f"Lecture de l'épisode {ep} avec mpv… (chargement possible, touche q pour quitter mpv)")
                subprocess.run(mpv_cmd, check=True)
        except FileNotFoundError:
            app.set_status("[#e06c75]Erreur : mpv n'est pas installé.[/]")
            return False
        except Exception as e:
            app.set_status(f"[#e06c75]Erreur lors de la lecture : {e}[/]")
            return False
        saison_str = saison
        version_str = _version_for_url(url)
        if version_str and version_str.lower() not in saison_str.lower():
            saison_str = f"{saison_str} - {version_str}"
        add_to_history(
            anime_name=anime_name,
            episode=f"Episode {ep}",
            saison=saison_str,
            url=url,
            debug=False
        )
        app.set_status(f"[#86d6a2]Épisode {ep} terminé.[/]")
        return True

    def _handle_column_select(pane, zone, event):
        list_view = event.control
        col = list_view.parent
        if not isinstance(col, Column):
            return
        idx = list_view.index
        if idx is None or idx < 0 or idx >= len(col.entries):
            return
        label, payload = col.entries[idx]
        if col.kind == "results":
            anime_name, anime_url = payload
            vf = getattr(pane.app, "vf_mode", False)
            _open_anime(pane, zone, col, anime_name, anime_url, vf=vf)
        elif col.kind == "versions":
            _open_seasons_for_version(pane, zone, col, label, payload)
        elif col.kind == "seasons":
            _open_episodes(pane, zone, col, col.meta["anime_name"], label, payload)
        elif col.kind == "episodes":
            ep, video_ids = payload
            ok = _play_episode(pane, col.meta["anime_name"], ep, col.col_title, col.meta["season_url"], video_ids)
            if ok and idx + 1 < len(col.entries):
                list_view.index = idx + 1

    def _pop_column(zone, focus_input=None):
        cols = list(zone.children)
        if len(cols) > 1:
            cols[-1].remove()
            cols[-2].list_view.focus()
            return True
        return False


    class SearchPane(Static):
        def __init__(self, search_term=None):
            super().__init__()
            self.search_term = search_term

        def compose(self) -> ComposeResult:
            self.input = Input(placeholder="Nom de l'anime…", id="search-input")
            yield self.input
            self.result_label = Label("", id="search-result")
            yield self.result_label
            self.zone = Horizontal(id="results-zone")
            yield self.zone

        def on_mount(self):
            self.border_title = "Recherche"
            if self.search_term:
                self.input.value = self.search_term
                self.on_input_submitted(Input.Submitted(self.input, self.search_term))
            else:
                self.input.focus()

        def focus_default(self):
            self.input.focus()

        def on_input_submitted(self, event: Input.Submitted):
            query = event.value.strip()
            for child in list(self.zone.children):
                child.remove()
            if not query:
                self.result_label.update("")
                return
            vf = getattr(self.app, "vf_mode", False)
            lang = "VF" if vf else "VOSTFR"
            self.result_label.update(f"Recherche de \"{query}\" ({lang})…")
            animes, urls = AnimeDownloader().get_catalogue(query, vf=vf)
            if not animes:
                self.result_label.update(f"[#e06c75]Aucun anime trouvé ({lang}).[/]")
                return
            entries = [(name, (name, url)) for name, url in zip(animes, urls)]
            _mount_column(self.zone, None, Column(query, "results", entries))
            self.result_label.update(f"[#86d6a2]{len(animes)} résultat(s) ({lang})[/]")

        def on_list_view_selected(self, event):
            _handle_column_select(self, self.zone, event)

        def key_i(self):
            if isinstance(self.app.focused, Input):
                return
            url, title = _focused_anime_url(self)
            if url:
                _show_anime_info(self, url, title)

        def key_escape(self):
            if _pop_column(self.zone):
                return
            if self.input.has_focus:
                self.app.focus_nav()
            elif len(self.zone.children):
                self.input.focus()
            else:
                self.app.focus_nav()


    class HistoryPane(Static):
        def compose(self) -> ComposeResult:
            self.entries = get_history_entries()
            if not self.entries:
                yield Label("Aucun anime dans l'historique.\nLance un épisode pour commencer.", id="empty")
                return
            items = []
            for entry in self.entries:
                anime_name, episode, saison = entry[1:4]
                label = f" {anime_name}  [#6b6577]{episode}[/]  [italic #6ea8fe]{saison}[/]"
                items.append(ListItem(Label(label, markup=True)))
            self.list_view = ListView(*items, id="history-list")
            yield self.list_view

        def on_mount(self):
            self.border_title = "Historique"
            if hasattr(self, "list_view"):
                self.list_view.index = 0
                self.list_view.focus()

        def focus_default(self):
            if hasattr(self, "list_view"):
                self.list_view.focus()

        def on_list_view_selected(self, event):
            if not hasattr(self, "list_view") or event.control is not self.list_view:
                return
            idx = self.list_view.index
            if idx < 0 or idx >= len(self.entries):
                return
            entry = self.entries[idx]
            anime_name, episode, saison, url = entry[1:5]
            match = re.search(r'(\d+)$', episode)
            if not match:
                self.app.set_status("[#e06c75]Impossible de déterminer l'épisode courant.[/]")
                return
            current_ep = int(match.group(1))
            filever = get_episode_list(url)
            if not filever:
                self.app.set_status("[#e06c75]Impossible de récupérer la liste des épisodes.[/]")
                return
            episodes = AnimeDownloader().get_anime_episode(url, filever)
            if not episodes:
                self.app.set_status("[#e06c75]Aucun épisode trouvé.[/]")
                return
            ep_keys_int = sorted(int(e) for e in episodes.keys() if e.isdigit())
            next_ep = None
            for ep in ep_keys_int:
                if ep > current_ep:
                    next_ep = ep
                    break
            if next_ep is None:
                self.app.set_status("[#86d6a2]Déjà au dernier épisode.[/]")
                return
            video_ids = episodes[str(next_ep)]
            ok = _play_episode(self, anime_name, next_ep, saison, url, video_ids)
            if ok:
                self._refresh_entry(idx, next_ep)

        def _refresh_entry(self, idx, ep):
            anime_name, episode, saison, url = self.entries[idx][1:5]
            label = f" {anime_name}  [#6b6577]Episode {ep}[/]  [italic #6ea8fe]{saison}[/]"
            item = self.list_view.children[idx]
            item.query_one(Label).update(label)

        def key_i(self):
            if not hasattr(self, "list_view") or not hasattr(self, "entries"):
                return
            idx = self.list_view.index
            if idx is None or idx < 0 or idx >= len(self.entries):
                return
            entry = self.entries[idx]
            _show_anime_info(self, entry[4], entry[1])

        def key_d(self):
            self._delete_selected_entry()

        def key_delete(self):
            self._delete_selected_entry()

        def _delete_selected_entry(self):
            if not hasattr(self, "list_view") or not hasattr(self, "entries"):
                return
            idx = self.list_view.index
            if idx < 0 or idx >= len(self.entries):
                return
            entry_id = self.entries[idx][0]
            delete_history_entry(entry_id)
            del self.entries[idx]
            self.list_view.children[idx].remove()
            if not self.entries:
                self.list_view.visible = False
                self.mount(Label("Aucun anime dans l'historique.", id="empty"))
            self.app.set_status(HINTS["history"])

        def key_escape(self):
            self.app.focus_nav()


    class PlanningPane(Static):
        def compose(self) -> ComposeResult:
            self.days, self.planning = self.get_planning()
            self.zone = Horizontal(id="planning-zone")
            if not self.days:
                yield Label("Aucun planning trouvé.", id="empty")
                return
            yield self.zone

        def on_mount(self):
            self.border_title = "Planning"
            if self.days:
                entries = [(day.strip(), day.strip()) for day in self.days]
                _mount_column(self.zone, None, Column("Jours", "days", entries, classes="narrow"))

        def get_planning(self):
            url = f"https://{DOMAIN}/planning/"
            try:
                response = requests.get(url, headers=ANIME_HEADERS)
                html_content = response.text
                day_pattern = r'<h2 class="titreJours[^>]*>([^<]+)</h2>'
                days = re.findall(day_pattern, html_content)
                planning = {day.strip(): [] for day in days}
                day_sections = re.split(day_pattern, html_content)
                for i in range(1, len(day_sections), 2):
                    current_day = day_sections[i].strip()
                    day_content = day_sections[i + 1]
                    if current_day in planning:
                        cards = re.findall(
                            r'<a href="(/catalogue/[^"]+)"[^>]*>.*?<h3[^>]*>([^<]+)</h3>',
                            day_content, re.DOTALL
                        )
                        if not cards:
                            cards = re.findall(
                                r'<a href="(/catalogue/[^"]+)"[^>]*>.*?<img[^>]*alt="([^"]*)"',
                                day_content, re.DOTALL
                            )
                        for card_url, card_title in cards:
                            if _is_scan_url(card_url):
                                continue
                            planning[current_day].append((card_title.strip(), card_url.strip(), "", ""))
                return list(planning.keys()), planning
            except Exception:
                return [], {}

        def focus_default(self):
            if hasattr(self, "zone") and len(self.zone.children):
                self.zone.children[0].list_view.focus()

        def on_list_view_selected(self, event):
            list_view = event.control
            col = list_view.parent
            if not isinstance(col, Column):
                return
            if col.kind == "days":
                idx = list_view.index
                if idx is None or idx < 0 or idx >= len(self.days):
                    return
                selected_day = self.days[idx]
                animes = self.planning[selected_day]
                entries = [
                    (f"{title}{_version_tag(url)}{_season_tag(url)}", (title, url, time, version))
                    for (title, url, time, version) in animes
                ]
                if not entries:
                    self.app.set_status("[#6b6577]Aucun anime ce jour.[/]")
                    children = list(self.zone.children)
                    if col in children:
                        for later in children[children.index(col) + 1:]:
                            later.remove()
                    return
                _mount_column(self.zone, col, Column(selected_day, "animes", entries))
            elif col.kind == "animes":
                idx = list_view.index
                if idx is None or idx < 0 or idx >= len(col.entries):
                    return
                title, url, time, version = col.entries[idx][1]
                season_url = f"https://{DOMAIN}{url}" if url.startswith('/') else f"https://{DOMAIN}/catalogue/{url}"
                saison_name = f"{time} - {version}" if time or version else version
                _open_episodes(self, self.zone, col, title, saison_name, season_url)
            else:
                _handle_column_select(self, self.zone, event)

        def key_right(self):
            focused = self.app.focused
            if not isinstance(focused, ListView) or not isinstance(focused.parent, Column):
                return
            idx = focused.index
            if idx is None or idx < 0 or idx >= len(focused.children):
                return
            self.on_list_view_selected(ListView.Selected(focused, focused.children[idx], idx))

        def key_i(self):
            url, title = _focused_anime_url(self)
            if url:
                _show_anime_info(self, url, title)

        def key_left(self):
            _pop_column(self.zone)

        def key_escape(self):
            if _pop_column(self.zone):
                return
            self.app.focus_nav()


    class UpcomingPane(Static):
        def compose(self) -> ComposeResult:
            items = self.get_upcoming()
            if not items:
                yield Label("Aucun résultat trouvé.", id="empty")
            else:
                self.upcoming_list = ListView(*items, id="upcoming-list")
                yield self.upcoming_list

        def get_upcoming(self):
            try:
                url = "https://animecountdown.com/upcoming"
                headers = HEADERS_BASE.copy()
                response = requests.get(url, headers=headers)
                soup = BeautifulSoup(response.text, 'html.parser')
                anime_list = soup.find_all('a', class_='countdown-content-trending-item')
                display_items = []
                for anime in anime_list:
                    anime_title = anime.find('countdown-content-trending-item-title').text.strip()
                    anime_episode = anime.find('countdown-content-trending-item-desc').text.strip()
                    display_items.append(ListItem(Label(f" {anime_title}  [#6b6577]{anime_episode}[/]", markup=True)))
                return display_items
            except Exception:
                return []

        def on_mount(self):
            self.border_title = "À venir"
            if hasattr(self, "upcoming_list"):
                self.upcoming_list.index = 0
                self.upcoming_list.focus()

        def focus_default(self):
            if hasattr(self, "upcoming_list"):
                self.upcoming_list.focus()

        def key_escape(self):
            self.app.focus_nav()


    class AnimeInfoScreen(Screen):
        def __init__(self, info, anime_name=""):
            super().__init__()
            self.info = info
            self.anime_name = anime_name

        def compose(self) -> ComposeResult:
            title = self.info["title"] or self.anime_name
            with Horizontal(id="info-slide"):
                with VerticalScroll(id="info-body"):
                    yield Label(title, id="screen-title")
                    if self.info["alt_titles"]:
                        yield Label(self.info["alt_titles"], id="screen-subtitle", classes="info-alt")
                    if self.info["genres"]:
                        yield Label("Genres", classes="info-section")
                        yield Label("  ".join(f"[#6ea8fe]{g}[/]" for g in self.info["genres"]))
                    if self.info["seasons"]:
                        yield Label("Saisons", classes="info-section")
                        for season in self.info["seasons"]:
                            yield Label(f" {season['name']}{_version_tag(season['url'])}")
                    if self.info["synopsis"]:
                        yield Label("Synopsis", classes="info-section")
                        yield Label(self.info["synopsis"], id="info-synopsis")
                with VerticalScroll(classes="info-side"):
                    yield Label("Chargement de la cover…", id="empty")
                    if self.info["details"]:
                        yield Label("Infos", classes="info-section")
                        with Container(id="info-grid"):
                            for key, val in self.info["details"]:
                                yield Label(f"[#6b6577]{key}[/]\n[bold]{val}[/]", classes="info-cell")
            yield Label("[bold #8db8ff]← →[/] slider   [bold #8db8ff]échap[/] / [bold #8db8ff]i[/] fermer", id="screen-help")

        def on_mount(self):
            self.call_after_refresh(self._load_cover)

        def _load_cover(self):
            side = self.query_one(".info-side")
            cover = self.info.get("cover")
            if not cover:
                self._cover_fallback()
                return
            try:
                import io
                from PIL import Image
            except ImportError:
                self._cover_fallback()
                return
            try:
                resp = requests.get(cover, headers=ANIME_HEADERS, timeout=15)
                resp.raise_for_status()
                img = Image.open(io.BytesIO(resp.content)).convert("RGB")
            except Exception:
                self._cover_fallback()
                return
            side = self.query_one(".info-side")
            max_w = max(side.content_size.width - 4, 10)
            max_h = max(int(self.size.height * 0.5) * 2, 12)
            img.thumbnail((max_w, max_h))
            w, h = img.size
            side.query_one("#empty").remove()
            cover_widget = Static(HalfBlockImage(img), id="info-cover")
            cover_widget.styles.width = w
            cover_widget.styles.height = h // 2
            infos = side.query(".info-section")
            if infos:
                side.mount(cover_widget, before=infos.first())
            else:
                side.mount(cover_widget)
            if _supports_kitty_graphics():
                self._kitty_overlay(resp.content, w, h // 2, cover_widget)
            else:
                _kitty_dbg("kitty non détecté: TERM=%r KITTY_WINDOW_ID=%r TERM_PROGRAM=%r" % (
                    os.environ.get("TERM"), os.environ.get("KITTY_WINDOW_ID"), os.environ.get("TERM_PROGRAM")))

        def _kitty_overlay(self, data, cols, rows, widget):
            try:
                import base64
                import io
                import tempfile
                from PIL import Image
                img = Image.open(io.BytesIO(data)).convert("RGB")
                fd, path = tempfile.mkstemp(suffix=".png", prefix="animesama-cover-")
                os.close(fd)
                img.save(path, "PNG")
                self._kitty_file = path

                attempts = {"n": 0}

                def place():
                    region = widget.region
                    if region.width == 0:
                        if attempts["n"] < 20:
                            attempts["n"] += 1
                            self.set_timer(0.1, place)
                        return
                    _kitty_dbg(f"place: region={region} cols={cols} rows={rows} path={path}")
                    quiet = "" if os.environ.get("ANIMESAMA_KITTY_DEBUG") else "q=2,"
                    b64 = base64.b64encode(path.encode()).decode()
                    seq = (f"\x1b[{region.y + 1};{region.x + 1}H"
                           f"\x1b_Ga=d,d=i,i={KITTY_COVER_ID},{quiet};\x1b\\"
                           f"\x1b_Ga=T,f=100,t=f,i={KITTY_COVER_ID},{quiet}C=1,z=1,c={cols},r={rows};{b64}\x1b\\")
                    sys.__stdout__.write(seq)
                    sys.__stdout__.flush()
                    _kitty_dbg(f"séquence écrite ({len(seq)} octets)")
                self.set_timer(0.1, place)
            except Exception as e:
                _kitty_dbg(f"exception overlay: {e!r}")

        def on_unmount(self):
            path = getattr(self, "_kitty_file", None)
            if not path:
                return
            try:
                sys.__stdout__.write(f"\x1b_Ga=d,d=i,i={KITTY_COVER_ID},q=2;\x1b\\")
                sys.__stdout__.flush()
            except Exception:
                pass
            try:
                os.unlink(path)
            except OSError:
                pass

        def _cover_fallback(self):
            self.query_one(".info-side #empty").remove()

        def key_right(self):
            slide = self.query_one("#info-slide")
            panels = slide.query(".info-side")
            if panels:
                slide.scroll_to_widget(panels.last(), animate=True, duration=0.3)

        def key_left(self):
            slide = self.query_one("#info-slide")
            slide.scroll_to_widget(self.query_one("#info-body"), animate=True, duration=0.3)

        def key_escape(self):
            self.app.pop_screen()

        def key_i(self):
            self.app.pop_screen()


    class HistoryCheckFinalScreen(Screen):
        def compose(self) -> ComposeResult:
            yield Label("Historique", id="screen-title")
            yield Label("Le dernier épisode disponible est en rouge", id="screen-subtitle")
            self.entries = get_history_entries()
            if not self.entries:
                yield Label("Aucun historique trouvé.", id="empty")
                yield Label("[bold #8db8ff]q[/] retour", id="screen-help")
                return
            items = []
            self.last_ep_indices = set()
            for entry in self.entries:
                anime_name, episode, saison, url = entry[1:5]
                match = re.search(r'(\d+)$', episode)
                if match:
                    current_ep = int(match.group(1))
                else:
                    current_ep = None
                filever = get_episode_list(url)
                if not filever:
                    is_last = False
                else:
                    episodes = AnimeDownloader().get_anime_episode(url, filever)
                    if not episodes:
                        is_last = False
                    else:
                        ep_keys = [int(e) for e in episodes.keys() if e.isdigit()]
                        if not ep_keys or current_ep is None:
                            is_last = False
                        else:
                            is_last = (current_ep == max(ep_keys))
                label = f" {anime_name} - {episode} - {saison}"
                if is_last:
                    items.append(ListItem(Label(f"[#e06c75]{label}[/]", markup=True)))
                else:
                    items.append(ListItem(Label(label)))
            self.list_view = ListView(*items, id="history-list")
            yield self.list_view
            yield Label("[bold #8db8ff]q[/] retour", id="screen-help")

        def on_mount(self):
            if hasattr(self, "list_view"):
                self.list_view.index = 0
                self.set_focus(self.list_view)

        def key_q(self):
            self.app.pop_screen()
        def key_escape(self):
            self.key_q()


    class AnimeSamaTUI(App):
        CSS = EMBEDDED_CSS
        BINDINGS = [
            ("ctrl+q", "quit", "Quitter"),
        ]

        def __init__(self, start_screen=None, search_term=None, pre_screen=None, vf_mode=False):
            super().__init__()
            self.start_screen = start_screen
            self.search_term = search_term
            self.pre_screen = pre_screen
            self.current_pane = None
            self.current_pane_name = None
            self.vf_mode = vf_mode

        def compose(self) -> ComposeResult:
            with Container(id="app-grid"):
                with Container(id="sidebar"):
                    yield Label("╭────────────╮\n│ anime-sama │\n╰────────────╯", id="logo")
                    yield Label("", id="domain-status")
                    lang_items = [ListItem(Label(f" {text}")) for text in LANG_ITEMS]
                    self.lang_nav = ListView(*lang_items, id="lang-nav")
                    yield self.lang_nav
                    yield Label("─" * 14, id="sep")
                    items = [ListItem(Label(f" {text}")) for text, _ in NAV_ITEMS]
                    self.nav = ListView(*items, id="nav")
                    yield self.nav
                yield Container(id="content")
            yield Static("", id="status-bar", markup=True)

        def _update_lang_display(self):
            for i, item in enumerate(self.lang_nav.children):
                label = item.query_one(Label)
                name = LANG_ITEMS[i]
                active = (i == 1) == self.vf_mode
                if active:
                    label.update(f"[bold #6ea8fe] {name}[/]")
                else:
                    label.update(f"[#6b6577] {name}[/]")

        async def on_mount(self):
            self.query_one("#domain-status", Label).update(f"[#6b6577]●[/] {DOMAIN}")
            self.lang_nav.index = 1 if self.vf_mode else 0
            self._update_lang_display()
            threading.Thread(target=self._resolve_domain_bg, daemon=True).start()
            pane = "search"
            if self.start_screen in NAV_INDEX and self.start_screen != "search":
                pane = self.start_screen
            self.nav.index = NAV_INDEX[pane]
            if self.search_term or pane in ("planning", "upcoming"):
                ensure_domain()
            if self.search_term:
                pane = "search"
                self.nav.index = NAV_INDEX[pane]
                await self.show_pane(pane, search_term=self.search_term)
            else:
                await self.show_pane(pane)
            if self.pre_screen:
                await self.push_screen(self.pre_screen)

        def _resolve_domain_bg(self):
            ensure_domain(check_availability=True)
            dot = "#86d6a2" if IS_DOMAIN_AVAILABLE else "#e06c75"
            try:
                self.call_from_thread(
                    self.query_one("#domain-status", Label).update,
                    f"[{dot}]●[/] {DOMAIN}"
                )
            except Exception:
                pass

        async def show_pane(self, name, search_term=None):
            pane_classes = {
                "search": SearchPane,
                "history": HistoryPane,
                "planning": PlanningPane,
                "upcoming": UpcomingPane,
            }
            if name not in pane_classes:
                return
            if self.current_pane_name == name and search_term is None and self.current_pane is not None:
                self.current_pane.focus_default()
                return
            if self.current_pane is not None:
                await self.current_pane.remove()
            cls = pane_classes[name]
            pane = cls(search_term=search_term) if name == "search" else cls()
            self.current_pane = pane
            self.current_pane_name = name
            await self.query_one("#content").mount(pane)
            self.set_status(HINTS[name])

        def set_status(self, text):
            self.query_one("#status-bar", Static).update(text)

        def reset_status(self):
            if self.current_pane_name:
                self.set_status(HINTS[self.current_pane_name])

        def focus_nav(self):
            self.nav.focus()
            self.reset_status()

        def on_list_view_selected(self, event):
            if event.control is self.nav:
                action = NAV_ITEMS[self.nav.index][1]
                asyncio.create_task(self.show_pane(action))
            elif event.control is self.lang_nav:
                self.vf_mode = self.lang_nav.index == 1
                self._update_lang_display()
                lang = "VF" if self.vf_mode else "VOSTFR"
                self.set_status(f"[#86d6a2]Langue de recherche : {lang}[/]")
                if self.current_pane_name == "search" and self.current_pane is not None:
                    query = self.current_pane.input.value.strip()
                    if query:
                        self.current_pane.on_input_submitted(
                            Input.Submitted(self.current_pane.input, query)
                        )


    def tui_main(args):
        start_screen = None
        if args.planing:
            start_screen = "planning"
        elif args.continuer:
            start_screen = "history"
        elif args.upcoming:
            start_screen = "upcoming"

        if args.check_final:
            app = AnimeSamaTUI(pre_screen=HistoryCheckFinalScreen(), vf_mode=args.vf)
            app.run()
        else:
            search_term = " ".join(args.query) if args.query else None
            app = AnimeSamaTUI(start_screen=start_screen, search_term=search_term, vf_mode=args.vf)
            app.run()

def main():
    parser = argparse.ArgumentParser(
        description=f"Anime-sama CLI - Interface CLI et TUI pour {DOMAIN}",
        add_help=False
    )
    parser.add_argument("query", nargs="*", help="Recherche d'anime")
    parser.add_argument("-c", "--continuer", action="store_true", help="Afficher l'historique")
    parser.add_argument("-f", "--full", action="store_true", help="Vérification des derniers épisodes dans l'historique")
    parser.add_argument("--vf", action="store_true", help="Recherche uniquement en VF")
    parser.add_argument("--debug", action="store_true", help="Mode debug")
    parser.add_argument("-h", "--help", action="store_true", help="Afficher l'aide")
    parser.add_argument("-p", "--planing", action="store_true", help="Afficher le planning")
    parser.add_argument("-up", "--upcoming", action="store_true", help="Afficher les prochains épisodes à sortir")
    parser.add_argument("-t", "--textual", action="store_true", help="Utiliser l'interface TUI (Textual)")
    parser.add_argument("--cli", action="store_true", help="Utiliser l'interface en ligne de commande traditionnelle")
    parser.add_argument("-cf", "--check-final", action="store_true", help="Historique avec vérification du dernier épisode")
    
    args = parser.parse_args()
    
    if args.help:
        display_help()
        return
    
    use_tui = not args.cli and TEXTUAL_AVAILABLE
    
    if args.textual and not TEXTUAL_AVAILABLE:
        print("Erreur: La librairie Textual n'est pas installée. Impossible d'utiliser le mode TUI.")
        print("Installez-la avec: pip install textual")
        print("Passage en mode CLI...")
        use_tui = False
    
    if use_tui:
        tui_main(args)
    else:
        try:
            cli_main(args)
        except KeyboardInterrupt:
            print("\nProgramme interrompu par l'utilisateur")
        except Exception as e:
            print(f"\nUne erreur s'est produite : {str(e)}")

if __name__ == "__main__":
    main()
