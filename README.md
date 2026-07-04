# kkmab-swagger

A fast, multi-threaded Swagger / OpenAPI documentation endpoint discovery tool. Brute-forces a target host against a wordlist of common Swagger UI, OpenAPI spec, and API-docs paths, and reports status codes, redirects, and confirmed matches.

> **For authorized security testing only.** Only run this against hosts you own or have explicit written permission to test.

---

## Files

| File | Purpose |
|---|---|
| `swagger_finder.py` | Main scanner script |
| `swagger_wordlist.txt` | Default wordlist (135 paths), one entry per line |
| `requirements.txt` | Python dependencies |

Keep all three files in the same directory — the script looks for `swagger_wordlist.txt` next to itself by default.

---

## 1. Requirements

- Kali Linux (2023.x or newer recommended)
- Python 3.8+
- `pip` or `pipx`

Kali ships with Python 3 pre-installed. Check your version:

```bash
python3 --version
```

Dependencies are listed in `requirements.txt`:

```
requests>=2.31.0
urllib3>=2.0.0
```

---

## 2. Installation on Kali

### Step 1 — Copy the files onto your Kali machine

Place `swagger_finder.py`, `swagger_wordlist.txt`, and `requirements.txt` in a working directory, e.g.:

```bash
mkdir -p ~/tools/kkmab-swagger
cd ~/tools/kkmab-swagger
# copy swagger_finder.py, swagger_wordlist.txt, and requirements.txt here
```

### Step 2 — Install dependencies

Kali's system Python is externally managed (PEP 668), so a plain `pip install` will usually be blocked. Use one of the following:

**Option A — virtual environment (recommended)**
```bash
sudo apt install -y python3-venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```
Remember to `source venv/bin/activate` again each time you open a new terminal to run the script.

**Option B — apt package (simplest, system-wide)**
```bash
sudo apt update
sudo apt install -y python3-requests
```

**Option C — pip with override (if you understand the risk)**
```bash
pip install -r requirements.txt --break-system-packages
```

### Step 3 — Make the script executable (optional)

```bash
chmod +x swagger_finder.py
```

---

## 3. Basic Usage

```bash
python3 swagger_finder.py <target>
```

Example:

```bash
python3 swagger_finder.py https://example.com
```

`http://` or `https://` is optional — if omitted, `https://` is assumed:

```bash
python3 swagger_finder.py example.com
```

---

## 4. Command-Line Options

```bash
python3 swagger_finder.py --help
```

| Flag | Description | Default |
|---|---|---|
| `target` | Target URL or hostname (required, positional) | — |
| `-w`, `--wordlist` | Path to a custom wordlist file | `swagger_wordlist.txt` (next to the script) |
| `-v`, `--verbose` | Show every response, including 404s | off |
| `--timeout` | Per-request timeout in seconds | `10` |
| `--workers` | Number of concurrent threads | `30` |

### Examples

Verbose scan (see every status code, not just hits):
```bash
python3 swagger_finder.py https://example.com --verbose
```

Faster scan with more threads:
```bash
python3 swagger_finder.py https://example.com --workers 60 --timeout 5
```

Use your own wordlist:
```bash
python3 swagger_finder.py https://example.com -w my_wordlist.txt
```

Scan an internal / self-signed HTTPS target (SSL warnings are already suppressed):
```bash
python3 swagger_finder.py https://192.168.1.50:8443
```

---

## 5. Custom Wordlists

The wordlist file accepts two formats, and you can mix both in the same file:

**Plain format** (one path per line):
```
/swagger.json
/openapi.json
/v2/api-docs
```

**Python-list / quoted format** (handy if you're pasting from another tool or script):
```
"/swagger.json",
"/openapi.json",
"/v2/api-docs",
```

The loader automatically strips quotes, trailing commas, and brackets, normalizes leading slashes, removes duplicates, and ignores blank lines and lines starting with `#`.

To merge your own list with the SecLists API wordlist on Kali:

```bash
cat /usr/share/seclists/Discovery/Web-Content/api/objects-uuids.txt swagger_wordlist.txt | sort -u > combined_wordlist.txt
python3 swagger_finder.py https://example.com -w combined_wordlist.txt
```

(Install SecLists first if you don't have it: `sudo apt install seclists`)

---

## 6. Reading the Output

While scanning, a live progress counter updates in place:

```
[*] Progress: 87/135 checked ( 64.4%)
```

Matches are highlighted in green as they're found:

```
[+] 200 FOUND: https://example.com/v2/api-docs
```

At the end, a summary block shows the full breakdown:

```
============================================================
Scan summary
  Paths checked : 135
  Status codes  : {200: 2, 403: 5, 404: 128}
  Redirects     : 0
  Errors        : 0
  Matches       : 2

[+] Swagger/OpenAPI endpoints found:
  - 200  https://example.com/v2/api-docs
  - 200  https://example.com/swagger-ui/
============================================================
```

The script exits with code `0` if at least one match was found, and `1` otherwise — useful for chaining into scripts:

```bash
python3 swagger_finder.py https://example.com && echo "Swagger found!"
```

---

## 7. Tips for Kali Workflows

- **Run inside a `screen`/`tmux` session** for long scans across many hosts so you don't lose progress if your SSH session drops.
- **Combine with `httpx` or `subfinder`** for recon pipelines — feed a list of live subdomains into this script one at a time:
  ```bash
  for host in $(cat live_hosts.txt); do
      python3 swagger_finder.py "$host" --timeout 5 >> results.log
  done
  ```
- **Redirect output to a log file** for later review — the progress bar automatically disables itself when output isn't a terminal, so log files stay clean:
  ```bash
  python3 swagger_finder.py https://example.com > scan_results.log
  ```
- **Increase `--workers` cautiously** on internal networks with rate limiting or IDS/IPS in place — a high thread count can trigger alerts or lockouts.

---

## 8. Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError: No module named 'requests'` | Install `requests` using one of the methods in Section 2 |
| `error: externally-managed-environment` from pip | Use `pipx`, a venv, `apt install python3-requests`, or `--break-system-packages` |
| `[!] Wordlist file not found` | Check the path passed to `-w`, or confirm `swagger_wordlist.txt` sits next to `swagger_finder.py` |
| SSL certificate errors | Already handled — the script disables cert verification and suppresses the related warnings for self-signed/internal targets |
| All requests show `403` | Target likely has a WAF; try lowering `--workers`, adding delays, or testing from a different network path |

---

## 9. Legal Notice

This tool is intended for authorized penetration testing, bug bounty programs within scope, and security research on systems you own or have explicit permission to test. Unauthorized scanning of systems you do not own or have permission to test may violate computer misuse laws in your jurisdiction. Use responsibly.