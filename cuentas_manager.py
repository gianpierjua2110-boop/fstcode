import json
import os

CONFIG_FILE = "config_cuentas.json"

def init_cuentas():
    if not os.path.exists(CONFIG_FILE):
        default_data = {
            "sdnet_emails": [
                "meryn_megann4735@hotmail.com", "coraleigh.lxtm265@hotmail.com", 
                "blen-poa_reice@hotmail.com", "csdqqnktq287@hotmail.com", 
                "naysha_brittanieic@hotmail.com"
            ],
            "gmail_passwords": {
                "gianbc66@gmail.com": "cyfjxttjgbunefmh",
                "oscaqn23@gmail.com": "dwngfavhysbzonhm",
                "streaming6a@gmail.com": "ldyiorcltyjksdxi"
            },
            "cpanel_accounts": {
                "yogun@mttplay.net": {"pass": "0;P+GL%+_}%9WQ=D", "server": "mttplay.net"},
                "bebetio@globalmtt.com": {"pass": "fdBfl(!dDBevo8x}", "server": "globalmtt.com"},
                "ancelin763nertiean@strmttb.com": {"pass": "9F5pu}!*GyPXV(^L", "server": "strmttb.com"}
            }
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(default_data, f, indent=4)

def cargar_cuentas():
    init_cuentas()
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    if "wsp_emails" not in data:
        data["wsp_emails"] = []
    return data

def guardar_cuentas(data):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

init_cuentas()
