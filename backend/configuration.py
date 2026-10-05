"""Validate and project the public, file-based UI configuration without dependencies."""

import json
import re
from pathlib import Path
from urllib.parse import urlsplit

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "config" / "controldeck.json"
ICONS = {"dashboard", "virtual-apps", "bookmarks", "proxmox", "media", "terminal", "admin"}


class ConfigurationError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ConfigurationError(message)


def fields(value, allowed, required, where):
    require(isinstance(value, dict), f"{where}: expected an object")
    require(set(value) <= set(allowed), f"{where}: unknown fields")
    require(set(required) <= set(value), f"{where}: required fields missing")


def text(value, where, maximum=200):
    require(isinstance(value, str) and 0 < len(value) <= maximum, f"{where}: expected nonempty text")
    return value


def identifier(value, where):
    text(value, where, 64)
    require(re.fullmatch(r"[a-z][a-z0-9-]*", value), f"{where}: invalid identifier")
    return value


def web_url(value, where):
    text(value, where, 2048)
    try:
        parsed = urlsplit(value)
        require(parsed.scheme in ("http", "https") and parsed.hostname and not parsed.username and not parsed.password, f"{where}: expected http(s) URL without credentials")
        require(not any(c.isspace() or ord(c) < 32 for c in value), f"{where}: invalid URL")
        _ = parsed.port
    except ValueError as error:
        raise ConfigurationError(f"{where}: invalid URL") from error
    return value


def validate(config):
    fields(config, ["schemaVersion", "site", "modules", "menu", "providers", "widgets"], ["schemaVersion", "site", "modules", "menu"], "config")
    require(type(config["schemaVersion"]) is int and config["schemaVersion"] == 1, "Unsupported schemaVersion")
    site = config["site"]
    fields(site, ["title", "subtitle", "logo", "defaultTheme", "refreshSeconds", "footerText", "supportLabel", "supportUrl"], ["title", "subtitle", "logo", "defaultTheme", "refreshSeconds", "footerText", "supportLabel", "supportUrl"], "site")
    for key in ("title", "subtitle", "footerText", "supportLabel"):
        text(site[key], f"site.{key}")
    text(site["logo"], "site.logo", 2048)
    require(site["logo"].startswith("/") and not site["logo"].startswith("//") and not any(c.isspace() or c == "\\" for c in site["logo"]), "site.logo: expected local absolute asset path")
    require(site["defaultTheme"] in ("dark", "light"), "site.defaultTheme: dark or light required")
    require(type(site["refreshSeconds"]) is int and 5 <= site["refreshSeconds"] <= 3600, "site.refreshSeconds: expected 5..3600")
    web_url(site["supportUrl"], "site.supportUrl")
    require(isinstance(config["modules"], list) and 0 < len(config["modules"]) <= 100, "modules: expected 1..100 modules")
    provider_list = config.get("providers", [])
    require(isinstance(provider_list, list) and len(provider_list) <= 100, "providers: expected at most 100 entries")
    providers, provider_ids, active_providers = [], set(), set()
    for provider in provider_list:
        fields(provider, ["id", "type", "label", "enabled", "url", "tokenEnv"], ["id", "type", "label", "enabled", "url"], "provider")
        pid = identifier(provider["id"], "provider.id")
        require(pid not in provider_ids, "Duplicate provider id")
        provider_ids.add(pid)
        identifier(provider["type"], "provider.type")
        text(provider["label"], "provider.label")
        require(type(provider["enabled"]) is bool, "provider.enabled: boolean required")
        if provider["url"] is not None:
            web_url(provider["url"], "provider.url")
            parsed = urlsplit(provider["url"])
            require(not parsed.query and not parsed.fragment, "provider.url: use a base URL without query parameters or fragments")
        require(not provider["enabled"] or provider["url"] is not None, "Enabled provider requires a URL")
        if "tokenEnv" in provider:
            require(isinstance(provider["tokenEnv"], str) and re.fullmatch(r"[A-Z][A-Z0-9_]*", provider["tokenEnv"]), "provider.tokenEnv: expected environment variable name")
        # Explicit projection: private credential references never enter the API response.
        providers.append({key: provider[key] for key in ("id", "type", "label", "enabled", "url")})
        if provider["enabled"]:
            active_providers.add(pid)
    all_routes, enabled_routes, modules, module_ids = set(), set(), [], set()
    for module in config["modules"]:
        fields(module, ["id", "enabled", "title", "description", "view", "pages", "provider"], ["id", "enabled", "title"], "module")
        mid = identifier(module["id"], "module.id")
        require(mid not in module_ids, "Duplicate module id")
        module_ids.add(mid)
        require(type(module["enabled"]) is bool, "module.enabled: boolean required")
        text(module["title"], "module.title")
        if "description" in module:
            text(module["description"], "module.description", 2000)
        require(module.get("view", "placeholder") in ("empty", "placeholder", "integration", "terminal"), "Unsupported module.view")
        require(module.get("view") != "terminal" or mid == "terminal", "Terminal view requires terminal module")
        if "provider" in module:
            require(isinstance(module["provider"], str) and module["provider"] in provider_ids, "module.provider: unknown provider")
        require(module.get("view") != "integration" or "provider" in module, "Integration module requires provider")
        pages = module.get("pages", [])
        require(isinstance(pages, list) and len(pages) <= 100, "module.pages: expected at most 100 pages")
        routes = {mid}
        for page in pages:
            fields(page, ["id", "title", "description"], ["id", "title"], "page")
            route = f"{mid}/{identifier(page['id'], 'page.id')}"
            require(route not in routes, "Duplicate page id")
            routes.add(route)
            text(page["title"], "page.title")
            if "description" in page:
                text(page["description"], "page.description", 2000)
        all_routes.update(routes)
        if module["enabled"] and ("provider" not in module or module["provider"] in active_providers):
            enabled_routes.update(routes)
            modules.append(module)
    require(modules, "At least one module must be enabled")
    require(isinstance(config["menu"], list) and 0 < len(config["menu"]) <= 100, "menu: expected 1..100 items")
    menu_ids = set()

    def menu_item(item, depth=0):
        fields(item, ["id", "label", "icon", "route", "url", "children", "enabled"], ["id", "label"], "menu item")
        iid = identifier(item["id"], "menu.id")
        require(iid not in menu_ids, "Duplicate menu id")
        menu_ids.add(iid)
        text(item["label"], "menu.label")
        require(isinstance(item.get("icon", "dashboard"), str) and item.get("icon", "dashboard") in ICONS, "menu.icon: unsupported icon")
        require(type(item.get("enabled", True)) is bool, "menu.enabled: boolean required")
        require(sum(key in item for key in ("route", "url", "children")) == 1, "menu item needs exactly one route, url or children")
        output = dict(item)
        if "children" in item:
            require(depth == 0, "Only one dropdown level is currently supported")
            require(isinstance(item["children"], list) and 0 < len(item["children"]) <= 100, "menu.children: expected 1..100 items")
            output["children"] = [child for child in (menu_item(entry, depth + 1) for entry in item["children"]) if child]
            if not output["children"]:
                return None
        elif "route" in item:
            text(item["route"], "menu.route", 130)
            require(item["route"] in all_routes, "menu.route: unknown module/page")
            if item["route"] not in enabled_routes:
                return None
        else:
            web_url(item["url"], "menu.url")
        return output if item.get("enabled", True) else None

    menu = [item for item in (menu_item(entry) for entry in config["menu"]) if item]
    require(menu, "At least one visible menu item required")
    widget_list = config.get("widgets", [])
    require(isinstance(widget_list, list) and len(widget_list) <= 100, "widgets: expected at most 100 entries")
    widgets, widget_ids = [], set()
    for widget in widget_list:
        fields(widget, ["id", "enabled", "title", "provider", "route"], ["id", "enabled", "title", "provider", "route"], "widget")
        wid = identifier(widget["id"], "widget.id")
        require(wid not in widget_ids, "Duplicate widget id")
        widget_ids.add(wid)
        text(widget["title"], "widget.title")
        require(type(widget["enabled"]) is bool, "widget.enabled: boolean required")
        require(isinstance(widget["provider"], str) and widget["provider"] in provider_ids, "widget.provider: unknown provider")
        require(isinstance(widget["route"], str) and widget["route"] in all_routes, "widget.route: unknown route")
        if widget["enabled"] and widget["provider"] in active_providers and widget["route"] in enabled_routes:
            widgets.append(widget)
    return {"schemaVersion": 1, "site": site, "modules": modules, "menu": menu, "providers": providers, "widgets": widgets}


