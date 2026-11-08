#!/usr/bin/env python3
"""Opening Radar: scrape public HTML pages, NO API keys or ticketing APIs.

Be conservative: scraped links are only candidates. A human-vetted official
first-presale announcement can enter data/verified_events.json with verification
metadata. The publication always drops events after their first sale timestamp.
Never bypass access controls, bot challenges, login, or rate limits.
"""
import datetime as dt
import json
import re
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / 'data' / 'events.json'
VERIFIED = ROOT / 'data' / 'verified_events.json'
NOW = dt.datetime.now(dt.timezone.utc)
END = NOW + dt.timedelta(days=90)

# Pages are public event directories, not APIs. Links and markup may change.
SOURCES = {
    'Ticketmaster SG': ['https://ticketmaster.sg/activity/latest/Singapore', 'https://ticketmaster.sg/activity?type=table'],
    'Ticketmaster AU': ['https://www.ticketmaster.com.au/discover/concerts'],
    'ThaiTicketMajor': ['https://www.thaiticketmajor.com/concert/', 'https://www.thaiticketmajor.com/concert/latest/'],
    'HK Ticketing': ['https://hkt.hkticketing.com/hant/allEvents/detail'],
    'Cityline': ['https://shows.cityline.com/', 'https://www.cityline.com/'],
    'Interpark / NOL': ['https://nol.yanolja.com/ticket/display/ranking/concert'],
    'Melon Ticket': ['https://ticket.melon.com/main/index.htm'],
}
# Conservative event-detail URL patterns. Generic home/category/search pages must
# never become an event candidate, even if their text contains "concert".
DETAIL_PATHS = {
    'Ticketmaster SG': re.compile(r'^/activity/detail/[a-z0-9_-]+/?$', re.I),
    'Ticketmaster AU': re.compile(r'^/(?:event/[^/]+|[^/]+/event/[0-9A-Za-z]+|[^/]+-tickets/[^/]+/event/[0-9A-Za-z]+|[^/]+-tickets/artist/\d+)/?$', re.I),
    'ThaiTicketMajor': re.compile(r'^/(?:concert|performance)/[a-z0-9][a-z0-9_-]*\.html$', re.I),
    'HK Ticketing': re.compile(r'^/(?:hant|eng|en)/(?:allEvents|events)/detail/(?:[^/?]+)', re.I),
    'Cityline': re.compile(r'^/(?:tc|en|sc|zh|hk)/20\d\d/[^/]+\.html$', re.I),
    'Interpark / NOL': re.compile(r'^/ticket/products/\d+/?$', re.I),
    'Melon Ticket': re.compile(r'^/performance/index\.htm$', re.I),
}
NAV_LABELS = re.compile(r'^(concerts?|events?|tickets?|performances?|music|shows?|latest|all events|view all|more|details?|buy tickets?|book now|演唱会|演唱會|音乐|音樂|票务|票務|更多|全部|공연|콘서트|예매|전체|詳細|詳情)$', re.I)
BAD_LABEL = re.compile(r'home\s*page|首页|首頁|分類|分类|search|signin|login|register|FAQ|privacy|terms|cookie|help|about us|accessibility', re.I)
# Avoid trusting URL keywords as evidence of a concert.
PERFORMANCE_HINT = re.compile(r'concert|world tour|live(?:\s+in|\s+tour|\s+20\d\d)|fanmeeting|fan meeting|showcase|recital|演唱会|演唱會|音乐会|音樂會|巡演|演奏会|공연|콘서트|팬미팅|라이브|ทัวร์|คอนเสิร์ต', re.I)

def is_detail_url(platform, final):
    parsed = urlparse(final)
    if not DETAIL_PATHS[platform].fullmatch(parsed.path):
        return False
    if platform == 'Melon Ticket':
        return bool(re.search(r'(?:^|&)prodId=\d+(?:&|$)', parsed.query, re.I))
    return True

def candidate_title(raw):
    title = re.sub(r'\s+', ' ', raw).strip(' -|\u2022\u00b7')
    return title if 9 <= len(title) <= 160 and not NAV_LABELS.fullmatch(title) and not BAD_LABEL.search(title) else None

def parse_time(value):
    try:
        d = dt.datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return d.astimezone(dt.timezone.utc) if d.tzinfo else None
    except (TypeError, ValueError):
        return None

def stamp(value):
    return value.isoformat(timespec='seconds').replace('+00:00', 'Z')

class PageLinks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links, self.href, self.parts, self.depth = [], None, [], 0
        self.page_title, self.in_title = '', False
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'title': self.in_title = True
        if tag == 'a':
            self.href = a.get('href', '')
            self.parts = [a.get('title', ''), a.get('aria-label', '')]
            self.depth += 1
    def handle_data(self, data):
        if self.in_title: self.page_title += data
        if self.href is not None: self.parts.append(data)
    def handle_endtag(self, tag):
        if tag == 'title': self.in_title = False
        if tag == 'a' and self.href is not None:
            self.links.append((self.href, re.sub(r'\s+', ' ', ' '.join(self.parts)).strip()))
            self.href, self.parts = None, []

