"""Shared SEC EDGAR client. Solves the 403 that blocked the credit pillar.

The 403 recorded on 2026-10-30 had two causes, found by elimination on
2026-10-30 and both reproducible:

1. Both SEC hosts reject the default `Python-urllib/3.x` User-Agent. A
   declared one in SEC's requested format returns 200. This is SEC's fair
   access policy, not a bot defence, and the fix is to comply with it.
2. `www.sec.gov` additionally rejects any request with no `Accept` header,
   with 403 rather than 406. `data.sec.gov` does not. This is why the earlier
   attempts looked inconsistent: the JSON APIs worked while the filing
   documents did not, with the same User-Agent.

Tested directly. With `User-Agent` plus `Accept-Encoding` only, the same
FilingSummary.xml returned 403 three times in a row at half-second spacing.
Adding `Accept: */*` returned 200. Adding `Host` instead did not help, so
`Accept` is the one that matters.

Neither cause was rate limiting, which is worth stating because the obvious
guess at a 403 is that you are being throttled, and the obvious fix of
waiting longer would never have worked here.

Rate limiting is still applied. SEC asks for no more than 10 requests a
second and this client paces at 5, because nothing here is urgent and the
cost of being wrong about the limit is losing access again.

Contact address. SEC asks that the User-Agent identify the requester. The
default below names the project and its public domain, which is a real
contact route and keeps a personal address out of a repo that is meant to
go public. Set SEC_USER_AGENT in .env to override it with a real email,
which is what SEC would prefer. .env is gitignored.

Usage as a module:
    from sec_client import SecClient
    sec = SecClient()
    data = sec.json("https://data.sec.gov/submissions/CIK0001769628.json")

Usage as a check, which fetches one of each endpoint type and reports:
    python scripts/sec_client.py --check
"""

import gzip
import json
import os
import sys
import time
import urllib.error
import urllib.request

# Named in .env.example. Falls back to the project's public identity so the
# client works on a fresh clone with no .env at all.
DEFAULT_UA = ("ai-infra-scorecard research collector "
              "(tonycresearch.substack.com)")
ENV_FILE = ".env"
ENV_KEY = "SEC_USER_AGENT"

MIN_INTERVAL = 0.2          # 5 requests a second against SEC's limit of 10
ATTEMPTS = 4
RETRY_STATUS = {429, 500, 502, 503, 504}


def _user_agent():
    """SEC_USER_AGENT from .env if set, else the project default."""
    if not os.path.exists(ENV_FILE):
        return DEFAULT_UA
    with open(ENV_FILE, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            if key.strip() == ENV_KEY:
                value = value.strip().strip('"').strip("'")
                if value and "your@email" not in value:
                    return value
    return DEFAULT_UA


class SecClient:
    """Rate-limited EDGAR fetcher that sends the headers SEC requires."""

    def __init__(self, user_agent=None, min_interval=MIN_INTERVAL):
        self.user_agent = user_agent or _user_agent()
        self.min_interval = min_interval
        self._last = 0.0
        self.requests = 0

    def _headers(self):
        # Accept is not optional. www.sec.gov answers 403 without it.
        return {
            "User-Agent": self.user_agent,
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate",
        }

    def _wait(self):
        gap = time.time() - self._last
        if gap < self.min_interval:
            time.sleep(self.min_interval - gap)
        self._last = time.time()

    def get(self, url):
        """Response body as bytes. Raises after ATTEMPTS failures."""
        req = urllib.request.Request(url, headers=self._headers())
        last = None
        for attempt in range(ATTEMPTS):
            self._wait()
            try:
                with urllib.request.urlopen(req, timeout=60) as fh:
                    body = fh.read()
                    if fh.headers.get("Content-Encoding") == "gzip":
                        body = gzip.decompress(body)
                self.requests += 1
                return body
            except urllib.error.HTTPError as exc:
                last = exc
                # A 403 here means the headers are wrong, not that we are
                # going too fast. Retrying it would only waste SEC's time.
                if exc.code not in RETRY_STATUS:
                    raise
            except Exception as exc:
                last = exc
            if attempt < ATTEMPTS - 1:
                time.sleep(2 * (attempt + 1))
        raise RuntimeError("%s failed after %d attempts: %s"
                           % (url, ATTEMPTS, last))

    def text(self, url):
        return self.get(url).decode("utf-8", errors="replace")

    def json(self, url):
        return json.loads(self.get(url))

    def save(self, url, path):
        """Fetch and write to path, creating parent directories."""
        body = self.get(url)
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(body)
        return len(body)


CHECKS = [
    ("submissions index",
     "https://data.sec.gov/submissions/CIK0001769628.json"),
    ("XBRL company concept",
     "https://data.sec.gov/api/xbrl/companyconcept/CIK0001769628"
     "/us-gaap/LongTermDebt.json"),
    ("XBRL frames",
     "https://data.sec.gov/api/xbrl/frames/us-gaap"
     "/LongTermDebtNoncurrent/USD/CY2026Q2I.json"),
    ("filing index page",
     "https://www.sec.gov/Archives/edgar/data/1769628"
     "/000176962826000366/"),
    ("FilingSummary.xml",
     "https://www.sec.gov/Archives/edgar/data/1769628"
     "/000176962826000366/FilingSummary.xml"),
    ("full-text search",
     "https://efts.sec.gov/LATEST/search-index"
     "?q=%22delayed+draw+term+loan%22&forms=8-K"),
]


def check():
    sec = SecClient()
    print("user agent: %s" % sec.user_agent)
    print("pacing: %.2fs between requests\n" % sec.min_interval)
    ok = True
    for name, url in CHECKS:
        try:
            n = len(sec.get(url))
            print("  %-22s OK    %8d bytes" % (name, n))
        except Exception as exc:
            ok = False
            print("  %-22s FAIL  %s" % (name, exc))
    print("\n%d requests, %s" % (sec.requests, "all endpoints reachable"
                                 if ok else "SOME ENDPOINTS FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    if "--check" in sys.argv:
        sys.exit(check())
    print(__doc__)
