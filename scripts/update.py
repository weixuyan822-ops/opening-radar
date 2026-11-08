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
# Only links pointing to official event/listing pages are retained; no XHS/X login scraping.
LINK_SIGNALS = re.compile(r'concert|performance|event|activity|ticket|show|product|prodid|공연|콘서트|演唱|音樂|음악', re.I)

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
        for url in urls:
            try:
                html = retrieve(url)
                page = PageLinks()
                page.feed(html)
                successes += 1
                origin_host = urlparse(url).hostname or ''
                added = 0
                for href, title in page.links:
                    final = urljoin(url, href)
                    parsed = urlparse(final)
                    # Keep only same host or subdomains thereof, ordinary web pages.
                    if parsed.scheme != 'https' or not parsed.hostname or not (parsed.hostname == origin_host or parsed.hostname.endswith('.'+origin_host) or origin_host.endswith('.'+parsed.hostname)):
                        continue
                    if not LINK_SIGNALS.search(final+' '+title): continue
                    if final in seen or final.rstrip('/') == url.rstrip('/'): continue
                    if not title or len(title) < 5 or len(title) > 220: continue
                    seen.add(final)
                    rows.append({'platform': platform, 'title': title[:160], 'url': final, 'source_page': url, 'discovered_at': stamp(NOW), 'verification_status': '未核实首次预售时间'})
                    added += 1
                    if added >= 24: break
            except Exception as exc:
                problems.append(f'{type(exc).__name__}: {str(exc)[:65]}')
            time.sleep(0.3)
        if successes:
            statuses[platform] = f'网页读取成功 {successes}/{len(urls)}；候选必须核实开票时间' + ('；部分页面失败' if problems else '')
        else:
            statuses[platform] = f'网页抓取失败（{problems[0] if problems else "未知原因"}）；不能断言暂无演出'
    return rows[:140], statuses

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
        'note': '候选列表可能包含已售票、非演唱会或重复项目。正式榜单仅显示7天内人工复核且首次开票时间尚未到来的记录。'
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(f'Published {len(events)} verified upcoming first onsales; {len(candidates)} unverified webpage candidates')
    for platform, status in coverage.items(): print(f'{platform}: {status}')

if __name__ == '__main__': main()
