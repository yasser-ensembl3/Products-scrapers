"""
Test Viator scraper avec Playwright + Bright Data Proxy
"""

import asyncio
import json
import os
from playwright.async_api import async_playwright
from dotenv import load_dotenv

load_dotenv('.env.local')

# Configuration Bright Data - on va essayer d'utiliser l'API key comme password
# Format: brd-customer-CUSTOMER_ID-zone-ZONE_NAME:PASSWORD@brd.superproxy.io:22225
# Avec l'API key, on peut aussi essayer le format de proxy direct

BRIGHTDATA_API_KEY = os.getenv("BRIGHTDATA_API_KEY")


async def scrape_viator_with_proxy(url: str):
    """Scrape Viator avec Playwright + Bright Data proxy"""

    async with async_playwright() as p:
        # Configuration du proxy Bright Data
        # Le format peut varier - essayons avec le web_unlocker
        proxy_config = {
            "server": "http://brd.superproxy.io:22225",
            "username": "brd-customer-hl_4a3e4949-zone-web_unlocker1",
            "password": BRIGHTDATA_API_KEY
        }

        print(f"Utilisation du proxy Bright Data...")

        # Lancer le navigateur avec le proxy
        browser = await p.chromium.launch(
            headless=True,
            proxy=proxy_config,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-blink-features=AutomationControlled'
            ]
        )

        # Contexte avec anti-détection
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            locale='en-US',
            timezone_id='America/New_York',
            permissions=['geolocation'],
            geolocation={'latitude': 43.6532, 'longitude': -79.3832},  # Toronto
            color_scheme='light'
        )

        # Ajouter des scripts anti-détection
        await context.add_init_script("""
            // Masquer webdriver
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});

            // Masquer le fait que c'est headless
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});

            // Masquer automation
            window.chrome = {runtime: {}};
        """)

        page = await context.new_page()

        print(f"Navigation vers: {url}")

        try:
            # Aller sur la page
            response = await page.goto(url, wait_until='domcontentloaded', timeout=90000)
            print(f"Status: {response.status}")

            # Attendre un peu que le JS s'exécute
            await page.wait_for_timeout(5000)

            # Attendre le contenu
            print("Attente du chargement...")

            selectors = [
                '[data-testid="product-card"]',
                '.product-card',
                'a[href*="/tours/"]',
                '[class*="ProductCard"]',
                'article'
            ]

            for selector in selectors:
                try:
                    await page.wait_for_selector(selector, timeout=15000)
                    print(f"Trouvé: {selector}")
                    break
                except:
                    continue

            # Sauvegarder
            html = await page.content()
            with open("debug_viator_playwright.html", "w") as f:
                f.write(html)
            print(f"HTML sauvegardé ({len(html)} bytes)")

            await page.screenshot(path="viator_screenshot.png", full_page=False)
            print("Screenshot sauvegardé")

            # Vérifier si on a une page CAPTCHA
            if 'captcha' in html.lower() or 'datadome' in html.lower():
                print("\n⚠️  CAPTCHA détecté - le proxy n'a pas contourné la protection")
            else:
                products = await extract_products(page)
                print(f"\nProduits trouvés: {len(products)}")
                return products

            return []

        except Exception as e:
            print(f"Erreur: {e}")
            html = await page.content()
            with open("debug_viator_error.html", "w") as f:
                f.write(html)
            await page.screenshot(path="viator_error.png")
            return []

        finally:
            await browser.close()


async def scrape_viator_stealth(url: str):
    """Essayer sans proxy mais avec stealth maximal"""

    async with async_playwright() as p:
        print("Mode stealth sans proxy...")

        browser = await p.chromium.launch(
            headless=False,  # Mode visible pour éviter détection
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-infobars',
                '--window-size=1920,1080'
            ]
        )

        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            locale='en-CA',
            timezone_id='America/Toronto'
        )

        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-CA', 'en-US', 'en']});
            window.chrome = {runtime: {}};
        """)

        page = await context.new_page()

        try:
            await page.goto(url, wait_until='networkidle', timeout=60000)
            await page.wait_for_timeout(3000)

            html = await page.content()
            with open("debug_viator_stealth.html", "w") as f:
                f.write(html)
            print(f"HTML sauvegardé ({len(html)} bytes)")

            await page.screenshot(path="viator_stealth.png")

            if 'captcha' in html.lower():
                print("⚠️  CAPTCHA détecté")
                return []

            products = await extract_products(page)
            return products

        finally:
            await browser.close()


async def extract_products(page) -> list:
    """Extrait les produits de la page"""
    products = []

    cards = await page.query_selector_all('[data-testid="product-card"]')
    if not cards:
        cards = await page.query_selector_all('[class*="ProductCard"]')
    if not cards:
        cards = await page.query_selector_all('a[href*="/tours/"]')

    print(f"Cartes trouvées: {len(cards)}")

    for card in cards[:20]:
        try:
            product = {}

            title_el = await card.query_selector('h3, h2, [class*="title"]')
            if title_el:
                product['title'] = await title_el.inner_text()

            link_el = await card.query_selector('a[href*="/tours/"]')
            if not link_el:
                link_el = card if await card.get_attribute('href') else None
            if link_el:
                href = await link_el.get_attribute('href')
                if href:
                    product['url'] = f"https://www.viator.com{href}" if href.startswith('/') else href

            price_el = await card.query_selector('[class*="rice"]')
            if price_el:
                product['price_text'] = await price_el.inner_text()

            if product.get('title') or product.get('url'):
                products.append(product)

        except Exception as e:
            continue

    return products


if __name__ == "__main__":
    url = "https://www.viator.com/Canada/d75-ttd?sortType=external"

    print("=" * 50)
    print("Test 1: Avec proxy Bright Data")
    print("=" * 50)
    products = asyncio.run(scrape_viator_with_proxy(url))

    if not products:
        print("\n" + "=" * 50)
        print("Test 2: Mode stealth (navigateur visible)")
        print("=" * 50)
        products = asyncio.run(scrape_viator_stealth(url))

    if products:
        with open("viator_products.json", "w") as f:
            json.dump(products, f, indent=2, ensure_ascii=False)
        print(f"\n✅ {len(products)} produits sauvegardés")
    else:
        print("\n❌ Aucun produit trouvé")
