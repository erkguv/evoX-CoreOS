# scripts/fetchers/pkg_fetcher.py
import os
from scripts.config_rules import PATHS
from scripts.fetchers.utils import parse_opml_file, fetch_assets_according_to_rules

def fetch_pkg_category(credits_set):
    feed_dir = PATHS["categories"]["pkg"]["feed"]
    root_dir = PATHS["categories"]["pkg"]["root"] if "root" in PATHS["categories"]["pkg"] else "pkg"
    all_flat = []
    by_category = {}

    if not os.path.exists(feed_dir):
        return by_category, all_flat

    for opml_file in [f for f in os.listdir(feed_dir) if f.endswith('.opml')]:
        cat_tech = opml_file.replace('.opml', '').lower()
        cat_display = "PKG"
        cat_list = []
        entries = parse_opml_file(os.path.join(feed_dir, opml_file))

        for entry in entries:
            title, xml_url, author = entry['title'], entry['xml_url'], entry['author']
            if not xml_url: continue

            assets = fetch_assets_according_to_rules(entry, root_dir, ('.pkg',))
            for item in assets:
                item["category"] = cat_display
                credits_set.add(f"- **{author}** : [{title}]({xml_url})")
                cat_list.append(item)
                all_flat.append(item)

        by_category[cat_tech] = {"name": cat_display, "items": cat_list}
    return by_category, all_flat
