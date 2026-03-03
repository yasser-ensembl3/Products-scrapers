"""
Bright Data Shopify Scraper
Scrape des produits depuis n'importe quel site Shopify
"""

import requests
import json
import re
import os
from datetime import datetime
from typing import Optional, List
from html import unescape
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv('.env.local')

# =============================================================================
# CONFIGURATION
# =============================================================================

BRIGHTDATA_API_KEY = os.getenv("BRIGHTDATA_API_KEY")
BRIGHTDATA_ZONE = "web_unlocker1"
BRIGHTDATA_ENDPOINT = "https://api.brightdata.com/request"

# =============================================================================
# API CLIENT
# =============================================================================

class BrightDataClient:
    def __init__(self, api_key: str, zone: str):
        self.api_key = api_key
        self.zone = zone
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

    def fetch_url(self, url: str, format: str = "raw") -> Optional[str]:
        """Récupère le contenu d'une URL via Bright Data"""
        try:
            response = requests.post(
                BRIGHTDATA_ENDPOINT,
                headers=self.headers,
                json={
                    "zone": self.zone,
                    "url": url,
                    "format": format
                },
                timeout=60
            )
            if response.status_code == 200:
                return response.text
            else:
                print(f"  ❌ Erreur {response.status_code}: {response.text[:200]}")
                return None
        except Exception as e:
            print(f"  ❌ Exception: {str(e)}")
            return None


# =============================================================================
# PRODUCT PROCESSOR
# =============================================================================

def clean_html(html_text: str) -> str:
    """Nettoie le HTML pour extraire le texte"""
    if not html_text:
        return ""
    # Supprimer les tags HTML
    clean = re.sub(r'<[^>]+>', ' ', html_text)
    # Décoder les entités HTML
    clean = unescape(clean)
    # Nettoyer les espaces multiples
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean


def extract_product_data(raw_product: dict, collection_url: str) -> dict:
    """Extraire et normaliser les données d'un produit Shopify"""

    # Extraire les variantes (prix, SKU, stock)
    variants = raw_product.get("variants", [])

    # Prix du premier variant disponible
    price_current = None
    price_compare = None
    currency = "USD"
    available = False
    sku = None

    if variants:
        first_variant = variants[0]
        price_current = float(first_variant.get("price", 0))
        compare_price = first_variant.get("compare_at_price")
        if compare_price:
            price_compare = float(compare_price)
        available = first_variant.get("available", False)
        sku = first_variant.get("sku")

    # Extraire toutes les variantes
    all_variants = []
    for v in variants:
        all_variants.append({
            "id": v.get("id"),
            "title": v.get("title"),
            "sku": v.get("sku"),
            "price": float(v.get("price", 0)) if v.get("price") else None,
            "compare_at_price": float(v.get("compare_at_price")) if v.get("compare_at_price") else None,
            "available": v.get("available", False),
            "option1": v.get("option1"),
            "option2": v.get("option2"),
            "option3": v.get("option3"),
        })

    # Extraire les images
    images = []
    for img in raw_product.get("images", []):
        images.append({
            "id": img.get("id"),
            "src": img.get("src"),
            "alt": img.get("alt"),
            "width": img.get("width"),
            "height": img.get("height"),
        })

    # Image principale
    main_image = images[0]["src"] if images else None

    # Extraire les options (taille, couleur, etc.)
    options = []
    for opt in raw_product.get("options", []):
        options.append({
            "name": opt.get("name"),
            "values": opt.get("values", [])
        })

    # Calculer discount
    discount_percent = None
    if price_current and price_compare and price_compare > price_current:
        discount_percent = round((1 - price_current / price_compare) * 100, 1)

    # Construire l'URL du produit
    handle = raw_product.get("handle", "")
    base_url = collection_url.split("/collections/")[0]
    product_url = f"{base_url}/products/{handle}"

    return {
        # Identifiants
        "id": raw_product.get("id"),
        "handle": handle,
        "title": raw_product.get("title"),
        "url": product_url,

        # Prix
        "price_current": price_current,
        "price_compare": price_compare,
        "currency": currency,
        "discount_percent": discount_percent,

        # Disponibilité
        "available": available,
        "sku": sku,

        # Marque / Vendeur
        "vendor": raw_product.get("vendor"),
        "product_type": raw_product.get("product_type"),

        # Description
        "description": clean_html(raw_product.get("body_html", "")),

        # Tags
        "tags": raw_product.get("tags", []),

        # Images
        "image_url": main_image,
        "images": images,

        # Variantes
        "variants": all_variants,
        "options": options,

        # Dates
        "published_at": raw_product.get("published_at"),
        "updated_at": raw_product.get("updated_at"),

        # Métadonnées scraping
        "source_collection": collection_url,
        "scraped_at": datetime.utcnow().isoformat(),
    }


# =============================================================================
# MAIN SCRAPER
# =============================================================================

def scrape_shopify_collection(
    collection_url: str,
    max_products: int = 250,
    output_file: str = None
) -> List[dict]:
    """
    Scrape une collection Shopify via Bright Data

    Args:
        collection_url: URL de la collection (ex: https://site.com/collections/best-sellers)
        max_products: Nombre max de produits à récupérer
        output_file: Fichier JSON de sortie (optionnel)

    Returns:
        Liste des produits
    """

    print("=" * 60)
    print("🛍️  Bright Data Shopify Scraper")
    print("=" * 60)
    print(f"Collection: {collection_url}")
    print(f"Max products: {max_products}")
    print("=" * 60)

    client = BrightDataClient(BRIGHTDATA_API_KEY, BRIGHTDATA_ZONE)
    all_products = []
    page = 1

    # Shopify limite à 250 produits par page
    products_per_page = min(250, max_products)

    while len(all_products) < max_products:
        # Construire l'URL JSON
        json_url = f"{collection_url}/products.json?limit={products_per_page}&page={page}"

        print(f"\n📥 Page {page}: {json_url}")

        content = client.fetch_url(json_url)

        if not content:
            print("  ⚠️ Pas de contenu, arrêt")
            break

        try:
            data = json.loads(content)
            products = data.get("products", [])

            if not products:
                print("  ✓ Fin des produits")
                break

            for raw_product in products:
                if len(all_products) >= max_products:
                    break

                product = extract_product_data(raw_product, collection_url)
                all_products.append(product)

            print(f"  ✓ {len(products)} produits récupérés (total: {len(all_products)})")

            # Page suivante
            if len(products) < products_per_page:
                break
            page += 1

        except json.JSONDecodeError as e:
            print(f"  ❌ Erreur JSON: {e}")
            break

    # Export JSON
    if output_file:
        output = {
            "metadata": {
                "source": "brightdata_shopify",
                "collection_url": collection_url,
                "scraped_at": datetime.utcnow().isoformat(),
                "total_products": len(all_products),
            },
            "products": all_products
        }

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        print(f"\n✅ {len(all_products)} produits exportés vers {output_file}")

    # Résumé
    print("\n" + "=" * 60)
    print("📈 Top 5 produits:")
    print("=" * 60)
    for i, p in enumerate(all_products[:5], 1):
        title = p['title'][:45] if p['title'] else "N/A"
        price = p['price_current'] or 0
        print(f"{i}. {title}...")
        print(f"   💰 ${price:.2f} | 🏷️ {p['vendor']} | {'✓ Dispo' if p['available'] else '✗ Indispo'}")
        print()

    return all_products


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    # Test avec Sol de Janeiro
    products = scrape_shopify_collection(
        collection_url="https://soldejaneiro.com/collections/best-sellers",
        max_products=100,
        output_file="soldejaneiro_products.json"
    )
