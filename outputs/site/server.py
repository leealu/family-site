#!/usr/bin/env python3
"""Small, dependency-free family diary web app."""
from datetime import date, datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import sqlite3
import tarfile
import tempfile
import time
from urllib.parse import parse_qs, unquote, urlencode, urlparse
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("DIARY_DATA_DIR", ROOT / "data"))
DB_PATH = DATA_DIR / "family.sqlite3"
MEDIA_DIR = DATA_DIR / "media"
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "0") == "1"
PORT = int(os.environ.get("PORT", "8000"))
SESSION_HOURS = 4
SESSION_POLICY = "4-hour-v1"
MAX_UPLOAD_BYTES = 200 * 1024 * 1024
MAX_UPLOAD_CHUNK_BYTES = 8 * 1024 * 1024
MAX_BACKUP_BYTES = 4 * 1024 * 1024 * 1024
MEDIA_SUFFIXES = {
    ".jpg": "image", ".jpeg": "image", ".png": "image", ".webp": "image", ".gif": "image",
    ".mp4": "video", ".webm": "video", ".mov": "video",
    ".mp3": "audio", ".m4a": "audio", ".aac": "audio", ".ogg": "audio", ".wav": "audio",
}
PBKDF2_ROUNDS = 310_000
COOKIE = "family_session"
LOGIN_ATTEMPTS = {}

DEFAULT_CONTENT = {
    "siteName": "kani的奇妙小世界",
    "logoEmoji": "🌼",
    "navDiary": "成长日记",
    "navLikes": "兴趣角",
    "heroBadge": "🎈 3 岁半的小小探险家",
    "heroLine1": "你好呀！",
    "heroLine2": "欢迎来到",
    "heroLine3": "我的小世界",
    "heroEmoji": "☀️",
    "heroMascot": "🐻",
    "heroDescription": "这里有我喜欢的东西、每天的新发现，还有一点点长大的故事。牵好大人的手，一起来逛逛吧！",
    "heroButton": "翻开成长日记",
    "float1": "🌷 你好朋友！",
    "float2": "✨ 今天也有新发现",
    "float3": "🧸 抱抱时间",
    "profile": [
        {"icon":"🧸","title":"我的年龄","text":"3 岁半啦，正在长大"},
        {"icon":"💛","title":"我喜欢","text":"画画 · 故事 · 唱唱跳跳"},
        {"icon":"🌱","title":"每天一点点","text":"发现新东西，学会新本领"}
    ],
    "likesEyebrow": "MY FAVORITE THINGS",
    "likesTitle": "我的兴趣角 🎨",
    "likesDescription": "喜欢的事情，就像口袋里的小星星。",
    "interests": [
        {"icon":"🖍️","title":"画画涂颜色","description":"拿起蜡笔，把脑袋里的奇妙想法画出来。","tag":"我的小画家时光"},
        {"icon":"📚","title":"听故事时间","description":"翻开绘本，和小动物一起去冒险。","tag":"再讲一个嘛！"},
        {"icon":"🎵","title":"唱歌蹦蹦跳","description":"听到喜欢的音乐，身体就忍不住动起来。","tag":"啦啦啦～"}
    ],
    "diaryEyebrow": "LITTLE GROWING MOMENTS",
    "diaryTitle": "成长日记 📔",
    "diaryDescription": "把平凡日子里的小小进步，收藏起来。",
    "diaryCardEyebrow": "我的小小记录本",
    "diaryIcon": "📒",
    "diaryCardTitle": "今天，我又长大一点点啦！",
    "diaryCardDescription": "这里记录第一次尝试的新事情、最近学会的小本领，或一句可爱的童言童语。家长登录后，就可以添加和管理成长记录。",
    "loginCta": "家长登录后添加",
    "recordFormTitle": "记下一个小瞬间 ✨",
    "recordDateLabel": "日期",
    "recordTitleLabel": "小标题",
    "recordStoryLabel": "成长故事",
    "recordTitlePlaceholder": "比如：第一次自己穿上鞋子",
    "recordStoryPlaceholder": "写下今天的小发现、童言童语或学会的新本领……",
    "recordSaveButton": "保存记录",
    "recordCancelButton": "取消修改",
    "emptyRecords": "还没有成长记录，添加第一条小故事吧 🌷",
    "footerLeft": "每天都有新发现，慢慢长大真奇妙！ 🌈",
    "footerRight": "家庭小天地 · 请和大人一起浏览"
}

TEXT_LIMITS = {
    "siteName":100,"logoEmoji":16,"navDiary":40,"navLikes":40,"heroBadge":120,
    "heroLine1":80,"heroLine2":80,"heroLine3":80,"heroEmoji":16,"heroMascot":256,
    "heroDescription":500,"heroButton":60,"float1":60,"float2":60,"float3":60,
    "likesEyebrow":80,"likesTitle":100,"likesDescription":300,
    "diaryEyebrow":80,"diaryTitle":100,"diaryDescription":300,
    "diaryCardEyebrow":80,"diaryIcon":16,"diaryCardTitle":100,"diaryCardDescription":800,
    "loginCta":60,"recordFormTitle":100,"recordDateLabel":30,"recordTitleLabel":30,"recordStoryLabel":30,
    "recordTitlePlaceholder":100,"recordStoryPlaceholder":200,"recordSaveButton":40,"recordCancelButton":40,"emptyRecords":160,
    "footerLeft":200,"footerRight":200
}

def read_content(db):
    row = db.execute("SELECT value FROM settings WHERE key='page_content'").fetchone()
    if not row:
        return DEFAULT_CONTENT
    try:
        saved = json.loads(row["value"])
        if not isinstance(saved, dict):
            return DEFAULT_CONTENT
        if saved.get("siteName") == "芽芽的奇妙小世界":
            saved["siteName"] = DEFAULT_CONTENT["siteName"]
            db.execute("UPDATE settings SET value=? WHERE key='page_content'", (json.dumps(saved, ensure_ascii=False),))
            db.commit()
        return saved
    except (TypeError, json.JSONDecodeError):
        return DEFAULT_CONTENT

