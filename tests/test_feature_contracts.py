"""Feature contracts: normal use, boundary values and failure handling for each area."""
import copy
import json

import pytest

from backend.configuration import ConfigurationError, DEFAULT_PATH, load_config, validate
from backend.auth import validate_accounts


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_site_settings_three_cases(case):
    config = load_config(DEFAULT_PATH)
    if case == "normaal":
        assert validate(config)["site"]["refreshSeconds"] == 30
    elif case == "boundary":
        for value in (5, 3600):
            config["site"]["refreshSeconds"] = value
            assert validate(config)["site"]["refreshSeconds"] == value
    else:
        for value in (4, 3601, True):
            config["site"]["refreshSeconds"] = value
            with pytest.raises(ConfigurationError): validate(config)


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_provider_settings_three_cases(case):
    config = load_config(DEFAULT_PATH)
    if case == "normaal":
        config["providers"][0].update(enabled=True, url="https://kasm.example.test")
        assert validate(config)["providers"][0]["enabled"] is True
    elif case == "boundary":
        assert validate(config)["providers"][0]["url"] is None
    else:
        config["providers"][0].update(enabled=True, url=None)
        with pytest.raises(ConfigurationError): validate(config)


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_module_pages_three_cases(case):
    config = load_config(DEFAULT_PATH)
    module = next(m for m in config["modules"] if m["id"] == "proxmox")
    if case == "normaal":
        assert validate(config)["modules"][3]["pages"][0]["id"] == "nodes"
    elif case == "boundary":
        module["enabled"] = False
        result = validate(config)
        assert all(m["id"] != "proxmox" for m in result["modules"])
        group = next(item for item in result["menu"] if item["id"] == "proxmox")
        assert all(not child["route"].startswith("proxmox") for child in group["children"])
    else:
        module["pages"].append(copy.deepcopy(module["pages"][0]))
        with pytest.raises(ConfigurationError): validate(config)


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_menu_settings_three_cases(case):
    config = load_config(DEFAULT_PATH)
    if case == "normaal":
        config["menu"][0]["label"] = "Mijn dashboard"
        assert validate(config)["menu"][0]["label"] == "Mijn dashboard"
    elif case == "boundary":
        group = next(item for item in config["menu"] if item["id"] == "proxmox")
        for child in group["children"]: child["enabled"] = False
        assert all(item["id"] != "proxmox" for item in validate(config)["menu"])
    else:
        config["menu"][0]["route"] = "missing"
        with pytest.raises(ConfigurationError): validate(config)


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_widget_definitions_three_cases(case):
    config = load_config(DEFAULT_PATH)
    config["providers"][0].update(enabled=True,url="https://kasm.example.test")
    config["modules"].append({"id":"kasm","title":"Kasm","enabled":True,"view":"integration","provider":"kasm"})
    config["widgets"] = [{"id":"kasm","title":"Kasm","enabled":True,"provider":"kasm","route":"kasm"}]
    if case == "normaal":
        assert validate(config)["widgets"][0]["id"] == "kasm"
    elif case == "boundary":
        config["widgets"][0]["enabled"] = False
        assert validate(config)["widgets"] == []
    else:
        config["widgets"][0]["route"] = "missing"
        with pytest.raises(ConfigurationError): validate(config)


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_account_profile_three_cases(case):
    account = {"email":"user@example.test","role":"user","firstName":"New","lastName":"Person"}
    if case == "normaal":
        result = validate_accounts([account])[0]
        assert result["enabled"] is True and result["ssoType"] == "google"
    elif case == "boundary":
        account.update(firstName="a"*100,lastName="b"*100,enabled=False,ssoType="windows")
        assert validate_accounts([account])[0]["enabled"] is False
    else:
        account["firstName"] = "a"*101
        with pytest.raises(ConfigurationError): validate_accounts([account])

@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_configuration_file_size_three_cases(tmp_path, case):
    config = load_config(DEFAULT_PATH)
    raw = json.dumps(config).encode()
    maximum = 256 * 1024
    size = len(raw) if case == "normaal" else maximum + (1 if case == "faal" else 0)
    path = tmp_path / "controldeck.json"
    path.write_bytes(raw + b" "*(size-len(raw)))
    if case == "faal":
        with pytest.raises(ConfigurationError): load_config(path)
    else:
        assert load_config(path)["site"]["title"] == "ControlDeck"
