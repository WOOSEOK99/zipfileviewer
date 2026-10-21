"""영문 게임명으로 장르를 확인한다. Wikidata → 영어 Wikipedia 게임 정보표."""
import html
import json
import re
import unicodedata
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
    "snes": ("super nintendo entertainment system", "super nintendo", "super famicom", "super nes", "snes"),
    "nes": ("nintendo entertainment system", "famicom", "nes"),
    "genesis": ("sega genesis", "sega mega drive", "mega drive", "genesis"),
    "gba": ("game boy advance", "gba"),
}
GENRE_RULES = (
    ("RPG", ("role-playing", "role playing", "rpg", "roguelike", "dungeon crawl", "tactical role")),
    ("격투", ("fighting", "versus fighting", "one-on-one fighter")),
    ("레이싱", ("racing", "kart")),
    ("슈팅", ("shoot", "gun game", "bullet hell", "run and gun")),
    ("스포츠", ("sport", "soccer", "football", "baseball", "basketball", "golf", "tennis")),
    ("시뮬레이션", ("simulation", "strategy", "management", "city-building", "city building")),
    ("퀴즈", ("quiz", "trivia")),
    ("퍼즐/캐주얼", ("puzzle", "casual", "board game", "card game", "rhythm", "pinball", "party game")),
    ("액션", ("action", "platform", "adventure", "beat 'em up", "beat 'em", "hack and slash")),
)


def _normalized(name):
    name = unicodedata.normalize("NFKD", name.casefold())
    name = "".join(char for char in name if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "", name)


def _clean_wiki_title(title):
    return re.sub(r"\s+\((?:\d{4}\s+)?(?:video\s+)?game\)$", "", title, flags=re.I)


def _request(host, **params):
    params["format"] = "json"
    params["formatversion"] = "2"
    url = "https://" + host + "/w/api.php?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "ZipfileViewer/2.1 (https://github.com/WOOSEOK99/zipfileviewer)",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=7) as response:
        return json.load(response)


def _entity_ids(claims, prop):
    result = []
    for claim in claims.get(prop, []):
        if claim.get("rank") == "deprecated":
            continue
        value = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
        if isinstance(value, dict) and value.get("id"):
            result.append(value["id"])
    return result


@lru_cache(maxsize=256)
def _labels(identifiers):
    if not identifiers:
        return {}
    result = {}
    ids = sorted(set(identifiers))
    for start in range(0, len(ids), 40):
        response = _request(
            "www.wikidata.org", action="wbgetentities",
            ids="|".join(ids[start:start + 40]),
            props="labels", languages="en",
        )
        result.update({
            key: item.get("labels", {}).get("en", {}).get("value", "")
            for key, item in response.get("entities", {}).items()
        })
    return result


def _platform_matches(text, system):
    lowered = unicodedata.normalize("NFKC", text).casefold()
    return any(
        re.search(r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])", lowered)
        for alias in PLATFORM_NAMES[system]
    )


def _classify(raw_genres):
    genres = [re.sub(r"\s+", " ", item.casefold().replace("–", "-")) for item in raw_genres]
    for chosen, keywords in GENRE_RULES:
        if any(word in genre for genre in genres for word in keywords):
            return chosen
    return ""


def _html_text(fragment):
    fragment = re.sub(r"<(?:script|style|sup)\b[^>]*>.*?</(?:script|style|sup)>", " ", fragment, flags=re.I | re.S)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


@lru_cache(maxsize=512)
def _wikipedia_infobox(title):
    """Return infobox fields only when the resolved Wikipedia title matches."""
    if not title:
        return None
    payload = _request(
        "en.wikipedia.org", action="parse", page=title,
        prop="text", section=0, redirects=1,
    ).get("parse", {})
    page_title = payload.get("title", "")
    if _normalized(_clean_wiki_title(page_title)) != _normalized(_clean_wiki_title(title)):
        return None
    markup = payload.get("text", "")
    # Only the infobox near the article beginning is relevant.
    begin = re.search(r"<table\b[^>]*class=[\"'][^\"']*\binfobox\b", markup[:50000], flags=re.I)
    if not begin:
        return None
    excerpt = markup[begin.start():begin.start() + 32000]
    fields = {}
    for match in re.finditer(r"<tr\b[^>]*>(.*?)</tr\s*>", excerpt, flags=re.I | re.S):
        segment = match.group(1)
        th = re.search(r"<th\b[^>]*>(.*?)</th\s*>", segment, flags=re.I | re.S)
        td = re.search(r"<td\b[^>]*>(.*?)</td\s*>", segment, flags=re.I | re.S)
        if not (th and td):
            continue
        heading = re.sub(r"[^a-z]", "", _html_text(th.group(1)).casefold())
        if heading in ("genre", "genres", "platform", "platforms"):
            fields["genre" if heading.startswith("genre") else "platform"] = _html_text(td.group(1))
        if len(fields) == 2:
            break
    return fields or None


