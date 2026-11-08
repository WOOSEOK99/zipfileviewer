"""TheGamesDB public-page fallback for console genres (no API key)."""
import html
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from functools import lru_cache
from html.parser import HTMLParser

from mixins.genre_lookup import _classify

PLATFORMS = {
    "gba": {"nintendo game boy advance", "game boy advance"},
    "snes": {"super nintendo (snes)", "super nintendo", "super nintendo entertainment system"},
    "nes": {"nintendo entertainment system (nes)", "nintendo entertainment system", "nintendo nes"},
    "genesis": {"sega genesis", "sega mega drive", "mega drive"},
}
BASE = "https://thegamesdb.net/"
MAX_HTML_BYTES = 1_000_000
_BLOCK_UNTIL = 0.0


def _key(value):
    value = unicodedata.normalize("NFKD", value.casefold())
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "", value)


class _SearchResults(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.items = []
        self._id = None
        self._paragraphs = []
        self._in_p = False
        self._p_class = ""
        self._parts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and self._id is None:
            matched = re.fullmatch(r"(?:\./|/)?game\.php\?id=(\d+)", html.unescape(attrs.get("href", "")))
            if matched:
                self._id = matched.group(1)
                self._paragraphs = []
        elif tag == "p" and self._id is not None:
            self._in_p = True
            self._p_class = attrs.get("class", "")
            self._parts = []

    def handle_data(self, data):
        if self._in_p:
            self._parts.append(data)

    def handle_endtag(self, tag):
        if tag == "p" and self._in_p:
            self._paragraphs.append((self._p_class, " ".join("".join(self._parts).split())))
            self._in_p = False
        elif tag == "a" and self._id is not None:
            title = next((value for cls, value in self._paragraphs if "text-muted" not in cls and value), "")
            platform = next((value for cls, value in self._paragraphs if "text-muted" in cls and value), "")
            if title and platform:
                self.items.append((self._id, title, platform))
            self._id = None
            self._in_p = False


class _GameDetails(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.paragraphs = []
        self._capture = ""
        self._parts = []

    def handle_starttag(self, tag, attrs):
        if tag in ("h1", "p") and not self._capture:
            self._capture = tag
            self._parts = []

    def handle_data(self, data):
        if self._capture:
            self._parts.append(data)

    def handle_endtag(self, tag):
        if tag == self._capture:
            value = " ".join("".join(self._parts).split())
            if tag == "h1" and value and not self.title:
                self.title = value
            elif tag == "p" and value:
                self.paragraphs.append(value)
            self._capture = ""


def _get_html(url):
    global _BLOCK_UNTIL
    if time.monotonic() < _BLOCK_UNTIL:
        raise OSError("TheGamesDB 요청 제한 중")
    req = urllib.request.Request(url, headers={
        "User-Agent": "ZipfileViewer/2.2 (game metadata lookup)",
        "Accept": "text/html",
    })
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            data = response.read(MAX_HTML_BYTES + 1)
    except urllib.error.HTTPError as exc:
        if exc.code in (403, 429, 503):
            _BLOCK_UNTIL = time.monotonic() + 120
        raise
    if len(data) > MAX_HTML_BYTES:
        raise ValueError("TheGamesDB 응답 크기 초과")
    return data.decode("utf-8-sig", errors="replace")


@lru_cache(maxsize=1024)
def lookup_extra_genre(title, system):
    """Return (genre, reason, source URL); require exact title and platform."""
    title = title.strip()
    if system not in PLATFORMS or not title or not _key(title):
        return "", "조회할 영문 제목 또는 지원 기종이 없습니다.", ""
    search_url = BASE + "search.php?" + urllib.parse.urlencode({"name": title})
    try:
        listing = _SearchResults()
        listing.feed(_get_html(search_url))
        matches = [(game_id, name) for game_id, name, platform in listing.items
                   if _key(name) == _key(title)
                   and platform.casefold().strip() in PLATFORMS[system]]
        matches = list(dict.fromkeys(matches))
        if len(matches) != 1:
            note = "게임명이 일치하는 기종별 결과 없음" if not matches else "동일 제목/기종의 게임이 여러 개 있음"
            return "", "TheGamesDB: " + note, ""
        game_id, _ = matches[0]
        game_url = BASE + "game.php?id=" + game_id
        details = _GameDetails()
        details.feed(_get_html(game_url))
        if _key(details.title) != _key(title):
            return "", "TheGamesDB: 상세 페이지 제목 불일치", game_url
        platforms = [text.split(":", 1)[1].strip().casefold() for text in details.paragraphs
                     if text.startswith("Platform:")]
        if not any(value in PLATFORMS[system] for value in platforms):
            return "", "TheGamesDB: 상세 페이지 기종 불일치", game_url
        genres = [text.split(":", 1)[1].strip() for text in details.paragraphs
                  if text.startswith("Genre(s):")]
        classified = {_classify([part]) for value in genres
                      for part in re.split(r"\s*[|,]\s*", value)} - {""}
        if len(classified) != 1:
            return "", "TheGamesDB: 장르 없음 또는 복합 장르 (수동 확인)", game_url
        return classified.pop(), "TheGamesDB 영문 게임명·기종 일치", game_url
    except (OSError, ValueError, UnicodeError) as exc:
        return "", "TheGamesDB 조회 실패: " + str(exc)[:80], ""