def load_config(path):
    try:
        root = Path(path).resolve().parent
        total_bytes = 0

        def read_json(filename):
            nonlocal total_bytes
            # A bounded read also protects against accidentally enormous files.
            with filename.open("rb") as stream:
                data = stream.read(256 * 1024 + 1)
            total_bytes += len(data)
            require(total_bytes <= 256 * 1024, "Configuration exceeds 256 KiB in total")
            return json.loads(data.decode("utf-8-sig"))

        config = read_json(Path(path))
        require(isinstance(config, dict), "config: expected an object")
        includes = config.pop("includes", {})
        fields(includes, ["modules", "providers", "widgets"], [], "includes")
        for section, relative in includes.items():
            text(relative, f"includes.{section}", 200)
            directory = (root / relative).resolve()
            require(directory != root and directory.is_relative_to(root) and directory.is_dir(), "Includes must name a directory within the configuration folder")
            files = sorted(directory.glob("*.json"))
            require(0 < len(files) <= 100, "Include directory must contain 1..100 JSON files")
            entries = config.setdefault(section, [])
            require(isinstance(entries, list), "Inline configuration section must be an array")
            for filename in files:
                require(filename.resolve().is_relative_to(root), "Included file outside configuration folder")
                data = read_json(filename)
                entries.extend(data if isinstance(data, list) else [data])
        return validate(config)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ConfigurationError("Cannot read valid JSON configuration") from error


if __name__ == "__main__":
    import sys
    try:
        load_config(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PATH)
    except ConfigurationError as error:
        raise SystemExit(f"Invalid configuration: {error}") from error
    print("Configuration valid")
