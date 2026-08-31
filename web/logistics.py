import math
from typing import Dict, Any, Tuple, Optional

# Coordenadas geográficas das principais capitais e cidades brasileiras (Lat, Lon)
CITY_COORDINATES: Dict[str, Tuple[float, float]] = {
    # São Paulo
    "SÃO PAULO": (-23.5505, -46.6333),
    "CAMPINAS": (-22.9099, -47.0626),
    "SANTOS": (-23.9608, -46.3336),
    "SÃO JOSÉ DOS CAMPOS": (-23.1896, -45.8841),
    "RIBEIRÃO PRETO": (-21.1767, -47.8208),
    "SOROCABA": (-23.5015, -47.4526),
    "SANTO ANDRÉ": (-23.6638, -46.5383),
    "SÃO BERNARDO DO CAMPO": (-23.6914, -46.5646),
    "LOUVEIRA": (-23.0861, -46.9511),
    "JUNDIAÍ": (-23.1857, -46.8978),
    "BARUERI": (-23.5108, -46.8761),
    "OSASCO": (-23.5329, -46.7916),
    "PIRACICABA": (-22.7253, -47.6492),
    "BAURU": (-22.3147, -49.0606),
    "SÃO JOSÉ DO RIO PRETO": (-20.8113, -49.3758),

    # Paraná
    "CURITIBA": (-25.4284, -49.2733),
    "LONDRINA": (-23.3045, -51.1696),
    "MARINGÁ": (-23.4209, -51.9331),
    "CASCAVEL": (-24.9578, -53.4595),
    "PONTA GROSSA": (-25.0994, -50.1583),
    "FOZ DO IGUAÇU": (-25.5163, -54.5854),
    "SÃO JOSÉ DOS PINHAIS": (-25.5347, -49.2064),

    # Rio de Janeiro
    "RIO DE JANEIRO": (-22.9068, -43.1729),
    "NITERÓI": (-22.8832, -43.1034),
    "DUQUE DE CAXIAS": (-22.7858, -43.3117),
    "PETRÓPOLIS": (-22.5050, -43.1789),
    "VOLTA REDONDA": (-22.5232, -44.1041),
    "CAMPOS DOS GOYTACAZES": (-21.7545, -41.3242),

    # Minas Gerais
    "BELO HORIZONTE": (-19.9167, -43.9345),
    "UBERLÂNDIA": (-18.9186, -48.2772),
    "JUIZ DE FORA": (-21.7642, -43.3496),
    "CONTAGEM": (-19.9321, -44.0539),
    "BETIM": (-19.9678, -44.1983),
    "MONTES CLAROS": (-16.7282, -43.8617),
    "UBERABA": (-19.7472, -47.9392),

    # Santa Catarina
    "FLORIANÓPOLIS": (-27.5954, -48.5480),
    "JOINVILLE": (-26.3045, -48.8487),
    "BLUMENAU": (-26.9194, -49.0661),
    "ITAJAÍ": (-26.9078, -48.6619),
    "CRICIÚMA": (-28.6773, -49.3704),
    "CHAPECÓ": (-27.1004, -52.6152),

    # Rio Grande do Sul
    "PORTO ALEGRE": (-30.0346, -51.2177),
    "CAXIAS DO SUL": (-29.1681, -51.1794),
    "PELOTAS": (-31.7654, -52.3376),
    "CANOAS": (-29.9178, -51.1836),
    "SANTA MARIA": (-29.6842, -53.8069),

    # Centro-Oeste / Nordeste / Norte
    "BRASÍLIA": (-15.7975, -47.8919),
    "GOIÂNIA": (-16.6869, -49.2648),
    "SALVADOR": (-12.9777, -38.5016),
    "FORTALEZA": (-3.7172, -38.5433),
    "RECIFE": (-8.0476, -34.8770),
    "VITÓRIA": (-20.3155, -40.3128),
    "CUIABÁ": (-15.6014, -56.0979),
    "CAMPO GRANDE": (-20.4697, -54.6201),
    "MANAUS": (-3.1190, -60.0217),
    "BELÉM": (-1.4558, -48.4902),
}

# Centróides médios por UF caso a cidade não esteja mapeada
STATE_CENTROIDS: Dict[str, Tuple[float, float]] = {
    "SP": (-23.5505, -46.6333),
    "RJ": (-22.9068, -43.1729),
    "MG": (-19.9167, -43.9345),
    "PR": (-25.4284, -49.2733),
    "SC": (-27.5954, -48.5480),
    "RS": (-30.0346, -51.2177),
    "BA": (-12.9777, -38.5016),
    "GO": (-16.6869, -49.2648),
    "DF": (-15.7975, -47.8919),
    "ES": (-20.3155, -40.3128),
    "PE": (-8.0476, -34.8770),
    "CE": (-3.7172, -38.5433),
    "MT": (-15.6014, -56.0979),
    "MS": (-20.4697, -54.6201),
}


