"""
Test Viator scraper avec Playwright (mode visible + anti-détection)
"""

import asyncio
import json
from playwright.async_api import async_playwright


async def scrape_viator(url: str):
    """Scrape Viator avec Playwright en mode visible"""

    async with async_playwright() as p:
        print("Lancement du navigateur (mode visible)...")

        # Utiliser Firefox (moins détecté que Chromium)
        browser = await p.firefox.launch(
            headless=False,
            args=['--width=1920', '--height=1080']
        )

        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            locale='en-CA',
            timezone_id='America/Toronto',
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )

        # Injecter des scripts anti-détection
        await context.add_init_script("""
            // Cacher webdriver
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });

            // Simuler plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [
                    {name: 'Chrome PDF Plugin'},
                    {name: 'Chrome PDF Viewer'},
                    {name: 'Native Client'}
                ]
            });

            // Languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-CA', 'en-US', 'en', 'fr']
            });

            // Platform
            Object.defineProperty(navigator, 'platform', {
                get: () => 'MacIntel'
            });

            // Chrome runtime
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {}
            };

            // Permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        """)

        page = await context.new_page()

        print(f"Navigation vers: {url}")

        try:
            # Naviguer
            response = await page.goto(url, wait_until='networkidle', timeout=60000)
            print(f"Status: {response.status if response else 'N/A'}")

            # Attendre un peu
            await page.wait_for_timeout(3000)

            # Vérifier le contenu
            html = await page.content()
            print(f"HTML: {len(html)} bytes")

            # CAPTCHA?
            if 'captcha' in html.lower() or 'datadome' in html.lower():
                print("⚠️  CAPTCHA détecté!")
                print("Le navigateur reste ouvert - résous le CAPTCHA manuellement si possible...")
                await page.wait_for_timeout(20000)  # 20 sec pour résoudre manuellement
                html = await page.content()

            # Sauvegarder
            with open("debug_viator_stealth.html", "w") as f:
                f.write(html)
            await page.screenshot(path="viator_stealth.png")

            # Extraire si pas de CAPTCHA
            if 'captcha' not in html.lower():
                try:
                    await page.wait_for_selector('a[href*="/tours/"]', timeout=10000)
                except:
                    pass

                products = await extract_products(page)
                print(f"\nProduits: {len(products)}")
                return products
            else:
                print("Toujours bloqué par CAPTCHA")
                return []

        except Exception as e:
            print(f"Erreur: {e}")
            return []

        finally:
            await browser.close()


async def extract_products(page) -> list:
    """Extrait les produits"""
    products = []
    seen = set()

    links = await page.query_selector_all('a[href*="/tours/"]')
    print(f"Liens tours trouvés: {len(links)}")

    for link in links[:30]:
        try:
            href = await link.get_attribute('href')
            if href and href not in seen and '/tours/' in href:
                seen.add(href)

                text = await link.inner_text()
                title = text.strip() if text else None

                if title and len(title) > 10:
                    products.append({
                        'title': title,
                        'url': f"https://www.viator.com{href}" if href.startswith('/') else href
                    })
        except:
            continue

    return products


if __name__ == "__main__":
    url = "https://www.viator.com/Canada/d75-ttd?sortType=external"

    print("=" * 60)
    print("Viator Scraper - Mode Visible")
    print("=" * 60)

    products = asyncio.run(scrape_viator(url))

    if products:
        with open("viator_products.json", "w") as f:
            json.dump(products, f, indent=2, ensure_ascii=False)
        print(f"\n✅ {len(products)} produits")
        print(json.dumps(products[0], indent=2, ensure_ascii=False))
    else:
        print("\n❌ Aucun produit")
