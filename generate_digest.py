import html
import json
import re
import socket
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime, parsedate_to_datetime
from pathlib import Path
from xml.etree.ElementTree import Element, ElementTree, SubElement, indent

try:
    import feedparser
except ModuleNotFoundError:
    print("Error: the feedparser package is not installed.")
    print("Install it with: python3 -m pip install feedparser")
    raise SystemExit(1)


SOURCES_FILE = Path("sources.json")
DIGEST_FILE = Path("digest.xml")
ARCHIVES_DIR = Path("archives")
RSS_TITLE = "Canadian Health Monitor"
RSS_DESCRIPTION = (
    "Weekly Canadian EMR, EHR, digital health, privacy, cybersecurity, CIHI, "
    "Infoway, and regulatory updates."
)
RSS_LINK = "https://example.com/digest.xml"
DAYS_BACK = 14
TOP_MATCH_LIMIT = 25
REQUEST_TIMEOUT_SECONDS = 15
REQUEST_HEADERS = {
    "User-Agent": "CanadianHealthMonitor/0.1 (+https://example.com/rss-check)"
}
STRONG_TOPIC_KEYWORDS = [
    "EMR",
    "EHR",
    "electronic medical record",
    "electronic health record",
    "digital health",
    "CIHI",
    "Infoway",
    "Canada Health Infoway",
    "interoperability",
    "FHIR",
    "HL7",
    "SNOMED",
    "e-prescribing",
    "PrescribeIT",
    "patient portal",
    "health data",
    "health information",
]
REGULATORY_CYBER_PRIVACY_KEYWORDS = [
    "regulatory",
    "regulation",
    "privacy",
    "PIPEDA",
    "Privacy Act",
    "cybersecurity",
    "cyber security",
    "ransomware",
    "data breach",
]
HEALTH_CONTEXT_KEYWORDS = [
    "health",
    "healthcare",
    "hospital",
    "clinic",
    "patient",
    "medical",
    "digital health",
    "health data",
    "health information",
    "EMR",
    "EHR",
]

socket.setdefaulttimeout(REQUEST_TIMEOUT_SECONDS)


def clean_text(text):
    if not text:
        return ""

    text_without_tags = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text_without_tags).strip()


def keyword_matches(text, keyword):
    if len(keyword) <= 4 and keyword.replace("-", "").isalnum():
        pattern = r"\b" + re.escape(keyword) + r"\b"
        return re.search(pattern, text, re.IGNORECASE) is not None

    return keyword.lower() in text.lower()


def choose_keywords(configured_keywords, requested_keywords):
    configured_by_lowercase = {
        keyword.lower(): keyword for keyword in configured_keywords
    }
    chosen_keywords = []

    for keyword in requested_keywords:
        chosen_keywords.append(configured_by_lowercase.get(keyword.lower(), keyword))

    return chosen_keywords


def unique_keywords(keywords):
    unique = []

    for keyword in keywords:
        if keyword not in unique:
            unique.append(keyword)

    return unique


def find_matching_keywords(title, summary, keywords):
    text_to_check = f"{title} {summary}"
    matches = []

    for keyword in keywords:
        if keyword_matches(text_to_check, keyword):
            matches.append(keyword)

    return matches


def find_relevant_keywords(title, summary, keyword_groups):
    strong_matches = find_matching_keywords(
        title, summary, keyword_groups["strong_topics"]
    )
    regulatory_matches = find_matching_keywords(
        title, summary, keyword_groups["regulatory_cyber_privacy"]
    )
    context_matches = find_matching_keywords(
        title, summary, keyword_groups["health_context"]
    )

    if strong_matches:
        return unique_keywords(strong_matches)

    if regulatory_matches and context_matches:
        return unique_keywords(regulatory_matches + context_matches)

    return []


