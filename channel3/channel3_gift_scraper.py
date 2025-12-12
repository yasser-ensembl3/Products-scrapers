"""
Channel3 Gift Products Scraper
Pour app de recommandation de cadeaux
"""

import json
from datetime import datetime
from typing import Optional
from channel3_sdk import Channel3

# =============================================================================
# CONFIGURATION
# =============================================================================

CHANNEL3_API_KEY = "YOUR_CHANNEL3_API_KEY"

# Seed keywords pour cadeaux (mêmes que Amazon scraper)
GIFT_KEYWORDS = [
    # Par relation
    "gift for mom",
    "gift for dad",
    "gift for wife",
    "gift for husband",
    "gift for boyfriend",
    "gift for girlfriend",
    "gift for best friend",
    "gift for grandma",
    "gift for grandpa",
    "gift for kids",
    "gift for teenager",
    "gift for coworker",

    # Par occasion
    "birthday gift",
    "christmas gift",
    "anniversary gift",
    "valentines day gift",
    "mothers day gift",
    "fathers day gift",
    "graduation gift",
    "wedding gift",
    "housewarming gift",
    "baby shower gift",

    # Par intérêt
    "gift for gamers",
    "gift for book lovers",
    "gift for cooks",
    "gift for travelers",
    "gift for fitness",
    "gift for gardeners",
    "gift for music lovers",
    "gift for artists",
    "gift for tech lovers",
    "gift for coffee lovers",
    "gift for wine lovers",
    "gift for pet owners",

    # Par type
    "unique gift ideas",
    "personalized gifts",
    "luxury gift",
    "funny gift",
    "practical gift",
    "experience gift box",
    "gift basket",
    "subscription box gift",

    # Par genre/âge
    "gift for men",
    "gift for women",
    "gift for boys",
    "gift for girls",
    "gift for toddler",
    "gift for senior",

    # Populaires
    "best seller gift",
    "trending gifts",
    "popular gift ideas",
]

# Filtres qualité
MIN_SCORE = 50  # Score de pertinence minimum (0-100)

# =============================================================================
# PRODUCT PROCESSOR
# =============================================================================

def extract_product_data(product, keyword: str) -> Optional[dict]:
    """Extraire et normaliser les données d'un produit Channel3"""

    # Skip si score trop bas
    score = getattr(product, 'score', 0) or 0
    if score < MIN_SCORE:
        return None

    # Skip gift cards et produits digitaux
    title = (getattr(product, 'title', '') or '').lower()
    excluded_terms = ["gift card", "egift", "e-gift", "digital code", "email delivery"]
    if any(term in title for term in excluded_terms):
        return None

    # Extraire prix
    price_obj = getattr(product, 'price', None)
    price_current = None
    price_compare = None
    currency = "USD"

    if price_obj:
        price_current = getattr(price_obj, 'price', None)
        price_compare = getattr(price_obj, 'compare_at_price', None)
        currency = getattr(price_obj, 'currency', 'USD')

    # Extraire images
    images = []
    images_list = getattr(product, 'images', []) or []
    for img in images_list[:5]:  # Max 5 images
        url = getattr(img, 'url', None)
        if url:
            images.append(url)

    # Image principale
    main_image = getattr(product, 'image_url', None)
    if main_image and main_image not in images:
        images.insert(0, main_image)

    # Extraire catégories
    categories = getattr(product, 'categories', []) or []

    # Extraire key features
    key_features = getattr(product, 'key_features', []) or []

    # Construire objet normalisé
    return {
        # Identifiants
        "id": getattr(product, 'id', None),
        "title": getattr(product, 'title', None),
        "url": getattr(product, 'url', None),

        # Prix
        "price_current": price_current,
        "price_compare": price_compare,
        "currency": currency,
        "discount_percent": round((1 - price_current / price_compare) * 100, 1) if price_current and price_compare and price_compare > price_current else None,

        # Score de pertinence Channel3
        "relevance_score": score,

        # Disponibilité
        "availability": getattr(product, 'availability', None),

        # Marque
        "brand_id": getattr(product, 'brand_id', None),
        "brand_name": getattr(product, 'brand_name', None),

        # Description
        "description": getattr(product, 'description', None),

        # Catégories
        "categories": categories,

        # Images
        "image_url": main_image,
        "images": images,

        # Caractéristiques
        "key_features": key_features,
        "materials": getattr(product, 'materials', []) or [],
        "gender": getattr(product, 'gender', None),

        # Métadonnées
        "search_keyword": keyword,
        "scraped_at": datetime.utcnow().isoformat(),
    }


