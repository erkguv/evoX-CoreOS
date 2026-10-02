import os
import re
import json
import hashlib
import zipfile
import subprocess
import urllib.request
from scripts.config_rules import REPO_RULES, DEFAULT_REPO_CONFIG, BASE_URL

def parse_opml_file(opml_path):
    """Parse basique d'un fichier OPML pour en extraire les flux/dépôts."""
    entries = []
    if not os.path.exists(opml_path):
        return entries
    
    with open(opml_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    outline_matches = re.findall(r'<outline([^>]+)>', content, re.IGNORECASE)
    for match in outline_matches:
        title_match = re.search(r'title=["\']([^"\']+)["\']', match, re.IGNORECASE)
        url_match = re.search(r'xmlUrl=["\']([^"\']+)["\']', match, re.IGNORECASE)
        author_match = re.search(r'author=["\']([^"\']+)["\']', match, re.IGNORECASE)
        desc_match = re.search(r'description=["\']([^"\']+)["\']', match, re.IGNORECASE)
        
        title = title_match.group(1) if title_match else "Inconnu"
        xml_url = url_match.group(1) if url_match else ""
        author = author_match.group(1) if author_match else "Auteur inconnu"
        description = desc_match.group(1) if desc_match else ""
        
        if xml_url:
            entries.append({
                "title": title,
                "xml_url": xml_url,
                "author": author,
                "description": description
            })
    return entries

def get_repo_config(repo_lower):
    """Récupère les règles spécifiques du dépôt ou applique le profil par défaut."""
    custom_rules = REPO_RULES.get("custom_payload_rules", {}).get(repo_lower, {})
    config = DEFAULT_REPO_CONFIG.copy()
    config.update(custom_rules)
    return config

def fetch_github_release_data(repo, config):
    """Interroge l'API GitHub en gérant proprement le canal pre-release et le fallback 404."""
    channel = config.get("release_channel", "stable")
    try:
        url = f"https://api.github.com/repos/{repo}/releases"
        if channel != "pre-release":
            url = f"https://api.github.com/repos/{repo}/releases/latest"
            
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0',
            'Accept': 'application/vnd.github.v3+json'
        })
        
        if os.environ.get('GITHUB_TOKEN'):
            req.add_header('Authorization', f"token {os.environ.get('GITHUB_TOKEN')}")
            
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            if isinstance(data, list) and data:
                return data[0]
            elif isinstance(data, dict):
                return data
                
    except urllib.error.HTTPError as e:
        # Fallback de secours si /latest renvoie 404 (cas fréquent des pre-releases pures)
        if e.code == 404 and channel != "pre-release":
            try:
                fallback_url = f"https://api.github.com/repos/{repo}/releases"
                req = urllib.request.Request(fallback_url, headers={
                    'User-Agent': 'Mozilla/5.0',
                    'Accept': 'application/vnd.github.v3+json'
                })
                if os.environ.get('GITHUB_TOKEN'):
                    req.add_header('Authorization', f"token {os.environ.get('GITHUB_TOKEN')}")
                with urllib.request.urlopen(req) as resp:
                    fallback_data = json.loads(resp.read().decode())
                    if isinstance(fallback_data, list) and fallback_data:
                        return fallback_data[0]
            except Exception:
                pass
        print(f"    ⚠️ Erreur de récupération GitHub pour {repo}: {e}")
    except Exception as e:
        print(f"    ⚠️ Erreur de récupération GitHub pour {repo}: {e}")
    
    return None

def fetch_forgejo_release_data(domain, repo, config):
    """Interroge l'API Forgejo / Gitea en injectant le token d'accès s'il est présent."""
    api_url = f"https://{domain}/api/v1/repos/{repo}/releases"
    try:
        req = urllib.request.Request(api_url, headers={'User-Agent': 'Mozilla/5.0'})
        token = os.environ.get('FORGEJO_TOKEN')
        if token:
            req.add_header('Authorization', f"token {token}")
            
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            if data and isinstance(data, list):
                return data[0]
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print(f"    ⚠️ Dépôt Forgejo privé ou restreint ({repo} sur {domain}) : Accès non autorisé (401). Vérifie ton token.")
        else:
            print(f"    ⚠️ Erreur HTTP {e.code} pour Forgejo ({repo} sur {domain}) : {e.reason}")
    except Exception as e:
        print(f"    ⚠️ Erreur lors de la récupération Forgejo pour {repo} sur {domain}: {e}")
    return None

