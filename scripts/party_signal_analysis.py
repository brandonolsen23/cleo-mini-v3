#!/usr/bin/env python3
"""
Deep exploration of party matching signals across all parsed transaction records.
Analyzes: aliases, address sharing, phone sharing, contact patterns, cross-signals.
"""

import json
import os
import re
import sys
from collections import defaultdict, Counter
from pathlib import Path
from itertools import combinations

DATA_DIR = Path("/Users/brandonolsen23/cleo-mini-v3/data/parsed/active")

# ─── Load all records ───────────────────────────────────────────────────────

def load_all_records():
    records = []
    for fname in sorted(os.listdir(DATA_DIR)):
        if not fname.endswith(".json") or fname == "_meta.json":
            continue
        with open(DATA_DIR / fname) as f:
            try:
                records.append(json.load(f))
            except json.JSONDecodeError:
                pass
    return records

print("Loading records...")
records = load_all_records()
print(f"Loaded {len(records)} records.\n")

# ─── Extract all party entries ──────────────────────────────────────────────

def normalize_name(name):
    """Normalize entity name for comparison."""
    if not name:
        return ""
    return re.sub(r'\s+', ' ', name.strip().upper())

def normalize_address(addr):
    """Normalize address for comparison."""
    if not addr:
        return ""
    return re.sub(r'\s+', ' ', addr.strip().upper())

def normalize_phone(phone):
    """Strip to digits only."""
    if not phone:
        return ""
    digits = re.sub(r'\D', '', phone)
    if len(digits) == 11 and digits.startswith('1'):
        digits = digits[1:]
    return digits if len(digits) >= 7 else ""

def normalize_contact(contact):
    if not contact:
        return ""
    return re.sub(r'\s+', ' ', contact.strip().upper())

# Collect all party observations
# Each observation: (entity_name, contact, address, phones[], aliases[], alternate_names[], role, rt_id)

parties = []

for rec in records:
    rt_id = rec.get("rt_id", "")
    for role in ("transferor", "transferee"):
        party = rec.get(role)
        if not party:
            continue
        name = normalize_name(party.get("name", ""))
        contact = normalize_contact(party.get("contact", ""))
        address = normalize_address(party.get("address", ""))
        phones_raw = party.get("phones", [])
        phone_single = party.get("phone", "")
        all_phones = set()
        for p in phones_raw:
            np = normalize_phone(p)
            if np:
                all_phones.add(np)
        if phone_single:
            np = normalize_phone(phone_single)
            if np:
                all_phones.add(np)
        aliases = [a.strip().upper() for a in party.get("aliases", []) if a.strip()]
        alt_names = [a.strip().upper() for a in party.get("alternate_names", []) if a.strip()]

        parties.append({
            "name": name,
            "contact": contact,
            "address": address,
            "phones": all_phones,
            "aliases": aliases,
            "alternate_names": alt_names,
            "role": role,
            "rt_id": rt_id,
        })

print(f"Total party observations: {len(parties)}")
print(f"  Transferors: {sum(1 for p in parties if p['role'] == 'transferor')}")
print(f"  Transferees: {sum(1 for p in parties if p['role'] == 'transferee')}")

# Count unique entity names
all_entity_names = set(p["name"] for p in parties if p["name"])
print(f"  Unique entity names: {len(all_entity_names)}")
print()

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 1: ALIAS SOURCE ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════

print("=" * 80)
print("SECTION 1: ALIAS SOURCE ANALYSIS")
print("=" * 80)
print()

# Collect all aliases
all_aliases = []
for p in parties:
    for a in p["aliases"]:
        all_aliases.append({"alias": a, "entity": p["name"], "rt_id": p["rt_id"]})
    for a in p["alternate_names"]:
        all_aliases.append({"alias": a, "entity": p["name"], "rt_id": p["rt_id"]})

print(f"Total alias occurrences: {len(all_aliases)}")
unique_aliases = set(a["alias"] for a in all_aliases)
print(f"Unique alias strings: {len(unique_aliases)}")
print()

