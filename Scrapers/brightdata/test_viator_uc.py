"""
Test Viator scraper avec undetected-chromedriver
"""

import json
import time
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def scrape_viator(url: str):
    """Scrape Viator avec undetected-chromedriver"""

    print("Lancement du navigateur (undetected-chromedriver)...")

    options = uc.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--lang=en-US')

    # Lancer le driver
    driver = uc.Chrome(options=options, headless=False)

    try:
        print(f"Navigation vers: {url}")
        driver.get(url)

        # Attendre le chargement
        print("Attente du chargement de la page...")
        time.sleep(5)

        # Vérifier si on a un CAPTCHA
        page_source = driver.page_source
        if 'captcha' in page_source.lower() or 'datadome' in page_source.lower():
            print("⚠️  CAPTCHA détecté, attente...")
            time.sleep(10)
            page_source = driver.page_source

        # Sauvegarder le HTML
        with open("debug_viator_uc.html", "w") as f:
            f.write(page_source)
        print(f"HTML sauvegardé ({len(page_source)} bytes)")

        # Screenshot
        driver.save_screenshot("viator_uc.png")
        print("Screenshot sauvegardé")

        # Attendre les produits
        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'a[href*="/tours/"]'))
            )
            print("Produits trouvés!")
        except:
            print("Timeout en attendant les produits")

        # Extraire les produits
        products = extract_products(driver)
        print(f"\nProduits extraits: {len(products)}")

        return products

    except Exception as e:
        print(f"Erreur: {e}")
        driver.save_screenshot("viator_error.png")
        return []

    finally:
        driver.quit()


def extract_products(driver) -> list:
    """Extrait les produits de la page"""
    products = []

    # Chercher tous les liens vers des tours
    tour_links = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/tours/"]')
    print(f"Liens tours trouvés: {len(tour_links)}")

    # Chercher les cartes produits
    cards = driver.find_elements(By.CSS_SELECTOR, '[data-testid="product-card"]')
    if not cards:
        cards = driver.find_elements(By.CSS_SELECTOR, 'article')

    print(f"Cartes trouvées: {len(cards)}")

    seen_urls = set()

    for link in tour_links[:30]:
        try:
            href = link.get_attribute('href')
            if href and '/tours/' in href and href not in seen_urls:
                seen_urls.add(href)

                product = {'url': href}

                # Essayer de trouver le titre
                try:
                    # Remonter au parent pour trouver le contexte
                    parent = link.find_element(By.XPATH, './ancestor::article') or \
                             link.find_element(By.XPATH, './ancestor::div[contains(@class, "card")]')

                    title_el = parent.find_element(By.CSS_SELECTOR, 'h2, h3')
                    product['title'] = title_el.text

                    price_el = parent.find_element(By.CSS_SELECTOR, '[class*="rice"]')
                    product['price_text'] = price_el.text
                except:
                    # Juste utiliser le texte du lien
                    product['title'] = link.text[:100] if link.text else None

                if product.get('title') or product.get('url'):
                    products.append(product)

        except Exception as e:
            continue

    return products


if __name__ == "__main__":
    url = "https://www.viator.com/Canada/d75-ttd?sortType=external"

    print("=" * 60)
    print("Viator Scraper avec undetected-chromedriver")
    print("=" * 60)

    products = scrape_viator(url)

    if products:
        with open("viator_products.json", "w") as f:
            json.dump(products, f, indent=2, ensure_ascii=False)
        print(f"\n✅ {len(products)} produits sauvegardés dans viator_products.json")

        print("\nExemple:")
        print(json.dumps(products[0], indent=2, ensure_ascii=False))
    else:
        print("\n❌ Aucun produit trouvé")
