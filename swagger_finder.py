#!/usr/bin/env python3
"""
swagger_finder.py — Discover Swagger / OpenAPI documentation endpoints on a target host.

Usage:
    python swagger_finder.py <target_url> [--verbose] [--timeout 10] [--workers 30]

Example:
    python swagger_finder.py https://example.com
    python swagger_finder.py example.com --verbose --timeout 5
"""

import argparse
import concurrent.futures
import os
import sys
from dataclasses import dataclass, field
from typing import List, Optional
from urllib.parse import urljoin

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------------------------------------------------------------------------
# Wordlist — loaded from an external file (one path per line) so it can be
# edited, extended, or swapped without touching the script.
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Wordlist — loaded from an external file so it can be edited, extended, or
# swapped without touching the script.
#
# Accepts either plain one-path-per-line format:
#     /swagger.json
#     /openapi.json
#
# ...or Python-list style, quotes/commas/brackets included (handy for
# pasting straight out of a `paths = [...]` list):
#     "/swagger.json",
#     "/openapi.json",
# ---------------------------------------------------------------------------
DEFAULT_WORDLIST_FILE = "swagger_wordlist.txt"


def _clean_wordlist_line(raw_line: str) -> str:
    """Strip a single wordlist line down to a bare path.

    Handles plain lines ('/swagger.json') as well as Python-list-style
    lines ('"/swagger.json",', "'/swagger.json',", '[ "/swagger.json" ]').
    """
    line = raw_line.strip()

    # Drop a trailing comma (list-item style)
    if line.endswith(","):
        line = line[:-1].strip()

    # Strip surrounding brackets, e.g. leftover '[' or ']' from a pasted list
    line = line.strip("[]").strip()

    # Strip matching surrounding quotes (single or double)
    if len(line) >= 2 and line[0] == line[-1] and line[0] in ("'", '"'):
        line = line[1:-1].strip()

    return line


def load_wordlist(path: str) -> List[str]:
    """Load paths from a wordlist file, one entry per line.

    Blank lines, lines starting with '#', and stray list punctuation
    (quotes, trailing commas, brackets) are all handled automatically.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw_lines = f.readlines()
    except FileNotFoundError:
        print(f"\033[91m[!] Wordlist file not found: {path}{RESET}")
        sys.exit(1)

    paths: List[str] = []
    for raw_line in raw_lines:
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        cleaned = _clean_wordlist_line(stripped)
        if cleaned and not cleaned.startswith("#"):
            # Ensure every path starts with a single leading slash
            cleaned = "/" + cleaned.lstrip("/")
            paths.append(cleaned)

    if not paths:
        print(f"\033[91m[!] Wordlist file is empty: {path}{RESET}")
        sys.exit(1)

    return sorted(set(paths))


@dataclass
class Result:
    url: str
    status_code: Optional[int] = None
    is_match: bool = False
    error: Optional[str] = None
    redirect_to: Optional[str] = None


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
    )
}

SWAGGER_MARKERS = ("swagger", "openapi", "swagger-ui")

# ANSI colors
GREEN, YELLOW, RED, BLUE, CYAN, BOLD, RESET = (
    "\033[92m", "\033[93m", "\033[91m", "\033[94m", "\033[96m", "\033[1m", "\033[0m"
)

VERSION = "1.0.0"
AUTHOR = "kkmab"

_ASCII_LOGO = r"""
 _  _______ ______  ___  ______     _______        ___    ___  ___ ___ ___
