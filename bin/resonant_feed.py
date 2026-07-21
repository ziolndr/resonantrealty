#!/usr/bin/env python3
"""Fetch, normalize, and snapshot real-estate listings for the RESONANT ARBITER field.

Supported feeds:
- homeharvest: open-source, credential-free Realtor.com extraction
- seed: bundled public San Diego demonstration records
- simplyrets: SimplyRETS /properties API
- reso: generic RESO Web API / OData Property endpoint

The output is JSONL shaped for ARBITER_field_forge.py ingest-jsonl --keep-original.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

USER_AGENT = "RESONANT/1.0 (+ARBITER real-estate field)"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def clean(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def dotted(obj: Any, path: str, default: Any = None) -> Any:
    cur = obj
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def first(obj: dict[str, Any], *paths: str, default: Any = None) -> Any:
    for path in paths:
        value = dotted(obj, path)
        if value not in (None, "", [], {}):
            return value
    return default


def number(value: Any) -> float | int | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    text = re.sub(r"[^0-9.\-]", "", str(value))
    if not text or text in {"-", ".", "-."}:
        return None
    try:
        val = float(text)
        return int(val) if val.is_integer() else val
    except ValueError:
        return None


def as_list(value: Any) -> list[Any]:
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def strings(value: Any, limit: int = 80) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in as_list(value):
        if isinstance(item, dict):
            for key in ("name", "value", "description", "label"):
                text = clean(item.get(key))
                if text:
                    break
            else:
                text = ""
        else:
            text = clean(item)
        if not text:
            continue
        norm = text.casefold()
        if norm in seen:
            continue
        seen.add(norm)
        out.append(text)
        if len(out) >= limit:
            break
    return out


def json_request(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: int = 90,
) -> tuple[Any, dict[str, str]]:
    req_headers = {
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
        **(headers or {}),
    }
    req = urllib.request.Request(url, headers=req_headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read()
            data = json.loads(raw.decode("utf-8"))
            return data, {k.lower(): v for k, v in response.headers.items()}
    except urllib.error.HTTPError as exc:
        body = exc.read(4096).decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from {url}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach {url}: {exc}") from exc


def address_from(record: dict[str, Any]) -> tuple[str, str, str, str]:
    city = clean(first(record, "address.city", "city", "City"))
    state = clean(first(record, "address.state", "state", "StateOrProvince"))
    postal = clean(first(record, "address.postalCode", "address.zip", "postalCode", "PostalCode", "PostalCodePlus4"))
    full = clean(first(record, "address.formatted_address", "address.full", "address.full_line", "formatted_address", "address", "UnparsedAddress"))
    if not full:
        pieces = [
            clean(first(record, "StreetNumber", "address.streetNumber")),
            clean(first(record, "StreetDirPrefix")),
            clean(first(record, "StreetName", "address.streetName")),
            clean(first(record, "StreetSuffix", "address.streetSuffix")),
            clean(first(record, "UnitNumber", "address.unit")),
        ]
        full = " ".join(x for x in pieces if x)
    locality = ", ".join(x for x in (city, state) if x)
    if postal:
        locality = f"{locality} {postal}".strip()
    if full and locality and locality.casefold() not in full.casefold():
        full = f"{full}, {locality}"
    return full or "Address withheld", city, state, postal


def collect_photos(record: dict[str, Any]) -> list[str]:
    candidates: list[Any] = []
    candidates.extend(as_list(first(record, "photos", "Images", "imageUrls", default=[])))
    candidates.extend(as_list(first(record, "Media", "media", default=[])))
    primary = first(record, "imageUrl", "description.primary_photo", "primary_photo", "PrimaryPhotoURL", "PhotoURL", "thumbnail")
    candidates.extend(as_list(first(record, "description.alt_photos", "alt_photos", default=[])))
    if primary:
        candidates.insert(0, primary)

    rows: list[tuple[int, str]] = []
    for idx, item in enumerate(candidates):
        order = idx
        url = ""
        if isinstance(item, str):
            url = item
        elif isinstance(item, dict):
            url = clean(first(item, "MediaURL", "MediaUrl", "url", "href", "Uri", "uri", "imageUrl"))
            order_val = number(first(item, "Order", "order", "MediaOrder", "Sequence"))
            if isinstance(order_val, (int, float)):
                order = int(order_val)
        url = clean(url)
        if url.startswith("//"):
            url = "https:" + url
        if url.startswith("http://") or url.startswith("https://"):
            rows.append((order, url))

    rows.sort(key=lambda pair: pair[0])
    out: list[str] = []
    seen: set[str] = set()
    for _, url in rows:
        if url in seen:
            continue
        seen.add(url)
        out.append(url)
        if len(out) >= 40:
            break
    return out


def feature_values(record: dict[str, Any]) -> list[str]:
    paths = (
        "property.interiorFeatures", "property.exteriorFeatures", "property.heating",
        "property.cooling", "property.parking", "property.view", "property.subdivision",
        "InteriorFeatures", "ExteriorFeatures", "CommunityFeatures", "View",
        "Heating", "Cooling", "FireplaceFeatures", "ParkingFeatures", "PoolFeatures",
        "ArchitecturalStyle", "AssociationAmenities", "Appliances", "PatioAndPorchFeatures",
        "WaterfrontFeatures", "GreenEnergyEfficient", "SubdivisionName", "Levels",
        "tags", "details", "nearby_schools", "parking", "terms",
    )
    out: list[str] = []
    seen: set[str] = set()
    for path in paths:
        for item in strings(dotted(record, path)):
            norm = item.casefold()
            if norm in seen:
                continue
            seen.add(norm)
            out.append(item)
            if len(out) >= 80:
                return out
    return out


def bathrooms(record: dict[str, Any]) -> float | int | None:
    direct = number(first(record, "property.baths", "property.bathrooms", "bathrooms", "BathroomsTotalInteger", "BathroomsTotalDecimal"))
    if direct is not None:
        return direct
    full = number(first(record, "property.bathsFull", "description.baths_full", "full_baths", "BathroomsFull")) or 0
    half = number(first(record, "property.bathsHalf", "description.baths_half", "half_baths", "BathroomsHalf")) or 0
    threeq = number(first(record, "BathroomsThreeQuarter")) or 0
    total = float(full) + float(half) * 0.5 + float(threeq) * 0.75
    return int(total) if total.is_integer() else total if total else None


def normalize(record: dict[str, Any], provider: str) -> dict[str, Any] | None:
    address, city, state, postal = address_from(record)
    mls_id = clean(first(record, "mlsId", "mls_id", "listing_id", "property_id", "ListingId", "ListingKey", "ListingKeyNumeric", "id"))
    if not mls_id:
        basis = address + clean(first(record, "ListPrice", "listPrice"))
        mls_id = hashlib.sha256(basis.encode()).hexdigest()[:24]

    status = clean(first(record, "status", "mls_status", "StandardStatus", "MlsStatus"))
    price = number(first(record, "listPrice", "list_price", "price", "ListPrice", "ClosePrice", "sales.closePrice"))
    beds = number(first(record, "property.bedrooms", "description.beds", "beds", "bedrooms", "BedroomsTotal"))
    baths = bathrooms(record)
    sqft = number(first(record, "property.area", "description.sqft", "sqft", "squareFeet", "LivingArea", "BuildingAreaTotal", "AboveGradeFinishedArea"))
    lot = number(first(record, "property.lotSize", "description.lot_sqft", "lot_sqft", "lotSquareFeet", "LotSizeSquareFeet", "LotSizeArea"))
    year = number(first(record, "property.yearBuilt", "description.year_built", "year_built", "yearBuilt", "YearBuilt"))
    prop_type = clean(first(record, "property.type", "property.subType", "description.style", "description.type", "style", "propertyType", "PropertySubType", "PropertyType")) or "Property"
    remarks = clean(first(record, "remarks", "description.text", "text", "PublicRemarks", "PrivateRemarks", "overview"))
    neighborhood = clean(first(record, "property.subdivision", "neighborhoods", "SubdivisionName", "Neighborhood", "address.neighborhood"))
    features = strings(record.get("features")) + [x for x in feature_values(record) if x not in strings(record.get("features"))]
    photos = collect_photos(record)

    agent_first = clean(first(record, "agent.firstName", "ListAgentFirstName"))
    agent_last = clean(first(record, "agent.lastName", "ListAgentLastName"))
    agent = clean(first(record, "agent.name", "advertisers.agent.name", "agent_name", "ListAgentFullName")) or " ".join(x for x in (agent_first, agent_last) if x)
    office = clean(first(record, "office.name", "advertisers.office.name", "advertisers.broker.name", "office_name", "broker_name", "office.servingName", "ListOfficeName"))
    modified = clean(first(record, "modified", "last_update_date", "last_status_change_date", "ModificationTimestamp", "StatusChangeTimestamp", "list_date", "listDate", "ListingContractDate"))
    lat = number(first(record, "geo.lat", "latitude", "Latitude"))
    lng = number(first(record, "geo.lng", "longitude", "Longitude"))

    listing_url = clean(first(record, "url", "property_url", "permalink", "listingUrl", "VirtualTourURLUnbranded", "virtualTourUrl"))
    if not listing_url and provider == "simplyrets":
        listing_url = f"https://api.simplyrets.com/properties/{urllib.parse.quote(mls_id)}"

    facts: list[str] = [address + "."]
    if price is not None:
        facts.append(f"List price ${float(price):,.0f}.")
    if status:
        facts.append(f"Status {status}.")
    specs: list[str] = []
    if beds is not None:
        specs.append(f"{beds:g} bedrooms" if isinstance(beds, float) else f"{beds} bedrooms")
    if baths is not None:
        specs.append(f"{baths:g} bathrooms" if isinstance(baths, float) else f"{baths} bathrooms")
    if sqft is not None:
        specs.append(f"{float(sqft):,.0f} square feet")
    if specs:
        facts.append(", ".join(specs) + ".")
    if prop_type:
        facts.append(f"Property type {prop_type}.")
    if year:
        facts.append(f"Built in {int(year)}.")
    if neighborhood:
        facts.append(f"Neighborhood or subdivision {neighborhood}.")
    if remarks:
        facts.append(remarks)
    if features:
        facts.append("Features: " + ", ".join(features) + ".")
    if agent:
        facts.append(f"Listing agent {agent}.")
    if office:
        facts.append(f"Listing office {office}.")
    text = " ".join(facts)

    source_id = f"{provider}:{mls_id}"
    return {
        "id": source_id,
        "mlsId": mls_id,
        "title": address,
        "address": address,
        "city": city,
        "state": state,
        "postalCode": postal,
        "status": status,
        "price": price,
        "bedrooms": beds,
        "bathrooms": baths,
        "squareFeet": sqft,
        "lotSquareFeet": lot,
        "yearBuilt": int(year) if year else None,
        "propertyType": prop_type,
        "remarks": remarks,
        "features": features,
        "neighborhood": neighborhood,
        "imageUrl": photos[0] if photos else "",
        "images": photos,
        "url": listing_url,
        "agent": agent,
        "office": office,
        "latitude": lat,
        "longitude": lng,
        "modified": modified,
        "sourceName": provider,
        "type": "property",
        "year": int(year) if year else None,
        "text": text,
    }


@dataclass
class StateDB:
    path: Path

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS listing_state (
                    id TEXT PRIMARY KEY,
                    fingerprint TEXT NOT NULL,
                    modified TEXT,
                    last_seen TEXT NOT NULL
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

    def changed(self, item: dict[str, Any]) -> bool:
        payload = json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        fingerprint = hashlib.sha256(payload.encode()).hexdigest()
        conn = sqlite3.connect(self.path)
        try:
            row = conn.execute("SELECT fingerprint FROM listing_state WHERE id=?", (item["id"],)).fetchone()
            conn.execute(
                "INSERT INTO listing_state(id,fingerprint,modified,last_seen) VALUES(?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET fingerprint=excluded.fingerprint, modified=excluded.modified, last_seen=excluded.last_seen",
                (item["id"], fingerprint, clean(item.get("modified")), utc_now()),
            )
            conn.commit()
            return row is None or row[0] != fingerprint
        finally:
            conn.close()



def homeharvest_records(args: argparse.Namespace) -> Iterator[dict[str, Any]]:
    try:
        from homeharvest import scrape_property
    except ImportError as exc:
        raise RuntimeError(
            "HomeHarvest is not installed. Run INSTALL_RESONANT.command again."
        ) from exc

    locations = [x.strip() for x in re.split(r"[|\n]+", args.location or "San Diego County") if x.strip()]
    listing_types = [x.strip() for x in (args.listing_types or "for_sale,pending").split(",") if x.strip()]
    if not locations:
        locations = ["San Diego County"]

    remaining = args.max_listings if args.max_listings > 0 else 10_000
    for location in locations:
        if remaining <= 0:
            return
        print(f"[homeharvest] fetching {location} · {','.join(listing_types)}", flush=True)
        result = scrape_property(
            location=location,
            listing_type=listing_types,
            limit=min(10_000, remaining),
            return_type="pydantic",
            parallel=not args.sequential,
            extra_property_data=args.extra_property_data,
            exclude_pending=False,
        )
        for prop in result:
            if hasattr(prop, "model_dump"):
                row = prop.model_dump(mode="json", exclude_none=True)
            elif isinstance(prop, dict):
                row = prop
            else:
                continue
            if isinstance(row, dict):
                yield row
                remaining -= 1
                if remaining <= 0:
                    return
        if args.delay:
            time.sleep(args.delay)


def simplyrets_records(args: argparse.Namespace) -> Iterator[dict[str, Any]]:
    key = args.key or os.environ.get("SIMPLYRETS_KEY", "")
    secret = args.secret or os.environ.get("SIMPLYRETS_SECRET", "")
    if not key or not secret:
        raise RuntimeError("SIMPLYRETS_KEY and SIMPLYRETS_SECRET are required")
    token = base64.b64encode(f"{key}:{secret}".encode()).decode()
    headers = {
        "Authorization": f"Basic {token}",
        "Accept": "application/vnd.simplyrets-v0.1+json",
    }
    base = args.base_url or os.environ.get("SIMPLYRETS_BASE_URL", "https://api.simplyrets.com/properties")
    last_id = "0"
    fetched = 0
    while True:
        query = {"limit": str(min(500, args.page_size)), "lastId": last_id, "idx": args.idx}
        url = base + ("&" if "?" in base else "?") + urllib.parse.urlencode(query)
        data, _ = json_request(url, headers=headers, timeout=args.timeout)
        if not isinstance(data, list) or not data:
            break
        for row in data:
            if not isinstance(row, dict):
                continue
            yield row
            fetched += 1
            if args.max_listings and fetched >= args.max_listings:
                return
        next_id = clean(data[-1].get("mlsId")) if isinstance(data[-1], dict) else ""
        if not next_id or next_id == last_id or len(data) < min(500, args.page_size):
            break
        last_id = next_id
        if args.delay:
            time.sleep(args.delay)


def reso_records(args: argparse.Namespace) -> Iterator[dict[str, Any]]:
    base = args.base_url or os.environ.get("RESO_BASE_URL", "")
    token = args.token or os.environ.get("RESO_TOKEN", "")
    if not base or not token:
        raise RuntimeError("RESO_BASE_URL and RESO_TOKEN are required")
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    page_size = min(max(1, args.page_size), 1000)
    params: dict[str, str] = {"$top": str(page_size)}
    filter_expr = args.filter or os.environ.get("RESO_FILTER", "")
    select_expr = args.select or os.environ.get("RESO_SELECT", "")
    expand_expr = args.expand or os.environ.get("RESO_EXPAND", "Media")
    if filter_expr:
        params["$filter"] = filter_expr
    if select_expr:
        params["$select"] = select_expr
    if expand_expr:
        params["$expand"] = expand_expr
    url = base + ("&" if "?" in base else "?") + urllib.parse.urlencode(params)
    fetched = 0
    while url:
        data, _ = json_request(url, headers=headers, timeout=args.timeout)
        if isinstance(data, dict):
            rows = data.get("value") or data.get("results") or data.get("items") or []
            next_url = clean(data.get("@odata.nextLink") or data.get("nextLink") or data.get("next"))
        elif isinstance(data, list):
            rows = data
            next_url = ""
        else:
            rows, next_url = [], ""
        if not isinstance(rows, list) or not rows:
            break
        for row in rows:
            if not isinstance(row, dict):
                continue
            yield row
            fetched += 1
            if args.max_listings and fetched >= args.max_listings:
                return
        url = next_url
        if args.delay and url:
            time.sleep(args.delay)


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> tuple[int, int]:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    accepted = 0
    with tmp.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
            accepted += 1
        fh.flush()
        os.fsync(fh.fileno())
    tmp.replace(path)
    return accepted, path.stat().st_size


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Build a normalized RESONANT property snapshot")
    p.add_argument("--provider", choices=("homeharvest", "simplyrets", "reso"), default=os.environ.get("REAL_ESTATE_PROVIDER", "homeharvest"))
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--state-db", type=Path)
    p.add_argument("--only-changed", action="store_true")
    p.add_argument("--max-listings", type=int, default=int(os.environ.get("REAL_ESTATE_MAX_LISTINGS", "0") or 0))
    p.add_argument("--page-size", type=int, default=int(os.environ.get("REAL_ESTATE_PAGE_SIZE", "500") or 500))
    p.add_argument("--timeout", type=int, default=90)
    p.add_argument("--delay", type=float, default=0.0)
    p.add_argument("--base-url")
    p.add_argument("--key")
    p.add_argument("--secret")
    p.add_argument("--idx", default=os.environ.get("SIMPLYRETS_IDX", "null"))
    p.add_argument("--token")
    p.add_argument("--filter")
    p.add_argument("--select")
    p.add_argument("--expand")
    p.add_argument("--location", default=os.environ.get("HOMEHARVEST_LOCATIONS", "San Diego County"))
    p.add_argument("--listing-types", default=os.environ.get("HOMEHARVEST_LISTING_TYPES", "for_sale,pending"))
    p.add_argument("--sequential", action="store_true", default=os.environ.get("HOMEHARVEST_SEQUENTIAL", "0") == "1")
    p.add_argument("--extra-property-data", action="store_true", default=os.environ.get("HOMEHARVEST_EXTRA_PROPERTY_DATA", "0") == "1")
    return p


def main() -> int:
    args = build_parser().parse_args()
    state = StateDB(args.state_db) if args.state_db else None
    if args.provider == "homeharvest":
        normalized_rows = (
            item for item in (normalize(row, "homeharvest") for row in homeharvest_records(args)) if item
        )
    elif args.provider == "simplyrets":
        normalized_rows = (
            item for item in (normalize(row, "simplyrets") for row in simplyrets_records(args)) if item
        )
    else:
        normalized_rows = (
            item for item in (normalize(row, "reso") for row in reso_records(args)) if item
        )

    def selected() -> Iterator[dict[str, Any]]:
        seen: set[str] = set()
        for item in normalized_rows:
            rid = clean(item.get("id"))
            if not rid or rid in seen:
                continue
            seen.add(rid)
            changed = state.changed(item) if state else True
            if args.only_changed and not changed:
                continue
            yield {k: v for k, v in item.items() if v not in (None, "", [], {})}

    count, size = write_jsonl(args.output, selected())
    print(json.dumps({
        "provider": args.provider,
        "records": count,
        "bytes": size,
        "output": str(args.output),
        "completed_at": utc_now(),
    }, indent=2))
    if count == 0:
        raise SystemExit("No property records were written")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
