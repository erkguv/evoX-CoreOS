# payloads_fetcher.py
import os
import re
import json
import hashlib
import zipfile
import subprocess
import urllib.request
from scripts.config_rules import PATHS, BASE_URL
from scripts.fetchers.utils import parse_opml_file, get_repo_config, fetch_github_release_data, fetch_forgejo_release_data
from scripts.cleaner import process_downloaded_payloads

def fetch_payloads_category(credits_set):
    payload_feed_dir = PATHS["categories"]["payloads"]["feed"]
    all_flat = []
    by_category = {}

    if not os.path.exists(payload_feed_dir):
        return by_category, all_flat

    for opml_file in [f for f in os.listdir(payload_feed_dir) if f.endswith('.opml')]:
        cat_tech = opml_file.replace('.opml', '')
        cat_display = cat_tech.replace('_', ' ').title()
        if "Hen" in cat_display: cat_display = cat_display.replace("Hen", "HEN")
        if cat_display.startswith("Ps5 "): cat_display = cat_display.replace("Ps5 ", "PS5 ")

        cat_list = []
        entries = parse_opml_file(os.path.join(payload_feed_dir, opml_file))

        for entry in entries:
            title = entry['title']
            xml_url = entry['xml_url']
            author = entry['author']
            description = entry['description']

            if not xml_url or "ps4" in title.lower() or "ps4" in description.lower():
                continue

            version = "v1.0.0"
            downloaded = False
            clean_xml_url = xml_url.split('?')[0].lower()
            repo_lower = ""

            # Gestion des sources fixes directes (URL brute .elf / .bin / .ffpfsc)
            if clean_xml_url.endswith(('.elf', '.bin', '.ffpfsc')):
                try:
                    version = "Source-Fixe"
                    version_clean = "Source-Fixe"
                    target_dir = os.path.join(PATHS["categories"]["payloads"]["root"], cat_tech, title.replace(" ", "_"), version_clean)
                    os.makedirs(target_dir, exist_ok=True)
                    f_name = xml_url.split('?')[0].split('/')[-1]
                    opener = urllib.request.build_opener()
                    opener.addheaders = [('User-Agent', 'Mozilla/5.0')]
                    urllib.request.install_opener(opener)
                    urllib.request.urlretrieve(xml_url, os.path.join(target_dir, f_name))
                    downloaded = True
                except Exception as e:
                    print(f"    ⚠️ Échec source fixe ({title}) : {e}")

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

            # Gestion des dépôts GitHub ou Forgejo via les règles unifiées
            if not downloaded and ("github.com" in xml_url or is_forgejo):
                repo_match = re.search(r'github\.com/([^/]+/[^/]+)', xml_url) if not is_forgejo else None
                repo = repo_match.group(1).rstrip('/') if repo_match else repo_path
                repo_lower = repo.lower() if repo else ""
                
                rules = get_repo_config(repo_lower)
                
                try:
                    if is_forgejo:
                        release_data = fetch_forgejo_release_data(forgejo_domain, repo, rules)
                    else:
                        release_data = fetch_github_release_data(repo, rules)
                    
                    if release_data:
                        version = release_data.get('tag_name', release_data.get('name', 'v1.0.0'))
                        version_clean = re.sub(r'[^a-zA-Z0-9._-]', '', version)
                        target_dir = os.path.join(PATHS["categories"]["payloads"]["root"], cat_tech, title.replace(" ", "_"), version_clean)
                        os.makedirs(target_dir, exist_ok=True)

                        if rules.get("strict_clean") and os.path.exists(target_dir):
                            for existing_file in os.listdir(target_dir):
                                file_path = os.path.join(target_dir, existing_file)
                                if os.path.isfile(file_path):
                                    os.remove(file_path)

                        for asset in release_data.get('assets', []):
                            asset_url = asset.get('browser_download_url', '')
                            asset_name = asset.get('name', '')
                            
                            if not any(asset_name.lower().endswith(ext) for ext in rules.get("allowed_extensions", [])):
                                continue
                            if any(asset_name.lower().endswith(ext) for ext in rules.get("exclude_extensions", [])):
                                continue
                            if any(keyword in asset_name.lower() for keyword in rules.get("exclude_keywords", [])):
                                continue

                            should_download = True
                            target_filename = asset_name

                            local_file_path = os.path.join(target_dir, target_filename)
                            opener = urllib.request.build_opener()
                            opener.addheaders = [('User-Agent', 'Mozilla/5.0'), ('Accept', 'application/octet-stream')]
                            if not is_forgejo and os.environ.get('GITHUB_TOKEN'):
                                opener.addheaders.append(('Authorization', f"token {os.environ.get('GITHUB_TOKEN')}"))
                            urllib.request.install_opener(opener)
                            urllib.request.urlretrieve(asset_url, local_file_path)
                            downloaded = True

                except Exception as e:
                    print(f"    ⚠️ Échec de récupération pour {repo}: {e}")

            version_clean = re.sub(r'[^a-zA-Z0-9._-]', '', version) if version != "Source-Fixe" else "Source-Fixe"
            target_dir = os.path.join(PATHS["categories"]["payloads"]["root"], cat_tech, title.replace(" ", "_"), version_clean)
            default_base_name = re.sub(r'[^a-zA-Z0-9._-]', '_', title)
            default_base_name = re.sub(r'_{2,}', '_', default_base_name).strip('_')

            rules = get_repo_config(repo_lower)
            if rules.get("keep_original") or rules.get("mapping") or rules.get("targets"):
                eligible_binaries = [f for f in os.listdir(target_dir) if os.path.isfile(os.path.join(target_dir, f))] if os.path.exists(target_dir) else []
            else:
                eligible_binaries = process_downloaded_payloads(target_dir, repo_lower, default_base_name, version_clean)

            for main_file in eligible_binaries:
                full_path = os.path.join(target_dir, main_file)
                if not os.path.exists(full_path):
                    continue
                hasher = hashlib.sha256()
                with open(full_path, 'rb') as fb:
                    for chunk in iter(lambda: fb.read(4096), b""): hasher.update(chunk)

                credits_set.add(f"- **{author}** : [{title}]({xml_url})")
                display_name = os.path.splitext(main_file)[0]

                item_data = {
                    "name": display_name.replace('_', ' ').title(),
                    "filename": main_file,
                    "url": f"{BASE_URL}/{target_dir.replace(os.sep, '/')}/{main_file}",
                    "local_path": full_path,
                    "description": description if description else f"Payload {display_name} pour PS5",
                    "version": version,
                    "category": cat_display,
                    "checksum": hasher.hexdigest()
                }
                cat_list.append(item_data)
                all_flat.append(item_data)

        by_category[cat_tech] = {"name": cat_display, "items": cat_list}

    return by_category, all_flat
