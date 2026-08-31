import os
import sys
import time
import json
import signal
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from config.settings import (
    DAEMON_INTERVAL_SECONDS,
    DAEMON_STATUS_PATH,
    DATA_DIR,
    ALL_UFS,
    UFS_TIER_1,
    UFS_TIER_2,
    ALL_BRANDS,
    TARGET_BRANDS,
    DEFAULT_DELAY_MIN,
    DEFAULT_DELAY_MAX,
)
from database.db_manager import DatabaseManager
from crawler.orchestrator import NationalCrawlerOrchestrator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [DAEMON] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(DATA_DIR / "daemon.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("CrawlerDaemon")


class CrawlerDaemon:
    """
    Serviço contínuo que executa a sincronização completa do WebMotors
    a cada hora, atualizando automaticamente anúncios novos e alterados.
    """

    def __init__(
        self,
        interval_seconds: int = DAEMON_INTERVAL_SECONDS,
        tier: str = "all",
        brands_cat: str = "all",
        pages_per_shard: int = 0,
        db_manager: Optional[DatabaseManager] = None,
    ):
        self.interval = interval_seconds
        self.tier = tier
        self.brands_cat = brands_cat
        self.pages_per_shard = pages_per_shard
        self.db = db_manager or DatabaseManager()
        self.orchestrator = NationalCrawlerOrchestrator(self.db)
        self.stop_requested = False
        self.pid_file = DATA_DIR / "daemon.pid"

        # Capturar sinais do sistema
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

    def _handle_shutdown(self, signum, frame):
        logger.warning(f"Sinal de encerramento recebido ({signum}). Finalizando ciclo com segurança...")
        self.stop_requested = True
        self.orchestrator.stop_requested = True

    def _save_pid(self):
        with open(self.pid_file, "w") as f:
            f.write(str(os.getpid()))

    def _remove_pid(self):
        if self.pid_file.exists():
            self.pid_file.unlink(missing_ok=True)

    def update_status(self, status: str, extra: Optional[Dict[str, Any]] = None):
        """Salva o estado atual do daemon em JSON para telemetria em tempo real"""
        payload = {
            "status": status,
            "pid": os.getpid(),
            "intervalo_minutos": self.interval // 60,
            "ultima_atualizacao": datetime.now().isoformat(),
        }
        if DAEMON_STATUS_PATH.exists():
            try:
                with open(DAEMON_STATUS_PATH, "r", encoding="utf-8") as f:
                    antigo = json.load(f)
                    payload["ciclos_completados"] = antigo.get("ciclos_completados", 0)
                    payload["total_coletados_acumulado"] = antigo.get("total_coletados_acumulado", 0)
                    payload["total_novos_acumulado"] = antigo.get("total_novos_acumulado", 0)
                    payload["total_atualizados_acumulado"] = antigo.get("total_atualizados_acumulado", 0)
                    payload["ultimo_ciclo_inicio"] = antigo.get("ultimo_ciclo_inicio")
                    payload["ultimo_ciclo_fim"] = antigo.get("ultimo_ciclo_fim")
                    payload["proximo_ciclo"] = antigo.get("proximo_ciclo")
            except Exception:
                pass

        if extra:
            payload.update(extra)

        try:
            with open(DAEMON_STATUS_PATH, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Erro ao salvar status do daemon: {e}")

    async def execute_cycle(self) -> Dict[str, Any]:
        """Executa um ciclo completo de sincronização nacional"""
        id_execucao = f"EXEC_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        inicio = datetime.now()
        logger.info(f"🚀 Iniciando Ciclo Horário [{id_execucao}]...")

        self.db.iniciar_execucao(id_execucao=id_execucao, uf="NACIONAL", marca="TODAS")
        self.update_status("EM_EXECUCAO", {
            "ultimo_ciclo_inicio": inicio.isoformat(),
            "execucao_atual": id_execucao,
        })

        try:
            # Shards direcionados por marca para evitar disparo de WAF e sobrecarga
            todos_os_shards = self.orchestrator.build_shards(tier=self.tier, brands_category=self.brands_cat)

            logger.info(f"📋 Total de partições por marca mapeadas para este ciclo: {len(todos_os_shards)}")

            resultado = await self.orchestrator.run(
                shards=todos_os_shards,
                pages_per_shard=self.pages_per_shard,
                resume=True,  # Retoma de onde parou caso haja interrupção
                delay_min=1.8,
                delay_max=3.2,
            )
            # Limpar checkpoint ao final do ciclo para a próxima hora
            self.orchestrator.checkpoint_mgr.clear()

            fim = datetime.now()
            self.db.finalizar_execucao(
                id_execucao=id_execucao,
                total_processados=resultado["total_coletados"],
                novos=resultado["novos_inseridos"],
                atualizados=resultado["atualizados"],
                status="SUCESSO",
            )

            logger.info(
                f"✅ Ciclo Horário Concluído em {(fim - inicio).total_seconds():.1f}s: "
                f"+{resultado['novos_inseridos']} novos, {resultado['atualizados']} atualizados "
                f"({resultado['total_coletados']} processados no total)."
            )

            return resultado

        except Exception as e:
            logger.error(f"❌ Erro durante o ciclo {id_execucao}: {e}")
            self.db.finalizar_execucao(id_execucao=id_execucao, total_processados=0, novos=0, atualizados=0, status="ERRO")
            raise

    async def start(self, run_once: bool = False):
        """Inicia o loop contínuo agendado a cada hora"""
        self._save_pid()
        logger.info(f"⏰ Serviço de Atualização Horária iniciado (PID: {os.getpid()}). Intervalo: {self.interval}s ({self.interval//60} min)")

        ciclos = 0
        total_coletados_geral = 0
        total_novos_geral = 0
        total_atualizados_geral = 0

        try:
            while not self.stop_requested:
                ciclo_inicio = datetime.now()
                proximo = ciclo_inicio + timedelta(seconds=self.interval)

                try:
                    resultado = await self.execute_cycle()
                    ciclos += 1
                    total_coletados_geral += resultado["total_coletados"]
                    total_novos_geral += resultado["novos_inseridos"]
                    total_atualizados_geral += resultado["atualizados"]

                    self.update_status("AGUARDANDO", {
                        "ultimo_ciclo_fim": datetime.now().isoformat(),
                        "proximo_ciclo": proximo.isoformat(),
                        "ciclos_completados": ciclos,
                        "total_coletados_acumulado": total_coletados_geral,
                        "total_novos_acumulado": total_novos_geral,
                        "total_atualizados_acumulado": total_atualizados_geral,
                        "ultimo_resultado": resultado,
                    })

                except Exception as e:
                    self.update_status("ERRO", {"erro": str(e), "proximo_ciclo": proximo.isoformat()})

                if run_once:
                    logger.info("Execução única concluída com sucesso. Finalizando serviço.")
                    break

                logger.info(f"💤 Aguardando próximo ciclo horário previsto para: {proximo.strftime('%H:%M:%S')}...")
                
                # Aguardar o intervalo verificando pedido de parada a cada segundo
                segundos_espera = 0
                while segundos_espera < self.interval and not self.stop_requested:
                    await asyncio.sleep(1)
                    segundos_espera += 1

        finally:
            self._remove_pid()
            self.update_status("PARADO")
            logger.info("🛑 Serviço de Atualização Horária finalizado.")
