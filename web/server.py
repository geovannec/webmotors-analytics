import os
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, Query, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import duckdb

from database.db_manager import DatabaseManager
from web.logistics import calculate_trip_cost, CITY_COORDINATES
from web.tco import calculate_tco

# Adicionar pasta raiz ao path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from database.db_manager import DatabaseManager
from config.settings import DB_PATH

app = FastAPI(title="WebMotors Reconstructed + Embedded Analytics API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db = DatabaseManager(DB_PATH)
STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)


@app.get("/api/summary")
def get_summary():
    """Retorna métricas globais de mercado para o header da WebMotors"""
    with db.get_connection(read_only=True) as conn:
        res = conn.execute(
            """
            SELECT 
                count(*) as total_veiculos,
                count(distinct marca) as total_marcas,
                count(distinct modelo) as total_modelos,
                round(avg(preco), 0) as preco_medio
            FROM anuncios
            WHERE status = 'ATIVO'
            """
        ).fetchone()

        # Calcular pechinchas (veículos com preço >= 10% abaixo da média do modelo+ano)
        pechinchas = conn.execute(
            """
            WITH medias AS (
                SELECT marca, modelo, ano_modelo, avg(preco) as media_mercado, count(*) as qtd
                FROM anuncios
                WHERE status = 'ATIVO'
                GROUP BY marca, modelo, ano_modelo
                HAVING count(*) >= 2
            )
            SELECT count(*)
            FROM anuncios a
            JOIN medias m ON a.marca = m.marca AND a.modelo = m.modelo AND a.ano_modelo = m.ano_modelo
            WHERE a.status = 'ATIVO' AND ((m.media_mercado - a.preco) / m.media_mercado) >= 0.10
            """
        ).fetchone()

    return {
        "total_veiculos": int(res[0] or 0),
        "total_marcas": int(res[1] or 0),
        "total_modelos": int(res[2] or 0),
        "preco_medio": float(res[3] or 0.0),
        "total_pechinchas": int(pechinchas[0] if pechinchas else 0),
    }


@app.get("/api/filters/facets")
def get_facets():
    """Retorna opções e contadores para a barra lateral de filtros da WebMotors"""
    with db.get_connection(read_only=True) as conn:
        # Marcas com contagem
        marcas = conn.execute(
            """
            SELECT marca, count(*) as total
            FROM anuncios
            WHERE status = 'ATIVO'
            GROUP BY marca
            ORDER BY total DESC, marca ASC
            """
        ).fetchall()

        # UFs com contagem
        ufs = conn.execute(
            """
            SELECT upper(estado) as uf, count(*) as total
            FROM anuncios
            WHERE status = 'ATIVO' AND estado IS NOT NULL AND trim(estado) != ''
            GROUP BY upper(estado)
            ORDER BY total DESC
            """
        ).fetchall()

        # Limites numéricos
        limites = conn.execute(
            """
            SELECT 
                min(ano_modelo) as ano_min,
                max(ano_modelo) as ano_max,
                min(preco) as preco_min,
                max(preco) as preco_max,
                max(quilometragem) as km_max
            FROM anuncios
            WHERE status = 'ATIVO'
            """
        ).fetchone()

    return {
        "marcas": [{"marca": r[0], "total": r[1]} for r in marcas],
        "ufs": [{"uf": r[0], "total": r[1]} for r in ufs],
        "ano_min": int(limites[0] or 2010),
        "ano_max": int(limites[1] or 2026),
        "preco_min": float(limites[2] or 20000.0),
        "preco_max": float(limites[3] or 800000.0),
        "km_max": float(limites[4] or 200000.0),
    }


@app.get("/api/cities")
def get_cities():
    """Retorna a lista de cidades suportadas para cálculo de viagem e logística."""
    cities = sorted(list(CITY_COORDINATES.keys()))
    return {"cities": cities}


