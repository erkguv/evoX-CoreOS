# scripts/cleaner.py
import os
import re
import zipfile
from scripts.config_rules import REPO_RULES, DISALLOWED_EXTENSIONS

def process_downloaded_payloads(target_dir, repo_lower, default_base_name, version_clean):
    if not os.path.exists(target_dir):
        return []

    # Récupération des règles spécifiques au dépôt courant (avec fallback sur un dict vide)
    custom_rules = REPO_RULES.get("custom_payload_rules", {})
    repo_config = {}
    for key, rules in custom_rules.items():
        if key.lower() in repo_lower:
            repo_config = rules
            break

    # Vérification de l'extraction ZIP via le nouveau paramètre granulaire
    if repo_config.get("extract_zip", False):
        for item in os.listdir(target_dir):
            item_path = os.path.join(target_dir, item)
            if item.lower().endswith('.zip'):
                try:
                    with zipfile.ZipFile(item_path, 'r') as zf:
                        for member in zf.namelist():
                            if member.lower().endswith(('.elf', '.bin')):
                                zf.extract(member, target_dir)
                                extracted_path = os.path.join(target_dir, member)
                                dest_path = os.path.join(target_dir, os.path.basename(member))
                                if extracted_path != dest_path and os.path.exists(extracted_path):
                                    os.rename(extracted_path, dest_path)
                except Exception as e:
                    print(f"    ⚠️ Erreur dézippage pour {item}: {e}")
                finally:
                    if os.path.exists(item_path):
                        os.remove(item_path)

    files_downloaded = os.listdir(target_dir)
    
    # Vérification du nettoyage strict via la règle granulaire
    if repo_config.get("strict_clean", False):
        for f in files_downloaded:
            if not (f.lower().endswith('.elf') or f.lower().endswith('.bin')):
                try: os.remove(os.path.join(target_dir, f))
                except: pass
    else:
        for f in files_downloaded:
            if f.lower().endswith(DISALLOWED_EXTENSIONS):
                try: os.remove(os.path.join(target_dir, f))
                except: pass

    eligible_binaries = []
    v_suffix = version_clean
    if v_suffix != "Source-Fixe":
        if not v_suffix.lower().startswith('v'): 
            v_suffix = f"v{v_suffix}"
        v_suffix = f"_{v_suffix}"
    else:
        v_suffix = ""

    for f_name in [f for f in os.listdir(target_dir) if f.lower().endswith(('.elf', '.bin'))]:
        base_name, ext = os.path.splitext(f_name)
        
        # Vérification de la conservation du nom d'origine via la règle granulaire
        keep_orig = repo_config.get("keep_original", False)
        final_base = base_name if keep_orig else default_base_name
        
        new_f_name = f"{final_base}{v_suffix}{ext}" if not f_name.lower().endswith(f"{v_suffix.lower()}{ext.lower()}") else f_name
        old_path = os.path.join(target_dir, f_name)
        new_path = os.path.join(target_dir, new_f_name)
        
        if old_path != new_path:
            try:
                os.rename(old_path, new_path)
            except Exception:
                new_f_name = f_name
        
        if new_f_name not in eligible_binaries:
            eligible_binaries.append(new_f_name)

    return eligible_binaries