def load_sources():
    try:
        with SOURCES_FILE.open("r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        print("Error: sources.json was not found.")
        print("Make sure sources.json is in the same folder as generate_digest.py.")
        return None
    except json.JSONDecodeError as error:
        print("Error: sources.json is not valid JSON.")
        print(f"Problem near line {error.lineno}, column {error.colno}: {error.msg}")
        return None


def get_item_summary(item):
    summary = item.get("summary", "")

    if not summary:
        summary = item.get("description", "")

    return clean_text(summary)


def get_item_published_datetime(item):
    parsed_date = item.get("published_parsed") or item.get("updated_parsed")

    if parsed_date:
        return datetime(*parsed_date[:6], tzinfo=timezone.utc)

    published_text = item.get("published") or item.get("updated")
    if not published_text:
        return None

    try:
        parsed_text_date = parsedate_to_datetime(published_text)
        if parsed_text_date.tzinfo is None:
            parsed_text_date = parsed_text_date.replace(tzinfo=timezone.utc)
        return parsed_text_date.astimezone(timezone.utc)
    except (TypeError, ValueError):
        pass

    for date_format in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(published_text, date_format).replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            pass

    return None


def get_item_published_label(item):
    return item.get("published") or item.get("updated") or "Unknown date"


def is_recent(published_datetime):
    if published_datetime is None:
        return False

    cutoff = datetime.now(timezone.utc) - timedelta(days=DAYS_BACK)
    return published_datetime >= cutoff


def fetch_matched_items(source, keyword_groups):
    name = source.get("name", "Unnamed source")
    feed_url = source.get("feed_url")
    matched_items = []
    checked_count = 0

    if not feed_url:
        print(f"{name}: no feed URL found. Skipping this source.")
        return matched_items, checked_count

    try:
        feed = feedparser.parse(feed_url, request_headers=REQUEST_HEADERS)
    except Exception as error:
        print(f"{name}: could not fetch this feed: {error}")
        return matched_items, checked_count

    status = feed.get("status")
    if status and status >= 400:
        print(f"{name}: could not fetch this feed. HTTP status: {status}")
        return matched_items, checked_count

    items = feed.get("entries", [])
    if feed.get("bozo") and not items:
        print(f"{name}: could not read this feed: {feed.bozo_exception}")
        return matched_items, checked_count

    if feed.get("bozo"):
        print(f"{name}: warning: feedparser noticed a problem: {feed.bozo_exception}")

    if not items:
        print(f"{name}: no items found for this feed.")
        return matched_items, checked_count

    for item in items:
        checked_count += 1
        published_datetime = get_item_published_datetime(item)

        if not is_recent(published_datetime):
            continue

        title = clean_text(item.get("title", "Untitled item"))
        summary = get_item_summary(item)
        matching_keywords = find_relevant_keywords(title, summary, keyword_groups)

        if not matching_keywords:
            continue

        link = item.get("link")
        matched_items.append(
            {
                "title": title,
                "source": name,
                "published_datetime": published_datetime,
                "published_label": get_item_published_label(item),
                "keywords": matching_keywords,
                "link": link,
            }
        )

    return matched_items, checked_count


def collect_matched_items(sources, keyword_groups):
    all_matches = []
    total_checked = 0

    for source in sources:
        matched_items, checked_count = fetch_matched_items(source, keyword_groups)
        all_matches.extend(matched_items)
        total_checked += checked_count

    all_matches.sort(key=lambda item: item["published_datetime"], reverse=True)
    return all_matches, total_checked


def print_matched_items(matched_items, total_checked):
    limited_items = matched_items[:TOP_MATCH_LIMIT]

    print()
    print("Matched items")
    print("-------------")
    print(f"Total feed items checked: {total_checked}")
    print(f"Matched before top-{TOP_MATCH_LIMIT} limit: {len(matched_items)}")
    print()

    if not matched_items:
        print("No matched items found.")
        return

    for number, item in enumerate(limited_items, start=1):
        keywords = ", ".join(item["keywords"])
        link = item["link"] or "No link available"

        print(f"{number}. {item['title']}")
        print(f"   Source: {item['source']}")
        print(f"   Published: {item['published_label']}")
        print(f"   Matching keywords: {keywords}")
        print(f"   Link: {link}")
        print()


def add_text_element(parent, tag_name, text):
    element = SubElement(parent, tag_name)
    element.text = text or ""
    return element


def build_item_description(item):
    keywords = ", ".join(item["keywords"])
    description_lines = [
        f"Source: {item['source']}",
        f"Matched keywords: {keywords}",
    ]

    if item["published_label"] != "Unknown date":
        description_lines.append(f"Published: {item['published_label']}")

    return "\n".join(description_lines)


def add_rss_item(channel, item):
    rss_item = SubElement(channel, "item")
    link = item["link"] or ""

    add_text_element(rss_item, "title", item["title"])
    add_text_element(rss_item, "link", link)
    add_text_element(rss_item, "description", build_item_description(item))

    if item["published_datetime"]:
        add_text_element(rss_item, "pubDate", format_datetime(item["published_datetime"]))

    guid = link or f"{item['source']} - {item['title']}"
    guid_element = add_text_element(rss_item, "guid", guid)
    guid_element.set("isPermaLink", "true" if link else "false")


def add_no_updates_item(channel):
    rss_item = SubElement(channel, "item")
    message = "No relevant Canadian health monitor updates found this week."

    add_text_element(rss_item, "title", message)
    add_text_element(rss_item, "description", message)
    guid_element = add_text_element(rss_item, "guid", "no-updates-this-week")
    guid_element.set("isPermaLink", "false")


def create_digest_xml(matched_items):
    rss = Element("rss", {"version": "2.0"})
    channel = SubElement(rss, "channel")

    add_text_element(channel, "title", RSS_TITLE)
    add_text_element(channel, "link", RSS_LINK)
    add_text_element(channel, "description", RSS_DESCRIPTION)
    add_text_element(channel, "language", "en-ca")
    add_text_element(channel, "lastBuildDate", format_datetime(datetime.now(timezone.utc)))

    if matched_items:
        for item in matched_items:
            add_rss_item(channel, item)
    else:
        add_no_updates_item(channel)

    indent(rss, space="  ")
    ElementTree(rss).write(DIGEST_FILE, encoding="utf-8", xml_declaration=True)

    return len(matched_items) if matched_items else 1


def markdown_link(title, link):
    if link:
        return f"[{title}]({link})"

    return title


def create_markdown_archive(matched_items, total_checked):
    ARCHIVES_DIR.mkdir(exist_ok=True)

    now = datetime.now(timezone.utc)
    archive_file = ARCHIVES_DIR / f"{now.date().isoformat()}-digest.md"
    limited_items = matched_items[:TOP_MATCH_LIMIT]
    lines = [
        "# Weekly Canadian Health Monitor Digest",
        "",
        f"Date generated: {now.strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        f"Total feed items checked: {total_checked}",
        f"Matched item count: {len(matched_items)}",
        "",
        "## Top updates",
        "",
    ]

    if not matched_items:
        lines.append("No relevant Canadian health monitor updates found this week.")
    else:
        for number, item in enumerate(limited_items, start=1):
            keywords = ", ".join(item["keywords"])
            link = item["link"] or ""

            lines.extend(
                [
                    f"### {number}. {item['title']}",
                    "",
                    f"- Source: {item['source']}",
                    f"- Published: {item['published_label']}",
                    f"- Matched keywords: {keywords}",
                    f"- Link: {markdown_link(link or 'No link available', link)}",
                    "",
                ]
            )

    archive_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return archive_file


def build_keyword_groups(configured_keywords):
    return {
        "strong_topics": choose_keywords(configured_keywords, STRONG_TOPIC_KEYWORDS),
        "regulatory_cyber_privacy": choose_keywords(
            configured_keywords, REGULATORY_CYBER_PRIVACY_KEYWORDS
        ),
        "health_context": choose_keywords(configured_keywords, HEALTH_CONTEXT_KEYWORDS),
    }


def main():
    data = load_sources()

    if data is None:
        return

    sources = data.get("sources", [])

    if not sources:
        print("No feeds found in sources.json.")
        return

    keywords = data.get("keywords", {}).get("priority", [])
    if not keywords:
        print("No keywords found in sources.json.")
        return

    keyword_groups = build_keyword_groups(keywords)
    matched_items, total_checked = collect_matched_items(sources, keyword_groups)
    print_matched_items(matched_items, total_checked)
    item_count = create_digest_xml(matched_items)
    print(f"Created digest.xml with {item_count} item(s).")
    archive_file = create_markdown_archive(matched_items, total_checked)
    print(f"Created Markdown archive: {archive_file}")


if __name__ == "__main__":
    main()
