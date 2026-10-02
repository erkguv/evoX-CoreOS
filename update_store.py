# update_store.py
import os
import json
import hashlib
import zipfile
from datetime import datetime
from scripts.config_rules import PATHS
from scripts.fetchers.payloads_fetcher import fetch_payloads_category
from scripts.fetchers.pkg_fetcher import fetch_pkg_category
from scripts.fetchers.ffpfsc_fetcher import fetch_ffpfsc_category
from scripts.fetchers.apps_fetcher import fetch_apps_category
from scripts.generate_json import build_all
from scripts.generate_rss import build_rss_feed
from scripts.generate_readme import build_readme
from scripts.changelog_builder import generate_build_changelog
from scripts.pegasus_builder import generate_pegasus_catalog
from scripts.download_pegasus_catalogs import download_catalogs

def clean_latest_versions_only(flat_list):
    """
    Filtre la liste pour ne garder que la version la plus récente (latest) 
    pour chaque application/payload, en se basant sur le nom de base.
    """
    latest_map = {}
    for item in flat_list:
        if not isinstance(item, dict):
            continue
        name = item.get("name", "")
        base_key = name.lower().split('_v')[0].split(' v')[0].strip()
        
        if base_key not in latest_map:
            latest_map[base_key] = item
        else:
            existing_filename = latest_map[base_key].get("filename", "")
            current_filename = item.get("filename", "")
            if current_filename > existing_filename:
                latest_map[base_key] = item

    return list(latest_map.values())

def recover_local_orphans(category_name, flat_list, allowed_exts):
    """
    Scanne le dossier physique de la catégorie pour récupérer les fichiers orphelins 
    présents en local (notamment les fichiers internes ou les sources en échec 503).
    """
    root_dir = PATHS.get("categories", {}).get(category_name, {}).get("root", category_name)
    if not os.path.exists(root_dir):
        return flat_list

    known_filenames = {item.get("filename") for item in flat_list if isinstance(item, dict)}
    recovered_count = 0

    for dirpath, _, filenames in os.walk(root_dir):
        if "archives" in dirpath.split(os.sep):
            continue

        for filename in filenames:
            if not filename.lower().endswith(tuple(allowed_exts)):
                continue
            
            if filename not in known_filenames:
                local_path = os.path.join(dirpath, filename)
                
                hasher = hashlib.sha256()
                try:
                    with open(local_path, 'rb') as fb:
                        for chunk in iter(lambda: fb.read(4096), b""):
                            hasher.update(chunk)
                    checksum = hasher.hexdigest()
                except Exception:
                    checksum = ""

                display_name = os.path.splitext(filename)[0].replace('_', ' ').title()
                version = "Local-Backup"
                
                parts = dirpath.split(os.sep)
                if len(parts) > 1:
                    repo_or_title = parts[1]
                    if len(parts) > 2:
                        version = parts[2]
                else:
                    repo_or_title = display_name

                orphan_item = {
                    "name": display_name,
                    "filename": filename,
                    "url": "",
                    "local_path": local_path,
                    "description": f"Récupéré depuis le stockage local (Interne / Fallback)",
                    "version": version,
                    "checksum": checksum
                }
                
                flat_list.append(orphan_item)
                known_filenames.add(filename)
                recovered_count += 1
                print(f"    ♻️ [Fallback Local] Récupération de l'orphelin : {filename} ({category_name})")

    if recovered_count > 0:
        print(f"    ✅ {recovered_count} élément(s) local(aux) préservé(s) pour {category_name}.")
    
    flat_list = clean_latest_versions_only(flat_list)
    return flat_list

