# payloads_fetcher.py
import os
import re
import json
import hashlib
import zipfile
import subprocess
import urllib.request
from scripts.config_rules import PATHS, BASE_URL
from scripts.fetchers.utils import parse_opml_file, get_repo_config, fetch_github_release_data
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

            # Gestion des sources fixes directes (URL brute .elf / .bin)
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

            # Gestion des dépôts GitHub via le nouveau moteur de règles unifié
            if not downloaded and "github.com" in xml_url:
                repo_match = re.search(r'github\.com/([^/]+/[^/]+)', xml_url)
                if repo_match:
                    repo = repo_match.group(1).rstrip('/')
                    repo_lower = repo.lower()
                    
                    # Chargement des règles unifiées du dépôt
                    rules = get_repo_config(repo_lower)
                    
                    try:
                        release_data = fetch_github_release_data(repo, rules)
                        
                        if release_data:
                            version = release_data.get('tag_name', 'v1.0.0')
                            version_clean = re.sub(r'[^a-zA-Z0-9._-]', '', version)
                            target_dir = os.path.join(PATHS["categories"]["payloads"]["root"], cat_tech, title.replace(" ", "_"), version_clean)
                            os.makedirs(target_dir, exist_ok=True)

                            # Option de nettoyage strict du dossier si demandé dans les règles
                            if rules.get("strict_clean") and os.path.exists(target_dir):
                                for existing_file in os.listdir(target_dir):
                                    file_path = os.path.join(target_dir, existing_file)
                                    if os.path.isfile(file_path):
                                        os.remove(file_path)

                            for asset in release_data.get('assets', []):
                                asset_url = asset.get('browser_download_url', '')
                                asset_name = asset.get('name', '')
                                
                                # 1. Vérification des extensions autorisées
                                if not any(asset_name.lower().endswith(ext) for ext in rules.get("allowed_extensions", [])):
                                    continue
                                
                                # 2. Vérification des extensions exclues (exclude_extensions)
                                if any(asset_name.lower().endswith(ext) for ext in rules.get("exclude_extensions", [])):
                                    continue

                                # 3. Vérification des mots-clés interdits
                                if any(keyword in asset_name.lower() for keyword in rules.get("exclude_keywords", [])):
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
                                            if "{version}" in target_pat:
                                                target_filename = target_pat.format(version=v_numeric)
                                            else:
                                                target_filename = target_pat
                                            matched_mapping = True
                                            break
                                    if not matched_mapping and not rules.get("keep_original"):
                                        should_download = True
                                elif rules.get("keep_original"):
                                    should_download = True
                                    target_filename = asset_name
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
                                    downloaded = True

                                    # Gestion de l'extraction ZIP si activée
                                    if rules.get("extract_zip") and asset_name.endswith('.zip'):
                                        try:
                                            with zipfile.ZipFile(local_file_path, 'r') as zip_ref:
                                                for zipped_file in zip_ref.namelist():
                                                    if zipped_file.endswith('.elf'):
                                                        extracted_path = zip_ref.extract(zipped_file, target_dir)
                                                        base_zipped_name = os.path.basename(zipped_file)
                                                        temp_match = re.search(r'(\d+c)', base_zipped_name, re.IGNORECASE)
                                                        v_numeric = version_clean.lstrip('v')
                                                        
                                                        suffix_fmt = rules.get("suffix_format", "_{temperature}_v{version}.elf")
                                                        if temp_match:
                                                            temp_val = temp_match.group(1).lower()
                                                            new_elf_name = f"fan_target{suffix_fmt.format(temperature=temp_val, version=v_numeric)}"
                                                        else:
                                                            new_elf_name = f"{os.path.splitext(base_zipped_name)[0]}_v{v_numeric}.elf"
                                                        
                                                        final_elf_path = os.path.join(target_dir, new_elf_name)
                                                        if os.path.exists(final_elf_path):
                                                            os.remove(final_elf_path)
                                                        os.rename(extracted_path, final_elf_path)
                                            os.remove(local_file_path)
                                        except Exception as zip_err:
                                            print(f"    ⚠️ Erreur extraction ZIP pour {repo}: {zip_err}")

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
