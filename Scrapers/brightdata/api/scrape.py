"""
Vercel Serverless Function - Scraper API
"""

import json
import re
import os
from http.server import BaseHTTPRequestHandler
from datetime import datetime
import requests
from bs4 import BeautifulSoup

# Configuration
BRIGHTDATA_API_KEY = os.getenv("BRIGHTDATA_API_KEY")
BRIGHTDATA_ZONE = "web_unlocker1"
BRIGHTDATA_ENDPOINT = "https://api.brightdata.com/request"


def fetch_url(url: str) -> str:
    """Récupère le contenu via Bright Data"""
    response = requests.post(
        BRIGHTDATA_ENDPOINT,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {BRIGHTDATA_API_KEY}"
        },
        json={"zone": BRIGHTDATA_ZONE, "url": url, "format": "raw"},
        timeout=120
    )
    if response.status_code == 200:
        return response.text
    raise Exception(f"Erreur {response.status_code}")


# =============================================================================
# AIRBNB SCRAPER
# =============================================================================

def scrape_airbnb(url: str) -> list:
    """Scrape les expériences Airbnb"""
    html = fetch_url(url)
    soup = BeautifulSoup(html, 'html.parser')
    experiences = []

    for script in soup.find_all('script'):
        if script.string and 'niobeClientData' in script.string:
            try:
                data = json.loads(script.string)
                niobe = data.get('niobeClientData', [])

                for item in niobe:
                    if isinstance(item, list) and len(item) >= 2:
                        value = item[1]
                        if isinstance(value, dict):
                            search_results = (
                                value.get('data', {})
                                .get('presentation', {})
                                .get('experiencesSearch', {})
                                .get('results', {})
                                .get('searchResults', [])
                            )

                            for sr in search_results:
                                if sr.get('__typename') == 'ExperienceSearchResult':
                                    exp = parse_airbnb_experience(sr)
                                    if exp:
                                        experiences.append(exp)
            except json.JSONDecodeError:
                continue

    return experiences


def parse_airbnb_experience(sr: dict) -> dict:
    """Parse une expérience Airbnb"""
    exp_id = sr.get('id')
    listing = sr.get('listing', {})

    # Titre
    title = (listing.get('descriptions', {})
             .get('name', {})
             .get('localizedValue', {})
             .get('localizedStringWithTranslationPreference'))
    if not title:
        return None

    # Description
    description = (listing.get('descriptions', {})
                   .get('byline', {})
                   .get('localizedValue', {})
                   .get('localizedStringWithTranslationPreference'))

    # Rating
    rating_stats = listing.get('listingRatingStats', {}).get('overallRatingStats', {})
    rating = rating_stats.get('ratingAverage')
    reviews_count = rating_stats.get('ratingCount')

    # Durée
    edges = listing.get('offerings', {}).get('publishedOfferings', {}).get('edges', [])
    duration = edges[0].get('node', {}).get('durationMinutes') if edges else None

    # Prix
    price_label = sr.get('displayPrice', {}).get('primaryLine', {}).get('accessibilityLabel')
    price = None
    if price_label:
        match = re.search(r'(\d+(?:[.,]\d+)?)\s*[€$]', price_label)
        if match:
            price = float(match.group(1).replace(',', '.'))

    # Image
    image_url = sr.get('picture', {}).get('poster')

    return {
        "id": exp_id,
        "title": title,
        "description": description,
        "url": f"https://fr.airbnb.com/experiences/{exp_id}",
        "price": price,
        "price_label": price_label,
        "currency": "EUR",
        "rating": float(rating) if rating else None,
        "reviews_count": int(reviews_count) if reviews_count else None,
        "category": sr.get('primaryThemeFormatted'),
        "duration_minutes": duration,
        "image_url": image_url,
        "scraped_at": datetime.utcnow().isoformat()
    }


# =============================================================================
# SHOPIFY SCRAPER
# =============================================================================

def scrape_shopify(url: str, max_products: int = 50) -> list:
    """Scrape une collection Shopify"""
    products = []
    page = 1

    while len(products) < max_products:
        json_url = f"{url}/products.json?limit=250&page={page}"
        content = fetch_url(json_url)

        try:
            data = json.loads(content)
            items = data.get("products", [])

            if not items:
                break

            for raw in items:
                if len(products) >= max_products:
                    break
                products.append(parse_shopify_product(raw, url))

            if len(items) < 250:
                break
            page += 1

        except json.JSONDecodeError:
            break

    return products


def parse_shopify_product(raw: dict, collection_url: str) -> dict:
    """Parse un produit Shopify"""
    variants = raw.get("variants", [])

    price_current = None
    price_compare = None
    available = False
    sku = None

    if variants:
        v = variants[0]
        price_current = float(v.get("price", 0))
        if v.get("compare_at_price"):
            price_compare = float(v["compare_at_price"])
        available = v.get("available", False)
        sku = v.get("sku")

    discount = None
    if price_current and price_compare and price_compare > price_current:
        discount = round((1 - price_current / price_compare) * 100, 1)

    images = raw.get("images", [])
    image_url = images[0].get("src") if images else None

    handle = raw.get("handle", "")
    base_url = collection_url.split("/collections/")[0]

    return {
        "id": raw.get("id"),
        "title": raw.get("title"),
        "url": f"{base_url}/products/{handle}",
        "price_current": price_current,
        "price_compare": price_compare,
        "currency": "USD",
        "discount_percent": discount,
        "available": available,
        "sku": sku,
        "vendor": raw.get("vendor"),
        "image_url": image_url,
        "scraped_at": datetime.utcnow().isoformat()
    }


# =============================================================================
# HANDLER
# =============================================================================

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        body = self.rfile.read(content_length)
        data = json.loads(body)

        url = data.get('url')
        scraper_type = data.get('scraper')

        try:
            if scraper_type == 'airbnb':
                results = scrape_airbnb(url)
            elif scraper_type == 'shopify':
                results = scrape_shopify(url)
            else:
                raise Exception(f"Scraper '{scraper_type}' non supporté")

            response = {
                "success": True,
                "scraper": scraper_type,
                "count": len(results),
                "data": results
            }
            self.send_response(200)

        except Exception as e:
            response = {"success": False, "error": str(e)}
            self.send_response(500)

        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
