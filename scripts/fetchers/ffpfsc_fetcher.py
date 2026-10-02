import os
from scripts.config_rules import PATHS
from scripts.fetchers.utils import parse_opml_file, fetch_assets_from_url

def fetch_ffpfsc_category(credits_set):
    feed_dir = PATHS["categories"]["ffpfsc"]["feed"]
    all_flat = []
    by_category = {}

    if not os.path.exists(feed_dir):
        return by_category, all_flat

    for opml_file in [f for f in os.listdir(feed_dir) if f.endswith('.opml')]:
        cat_tech = opml_file.replace('.opml', '').lower()
        cat_display = "FFPFSC"
        cat_list = []
        entries = parse_opml_file(os.path.join(feed_dir, opml_file))

        for entry in entries:
            title, xml_url, author = entry['title'], entry['xml_url'], entry['author']
            desc = entry.get('description', '')
            if not xml_url: continue

            # Appel avec l'extension .ffpfsc autorisée par défaut
            assets = fetch_assets_from_url(xml_url, title, desc, author, ('.ffpfsc',), category_folder="ffpfsc")
            
            for item in assets:
                file_url = item.get("url", "") or item.get("filename", "")
                if not file_url.lower().endswith('.ffpfsc'):
                    continue

                item["category"] = cat_display
                credits_set.add(f"- **{author}** : [{title}]({xml_url})")
                cat_list.append(item)
                all_flat.append(item)

        by_category[cat_tech] = {"name": cat_display, "items": cat_list}
    return by_category, all_flat
