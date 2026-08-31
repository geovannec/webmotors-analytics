import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# Caminho do banco e checkpoints
DB_PATH = DATA_DIR / "webmotors.duckdb"
CHECKPOINT_PATH = DATA_DIR / "crawler_checkpoint.json"

# Parâmetros padrão do Crawler
DEFAULT_UF = "sp"
DEFAULT_CITY = "São Paulo"
DEFAULT_DELAY_MIN = 1.8
DEFAULT_DELAY_MAX = 3.2
MAX_PAGES_PER_RUN = 100

# User agent e viewport padrão
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
)

VIEWPORT = {"width": 1440, "height": 900}

# Matriz Nacional de UFs por Tiers de Volume
UFS_TIER_1 = ["sp", "rj", "mg", "pr", "sc", "rs"]  # Polos de maior volume (~80% do estoque)
UFS_TIER_2 = ["ba", "go", "df", "pe", "ce", "es", "mt", "ms"]  # Centro-Oeste e Nordeste principais
UFS_TIER_3 = ["pa", "am", "rn", "pb", "al", "se", "pi", "ma", "to", "ro", "ac", "ap", "rr"]  # Demais estados

ALL_UFS = UFS_TIER_1 + UFS_TIER_2 + UFS_TIER_3

# Catálogo Nacional de Marcas
BRANDS_VOLUME = [
    "CHEVROLET",
    "VOLKSWAGEN",
    "FIAT",
    "HYUNDAI",
    "TOYOTA",
    "HONDA",
    "JEEP",
    "RENAULT",
    "NISSAN",
    "FORD",
    "PEUGEOT",
    "CITROEN",
    "MITSUBISHI",
    "CHERY",
]

BRANDS_LUXURY = [
    "BMW",
    "MERCEDES-BENZ",
    "AUDI",
    "VOLVO",
    "PORSCHE",
    "LAND ROVER",
    "LEXUS",
    "RAM",
    "MINI",
    "JAGUAR",
]

BRANDS_EV = [
    "BYD",
    "GWM",
]

BRANDS_NICHE_AND_EXOTIC = [
    "KIA",
    "SUBARU",
    "SUZUKI",
    "DODGE",
    "CHRYSLER",
    "TROLLER",
    "JAC",
    "SMART",
    "IVECO",
    "FERRARI",
    "MASERATI",
    "LAMBORGHINI",
    "ASTON MARTIN",
    "MCLAREN",
    "ROLLS-ROYCE",
    "BENTLEY",
]

# Lista consolidada de absolutamente todas as marcas
ALL_BRANDS = BRANDS_VOLUME + BRANDS_LUXURY + BRANDS_EV + BRANDS_NICHE_AND_EXOTIC
TARGET_BRANDS = ALL_BRANDS

# Configuração do Serviço Daemon Horário
DAEMON_INTERVAL_SECONDS = 3600  # 1 hora
DAEMON_STATUS_PATH = DATA_DIR / "daemon_status.json"
DAEMON_LOG_PATH = DATA_DIR / "daemon.log"
