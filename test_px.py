import requests
from curl_cffi import requests as cffi_requests

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
}

# 1. Testar home page
r1 = cffi_requests.get("https://www.webmotors.com.br/", headers=headers, impersonate="chrome124")
print("Home status:", r1.status_code)

# 2. Testar API com cookies da home
session = cffi_requests.Session()
r_home = session.get("https://www.webmotors.com.br/", headers=headers, impersonate="chrome124")
api_headers = {
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.webmotors.com.br/carros/sp/chevrolet?tipoveiculo=carros",
    "Accept-Language": "pt-BR,pt;q=0.9",
}
r2 = session.get("https://www.webmotors.com.br/api/search/car?url=https://www.webmotors.com.br/carros/sp/chevrolet?tipoveiculo=carros&actualPage=1", headers=api_headers, impersonate="chrome124")
print("API status:", r2.status_code)
if r2.status_code == 200:
    print("API results:", len(r2.json().get("SearchResults", [])))
else:
    print("API body:", r2.text[:200])