# Categorize aliases
def categorize_alias(alias):
    alias_upper = alias.upper()

    # C/O routing
    if re.match(r'^C/?O\b', alias_upper) or alias_upper.startswith("CARE OF") or "C/O " in alias_upper:
        return "c_o_routing"

    # Law firm indicators
    law_keywords = ["LLP", "BARRISTER", "SOLICITOR", "LAW OFFICE", "LAW FIRM", "BARRISTERS", "SOLICITORS", "LEGAL", "AVOCATS"]
    if any(kw in alias_upper for kw in law_keywords):
        return "law_firm"

    # Numbered company: mostly digits + Ontario/Canada/Inc/Ltd/Corp
    # Pattern: starts with digits, optionally followed by Ontario/Canada/Inc/Ltd/Corp
    stripped = re.sub(r'[^A-Z0-9]', '', alias_upper)
    digit_portion = re.sub(r'[^0-9]', '', alias_upper)
    alpha_portion = re.sub(r'[^A-Z]', '', alias_upper)
    if digit_portion and len(digit_portion) >= 4:
        remaining = alpha_portion
        for word in ["ONTARIO", "CANADA", "INC", "LTD", "CORP", "LIMITED", "INCORPORATED", "CORPORATION", "NUMBERED", "COMPANY", "CO"]:
            remaining = remaining.replace(word, "")
        if len(remaining) <= 3:  # Almost entirely digits + standard corp suffixes
            return "numbered_company"

    # Known brand names (common CRE companies)
    brands = [
        "RIOCAN", "KINGSETT", "GOLDMANCO", "SMARTCENTRES", "SMARTREIT", "MORGUARD",
        "DREAM", "FIRST CAPITAL", "BROOKFIELD", "CADILLAC FAIRVIEW", "OXFORD",
        "H&R REIT", "PRIMARIS", "BENTALL", "CROMBIE", "CHOICE PROPERTIES",
        "LOBLAWS", "SOBEYS", "METRO INC", "WALMART", "CANADIAN TIRE",
        "TIM HORTONS", "MCDONALD", "SHOPPERS", "STARBUCKS", "SHELL",
        "PETRO-CANADA", "ESSO", "SCOTIA", "CIBC", "BMO", "TD BANK", "RBC",
        "NORTHAM", "CALLOWAY", "CT REIT", "ARTIS", "ALLIED", "GRANITE",
        "SLATE", "TRIOVEST", "COLLIERS", "CBRE", "CUSHMAN", "JLL",
        "MINTO", "TRIDEL", "MATTAMY", "GREENWIN", "STARLIGHT",
        "KILLAM", "BOARDWALK", "CAPREIT", "INTERRENT", "MAINSTREET",
        "PLAZA", "FIRM CAPITAL", "TRUE NORTH", "NORTHWEST",
    ]
    for brand in brands:
        if brand in alias_upper:
            return "brand"

    # Full company name alias (contains Inc, Ltd, Corp, Trust, LP, etc.)
    corp_suffixes = [" INC", " LTD", " CORP", " LIMITED", " TRUST", " LP", " GP", " PARTNERSHIP", " HOLDINGS", " MANAGEMENT", " PROPERTIES", " REALTY", " INVESTMENTS", " DEVELOPMENT", " ENTERPRISES", " GROUP", " ASSOCIATES", " FOUNDATION"]
    if any(alias_upper.endswith(suffix) or (suffix + ".") in alias_upper or (suffix + ",") in alias_upper for suffix in corp_suffixes):
        return "entity_name"
    if any(suffix.strip() + " " in alias_upper for suffix in corp_suffixes):
        return "entity_name"

    return "other"

category_counts = Counter()
category_examples = defaultdict(list)
for a in all_aliases:
    cat = categorize_alias(a["alias"])
    category_counts[cat] += 1
    if len(category_examples[cat]) < 10:
        category_examples[cat].append(f"  {a['alias']}  (entity: {a['entity'][:60]})")

print("Alias categories (by occurrence count):")
for cat, count in category_counts.most_common():
    pct = 100.0 * count / len(all_aliases) if all_aliases else 0
    print(f"  {cat:25s}: {count:6d}  ({pct:.1f}%)")
print()

for cat in category_counts.most_common():
    cat_name = cat[0]
    print(f"--- {cat_name} examples ---")
    for ex in category_examples[cat_name]:
        print(ex)
    print()


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 2: ADDRESS SHARING PATTERNS
# ═══════════════════════════════════════════════════════════════════════════

print("=" * 80)
print("SECTION 2: ADDRESS SHARING PATTERNS")
print("=" * 80)
print()

# Map address -> set of entity names
addr_to_entities = defaultdict(set)
addr_to_details = defaultdict(list)  # address -> list of party dicts

for p in parties:
    if p["address"]:
        addr_to_entities[p["address"]].add(p["name"])
        addr_to_details[p["address"]].append(p)