@app.get("/api/filters/models")
def get_models(marca: str):
    """Retorna a lista de modelos e respectivas contagens para uma marca selecionada."""
    if not marca:
        return {"models": []}
    with db.get_connection(read_only=True) as conn:
        rows = conn.execute(
            """
            SELECT modelo, count(*) as total
            FROM anuncios
            WHERE status = 'ATIVO' AND upper(marca) = upper(?)
            GROUP BY modelo
            ORDER BY total DESC, modelo ASC
            """,
            [marca.strip()],
        ).fetchall()
    return {"marca": marca.upper(), "models": [{"modelo": r[0], "total": r[1]} for r in rows]}


@app.get("/api/cars")
def get_cars(
    q: Optional[str] = None,
    uf: Optional[str] = None,
    marca: Optional[str] = None,
    modelo: Optional[str] = None,
    ano_min: Optional[int] = None,
    ano_max: Optional[int] = None,
    preco_min: Optional[float] = None,
    preco_max: Optional[float] = None,
    km_max: Optional[float] = None,
    tipo_vendedor: Optional[str] = None,
    deal_type: Optional[str] = None,
    sort: str = "deal_desc",
    page: int = Query(1, ge=1),
    limit: int = Query(18, ge=1, le=100),
    user_city: str = "São Paulo",
    user_uf: str = "SP",
    fuel_type: str = "GASOLINA",
    fuel_price: float = 6.10,
    km_per_liter: float = 12.0,
    toll_per_100km: float = 16.0,
    extra_costs: float = 150.0,
):
    """
    Busca paginada de veículos com inteligência analítica, logística de viagem e TCO embutidos:
    - Deal Rating: Oportunidade, Preço Justo, Acima da Média
    - Custo de viagem de busca (ida/volta, combustível, pedágios)
    - Custo total de posse (Seguro, IPVA, manutenção, custo mensal)
    """
    p = int(getattr(page, "default", page) or 1)
    l = int(getattr(limit, "default", limit) or 18)
    offset = (p - 1) * l
    where_clauses = ["a.status = 'ATIVO'"]
    params = []

    if q:
        q_term = f"%{q.strip().lower()}%"
        where_clauses.append("(lower(a.marca) LIKE ? OR lower(a.modelo) LIKE ? OR lower(a.versao) LIKE ? OR lower(a.cidade) LIKE ?)")
        params.extend([q_term, q_term, q_term, q_term])

    if uf:
        where_clauses.append("upper(a.estado) = ?")
        params.append(uf.strip().upper())

    if marca:
        where_clauses.append("upper(a.marca) = ?")
        params.append(marca.strip().upper())

    if modelo:
        where_clauses.append("upper(a.modelo) = ?")
        params.append(modelo.strip().upper())

    if ano_min:
        where_clauses.append("a.ano_modelo >= ?")
        params.append(ano_min)

    if ano_max:
        where_clauses.append("a.ano_modelo <= ?")
        params.append(ano_max)

    if preco_min:
        where_clauses.append("a.preco >= ?")
        params.append(preco_min)

    if preco_max:
        where_clauses.append("a.preco <= ?")
        params.append(preco_max)

    if km_max:
        where_clauses.append("a.quilometragem <= ?")
        params.append(km_max)

    if tipo_vendedor:
        where_clauses.append("upper(a.tipo_vendedor) = ?")
        params.append(tipo_vendedor.strip().upper())

    where_sql = " AND ".join(where_clauses)

    # Ordenação
    sort_dict = {
        "deal_desc": "desconto_pct DESC",
        "price_asc": "a.preco ASC",
        "price_desc": "a.preco DESC",
        "km_asc": "a.quilometragem ASC",
        "year_desc": "a.ano_modelo DESC",
        "recent": "a.data_primeira_captura DESC",
    }
    order_sql = sort_dict.get(sort, "desconto_pct DESC")

    query = f"""
    WITH medias AS (
        SELECT marca, modelo, ano_modelo, avg(preco) as preco_medio_mercado
        FROM anuncios
        WHERE status = 'ATIVO'
        GROUP BY marca, modelo, ano_modelo
    ),
    historico_recente AS (
        SELECT id_anuncio, max(preco_anterior) as preco_anterior, max(data_alteracao) as data_alteracao
        FROM historico_precos
        GROUP BY id_anuncio
    )
    SELECT 
        a.id_anuncio,
        a.marca,
        a.modelo,
        a.versao,
        a.ano_fabricacao,
        a.ano_modelo,
        a.quilometragem,
        a.preco,
        a.cidade,
        a.estado,
        a.tipo_vendedor,
        a.url_anuncio,
        a.foto_url,
        a.data_primeira_captura,
        coalesce(m.preco_medio_mercado, a.preco) as preco_medio_mercado,
        CASE 
            WHEN m.preco_medio_mercado IS NOT NULL AND m.preco_medio_mercado > 0 
            THEN round(((m.preco_medio_mercado - a.preco) / m.preco_medio_mercado) * 100.0, 1)
            ELSE 0.0 
        END as desconto_pct,
        h.preco_anterior
    FROM anuncios a
    LEFT JOIN medias m ON a.marca = m.marca AND a.modelo = m.modelo AND a.ano_modelo = m.ano_modelo
    LEFT JOIN historico_recente h ON a.id_anuncio = h.id_anuncio
    WHERE {where_sql}
    """

    # Filtrar por deal_type se solicitado
    if deal_type == "pechincha":
        query = f"SELECT * FROM ({query}) WHERE desconto_pct >= 10.0"
    elif deal_type == "justo":
        query = f"SELECT * FROM ({query}) WHERE desconto_pct >= -5.0 AND desconto_pct < 10.0"
    elif deal_type == "acima":
        query = f"SELECT * FROM ({query}) WHERE desconto_pct < -5.0"

    count_query = f"SELECT count(*) FROM ({query})"
    paginated_query = f"{query} ORDER BY {order_sql} LIMIT {l} OFFSET {offset}"

    with db.get_connection(read_only=True) as conn:
        total = conn.execute(count_query, params).fetchone()[0]
        rows = conn.execute(paginated_query, params).fetchall()

    items = []
    for r in rows:
        preco = float(r[7] or 0.0)
        preco_mercado = float(r[14] or preco)
        desconto_pct = float(r[15] or 0.0)
        preco_ant = r[16]
        car_cidade = r[8] or ""
        car_estado = (r[9] or "").upper()
        car_marca = r[1]
        car_ano_modelo = int(r[5] or 2020)
        car_km = float(r[6] or 0.0)

        # Categorização de negócio
        if desconto_pct >= 10.0:
            deal_badge = {
                "label": "OPORTUNIDADE",
                "sub": f"{desconto_pct:.1f}% abaixo da média",
                "color": "emerald",
                "tag": "excelente",
            }
        elif desconto_pct >= 3.0:
            deal_badge = {
                "label": "BOM NEGÓCIO",
                "sub": f"{desconto_pct:.1f}% abaixo da média",
                "color": "blue",
                "tag": "bom",
            }
        elif desconto_pct >= -5.0:
            deal_badge = {
                "label": "PREÇO JUSTO",
                "sub": "Na média de mercado",
                "color": "slate",
                "tag": "justo",
            }
        else:
            deal_badge = {
                "label": "ACIMA DA MÉDIA",
                "sub": f"{abs(desconto_pct):.1f}% acima da média",
                "color": "amber",
                "tag": "acima",
            }

        # Detecção de redução recente de preço
        price_drop = None
        if preco_ant and float(preco_ant) > preco:
            diff = float(preco_ant) - preco
            price_drop = {
                "preco_anterior": float(preco_ant),
                "economia": diff,
                "texto": f"Baixou R$ {diff:,.0f}".replace(",", "."),
            }

        # Simulação de parcela (CDC padrão 20% entrada + 48x tx 1.49%)
        entrada = preco * 0.20
        financiado = preco - entrada
        parcela = (financiado * 0.031) if preco > 0 else 0.0

        # Cálculo Logístico de Viagem para Buscar o Carro
        viagem = calculate_trip_cost(
            user_city=user_city,
            user_uf=user_uf,
            car_city=car_cidade,
            car_uf=car_estado,
            car_price=preco,
            market_price=preco_mercado,
            fuel_type=fuel_type,
            fuel_price=fuel_price,
            km_per_liter=km_per_liter,
            toll_per_100km=toll_per_100km,
            extra_costs=extra_costs,
        )

        # Cálculo do Custo de Posse (TCO - Seguro, IPVA, Manutenções, Mensalidade)
        tco = calculate_tco(
            car_price=preco,
            ano_modelo=car_ano_modelo,
            quilometragem=int(car_km),
            marca=car_marca,
            estado=car_estado or user_uf,
            fuel_price=fuel_price,
            km_per_liter=km_per_liter,
        )

        items.append({
            "id_anuncio": r[0],
            "marca": car_marca,
            "modelo": r[2],
            "versao": r[3] or "",
            "ano_fabricacao": r[4],
            "ano_modelo": car_ano_modelo,
            "quilometragem": car_km,
            "preco": preco,
            "cidade": car_cidade,
            "estado": car_estado,
            "tipo_vendedor": r[10] or "Loja",
            "url_anuncio": r[11] or "",
            "foto_url": r[12] or "",
            "preco_mercado": preco_mercado,
            "desconto_pct": desconto_pct,
            "deal_badge": deal_badge,
            "price_drop": price_drop,
            "parcela_estimada": round(parcela, 0),
            "viagem": viagem,
            "tco": tco,
        })

    total_pages = (total + l - 1) // l if total > 0 else 1

    return {
        "items": items,
        "total": total,
        "page": p,
        "total_pages": total_pages,
        "limit": l,
    }


