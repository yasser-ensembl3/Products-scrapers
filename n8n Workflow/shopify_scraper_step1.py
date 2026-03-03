import requests
import re
import sys
import json
from urllib.parse import urlparse

def fetch_shopify_products(domain_url: str) -> dict:
    """Fetch products from Shopify store"""
    url = f"{domain_url}/products.json"
    params = {'limit': 125, 'sort_by': 'created_at', 'order': 'desc'}
    
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException:
        return None

def clean_html_description(html: str) -> str:
    """Remove HTML tags and clean description"""
    if not html:
        return ""
    text = re.sub(r'<[^>]*>', '', html)
    text = text.replace('&nbsp;', ' ')
    text = ' '.join(text.split())
    return text.strip()

def extract_domain(url: str) -> str:
    """Extract clean domain from URL"""
    parsed = urlparse(url)
    domain = parsed.netloc or parsed.path
    # Remove www. prefix
    domain = domain.replace('www.', '')
    return domain

def format_for_datatable(product: dict, domain: str, base_url: str) -> dict:
    """Format product data exactly as n8n DataTable expects"""
    variants = product.get('variants', [])
    images = product.get('images', [])
    
    description = clean_html_description(product.get('body_html', ''))
    
    return {
        'Website': domain,
        'handle': product.get('handle', ''),
        'sku': variants[0].get('sku', '') if variants else '',
        'title': product.get('title', ''),
        'Description': description,
        'vendor': product.get('vendor', ''),
        'price': float(variants[0].get('price', 0)) if variants else 0,
        'availabilty': variants[0].get('available', False) if variants else False,
        'image': images[0].get('src', '') if images else '',
        'categories': product.get('product_type', ''),
        'url': f"{base_url}/products/{product.get('handle', '')}"
    }

if __name__ == "__main__":
    # Check if URL argument is provided
    if len(sys.argv) < 2:
        sys.exit(1)
    
    # Get URL from command line argument
    domain_url = sys.argv[1].strip()
    
    # Ensure URL has protocol
    if not domain_url.startswith('http'):
        domain_url = f"https://{domain_url}"
    
    # Extract domain
    domain = extract_domain(domain_url)
    
    # Fetch products
    result = fetch_shopify_products(domain_url)
    
    if result and result.get('products'):
        products = result['products']
        
        # Format all products for DataTable
        formatted_products = [
            format_for_datatable(p, domain, domain_url) 
            for p in products
        ]
        
        # Output as JSON for n8n to consume
        print(json.dumps(formatted_products, ensure_ascii=False))
    else:
        sys.exit(1)