# =============================================================================
# MAIN SCRAPER
# =============================================================================

def scrape_channel3_gifts(
    keywords: list = None,
    max_products: int = 100,
    products_per_keyword: int = 20,
    output_file: str = "channel3_gift_products.json"
):
    """
    Scrape Channel3 pour des produits cadeaux

    Args:
        keywords: Liste de keywords (défaut: GIFT_KEYWORDS)
        max_products: Nombre max de produits à retourner
        products_per_keyword: Nombre de produits à récupérer par keyword
        output_file: Fichier JSON de sortie
    """

    if keywords is None:
        keywords = GIFT_KEYWORDS

    client = Channel3(api_key=CHANNEL3_API_KEY)

    all_products = {}  # Dédupliqué par ID

    print("=" * 60)
    print("🎁 Channel3 Gift Products Scraper")
    print("=" * 60)
    print(f"Keywords: {len(keywords)}")
    print(f"Max products: {max_products}")
    print(f"Products per keyword: {products_per_keyword}")
    print("=" * 60)

    # Recherche pour chaque keyword
    print("\n📤 Recherche des produits...")

    for keyword in keywords:
        try:
            response = client.search.perform(
                query=keyword,
                limit=products_per_keyword
            )

            products_found = 0

            if isinstance(response, list):
                for raw_product in response:
                    product = extract_product_data(raw_product, keyword)

                    if product and product["id"]:
                        product_id = product["id"]

                        # Dédupliquer - garder celui avec le meilleur score
                        if product_id not in all_products or \
                           product["relevance_score"] > all_products[product_id]["relevance_score"]:
                            all_products[product_id] = product
                            products_found += 1

            print(f"  ✓ {keyword}: {products_found} produits")

        except Exception as e:
            print(f"  ❌ {keyword}: {str(e)}")

        # Stop si on a assez de produits
        if len(all_products) >= max_products * 2:
            print(f"\n⚠️ Limite atteinte, arrêt anticipé")
            break

    # Trier par score de pertinence
    print(f"\n📊 Traitement de {len(all_products)} produits uniques...")

    sorted_products = sorted(
        all_products.values(),
        key=lambda x: x["relevance_score"],
        reverse=True
    )[:max_products]

    # Export JSON
    output = {
        "metadata": {
            "source": "channel3",
            "scraped_at": datetime.utcnow().isoformat(),
            "total_products": len(sorted_products),
            "keywords_used": len(keywords),
            "filters": {
                "min_score": MIN_SCORE
            }
        },
        "products": sorted_products
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n✅ {len(sorted_products)} produits exportés vers {output_file}")

    # Résumé
    print("\n" + "=" * 60)
    print("📈 Top 5 produits par score de pertinence:")
    print("=" * 60)
    for i, p in enumerate(sorted_products[:5], 1):
        title = p['title'][:50] if p['title'] else "N/A"
        print(f"{i}. [{p['relevance_score']}] {title}...")
        print(f"   💰 {p['currency']} {p['price_current']} | 🏷️ {p['brand_name']}")
        print()

    return sorted_products


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    products = scrape_channel3_gifts(
        keywords=GIFT_KEYWORDS,
        max_products=100,
        products_per_keyword=20,
        output_file="channel3_gift_products_100.json"
    )