# Filter addresses with 5+ distinct entity names
high_share_addrs = {addr: names for addr, names in addr_to_entities.items() if len(names) >= 5}
print(f"Addresses with 5+ distinct entity names: {len(high_share_addrs)}")
print(f"Addresses with 10+ distinct entity names: {sum(1 for names in high_share_addrs.values() if len(names) >= 10)}")
print(f"Addresses with 20+ distinct entity names: {sum(1 for names in high_share_addrs.values() if len(names) >= 20)}")
print()

# Top 3 addresses by entity count
top_addrs = sorted(high_share_addrs.items(), key=lambda x: len(x[1]), reverse=True)[:3]
for i, (addr, names) in enumerate(top_addrs, 1):
    print(f"--- Top Address #{i}: {addr[:100]} ({len(names)} entities) ---")
    # For each entity at this address, show aliases
    entity_aliases = defaultdict(set)
    for p in addr_to_details[addr]:
        for a in p["aliases"]:
            entity_aliases[p["name"]].add(a)
        for a in p["alternate_names"]:
            entity_aliases[p["name"]].add(a)

    for name in sorted(names):
        aliases_str = ", ".join(sorted(entity_aliases.get(name, set()))) if entity_aliases.get(name) else "(none)"
        print(f"  Entity: {name[:70]}")
        print(f"    Aliases: {aliases_str[:120]}")
    print()

# Characterize high-sharing addresses
print("--- Characterization of high-sharing addresses ---")
law_firm_addrs = 0
office_tower_addrs = 0
for addr, names in high_share_addrs.items():
    # Check if mostly numbered companies
    numbered = sum(1 for n in names if re.match(r'^\d{5,}', n))
    has_law = any("LLP" in n or "BARRISTER" in n or "SOLICITOR" in n for n in names)
    # Check aliases for law firms
    for p in addr_to_details[addr]:
        for a in p["aliases"] + p["alternate_names"]:
            if any(kw in a.upper() for kw in ["LLP", "BARRISTER", "SOLICITOR"]):
                has_law = True
    if has_law:
        law_firm_addrs += 1
    else:
        office_tower_addrs += 1

print(f"  Addresses where a law firm alias/name appears: {law_firm_addrs}")
print(f"  Addresses with no law firm indicator: {office_tower_addrs}")
print()

# Distribution of entity counts per address
addr_entity_counts = [len(names) for names in addr_to_entities.values()]
print(f"Address sharing distribution:")
print(f"  Addresses with exactly 1 entity: {sum(1 for c in addr_entity_counts if c == 1)}")
print(f"  Addresses with 2-4 entities: {sum(1 for c in addr_entity_counts if 2 <= c <= 4)}")
print(f"  Addresses with 5-9 entities: {sum(1 for c in addr_entity_counts if 5 <= c <= 9)}")
print(f"  Addresses with 10-19 entities: {sum(1 for c in addr_entity_counts if 10 <= c <= 19)}")
print(f"  Addresses with 20-49 entities: {sum(1 for c in addr_entity_counts if 20 <= c <= 49)}")
print(f"  Addresses with 50+ entities: {sum(1 for c in addr_entity_counts if c >= 50)}")
print()


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 3: PHONE SHARING PATTERNS
# ═══════════════════════════════════════════════════════════════════════════

print("=" * 80)
print("SECTION 3: PHONE SHARING PATTERNS")
print("=" * 80)
print()

# Map phone -> set of entity names, set of contacts
phone_to_entities = defaultdict(set)
phone_to_contacts = defaultdict(set)
phone_to_details = defaultdict(list)

for p in parties:
    for ph in p["phones"]:
        phone_to_entities[ph].add(p["name"])
        if p["contact"]:
            phone_to_contacts[ph].add(p["contact"])
        phone_to_details[ph].append(p)

high_share_phones = {ph: names for ph, names in phone_to_entities.items() if len(names) >= 5}
print(f"Total unique phones: {len(phone_to_entities)}")
print(f"Phones with 5+ distinct entity names: {len(high_share_phones)}")
print(f"Phones with 10+ distinct entity names: {sum(1 for names in high_share_phones.values() if len(names) >= 10)}")
print(f"Phones with 20+ distinct entity names: {sum(1 for names in high_share_phones.values() if len(names) >= 20)}")
print()

