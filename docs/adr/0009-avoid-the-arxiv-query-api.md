# Ingest via the listing page and OAI-PMH, not the arXiv query API

`export.arxiv.org/api/query` is the obvious way to ask arXiv for papers, and we do not use it. It is chronically overloaded: during development it returned HTTP 429 "Rate exceeded" continuously for over an hour, and — the telling detail — took **46 seconds** to do so. A per-IP rate limit rejects in milliseconds; a 46-second rejection is server-side congestion, so waiting does not reliably help and politeness alone does not avoid it.

Two other endpoints serve our needs and were unaffected during the same outage:

- **`arxiv.org/list/{category}/recent`** — the HTML listing page, ~50ms, returns ids and titles together. Used for `--recent N`.
- **`export.arxiv.org/oai2`** — OAI-PMH, ~5s for a full day of the `math` set (~476 records), with resumption tokens for longer ranges. Used for `--harvest FROM:UNTIL`.

OAI-PMH is also simply the right tool: it is the interface arXiv intends for bulk harvesting, and a date range is exactly what "every math.CO paper in June 2026" means. The query API was never suited to that — it paginates a search, and we were not searching.

## Consequences

Parsing HTML is more brittle than parsing an API response, and the listing-page regexes will break when arXiv changes its markup. That is an acceptable trade for an ingestion path that works; the failure is loud and local to one function.

OAI-PMH filters on **datestamp, not submission date**, so a range returns revisions of much older papers — a one-day harvest surfaced a 2014 paper. `harvest()` therefore keeps only ids whose `YYMM` prefix falls inside the requested months. Anyone extending this to fetch by any other criterion needs to remember that distinction.

The `fetch()` backoff and the 3-second politeness gap stay regardless. They cost nothing when things are healthy and they are the right behaviour toward a free service.