| |/ / ___/ __/ _ \/ _ )/ __/ /    / __/ | /| / /  / _ |  / _ \/ (_) __/ _ \
|   / /__/ _// // / _  / _// /__  _\ \ | |/ |/ /  / __ | / , _/ / / _// , _/
|_|_\___/___/____/____/___/____/ /___/ |__/|__/  /_/ |_|/_/|_/_/_/___/_/|_|
"""

BANNER = f"""{CYAN}{BOLD}{_ASCII_LOGO}{RESET}
{CYAN}  ┌──────────────────────────────────────────────────────────────┐{RESET}
{CYAN}  │{RESET}  {BOLD}kkmab-swagger{RESET}  ·  Swagger / OpenAPI Endpoint Discovery      {CYAN}│{RESET}
{CYAN}  │{RESET}  version {VERSION}  ·  by {AUTHOR}                                  {CYAN}│{RESET}
{CYAN}  │{RESET}  {YELLOW}For authorized security testing only.{RESET}                       {CYAN}│{RESET}
{CYAN}  └──────────────────────────────────────────────────────────────┘{RESET}
"""


def print_banner() -> None:
    print(BANNER)


def check_url(url: str, timeout: int) -> Result:
    """Fetch a single URL and classify the response. Always returns a Result
    (never None) so the caller can report on every status code, not just hits."""
    try:
        resp = requests.get(
            url,
            timeout=timeout,
            verify=False,
            headers=HEADERS,
            allow_redirects=True,
        )
    except requests.RequestException as exc:
        return Result(url=url, error=str(exc))

    result = Result(url=url, status_code=resp.status_code)

    if resp.url != url:
        result.redirect_to = resp.url

    if resp.status_code == 200:
        text_lower = resp.text.lower()
        content_type = resp.headers.get("Content-Type", "").lower()
        if any(marker in text_lower for marker in SWAGGER_MARKERS) or any(
            marker in content_type for marker in SWAGGER_MARKERS
        ):
            result.is_match = True

    return result


def print_result(result: Result, verbose: bool) -> None:
    """Print a single scan result immediately and flush stdout so it shows
    up right away — even when output is piped/redirected and would
    otherwise sit in a buffer until the script finishes."""
    if result.error:
        if verbose:
            print(f"{RED}[!] {result.url} -> ERROR: {result.error}{RESET}", flush=True)
        return

    if result.is_match:
        print(f"{GREEN}[+] {result.status_code} FOUND: {result.url}{RESET}", flush=True)
    elif result.redirect_to and result.status_code in (301, 302, 307, 308):
        print(f"{YELLOW}[→] {result.status_code} {result.url} -> {result.redirect_to}{RESET}", flush=True)
    elif verbose:
        color = RESET if result.status_code == 404 else BLUE
        print(f"{color}[.] {result.status_code} {result.url}{RESET}", flush=True)


def normalize_base_url(raw: str) -> str:
    base = raw.rstrip("/")
    if not base.startswith(("http://", "https://")):
        base = "https://" + base
    return base


def print_progress(completed: int, total: int, found: int) -> None:
    """Overwrite the current terminal line with a live N/Total counter,
    including a running tally of matches found so far.

    No-ops when stdout isn't a real terminal (e.g. piped to a file or CI
    log), since carriage-return redraws just produce garbled output there.
    """
    if not sys.stdout.isatty():
        return
    pct = (completed / total * 100) if total else 0
    found_color = GREEN if found else BLUE
    line = (
        f"{BLUE}[*] Progress: {completed}/{total} checked ({pct:5.1f}%)"
        f"  {found_color}Found: {found}{RESET}"
    )
    # Pad with spaces to clear any leftover characters from a longer previous line
    sys.stdout.write("\r" + line + " " * 10)
    sys.stdout.flush()


def run_scan(base_url: str, wordlist: List[str], timeout: int, workers: int, verbose: bool) -> List[Result]:
    results: List[Result] = []
    total = len(wordlist)
    completed = 0
    found = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(check_url, urljoin(base_url + "/", path.lstrip("/")), timeout): path
            for path in wordlist
        }
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            completed += 1
            if result.is_match:
                found += 1

            # If this result has something worth printing, clear the progress
            # line first so the message isn't smashed together with it.
            if sys.stdout.isatty() and (result.is_match or result.redirect_to or verbose):
                sys.stdout.write("\r" + " " * 80 + "\r")

            print_result(result, verbose)
            print_progress(completed, total, found)

            results.append(result)

    print()  # move off the progress line before the summary prints
    return results


def print_summary(results: List[Result]) -> None:
    matches = [r for r in results if r.is_match]
    redirects = [r for r in results if r.redirect_to and not r.is_match]
    errors = [r for r in results if r.error]

    status_counts = {}
    for r in results:
        if r.status_code is not None:
            status_counts[r.status_code] = status_counts.get(r.status_code, 0) + 1

    print("\n" + "=" * 60)
    print(f"{BLUE}Scan summary{RESET}")
    print(f"  Paths checked : {len(results)}")
    print(f"  Status codes  : {dict(sorted(status_counts.items()))}")
    print(f"  Redirects     : {len(redirects)}")
    print(f"  Errors        : {len(errors)}")
    print(f"  Matches       : {len(matches)}")

    if matches:
        print(f"\n{GREEN}[+] Swagger/OpenAPI endpoints found:{RESET}")
        for r in matches:
            print(f"  {GREEN}- {r.status_code}  {r.url}{RESET}")
    else:
        print(f"\n{YELLOW}[-] No Swagger/OpenAPI endpoints matched.{RESET}")
        print("    Tip: rerun with --verbose to inspect non-200 responses,")
        print("    or expand the wordlist for framework-specific paths.")
    print("=" * 60)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Discover Swagger/OpenAPI endpoints on a target host.")
    parser.add_argument("target", help="Target URL or hostname, e.g. https://example.com")
    parser.add_argument(
        "--wordlist", "-w",
        default=None,
        help=f"Path to a wordlist file, one path per line (default: {DEFAULT_WORDLIST_FILE} next to this script)",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Show every response, including 404s")
    parser.add_argument("--timeout", type=int, default=10, help="Per-request timeout in seconds (default: 10)")
    parser.add_argument("--workers", type=int, default=30, help="Concurrent request workers (default: 30)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    base_url = normalize_base_url(args.target)

    wordlist_path = args.wordlist or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), DEFAULT_WORDLIST_FILE
    )
    wordlist = load_wordlist(wordlist_path)

    print_banner()
    print(f"{BLUE}[*] Target       : {base_url}{RESET}")
    print(f"{BLUE}[*] Wordlist file: {wordlist_path}{RESET}")
    print(f"{BLUE}[*] Wordlist size: {len(wordlist)} paths{RESET}")
    print(f"{BLUE}[*] Workers      : {args.workers}  Timeout: {args.timeout}s{RESET}\n")

    results = run_scan(base_url, wordlist, args.timeout, args.workers, args.verbose)
    print_summary(results)

    sys.exit(0 if any(r.is_match for r in results) else 1)


if __name__ == "__main__":
    main()