def validate_content(data):
    if not isinstance(data, dict):
        raise ValueError("页面内容格式无效。")
    result = {}
    for key, limit in TEXT_LIMITS.items():
        value = data.get(key)
        if not isinstance(value, str):
            raise ValueError(f"“{key}”内容无效或超过 {limit} 个字符。")
        value = value.strip()
        if key == "heroMascot" and value.startswith("/media/"):
            if not re.fullmatch(r"/media/[a-f0-9]{32}\.(?:jpg|jpeg|png|webp|gif)", value):
                raise ValueError("主视觉角色图片地址无效。")
        elif len(value) > (16 if key == "heroMascot" else limit):
            raise ValueError(f"“{key}”内容无效或超过 {limit} 个字符。")
        result[key] = value
    for key, count, fields in (
        ("profile", 3, {"icon":16,"title":50,"text":100}),
    ):
        rows = data.get(key)
        if not isinstance(rows, list) or len(rows) != count:
            raise ValueError("基本介绍需要保留 3 张卡片。")
        result[key] = []
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("基本介绍卡片格式无效。")
            result[key].append({})
            for field, limit in fields.items():
                value = row.get(field)
                if not isinstance(value, str) or len(value.strip()) > limit:
                    raise ValueError(f"基本介绍卡片的“{field}”内容无效。")
                result[key][-1][field] = value.strip()
    interests = data.get("interests")
    if not isinstance(interests, list) or not 1 <= len(interests) <= 8:
        raise ValueError("兴趣卡片数量需要在 1 到 8 张之间。")
    result["interests"] = []
    for item in interests:
        if not isinstance(item, dict):
            raise ValueError("兴趣卡片格式无效。")
        entry = {}
        for field, limit in {"icon":16,"title":80,"description":240,"tag":60}.items():
            value = item.get(field)
            if not isinstance(value, str) or len(value.strip()) > limit:
                raise ValueError(f"兴趣卡片的“{field}”内容无效或过长。")
            entry[field] = value.strip()
        media = item.get("media", [])
        if not isinstance(media, list) or len(media) > 50:
            raise ValueError("每张兴趣卡片最多添加 50 个作品或故事链接。")
        entry["media"] = []
        for asset in media:
            if not isinstance(asset, dict):
                raise ValueError("作品或故事链接格式无效。")
            kind = asset.get("type")
            title = asset.get("title", "").strip() if isinstance(asset.get("title", ""), str) else ""
            name = asset.get("name", "").strip() if isinstance(asset.get("name", ""), str) else ""
            url = asset.get("url", "")
            if len(title) > 120 or len(name) > 240:
                raise ValueError("作品名称过长。")
            if kind in ("image", "video", "audio"):
                match = re.fullmatch(r"/media/([a-f0-9]{32}\.(?:jpg|jpeg|png|webp|gif|mp4|webm|mov|mp3|m4a|aac|ogg|wav))", str(url))
                if not match or MEDIA_SUFFIXES[Path(match.group(1)).suffix] != kind:
                    raise ValueError("上传作品地址无效。")
                clean_asset = {"type":kind,"title":title,"name":name,"url":url}
                if kind == "audio" and asset.get("coverUrl"):
                    cover_url = str(asset["coverUrl"])
                    cover_match = re.fullmatch(r"/media/([a-f0-9]{32}\.(?:jpg|jpeg|png|webp|gif))", cover_url)
                    if not cover_match:
                        raise ValueError("歌曲封面地址无效。")
                    clean_asset["coverUrl"] = cover_url
                entry["media"].append(clean_asset)
            elif kind == "netease":
                parsed = urlparse(str(url))
                if parsed.scheme != "https" or parsed.hostname not in {"music.163.com", "www.music.163.com"}:
                    raise ValueError("网易云故事链接请使用 music.163.com 的 HTTPS 分享地址。")
                if not title or len(url) > 1000:
                    raise ValueError("请填写故事专辑名称和有效的网易云链接。")
                entry["media"].append({"type":"netease","title":title,"name":"网易云音乐","url":url})
            elif kind == "provider-track":
                track = asset.get("track")
                if not isinstance(track, dict):
                    raise ValueError("在线曲目信息无效。")
                provider_id = str(track.get("providerId", ""))
                item_id = str(track.get("itemId", ""))
                saved_key = str(asset.get("savedItemKey", ""))
                track_kind = str(track.get("kind", "song"))
                if not re.fullmatch(r"[a-f0-9]{32}", saved_key) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", provider_id) or not re.fullmatch(r"[A-Za-z0-9_-]{1,160}", item_id) or track_kind not in ("song", "album"):
                    raise ValueError("在线曲目标识无效。")
                clean_track = {"providerId":provider_id,"providerName":str(track.get("providerName", ""))[:80],"itemId":item_id,"kind":track_kind,"title":str(track.get("title", ""))[:160],"creator":str(track.get("creator", ""))[:160],"collection":str(track.get("collection", ""))[:160],"coverUrl":"","durationSeconds":max(0, min(86400, int(track.get("durationSeconds", 0) or 0)))}
                cover = str(track.get("coverUrl", ""))
                if cover:
                    parsed_cover = urlparse(cover)
                    if parsed_cover.scheme == "https" and parsed_cover.hostname and len(cover) <= 1000:
                        clean_track["coverUrl"] = cover
                if not clean_track["title"]:
                    raise ValueError("在线曲目名称不能为空。")
                entry["media"].append({"type":"provider-track","title":title or clean_track["title"],"name":clean_track["providerName"],"savedItemKey":saved_key,"track":clean_track})
            else:
                raise ValueError("作品类型无效。")
        result["interests"].append(entry)
    return result

def get_music_sources(db):
    row = db.execute("SELECT value FROM settings WHERE key='music_sources'").fetchone()
    if not row:
        return []
    try:
        sources = json.loads(row["value"])
        return sources if isinstance(sources, list) else []
    except (TypeError, json.JSONDecodeError):
        return []

def sanitize_music_sources(sources):
    if not isinstance(sources, list) or len(sources) > 5:
        raise ValueError("最多配置 5 个音源。")
    result = []
    seen = set()
    for item in sources:
        if not isinstance(item, dict):
            raise ValueError("音源配置格式无效。")
        source_id = str(item.get("id", ""))
        name = str(item.get("name", "")).strip()[:80]
        base_url = str(item.get("baseUrl", "")).strip().rstrip("/")
        platform = str(item.get("platform", "")).strip().lower()
        enabled = bool(item.get("enabled", True))
        key = str(item.get("apiKey", ""))
        auth_mode = str(item.get("authMode", "token"))
        if not re.fullmatch(r"[a-f0-9]{32}", source_id) or source_id in seen:
            raise ValueError("音源标识无效。")
        seen.add(source_id)
        parsed = urlparse(base_url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or len(base_url) > 1000:
            raise ValueError("音源 API 地址必须是有效的 HTTP 或 HTTPS 地址。")
        if not re.fullmatch(r"[a-z0-9_-]{1,40}", platform) or not name or len(key) > 500 or auth_mode not in ("token", "meting-hmac"):
            raise ValueError("请填写音源名称、平台代码和有效配置。")
        if auth_mode == "meting-hmac" and not key:
            raise ValueError("Meting-API HMAC 鉴权需要填写服务密钥。")
        result.append({"id":source_id,"name":name,"baseUrl":base_url,"platform":platform,"apiKey":key,"authMode":auth_mode,"enabled":enabled})
    return result

class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        return None

def meting_request(source, params, max_bytes=512_000):
    query = {"server":source["platform"], **params}
    if source.get("apiKey"):
        if source.get("authMode", "token") == "meting-hmac" and params.get("type") in ("lrc", "url", "pic"):
            message = f"{source['platform']}{params['type']}{params.get('id', '')}"
            query["token"] = hmac.new(source["apiKey"].encode("utf-8"), message.encode("utf-8"), hashlib.sha1).hexdigest()
        elif source.get("authMode", "token") != "meting-hmac":
            query["token"] = source["apiKey"]
    separator = "&" if "?" in source["baseUrl"] else "?"
    url = source["baseUrl"] + separator + urlencode(query)
    request = Request(url, headers={"Accept":"application/json, text/plain;q=0.9", "User-Agent":"FamilySite/1.0"})
    try:
        with build_opener(_NoRedirectHandler()).open(request, timeout=8) as response:
            if response.status < 200 or response.status >= 300:
                raise ValueError("音源服务暂时不可用。")
            if int(response.headers.get("Content-Length", "0") or 0) > max_bytes:
                raise ValueError("音源响应过大。")
            body = response.read(max_bytes + 1)
    except HTTPError as response:
        try:
            if params.get("type") in ("url", "pic") and response.code in (301, 302, 303, 307, 308):
                location = response.headers.get("Location", "").strip()
                if not location or len(location.encode("utf-8")) > max_bytes:
                    raise ValueError("音源资源跳转地址无效。")
                return location.encode("utf-8")
            raise ValueError("音源服务暂时不可用。")
        finally:
            response.close()
    if len(body) > max_bytes:
        raise ValueError("音源响应过大。")
    return body

def resolve_music_cover(source, row):
    cover_id = str(row.get("pic_id") or row.get("picId") or "").strip()
    direct_cover = ""
    for field in ("pic", "cover", "picUrl", "coverUrl"):
        value = row.get(field)
        if not isinstance(value, str) or not value.strip():
            continue
        value = value.strip()
        parsed = urlparse(value)
        query = parse_qs(parsed.query)
        if query.get("type") == ["pic"] and query.get("id"):
            cover_id = query["id"][0].strip()
            break
        if parsed.scheme == "https" and parsed.hostname and len(value) <= 1000:
            direct_cover = value
            break
    if not cover_id:
        return direct_cover
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,160}", cover_id):
        return direct_cover
    try:
        body = meting_request(source, {"type":"pic", "id":cover_id}, max_bytes=32_000)
        resolved = body.decode("utf-8", errors="replace").strip()
    except (OSError, ValueError, UnicodeError):
        return direct_cover
    parsed = urlparse(resolved)
    if parsed.scheme == "https" and parsed.hostname and len(resolved) <= 4000:
        return resolved
    return direct_cover

