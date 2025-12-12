"""
Amazon Gift Products Scraper via DataForSEO API
Pour app de recommandation de cadeaux
"""

import requests
import base64
import time
import json
from datetime import datetime
from typing import Optional

# =============================================================================
# CONFIGURATION
# =============================================================================

# Remplace par tes credentials DataForSEO
DATAFORSEO_LOGIN = "YOUR_DATAFORSEO_LOGIN"
DATAFORSEO_PASSWORD = "YOUR_DATAFORSEO_PASSWORD"

BASE_URL = "https://api.dataforseo.com/v3"

# Locations
LOCATIONS = {
    "US": {"code": 2840, "language": "en_US", "domain": "amazon.com"},
    "CA": {"code": 2124, "language": "en_CA", "domain": "amazon.ca"},
}

# Seed keywords pour cadeaux (50 keywords diversifiés)
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
MIN_REVIEWS = 100
MIN_RATING = 4.0

# =============================================================================
# API CLIENT
# =============================================================================

class DataForSEOClient:
    def __init__(self, login: str, password: str):
        credentials = base64.b64encode(f"{login}:{password}".encode()).decode()
        self.headers = {
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/json"
        }
    
    def _post(self, endpoint: str, payload: list) -> dict:
        response = requests.post(
            f"{BASE_URL}{endpoint}",
            headers=self.headers,
            json=payload
        )
        return response.json()
    
    def _get(self, endpoint: str) -> dict:
        response = requests.get(
            f"{BASE_URL}{endpoint}",
            headers=self.headers
        )
        return response.json()
    
    def create_product_task(self, keyword: str, location_code: int, language_code: str) -> Optional[str]:
        """Créer une tâche de recherche produits Amazon"""
        payload = [{
            "keyword": keyword,
            "location_code": location_code,
            "language_code": language_code,
            "priority": 2,
            "depth": 20  # Nombre de résultats par page
        }]
        
        response = self._post("/merchant/amazon/products/task_post", payload)
        
        if response.get("status_code") == 20000:
            tasks = response.get("tasks", [])
            if tasks and tasks[0].get("id"):
                return tasks[0]["id"]
        
        print(f"  ❌ Erreur création tâche: {response.get('status_message')}")
        return None
    
    def get_tasks_ready(self) -> list:
        """Récupérer la liste des tâches prêtes"""
        response = self._get("/merchant/amazon/products/tasks_ready")
        
        if response.get("status_code") == 20000:
            tasks = response.get("tasks", [])
            if tasks and tasks[0].get("result"):
                return [r["id"] for r in tasks[0]["result"]]
        return []
    
    def get_task_results(self, task_id: str) -> Optional[dict]:
        """Récupérer les résultats d'une tâche"""
        response = self._get(f"/merchant/amazon/products/task_get/advanced/{task_id}")
        
        if response.get("status_code") == 20000:
            tasks = response.get("tasks", [])
            if tasks and tasks[0].get("result"):
                return tasks[0]["result"][0]
        return None


# =============================================================================
# PRODUCT PROCESSOR
# =============================================================================

def calculate_popularity_score(product: dict) -> float:
    """
    Calcule un score de popularité composite (0-100)
    Basé sur: rating, nombre de reviews, badges
    """
    score = 0.0
    
    # Rating (max 25 points)
    rating = product.get("rating", {})
    if rating:
        rating_value = rating.get("value", 0) or 0
        score += (rating_value / 5) * 25
    
    # Nombre de reviews (max 35 points) - logarithmique
    # DataForSEO: votes_count est dans rating, pas reviews_count
    rating_data = product.get("rating") or {}
    reviews_count = rating_data.get("votes_count", 0) if isinstance(rating_data, dict) else 0
    reviews_count = reviews_count or 0
    if reviews_count > 0:
        import math
        # 10 reviews = ~8 pts, 100 = ~17 pts, 1000 = ~25 pts, 10000 = ~35 pts
        score += min(35, math.log10(reviews_count + 1) * 8.75)
    
    # Amazon's Choice badge (15 points)
    if product.get("is_amazon_choice"):
        score += 15
    
    # Best Seller badge (15 points)
    if product.get("is_best_seller"):
        score += 15
    
    # Prime eligible (10 points)
    if product.get("is_prime"):
        score += 10
    
    return round(min(100, score), 2)


def extract_product_data(raw_product: dict, keyword: str, location: str) -> Optional[dict]:
    """Extraire et normaliser les données d'un produit"""

    # Filtres qualité
    rating = raw_product.get("rating") or {}
    rating_value = rating.get("value") if rating else None
    # DataForSEO utilise votes_count dans rating, pas reviews_count
    reviews_count = rating.get("votes_count", 0) if rating else 0
    reviews_count = reviews_count or 0
    
    # Skip gift cards et produits digitaux
    title = (raw_product.get("title") or "").lower()
    excluded_terms = ["gift card", "egift", "e-gift", "digital code", "email delivery"]
    if any(term in title for term in excluded_terms):
        return None

    # Skip produits obscurs
    if reviews_count < MIN_REVIEWS:
        return None
    if rating_value and rating_value < MIN_RATING:
        return None
    
    # Extraire prix (DataForSEO utilise price_from/price_to, pas price.current/regular)
    price_current = raw_product.get("price_from")
    price_regular = raw_product.get("price_to")
    currency = raw_product.get("currency", "USD")
    
    # Construire objet normalisé
    product = {
        # Identifiants (DataForSEO utilise data_asin, pas asin)
        "asin": raw_product.get("data_asin") or raw_product.get("asin"),
        "title": raw_product.get("title"),
        "url": raw_product.get("url"),
        
        # Prix
        "price_current": price_current,
        "price_regular": price_regular,
        "currency": currency,
        "discount_percent": None,
        
        # Ratings & Reviews
        "rating": rating_value,
        "reviews_count": reviews_count,
        
        # Badges & Indicateurs
        "is_amazon_choice": raw_product.get("is_amazon_choice", False),
        "is_best_seller": raw_product.get("is_best_seller", False),
        "is_prime": raw_product.get("is_prime", False),
        
        # Images
        "image_url": raw_product.get("image_url"),
        
        # Catégorisation
        "category": raw_product.get("category"),
        "seller": raw_product.get("seller"),
        
        # Métadonnées
        "search_keyword": keyword,
        "location": location,
        "scraped_at": datetime.utcnow().isoformat(),
        
        # Score calculé
        "popularity_score": 0
    }
    
    # Calculer discount
    if price_current and price_regular and price_regular > price_current:
        product["discount_percent"] = round((1 - price_current / price_regular) * 100, 1)
    
    # Calculer score popularité
    product["popularity_score"] = calculate_popularity_score(raw_product)
    
    return product


