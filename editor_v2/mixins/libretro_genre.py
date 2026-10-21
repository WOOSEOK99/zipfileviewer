"""Libretro 기종별 장르 DAT: ZIP 내부 ROM CRC32/영문 제목 매칭 및 로컬 캐시."""
import os
import re
import tempfile
import time
import unicodedata
import urllib.parse
import urllib.request
from functools import lru_cache

from mixins.genre_lookup import _classify

LIBRETRO_FILES = {
    "snes": "Nintendo - Super Nintendo Entertainment System.dat",
    "nes": "Nintendo - Nintendo Entertainment System.dat",
    "genesis": "Sega - Mega Drive - Genesis.dat",
    "gba": "Nintendo - Game Boy Advance.dat",
}
BASE_URL = "https://raw.githubusercontent.com/libretro/libretro-database/master/metadat/genre/"
BROWSER_URL = "https://github.com/libretro/libretro-database/blob/master/metadat/genre/"
CACHE_SECONDS = 30 * 24 * 60 * 60
MAX_DAT_BYTES = 16 * 1024 * 1024

# Libretro genre DAT 형식: game ( comment "..." genre "..." rom ( crc ABCD1234 ) )
_ENTRY = re.compile(
    r'\bgame\s*\(\s*comment\s*"((?:[^"\\]|\\.)*)"\s*'
    r'genre\s*"((?:[^"\\]|\\.)*)"\s*'
    r'rom\s*\(\s*crc\s+([0-9a-fA-F]{8})\s*\)\s*\)',
    flags=re.IGNORECASE,
)


def _display_title(name):
    name = re.sub(r'\s*\([^)]*\)|\s*\[[^]]*\]', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip(" _-")
    article = re.match(r"(.+), (The|A|An)$", name, flags=re.I)
    return article.group(2) + " " + article.group(1) if article else name


def _title_key(name):
    name = _display_title(name)
    name = unicodedata.normalize("NFKD", name.casefold())
    name = "".join(ch for ch in name if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "", name)


def _genre_of(name):
    genre = _classify([name])
    if genre:
        return genre
    lowered = name.casefold().strip()
    if any(word in lowered for word in (
        "educational", "board", "gambling", "casino", "mahjong",
        "card", "music", "rhythm", "party", "pinball", "word game",
    )):
        return "퍼즐/캐주얼"
    return ""


def _read_dat(path):
    with open(path, "rb") as data:
        content = data.read(MAX_DAT_BYTES + 1)
    if len(content) > MAX_DAT_BYTES:
        raise ValueError("Libretro 장르 DB가 허용 크기를 초과했습니다.")
    return content.decode("utf-8-sig", errors="replace")


def _download_dat(system, cache_dir):
    filename = LIBRETRO_FILES[system]
    os.makedirs(cache_dir, exist_ok=True)
    destination = os.path.join(cache_dir, filename)
    if os.path.isfile(destination) and (
        time.time() - os.path.getmtime(destination) < CACHE_SECONDS
    ):
        return _read_dat(destination)
    url = BASE_URL + urllib.parse.quote(filename)
    try:
        req = urllib.request.Request(
            url, headers={
                "User-Agent": "ZipfileViewer/2.2 (https://github.com/WOOSEOK99/zipfileviewer)",
                "Accept": "text/plain",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            binary = response.read(MAX_DAT_BYTES + 1)
        if len(binary) > MAX_DAT_BYTES:
            raise ValueError("다운로드한 Libretro 장르 DB가 너무 큽니다.")
        decoded = binary.decode("utf-8-sig", errors="replace")
        if len(_ENTRY.findall(decoded)) < 50:
            raise ValueError("다운로드한 Libretro 장르 DB 형식이 올바르지 않습니다.")
        temp_name = None
        try:
            with tempfile.NamedTemporaryFile(mode="wb", dir=cache_dir, delete=False) as temp:
                temp_name = temp.name
                temp.write(binary)
            os.replace(temp_name, destination)
        finally:
            if temp_name and os.path.isfile(temp_name):
                os.remove(temp_name)
        return decoded
    except (OSError, ValueError):
        # 이전에 다운로드한 파일이 있으면 오프라인에서도 재사용
        if os.path.isfile(destination):
            return _read_dat(destination)
        raise


@lru_cache(maxsize=8)
def _index(system, cache_dir):
    content = _download_dat(system, cache_dir)
    by_crc = {}
    by_title = {}
    for raw_name, raw_genre, crc in _ENTRY.findall(content):
        title = _display_title(raw_name.replace('\\"', '"'))
        genre = _genre_of(raw_genre.replace('\\"', '"'))
        if not title or not genre:
            continue
        entry = (genre, title)
        by_crc.setdefault(crc.upper(), set()).add(entry)
        key = _title_key(title)
        if key:
            by_title.setdefault(key, set()).add(entry)
    if not by_crc:
        raise ValueError("Libretro 장르 DB에서 게임 항목을 읽지 못했습니다.")
    return by_crc, by_title


def lookup_libretro(title, system, crc=None, cache_dir=None):
    """(genre, DB_game_title, reason, source_url) 반환. 중복 장르가 모호하면 비움."""
    if system not in LIBRETRO_FILES:
        return "", "", "지원하지 않는 Libretro 기종입니다.", ""
    if not cache_dir:
        return "", "", "Libretro 캐시 폴더가 지정되지 않았습니다.", ""
    source = BROWSER_URL + urllib.parse.quote(LIBRETRO_FILES[system])
    try:
        by_crc, by_title = _index(system, os.path.abspath(cache_dir))
    except (OSError, ValueError, UnicodeError) as exc:
        return "", "", "Libretro DB 다운로드/읽기 실패: " + str(exc)[:100], source

    crc_key = f"{crc:08X}" if isinstance(crc, int) else str(crc or "").upper()
    if re.fullmatch(r"[0-9A-F]{8}", crc_key):
        candidates = by_crc.get(crc_key, set())
        if candidates:
            distinct = {genre for genre, _ in candidates}
            if len(distinct) == 1:
                genre, name = sorted(candidates)[0]
                return genre, name, "Libretro ROM CRC32 일치", source
            return "", "", "Libretro에서 동일 CRC의 장르가 충돌합니다.", source

    candidates = by_title.get(_title_key(title), set()) if title else set()
    if candidates:
        distinct = {genre for genre, _ in candidates}
        if len(distinct) == 1:
            genre, name = sorted(candidates)[0]
            return genre, name, "Libretro 영문 제목 일치 (CRC 미일치)", source
        return "", "", "Libretro에서 같은 게임 제목의 장르가 서로 다릅니다.", source
    return "", "", "Libretro에서 CRC32/영문 제목이 일치하는 게임을 찾지 못했습니다.", source
