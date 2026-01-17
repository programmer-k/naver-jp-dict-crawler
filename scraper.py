import argparse
import time
import os
import csv
from typing import List, Dict
from playwright_helpers import BrowserContext, load_jlpt_page, discover_pos_buttons, click_pos_button, wait_for_list
from output_utils import write_csv, sanitize_filename


def extract_items_from_page(page) -> List[Dict[str, str]]:
    # Return list item elements (links) to be resolved via detail pages.
    candidates = [".component_keyword > li", "ul.list > li", "ul.word_list > li", "div.list li", "div.result_list li", "li.item"]
    items = []
    for sel in candidates:
        els = page.query_selector_all(sel)
        if not els:
            continue
        for e in els:
            try:
                a = e.query_selector('a')
                href = a.get_attribute('href') if a else ''
                # short label (first line) to help debug
                text = e.inner_text().strip().splitlines()
                label = text[0].strip() if text else ''
                items.append({'label': label, 'href': href})
            except Exception:
                continue
        if items:
            break
    return items


def fetch_entry_detail(browser_ctx: BrowserContext, href: str) -> Dict[str, str]:
    """Open a detail entry (hash href) and extract japanese, reading, korean meaning."""
    page = browser_ctx.new_page()
    try:
        full = href if href.startswith('http') else ('https://ja.dict.naver.com/' + href.lstrip('/'))
        page.goto(full, wait_until='domcontentloaded')
        time.sleep(0.6)
        # japanese (prefer kanji if present) and reading (kana)
        jap = ''
        reading = ''
        kanji_el = page.query_selector('strong.word._kanji')
        kana_el = page.query_selector('strong.word:not(._kanji)') or page.query_selector('strong.word') or page.query_selector('.word')
        try:
            if kanji_el:
                # kanji text may be like '[宛·充て]'; clean brackets
                raw = kanji_el.inner_text().strip()
                jap = raw.replace('[', '').replace(']', '')
            if kana_el:
                reading = kana_el.inner_text().strip()
                if not jap:
                    jap = reading
        except Exception:
            pass
        # fallback: any rt near headword (if reading not found)
        if not reading:
            el = kana_el or kanji_el
            if el:
                try:
                    reading = el.evaluate("e => { const r = e.parentElement && e.parentElement.querySelector('rt'); if(r) return r.textContent.trim(); const sec = e.closest('.section'); return sec && sec.querySelector('rt') ? sec.querySelector('rt').textContent.trim() : ''; }")
                except Exception:
                    reading = ''
        # korean meaning
        kor = ''
        for sel in ['.mean', '.meaning', '.mean_list', '.fnt_kor']:
            el = page.query_selector(sel)
            if el:
                kor = el.inner_text().strip()
                if kor:
                    break
        return {'japanese': jap, 'reading': reading, 'korean': kor, 'source_url': full}
    finally:
        try:
            page.context.close()
        except Exception:
            pass


def paginate_click_next(page) -> bool:
    # try to find a next button
    for sel in ["a.next", "button.next", "a[aria-label='次へ']", "a[aria-label='Next']"]:
        btn = page.query_selector(sel)
        if btn:
            try:
                btn.click()
                time.sleep(0.7)
                return True
            except Exception:
                continue
    # try pagination area
    pagelinks = page.query_selector_all('ul.pagination li a')
    if pagelinks:
        # find current and then next
        for i, a in enumerate(pagelinks):
            cls = a.get_attribute('class') or ''
            if 'active' in cls:
                if i + 1 < len(pagelinks):
                    try:
                        pagelinks[i + 1].click()
                        time.sleep(0.7)
                        return True
                    except Exception:
                        return False
    return False


def normalize_pos_label(raw: str) -> str:
    m = {
        '전체': 'all', '명사': 'noun', '동사': 'verb', '형용사': 'adj', '부사': 'adv',
        '조사': 'particle', '대명사': 'pronoun', '접사': 'affix', '감동사': 'interj', '형용동사': 'na_adj',
        '기타': 'other'
    }
    if not raw:
        return 'all'
    raw = raw.strip()
    return m.get(raw, ''.join(c if c.isalnum() else '_' for c in raw))


def scrape_level_pos(browser_ctx: BrowserContext, level: int, pos_label_click: str, pos_label_name: str, out_dir: str, max_pages: int = 200):
    page = browser_ctx.new_page()
    load_jlpt_page(page, level)
    # discover pos controls
    if pos_label_click and pos_label_click not in ('all', '전체'):
        click_pos_button(page, pos_label_click)
    wait_for_list(page)
    rows = []
    page_count = 0
    while True:
        page_count += 1
        if page_count > max_pages:
            break
        items = extract_items_from_page(page)
        for it in items:
            href = it.get('href') or ''
            if not href:
                continue
            detail = fetch_entry_detail(browser_ctx, href)
            detail.update({'level': f'N{level}', 'pos': pos_label_name})
            rows.append(detail)
        # try to go next
        moved = paginate_click_next(page)
        if not moved:
            break
        wait_for_list(page)
    fname = f"N{level}_{sanitize_filename(pos_label_name)}.csv"
    path = os.path.join(out_dir, fname)
    headers = ['level', 'pos', 'japanese', 'reading', 'korean', 'source_url']
    write_csv(path, rows, headers)
    page.context.close()
    return path, len(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--levels', default='1', help='Comma separated levels 1..5')
    parser.add_argument('--pos', default='all', help='POS label to filter or "all"')
    parser.add_argument('--out-dir', default='outputs', help='Output directory')
    args = parser.parse_args()

    levels = [int(x.strip()) for x in args.levels.split(',') if x.strip()]
    pos_arg = args.pos
    os.makedirs(args.out_dir, exist_ok=True)

    with BrowserContext(headless=True) as ctx:
        # open an exploratory page to discover POS labels if "all"
        p = ctx.new_page()
        load_jlpt_page(p, levels[0])
        all_pos = discover_pos_buttons(p)
        p.context.close()
        pos_list = []
        if pos_arg == 'all':
            if all_pos:
                pos_list = [(k, normalize_pos_label(k)) for k in all_pos.keys()]
            else:
                pos_list = [('all', 'all')]
        else:
            pos_list = [(pos_arg, normalize_pos_label(pos_arg))]

        results = []
        for level in levels:
            for pos_click, pos_name in pos_list:
                print(f"Scraping level N{level} pos={pos_click} (file label={pos_name})...")
                path, count = scrape_level_pos(ctx, level, pos_click, pos_name, args.out_dir)
                print(f"Saved {count} rows to {path}")
                results.append({'level': level, 'pos': pos_name, 'path': path, 'count': count})

    print("Done. Summary:")
    for r in results:
        print(r)


if __name__ == '__main__':
    main()