def _wikipedia_url(title):
    return "https://en.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_"))


def _wikidata_matches(title):
    search = _request(
        "www.wikidata.org", action="wbsearchentities",
        search=title, language="en", type="item", limit=18,
    )
    ids = [result.get("id", "") for result in search.get("search", [])]
    ids = list(dict.fromkeys(qid for qid in ids if re.fullmatch(r"Q\d+", qid)))
    if not ids:
        return []
    data = _request(
        "www.wikidata.org", action="wbgetentities", ids="|".join(ids),
        props="labels|aliases|descriptions|claims|sitelinks",
        sitefilter="enwiki", languages="en",
    ).get("entities", {})
    matches = []
    for qid in ids:
        item = data.get(qid, {})
        label = item.get("labels", {}).get("en", {}).get("value", "")
        aliases = [alias.get("value", "") for alias in item.get("aliases", {}).get("en", [])]
        wiki_title = item.get("sitelinks", {}).get("enwiki", {}).get("title", "")
        names = [label, *aliases, _clean_wiki_title(wiki_title)]
        if not any(_normalized(name) == _normalized(title) for name in names if name):
            continue
        description = item.get("descriptions", {}).get("en", {}).get("value", "").casefold()
        claims = item.get("claims", {})
        if "game" not in description and not claims.get("P400"):
            continue
        matches.append((qid, claims, wiki_title))
    return matches


@lru_cache(maxsize=2048)
def lookup_genre(title, system):
    """Return (genre, reason, source_url); uncertain classification remains empty."""
    title = title.strip()
    system = system.strip().lower()
    if not title or system not in PLATFORM_NAMES:
        return "", "영문 제목 또는 지원 기종이 없습니다.", ""

    explanations = []
    try:
        candidates = _wikidata_matches(title)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        candidates = []
        explanations.append("Wikidata 조회 실패: " + str(exc)[:70])

    # Different editions with the same name must never borrow another console's genre.
    for qid, claims, wiki_title in candidates:
        platform_ids = _entity_ids(claims, "P400")
        genre_ids = _entity_ids(claims, "P136")
        try:
            labels = _labels(tuple(sorted(set(platform_ids + genre_ids))))
        except (OSError, ValueError, TypeError, KeyError) as exc:
            explanations.append("Wikidata 속성 조회 실패: " + str(exc)[:70])
            labels = {}
        wd_platforms = [labels.get(item, "") for item in platform_ids]
        wd_genres = [labels.get(item, "") for item in genre_ids]
        wd_matches = any(_platform_matches(value, system) for value in wd_platforms)
        genre = _classify(wd_genres)
        wiki_info = None
        if wiki_title and (not genre or not wd_matches):
            try:
                wiki_info = _wikipedia_infobox(wiki_title)
            except (OSError, ValueError, TypeError, KeyError):
                pass
        wp_matches = bool(wiki_info and _platform_matches(wiki_info.get("platform", ""), system))
        if platform_ids and wd_platforms and not (wd_matches or wp_matches):
            # Explicitly incompatible platform metadata: skip.
            continue
        if not genre and wiki_info:
            genre = _classify([wiki_info.get("genre", "")])
        if not genre:
            continue
        url = _wikipedia_url(wiki_title) if wiki_info and wiki_title else "https://www.wikidata.org/wiki/" + qid
        if wd_matches or wp_matches:
            return genre, "영문명·기종 확인 (Wikidata/영어 Wikipedia)", url
        return genre, "영문명·장르 확인, 기종 정보 없음 (확인 권장)", url

    # Wikipedia infobox fallback for titles not fully catalogued in Wikidata.
    for page in dict.fromkeys((title, title + " (video game)")):
        try:
            fields = _wikipedia_infobox(page)
        except (OSError, ValueError, TypeError, KeyError):
            continue
        if not fields or not _platform_matches(fields.get("platform", ""), system):
            continue
        genre = _classify([fields.get("genre", "")])
        if genre:
            return genre, "영어 Wikipedia 게임 정보표의 기종·장르 확인", _wikipedia_url(page)

    note = " / ".join(explanations[:2])
    return "", ("장르 근거를 확인할 수 없습니다. " + note).strip(), ""
