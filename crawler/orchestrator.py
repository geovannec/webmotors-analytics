import asyncio
import json
import random
import logging
import signal
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from config.settings import (
    CHECKPOINT_PATH,
    UFS_TIER_1,
    UFS_TIER_2,
    UFS_TIER_3,
    ALL_UFS,
    TARGET_BRANDS,
    BRANDS_VOLUME,
    BRANDS_LUXURY,
    BRANDS_EV,
    DEFAULT_DELAY_MIN,
    DEFAULT_DELAY_MAX,
)
from crawler.scraper import WebmotorsScraper
from database.db_manager import DatabaseManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("CrawlerOrchestrator")


class CheckpointManager:
    """Gerencia o salvamento e recuperação do progresso da coleta nacional"""

    def __init__(self, path: Path = CHECKPOINT_PATH):
        self.path = path

    def load(self) -> Dict[str, Any]:
        if self.path.exists():
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Erro ao ler checkpoint: {e}. Iniciando novo.")
        return {
            "completed_shards": [],
            "total_coletados": 0,
            "novos_inseridos": 0,
            "atualizados": 0,
            "timestamp_inicio": datetime.now().isoformat(),
            "ultimo_shard": None,
        }

    def save(self, data: Dict[str, Any]):
        data["ultima_atualizacao"] = datetime.now().isoformat()
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Erro ao salvar checkpoint: {e}")

    def clear(self):
        if self.path.exists():
            self.path.unlink(missing_ok=True)


class NationalCrawlerOrchestrator:
    """
    Orquestrador de coleta em escala nacional com particionamento (sharding)
    por UF e Marca, rate limiting inteligente e retomada automática via checkpoint.
    """

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager()
        self.scraper = WebmotorsScraper(self.db)
        self.checkpoint_mgr = CheckpointManager()
        self.stop_requested = False

        # Registrar tratamento gracioso de interrupção
        signal.signal(signal.SIGINT, self._handle_interrupt)

    def _handle_interrupt(self, sig, frame):
        logger.warning("\n⚠️ Interrupção detectada (Ctrl+C). Finalizando lote atual com segurança...")
        self.stop_requested = True

    def build_shards(
        self,
        tier: str = "1",
        brands_category: str = "volume",
        custom_ufs: Optional[List[str]] = None,
        custom_brands: Optional[List[str]] = None,
    ) -> List[Tuple[str, Optional[str]]]:
        """Constrói a matriz de partições (UF, Marca) com base nos parâmetros"""
        # Definir lista de UFs
        if custom_ufs:
            ufs = [u.lower() for u in custom_ufs]
        elif tier == "1":
            ufs = UFS_TIER_1
        elif tier == "2":
            ufs = UFS_TIER_2
        elif tier == "3":
            ufs = UFS_TIER_3
        elif tier == "all":
            ufs = ALL_UFS
        else:
            ufs = UFS_TIER_1

        # Definir lista de Marcas
        if custom_brands:
            brands = [b.lower() if b != "TODAS" else None for b in custom_brands]
        elif brands_category == "volume":
            brands = [b.lower() for b in BRANDS_VOLUME]
        elif brands_category == "luxury":
            brands = [b.lower() for b in BRANDS_LUXURY]
        elif brands_category == "ev":
            brands = [b.lower() for b in BRANDS_EV]
        elif brands_category == "all":
            brands = [b.lower() for b in TARGET_BRANDS]
        elif brands_category == "none":
            brands = [None]  # Apenas por UF geral
        else:
            brands = [b.lower() for b in BRANDS_VOLUME]

        shards = []
        for uf in ufs:
            for b in brands:
                shards.append((uf, b))

        return shards

    async def run(
        self,
        shards: List[Tuple[str, Optional[str]]],
        pages_per_shard: int = 3,
        resume: bool = True,
        delay_min: float = DEFAULT_DELAY_MIN,
        delay_max: float = DEFAULT_DELAY_MAX,
    ) -> Dict[str, Any]:
        """
        Executa a varredura nacional por todos os shards definidos.
        """
        self.stop_requested = False
        cp = self.checkpoint_mgr.load() if resume else {
            "completed_shards": [],
            "total_coletados": 0,
            "novos_inseridos": 0,
            "atualizados": 0,
            "timestamp_inicio": datetime.now().isoformat(),
            "ultimo_shard": None,
        }

        completed_set = set(cp.get("completed_shards", []))
        total_shards = len(shards)
        logger.info(f"🌍 Iniciando Varredura Nacional | Total de Shards: {total_shards} | Retomada: {resume}")

        for idx, (uf, marca) in enumerate(shards, 1):
            if self.stop_requested:
                logger.info("🛑 Execução pausada a pedido do usuário. Checkpoint salvo com sucesso!")
                break

            shard_key = f"{uf.upper()}:{marca.upper() if marca else 'GERAL'}"

            if resume and shard_key in completed_set:
                continue

            max_pages = 250 if pages_per_shard <= 0 else pages_per_shard
            mode_str = "Exaustivo (todos os anúncios disponíveis)" if pages_per_shard <= 0 else f"{pages_per_shard} páginas"
            logger.info(f"\n[{idx}/{total_shards}] Coletando Shard: {shard_key} ({mode_str})")

            shard_coletados = 0
            for pag in range(1, max_pages + 1):
                if self.stop_requested:
                    break

                veiculos = self.scraper.scrape_api_page(
                    uf=uf,
                    pagina=pag,
                    marca=marca,
                )

                if not veiculos:
                    # Não há mais anúncios nessa fatia
                    break

                res_db = self.db.upsert_anuncios(veiculos)
                shard_coletados += len(veiculos)
                cp["total_coletados"] += len(veiculos)
                cp["novos_inseridos"] += res_db["inseridos"]
                cp["atualizados"] += res_db["atualizados"]

                # Pequena pausa entre páginas da mesma fatia
                delay = random.uniform(delay_min, delay_max)
                await asyncio.sleep(delay)

            # Marcar shard como concluído
            completed_set.add(shard_key)
            cp["completed_shards"] = list(completed_set)
            cp["ultimo_shard"] = shard_key
            self.checkpoint_mgr.save(cp)

            logger.info(
                f"✅ Concluído {shard_key}: +{shard_coletados} coletados | "
                f"Progresso Global: {len(completed_set)}/{total_shards} shards ({len(completed_set)/total_shards*100:.1f}%)"
            )

        metricas = self.db.get_metricas_gerais()
        logger.info(
            f"\n🏁 Coleta Finalizada! Total na Sessão: {cp['total_coletados']} | Novos no Banco: {cp['novos_inseridos']}\n"
            f"📊 Total Atual no DuckDB: {metricas['total_veiculos']} veículos em {metricas['total_marcas']} marcas."
        )

        return {
            "total_coletados": cp["total_coletados"],
            "novos_inseridos": cp["novos_inseridos"],
            "atualizados": cp["atualizados"],
            "shards_concluidos": len(completed_set),
            "total_shards": total_shards,
        }
