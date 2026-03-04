"""Search index builder and query engine for properties.

Builds an inverted index mapping normalized tokens to property IDs.
Supports prefix matching for autocomplete-style search.
"""

import json
import logging
import re
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple

logger = logging.getLogger(__name__)

# Tokens shorter than this are ignored (too noisy)
MIN_TOKEN_LENGTH = 2


def _tokenize(text: str) -> List[str]:
    """Tokenize text into lowercase alphanumeric tokens."""
    if not text:
        return []
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) >= MIN_TOKEN_LENGTH]


def _index_value(index: Dict[str, Set[str]], pid: str, value) -> None:
    """Add all tokens from a value to the index."""
    if value is None:
        return
    text = str(value).strip()
    if not text:
        return

    for tok in _tokenize(text):
        index[tok].add(pid)

    # Also index the full normalized string (for exact/phrase matching)
    # e.g. "RT100008" as one token, "Tim Hortons" as "tim hortons"
    full = re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()
    if full and len(full) >= MIN_TOKEN_LENGTH:
        index[full].add(pid)


def _index_list(index: Dict[str, Set[str]], pid: str, values: list) -> None:
    """Index each item in a list."""
    for v in (values or []):
        _index_value(index, pid, v)


def build_search_index(properties: Dict[str, Dict]) -> Dict:
    """Build an inverted search index from property records.

    Returns {tokens: {token: [pid, pid, ...], ...}, meta: {...}}
    """
    start = time.time()
    index: Dict[str, Set[str]] = defaultdict(set)

    for pid, prop in properties.items():
        # ARN and PINs
        _index_value(index, pid, prop.get("arn"))
        _index_list(index, pid, prop.get("pins"))

        # Source record IDs (RT100008, BR_00001, GW00001, OSM_00001)
        _index_list(index, pid, prop.get("source_records"))

        # All addresses (canonical strings)
        for addr in prop.get("all_addresses", []):
            _index_value(index, pid, addr)

        # City
        _index_value(index, pid, prop.get("city"))

        # Primary address
        _index_value(index, pid, prop.get("primary_address"))

        # Current owner
        owner = prop.get("current_owner") or {}
        for f in ("name", "contact", "attention", "phone"):
            _index_value(index, pid, owner.get(f))
        _index_list(index, pid, owner.get("aliases"))
        _index_list(index, pid, owner.get("company_lines"))
        _index_list(index, pid, owner.get("phones"))

        # All party names
        _index_list(index, pid, prop.get("all_party_names"))

        # All contacts
        for contact in prop.get("all_contacts", []):
            for f in ("name", "contact", "attention", "phone"):
                _index_value(index, pid, contact.get(f))
            _index_list(index, pid, contact.get("phones"))

        # Transactions
        for txn in prop.get("transactions", []):
            _index_value(index, pid, txn.get("rt_id"))
            _index_value(index, pid, txn.get("sale_date"))
            _index_value(index, pid, txn.get("sale_price_display"))
            _index_value(index, pid, txn.get("arn"))
            _index_list(index, pid, txn.get("pins"))
            for party_prefix in ("seller", "buyer"):
                _index_value(index, pid, txn.get(f"{party_prefix}_name"))
                _index_value(index, pid, txn.get(f"{party_prefix}_contact"))
                _index_list(index, pid, txn.get(f"{party_prefix}_aliases"))
                _index_list(index, pid, txn.get(f"{party_prefix}_company_lines"))
            _index_value(index, pid, txn.get("broker_name"))
            _index_value(index, pid, txn.get("legal_description"))
            _index_value(index, pid, txn.get("zoning"))
            _index_value(index, pid, txn.get("description"))

        # Tenants
        for tenant in prop.get("tenants", []):
            _index_value(index, pid, tenant.get("source_id"))
            _index_value(index, pid, tenant.get("name"))
            _index_value(index, pid, tenant.get("brand"))

        # Site summary fields
        _index_value(index, pid, prop.get("zoning"))
        _index_value(index, pid, prop.get("legal_description"))
        _index_value(index, pid, prop.get("broker"))
        _index_value(index, pid, prop.get("description"))

        # Property ID itself
        _index_value(index, pid, pid)

    elapsed = time.time() - start

    # Convert sets to sorted lists for JSON serialization
    tokens = {tok: sorted(pids) for tok, pids in index.items()}

    total_entries = sum(len(v) for v in tokens.values())
    logger.info(
        "Search index: %d tokens, %d entries in %.1fs",
        len(tokens), total_entries, elapsed,
    )

    return {
        "meta": {
            "built_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "total_tokens": len(tokens),
            "total_entries": total_entries,
            "elapsed_seconds": round(elapsed, 1),
        },
        "tokens": tokens,
    }


def search(index_data: Dict, query: str, limit: int = 50) -> List[Tuple[str, float]]:
    """Search the index for properties matching the query.

    Returns list of (property_id, score) tuples sorted by relevance.
    Score is higher for more token matches and exact matches.

    Matching logic:
    - Each query token is matched against index tokens via prefix match
    - Results are intersected (AND logic) across query tokens
    - Exact token matches score higher than prefix matches
    """
    tokens_index = index_data.get("tokens", {})
    query_tokens = _tokenize(query)

    if not query_tokens:
        return []

    # Also try the full query as one token (for "RT100008" or "Tim Hortons")
    full_query = re.sub(r"[^a-z0-9 ]", "", query.lower()).strip()

    # For each query token, find matching property IDs
    token_results: List[Dict[str, float]] = []

    for qt in query_tokens:
        matches: Dict[str, float] = {}

        # Exact match (highest score)
        if qt in tokens_index:
            for pid in tokens_index[qt]:
                matches[pid] = matches.get(pid, 0) + 2.0

        # Prefix match (lower score, only for tokens >= 3 chars)
        if len(qt) >= 3:
            for idx_tok, pids in tokens_index.items():
                if idx_tok != qt and idx_tok.startswith(qt):
                    for pid in pids:
                        if pid not in matches:
                            matches[pid] = matches.get(pid, 0) + 0.5

        token_results.append(matches)

    # Full query match (bonus)
    full_matches: Dict[str, float] = {}
    if full_query and full_query in tokens_index:
        for pid in tokens_index[full_query]:
            full_matches[pid] = 3.0

    if not token_results:
        return []

    # Intersect: property must match ALL query tokens
    common_pids = set(token_results[0].keys())
    for tr in token_results[1:]:
        common_pids &= set(tr.keys())

    # Score = sum of per-token scores + full query bonus
    scored: List[Tuple[str, float]] = []
    for pid in common_pids:
        score = sum(tr.get(pid, 0) for tr in token_results)
        score += full_matches.get(pid, 0)
        scored.append((pid, score))

    scored.sort(key=lambda x: -x[1])
    return scored[:limit]


def save_search_index(index_data: Dict, path: Path) -> None:
    """Save search index to disk."""
    path.write_text(
        json.dumps(index_data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    size_mb = path.stat().st_size / 1024 / 1024
    logger.info("Search index saved: %s (%.1f MB)", path, size_mb)


def load_search_index(path: Path) -> Dict:
    """Load search index from disk."""
    return json.loads(path.read_text(encoding="utf-8"))
