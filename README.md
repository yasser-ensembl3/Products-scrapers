# Products Scrapers

Multi-provider e-commerce product scraping toolkit. Five standalone scrapers using different APIs (Apify, Bright Data, Channel3, DataForSEO, Zyte), plus an n8n workflow that scrapes Shopify stores via their public `/products.json` endpoint and upserts results into PostgreSQL.

## Architecture

```
Products-scrapers/
├── Scrapers/
│   ├── apify/
│   │   └── apify_ecommerce_scraper.py      # Apify — any e-commerce site
│   ├── brightdata/
│   │   ├── brightdata_shopify_scraper.py    # Bright Data — Shopify stores
│   │   ├── brightdata_airbnb_scraper.py     # Bright Data — Airbnb Experiences
│   │   ├── api/scrape.py                    # Vercel serverless API (Airbnb + Shopify)
│   │   ├── server.py                        # Local dev server + Google Drive OAuth
│   │   └── public/index.html               # Frontend UI
│   ├── channel3/
│   │   └── channel3_gift_scraper.py         # Channel3 — gift product search
│   ├── dataforseo/
│   │   └── amazon_gift_scraper.py           # DataForSEO — Amazon products
│   └── zyte/
│       └── zyte_ecommerce_scraper.py        # Zyte — AI-powered extraction
├── n8n Workflow/
│   ├── Scraping produits (1).json           # n8n workflow definition
│   └── shopify_scraper_step1.py             # Shopify fetcher script (called by n8n)
└── README.md
```

## Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3 |
| Scraping APIs | Apify, Bright Data, Channel3 SDK, DataForSEO, Zyte |
| Workflow engine | n8n (self-hosted) |
| Database | PostgreSQL |
| Frontend | Vanilla HTML/CSS/JS |
| Deployment | Vercel (serverless API) |
| Storage | Google Sheets, Google Drive (OAuth2) |

---

## Scrapers

### 1. Apify — E-commerce Scraper

**File:** `Scrapers/apify/apify_ecommerce_scraper.py`

Scrapes any e-commerce site using Apify's "E-commerce Scraping Tool" actor. Supports listing pages, product pages, and search result pages.

- **API:** Apify REST API (token as query param)
- **Actor:** `aYG0l9s7dbB7j3gbS` (E-commerce Scraping Tool)
- **Modes:** Synchronous (10 min timeout) or async with polling
- **Input:** Lists of URLs (listing, product, search) + scrape mode (`BROWSER` or `HTTP`)
- **Output:** JSON file with normalized product data

```bash
# Configure API token in the script
python3 Scrapers/apify/apify_ecommerce_scraper.py
```

### 2. Bright Data — Shopify Scraper

**File:** `Scrapers/brightdata/brightdata_shopify_scraper.py`

Scrapes Shopify stores via their `/products.json` endpoint, proxied through Bright Data's Web Unlocker to bypass anti-bot protections. Full pagination support.

- **API:** Bright Data Web Unlocker (`web_unlocker1` zone)
- **Pagination:** `?limit=250&page=N` — stops when empty or max reached
- **Extracts:** All variants (price, SKU, availability, options), images with dimensions, discount calculations
- **Env:** `BRIGHTDATA_API_KEY` in `.env.local`

```bash
cd Scrapers/brightdata
python3 brightdata_shopify_scraper.py
```

### 3. Bright Data — Airbnb Experiences Scraper

**File:** `Scrapers/brightdata/brightdata_airbnb_scraper.py`

Scrapes Airbnb Experiences from search pages. Fetches full HTML via Bright Data, parses embedded `niobeClientData` JSON from `<script>` tags.

- **API:** Bright Data Web Unlocker
- **Parsing:** BeautifulSoup → finds `niobeClientData` in scripts → deep JSON traversal
- **Extracts:** Title, rating, reviews, duration, price (regex), category, images
- **No pagination** — single page only

```bash
cd Scrapers/brightdata
python3 brightdata_airbnb_scraper.py
```

### 4. Bright Data — Web App (Vercel + Local Server)

**Files:** `Scrapers/brightdata/api/scrape.py`, `server.py`, `public/index.html`

Full-stack web application with Airbnb + Shopify scraping and Google Drive export.

- **Vercel API** (`api/scrape.py`): Serverless POST endpoint — accepts `{"url": "...", "scraper": "airbnb"|"shopify"}`
- **Local server** (`server.py`): Development server on `localhost:8000` with Google OAuth2 for Drive upload
- **Frontend** (`public/index.html`): Dark-themed UI with scraper selection, results grid, and Drive save button
- **Env:** `BRIGHTDATA_API_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_DRIVE_FOLDER_ID`

```bash
cd Scrapers/brightdata
pip install -r requirements.txt
python3 server.py  # http://localhost:8000
```

### 5. Channel3 — Gift Product Scraper

**File:** `Scrapers/channel3/channel3_gift_scraper.py`

Scrapes gift products from Channel3's product discovery API using keyword-based search across 50 gift-related keywords.

- **API:** Channel3 SDK (`channel3_sdk`)
- **Keywords:** 50 seed keywords organized by relation, occasion, interest, type, gender/age
- **Deduplication:** By product ID, keeps highest relevance score
- **Filters:** Min relevance score 50, excludes gift cards and digital products

```bash
python3 Scrapers/channel3/channel3_gift_scraper.py
```

### 6. DataForSEO — Amazon Gift Scraper

**File:** `Scrapers/dataforseo/amazon_gift_scraper.py`

Scrapes Amazon product listings via DataForSEO Merchant API. Async task-based architecture with multi-location support.

