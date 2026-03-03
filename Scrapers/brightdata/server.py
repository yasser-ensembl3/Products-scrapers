"""
Serveur local pour tester l'application
"""

import os
import json
import urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler
from dotenv import load_dotenv
import requests

# Charger les variables d'environnement
load_dotenv('.env.local')

# Importer les fonctions du scraper
import sys
sys.path.insert(0, os.path.dirname(__file__))
from api.scrape import scrape_airbnb, scrape_shopify

# Google OAuth Config
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
GOOGLE_DRIVE_FOLDER_ID = os.getenv('GOOGLE_DRIVE_FOLDER_ID')
REDIRECT_URI = 'http://localhost:8000/oauth/callback'

# Token storage (en mémoire pour le dev)
google_tokens = {}


class LocalHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory='public', **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)

        # OAuth callback
        if parsed.path == '/oauth/callback':
            query = urllib.parse.parse_qs(parsed.query)
            code = query.get('code', [None])[0]

            if code:
                # Échanger le code contre un token
                token_response = requests.post(
                    'https://oauth2.googleapis.com/token',
                    data={
                        'code': code,
                        'client_id': GOOGLE_CLIENT_ID,
                        'client_secret': GOOGLE_CLIENT_SECRET,
                        'redirect_uri': REDIRECT_URI,
                        'grant_type': 'authorization_code'
                    }
                )

                if token_response.status_code == 200:
                    tokens = token_response.json()
                    google_tokens['access_token'] = tokens.get('access_token')
                    google_tokens['refresh_token'] = tokens.get('refresh_token')

                    # Rediriger vers la page principale avec succès
                    self.send_response(302)
                    self.send_header('Location', '/?auth=success')
                    self.end_headers()
                    print("✅ Google Drive connecté!")
                    return

            # Erreur
            self.send_response(302)
            self.send_header('Location', '/?auth=error')
            self.end_headers()
            return

        # Auth status
        elif parsed.path == '/api/auth-status':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({
                'authenticated': bool(google_tokens.get('access_token'))
            }).encode())
            return

        # Auth URL
        elif parsed.path == '/api/auth-url':
            auth_url = (
                'https://accounts.google.com/o/oauth2/v2/auth?'
                f'client_id={GOOGLE_CLIENT_ID}&'
                f'redirect_uri={urllib.parse.quote(REDIRECT_URI)}&'
                'response_type=code&'
                'scope=https://www.googleapis.com/auth/drive.file&'
                'access_type=offline&'
                'prompt=consent'
            )
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({'url': auth_url}).encode())
            return

        # Fichier statique
        super().do_GET()

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        body = self.rfile.read(content_length)
        data = json.loads(body)

        # Scrape endpoint
        if self.path == '/api/scrape':
            url = data.get('url')
            scraper_type = data.get('scraper')

            print(f"\n🕷️  Scraping: {scraper_type}")
            print(f"📍 URL: {url[:60]}...")

            try:
                if scraper_type == 'airbnb':
                    results = scrape_airbnb(url)
                elif scraper_type == 'shopify':
                    results = scrape_shopify(url)
                else:
                    raise Exception(f"Scraper '{scraper_type}' non supporté")

                print(f"✅ {len(results)} résultats trouvés")

                response = {
                    "success": True,
                    "scraper": scraper_type,
                    "count": len(results),
                    "data": results
                }
                self.send_response(200)

            except Exception as e:
                print(f"❌ Erreur: {e}")
                response = {"success": False, "error": str(e)}
                self.send_response(500)

            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())

        # Save to Drive endpoint
        elif self.path == '/api/save-to-drive':
            if not google_tokens.get('access_token'):
                self.send_response(401)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Non authentifié"}).encode())
                return

            filename = data.get('filename', 'scrape_results.json')
            content = data.get('content')

            print(f"\n💾 Sauvegarde sur Drive: {filename}")

            try:
                # Metadata du fichier
                file_metadata = {
                    'name': filename,
                    'parents': [GOOGLE_DRIVE_FOLDER_ID],
                    'mimeType': 'application/json'
                }

                # Upload multipart
                boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'

                body_parts = []
                body_parts.append(f'--{boundary}'.encode())
                body_parts.append(b'Content-Type: application/json; charset=UTF-8')
                body_parts.append(b'')
                body_parts.append(json.dumps(file_metadata).encode())
                body_parts.append(f'--{boundary}'.encode())
                body_parts.append(b'Content-Type: application/json')
                body_parts.append(b'')
                body_parts.append(json.dumps(content, ensure_ascii=False, indent=2).encode())
                body_parts.append(f'--{boundary}--'.encode())

                multipart_body = b'\r\n'.join(body_parts)

                upload_response = requests.post(
                    'https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart',
                    headers={
                        'Authorization': f'Bearer {google_tokens["access_token"]}',
                        'Content-Type': f'multipart/related; boundary={boundary}'
                    },
                    data=multipart_body
                )

                if upload_response.status_code in [200, 201]:
                    file_info = upload_response.json()
                    print(f"✅ Fichier sauvegardé: {file_info.get('id')}")
                    response = {
                        "success": True,
                        "fileId": file_info.get('id'),
                        "filename": filename
                    }
                    self.send_response(200)
                else:
                    print(f"❌ Erreur Drive: {upload_response.text}")
                    response = {"success": False, "error": upload_response.text}
                    self.send_response(500)

            except Exception as e:
                print(f"❌ Exception: {e}")
                response = {"success": False, "error": str(e)}
                self.send_response(500)

            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())

        else:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()


if __name__ == '__main__':
    port = 8000
    server = HTTPServer(('localhost', port), LocalHandler)

    print("=" * 50)
    print("🚀 Scraper App - Serveur Local")
    print("=" * 50)
    print(f"➡️  Ouvrir: http://localhost:{port}")
    print("=" * 50)
    print("Ctrl+C pour arrêter\n")

    server.serve_forever()
