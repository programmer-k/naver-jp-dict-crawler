import csv
import os
from typing import List, Dict


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def sanitize_filename(name: str) -> str:
    # keep alphanum, dash, underscore
    return ''.join(c if c.isalnum() or c in ('-', '_') else '_' for c in name)


def write_csv(path: str, rows: List[Dict[str, str]], headers: List[str]):
    ensure_dir(os.path.dirname(path) or '.')
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: (r.get(k) or '') for k in headers})
