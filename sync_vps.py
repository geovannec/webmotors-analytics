import subprocess
import sys
import logging
from pathlib import Path
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("VPSSync")

BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "data" / "webmotors.duckdb"
STATUS_FILE = BASE_DIR / "data" / "daemon_status.json"


def sync():
    logger.info("🚀 Iniciando sincronização da base de dados com a VPS Hostinger...")

    if not DB_FILE.exists():
        logger.error(f"Arquivo de banco não encontrado em {DB_FILE}")
        return False

    try:
        # 1. Git add e commit
        logger.info("📦 Empacotando banco de dados atualizado...")
        subprocess.run(["git", "add", str(DB_FILE), str(STATUS_FILE)], check=True, cwd=BASE_DIR)
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        commit_res = subprocess.run(
            ["git", "commit", "-m", f"chore(db): sync live database to Hostinger VPS ({timestamp})"],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
        )
        if "nothing to commit" in commit_res.stdout:
            logger.info("ℹ️ Nenhuma alteração pendente no banco de dados local.")
        else:
            logger.info("✅ Commit registrado com sucesso.")

        # 2. Git push para GitHub
        logger.info("⬆️ Enviando dados para o repositório remoto...")
        subprocess.run(["git", "push", "origin", "main"], check=True, cwd=BASE_DIR)
        subprocess.run(["git", "push", "origin", "master"], check=True, cwd=BASE_DIR)
        logger.info("✅ Dados enviados para o GitHub com sucesso.")

        logger.info("==========================================================")
        logger.info("🎉 Sincronização concluída!")
        logger.info(f"🌐 Acesse seu aplicativo na Hostinger em: http://187.77.230.235:8501")
        logger.info("==========================================================")
        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Erro durante sincronização: {e}")
        return False


if __name__ == "__main__":
    sync()
