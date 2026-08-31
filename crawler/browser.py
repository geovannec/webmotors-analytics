import os
import asyncio
import random
from typing import Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from config.settings import USER_AGENT, VIEWPORT


class BrowserFactory:
    """Gerenciador de navegador Playwright com perfil stealth anti-detecção"""

    @staticmethod
    async def create_persistent_context(playwright_instance, user_data_dir: str, headless: bool = True) -> BrowserContext:
        """Cria ou recupera um contexto de navegador persistente salvo no disco (mantém cookies do PerimeterX)"""
        args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-infobars",
            "--window-position=0,0",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
        ]

        proxy_env = os.environ.get("ALL_PROXY") or os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
        proxy_dict = None
        if proxy_env:
            proxy_clean = proxy_env.replace("socks5h://", "socks5://")
            proxy_dict = {"server": proxy_clean}

        context: BrowserContext = await playwright_instance.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=headless,
            args=args,
            proxy=proxy_dict,
            user_agent=USER_AGENT,
            viewport=VIEWPORT,
            locale="pt-BR",
            timezone_id="America/Sao_Paulo",
            color_scheme="light",
            extra_http_headers={
                "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            },
        )

        await context.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['pt-BR', 'pt', 'en-US', 'en'] });
            window.chrome = { runtime: {}, loadTimes: function() {}, csi: function() {}, app: {} };
            """
        )

        return context

    @staticmethod
    async def create_context(playwright_instance, headless: bool = True) -> BrowserContext:
        args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-infobars",
            "--window-position=0,0",
            "--ignore-certifcate-errors",
            "--ignore-certifcate-errors-spki-list",
            "--disable-dev-shm-usage",
            "--disable-accelerated-2d-canvas",
            "--disable-gpu",
        ]

        browser: Browser = await playwright_instance.chromium.launch(
            headless=headless,
            args=args,
        )

        context: BrowserContext = await browser.new_context(
            user_agent=USER_AGENT,
            viewport=VIEWPORT,
            locale="pt-BR",
            timezone_id="America/Sao_Paulo",
            color_scheme="light",
            extra_http_headers={
                "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            },
        )

        # Injetar script para neutralizar flags de automação (stealth)
        await context.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
            Object.defineProperty(navigator, 'languages', {
                get: () => ['pt-BR', 'pt', 'en-US', 'en'],
            });
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {}
            };
            """
        )

        return context
