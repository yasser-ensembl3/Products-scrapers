"""
Test Viator scraper avec Bright Data
"""

import os
import json
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv('.env.local')

BRIGHTDATA_API_KEY = os.getenv("BRIGHTDATA_API_KEY")
BRIGHTDATA_ENDPOINT = "https://api.brightdata.com/request"

def fetch_viator(url: str) -> str:
    """Récupère le contenu Viator via Bright Data"""

    # Headers de navigateur réalistes
    headers_to_send = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1"
    }

    response = requests.post(
        BRIGHTDATA_ENDPOINT,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {BRIGHTDATA_API_KEY}"
        },
        json={
            "zone": "web_unlocker1",
            "url": url,
            "format": "raw",
            "country": "ca",  # Canada
            "headers": headers_to_send
        },
        timeout=120
    )
    print(f"Status: {response.status_code}")
    print(f"Taille réponse: {len(response.text)} bytes")
    return response.text


def find_json_data(html: str) -> dict:
    """Cherche les données JSON dans le HTML"""
    soup = BeautifulSoup(html, 'html.parser')

    # Chercher __NEXT_DATA__ (Next.js)
    next_data = soup.find('script', id='__NEXT_DATA__')
    if next_data and next_data.string:
        print("✅ Trouvé __NEXT_DATA__")
        try:
            return json.loads(next_data.string)
        except:
            pass

    # Chercher dans tous les scripts
    for script in soup.find_all('script'):
        text = script.string or ''

        # Chercher des patterns de données
        patterns = [
            'window.__INITIAL_STATE__',
            'window.__DATA__',
            'window.VIATOR_DATA',
            '__PRELOADED_STATE__',
            'initialState',
            '"products":[',
            '"items":[',
            '"searchResults":'
        ]

        for pattern in patterns:
            if pattern in text:
                print(f"✅ Trouvé pattern: {pattern}")
                # Essayer d'extraire le JSON
                try:
                    # Chercher le JSON après le pattern
                    start = text.find('{')
                    if start >= 0:
                        # Trouver la fin du JSON
                        depth = 0
                        for i, c in enumerate(text[start:]):
                            if c == '{':
                                depth += 1
                            elif c == '}':
                                depth -= 1
                                if depth == 0:
                                    json_str = text[start:start+i+1]
                                    data = json.loads(json_str)
                                    return data
                except Exception as e:
                    print(f"   Erreur parse: {e}")

    return None


def extract_products_from_html(html: str) -> list:
    """Extrait les produits du HTML"""
    soup = BeautifulSoup(html, 'html.parser')
    products = []

    # Chercher les liens vers les tours
    tour_links = soup.find_all('a', href=lambda h: h and '/tours/' in h)
    print(f"Liens tours trouvés: {len(tour_links)}")

    # Chercher différents sélecteurs
    selectors_to_try = [
        '[data-testid="product-card"]',
        '[class*="product-card"]',
        '[class*="ProductCard"]',
        '[class*="tour-card"]',
        'article',
        '.card',
        '[itemtype*="Product"]'
    ]

    for selector in selectors_to_try:
        elements = soup.select(selector)
        if elements:
            print(f"Trouvé {len(elements)} avec '{selector}'")
            for el in elements[:3]:
                # Afficher un aperçu
                text = el.get_text(strip=True)[:100]
                print(f"  - {text}")

    # Afficher les premières lignes du body pour debug
    body = soup.find('body')
    if body:
        body_text = body.get_text(strip=True)[:500]
        print(f"\n--- Début du body ---\n{body_text}")

    return products


if __name__ == "__main__":
    url = "https://www.viator.com/Canada/d75-ttd?sortType=external"
    print(f"🕷️  Scraping Viator: {url}\n")

    html = fetch_viator(url)

    # Sauvegarder pour debug
    with open("debug_viator_js.html", "w") as f:
        f.write(html)
    print("HTML sauvegardé dans debug_viator_js.html\n")

    # Chercher les données JSON
    print("--- Recherche de données JSON ---")
    json_data = find_json_data(html)
    if json_data:
        print("Données JSON trouvées!")
        # Sauvegarder les données
        with open("viator_data.json", "w") as f:
            json.dump(json_data, f, indent=2)
        print("Données sauvegardées dans viator_data.json")

    # Extraire les produits du HTML
    print("\n--- Extraction des produits ---")
    products = extract_products_from_html(html)
    print(f"\n📦 Produits trouvés: {len(products)}")