- **API:** DataForSEO Merchant API (HTTP Basic Auth)
- **Workflow:** Create tasks → poll for completion (2s interval, 60s max) → fetch results
- **Locations:** US (2840) and CA (2124)
- **Scoring:** Composite 0-100 score based on rating, reviews (log scale), badges (Choice/Seller), Prime
- **Filters:** Min 100 reviews, min 4.0 rating
- **Deduplication:** By ASIN

```bash
python3 Scrapers/dataforseo/amazon_gift_scraper.py
```

### 7. Zyte — AI E-commerce Scraper

**File:** `Scrapers/zyte/zyte_ecommerce_scraper.py`

Scrapes any e-commerce site using Zyte's AI-powered extraction API. No site-specific selectors needed — ML auto-identifies product data.

- **API:** Zyte API (HTTP Basic Auth, key as username)
- **Extraction modes:** Product list, product navigation (pagination), individual product
- **Pagination:** AI-detected `nextPage.url` from product navigation extraction
- **Includes:** Zyte's `probability` confidence score per product
- **Rate limiting:** 1s between pages

```bash
python3 Scrapers/zyte/zyte_ecommerce_scraper.py
```

---

## n8n Workflow — Scraping produits

**Files:** `n8n Workflow/Scraping produits (1).json`, `n8n Workflow/shopify_scraper_step1.py`

Automated workflow that reads Shopify store URLs from Google Sheets, scrapes products via the public `/products.json` endpoint, and upserts results into PostgreSQL.

### Pipeline

```
Manual Trigger
    → Google Sheets (read rows where Statut = "KO")
    → Limit (75 items per run)
    → Loop Over Items
        → Execute Command (python3 shopify_scraper_step1.py <domain_url>)
        → Code in JavaScript (parse JSON stdout → array of products)
        → PostgreSQL Upsert (insert or update by url)
    → Loop back
```

### Nodes

| Node | Type | Description |
|------|------|-------------|
| Manual Trigger | manualTrigger | Click to execute |
| Get row(s) in sheet1 | googleSheets | Read from "weddingUS" sheet, filter `Statut = "KO"` |
| Limit1 | limit | Cap at 75 items per run |
| Loop Over Items | splitInBatches | Process one domain at a time |
| Execute Command1 | executeCommand | Run `shopify_scraper_step1.py` with domain URL |
| Code in JavaScript | code | Parse stdout JSON into product array |
| Insert or update rows | postgres | Upsert into `products` table, match on `url` |

### shopify_scraper_step1.py

Lightweight Shopify scraper for n8n integration:

- Fetches `{domain}/products.json?limit=125&sort_by=created_at&order=desc`
- No proxy needed — direct access to Shopify's public API
- Outputs JSON array to stdout (consumed by n8n)
- Fields: Website, handle, sku, title, Description, vendor, price, image, url

### PostgreSQL Database Setup

Create the `products` table before running the workflow:

```sql
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    website VARCHAR(255),
    handle VARCHAR(255),
    sku VARCHAR(255),
    title VARCHAR(255),
    description TEXT,
    vendor VARCHAR(255),
    price NUMERIC(10, 2),
    image VARCHAR(1000),
    availability BOOLEAN,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    url VARCHAR(1000) UNIQUE
);
```

The workflow uses `url` as the upsert matching column — existing products are updated, new ones are inserted.

### Google Sheets Structure

| Column | Description |
|--------|-------------|
| domain_url | Shopify store URL (input) |
| Statut | "KO" = pending, updated after processing |

### Credentials

| Service | Type | Used By |
|---------|------|---------|
| Google Sheets | OAuth2 (n8n) | Read domain URLs |
| PostgreSQL | Connection (n8n) | Upsert products |

---

## Scraper Comparison

| Scraper | Provider | Target | Pagination | Auth | Output |
|---------|----------|--------|-----------|------|--------|
| Apify | Apify | Any e-commerce | Via actor | Token param | JSON file |
| Bright Data Shopify | Bright Data | Shopify stores | Page-based | Bearer (env) | JSON file |
| Bright Data Airbnb | Bright Data | Airbnb Experiences | None | Bearer (env) | JSON file |
| Channel3 | Channel3 SDK | Gift products | Keyword iteration | API key | JSON file |
| DataForSEO | DataForSEO | Amazon | Async tasks | Basic Auth | JSON file |
| Zyte | Zyte | Any e-commerce | AI-detected | Basic Auth | JSON file |
| n8n Workflow | Direct (public API) | Shopify stores | None (125/req) | None | PostgreSQL |

## Setup

### Prerequisites

- Python 3.8+
- n8n instance (for the workflow)
- PostgreSQL (for the workflow)

### Installation

```bash
pip install requests python-dotenv beautifulsoup4
```

For the Bright Data web app:

```bash
cd Scrapers/brightdata
pip install -r requirements.txt
```

For the n8n workflow:

1. Import `n8n Workflow/Scraping produits (1).json` into n8n
2. Create the PostgreSQL `products` table (see SQL above)
3. Configure Google Sheets OAuth2 credentials in n8n
4. Configure PostgreSQL connection in n8n
5. Update the script path in the Execute Command node to point to `shopify_scraper_step1.py`
6. Add Shopify store URLs to the Google Sheet with `Statut = "KO"`
7. Click "Execute workflow"

### Environment Variables (Bright Data scrapers)

Create `Scrapers/brightdata/.env.local`:

```
BRIGHTDATA_API_KEY=your_key
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_secret
GOOGLE_DRIVE_FOLDER_ID=your_folder_id
```
