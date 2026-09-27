# scripts/fetchers/utils.py
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
    """Interroge l'API GitHub en tenant compte du canal de release (stable / pre-release)."""
    channel = config.get("release_channel", "stable")
    try:
        if channel == "pre-release":
            releases_json_str = subprocess.check_output(f"gh api repos/{repo}/releases", shell=True).decode().strip()
            releases_data = json.loads(releases_json_str)
            if releases_data and isinstance(releases_data, list):
                return releases_data[0]
        else:
            release_json_str = subprocess.check_output(f"gh api repos/{repo}/releases/latest", shell=True).decode().strip()
            return json.loads(release_json_str)
    except Exception as e:
        print(f"    ⚠️ Erreur lors de la récupération de la release pour {repo}: {e}")
    return None

def fetch_assets_according_to_rules(entry, category_root_path, default_allowed_exts):
    """Moteur générique unifié pour télécharger et filtrer les assets selon les règles du dépôt."""
    title = entry['title']
    xml_url = entry['xml_url']
    description = entry['description']
    
    if not xml_url or "ps4" in title.lower() or "ps4" in description.lower():
        return []

    version = "v1.0.0"
    clean_xml_url = xml_url.split('?')[0].lower()
    processed_items = []

    # Source fixe directe
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
                    "url": xml_url,  # <-- URL d'origine directe
                    "local_path": local_file_path,
                    "description": description if description else f"Fichier {display_name}",
                    "version": version,
                    "checksum": hasher.hexdigest()
                })
        except Exception as e:
            print(f"    ⚠️ Échec source fixe ({title}) : {e}")
        return processed_items

    # Dépôt GitHub
    if "github.com" in xml_url:
        repo_match = re.search(r'github\.com/([^/]+/[^/]+)', xml_url)
        if repo_match:
            repo = repo_match.group(1).rstrip('/')
            repo_lower = repo.lower()
            rules = get_repo_config(repo_lower)
            
            allowed_exts = rules.get("allowed_extensions", default_allowed_exts)
            exclude_exts = rules.get("exclude_extensions", [])
            exclude_keys = rules.get("exclude_keywords", [])

            try:
                release_data = fetch_github_release_data(repo, rules)
                if release_data:
                    version = release_data.get('tag_name', 'v1.0.0')
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

                        should_download = False
                        target_filename = asset_name
                        targets_list = rules.get("targets", [])
                        custom_mapping = rules.get("mapping", {})

                        if targets_list:
                            for t in targets_list:
                                if t["match"] in asset_name:
                                    should_download = True
                                    v_numeric = version_clean.lstrip('v')
                                    target_filename = t["rename"].format(version=v_numeric)
                                    break
                        elif custom_mapping:
                            matched_mapping = False
                            for orig_pat, target_pat in custom_mapping.items():
                                if orig_pat in asset_name:
                                    should_download = True
                                    v_numeric = version_clean.lstrip('v')
                                    target_filename = target_pat.format(version=v_numeric) if "{version}" in target_pat else target_pat
                                    matched_mapping = True
                                    break
                            if not matched_mapping and not rules.get("keep_original"):
                                should_download = True
                        else:
                            should_download = True

                        if should_download:
                            local_file_path = os.path.join(target_dir, target_filename)
                            opener = urllib.request.build_opener()
                            opener.addheaders = [('User-Agent', 'Mozilla/5.0'), ('Accept', 'application/octet-stream')]
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
                                "url": asset_url,  # <-- Conserve l'URL GitHub d'origine
                                "local_path": local_file_path,
                                "description": description if description else f"Élément {display_name}",
                                "version": version,
                                "checksum": hasher.hexdigest()
                            })

            except Exception as e:
                print(f"    ⚠️ Échec de récupération GitHub pour {repo}: {e}")

    return processed_items
