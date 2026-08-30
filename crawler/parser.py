import re
from typing import Dict, Any, Optional, List
from bs4 import BeautifulSoup


class WebmotorsParser:
    """Extrai e higieniza informações de veículos a partir de JSON ou HTML do Webmotors"""

    @staticmethod
    def clean_number(text: Optional[str]) -> float:
        """Extrai apenas dígitos e converte para float/int"""
        if not text:
            return 0.0
        # Remove R$, km, pontos e espaços
        cleaned = re.sub(r"[^\d,]", "", str(text))
        if "," in cleaned:
            cleaned = cleaned.replace(",", ".")
        try:
            return float(cleaned)
        except ValueError:
            return 0.0

    @staticmethod
    def parse_ano(ano_str: Optional[str]) -> tuple[int, int]:
        """Extrai ano de fabricação e ano modelo (ex: '2023/2024' -> (2023, 2024))"""
        if not ano_str:
            return 0, 0
        matches = re.findall(r"\b(19\d\d|20\d\d)\b", str(ano_str))
        if len(matches) >= 2:
            return int(matches[0]), int(matches[1])
        elif len(matches) == 1:
            val = int(matches[0])
            return val, val
        return 0, 0

    @classmethod
    def parse_json_item(cls, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Processa um item retornado pelas APIs internas de busca do Webmotors"""
        try:
            specification = item.get("Specification", {})
            prices = item.get("Prices", {})
            seller = item.get("Seller", {})

            aid = str(item.get("UniqueId") or item.get("Id") or "").strip()
            if not aid:
                return None

            marca = str(specification.get("Make", {}).get("Value") or "").strip().upper()
            modelo = str(specification.get("Model", {}).get("Value") or "").strip().upper()
            versao = str(specification.get("Version", {}).get("Value") or "").strip()

            try:
                ano_fab = int(float(specification.get("YearFabrication") or 0))
            except (ValueError, TypeError):
                ano_fab = 0

            try:
                ano_mod = int(float(specification.get("YearModel") or 0))
            except (ValueError, TypeError):
                ano_mod = 0

            try:
                km = float(specification.get("Odometer") or 0.0)
            except (ValueError, TypeError):
                km = 0.0

            try:
                preco = float(prices.get("Price") or 0.0)
            except (ValueError, TypeError):
                preco = 0.0

            cidade = str(seller.get("City") or "").strip()
            estado = str(seller.get("State") or "").strip()
            tipo_vendedor = str(seller.get("SellerType") or "LOJA").strip()

            # Normalização da foto com CDN do Webmotors
            fotos = item.get("Media", {}).get("Photos", [])
            foto_path = fotos[0].get("PhotoPath", "") if fotos else ""
            if foto_path:
                clean_path = str(foto_path).replace("\\", "/").strip()
                if clean_path.startswith("http"):
                    foto_url = clean_path
                else:
                    foto_url = f"https://image.webmotors.com.br/_fotos/AnuncioUsados/G/{clean_path}"
            else:
                foto_url = ""

            url_anuncio = f"https://www.webmotors.com.br/comprar/{marca.lower()}/{modelo.lower()}/{aid}"

            return {
                "id_anuncio": aid,
                "marca": marca or "OUTROS",
                "modelo": modelo or "DIVERSOS",
                "versao": versao,
                "ano_fabricacao": ano_fab,
                "ano_modelo": ano_mod,
                "quilometragem": km,
                "preco": preco,
                "cidade": cidade,
                "estado": estado,
                "tipo_vendedor": tipo_vendedor,
                "url_anuncio": url_anuncio,
                "foto_url": foto_url,
            }
        except Exception:
            return None

    @classmethod
    def parse_html_card(cls, card_element) -> Optional[Dict[str, Any]]:
        """Extrai dados a partir de um card HTML da listagem"""
        try:
            # Buscar link com o ID
            link = card_element.find("a", href=re.compile(r"/comprar/"))
            if not link:
                return None

            href = link.get("href", "")
            match_id = re.search(r"/(\d+)(?:\?|$)", href)
            if not match_id:
                return None
            aid = match_id.group(1)

            # Título (Marca e Modelo)
            title_tag = card_element.find(["h2", "h3"]) or link
            title_text = title_tag.get_text(separator=" ", strip=True) if title_tag else ""

            # Versão
            versao_tag = card_element.find(attrs={"class": re.compile(r"version|sub-title", re.I)})
            versao = versao_tag.get_text(strip=True) if versao_tag else ""

            # Extrair Marca e Modelo do título ou da URL
            # Ex URL: /comprar/hyundai/hb20/10-12v-flex-limited-manual/.../59319787
            url_parts = [p for p in href.split("/") if p]
            marca = ""
            modelo = ""
            if "comprar" in url_parts:
                idx = url_parts.index("comprar")
                if len(url_parts) > idx + 1:
                    marca = url_parts[idx + 1].upper()
                if len(url_parts) > idx + 2:
                    modelo = url_parts[idx + 2].upper()

            if not marca and title_text:
                parts = title_text.split()
                marca = parts[0].upper() if parts else "OUTROS"
                modelo = parts[1].upper() if len(parts) > 1 else ""

            # Preço
            price_tag = card_element.find(text=re.compile(r"R\$\s*[\d\.]+"))
            preco = cls.clean_number(price_tag) if price_tag else 0.0

            # Ano e KM
            ano_fab, ano_mod = 0, 0
            km = 0.0
            text_all = card_element.get_text(" ", strip=True)
            ano_match = re.search(r"\b(20\d\d\s*/\s*20\d\d|20\d\d)\b", text_all)
            if ano_match:
                ano_fab, ano_mod = cls.parse_ano(ano_match.group(1))

            km_match = re.search(r"([\d\.]+)\s*(?:km|KM)", text_all)
            if km_match:
                km = cls.clean_number(km_match.group(1))

            # Cidade / Estado
            cidade, estado = "", ""
            uf_match = re.search(r"([A-Za-zÀ-ÿ\s]+)\s*-\s*([A-Z]{2})", text_all)
            if uf_match:
                cidade = uf_match.group(1).strip()
                estado = uf_match.group(2).strip()

            # Imagem
            img = card_element.find("img", src=True)
            foto_url = img["src"] if img else ""

            full_url = href if href.startswith("http") else f"https://www.webmotors.com.br{href}"

            return {
                "id_anuncio": aid,
                "marca": marca,
                "modelo": modelo,
                "versao": versao,
                "ano_fabricacao": ano_fab,
                "ano_modelo": ano_mod,
                "quilometragem": km,
                "preco": preco,
                "cidade": cidade,
                "estado": estado,
                "tipo_vendedor": "LOJA" if "concessionária" not in text_all.lower() else "CONCESSIONARIA",
                "url_anuncio": full_url,
                "foto_url": foto_url,
            }
        except Exception:
            return None