# Phone sharing distribution
phone_entity_counts = [len(names) for names in phone_to_entities.values()]
print(f"Phone sharing distribution:")
print(f"  Phones with exactly 1 entity: {sum(1 for c in phone_entity_counts if c == 1)}")
print(f"  Phones with 2-4 entities: {sum(1 for c in phone_entity_counts if 2 <= c <= 4)}")
print(f"  Phones with 5-9 entities: {sum(1 for c in phone_entity_counts if 5 <= c <= 9)}")
print(f"  Phones with 10-19 entities: {sum(1 for c in phone_entity_counts if 10 <= c <= 19)}")
print(f"  Phones with 20+ entities: {sum(1 for c in phone_entity_counts if c >= 20)}")
print()

# Top 5 phones by entity count
top_phones = sorted(high_share_phones.items(), key=lambda x: len(x[1]), reverse=True)[:5]
for i, (ph, names) in enumerate(top_phones, 1):
    contacts = phone_to_contacts.get(ph, set())
    print(f"--- Top Phone #{i}: {ph} ({len(names)} entities, {len(contacts)} contacts) ---")
    print(f"  Contacts: {', '.join(sorted(contacts)[:15])}")
    for name in sorted(names)[:20]:
        print(f"  Entity: {name[:80]}")
    if len(names) > 20:
        print(f"  ... and {len(names) - 20} more entities")
    print()

# For high-sharing phones: are contacts consistent or diverse?
print("--- Contact consistency for phones with 5+ entities ---")
consistent_phones = 0
diverse_phones = 0
for ph, names in high_share_phones.items():
    contacts = phone_to_contacts.get(ph, set())
    if len(contacts) <= 2:
        consistent_phones += 1
    else:
        diverse_phones += 1
print(f"  Phones with 1-2 contacts (consistent): {consistent_phones}")
print(f"  Phones with 3+ contacts (diverse): {diverse_phones}")
print()


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 4: CONTACT PATTERNS
# ═══════════════════════════════════════════════════════════════════════════

print("=" * 80)
print("SECTION 4: CONTACT PATTERNS")
print("=" * 80)
print()

# Map contact -> set of entity names
contact_to_entities = defaultdict(set)
contact_to_addresses = defaultdict(set)
contact_to_phones = defaultdict(set)
contact_to_details = defaultdict(list)

for p in parties:
    if p["contact"]:
        contact_to_entities[p["contact"]].add(p["name"])
        if p["address"]:
            contact_to_addresses[p["contact"]].add(p["address"])
        for ph in p["phones"]:
            contact_to_phones[p["contact"]].add(ph)
        contact_to_details[p["contact"]].append(p)

print(f"Total unique contact names: {len(contact_to_entities)}")
high_share_contacts = {c: names for c, names in contact_to_entities.items() if len(names) >= 5}
print(f"Contacts with 5+ distinct entity names: {len(high_share_contacts)}")
print(f"Contacts with 10+ distinct entity names: {sum(1 for names in high_share_contacts.values() if len(names) >= 10)}")
print(f"Contacts with 20+ distinct entity names: {sum(1 for names in high_share_contacts.values() if len(names) >= 20)}")
print()

# Contact sharing distribution
contact_entity_counts = [len(names) for names in contact_to_entities.values()]
print(f"Contact sharing distribution:")
print(f"  Contacts with exactly 1 entity: {sum(1 for c in contact_entity_counts if c == 1)}")
print(f"  Contacts with 2-4 entities: {sum(1 for c in contact_entity_counts if 2 <= c <= 4)}")
print(f"  Contacts with 5-9 entities: {sum(1 for c in contact_entity_counts if 5 <= c <= 9)}")
print(f"  Contacts with 10-19 entities: {sum(1 for c in contact_entity_counts if 10 <= c <= 19)}")
print(f"  Contacts with 20+ entities: {sum(1 for c in contact_entity_counts if c >= 20)}")
print()

# Top 10 contacts by entity count
top_contacts = sorted(high_share_contacts.items(), key=lambda x: len(x[1]), reverse=True)[:10]
for i, (contact, names) in enumerate(top_contacts, 1):
    addrs = contact_to_addresses.get(contact, set())
    # Check if law-related: consistent address, law keywords in aliases of entities
    is_law = False
    for p in contact_to_details[contact]:
        for a in p["aliases"] + p["alternate_names"]:
            if any(kw in a.upper() for kw in ["LLP", "BARRISTER", "SOLICITOR", "LAW"]):
                is_law = True
                break
    # Also check if many different addresses (intermediary vs principal)
    law_label = "LAW-RELATED" if is_law else ""
    addr_label = f"{len(addrs)} distinct addresses"

    print(f"--- Top Contact #{i}: {contact} ({len(names)} entities, {addr_label}) {law_label} ---")
    for name in sorted(names)[:15]:
        print(f"  Entity: {name[:80]}")
    if len(names) > 15:
        print(f"  ... and {len(names) - 15} more entities")
    if addrs:
        print(f"  Sample addresses: {list(sorted(addrs))[:3]}")
    print()


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 5: CROSS-SIGNAL ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════

