"""장르 조회: Wikidata에서 제목과 기종이 모두 확인된 경우에만 자동 분류."""
import json
import re
import urllib.parse
import urllib.request
from functools import lru_cache

GENRES = ("RPG", "격투", "레이싱", "슈팅", "스포츠", "시뮬레이션", "액션", "퀴즈", "퍼즐/캐주얼")
GENRE_EN = {
    "RPG": "RPG", "격투": "Fighting", "레이싱": "Racing",
    "슈팅": "Shooter", "스포츠": "Sports", "시뮬레이션": "Simulation",
    "액션": "Action", "퀴즈": "Quiz", "퍼즐/캐주얼": "Puzzle/Casual",
}
PLATFORM_NAMES = {
    "snes": ("super nintendo", "super famicom", "snes"),
    "nes": ("nintendo entertainment system", "famicom", "nes"),
    "genesis": ("sega genesis", "mega drive", "genesis"),
    "gba": ("game boy advance",),
}
GENRE_RULES = (
    ("RPG", ("role-playing", "role playing", "rpg", "roguelike", "dungeon crawl")),
    ("격투", ("fighting", "versus fighting")),
    ("레이싱", ("racing", "kart")),
    ("슈팅", ("shoot", "gun game", "bullet hell", "run and gun")),
    ("스포츠", ("sport", "soccer", "football", "baseball", "basketball", "golf")),
    ("시뮬레이션", ("simulation", "strategy", "management", "city-building", "city building")),
    ("퀴즈", ("quiz", "trivia")),
    ("퍼즐/캐주얼", ("puzzle", "casual", "board game", "card game", "rhythm", "pinball", "party game")),
    ("액션", ("action", "platform", "adventure", "beat 'em up", "hack and slash")),
)


def _normalized(name):
    return re.sub(r"[^a-z0-9]+", "", name.casefold())


def _api(**params):
    params["format"] = "json"
    params["formatversion"] = "2"
    url = "https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url, headers={"User-Agent": "ZipfileViewer-Editor/2.0 (personal metadata lookup)",
                      "Accept": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=7) as response:
        return json.load(response)


def _entity_ids(claims, prop):
    result = []
    for claim in claims.get(prop, []):
        value = claim.get("mainsnak", {}).get("datavalue", {}).get("value", {})
        if isinstance(value, dict) and value.get("id"):
            result.append(value["id"])
    return result


def _labels(ids):
    if not ids:
        return {}
    payload = _api(action="wbgetentities", ids="|".join(sorted(set(ids))),
                   props="labels", languages="en")
    return {
        key: value.get("labels", {}).get("en", {}).get("value", "")
        for key, value in payload.get("entities", {}).items()
    }


@lru_cache(maxsize=1024)
def lookup_genre(title, system):
    """Return (genre, explanation, source_url); no confident match => empty genre."""
    title = title.strip()
    if not title or system not in PLATFORM_NAMES:
        return "", "영문 제목 또는 지원 기종이 없습니다.", ""
    try:
        search = _api(action="wbsearchentities", language="en",
                      search=title, limit=8, type="item")
        for found in search.get("search", []):
            # 부분 일치/동명의 다른 게임을 장르로 잘못 사용하는 것을 방지
            if _normalized(found.get("label", "")) != _normalized(title):
                continue
            qid = found.get("id", "")
            if not re.fullmatch(r"Q\d+", qid):
                continue
            data = _api(action="wbgetentities", ids=qid,
                        props="labels|descriptions|claims", languages="en")
            entity = data.get("entities", {}).get(qid, {})
            description = entity.get("descriptions", {}).get("en", {}).get("value", "").casefold()
            claims = entity.get("claims", {})
            if "game" not in description and not claims.get("P400"):
                continue
            platform_ids = _entity_ids(claims, "P400")
            genre_ids = _entity_ids(claims, "P136")
            # 플랫폼 속성이 없으면 추측하지 않는다.
            if not platform_ids or not genre_ids:
                continue
            labels = _labels(platform_ids + genre_ids)
            platforms = [labels.get(item, "").casefold() for item in platform_ids]
            if not any(
                token in platform for platform in platforms
                for token in PLATFORM_NAMES[system]
            ):
                continue
            source = "https://www.wikidata.org/wiki/" + qid
            genre_labels = [labels.get(item, "").casefold() for item in genre_ids]
            for chosen, keywords in GENRE_RULES:
                if any(word in label for label in genre_labels for word in keywords):
                    return chosen, "Wikidata 기종·장르 확인", source
            return "", "기종은 일치하지만 9종 장르로 변환할 수 없습니다.", source
        return "", "Wikidata에서 제목·기종·장르의 일치를 확인하지 못했습니다.", ""
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return "", "인터넷 조회 실패: " + str(exc)[:100], ""