# =============================================================================
# MAIN SCRAPER
# =============================================================================

def scrape_amazon_gifts(
    keywords: list = None,
    locations: list = None,
    max_products: int = 5,
    output_file: str = "gift_products.json"
):
    """
    Scrape Amazon pour des produits cadeaux
    
    Args:
        keywords: Liste de keywords (défaut: GIFT_KEYWORDS)
        locations: Liste de locations ["US", "CA"] (défaut: les deux)
        max_products: Nombre max de produits à retourner
        output_file: Fichier JSON de sortie
    """
    
    if keywords is None:
        keywords = GIFT_KEYWORDS
    if locations is None:
        locations = ["US", "CA"]
    
    client = DataForSEOClient(DATAFORSEO_LOGIN, DATAFORSEO_PASSWORD)
    
    all_products = {}  # Dédupliqué par ASIN
    tasks_pending = []  # (task_id, keyword, location)
    
    print("=" * 60)
    print("🎁 Amazon Gift Products Scraper")
    print("=" * 60)
    print(f"Keywords: {len(keywords)}")
    print(f"Locations: {locations}")
    print(f"Max products: {max_products}")
    print("=" * 60)
    
    # Phase 1: Créer les tâches
    print("\n📤 Création des tâches...")
    
    for location_key in locations:
        loc = LOCATIONS[location_key]
        
        for keyword in keywords:
            # Stop si on a assez de produits en attente
            if len(tasks_pending) >= max_products * 2:
                break
                
            task_id = client.create_product_task(
                keyword=keyword,
                location_code=loc["code"],
                language_code=loc["language"]
            )
            
            if task_id:
                tasks_pending.append((task_id, keyword, location_key))
                print(f"  ✓ [{location_key}] {keyword}")
            
            time.sleep(0.1)  # Rate limiting
    
    print(f"\n⏳ {len(tasks_pending)} tâches créées, attente des résultats...")
    
    # Phase 2: Attendre et récupérer les résultats
    max_wait = 60  # secondes
    start_time = time.time()
    tasks_completed = set()
    
    while len(tasks_completed) < len(tasks_pending):
        if time.time() - start_time > max_wait:
            print("  ⚠️ Timeout atteint")
            break
        
        time.sleep(2)
        ready_ids = client.get_tasks_ready()
        
        for task_id, keyword, location in tasks_pending:
            if task_id in tasks_completed:
                continue
            
            if task_id in ready_ids:
                results = client.get_task_results(task_id)
                tasks_completed.add(task_id)
                
                if results and results.get("items"):
                    for raw_product in results["items"]:
                        product = extract_product_data(raw_product, keyword, location)
                        
                        if product and product["asin"]:
                            asin = product["asin"]
                            
                            # Dédupliquer - garder celui avec le meilleur score
                            if asin not in all_products or \
                               product["popularity_score"] > all_products[asin]["popularity_score"]:
                                all_products[asin] = product
                    
                    print(f"  ✓ [{location}] {keyword}: {len(results['items'])} produits")
                
                # Stop si on a assez
                if len(all_products) >= max_products:
                    break
        
        if len(all_products) >= max_products:
            break
    
    # Phase 3: Trier et exporter
    print(f"\n📊 Traitement de {len(all_products)} produits uniques...")
    
    # Trier par score de popularité
    sorted_products = sorted(
        all_products.values(),
        key=lambda x: x["popularity_score"],
        reverse=True
    )[:max_products]
    
    # Export JSON
    output = {
        "metadata": {
            "scraped_at": datetime.utcnow().isoformat(),
            "total_products": len(sorted_products),
            "locations": locations,
            "keywords_used": len(keywords),
            "filters": {
                "min_reviews": MIN_REVIEWS,
                "min_rating": MIN_RATING
            }
        },
        "products": sorted_products
    }
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ {len(sorted_products)} produits exportés vers {output_file}")
    
    # Résumé
    print("\n" + "=" * 60)
    print("📈 Top 5 produits par popularité:")
    print("=" * 60)
    for i, p in enumerate(sorted_products[:5], 1):
        print(f"{i}. [{p['popularity_score']:.0f}] {p['title'][:50]}...")
        print(f"   💰 {p['currency']} {p['price_current']} | ⭐ {p['rating']} ({p['reviews_count']} reviews)")
        print()
    
    return sorted_products


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    products = scrape_amazon_gifts(
        keywords=GIFT_KEYWORDS,  # Tous les keywords
        locations=["US"],
        max_products=100,
        output_file="gift_products_100.json"
    )