print("=" * 80)
print("SECTION 5: CROSS-SIGNAL ANALYSIS")
print("=" * 80)
print()

# Build entity-level aggregations: for each entity name, collect all addresses, phones, contacts, aliases
entity_addresses = defaultdict(set)
entity_phones = defaultdict(set)
entity_contacts = defaultdict(set)
entity_aliases = defaultdict(set)

for p in parties:
    name = p["name"]
    if not name:
        continue
    if p["address"]:
        entity_addresses[name].add(p["address"])
    for ph in p["phones"]:
        entity_phones[name].add(ph)
    if p["contact"]:
        entity_contacts[name].add(p["contact"])
    for a in p["aliases"]:
        cat = categorize_alias(a)
        if cat not in ("c_o_routing", "law_firm"):
            entity_aliases[name].add(a)
    for a in p["alternate_names"]:
        cat = categorize_alias(a)
        if cat not in ("c_o_routing", "law_firm"):
            entity_aliases[name].add(a)

all_entities = list(all_entity_names)
print(f"Analyzing cross-signals across {len(all_entities)} unique entity names...")
print()

# --- 5A: Entities sharing SAME address AND phone ---
print("--- 5A: Same Address + Same Phone => Shared Contact? ---")
# Build inverted indices
addr_entities_map = defaultdict(set)  # address -> set of entity names
phone_entities_map = defaultdict(set)  # phone -> set of entity names

for name in all_entities:
    for addr in entity_addresses[name]:
        addr_entities_map[addr].add(name)
    for ph in entity_phones[name]:
        phone_entities_map[ph].add(name)

# Find pairs sharing both address and phone
pairs_addr_phone = set()
pairs_addr_phone_contact = set()

# More efficient: iterate over addresses, find entities sharing address, check if they share phone
count_addr_phone_pairs = 0
count_addr_phone_contact_pairs = 0
sample_pairs = []

for addr, addr_ents in addr_entities_map.items():
    if len(addr_ents) < 2:
        continue
    for e1, e2 in combinations(sorted(addr_ents), 2):
        shared_phones = entity_phones[e1] & entity_phones[e2]
        if shared_phones:
            count_addr_phone_pairs += 1
            shared_contacts = entity_contacts[e1] & entity_contacts[e2]
            if shared_contacts:
                count_addr_phone_contact_pairs += 1
            if len(sample_pairs) < 5:
                sample_pairs.append((e1, e2, addr[:60], shared_phones, shared_contacts))

print(f"  Entity pairs sharing BOTH address AND phone: {count_addr_phone_pairs}")
print(f"  Of those, pairs also sharing a contact: {count_addr_phone_contact_pairs}")
if count_addr_phone_pairs > 0:
    pct = 100.0 * count_addr_phone_contact_pairs / count_addr_phone_pairs
    print(f"  Percentage: {pct:.1f}%")
print()
print("  Sample pairs (addr+phone):")
for e1, e2, addr, phones, contacts in sample_pairs[:5]:
    print(f"    {e1[:40]} <-> {e2[:40]}")
    print(f"      Address: {addr}")
    print(f"      Phones: {phones}")
    print(f"      Shared contacts: {contacts if contacts else 'NONE'}")
print()

# --- 5B: Entities sharing alias (non-c/o, non-law) => shared address? ---
print("--- 5B: Shared Alias (non-c/o, non-law) => Shared Address? ---")
alias_entities_map = defaultdict(set)
for name in all_entities:
    for a in entity_aliases[name]:
        alias_entities_map[a].add(name)

count_alias_pairs = 0
count_alias_addr_pairs = 0
sample_alias_pairs = []

