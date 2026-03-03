"""
Zyte E-commerce Scraper
Scrape des produits depuis n'importe quel site e-commerce avec AI extraction
"""

import requests
import json
import time
from datetime import datetime
from typing import List, Optional

# =============================================================================
# CONFIGURATION
# =============================================================================

ZYTE_API_KEY = "YOUR_ZYTE_API_KEY"
ZYTE_ENDPOINT = "https://api.zyte.com/v1/extract"

# =============================================================================
# API CLIENT
# =============================================================================

class ZyteClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.auth = (api_key, "")

    def extract_product_list(self, url: str, timeout: int = 120) -> Optional[dict]:
        """
        Extrait la liste des produits d'une page de collection/catégorie
        """
        try:
            response = requests.post(
                ZYTE_ENDPOINT,
                auth=self.auth,
                json={
                    "url": url,
                    "productList": True
                },
                timeout=timeout
            )

            if response.status_code == 200:
                return response.json()
            else:
                print(f"  ❌ Erreur {response.status_code}: {response.text[:200]}")
                return None

        except requests.exceptions.Timeout:
            print("  ❌ Timeout")
            return None
        except Exception as e:
            print(f"  ❌ Exception: {str(e)}")
            return None

    def extract_product_navigation(self, url: str, timeout: int = 120) -> Optional[dict]:
        """
        Extrait les liens de navigation (pagination, catégories)
        """
        try:
            response = requests.post(
                ZYTE_ENDPOINT,
                auth=self.auth,
                json={
                    "url": url,
                    "productNavigation": True
                },
                timeout=timeout
            )

            if response.status_code == 200:
                return response.json()
            return None

        except Exception as e:
            print(f"  ❌ Exception: {str(e)}")
            return None

    def extract_product(self, url: str, timeout: int = 60) -> Optional[dict]:
        """
        Extrait les détails d'un produit individuel
        """
        try:
            response = requests.post(
                ZYTE_ENDPOINT,
                auth=self.auth,
                json={
                    "url": url,
                    "product": True
                },
                timeout=timeout
            )

            if response.status_code == 200:
                return response.json().get("product")
            return None

        except Exception as e:
            return None


# =============================================================================
# PRODUCT PROCESSOR
# =============================================================================

def normalize_product(raw_product: dict, source_url: str) -> dict:
    """
    Normalise les données d'un produit Zyte
    """
    # Extraire le prix
    price = raw_product.get("price")
    if price:
        price = float(price) if isinstance(price, str) else price

    # Extraire l'image
    main_image = raw_product.get("mainImage", {})
    image_url = main_image.get("url") if isinstance(main_image, dict) else main_image

    # Extraire les images additionnelles
    images = []
    if image_url:
        images.append(image_url)
    for img in raw_product.get("images", []):
        img_url = img.get("url") if isinstance(img, dict) else img
        if img_url and img_url not in images:
            images.append(img_url)

    return {
        # Identifiants
        "url": raw_product.get("url"),
        "name": raw_product.get("name"),
        "sku": raw_product.get("sku"),
        "mpn": raw_product.get("mpn"),
        "gtin": raw_product.get("gtin"),

        # Prix
        "price": price,
        "price_regular": raw_product.get("regularPrice"),
        "currency": raw_product.get("currency", "USD"),
        "currency_raw": raw_product.get("currencyRaw"),

        # Disponibilité
        "availability": raw_product.get("availability"),

        # Marque
        "brand": raw_product.get("brand"),

        # Description
        "description": raw_product.get("description"),

        # Images
        "image_url": image_url,
        "images": images,

        # Catégorie
        "breadcrumbs": raw_product.get("breadcrumbs", []),

        # Avis
        "rating": raw_product.get("aggregateRating", {}).get("ratingValue") if raw_product.get("aggregateRating") else None,
        "review_count": raw_product.get("aggregateRating", {}).get("reviewCount") if raw_product.get("aggregateRating") else None,

        # Métadonnées Zyte
        "probability": raw_product.get("metadata", {}).get("probability"),

        # Métadonnées scraping
        "source_url": source_url,
        "scraped_at": datetime.utcnow().isoformat(),
    }


# =============================================================================
# MAIN SCRAPER
# =============================================================================

def scrape_zyte_products(
    collection_url: str,
    max_products: int = 100,
    output_file: str = None
) -> List[dict]:
    """
    Scrape des produits e-commerce via Zyte API

    Args:
        collection_url: URL de la page de collection/catégorie
        max_products: Nombre max de produits à récupérer
        output_file: Fichier JSON de sortie

    Returns:
        Liste des produits normalisés
    """

    print("=" * 60)
    print("🎮 Zyte E-commerce Scraper")
    print("=" * 60)
    print(f"Collection: {collection_url}")
    print(f"Max products: {max_products}")
    print("=" * 60)

    client = ZyteClient(ZYTE_API_KEY)
    all_products = {}  # Dédupliqué par URL
    pages_scraped = 0
    current_url = collection_url

    while len(all_products) < max_products:
        pages_scraped += 1
        print(f"\n📥 Page {pages_scraped}: {current_url[:70]}...")

        # Extraire les produits de la page
        data = client.extract_product_list(current_url)

        if not data:
            print("  ⚠️ Pas de données, arrêt")
            break

        product_list = data.get("productList", {})
        products = product_list.get("products", [])

        if not products:
            print("  ✓ Fin des produits")
            break

        # Normaliser et ajouter les produits
        for raw in products:
            if len(all_products) >= max_products:
                break

            product = normalize_product(raw, current_url)
            if product["url"]:
                all_products[product["url"]] = product

        print(f"  ✓ {len(products)} produits (total: {len(all_products)})")

        # Chercher la page suivante
        nav_data = client.extract_product_navigation(current_url)
        if nav_data:
            nav = nav_data.get("productNavigation", {})
            next_page = nav.get("nextPage")

            if next_page and next_page.get("url"):
                next_url = next_page["url"]
                if next_url != current_url:
                    current_url = next_url
                    time.sleep(1)  # Rate limiting
                    continue

        # Pas de page suivante trouvée
        break

    products_list = list(all_products.values())

    # Export JSON
    if output_file:
        output = {
            "metadata": {
                "source": "zyte",
                "collection_url": collection_url,
                "scraped_at": datetime.utcnow().isoformat(),
                "total_products": len(products_list),
                "pages_scraped": pages_scraped
            },
            "products": products_list
        }

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        print(f"\n✅ {len(products_list)} produits exportés vers {output_file}")

    # Résumé
    print("\n" + "=" * 60)
    print("📈 Top 5 produits:")
    print("=" * 60)
    for i, p in enumerate(products_list[:5], 1):
        name = p['name'][:45] if p['name'] else "N/A"
        price = p['price'] or 0
        currency = p['currency'] or "CAD"
        print(f"{i}. {name}...")
        print(f"   💰 {currency} {price}")
        print()

    return products_list


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    products = scrape_zyte_products(
        collection_url="https://videogamesplus.ca/collections/all",
        max_products=100,
        output_file="videogamesplus_products.json"
    )
