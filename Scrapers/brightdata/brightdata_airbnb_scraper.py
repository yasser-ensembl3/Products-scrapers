"""
Bright Data Airbnb Experiences Scraper
Scrape des expériences Airbnb depuis une page de recherche
"""

import requests
import json
import re
import os
from datetime import datetime
from typing import Optional, List
from bs4 import BeautifulSoup
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

    def fetch_url(self, url: str) -> Optional[str]:
        """Récupère le contenu d'une URL via Bright Data"""
        try:
            response = requests.post(
                BRIGHTDATA_ENDPOINT,
                headers=self.headers,
                json={
                    "zone": self.zone,
                    "url": url,
                    "format": "raw"
                },
                timeout=120
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
# EXPERIENCE PARSER
# =============================================================================

def extract_experiences_from_html(html_content: str) -> List[dict]:
    """Extraire les expériences depuis le HTML"""
    soup = BeautifulSoup(html_content, 'html.parser')
    experiences = []

    # Chercher le JSON niobeClientData dans les scripts
    scripts = soup.find_all('script')

    for script in scripts:
        if script.string and 'niobeClientData' in script.string:
            try:
                # Parser le JSON
                data = json.loads(script.string)
                niobe = data.get('niobeClientData', [])

                for item in niobe:
                    if isinstance(item, list) and len(item) >= 2:
                        value = item[1]
                        if isinstance(value, dict):
                            # Naviguer vers les résultats de recherche
                            search_results = (
                                value.get('data', {})
                                .get('presentation', {})
                                .get('experiencesSearch', {})
                                .get('results', {})
                                .get('searchResults', [])
                            )

                            for sr in search_results:
                                if sr.get('__typename') == 'ExperienceSearchResult':
                                    exp = extract_experience_data(sr)
                                    if exp:
                                        experiences.append(exp)

                if experiences:
                    return experiences

            except json.JSONDecodeError:
                continue

    return experiences


def extract_experience_data(sr: dict) -> Optional[dict]:
    """Extraire les données normalisées d'une expérience"""

    exp_id = sr.get('id')
    listing = sr.get('listing', {})

    # Titre
    title = None
    descriptions = listing.get('descriptions', {})
    name_obj = descriptions.get('name', {})
    localized_value = name_obj.get('localizedValue', {})
    title = localized_value.get('localizedStringWithTranslationPreference')

    if not title:
        return None

    # Description courte (byline)
    byline = None
    byline_obj = descriptions.get('byline', {})
    byline_localized = byline_obj.get('localizedValue', {})
    byline = byline_localized.get('localizedStringWithTranslationPreference')

    # Note et avis
    rating = None
    reviews_count = None
    rating_stats = listing.get('listingRatingStats', {})
    overall_stats = rating_stats.get('overallRatingStats', {})
    if overall_stats:
        rating = overall_stats.get('ratingAverage')
        reviews_count = overall_stats.get('ratingCount')
        if reviews_count:
            reviews_count = int(reviews_count)

    # Durée
    duration_minutes = None
    offerings = listing.get('offerings', {})
    published = offerings.get('publishedOfferings', {})
    edges = published.get('edges', [])
    if edges:
        node = edges[0].get('node', {})
        duration_minutes = node.get('durationMinutes')

    # Prix
    price = None
    price_label = None
    display_price = sr.get('displayPrice', {})
    primary_line = display_price.get('primaryLine', {})
    price_label = primary_line.get('accessibilityLabel')

    # Extraire le montant numérique du prix
    if price_label:
        price_match = re.search(r'(\d+(?:[.,]\d+)?)\s*[€$CAD]', price_label)
        if price_match:
            price = float(price_match.group(1).replace(',', '.'))

    # Catégorie
    category = sr.get('primaryThemeFormatted')

    # Image
    image_url = None
    picture = sr.get('picture', {})
    if picture:
        image_url = picture.get('poster')

    # URL
    url = f"https://fr.airbnb.com/experiences/{exp_id}"

    return {
        "id": exp_id,
        "title": title,
        "description": byline,
        "url": url,
        "price": price,
        "price_label": price_label,
        "currency": "EUR",
        "rating": float(rating) if rating else None,
        "reviews_count": reviews_count,
        "category": category,
        "duration_minutes": duration_minutes,
        "image_url": image_url,
        "scraped_at": datetime.utcnow().isoformat(),
    }


# =============================================================================
# MAIN SCRAPER
# =============================================================================

def scrape_airbnb_experiences(
    search_url: str,
    output_file: str = None
) -> List[dict]:
    """
    Scrape les expériences Airbnb depuis une page de recherche

    Args:
        search_url: URL de la page de recherche Airbnb
        output_file: Fichier JSON de sortie (optionnel)

    Returns:
        Liste des expériences
    """

    print("=" * 60)
    print("🎭 Bright Data Airbnb Experiences Scraper")
    print("=" * 60)
    print(f"URL: {search_url[:80]}...")
    print("=" * 60)

    client = BrightDataClient(BRIGHTDATA_API_KEY, BRIGHTDATA_ZONE)

    print("\n📥 Récupération de la page...")
    html_content = client.fetch_url(search_url)

    if not html_content:
        print("  ❌ Impossible de récupérer la page")
        return []

    print(f"  ✓ {len(html_content)} caractères reçus")

    print("\n🔍 Extraction des expériences...")
    experiences = extract_experiences_from_html(html_content)

    print(f"  ✓ {len(experiences)} expériences trouvées")

    # Export JSON
    if output_file and experiences:
        output = {
            "metadata": {
                "source": "brightdata_airbnb",
                "search_url": search_url,
                "scraped_at": datetime.utcnow().isoformat(),
                "total_experiences": len(experiences),
            },
            "experiences": experiences
        }

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        print(f"\n✅ {len(experiences)} expériences exportées vers {output_file}")

    # Résumé
    if experiences:
        print("\n" + "=" * 60)
        print("📈 Aperçu des expériences:")
        print("=" * 60)
        for i, exp in enumerate(experiences[:5], 1):
            title = (exp.get('title') or 'N/A')[:50]
            price = exp.get('price') or 'N/A'
            rating = exp.get('rating') or 'N/A'
            reviews = exp.get('reviews_count') or 0
            duration = exp.get('duration_minutes') or 'N/A'
            url = exp.get('url') or 'N/A'
            print(f"{i}. {title}...")
            print(f"   💰 {price}€ | ⭐ {rating} ({reviews} avis) | ⏱️ {duration} min")
            print(f"   🔗 {url}")
            print()

    return experiences


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    # Scraper les expériences à Québec
    experiences = scrape_airbnb_experiences(
        search_url="https://fr.airbnb.com/s/Qu%C3%A9bec--Canada/experiences?flexible_trip_lengths%5B%5D=one_week&monthly_start_date=2026-01-01&monthly_length=3&monthly_end_date=2026-04-01&rank_mode=default&refinement_paths%5B%5D=%2Fexperiences&place_id=ChIJk4jbBYqWuEwRAzro8GMtxY8&date_picker_type=calendar&checkin=2025-12-18&checkout=2025-12-31&adults=1&source=structured_search_input_header&search_type=AUTOSUGGEST",
        output_file="airbnb_quebec_experiences.json"
    )
