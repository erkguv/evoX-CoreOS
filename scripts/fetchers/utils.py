# scripts/fetchers/utils.py
import os
import re
import json
import subprocess
from scripts.config_rules import REPO_RULES, DEFAULT_REPO_CONFIG

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
            # Cherche spécifiquement dans la liste des releases
            releases_json_str = subprocess.check_output(f"gh api repos/{repo}/releases", shell=True).decode().strip()
            releases_data = json.loads(releases_json_str)
            if releases_data and isinstance(releases_data, list):
                # Trie ou prend la première pre-release ou la plus récente
                return releases_data[0]
        else:
            # Par défaut, récupère la dernière release officielle stable
            release_json_str = subprocess.check_output(f"gh api repos/{repo}/releases/latest", shell=True).decode().strip()
            return json.loads(release_json_str)
    except Exception as e:
        print(f"    ⚠️ Erreur lors de la récupération de la release pour {repo}: {e}")
    return None