def get_coordinates(city: Optional[str], uf: Optional[str]) -> Tuple[float, float]:
    """Recupera a latitude e longitude aproximada de uma cidade/estado brasileira"""
    if city:
        city_clean = city.strip().upper()
        if city_clean in CITY_COORDINATES:
            return CITY_COORDINATES[city_clean]
        for c_name, coords in CITY_COORDINATES.items():
            if c_name in city_clean or city_clean in c_name:
                return coords

    if uf:
        uf_clean = uf.strip().upper()
        if uf_clean in STATE_CENTROIDS:
            return STATE_CENTROIDS[uf_clean]

    # Default: São Paulo
    return (-23.5505, -46.6333)


def haversine_distance_km(coord1: Tuple[float, float], coord2: Tuple[float, float]) -> float:
    """Calcula a distância geodésica entre duas coordenadas com fator de sinuosidade rodoviária"""
    lat1, lon1 = coord1
    lat2, lon2 = coord2

    R = 6371.0  # Raio da Terra em km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    dist_geodesica = R * c

    # Fator de tortuosidade rodoviária no Brasil (~1.18x sobre a linha reta)
    dist_rodoviaria = dist_geodesica * 1.18
    return round(dist_rodoviaria, 1)


def calculate_trip_cost(
    user_city: str = "São Paulo",
    user_uf: str = "SP",
    car_city: Optional[str] = None,
    car_uf: Optional[str] = None,
    car_price: float = 0.0,
    market_price: float = 0.0,
    fuel_type: str = "GASOLINA",
    fuel_price: float = 6.10,
    km_per_liter: float = 12.0,
    toll_per_100km: float = 16.0,
    extra_costs: float = 150.0,
) -> Dict[str, Any]:
    """
    Calcula os custos completos de viagem para buscar um veículo anunciado:
    - Distância de ida e volta
    - Consumo em litros e custo do combustível
    - Estimativa de pedágios de rodovia
    - Despesas de deslocamento e alimentação
    - Veredito financeiro: Vale a pena viajar para buscar?
    """
    user_coords = get_coordinates(user_city, user_uf)
    car_coords = get_coordinates(car_city, car_uf)

    dist_one_way = haversine_distance_km(user_coords, car_coords)

    # Se a distância for ínfima (mesma cidade)
    if dist_one_way < 25.0:
        return {
            "distancia_km": round(dist_one_way, 0),
            "mesma_cidade": True,
            "custo_combustivel": 35.0,
            "custo_pedagios": 0.0,
            "custo_extras": 0.0,
            "custo_total_viagem": 35.0,
            "preco_total_efetivo": round(car_price + 35.0, 0),
            "economia_liquida": round(market_price - car_price - 35.0, 0) if market_price > 0 else 0.0,
            "veredito": {
                "tipo": "LOCAL",
                "titulo": "VEÍCULO NA SUA REGIÃO",
                "descricao": "Sem necessidade de custos de viagem interestadual.",
                "cor": "emerald",
            },
        }

    dist_round_trip = dist_one_way * 2

    # Consumo e combustível
    litros_necessarios = dist_round_trip / max(km_per_liter, 1.0)
    custo_combustivel = litros_necessarios * fuel_price

    # Pedágios
    custo_pedagios = (dist_round_trip / 100.0) * toll_per_100km

    # Custo total de viagem
    custo_total_viagem = round(custo_combustivel + custo_pedagios + extra_costs, 0)
    preco_total_efetivo = round(car_price + custo_total_viagem, 0)

    # Economia líquida
    economia_bruta = max(0.0, market_price - car_price) if market_price > 0 else 0.0
    economia_liquida = round(economia_bruta - custo_total_viagem, 0)

    # Veredito
    if economia_liquida >= 3000.0:
        veredito = {
            "tipo": "VALE_A_PENA",
            "titulo": "VALE MUITO A PENA BUSCAR!",
            "descricao": f"Economia líquida de R$ {economia_liquida:,.0f} mesmo após pagar toda a viagem.",
            "cor": "emerald",
        }
    elif economia_liquida > 0.0:
        veredito = {
            "tipo": "EMPATE",
            "titulo": "VALOR COMPENSATÓRIO",
            "descricao": f"Economia líquida de R$ {economia_liquida:,.0f} cobre os gastos de viagem.",
            "cor": "blue",
        }
    else:
        veredito = {
            "tipo": "NAO_COMPENSA",
            "titulo": "NÃO COMPENSA A DISTÂNCIA",
            "descricao": f"A viagem de R$ {custo_total_viagem:,.0f} anula a vantagem de preço deste anúncio.",
            "cor": "amber",
        }

    return {
        "distancia_km": round(dist_one_way, 0),
        "distancia_ida_volta_km": round(dist_round_trip, 0),
        "mesma_cidade": False,
        "litros_combustivel": round(litros_necessarios, 1),
        "custo_combustivel": round(custo_combustivel, 0),
        "custo_pedagios": round(custo_pedagios, 0),
        "custo_extras": round(extra_costs, 0),
        "custo_total_viagem": custo_total_viagem,
        "preco_total_efetivo": preco_total_efetivo,
        "economia_liquida": economia_liquida,
        "veredito": veredito,
    }