@app.get("/api/cars/{id_anuncio}")
def get_car_detail(
    id_anuncio: str,
    user_city: str = "São Paulo",
    user_uf: str = "SP",
    fuel_type: str = "GASOLINA",
    fuel_price: float = 6.10,
    km_per_liter: float = 12.0,
    toll_per_100km: float = 16.0,
    extra_costs: float = 150.0,
):
    """
    Retorna o perfil completo de um veículo específico mais todo o seu
    Raio-X de Inteligência Analítica (Curva de Depreciação, Arbitragem Interestadual, Histórico, Viagem e TCO).
    """
    with db.get_connection(read_only=True) as conn:
        car = conn.execute(
            """
            SELECT id_anuncio, marca, modelo, versao, ano_fabricacao, ano_modelo,
                   quilometragem, preco, cidade, estado, tipo_vendedor, url_anuncio,
                   foto_url, data_primeira_captura, data_ultima_captura
            FROM anuncios
            WHERE id_anuncio = ?
            """,
            [id_anuncio],
        ).fetchone()

        if not car:
            raise HTTPException(status_code=404, detail="Veículo não encontrado")

        marca, modelo, ano_modelo, preco_atual = car[1], car[2], car[5], float(car[7])

        # 1. Curva de Depreciação deste modelo
        curva_rows = conn.execute(
            """
            SELECT ano_modelo, round(avg(preco), 0) as preco_medio, count(*) as total_anuncios
            FROM anuncios
            WHERE marca = ? AND modelo = ? AND status = 'ATIVO'
            GROUP BY ano_modelo
            ORDER BY ano_modelo ASC
            """,
            [marca, modelo],
        ).fetchall()

        curva_depreciacao = [
            {"ano": int(r[0]), "preco_medio": float(r[1]), "total": int(r[2])}
            for r in curva_rows
        ]

        # 2. Arbitragem Interestadual para este mesmo modelo e ano
        arb_rows = conn.execute(
            """
            SELECT upper(estado) as uf, round(avg(preco), 0) as preco_medio, count(*) as total
            FROM anuncios
            WHERE marca = ? AND modelo = ? AND ano_modelo = ? AND status = 'ATIVO'
            GROUP BY upper(estado)
            ORDER BY preco_medio ASC
            """,
            [marca, modelo, ano_modelo],
        ).fetchall()

        arbitragem = [
            {
                "uf": r[0],
                "preco_medio": float(r[1]),
                "total": int(r[2]),
                "diferenca_vs_este": float(r[1]) - preco_atual,
            }
            for r in arb_rows
        ]

        # 3. Histórico de alterações de preço deste anúncio
        hist_rows = conn.execute(
            """
            SELECT data_alteracao, preco_anterior, preco_novo
            FROM historico_precos
            WHERE id_anuncio = ?
            ORDER BY data_alteracao ASC
            """,
            [id_anuncio],
        ).fetchall()

        historico = [
            {
                "data": str(r[0])[:16],
                "preco_anterior": float(r[1]),
                "preco_novo": float(r[2]),
                "diferenca": float(r[2]) - float(r[1]),
            }
            for r in hist_rows
        ]

        # 4. Média e Spread de Mercado do modelo + ano
        estatisticas = conn.execute(
            """
            SELECT round(avg(preco), 0), round(min(preco), 0), round(max(preco), 0), count(*)
            FROM anuncios
            WHERE marca = ? AND modelo = ? AND ano_modelo = ? AND status = 'ATIVO'
            """,
            [marca, modelo, ano_modelo],
        ).fetchone()

    media_mercado = float(estatisticas[0] or preco_atual)
    menor_mercado = float(estatisticas[1] or preco_atual)
    maior_mercado = float(estatisticas[2] or preco_atual)
    qtd_amostra = int(estatisticas[3] or 1)

    spread_pct = round(((media_mercado - preco_atual) / media_mercado) * 100.0, 1) if media_mercado > 0 else 0.0

    # Cálculo de Viagem e TCO para a página de detalhes
    viagem = calculate_trip_cost(
        user_city=user_city,
        user_uf=user_uf,
        car_city=car[8] or "",
        car_uf=(car[9] or "").upper(),
        car_price=preco_atual,
        market_price=media_mercado,
        fuel_type=fuel_type,
        fuel_price=fuel_price,
        km_per_liter=km_per_liter,
        toll_per_100km=toll_per_100km,
        extra_costs=extra_costs,
    )

    tco = calculate_tco(
        car_price=preco_atual,
        ano_modelo=ano_modelo,
        quilometragem=int(car[6] or 0),
        marca=marca,
        estado=(car[9] or user_uf).upper(),
        fuel_price=fuel_price,
        km_per_liter=km_per_liter,
    )

    return {
        "car": {
            "id_anuncio": car[0],
            "marca": car[1],
            "modelo": car[2],
            "versao": car[3] or "",
            "ano_fabricacao": car[4],
            "ano_modelo": car[5],
            "quilometragem": float(car[6] or 0.0),
            "preco": preco_atual,
            "cidade": car[8] or "",
            "estado": (car[9] or "").upper(),
            "tipo_vendedor": car[10] or "Loja",
            "url_anuncio": car[11] or "",
            "foto_url": car[12] or "",
            "data_primeira_captura": str(car[13])[:10],
        },
        "analytics": {
            "media_mercado": media_mercado,
            "menor_mercado": menor_mercado,
            "maior_mercado": maior_mercado,
            "qtd_amostra": qtd_amostra,
            "spread_pct": spread_pct,
            "curva_depreciacao": curva_depreciacao,
            "arbitragem_regional": arbitragem,
            "historico_precos": historico,
            "viagem": viagem,
            "tco": tco,
        },
    }


# Servir frontend estático na raiz
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def serve_index():
    return FileResponse(STATIC_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("web.server:app", host="0.0.0.0", port=8000, reload=True)