def generate_release_notes(data_store_by_cat):
    print("📝 Génération des notes de version pour la Release...")
    json_dir = PATHS.get("json_dir", "json")
    notes_path = "release_notes.md"
    date_str = datetime.now().strftime("v%Y.%m.%d-%H%M")
    
    categories = ["payloads", "pkg", "ffpfsc", "apps"]
    
    content = f"### 🚀 Synthèse de la mise à jour ({date_str})\n\n"
    content += "Le store PlayStation 5 a été mis à jour avec succès.\n\n"
    
    content += "#### 📦 Archives AIO Disponibles (Dossier `archives/`) :\n"
    content += "- `PS5_payloads_aio_latest.zip`\n"
    content += "- `PS5_pkg_aio_latest.zip`\n"
    content += "- `PS5_ffpfsc_aio_latest.zip`\n"
    content += "- `PS5_apps_aio_latest.zip`\n"
    content += "- `PS5_ultimate_pack_latest.zip`\n\n"
    
    content += "#### 📂 Fichiers inclus / mis à jour :\n"
    content += "📜 [Consulter le journal complet des modifications (CHANGELOG.md)](CHANGELOG.md)\n\n"

    content += "#### 🛠️️ Détail des Packs & Contenu\n"
    
    icons = {
        "payloads": "⚡",
        "pkg": "🎮",
        "ffpfsc": "📄",
        "apps": "🛠"
    }

    for cat_key in categories:
        json_file_path = os.path.join(json_dir, f"{cat_key}.json")
        icon = icons.get(cat_key, "📦")
        content += f"<details>\n<summary><b>{icon} Pack {cat_key.upper()}</b></summary>\n\n"
        
        has_items = False
        if os.path.exists(json_file_path):
            with open(json_file_path, 'r', encoding='utf-8') as f:
                json_content = json.load(f)
                
            if isinstance(json_content, dict):
                for section_key, section_val in json_content.items():
                    if section_key == "name":
                        continue
                        
                    file_entries = []
                    items_list = []
                    if isinstance(section_val, list):
                        items_list = section_val
                    elif isinstance(section_val, dict):
                        items_list = section_val.get('items', [])
                        
                    for item in items_list:
                        if isinstance(item, dict):
                            fname = item.get('filename')
                            if fname:
                                file_entries.append(fname)
                            
                    if file_entries:
                        has_items = True
                        content += f"* **{section_key}**\n"
                        seen = set()
                        for fname in file_entries:
                            if fname not in seen:
                                seen.add(fname)
                                content += f"  * `{fname}`\n"
        
        if not has_items:
            content += "*Aucun élément dans ce pack.*\n"
            
        content += "\n</details>\n\n"

    with open(notes_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("    ✅ Fichier release_notes.md généré avec succès !")

def build_aio_archives(payloads_flat, pkg_flat, ffpfsc_flat, apps_flat):
    print("📦 [Bonus] Génération des archives AIO ZIP dans le dossier 'archives' uniquement...")
    
    # Chemin absolu strict de la racine du dépôt
    base_workspace = os.path.abspath(os.getcwd())
    archives_dir = os.path.join(base_workspace, "archives")
    os.makedirs(archives_dir, exist_ok=True)

    def create_zip(zip_name, items):
        # Force le chemin cible DIRECTEMENT dans /archives/ à la racine, jamais ailleurs
        zip_path = os.path.join(archives_dir, zip_name)
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for item in items:
                file_path = item.get("local_path") if isinstance(item, dict) else None
                if file_path and os.path.exists(file_path):
                    norm_path = os.path.abspath(file_path)
                    # Sécurité absolue : on ignore tout ce qui touche de près ou de loin à un dossier archives ou json
                    if "archives" in norm_path.split(os.sep) or "json" in norm_path.split(os.sep):
                        continue
                    zf.write(norm_path, arcname=os.path.basename(norm_path))
                    
        size_bytes = os.path.getsize(zip_path) if os.path.exists(zip_path) else 0
        print(f"    ➔ Archive générée : {zip_path} ({size_bytes} octets)")

    create_zip("PS5_payloads_aio_latest.zip", payloads_flat)
    create_zip("PS5_pkg_aio_latest.zip", pkg_flat)
    create_zip("PS5_ffpfsc_aio_latest.zip", ffpfsc_flat)
    create_zip("PS5_apps_aio_latest.zip", apps_flat)
    create_zip("PS5_ultimate_pack_latest.zip", payloads_flat + pkg_flat + ffpfsc_flat + apps_flat)

def main():
    print("🚀 Démarrage de la mise à jour globale du store PS5...")
    credits_set = set()
    
    os.makedirs(PATHS["archives_dir"], exist_ok=True)
    os.makedirs(PATHS["json_dir"], exist_ok=True)
    os.makedirs(PATHS["payloads_dir"], exist_ok=True)

    print("📥 [0/5] Téléchargement des catalogues Pegasus distants...")
    download_catalogs()

    print("🔍 [1/5] Scraping des sources OPML et téléchargement des binaires...")
    payloads_by_cat, payloads_flat = fetch_payloads_category(credits_set)
    pkg_by_cat, pkg_flat = fetch_pkg_category(credits_set)
    ffpfsc_by_cat, ffpfsc_flat = fetch_ffpfsc_category(credits_set)
    apps_by_cat, apps_flat = fetch_apps_category(credits_set)

    print("🛡️ [1.5/5] Récupération de sécurité des fichiers locaux (Fallback anti-disparition)...")
    payloads_flat = recover_local_orphans("payloads", payloads_flat, [".elf", ".bin"])
    pkg_flat = recover_local_orphans("pkg", pkg_flat, [".pkg"])
    ffpfsc_flat = recover_local_orphans("ffpfsc", ffpfsc_flat, [".ffpfsc", ".bin", ".elf"])
    apps_flat = recover_local_orphans("apps", apps_flat, [".elf", ".zip"])

    data_store = {
        "payloads": (payloads_by_cat, payloads_flat),
        "pkg": (pkg_by_cat, pkg_flat),
        "ffpfsc": (ffpfsc_by_cat, ffpfsc_flat),
        "apps": (apps_by_cat, apps_flat)
    }

    data_store_by_cat = {
        "payloads": payloads_by_cat,
        "pkg": pkg_by_cat,
        "ffpfsc": ffpfsc_by_cat,
        "apps": apps_by_cat
    }

    data_store_flat = {
        "payloads": {"name": "Payloads", "items": payloads_flat},
        "pkg": {"name": "Packages PKG", "items": pkg_flat},
        "ffpfsc": {"name": "Fichiers FFPFSC", "items": ffpfsc_flat},
        "apps": {"name": "Applications", "items": apps_flat}
    }

    print("📦 [2/5] Génération de l'arborescence JSON complète...")
    build_all(data_store)

    print("🎯 [2.5/5] Génération du catalogue Pegasus-DL...")
    generate_pegasus_catalog(pkg_flat, ffpfsc_flat)

    print("📡 [3/5] Génération des flux RSS et OPML... ")
    build_rss_feed(data_store_flat)

    print("📝 [4/4] Mise à jour du README.md, des Crédits, du Changelog et des Notes de Release...")
    build_readme(credits_set, data_store_by_cat)
    generate_build_changelog()
    generate_release_notes(data_store_by_cat)

    build_aio_archives(payloads_flat, pkg_flat, ffpfsc_flat, apps_flat)

    print("✅ Mise à jour du store et des packages terminée avec succès !")

if __name__ == "__main__":
    main()