# RESONANT

RESONANT is a full-bleed real-estate search interface backed by a dedicated ARBITER property field.

A user describes the property in complete language. Current listings are normalized into semantic candidates, embedded once through ARBITER, and ranked against the entire intention.

## Architecture

```text
HomeHarvest public property collection
→ normalized property JSONL with descriptions and image sets
→ ARBITER /v1/embed
→ immutable 72D real-estate shards
→ property-only live index
→ RESONANT /field/v1/search
```

The default collector requires no MLS credentials or API key.

## Requirements

- macOS
- Python 3.9 or newer
- the existing ARBITER embedding endpoint at `http://127.0.0.1:8000/v1/embed`
- internet access for current public listings

## Install

```zsh
git clone git@github.com:ziolndr/resonantrealty.git
cd resonantrealty
chmod +x *.command
./INSTALL_RESONANT.command
```

The installer creates an isolated Python environment, fetches current San Diego County for-sale and pending properties, refuses incomplete snapshots, embeds and verifies the property field, and launches RESONANT at `http://127.0.0.1:8797/`.

## Refresh listings

```zsh
~/Downloads/BUILD_RESONANT_FIELD.command
```

Each successful refresh atomically replaces the prior field after collection, embedding, and verification.

## Status

```zsh
~/Downloads/RESONANT_STATUS.command
```

## Start

```zsh
~/Downloads/START_RESONANT.command
```

## Public tunnel

```zsh
~/Downloads/DEPLOY_RESONANT_PUBLIC.command
```

This publishes the local frontend and property search backend through an installed ngrok or Cloudflare tunnel.

## Default property scope

```text
San Diego County, CA
San Diego, CA
Chula Vista, CA
Oceanside, CA
Escondido, CA
Carlsbad, CA
El Cajon, CA
Vista, CA
San Marcos, CA
Encinitas, CA
```

Edit `~/Library/Application Support/SUMMON/resonant/config.env` to change locations, listing types, result ceiling, field minimum, embedding endpoint, or port.

## Data retained

- listing and property identifiers
- address and coordinates
- status and list price
- beds, baths, living area, lot area, year, and property type
- public description
- supplied features, neighborhood, parking, fees, and school data
- agent, broker, and office metadata
- listing URL
- primary image and full listing photo set
- listing and update timestamps

## Repository layout

```text
index.html                         GitHub-visible frontend
web/index.html                     frontend served by the local backend
bin/resonant_feed.py               property collector and normalizer
bin/ARBITER_field_forge.py         immutable field builder
bin/RESONANT_live_field_server.py  property-only search server
config/config.env.example          runtime configuration
*.command                          install, build, start, status, and public deployment
```

Generated property data, vectors, credentials, virtual environments, and logs are intentionally excluded from Git.