def fetch_assets_from_url(xml_url, title, description, author, default_allowed_exts, category_folder="pkg"):
    """Moteur générique unifié compatible GitHub, Forgejo/Gitea et sources fixes."""
    if not xml_url or "ps4" in title.lower() or "ps4" in description.lower():
        return []

    version = "v1.0.0"
    clean_xml_url = xml_url.split('?')[0].lower()
    processed_items = []
    category_root_path = category_folder

    # Source fixe directe (.elf, .bin, .ffpfsc)
    if clean_xml_url.endswith(default_allowed_exts):
        try:
            version = "Source-Fixe"
            target_dir = os.path.join(category_root_path, title.replace(" ", "_"), "Source-Fixe")
            os.makedirs(target_dir, exist_ok=True)
            f_name = xml_url.split('?')[0].split('/')[-1]
            opener = urllib.request.build_opener()
            opener.addheaders = [('User-Agent', 'Mozilla/5.0')]
            urllib.request.install_opener(opener)
            local_file_path = os.path.join(target_dir, f_name)
            urllib.request.urlretrieve(xml_url, local_file_path)
            
            if os.path.exists(local_file_path):
                hasher = hashlib.sha256()
                with open(local_file_path, 'rb') as fb:
                    for chunk in iter(lambda: fb.read(4096), b""): hasher.update(chunk)
                
                display_name = os.path.splitext(f_name)[0]
                processed_items.append({
                    "name": display_name.replace('_', ' ').title(),
                    "filename": f_name,
                    "url": xml_url,
                    "local_path": local_file_path,
                    "description": description if description else f"Fichier {display_name}",
                    "version": version,
                    "checksum": hasher.hexdigest()
                })
        except Exception as e:
            print(f"    ⚠️ Échec source fixe ({title}) : {e}")
        return processed_items

    # Détection Forgejo / Gitea (ex: git.etawen.dev)
    is_forgejo = False
    forgejo_domain = ""
    repo_path = ""
    
    if "git.etawen.dev" in xml_url:
        is_forgejo = True
        forgejo_domain = "git.etawen.dev"
        match = re.search(r'git\.etawen\.dev/([^/]+/[^/]+)', xml_url)
        if match:
            repo_path = match.group(1).rstrip('/')

    # Dépôt GitHub ou Forgejo
    if "github.com" in xml_url or is_forgejo:
        repo_match = re.search(r'github\.com/([^/]+/[^/]+)', xml_url) if not is_forgejo else None
        repo = repo_match.group(1).rstrip('/') if repo_match else repo_path
        repo_lower = repo.lower()
        rules = get_repo_config(repo_lower)
        
        allowed_exts = rules.get("allowed_extensions", default_allowed_exts)
        exclude_exts = rules.get("exclude_extensions", [])
        exclude_keys = rules.get("exclude_keywords", [])

        try:
            if is_forgejo:
                release_data = fetch_forgejo_release_data(forgejo_domain, repo, rules)
            else:
                release_data = fetch_github_release_data(repo, rules)

            if release_data:
                version = release_data.get('tag_name', release_data.get('name', 'v1.0.0'))
                version_clean = re.sub(r'[^a-zA-Z0-9._-]', '', version)
                target_dir = os.path.join(category_root_path, title.replace(" ", "_"), version_clean)
                os.makedirs(target_dir, exist_ok=True)

                if rules.get("strict_clean") and os.path.exists(target_dir):
                    for existing_file in os.listdir(target_dir):
                        f_path = os.path.join(target_dir, existing_file)
                        if os.path.isfile(f_path):
                            os.remove(f_path)

                for asset in release_data.get('assets', []):
                    asset_url = asset.get('browser_download_url', '')
                    asset_name = asset.get('name', '')

                    if not any(asset_name.lower().endswith(ext) for ext in allowed_exts):
                        continue
                    if any(asset_name.lower().endswith(ext) for ext in exclude_exts):
                        continue
                    if any(kw in asset_name.lower() for kw in exclude_keys):
                        continue

                    target_filename = asset_name
                    local_file_path = os.path.join(target_dir, target_filename)

                    opener = urllib.request.build_opener()
                    opener.addheaders = [('User-Agent', 'Mozilla/5.0'), ('Accept', 'application/octet-stream')]
                    
                    # Injection des tokens d'authentification pour le téléchargement des assets
                    if is_forgejo:
                        token = os.environ.get('FORGEJO_TOKEN')
                        if token:
                            opener.addheaders.append(('Authorization', f"token {token}"))
                    else:
                        if os.environ.get('GITHUB_TOKEN'):
                            opener.addheaders.append(('Authorization', f"token {os.environ.get('GITHUB_TOKEN')}"))
                            
                    urllib.request.install_opener(opener)
                    urllib.request.urlretrieve(asset_url, local_file_path)

                    hasher = hashlib.sha256()
                    with open(local_file_path, 'rb') as fb:
                        for chunk in iter(lambda: fb.read(4096), b""): hasher.update(chunk)

                    display_name = os.path.splitext(target_filename)[0]
                    processed_items.append({
                        "name": display_name.replace('_', ' ').title(),
                        "filename": target_filename,
                        "url": asset_url,
                        "local_path": local_file_path,
                        "description": description if description else f"Élément {display_name}",
                        "version": version,
                        "checksum": hasher.hexdigest()
                    })

        except Exception as e:
            print(f"    ⚠️ Échec de récupération pour {repo}: {e}")

    return processed_items
