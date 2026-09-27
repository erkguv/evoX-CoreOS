# scripts/config_rules.py
import os

GITHUB_REPO_ENV = os.environ.get('GITHUB_REPOSITORY', '')
if '/' in GITHUB_REPO_ENV:
    GITHUB_USER, REPO_NAME = GITHUB_REPO_ENV.split('/', 1)
else:
    GITHUB_USER, REPO_NAME = 'nexgen999', 'PS5-Super-PLDMGR-Auto-Updater-Core_OS' 
BASE_URL = f"https://{GITHUB_USER}.github.io/{REPO_NAME}"

PATHS = {
    "feed_dir": "feed",
    "json_dir": "json",
    "payloads_dir": "payloads",
    "rss_dir": "rss",
    "archives_dir": "archives",
    "categories": {
        "payloads": {"feed": "feed/payloads", "json": "json/payloads", "root": "payloads"},
        "pkg": {"feed": "feed/pkg", "json": "json/pkg"},
        "ffpfsc": {"feed": "feed/ffpfsc", "json": "json/ffpfsc"},
        "apps": {"feed": "feed/apps", "json": "json/apps"},
    }
}

# =========================================================================
# MOTEUR DE RÈGLES UNIFIÉ ET GRANULAIRE PAR DÉPÔT
# =========================================================================
REPO_RULES = {
    "custom_payload_rules": {
        
        # Exemple 1 : Overlay multi-fichiers en gardant les noms originaux
        "smoxa/ps5-new-overlay": {
            "release_channel": "stable",            # "stable", "pre-release", ou "all"
            "allowed_extensions": [".elf"],
            "exclude_extensions": [],
            "exclude_keywords": [],
            "keep_original": True,
            "strict_clean": True,
            "extract_zip": False,
            "download_source_archive": False,
            "targets": []
        },

        # Exemple 2 : Zftpd avec filtrage strict des .bin et de la version PS4
        "seregonwar/zftpd": {
            "release_channel": "stable",
            "allowed_extensions": [".elf"],
            "exclude_extensions": [".bin"],
            "exclude_keywords": ["-ps4-"],
            "keep_original": False,
            "strict_clean": True,
            "extract_zip": False,
            "download_source_archive": False,
            "targets": [
                {
                    "match": "zftpd-ps5-v1.5.0.elf", # Sera géré via mapping ou correspondance partielle
                    "rename": "zftpd_v{version}.elf"
                },
                {
                    "match": "zftpd-ps5-zhttp-v1.5.0.elf",
                    "rename": "zhttp_v{version}.elf"
                }
            ],
            "mapping": {
                "zftpd-ps5-v1.5.0.elf": "zftpd_v{version}.elf",
                "zftpd-ps5-zhttp-v1.5.0.elf": "zhttp_v{version}.elf"
            }
        },

        # Exemple 3 : Fan Target avec extraction de ZIP et variantes de température
        "drakmor/fan_target": {
            "release_channel": "stable",
            "allowed_extensions": [".zip", ".elf"],
            "exclude_extensions": [],
            "exclude_keywords": [],
            "keep_original": False,
            "strict_clean": True,
            "extract_zip": True,
            "suffix_format": "_{temperature}_v{version}.elf",
            "download_source_archive": False,
            "targets": []
        },

        # Exemple 4 : Web File Manager avec mapping simple
        "owendswang/ps5-web-file-manager": {
            "release_channel": "stable",
            "allowed_extensions": [".elf"],
            "exclude_extensions": [],
            "exclude_keywords": [],
            "keep_original": False,
            "strict_clean": False,
            "extract_zip": False,
            "download_source_archive": False,
            "mapping": {
                "web-file-mgr": "web-file-mgr_v{version}.elf",
                "wfm-7zip-helper.elf": "wfm-7zip-helper.elf"
            },
            "targets": []
        }
    }
}

# Configuration par défaut appliquée si un dépôt n'est pas explicitement déclaré ci-dessus
DEFAULT_REPO_CONFIG = {
    "release_channel": "stable",
    "allowed_extensions": [".elf", ".bin", ".ffpfsc", ".zip"],
    "exclude_extensions": [".txt", ".exe", ".dmg"],
    "exclude_keywords": [],
    "keep_original": False,
    "strict_clean": False,
    "extract_zip": False,
    "download_source_archive": False,
    "mapping": {},
    "targets": []
}

DISALLOWED_EXTENSIONS = ('.dmg', '.exe', '.appimage', '.msi', '.txt')
