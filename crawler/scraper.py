import os
import asyncio
import json
import random
import logging
from typing import List, Dict, Any, Optional
import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Page, Response

try:
    from curl_cffi import requests as cffi_requests
    HAS_CURL_CFFI = True
except ImportError:
    HAS_CURL_CFFI = False

from config.settings import DEFAULT_UF, DEFAULT_CITY, DEFAULT_DELAY_MIN, DEFAULT_DELAY_MAX, USER_AGENT, DATA_DIR
from crawler.browser import BrowserFactory
from crawler.parser import WebmotorsParser
from database.db_manager import DatabaseManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("WebmotorsScraper")


USER_AGENTS_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

IMPERSONATE_PROFILES = ["chrome124", "chrome120", "edge101", "safari17_0", "chrome110"]

import time


class WebmotorsScraper:
    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager()
        self.intercepted_items: List[Dict[str, Any]] = []
        self._pw_instance = None
        self._pw_context = None
        self._pw_page = None
        self.browser_dir = str(DATA_DIR / "browser_profile")
        self._init_session()

    def _init_session(self):
        proxy = os.environ.get("ALL_PROXY") or os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
        self.proxies = {"http": proxy, "https": proxy} if proxy else None
        if self.proxies:
            logger.info(f"🛡️ Roteamento ativo via proxy: {proxy}")

        if HAS_CURL_CFFI:
            self.http_session = cffi_requests.Session(proxies=self.proxies)
        else:
            self.http_session = requests.Session()
            if self.proxies:
                self.http_session.proxies.update(self.proxies)

    async def _ensure_browser_session(self):
        """Garante uma sessão Chromium com perfil persistente para contornar WAF via in-page execution"""
        if self._pw_page is None:
            logger.info(f"🌐 Inicializando navegador Chromium persistente em: {self.browser_dir}")
            self._pw_instance = await async_playwright().start()
            self._pw_context = await BrowserFactory.create_persistent_context(
                self._pw_instance,
                user_data_dir=self.browser_dir,
                headless=True,
            )
            self._pw_page = await self._pw_context.new_page()
            # Navegar para página inicial do Webmotors para carregar contexto e tokens
            try:
                await self._pw_page.goto("https://www.webmotors.com.br/carros/sp", wait_until="domcontentloaded", timeout=40000)
                await asyncio.sleep(3)
            except Exception as e:
                logger.warning(f"Aviso ao inicializar página base no navegador: {e}")

    async def close_browser(self):
        """Fecha o navegador persistente com segurança"""
        if self._pw_context:
            try:
                await self._pw_context.close()
            except Exception:
                pass
        if self._pw_instance:
            try:
                await self._pw_instance.stop()
            except Exception:
                pass
        self._pw_page = None
        self._pw_context = None
        self._pw_instance = None

    async def scrape_in_page_api(
        self,
        uf: str = "sp",
        pagina: int = 1,
        marca: Optional[str] = None,
        ano_min: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Executa a busca dentro do contexto do Chromium persistente, com tokens nativos do PerimeterX"""
        try:
            await self._ensure_browser_session()

            base_search_url = f"https://www.webmotors.com.br/carros/{uf.lower()}"
            if marca:
                base_search_url += f"/{marca.lower()}"

            query_params = ["tipoveiculo=carros"]
            if ano_min:
                query_params.append(f"anoinicial={ano_min}")

            inner_url = f"{base_search_url}?{'&'.join(query_params)}"
            target_api_url = f"https://www.webmotors.com.br/api/search/car?url={inner_url}&actualPage={pagina}"

            # Executar fetch dentro do navegador (origem autêntica com cookies criptografados)
            res_data = await self._pw_page.evaluate(
                """async (url) => {
                    try {
                        const res = await fetch(url, {
                            headers: {
                                'Accept': 'application/json, text/plain, */*',
                                'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7'
                            }
                        });
                        if (res.status === 200) {
                            return await res.json();
                        } else {
                            return { status: res.status, error: true };
                        }
                    } catch(err) {
                        return { error: err.message };
                    }
                }""",
                target_api_url,
            )

            if isinstance(res_data, dict) and not res_data.get("error"):
                items = res_data.get("SearchResults", []) or []
                collected = []
                for item in items:
                    parsed = WebmotorsParser.parse_json_item(item)
                    if parsed and parsed.get("id_anuncio"):
                        collected.append(parsed)
                if collected:
                    logger.info(f"[Browser-API] Página {pagina} ({uf.upper()}{' - ' + marca.upper() if marca else ''}): {len(collected)} veículos.")
                    return collected

        except Exception as e:
            logger.warning(f"[Browser-API] Erro ao executar in-page fetch: {e}")

        return []

    def scrape_api_page(
        self,
        uf: str = "sp",
        pagina: int = 1,
        marca: Optional[str] = None,
        ano_min: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Extrai anúncios diretamente do endpoint JSON da Webmotors.
        Utiliza rotação de impressões digitais TLS, User-Agents reais e retry com backoff exponencial.
        """
        base_search_url = f"https://www.webmotors.com.br/carros/{uf.lower()}"
        if marca:
            base_search_url += f"/{marca.lower()}"

        query_params = ["tipoveiculo=carros"]
        if ano_min:
            query_params.append(f"anoinicial={ano_min}")

        inner_url = f"{base_search_url}?{'&'.join(query_params)}"
        api_url = f"https://www.webmotors.com.br/api/search/car?url={inner_url}&actualPage={pagina}"

        headers = {
            "Accept": "application/json, text/plain, */*",
            "Referer": inner_url,
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"macOS"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        }

        for attempt in range(1, 4):
            try:
                ua = random.choice(USER_AGENTS_POOL)
                profile = random.choice(IMPERSONATE_PROFILES)
                headers["User-Agent"] = ua

                kw = {"headers": headers, "timeout": 20}
                if self.proxies:
                    kw["proxies"] = self.proxies

                if HAS_CURL_CFFI:
                    resp = self.http_session.get(api_url, impersonate=profile, **kw)
                else:
                    resp = self.http_session.get(api_url, **kw)

                if resp.status_code == 200:
                    data = resp.json()
                    items = data.get("SearchResults", []) or []
                    collected = []
                    for item in items:
                        parsed = WebmotorsParser.parse_json_item(item)
                        if parsed and parsed.get("id_anuncio"):
                            collected.append(parsed)
                    logger.info(f"[API] Página {pagina} ({uf.upper()}{' - ' + marca.upper() if marca else ''}): {len(collected)} veículos coletados.")
                    return collected
                elif resp.status_code in (403, 429):
                    logger.warning(f"[API] HTTP {resp.status_code} na página {pagina} (tentativa {attempt}/3). Renovando sessão e aguardando jitter...")
                    self._init_session()
                    time.sleep(2.0 * attempt + random.uniform(1.0, 2.5))
                else:
                    logger.warning(f"[API] HTTP {resp.status_code} na página {pagina}: {resp.text[:120]}")
                    break
            except Exception as e:
                logger.error(f"[API] Erro de requisição na página {pagina} (tentativa {attempt}): {e}")
                time.sleep(1.5 * attempt)

        return []

    async def _handle_response(self, response: Response):
        """Intercepta requisições de rede para extrair respostas JSON da API de busca (Modo Playwright)"""
        try:
            url = response.url.lower()
            if any(k in url for k in ["api/search/car", "search/car", "services/car", "resultado-busca"]):
                if response.status == 200:
                    try:
                        data = await response.json()
                        vehicles = []
                        if isinstance(data, dict):
                            vehicles = data.get("SearchResults", []) or data.get("Vehicles", []) or data.get("items", [])
                        elif isinstance(data, list):
                            vehicles = data

                        for v in vehicles:
                            parsed = WebmotorsParser.parse_json_item(v)
                            if parsed and parsed.get("id_anuncio"):
                                self.intercepted_items.append(parsed)
                    except Exception:
                        pass
        except Exception:
            pass

    async def scrape_uf_page(
        self,
        page: Page,
        uf: str = "sp",
        pagina: int = 1,
        marca: Optional[str] = None,
        ano_min: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Acessa uma página de listagem no Webmotors via Playwright e extrai veículos"""
        self.intercepted_items.clear()

        base_url = f"https://www.webmotors.com.br/carros/{uf.lower()}"
        if marca:
            base_url = f"https://www.webmotors.com.br/carros/{uf.lower()}/{marca.lower()}"

        query_params = ["tipoveiculo=carros"]
        if pagina > 1:
            query_params.append(f"pag={pagina}")
        if ano_min:
            query_params.append(f"anoinicial={ano_min}")

        target_url = f"{base_url}?{'&'.join(query_params)}"
        logger.info(f"[Browser] Navegando para: {target_url}")

        try:
            await page.goto(target_url, wait_until="domcontentloaded", timeout=45000)
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 3);")
            await asyncio.sleep(random.uniform(1.0, 1.8))
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.7);")
            await asyncio.sleep(random.uniform(1.2, 2.0))

            try:
                await page.wait_for_selector('a[href*="/comprar/"]', timeout=8000)
            except Exception:
                pass

        except Exception as e:
            logger.warning(f"[Browser] Aviso na navegação ({target_url}): {e}")

        collected = []
        if self.intercepted_items:
            logger.info(f"[Browser] Capturados {len(self.intercepted_items)} itens via JSON interceptado.")
            collected = list(self.intercepted_items)
        else:
            logger.info("[Browser] Extraindo dados diretamente dos cards HTML da página...")
            html = await page.content()
            soup = BeautifulSoup(html, "html.parser")
            
            ad_links = soup.find_all("a", href=lambda h: h and "/comprar/" in h)
            visited_ids = set()

            for link in ad_links:
                card_container = link.find_parent("div", class_=lambda c: c and any(w in str(c).lower() for w in ["card", "anuncio", "result", "sc-"])) or link.parent
                parsed = WebmotorsParser.parse_html_card(card_container or link)
                if parsed and parsed["id_anuncio"] not in visited_ids:
                    visited_ids.add(parsed["id_anuncio"])
                    collected.append(parsed)

            logger.info(f"[Browser] Capturados {len(collected)} veículos via HTML.")

        return collected

    async def run_collector(
        self,
        uf: str = "sp",
        marca: Optional[str] = None,
        ano_min: Optional[int] = None,
        max_paginas: int = 5,
        mode: str = "api",
        headless: bool = True,
    ) -> Dict[str, Any]:
        """
        Executa a coleta de múltiplas páginas para o piloto e salva no DuckDB.
        Modo 'api' (padrão): Ultrarrápido, consome o endpoint nativo sem bloqueios.
        Modo 'browser': Playwright stealth com navegação e renderização completa.
        """
        total_coletados = 0
        total_inseridos = 0
        total_atualizados = 0

        if mode == "api":
            logger.info(f"🚀 Iniciando Coletor em Modo API Direto (UF: {uf.upper()}, Marca: {marca or 'TODAS'}, Páginas: {max_paginas})")
            for pag in range(1, max_paginas + 1):
                veiculos = self.scrape_api_page(
                    uf=uf,
                    pagina=pag,
                    marca=marca,
                    ano_min=ano_min,
                )

                if not veiculos:
                    logger.warning(f"Nenhum veículo retornado na página {pag}. Encerrando coleta.")
                    break

                res_db = self.db.upsert_anuncios(veiculos)
                total_coletados += len(veiculos)
                total_inseridos += res_db["inseridos"]
                total_atualizados += res_db["atualizados"]

                logger.info(
                    f"Página {pag}/{max_paginas} gravada no DuckDB: "
                    f"+{res_db['inseridos']} novos, {res_db['atualizados']} atualizados, {res_db['precos_alterados']} preços alterados."
                )

                if pag < max_paginas:
                    delay = random.uniform(0.8, 1.8)
                    await asyncio.sleep(delay)

        else:
            logger.info(f"🌐 Iniciando Coletor em Modo Browser Playwright (UF: {uf.upper()}, Marca: {marca or 'TODAS'}, Páginas: {max_paginas})")
            async with async_playwright() as pw:
                context = await BrowserFactory.create_context(pw, headless=headless)
                page = await context.new_page()
                page.on("response", self._handle_response)

                for pag in range(1, max_paginas + 1):
                    logger.info(f"--- Processando Página {pag}/{max_paginas} ---")
                    veiculos = await self.scrape_uf_page(
                        page=page,
                        uf=uf,
                        pagina=pag,
                        marca=marca,
                        ano_min=ano_min,
                    )

                    if not veiculos:
                        logger.warning(f"Nenhum veículo encontrado na página {pag}. Finalizando coleta.")
                        break

                    res_db = self.db.upsert_anuncios(veiculos)
                    total_coletados += len(veiculos)
                    total_inseridos += res_db["inseridos"]
                    total_atualizados += res_db["atualizados"]

                    logger.info(
                        f"Página {pag} gravada no DuckDB: "
                        f"+{res_db['inseridos']} novos, {res_db['atualizados']} atualizados."
                    )

                    if pag < max_paginas:
                        delay = random.uniform(DEFAULT_DELAY_MIN, DEFAULT_DELAY_MAX)
                        await asyncio.sleep(delay)

                await context.close()

        logger.info(f"=== Coleta Concluída: {total_coletados} coletados, {total_inseridos} novos gravados no DuckDB. ===")
        return {
            "total_coletados": total_coletados,
            "novos_inseridos": total_inseridos,
            "atualizados": total_atualizados,
        }