def resolve_saved_music_cover(source, track):
    item_id = str(track.get("itemId", "")).strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,160}", item_id):
        return ""
    try:
        resource_type = "album" if track.get("kind") == "album" else "song"
        body = meting_request(source, {"type":resource_type, "id":item_id})
        rows = json.loads(body.decode("utf-8"))
    except (OSError, ValueError, UnicodeError, json.JSONDecodeError):
        return ""
    if isinstance(rows, dict):
        rows = rows.get("data", rows.get("result", rows))
    if isinstance(rows, dict):
        rows = [rows]
    if not isinstance(rows, list):
        return ""
    for row in rows[:20]:
        if not isinstance(row, dict):
            continue
        row_id = str(row.get("id") or row.get("url_id") or "").strip()
        if row_id and row_id != item_id:
            continue
        cover = resolve_music_cover(source, row)
        if cover:
            return cover
    return ""

def search_music_source(source, query, kind="song"):
    body = meting_request(source, {"type":"search", "id":query, "limit":"20"})
    try:
        rows = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("音源搜索响应格式无效。")
    if isinstance(rows, dict):
        rows = rows.get("data", rows.get("result", []))
    if not isinstance(rows, list):
        return []
    results = []
    cover_rows = []
    for row in rows[:20]:
        if not isinstance(row, dict):
            continue
        item_id = str(row.get("id") or row.get("url_id") or "").strip()
        if not item_id:
            play_url = row.get("url", "")
            if isinstance(play_url, str) and len(play_url) <= 4000:
                play_params = parse_qs(urlparse(play_url).query)
                if play_params.get("type") == ["url"]:
                    item_id = str((play_params.get("id") or [""])[0]).strip()
        title = str(row.get("name", row.get("title", ""))).strip()[:160]
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,160}", item_id) or not title:
            continue
        artist = row.get("artist", row.get("author", ""))
        if isinstance(artist, list):
            artist = ", ".join(map(str, artist[:5]))
        album = row.get("album", row.get("collection", ""))
        if isinstance(album, dict):
            album = album.get("name", "")
        cover_rows.append(row)
        try:
            duration = int(row.get("duration", row.get("time", 0)) or 0)
            if duration > 3600:
                duration //= 1000
        except (TypeError, ValueError):
            duration = 0
        results.append({"providerId":source["id"],"providerName":source["name"],"itemId":item_id,"kind":kind,"title":title,"creator":str(artist)[:160],"collection":str(album)[:160],"coverUrl":"","durationSeconds":max(0, min(duration, 86400))})
    if results:
        with ThreadPoolExecutor(max_workers=min(5, len(results))) as executor:
            covers = executor.map(lambda row: resolve_music_cover(source, row), cover_rows)
            for result, cover in zip(results, covers):
                result["coverUrl"] = cover
    return results

def resolve_music_url(source, item_id):
    body = meting_request(source, {"type":"url", "id":item_id}, max_bytes=32_000)
    text = body.decode("utf-8", errors="replace").strip()
    try:
        payload = json.loads(text)
        if isinstance(payload, str):
            text = payload.strip()
        elif isinstance(payload, dict):
            text = str(payload.get("url", payload.get("data", ""))).strip()
    except json.JSONDecodeError:
        pass
    parsed = urlparse(text)
    if parsed.scheme != "https" or not parsed.hostname or len(text) > 4000:
        raise ValueError("这个来源暂时无法播放，请检查音源返回的 HTTPS 播放地址。")
    return text

