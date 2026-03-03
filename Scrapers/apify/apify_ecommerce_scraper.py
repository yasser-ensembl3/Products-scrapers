"""
Apify E-commerce Scraping Tool
Scrape des produits depuis n'importe quel site e-commerce
"""

import requests
import json
import time
from datetime import datetime
from typing import List, Optional

# =============================================================================
# CONFIGURATION
# =============================================================================

APIFY_API_TOKEN = "YOUR_APIFY_API_TOKEN"
APIFY_ACTOR = "apify~e-commerce-scraping-tool"
APIFY_BASE_URL = "https://api.apify.com/v2"

# =============================================================================
# API CLIENT
# =============================================================================

class ApifyClient:
    def __init__(self, api_token: str):
        self.api_token = api_token
        self.params = {"token": api_token}
        self.headers = {"Content-Type": "application/json"}

    def run_actor_sync(self, actor_id: str, input_data: dict, timeout: int = 300) -> Optional[List[dict]]:
        """
        Exécute un Actor de manière synchrone et retourne les résultats
        """
        url = f"{APIFY_BASE_URL}/acts/{actor_id}/run-sync-get-dataset-items"

        try:
            response = requests.post(
                url,
                params=self.params,
                headers=self.headers,
                json=input_data,
                timeout=timeout
            )

            if response.status_code in [200, 201]:
                return response.json()
            else:
                print(f"  ❌ Erreur {response.status_code}: {response.text[:200]}")
                return None

        except requests.exceptions.Timeout:
            print("  ❌ Timeout - la requête a pris trop de temps")
            return None
        except Exception as e:
            print(f"  ❌ Exception: {str(e)}")
            return None

    def run_actor_async(self, actor_id: str, input_data: dict) -> Optional[str]:
        """
        Lance un Actor de manière asynchrone et retourne le run_id
        """
        url = f"{APIFY_BASE_URL}/acts/{actor_id}/runs"

        response = requests.post(
            url,
            params=self.params,
            headers=self.headers,
            json=input_data,
            timeout=30
        )

        if response.status_code == 201:
            return response.json().get("data", {}).get("id")
        return None

    def wait_for_run(self, run_id: str, max_wait: int = 300) -> Optional[str]:
        """
        Attend qu'un run soit terminé et retourne le status
        """
        start = time.time()
        while time.time() - start < max_wait:
            response = requests.get(
                f"{APIFY_BASE_URL}/actor-runs/{run_id}",
                params=self.params
            )
            status = response.json().get("data", {}).get("status")

            if status in ["SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"]:
                return status

            time.sleep(5)

        return "TIMEOUT"

    def get_dataset_items(self, dataset_id: str) -> List[dict]:
        """
        Récupère les items d'un dataset
        """
        response = requests.get(
            f"{APIFY_BASE_URL}/datasets/{dataset_id}/items",
            params=self.params
        )
        if response.status_code == 200:
            return response.json()
        return []


# =============================================================================
# PRODUCT PROCESSOR
# =============================================================================

def normalize_product(raw_product: dict, source_url: str) -> dict:
    """
    Normalise les données d'un produit Apify
    """
    # Extraire le prix
    offers = raw_product.get("offers", {})
    price = None
    price_compare = None
    currency = "USD"

    if isinstance(offers, dict):
        price = offers.get("price")
        if price:
            price = float(price) if isinstance(price, str) else price
        currency = offers.get("priceCurrency", "USD")
    elif isinstance(offers, list) and offers:
        price = offers[0].get("price")
        if price:
            price = float(price) if isinstance(price, str) else price

    # Extraire la marque
    brand = raw_product.get("brand", {})
    brand_name = None
    if isinstance(brand, dict):
        brand_name = brand.get("name") or brand.get("slogan")
    elif isinstance(brand, str):
        brand_name = brand

    # Extraire les images
    images = []
    main_image = raw_product.get("image")
    if main_image:
        if isinstance(main_image, list):
            images = main_image
        else:
            images = [main_image]

    # Calculer discount
    discount_percent = None
    if price and price_compare and price_compare > price:
        discount_percent = round((1 - price / price_compare) * 100, 1)

    return {
        # Identifiants
        "url": raw_product.get("url"),
        "name": raw_product.get("name"),
        "sku": raw_product.get("sku"),
        "mpn": raw_product.get("mpn"),
        "gtin13": raw_product.get("gtin13"),

        # Prix
        "price": price,
        "price_compare": price_compare,
        "currency": currency,
        "discount_percent": discount_percent,

        # Disponibilité
        "availability": raw_product.get("availability"),
        "in_stock": raw_product.get("inStock"),

        # Marque
        "brand": brand_name,

        # Description
        "description": raw_product.get("description"),

        # Images
        "image_url": images[0] if images else None,
        "images": images,

        # Catégories
        "categories": raw_product.get("categories", []),

        # Avis
        "rating": raw_product.get("aggregateRating", {}).get("ratingValue") if raw_product.get("aggregateRating") else None,
        "review_count": raw_product.get("aggregateRating", {}).get("reviewCount") if raw_product.get("aggregateRating") else None,

        # Données additionnelles
        "additional_properties": raw_product.get("additionalProperties", []),

        # Métadonnées
        "source_url": source_url,
        "scraped_at": datetime.utcnow().isoformat(),
    }