def retrieve(url):
    req = Request(url, headers={
        'User-Agent': 'OpeningRadar/1.1 (+public concert listings; no login or bypass)',
        'Accept': 'text/html,application/xhtml+xml',
    })
    with urlopen(req, timeout=18) as resp:
        content_type = resp.headers.get('Content-Type', '')
        if 'html' not in content_type.lower():
            raise ValueError('Non-HTML response')
        body = resp.read(1_500_000)
        charset = resp.headers.get_content_charset() or 'utf-8'
        return body.decode(charset, errors='replace')

def candidate_pages():
    rows, statuses = [], {}
    for platform, urls in SOURCES.items():
        successes, problems, seen = 0, [], set()
        found = []
        for url in urls:
            try:
                html = retrieve(url)
                page = PageLinks()
                page.feed(html)
                successes += 1
                origin_host = urlparse(url).hostname or ''
                for href, label in page.links:
                    final = urljoin(url, href).split('#', 1)[0]
                    parsed = urlparse(final)
                    if parsed.scheme != 'https' or not parsed.hostname or not (parsed.hostname == origin_host or parsed.hostname.endswith('.'+origin_host) or origin_host.endswith('.'+parsed.hostname)):
                        continue
                    if not is_detail_url(platform, final):
                        continue
                    if final in seen:
                        continue
                    seen.add(final)
                    # A detail URL alone isn't sufficient; verify the target HTML.
                    found.append((final, label, url))
            except Exception as exc:
                problems.append(f'{type(exc).__name__}: {str(exc)[:65]}')
            time.sleep(0.3)
        validated = 0
        # Limit request volume per domain; be polite to public ticketing sites.
        for final, link_label, directory in found[:12]:
            try:
                html = retrieve(final)
                page = PageLinks()
                page.feed(html)
                html_title = re.sub(r'\s+', ' ', page.page_title).strip()
                title = candidate_title(link_label) or candidate_title(re.sub(r'\s*[-|]\s*(?:Ticketmaster|ThaiTicketMajor|Cityline|Melon Ticket|Interpark|NOL).*$', '', html_title, flags=re.I))
                if not title:
                    continue
                # At least one human-readable text field must indicate a show.
                if not PERFORMANCE_HINT.search(title + ' ' + html_title):
                    continue
                # Explicitly reject common portals/categories even if templates mention tours.
                if BAD_LABEL.search(title):
                    continue
                rows.append({'platform': platform, 'title': title, 'url': final, 'source_page': directory, 'discovered_at': stamp(NOW), 'verification_status': '演出详情页已识别；首次预售时间仍待核实'})
                validated += 1
            except Exception as exc:
                problems.append(f'详情页: {type(exc).__name__}')
            time.sleep(0.3)
        if successes:
            statuses[platform] = f'目录读取 {successes}/{len(urls)}；识别具体演出详情 {validated} 条' + ('；部分页面不可访问' if problems else '')
        else:
            statuses[platform] = f'网页读取失败（{problems[0] if problems else "未知原因"}）；不能断言暂无演出'
    # Newly discovered candidates are NOT certified as never-on-sale.
    return rows[:90], statuses

def verified_records():
    try:
        records = json.loads(VERIFIED.read_text(encoding='utf-8'))
        if not isinstance(records, list): return [], ['核实文件不是数组']
    except (OSError, ValueError) as exc:
        return [], [f'核实文件读取错误: {type(exc).__name__}']
    found, rejected = [], []
    for record in records:
        first = parse_time(record.get('first_sale_utc'))
        verified_at = parse_time(record.get('verified_at')) if 'T' in str(record.get('verified_at', '')) else parse_time(str(record.get('verified_at', ''))+'T00:00:00Z')
        if not (record.get('verified') is True and first and NOW < first <= END and verified_at and NOW-verified_at < dt.timedelta(days=7) and record.get('official_url','').startswith('https://') and record.get('platform') in SOURCES and record.get('artist') and record.get('verification')):
            rejected.append(str(record.get('artist', record.get('id','unknown'))))
            continue
        found.append(record)
    return found, rejected

def main():
    events, rejected = verified_records()
    candidates, coverage = candidate_pages()
    result = {
        'generated_at': stamp(NOW),
        'policy': 'Public HTML only. First presale must be manually verified; next 90 days.',
        'events': sorted(events, key=lambda r: r['first_sale_utc']),
        'candidates': candidates,
        'coverage': coverage,
        'rejected_verified': len(rejected),
        'note': '候选已限定具体演出详情页且检查标题，但仍可能已开票；正式榜单仅显示7天内人工复核且首次开票尚未开始的记录。'
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(f'Published {len(events)} verified upcoming first onsales; {len(candidates)} unverified webpage candidates')
    for platform, status in coverage.items(): print(f'{platform}: {status}')

if __name__ == '__main__': main()
