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

REPO_RULES = {
    "extract_zip_repos": [
        "poords4", 
        "fan_target", 
        "drakmor/fan_target",
        "shadowmountplus", 
        "instalador-host-psm-poop2jb"
    ],
    "strict_clean_repos": [
        "ps5-payload-dev/websrv", 
        "phantomptr/ps5upload", 
        "boazvdwansem/ps5-debugger"
    ],
    "keep_original_filename_repos": [
        "instalador-host-psm-poop2jb", 
        "psm", 
        "poords4",
        "owendswang/ps5-web-file-manager" # Pour s'assurer que le cleaner ne renomme pas brutalement l'helper
    ],
    "custom_payload_rules": {
        "smoxa/ps5-new-overlay": {
            "files": ["ps5_overlay.elf", "ps5_overlay_shellui.elf"]
        },
        "seregonwar/zftpd": {
            "mapping": {
                "zftpd-ps5-v1.5.0.elf": "zftpd_v{version}.elf",
                "zftpd-ps5-zhttp-v1.5.0.elf": "zhttp_v{version}.elf"
            }
        },
        "drakmor/fan_target": {
            "extract_zip": True,
            "suffix_format": "_{temperature}_v{version}.elf"
        },
        "owendswang/ps5-web-file-manager": {
            "mapping": {
                "web-file-mgr": "web-file-mgr_v{version}.elf",
                "wfm-7zip-helper.elf": "wfm-7zip-helper.elf"
            }
        }
    }
}

DISALLOWED_EXTENSIONS = ('.dmg', '.exe', '.appimage', '.msi', '.txt')