# =============================================================================
# MAIN SCRAPER
# =============================================================================

def scrape_ecommerce(
    listing_urls: List[str] = None,
    product_urls: List[str] = None,
    search_urls: List[str] = None,
    scrape_mode: str = "BROWSER",
    additional_properties: bool = True,
    max_products: int = None,
    output_file: str = None
) -> List[dict]:
    """
    Scrape des produits e-commerce via Apify

    Args:
        listing_urls: URLs de pages de listing (catégories, collections)
        product_urls: URLs de pages produit individuelles
        search_urls: URLs de pages de recherche
        scrape_mode: "BROWSER" ou "HTTP"
        additional_properties: Récupérer les propriétés additionnelles
        max_products: Nombre max de produits
        output_file: Fichier JSON de sortie

    Returns:
        Liste des produits normalisés
    """

    print("=" * 60)
    print("🛒 Apify E-commerce Scraper")
    print("=" * 60)

    # Construire l'input
    input_data = {
        "additionalProperties": additional_properties,
        "additionalReviewProperties": True,
        "scrapeInfluencerProducts": False,
        "scrapeMode": scrape_mode
    }

    source_urls = []

    if listing_urls:
        input_data["listingUrls"] = [{"url": url} for url in listing_urls]
        source_urls.extend(listing_urls)
        print(f"Listing URLs: {len(listing_urls)}")

    if product_urls:
        input_data["productUrls"] = [{"url": url} for url in product_urls]
        source_urls.extend(product_urls)
        print(f"Product URLs: {len(product_urls)}")

    if search_urls:
        input_data["searchUrls"] = [{"url": url} for url in search_urls]
        source_urls.extend(search_urls)
        print(f"Search URLs: {len(search_urls)}")

    if max_products:
        input_data["maxItems"] = max_products

    print(f"Scrape mode: {scrape_mode}")
    print("=" * 60)

    # Exécuter le scraper
    print("\n📥 Lancement du scraper Apify...")
    client = ApifyClient(APIFY_API_TOKEN)

    raw_products = client.run_actor_sync(
        APIFY_ACTOR,
        input_data,
        timeout=600  # 10 minutes max
    )

    if not raw_products:
        print("  ❌ Aucun produit récupéré")
        return []

    print(f"  ✓ {len(raw_products)} produits bruts récupérés")

    # Normaliser les produits
    print("\n📊 Normalisation des produits...")
    products = []
    source_url = source_urls[0] if source_urls else ""

    for raw in raw_products:
        product = normalize_product(raw, source_url)
        products.append(product)

    print(f"  ✓ {len(products)} produits normalisés")

    # Export JSON
    if output_file:
        output = {
            "metadata": {
                "source": "apify_ecommerce",
                "source_urls": source_urls,
                "scraped_at": datetime.utcnow().isoformat(),
                "total_products": len(products),
                "scrape_mode": scrape_mode
            },
            "products": products
        }

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        print(f"\n✅ {len(products)} produits exportés vers {output_file}")

    # Résumé
    print("\n" + "=" * 60)
    print("📈 Top 5 produits:")
    print("=" * 60)
    for i, p in enumerate(products[:5], 1):
        name = p['name'][:45] if p['name'] else "N/A"
        price = p['price'] or 0
        brand = p['brand'] or "N/A"
        print(f"{i}. {name}...")
        print(f"   💰 ${price:.2f} | 🏷️ {brand}")
        print()

    return products


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    # Test avec Ashley HomeStore
    products = scrape_ecommerce(
        listing_urls=["https://ashleyhomestore.ca/collections/sofas"],
        scrape_mode="BROWSER",
        output_file="ashley_sofas.json"
    )
