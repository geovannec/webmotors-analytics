import asyncio
import argparse
import sys
import os
import signal
import json
from pathlib import Path

# Adicionar pasta raiz ao path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from config.settings import DAEMON_INTERVAL_SECONDS, DAEMON_STATUS_PATH, DATA_DIR
from crawler.scheduler import CrawlerDaemon


def print_status():
    pid_file = DATA_DIR / "daemon.pid"
    is_running = False
    pid = None

    if pid_file.exists():
        try:
            with open(pid_file, "r") as f:
                pid = int(f.read().strip())
            # Checar se processo está vivo no OS
            os.kill(pid, 0)
            is_running = True
        except (OSError, ValueError):
            is_running = False

    print("==================================================")
    print("⏰ WebMotors Analytics - Status do Serviço Horário")
    print("==================================================")
    print(f"Estado do Processo: {'🟢 ATIVO (Rodando)' if is_running else '🔴 PARADO'}")
    if pid and is_running:
        print(f"PID: {pid}")

    if DAEMON_STATUS_PATH.exists():
        try:
            with open(DAEMON_STATUS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            print(f"Status Reportado: {data.get('status', 'DESCONHECIDO')}")
            print(f"Intervalo: a cada {data.get('intervalo_minutos', 60)} minutos")
            print(f"Última Atualização: {data.get('ultima_atualizacao', 'N/A')}")
            print(f"Último Início de Ciclo: {data.get('ultimo_ciclo_inicio', 'N/A')}")
            print(f"Próximo Ciclo Previsto: {data.get('proximo_ciclo', 'N/A')}")
            print(f"Ciclos Completados: {data.get('ciclos_completados', 0)}")
            print(f"Total Coletados Acumulado: {data.get('total_coletados_acumulado', 0):,}")
            print(f"Novos Inseridos Acumulado: {data.get('total_novos_acumulado', 0):,}")
            print(f"Atualizados Acumulado: {data.get('total_atualizados_acumulado', 0):,}")
        except Exception as e:
            print(f"Erro ao ler detalhes de status: {e}")
    else:
        print("Nenhum histórico de execução do daemon encontrado.")
    print("==================================================")


def stop_daemon():
    pid_file = DATA_DIR / "daemon.pid"
    if not pid_file.exists():
        print("Nenhum daemon em execução encontrado (arquivo pid ausente).")
        return

    try:
        with open(pid_file, "r") as f:
            pid = int(f.read().strip())
        print(f"Enviando sinal de parada para o daemon (PID: {pid})...")
        os.kill(pid, signal.SIGTERM)
        print("✅ Sinal enviado com sucesso. O daemon finalizará de forma graciosa.")
    except Exception as e:
        print(f"Erro ao parar daemon: {e}")


def main():
    parser = argparse.ArgumentParser(description="WebMotors Analytics - Daemon de Atualização Horária")
    parser.add_argument("--interval", type=int, default=DAEMON_INTERVAL_SECONDS, help="Intervalo entre coletas em segundos (padrão: 3600 = 1 hora)")
    parser.add_argument("--tier", type=str, choices=["1", "2", "3", "all"], default="1", help="Tier de estados para cada ciclo (padrão: 1 = SP, RJ, MG, PR, SC, RS)")
    parser.add_argument("--brands-cat", type=str, choices=["volume", "luxury", "ev", "all", "none"], default="volume", help="Categoria de marcas (padrão: volume)")
    parser.add_argument("--pages-per-shard", type=int, default=2, help="Páginas por shard em cada ciclo (padrão: 2)")
    parser.add_argument("--run-once", action="store_true", help="Executar apenas 1 ciclo imediato e encerrar")
    parser.add_argument("--status", action="store_true", help="Exibir status do daemon em execução")
    parser.add_argument("--stop", action="store_true", help="Solicitar parada do daemon em execução")

    args = parser.parse_args()

    if args.status:
        print_status()
        return

    if args.stop:
        stop_daemon()
        return

    print("==================================================")
    print("🚀 Iniciando Serviço de Atualização Horária Contínua")
    print(f"⏰ Intervalo: {args.interval} segundos ({args.interval // 60} minutos)")
    print(f"📍 Cobertura: Tier {args.tier.upper()} | Marcas: {args.brands_cat.upper()} | Págs/Shard: {args.pages_per_shard}")
    print(f"🔄 Modo: {'Execução Única (--run-once)' if args.run_once else 'Daemon Contínuo (24/7)'}")
    print("==================================================")

    daemon = CrawlerDaemon(
        interval_seconds=args.interval,
        tier=args.tier,
        brands_cat=args.brands_cat,
        pages_per_shard=args.pages_per_shard,
    )

    asyncio.run(daemon.start(run_once=args.run_once))


if __name__ == "__main__":
    main()