def connect():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript("""
      CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        password_hash BLOB NOT NULL,
        salt BLOB NOT NULL,
        created_at TEXT NOT NULL
      );
      CREATE TABLE IF NOT EXISTS sessions (
        token_hash BLOB PRIMARY KEY,
        expires_at TEXT NOT NULL
      );
      CREATE TABLE IF NOT EXISTS records (
        id TEXT PRIMARY KEY,
        date TEXT NOT NULL,
        title TEXT NOT NULL,
        story TEXT NOT NULL,
        age_label TEXT NOT NULL DEFAULT '',
        media TEXT NOT NULL DEFAULT '[]',
        created_at TEXT NOT NULL
      );
      CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
      );
    """)
    record_columns = {row[1] for row in db.execute("PRAGMA table_info(records)")}
    if "age_label" not in record_columns:
        db.execute("ALTER TABLE records ADD COLUMN age_label TEXT NOT NULL DEFAULT ''")
    if "media" not in record_columns:
        db.execute("ALTER TABLE records ADD COLUMN media TEXT NOT NULL DEFAULT '[]'")
    policy = db.execute("SELECT value FROM settings WHERE key='session_policy'").fetchone()
    if not policy or policy["value"] != SESSION_POLICY:
        db.execute("DELETE FROM sessions")
        db.execute("INSERT INTO settings(key,value) VALUES('session_policy',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (SESSION_POLICY,))
        db.commit()
    return db

def record_dict(row):
    result = dict(row)
    try:
        result["media"] = json.loads(result.get("media") or "[]")
    except (TypeError, json.JSONDecodeError):
        result["media"] = []
    return result

def validate_record_media(value):
    if not isinstance(value, list) or len(value) > 50:
        raise ValueError("每条成长记录最多添加 50 张照片或视频。")
    result = []
    for asset in value:
        if not isinstance(asset, dict) or asset.get("type") not in ("image", "video"):
            raise ValueError("成长记录只支持照片和视频。")
        url = asset.get("url", "")
        match = re.fullmatch(r"/media/([a-f0-9]{32}\.(?:jpg|jpeg|png|webp|gif|mp4|webm|mov))", str(url))
        if not match or MEDIA_SUFFIXES[Path(match.group(1)).suffix] != asset["type"]:
            raise ValueError("成长记录附件地址无效。")
        title = asset.get("title", "")
        name = asset.get("name", "")
        if not isinstance(title, str) or len(title) > 120 or not isinstance(name, str) or len(name) > 240:
            raise ValueError("成长记录附件名称过长。")
        result.append({"type": asset["type"], "title": title.strip(), "name": name.strip(), "url": url})
    return result

def referenced_media(db):
    referenced = set()
    content = read_content(db)
    for item in content.get("interests", []):
        for asset in item.get("media", []):
            for url in (asset.get("url", ""), asset.get("coverUrl", "")):
                if isinstance(url, str) and url.startswith("/media/"):
                    referenced.add(url.rsplit("/", 1)[-1])
    mascot = content.get("heroMascot", "")
    if isinstance(mascot, str) and mascot.startswith("/media/"):
        referenced.add(mascot.rsplit("/", 1)[-1])
    for row in db.execute("SELECT media FROM records"):
        try:
            for asset in json.loads(row["media"] or "[]"):
                url = asset.get("url", "")
                if isinstance(url, str) and url.startswith("/media/"):
                    referenced.add(url.rsplit("/", 1)[-1])
        except (TypeError, json.JSONDecodeError):
            continue
    return referenced

def public_media_referenced(db, filename):
    content = read_content(db)
    mascot = content.get("heroMascot", "")
    if isinstance(mascot, str) and mascot.rsplit("/", 1)[-1] == filename:
        return True
    if any(
        filename in {asset.get("url", "").rsplit("/", 1)[-1], asset.get("coverUrl", "").rsplit("/", 1)[-1]}
        for item in content.get("interests", [])
        for asset in item.get("media", [])
        if isinstance(asset.get("url", ""), str) and isinstance(asset.get("coverUrl", ""), str)
    ):
        return True
    for row in db.execute("SELECT media FROM records"):
        try:
            for asset in json.loads(row["media"] or "[]"):
                url = asset.get("url", "")
                if isinstance(url, str) and url.rsplit("/", 1)[-1] == filename:
                    return True
        except (TypeError, json.JSONDecodeError):
            continue
    return False

def remove_unreferenced(db, candidates):
    retained = referenced_media(db)
    for filename in set(candidates) - retained:
        if re.fullmatch(r"[a-f0-9]{32}\.(?:jpg|jpeg|png|webp|gif|mp4|webm|mov|mp3|m4a|aac|ogg|wav)", filename):
            (MEDIA_DIR / filename).unlink(missing_ok=True)

def now_utc():
    return datetime.now(timezone.utc)

def token_hash(token):
    return hashlib.sha256(token.encode("ascii")).digest()

def new_session(db):
    token = secrets.token_urlsafe(32)
    expires = now_utc() + timedelta(hours=SESSION_HOURS)
    db.execute("INSERT INTO sessions(token_hash, expires_at) VALUES (?, ?)", (token_hash(token), expires.isoformat()))
    db.commit()
    return token

def safe_upload_name(filename):
    original = Path(str(filename).replace("\\", "/")).name
    suffix = Path(original).suffix.lower()
    if not original or suffix not in MEDIA_SUFFIXES:
        raise ValueError("支持 JPG、PNG、WebP、GIF 图片，MP4、WebM、MOV 视频，以及 MP3、M4A、AAC、OGG、WAV 音频。")
    return original[:240], suffix, MEDIA_SUFFIXES[suffix]

def cleanup_upload_staging():
    staging = DATA_DIR / ".uploads"
    staging.mkdir(parents=True, exist_ok=True)
    cutoff = time.time() - 24 * 60 * 60
    try:
        for entry in staging.iterdir():
            try:
                if entry.is_dir() and entry.stat().st_mtime < cutoff:
                    shutil.rmtree(entry)
            except OSError:
                continue
    except OSError:
        pass

class Handler(BaseHTTPRequestHandler):
    server_version = "FamilyDiary/1"
    sys_version = ""

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args))

    def send_json(self, status, payload, headers=None):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        if COOKIE_SECURE:
            self.send_header("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise ValueError("请求格式无效。")
        if length < 1 or length > 100_000:
            raise ValueError("提交内容过大或为空。")
        if "application/json" not in self.headers.get("Content-Type", ""):
            raise ValueError("请求格式无效。")
        try:
            result = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(result, dict):
                raise ValueError
            return result
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ValueError("请求格式无效。")

    def session(self, db):
        raw = self.headers.get("Cookie", "")
        token = None
        for item in raw.split(";"):
            key, sep, value = item.strip().partition("=")
            if sep and key == COOKIE:
                token = value
                break
        if not token or len(token) > 100:
            return None
        row = db.execute("SELECT token_hash, expires_at FROM sessions WHERE token_hash = ?", (token_hash(token),)).fetchone()
        if not row:
            return None
        if datetime.fromisoformat(row["expires_at"]) < now_utc():
            db.execute("DELETE FROM sessions WHERE token_hash = ?", (row["token_hash"],))
            db.commit()
            return None
        return token

    def cookie_header(self, token, max_age):
        parts = [f"{COOKIE}={token}", "Path=/", "HttpOnly", "SameSite=Strict", f"Max-Age={max_age}"]
        if COOKIE_SECURE:
            parts.append("Secure")
        return "; ".join(parts)

    def require_same_origin(self):
        origin = self.headers.get("Origin")
        if origin:
            host = self.headers.get("Host", "")
            if urlparse(origin).netloc.lower() != host.lower():
                self.send_json(403, {"error": "请求来源无效。"})
                return False
        return True

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/music/config":
            with connect() as db:
                if not self.session(db):
                    return self.send_json(401, {"error":"请先登录家长账号。"})
                sources = [{"id":item["id"],"name":item["name"],"baseUrl":item["baseUrl"],"platform":item["platform"],"authMode":item.get("authMode", "token"),"enabled":item["enabled"],"hasKey":bool(item.get("apiKey"))} for item in get_music_sources(db)]
                return self.send_json(200, {"sources":sources})
        if path == "/api/music/search":
            with connect() as db:
                if not self.session(db):
                    return self.send_json(401, {"error":"请先登录家长账号。"})
                args = parse_qs(urlparse(self.path).query)
                query = args.get("q", [""])[0].strip()
                kind = args.get("kind", ["song"])[0]
                if not query or len(query) > 100 or kind not in ("song", "album"):
                    return self.send_json(400, {"error":"请输入不超过 100 个字符的搜索内容。"})
                results, errors = [], []
                sources = [source for source in get_music_sources(db) if source.get("enabled")]
                if not sources:
                    errors.append({"providerName":"音源设置","message":"请先在“编辑网站”→“音乐音源”配置并启用兼容 API。"})
                for source in sources:
                    try:
                        results.extend(search_music_source(source, query, kind))
                    except Exception:
                        errors.append({"providerName":source["name"],"message":"搜索失败或暂时无法连接。"})
                return self.send_json(200, {"results":results[:60],"errors":errors})
        cover_match = re.fullmatch(r"/api/music/cover/([a-f0-9]{32})", path)
        if cover_match:
            key = cover_match.group(1)
            with connect() as db:
                content = read_content(db)
                asset = next((asset for item in content.get("interests", []) for asset in item.get("media", []) if asset.get("type") == "provider-track" and asset.get("savedItemKey") == key), None)
                if not asset:
                    return self.send_json(404, {"error":"找不到这首歌曲。"})
                track = asset.get("track", {})
                source = next((item for item in get_music_sources(db) if item.get("id") == track.get("providerId") and item.get("enabled")), None)
                if not source:
                    return self.send_json(503, {"error":"这个音源未配置或已停用。"})
                cover = track.get("coverUrl", "")
                if not (isinstance(cover, str) and urlparse(cover).scheme == "https" and urlparse(cover).hostname):
                    cover = resolve_saved_music_cover(source, track)
                    if not cover:
                        return self.send_json(404, {"error":"音源暂时没有提供这首歌曲的封面。"})
                    track["coverUrl"] = cover
                    db.execute("INSERT INTO settings(key,value) VALUES('page_content',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (json.dumps(content, ensure_ascii=False),))
                    db.commit()
                self.send_response(302)
                self.send_header("Location", cover)
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                return
        play_match = re.fullmatch(r"/api/music/play/([a-f0-9]{32})", path)
        if play_match:
            key = play_match.group(1)
            with connect() as db:
                content = read_content(db)
                track = next((asset for item in content.get("interests", []) for asset in item.get("media", []) if asset.get("type") == "provider-track" and asset.get("savedItemKey") == key), None)
                if not track:
                    return self.send_json(404, {"error":"这首内容已从兴趣卡片移除。"})
                source = next((item for item in get_music_sources(db) if item.get("id") == track["track"]["providerId"] and item.get("enabled")), None)
                if not source:
                    return self.send_json(503, {"error":"这个音源未配置或已停用。"})
                try:
                    media_url = resolve_music_url(source, track["track"]["itemId"])
                except Exception:
                    return self.send_json(502, {"error":"这个来源暂时无法播放。"})
                return self.send_json(200, {"url":media_url})
        if path == "/api/backup":
            with connect() as db:
                if not self.session(db):
                    return self.send_json(401, {"error":"请先登录家长账号。"})
                backup = {
                    "version": 1,
                    "content": read_content(db),
                    "records": [record_dict(row) for row in db.execute("SELECT id,date,title,story,age_label,media,created_at FROM records ORDER BY date,created_at")],
                }
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            MEDIA_DIR.mkdir(parents=True, exist_ok=True)
            media_names = {
                asset["url"].rsplit("/", 1)[-1]
                for item in backup["content"].get("interests", [])
                for asset in item.get("media", [])
                if asset.get("type") in ("image", "video", "audio")
            }
            media_names.update(
                asset["coverUrl"].rsplit("/", 1)[-1]
                for item in backup["content"].get("interests", [])
                for asset in item.get("media", [])
                if asset.get("type") == "audio" and isinstance(asset.get("coverUrl"), str) and asset["coverUrl"].startswith("/media/")
            )
            mascot_image = backup["content"].get("heroMascot", "")
            if isinstance(mascot_image, str) and mascot_image.startswith("/media/"):
                media_names.add(mascot_image.rsplit("/", 1)[-1])
            for record in backup["records"]:
                for asset in record["media"]:
                    media_names.add(asset["url"].rsplit("/", 1)[-1])
            media_paths = [MEDIA_DIR / name for name in sorted(media_names) if re.fullmatch(r"[a-f0-9]{32}\.[a-z0-9]{2,5}", name) and (MEDIA_DIR / name).is_file()]
            total_size = sum(path.stat().st_size for path in media_paths)
            if total_size > MAX_BACKUP_BYTES:
                return self.send_json(413, {"error":"备份附件总量超过 4 GB，请先减少大视频后再备份。"})
            try:
                with tempfile.TemporaryFile(dir=DATA_DIR) as archive_file:
                    with tarfile.open(fileobj=archive_file, mode="w:gz") as archive:
                        metadata = json.dumps(backup, ensure_ascii=False).encode("utf-8")
                        info = tarfile.TarInfo("backup.json")
                        info.size = len(metadata)
                        archive.addfile(info, __import__("io").BytesIO(metadata))
                        for media_path in media_paths:
                            archive.add(media_path, arcname="media/" + media_path.name, recursive=False)
                    size = archive_file.tell()
                    archive_file.seek(0)
                    self.send_response(200)
                    self.send_header("Content-Type", "application/gzip")
                    self.send_header("Content-Disposition", 'attachment; filename="family-site-backup.tar.gz"')
                    self.send_header("Content-Length", str(size))
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.end_headers()
                    shutil.copyfileobj(archive_file, self.wfile, length=64 * 1024)
            except (BrokenPipeError, ConnectionResetError):
                pass
            except OSError:
                return self.send_json(500, {"error":"创建备份失败，请检查服务器磁盘空间。"})
            return
        if path == "/api/state":
            with connect() as db:
                setup_required = db.execute("SELECT 1 FROM users LIMIT 1").fetchone() is None
                content = read_content(db)
                token = self.session(db)
                session_row = db.execute("SELECT expires_at FROM sessions WHERE token_hash=?", (token_hash(token),)).fetchone() if token else None
                rows = db.execute("SELECT id,date,title,story,age_label,media,created_at FROM records ORDER BY date DESC, created_at DESC").fetchall()
                visible_records = [record_dict(row) for row in rows]
                return self.send_json(200, {"setupRequired": setup_required, "authenticated": bool(token), "sessionExpiresAt":session_row["expires_at"] if session_row else None, "records": visible_records, "content": content})
        media_match = re.fullmatch(r"/media/([a-f0-9]{32}\.[a-z0-9]{2,5})", path)
        if media_match:
            filename = media_match.group(1)
            with connect() as db:
                is_public = public_media_referenced(db, filename)
                if not is_public and not self.session(db):
                    return self.send_json(404, {"error":"找不到这个作品。"})
            return self.send_media(MEDIA_DIR / filename, is_public=is_public)
        if path == "/" or path == "/index.html":
            return self.send_file(ROOT / "index.html", "text/html; charset=utf-8")
        if path == "/app.js":
            return self.send_file(ROOT / "app.js", "text/javascript; charset=utf-8")
        if path == "/style.css":
            return self.send_file(ROOT / "style.css", "text/css; charset=utf-8")
        if path == "/admin.css":
            return self.send_file(ROOT / "admin.css", "text/css; charset=utf-8")
        return self.send_json(404, {"error": "找不到这个页面。"})

    def send_file(self, path, content_type):
        try:
            body = path.read_bytes()
        except OSError:
            return self.send_json(404, {"error": "找不到这个页面。"})
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; img-src 'self' https: data: blob:; media-src 'self' https:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        if COOKIE_SECURE:
            self.send_header("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        self.end_headers()
        self.wfile.write(body)

    def send_media(self, path, is_public=False):
        try:
            size = path.stat().st_size
            suffix = path.suffix.lower()
            kind = MEDIA_SUFFIXES.get(suffix)
            content_type = {
                ".jpg":"image/jpeg", ".jpeg":"image/jpeg", ".png":"image/png", ".webp":"image/webp", ".gif":"image/gif",
                ".mp4":"video/mp4", ".webm":"video/webm", ".mov":"video/quicktime",
                ".mp3":"audio/mpeg", ".m4a":"audio/mp4", ".aac":"audio/aac", ".ogg":"audio/ogg", ".wav":"audio/wav",
            }[suffix]
            if not kind:
                raise OSError
        except (OSError, KeyError):
            return self.send_json(404, {"error":"找不到这个作品。"})
        start, end, status = 0, size - 1, 200
        range_header = self.headers.get("Range", "")
        if range_header:
            match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header.strip())
            if not match:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return
            left, right = match.groups()
            if left:
                start = int(left)
                end = min(int(right), size - 1) if right else size - 1
            elif right:
                start = max(0, size - int(right))
            if start >= size or start > end:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return
            status = 206
        length = end - start + 1
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("X-Content-Type-Options", "nosniff")
        # Only published images may enter browser and shared CDN caches.
        cache_control = "public, max-age=300, s-maxage=300" if is_public and kind == "image" else "private, no-store"
        self.send_header("Cache-Control", cache_control)
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        try:
            with path.open("rb") as stream:
                stream.seek(start)
                remaining = length
                while remaining:
                    chunk = stream.read(min(64 * 1024, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_POST(self):
        if not self.require_same_origin():
            return
        path = urlparse(self.path).path
        if path == "/api/music/test":
            with connect() as db:
                if not self.session(db):
                    return self.send_json(401, {"error":"请先登录家长账号。"})
            try:
                payload = self.read_json()
                source = sanitize_music_sources([payload.get("source")])[0]
                search_music_source(source, "小星星")
            except ValueError as error:
                return self.send_json(400, {"error":str(error)})
            except Exception:
                return self.send_json(502, {"error":"无法连接音源，或响应不符合 Meting API 兼容格式。"})
            return self.send_json(200, {"ok":True,"message":"连接成功，搜索接口已返回有效响应。"})
        if path == "/api/restore":
            with connect() as db:
                if not self.session(db):
                    return self.send_json(401, {"error":"请先登录家长账号。"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return self.send_json(400, {"error":"备份文件无效。"})
            if length < 1 or length > MAX_BACKUP_BYTES:
                return self.send_json(413, {"error":"备份文件为空或超过 4 GB。"})
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            stage = Path(tempfile.mkdtemp(prefix="restore-", dir=DATA_DIR))
            archive_path = stage / "upload.tar.gz"
            try:
                with archive_path.open("wb") as output:
                    remaining = length
                    while remaining:
                        chunk = self.rfile.read(min(64 * 1024, remaining))
                        if not chunk:
                            raise ValueError("备份上传中断，请重试。")
                        output.write(chunk)
                        remaining -= len(chunk)
                payload = None
                extracted_media = stage / "media"
                extracted_media.mkdir()
                media_seen = set()
                expanded = 0
                with tarfile.open(archive_path, mode="r:gz") as archive:
                    members = archive.getmembers()
                    if len(members) > 10002:
                        raise ValueError("备份文件包含过多项目。")
                    for member in members:
                        if not member.isfile() or member.issym() or member.islnk():
                            raise ValueError("备份文件格式无效。")
                        expanded += member.size
                        if expanded > MAX_BACKUP_BYTES:
                            raise ValueError("备份解压后超过 4 GB。")
                        if member.name == "backup.json":
                            if member.size > 25 * 1024 * 1024 or payload is not None:
                                raise ValueError("备份信息无效。")
                            stream = archive.extractfile(member)
                            payload = json.loads(stream.read().decode("utf-8"))
                        elif re.fullmatch(r"media/[a-f0-9]{32}\.[a-z0-9]{2,5}", member.name):
                            filename = member.name.split("/", 1)[1]
                            if filename in media_seen or member.size > MAX_UPLOAD_BYTES:
                                raise ValueError("备份中的媒体文件无效。")
                            media_seen.add(filename)
                            source = archive.extractfile(member)
                            with (extracted_media / filename).open("wb") as output:
                                shutil.copyfileobj(source, output, length=64 * 1024)
                        else:
                            raise ValueError("备份文件含有无法识别的路径。")
                if not isinstance(payload, dict) or payload.get("version") != 1 or not isinstance(payload.get("records"), list):
                    raise ValueError("这不是可识别的家庭网站备份。")
                content = validate_content(payload.get("content"))
                records = []
                seen_ids = set()
                for record in payload["records"]:
                    if not isinstance(record, dict):
                        raise ValueError("备份中的成长记录格式无效。")
                    record_id = str(record.get("id", ""))
                    record_date = str(record.get("date", ""))
                    title = str(record.get("title", ""))
                    story = str(record.get("story", ""))
                    age_label = str(record.get("age_label", ""))
                    created_at = str(record.get("created_at", now_utc().isoformat()))
                    record_media = validate_record_media(record.get("media", []))
                    if not re.fullmatch(r"[A-Za-z0-9_-]{1,50}", record_id) or record_id in seen_ids:
                        raise ValueError("备份中的记录编号无效。")
                    date.fromisoformat(record_date)
                    if not title or len(title) > 100 or not story or len(story) > 3000 or len(age_label) > 40:
                        raise ValueError("备份中的成长记录内容无效。")
                    seen_ids.add(record_id)
                    records.append((record_id, record_date, title, story, age_label, json.dumps(record_media, ensure_ascii=False), created_at))
                referenced = {
                    asset["url"].rsplit("/", 1)[-1]
                    for item in content["interests"]
                    for asset in item["media"]
                    if asset["type"] in ("image", "video", "audio")
                }
                referenced.update(
                    asset["coverUrl"].rsplit("/", 1)[-1]
                    for item in content["interests"]
                    for asset in item["media"]
                    if asset["type"] == "audio" and isinstance(asset.get("coverUrl"), str) and asset["coverUrl"].startswith("/media/")
                )
                mascot_image = content.get("heroMascot", "")
                if isinstance(mascot_image, str) and mascot_image.startswith("/media/"):
                    referenced.add(mascot_image.rsplit("/", 1)[-1])
                for record in records:
                    for asset in json.loads(record[5]):
                        referenced.add(asset["url"].rsplit("/", 1)[-1])
                if not referenced.issubset(media_seen):
                    raise ValueError("备份缺少页面或成长记录引用的媒体文件。")
                old_media = DATA_DIR / ("media-before-restore-" + secrets.token_hex(8))
                had_old_media = MEDIA_DIR.exists()
                with connect() as db:
                    if not self.session(db):
                        raise PermissionError("登录状态已过期，请重新登录后恢复。")
                    db.execute("BEGIN IMMEDIATE")
                    try:
                        if had_old_media:
                            MEDIA_DIR.rename(old_media)
                        extracted_media.rename(MEDIA_DIR)
                        db.execute("DELETE FROM records")
                        db.execute("DELETE FROM settings WHERE key='page_content'")
                        db.executemany("INSERT INTO records(id,date,title,story,age_label,media,created_at) VALUES (?,?,?,?,?,?,?)", records)
                        db.execute("INSERT INTO settings(key,value) VALUES('page_content',?)", (json.dumps(content, ensure_ascii=False),))
                        db.commit()
                    except Exception:
                        db.rollback()
                        if MEDIA_DIR.exists():
                            shutil.rmtree(MEDIA_DIR)
                        if had_old_media and old_media.exists():
                            old_media.rename(MEDIA_DIR)
                        raise
                if old_media.exists():
                    shutil.rmtree(old_media)
                with connect() as db:
                    rows = db.execute("SELECT id,date,title,story,age_label,media,created_at FROM records ORDER BY date DESC, created_at DESC").fetchall()
                    restored_content = read_content(db)
                shutil.rmtree(stage, ignore_errors=True)
                return self.send_json(200, {"ok":True,"records":[record_dict(row) for row in rows],"content":restored_content})
            except (ValueError, OSError, tarfile.TarError, json.JSONDecodeError, UnicodeDecodeError, PermissionError) as error:
                shutil.rmtree(stage, ignore_errors=True)
                return self.send_json(400, {"error":str(error) or "无法恢复该备份。"})
        if path == "/api/media/chunk":
            with connect() as db:
                if not self.session(db):
                    return self.send_json(401, {"error":"请先登录家长账号。"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return self.send_json(400, {"error":"上传请求无效。"})
            query = parse_qs(urlparse(self.path).query)
            upload_id = query.get("id", [""])[0]
            try:
                original, suffix, kind = safe_upload_name(query.get("filename", [""])[0])
                part = int(query.get("part", [""])[0])
                parts = int(query.get("parts", [""])[0])
            except (ValueError, TypeError) as error:
                return self.send_json(400, {"error":str(error) or "分块上传参数无效。"})
            if not re.fullmatch(r"[a-f0-9]{32}", upload_id) or parts < 1 or parts > (MAX_UPLOAD_BYTES + MAX_UPLOAD_CHUNK_BYTES - 1) // MAX_UPLOAD_CHUNK_BYTES or part < 0 or part >= parts:
                return self.send_json(400, {"error":"分块上传参数无效。"})
            if length < 1 or length > MAX_UPLOAD_CHUNK_BYTES:
                return self.send_json(413, {"error":"上传分块超过 8 MiB。"})
            cleanup_upload_staging()
            upload_dir = DATA_DIR / ".uploads" / upload_id
            upload_dir.mkdir(parents=True, exist_ok=True)
            manifest_path = upload_dir / "manifest.json"
            manifest = {"name":original,"suffix":suffix,"type":kind,"parts":parts}
            try:
                if manifest_path.exists() and json.loads(manifest_path.read_text("utf-8")) != manifest:
                    return self.send_json(409, {"error":"上传分块信息不一致，请重新选择文件。"})
                manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
                target = upload_dir / f"part-{part:03d}"
                temporary = upload_dir / f"part-{part:03d}.tmp"
                with temporary.open("wb") as stream:
                    remaining = length
                    while remaining:
                        chunk = self.rfile.read(min(64 * 1024, remaining))
                        if not chunk:
                            raise OSError("上传中断")
                        stream.write(chunk)
                        remaining -= len(chunk)
                temporary.replace(target)
            except (OSError, json.JSONDecodeError):
                (upload_dir / f"part-{part:03d}.tmp").unlink(missing_ok=True)
                return self.send_json(400, {"error":"分块上传中断，请重试。"})
            return self.send_json(201, {"ok":True,"part":part})
        if path == "/api/media/finish":
            with connect() as db:
                if not self.session(db):
                    return self.send_json(401, {"error":"请先登录家长账号。"})
            query = parse_qs(urlparse(self.path).query)
            upload_id = query.get("id", [""])[0]
            if not re.fullmatch(r"[a-f0-9]{32}", upload_id):
                return self.send_json(400, {"error":"上传编号无效。"})
            upload_dir = DATA_DIR / ".uploads" / upload_id
            try:
                manifest = json.loads((upload_dir / "manifest.json").read_text("utf-8"))
                original, suffix, kind = safe_upload_name(manifest.get("name", ""))
                parts = int(manifest.get("parts", 0))
                if manifest.get("suffix") != suffix or manifest.get("type") != kind or not 1 <= parts <= (MAX_UPLOAD_BYTES + MAX_UPLOAD_CHUNK_BYTES - 1) // MAX_UPLOAD_CHUNK_BYTES:
                    raise ValueError("分块上传信息无效。")
                part_paths = [upload_dir / f"part-{part:03d}" for part in range(parts)]
                if not all(path.is_file() and path.stat().st_size <= MAX_UPLOAD_CHUNK_BYTES for path in part_paths):
                    raise ValueError("有分块尚未上传完成，请重试。")
                total_size = sum(path.stat().st_size for path in part_paths)
                if total_size < 1 or total_size > MAX_UPLOAD_BYTES:
                    raise ValueError("单个作品最多上传 200 MiB。")
                MEDIA_DIR.mkdir(parents=True, exist_ok=True)
                stored = secrets.token_hex(16) + suffix
                destination = MEDIA_DIR / stored
                try:
                    with destination.open("wb") as output:
                        for part_path in part_paths:
                            with part_path.open("rb") as source:
                                shutil.copyfileobj(source, output, length=64 * 1024)
                except OSError:
                    destination.unlink(missing_ok=True)
                    raise
                shutil.rmtree(upload_dir, ignore_errors=True)
                return self.send_json(201, {"type":kind,"name":original,"title":Path(original).stem[:120],"url":f"/media/{stored}"})
            except (ValueError, OSError, TypeError, json.JSONDecodeError) as error:
                return self.send_json(400, {"error":str(error) or "无法完成媒体文件上传。"})
        if path == "/api/media":
            with connect() as db:
                if not self.session(db):
                    return self.send_json(401, {"error":"请先登录家长账号。"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return self.send_json(400, {"error":"上传请求无效。"})
            if length < 1 or length > MAX_UPLOAD_BYTES:
                return self.send_json(413, {"error":"单个作品最多上传 200 MiB。"})
            query = parse_qs(urlparse(self.path).query)
            try:
                original, suffix, kind = safe_upload_name(query.get("filename", [""])[0])
            except ValueError as error:
                return self.send_json(400, {"error":str(error)})
            stored = secrets.token_hex(16) + suffix
            MEDIA_DIR.mkdir(parents=True, exist_ok=True)
            destination = MEDIA_DIR / stored
            try:
                with destination.open("wb") as stream:
                    remaining = length
                    while remaining:
                        chunk = self.rfile.read(min(64 * 1024, remaining))
                        if not chunk:
                            raise OSError("上传中断")
                        stream.write(chunk)
                        remaining -= len(chunk)
            except OSError:
                destination.unlink(missing_ok=True)
                return self.send_json(400, {"error":"文件上传未完成，请重试。"})
            return self.send_json(201, {"type":kind,"name":original[:240],"title":Path(original).stem[:120],"url":f"/media/{stored}"})
        try:
            data = self.read_json()
        except ValueError as error:
            return self.send_json(400, {"error": str(error)})
        with connect() as db:
            if path == "/api/setup":
                if db.execute("SELECT 1 FROM users LIMIT 1").fetchone():
                    return self.send_json(409, {"error": "家长账号已经设置，请直接登录。"})
                name = str(data.get("name", "")).strip()
                email = str(data.get("email", "")).strip().lower()
                password = str(data.get("password", ""))
                if not name or len(name) > 40:
                    return self.send_json(400, {"error": "请填写 1–40 个字的家长称呼。"})
                if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or len(email) > 254:
                    return self.send_json(400, {"error": "请输入有效的邮箱地址。"})
                if len(password) < 12 or len(password) > 200:
                    return self.send_json(400, {"error": "密码请设置为 12–200 个字符。"})
                salt = secrets.token_bytes(16)
                password_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ROUNDS)
                try:
                    db.execute("INSERT INTO users(id,name,email,password_hash,salt,created_at) VALUES (1,?,?,?,?,?)", (name,email,password_hash,salt,now_utc().isoformat()))
                    token = new_session(db)
                except sqlite3.IntegrityError:
                    return self.send_json(409, {"error": "家长账号已经设置，请直接登录。"})
                return self.send_json(200, {"setupRequired": False,"authenticated": True,"records": []}, {"Set-Cookie":self.cookie_header(token, SESSION_HOURS*3600)})
            if path == "/api/login":
                ip = self.client_address[0]
                attempts = [stamp for stamp in LOGIN_ATTEMPTS.get(ip, []) if stamp > time.time()-900]
                if len(attempts) >= 10:
                    LOGIN_ATTEMPTS[ip] = attempts
                    return self.send_json(429, {"error": "尝试次数较多，请 15 分钟后再试。"})
                LOGIN_ATTEMPTS[ip] = attempts
                password = str(data.get("password", ""))
                row = db.execute("SELECT password_hash,salt FROM users WHERE id=1").fetchone()
                salt = row["salt"] if row else b"\0"*16
                expected = row["password_hash"] if row else b"\0"*32
                actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8")[:1000], salt, PBKDF2_ROUNDS)
                if not row or not hmac.compare_digest(actual, expected):
                    attempts.append(time.time())
                    LOGIN_ATTEMPTS[ip] = attempts
                    return self.send_json(401, {"error": "密码不正确。"})
                LOGIN_ATTEMPTS.pop(ip, None)
                token = new_session(db)
                rows = db.execute("SELECT id,date,title,story,age_label,media,created_at FROM records ORDER BY date DESC, created_at DESC").fetchall()
                return self.send_json(200, {"setupRequired": False,"authenticated": True,"records":[record_dict(x) for x in rows]}, {"Set-Cookie":self.cookie_header(token, SESSION_HOURS*3600)})
            token = self.session(db)
            if not token:
                return self.send_json(401, {"error": "请先登录家长账号。"})
            if path == "/api/logout":
                db.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash(token),))
                db.commit()
                return self.send_json(200, {"setupRequired":False,"authenticated":False,"records":[]}, {"Set-Cookie":self.cookie_header("",0)})
            if path == "/api/records":
                title = str(data.get("title", "")).strip()
                story = str(data.get("story", "")).strip()
                age_label = str(data.get("age_label", "")).strip()
                try:
                    record_media = validate_record_media(data.get("media", []))
                except ValueError as error:
                    return self.send_json(400, {"error":str(error)})
                record_date = str(data.get("date", ""))
                try:
                    date.fromisoformat(record_date)
                except ValueError:
                    return self.send_json(400, {"error": "请选择有效日期。"})
                if not title or len(title) > 100 or not story or len(story) > 3000 or len(age_label) > 40:
                    return self.send_json(400, {"error": "请填写标题和故事（标题最多 100 字，故事最多 3000 字）。"})
                record_id = secrets.token_urlsafe(12)
                db.execute("INSERT INTO records(id,date,title,story,age_label,media,created_at) VALUES (?,?,?,?,?,?,?)", (record_id,record_date,title,story,age_label,json.dumps(record_media, ensure_ascii=False),now_utc().isoformat()))
                db.commit()
                return self.send_json(201, {"ok":True,"id":record_id})
        self.send_json(404, {"error": "找不到这个接口。"})

    def do_DELETE(self):
        if not self.require_same_origin():
            return
        media_match = re.fullmatch(r"/api/media/([a-f0-9]{32}\.[a-z0-9]{2,5})", urlparse(self.path).path)
        if media_match:
            with connect() as db:
                if not self.session(db):
                    return self.send_json(401, {"error":"请先登录家长账号。"})
                filename = media_match.group(1)
                if filename in referenced_media(db):
                    return self.send_json(409, {"error":"这个文件仍被页面或日记记录使用，请先从编辑页面移除引用并保存。"})
                (MEDIA_DIR / filename).unlink(missing_ok=True)
            return self.send_json(200, {"ok":True})
        match = re.fullmatch(r"/api/records/([A-Za-z0-9_-]{1,50})", urlparse(self.path).path)
        if not match:
            return self.send_json(404, {"error": "找不到这条记录。"})
        with connect() as db:
            if not self.session(db):
                return self.send_json(401, {"error": "请先登录家长账号。"})
            row = db.execute("SELECT media FROM records WHERE id=?", (unquote(match.group(1)),)).fetchone()
            if not row:
                return self.send_json(404, {"error":"找不到这条记录。"})
            candidates = [asset.get("url", "").rsplit("/", 1)[-1] for asset in json.loads(row["media"] or "[]")]
            db.execute("DELETE FROM records WHERE id=?", (unquote(match.group(1)),))
            db.commit()
            remove_unreferenced(db, candidates)
        self.send_json(200, {"ok":True})

    def do_PUT(self):
        if not self.require_same_origin():
            return
        path = urlparse(self.path).path
        try:
            data = self.read_json()
        except ValueError as error:
            return self.send_json(400, {"error": str(error)})
        with connect() as db:
            if not self.session(db):
                return self.send_json(401, {"error": "请先登录家长账号。"})
            if path == "/api/music/config":
                try:
                    sources = sanitize_music_sources(data.get("sources"))
                except ValueError as error:
                    return self.send_json(400, {"error":str(error)})
                existing = {source["id"]:source for source in get_music_sources(db)}
                for source in sources:
                    if not source.get("apiKey") and source["id"] in existing:
                        source["apiKey"] = existing[source["id"]].get("apiKey", "")
                db.execute("INSERT INTO settings(key,value) VALUES('music_sources',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (json.dumps(sources, ensure_ascii=False),))
                db.commit()
                return self.send_json(200, {"ok":True,"sources":[{"id":item["id"],"name":item["name"],"baseUrl":item["baseUrl"],"platform":item["platform"],"authMode":item.get("authMode", "token"),"enabled":item["enabled"],"hasKey":bool(item.get("apiKey"))} for item in sources]})
            if path == "/api/content":
                try:
                    content = validate_content(data)
                except ValueError as error:
                    return self.send_json(400, {"error": str(error)})
                old_content = read_content(db)
                db.execute("INSERT INTO settings(key,value) VALUES('page_content',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (json.dumps(content, ensure_ascii=False),))
                db.commit()
                retained = {asset["url"].rsplit("/", 1)[-1] for item in content["interests"] for asset in item["media"] if asset["type"] in ("image", "video", "audio")}
                retained.update(asset["coverUrl"].rsplit("/", 1)[-1] for item in content["interests"] for asset in item["media"] if asset.get("type") == "audio" and isinstance(asset.get("coverUrl"), str) and asset["coverUrl"].startswith("/media/"))
                previous = {asset["url"].rsplit("/", 1)[-1] for item in old_content.get("interests", []) for asset in item.get("media", []) if asset.get("type") in ("image", "video", "audio") and isinstance(asset.get("url"), str)}
                previous.update(asset["coverUrl"].rsplit("/", 1)[-1] for item in old_content.get("interests", []) for asset in item.get("media", []) if asset.get("type") == "audio" and isinstance(asset.get("coverUrl"), str) and asset["coverUrl"].startswith("/media/"))
                if isinstance(content.get("heroMascot"), str) and content["heroMascot"].startswith("/media/"):
                    retained.add(content["heroMascot"].rsplit("/", 1)[-1])
                if isinstance(old_content.get("heroMascot"), str) and old_content["heroMascot"].startswith("/media/"):
                    previous.add(old_content["heroMascot"].rsplit("/", 1)[-1])
                remove_unreferenced(db, previous - retained)
                return self.send_json(200, {"ok":True,"content":content})
            match = re.fullmatch(r"/api/records/([A-Za-z0-9_-]{1,50})", path)
            if match:
                record_id = unquote(match.group(1))
                title = str(data.get("title", "")).strip()
                story = str(data.get("story", "")).strip()
                age_label = str(data.get("age_label", "")).strip()
                existing = db.execute("SELECT media FROM records WHERE id=?", (record_id,)).fetchone()
                if not existing:
                    return self.send_json(404, {"error":"找不到这条成长记录。"})
                try:
                    record_media = validate_record_media(data["media"]) if "media" in data else json.loads(existing["media"] or "[]")
                except ValueError as error:
                    return self.send_json(400, {"error":str(error)})
                old_media = json.loads(existing["media"] or "[]")
                record_date = str(data.get("date", ""))
                try:
                    date.fromisoformat(record_date)
                except ValueError:
                    return self.send_json(400, {"error":"请选择有效日期。"})
                if not title or len(title) > 100 or not story or len(story) > 3000 or len(age_label) > 40:
                    return self.send_json(400, {"error":"请填写标题和故事（标题最多 100 字，故事最多 3000 字）。"})
                cursor = db.execute("UPDATE records SET date=?, title=?, story=?, age_label=?, media=? WHERE id=?", (record_date,title,story,age_label,json.dumps(record_media, ensure_ascii=False),record_id))
                db.commit()
                if cursor.rowcount == 0:
                    return self.send_json(404, {"error":"找不到这条成长记录。"})
                old_names = [asset.get("url", "").rsplit("/", 1)[-1] for asset in old_media]
                new_names = {asset.get("url", "").rsplit("/", 1)[-1] for asset in record_media}
                remove_unreferenced(db, set(old_names) - new_names)
                return self.send_json(200, {"ok":True})
        self.send_json(404, {"error":"找不到这个接口。"})

if __name__ == "__main__":
    with connect():
        pass
    print(f"kani的奇妙小世界已启动：http://127.0.0.1:{PORT}")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()

