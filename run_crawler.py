import asyncio
import argparse
import sys
from pathlib import Path

# Adicionar pasta raiz ao path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from crawler.scraper import WebmotorsScraper
from crawler.orchestrator import NationalCrawlerOrchestrator
from database.db_manager import DatabaseManager


async def main():
    parser = argparse.ArgumentParser(description="WebMotors Analytics - Crawler Nacional em Escala")
    
    # Modos de execução
    parser.add_argument("--national", action="store_true", help="Ativar orquestrador de coleta nacional em lote")
    parser.add_argument("--tier", type=str, choices=["1", "2", "3", "all"], default="1", help="Tier de estados para coleta nacional (1: SP/RJ/MG/PR/SC/RS, 2: Centro-Oeste/Nordeste, 3: Norte/demais, all: 27 UFs)")
    parser.add_argument("--brands-cat", type=str, choices=["volume", "luxury", "ev", "all", "none"], default="volume", help="Categoria de marcas (volume, luxury, ev, all ou none para geral)")
    parser.add_argument("--pages-per-shard", type=int, default=3, help="Qtd de páginas por partição UF/Marca (padrão: 3)")
    parser.add_argument("--no-resume", dest="resume", action="store_false", default=True, help="Ignorar checkpoint e reiniciar do zero")
    parser.add_argument("--clear-checkpoint", action="store_true", help="Limpar arquivo de checkpoint existente")

    # Coleta pontual (caso não use --national)
    parser.add_argument("--uf", type=str, default=None, help="Estado (UF) para coleta pontual (ex: sp, rj, pr)")
    parser.add_argument("--marca", type=str, default=None, help="Marca específica para coleta pontual (ex: toyota, jeep)")
    parser.add_argument("--paginas", type=int, default=3, help="Número de páginas para coleta pontual (padrão: 3)")
    parser.add_argument("--mode", type=str, choices=["api", "browser"], default="api", help="Modo de coleta: 'api' (ultrarrápido, padrão) ou 'browser' (Playwright)")
    parser.add_argument("--headless", action="store_true", default=True, help="Executar em modo headless no browser")
    parser.add_argument("--no-headless", dest="headless", action="store_false", help="Exibir janela do navegador")

    args = parser.parse_args()
    db = DatabaseManager()

    if args.clear_checkpoint:
        orchestrator = NationalCrawlerOrchestrator(db)
        orchestrator.checkpoint_mgr.clear()
        print("🗑️ Checkpoint anterior limpo com sucesso.")

    if args.national or (args.uf is None and args.marca is None):
        print(f"==================================================")
        print(f"🌍 WebMotors Analytics - Expansão Nacional em Escala")
        print(f"📍 Tier de UFs: {args.tier.upper()} | Categoria de Marcas: {args.brands_cat.upper()}")
        print(f"📑 Páginas por Shard: {args.pages_per_shard} | Retomada ativa: {args.resume}")
        print(f"==================================================")

        orchestrator = NationalCrawlerOrchestrator(db)
        shards = orchestrator.build_shards(tier=args.tier, brands_category=args.brands_cat)
        
        resultado = await orchestrator.run(
            shards=shards,
            pages_per_shard=args.pages_per_shard,
            resume=args.resume,
        )

        print("\n==================================================")
        print(f"🎉 Varredura Nacional Concluída / Pausada!")
        print(f"📊 Shards Concluídos: {resultado['shards_concluidos']} / {resultado['total_shards']}")
        print(f"🚗 Total Coletados na Sessão: {resultado['total_coletados']}")
        print(f"🆕 Novos Veículos no DuckDB: {resultado['novos_inseridos']}")
        print(f"🔄 Atualizados: {resultado['atualizados']}")

    else:
        # Coleta pontual
        uf = (args.uf or "sp").lower()
        marca = args.marca.lower() if args.marca else None
        print(f"==================================================")
        print(f"🚗 WebMotors Crawler - Coleta Pontual")
        print(f"📍 UF: {uf.upper()} | Marca: {marca.upper() if marca else 'TODAS'} | Páginas: {args.paginas} | Modo: {args.mode.upper()}")
        print(f"==================================================")

        scraper = WebmotorsScraper(db)
        resultado = await scraper.run_collector(
            uf=uf,
            marca=marca,
            max_paginas=args.paginas,
            mode=args.mode,
            headless=args.headless,
        )

        print("\n==================================================")
        print(f"✅ Coleta Concluída!")
        print(f"📊 Total Coletados: {resultado['total_coletados']}")
        print(f"🆕 Novos no DuckDB: {resultado['novos_inseridos']}")
        print(f"🔄 Atualizados: {resultado['atualizados']}")

    metricas = db.get_metricas_gerais()
    print(f"\n📈 Estado Consolidado da Base no DuckDB:")
    print(f"   • Total de Veículos: {metricas['total_veiculos']}")
    print(f"   • Marcas Distintas: {metricas['total_marcas']}")
    print(f"   • Modelos Distintos: {metricas['total_modelos']}")
    print(f"   • Preço Médio: R$ {metricas['preco_medio']:,.2f}")
    print(f"   • KM Média: {metricas['km_media']:,.0f} km")
    print("==================================================")


if __name__ == "__main__":
    asyncio.run(main())