for alias, alias_ents in alias_entities_map.items():
    if len(alias_ents) < 2:
        continue
    for e1, e2 in combinations(sorted(alias_ents), 2):
        count_alias_pairs += 1
        shared_addrs = entity_addresses[e1] & entity_addresses[e2]
        if shared_addrs:
            count_alias_addr_pairs += 1
        if len(sample_alias_pairs) < 5 and len(alias_ents) >= 2:
            sample_alias_pairs.append((alias, e1, e2, shared_addrs))

print(f"  Entity pairs sharing a non-c/o, non-law alias: {count_alias_pairs}")
print(f"  Of those, pairs also sharing an address: {count_alias_addr_pairs}")
if count_alias_pairs > 0:
    pct = 100.0 * count_alias_addr_pairs / count_alias_pairs
    print(f"  Percentage: {pct:.1f}%")
print()
print("  Sample pairs (shared alias):")
for alias, e1, e2, addrs in sample_alias_pairs[:5]:
    print(f"    Alias: {alias}")
    print(f"    {e1[:50]} <-> {e2[:50]}")
    print(f"    Shared addresses: {list(addrs)[:2] if addrs else 'NONE'}")
print()

# --- 5C: Entities sharing contact name => shared phone? ---
print("--- 5C: Shared Contact Name => Shared Phone? ---")
contact_entities_map = defaultdict(set)
for name in all_entities:
    for c in entity_contacts[name]:
        contact_entities_map[c].add(name)

count_contact_pairs = 0
count_contact_phone_pairs = 0
sample_contact_pairs = []

for contact, contact_ents in contact_entities_map.items():
    if len(contact_ents) < 2:
        continue
    for e1, e2 in combinations(sorted(contact_ents), 2):
        count_contact_pairs += 1
        shared_ph = entity_phones[e1] & entity_phones[e2]
        if shared_ph:
            count_contact_phone_pairs += 1
        if len(sample_contact_pairs) < 5:
            sample_contact_pairs.append((contact, e1, e2, shared_ph))

print(f"  Entity pairs sharing a contact name: {count_contact_pairs}")
print(f"  Of those, pairs also sharing a phone: {count_contact_phone_pairs}")
if count_contact_pairs > 0:
    pct = 100.0 * count_contact_phone_pairs / count_contact_pairs
    print(f"  Percentage: {pct:.1f}%")
print()
print("  Sample pairs (shared contact):")
for contact, e1, e2, phones in sample_contact_pairs[:5]:
    print(f"    Contact: {contact}")
    print(f"    {e1[:50]} <-> {e2[:50]}")
    print(f"    Shared phones: {phones if phones else 'NONE'}")
print()

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 6: SUMMARY OF SIGNAL RELIABILITY
# ═══════════════════════════════════════════════════════════════════════════

print("=" * 80)
print("SECTION 6: SIGNAL RELIABILITY SUMMARY")
print("=" * 80)
print()

# Entities with vs without various signals
has_address = sum(1 for n in all_entities if entity_addresses[n])
has_phone = sum(1 for n in all_entities if entity_phones[n])
has_contact = sum(1 for n in all_entities if entity_contacts[n])
has_alias = sum(1 for n in all_entities if entity_aliases[n])

print(f"Signal coverage across {len(all_entities)} unique entity names:")
print(f"  Has address: {has_address} ({100*has_address/len(all_entities):.1f}%)")
print(f"  Has phone:   {has_phone} ({100*has_phone/len(all_entities):.1f}%)")
print(f"  Has contact: {has_contact} ({100*has_contact/len(all_entities):.1f}%)")
print(f"  Has alias (non-c/o, non-law): {has_alias} ({100*has_alias/len(all_entities):.1f}%)")
print()

# Law firm addresses: how many entities route through law firms?
law_addr_entities = set()
for p in parties:
    for a in p["aliases"] + p["alternate_names"]:
        if any(kw in a.upper() for kw in ["LLP", "BARRISTER", "SOLICITOR"]):
            law_addr_entities.add(p["name"])
print(f"Entities with a law-firm alias/alternate: {len(law_addr_entities)} ({100*len(law_addr_entities)/len(all_entities):.1f}%)")
print("  (These entities' addresses and contacts may reflect the law firm, not the entity itself)")
print()

# Numbered companies
numbered_entities = set()
for n in all_entities:
    if re.match(r'^\d{5,}', n):
        numbered_entities.add(n)
print(f"Numbered company entities (name starts with 5+ digits): {len(numbered_entities)} ({100*len(numbered_entities)/len(all_entities):.1f}%)")
print()

print("=" * 80)
print("ANALYSIS COMPLETE")
print("=" * 80)
