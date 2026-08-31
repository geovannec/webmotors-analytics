from typing import Dict, Any, Optional

# Alíquotas de IPVA por Estado (veículos de passeio)
IPVA_RATES = {
    "SP": 0.04,
    "RJ": 0.04,
    "MG": 0.04,
    "DF": 0.035,
    "PR": 0.035,
    "SC": 0.02,  # Santa Catarina tem alíquota reduzida de 2%
    "RS": 0.03,
    "BA": 0.03,
    "GO": 0.035,
    "ES": 0.02,
}

# Categorias de Seguro por Marca (taxa percentual anual média sobre o valor do veículo)
LUXURY_BRANDS = {"BMW", "MERCEDES-BENZ", "AUDI", "PORSCHE", "LAND ROVER", "VOLVO", "JAGUAR", "LEXUS"}
SUV_PICKUP_BRANDS = {"JEEP", "RAM", "MITSUBISHI", "TOYOTA"}
EV_HYBRID_BRANDS = {"BYD", "GWM"}


def calculate_tco(
    car_price: float,
    ano_modelo: int,
    quilometragem: int,
    marca: str = "",
    estado: str = "SP",
    fuel_price: float = 6.10,
    km_per_liter: float = 12.0,
    km_month_avg: float = 1000.0,
) -> Dict[str, Any]:
    """
    Calcula o Custo Total de Posse (TCO) para manter o veículo no Brasil:
    - IPVA anual estimado conforme UF
    - Seguro anual médio estimado pelo perfil da marca/veículo
    - Manutenção preventiva anual estimada pela idade e km
    - Gasto mensal com combustível (base 1.000 km/mês)
    - Custo total consolidado: Mensal e Anual
    """
    if car_price <= 0:
        car_price = 50000.0

    marca_upper = (marca or "").strip().upper()
    uf_upper = (estado or "SP").strip().upper()

    # 1. IPVA Anual
    # Isenção por idade: SP, PR e RJ isentam carros com 20 anos ou mais
    idade_veiculo = max(0, 2026 - ano_modelo)
    if idade_veiculo >= 20:
        ipva_anual = 0.0
        ipva_isento = True
    else:
        taxa_ipva = IPVA_RATES.get(uf_upper, 0.035)
        ipva_anual = round(car_price * taxa_ipva, 0)
        ipva_isento = False

    # 2. Seguro Anual Médio Estimado
    if any(b in marca_upper for b in LUXURY_BRANDS):
        taxa_seguro = 0.062  # 6.2% para marcas premium
        categoria_seguro = "Premium / Luxo"
    elif any(b in marca_upper for b in SUV_PICKUP_BRANDS):
        taxa_seguro = 0.052  # 5.2% para SUVs e picapes com índice de furto maior
        categoria_seguro = "SUV / Picape"
    elif any(b in marca_upper for b in EV_HYBRID_BRANDS):
        taxa_seguro = 0.045  # 4.5% para híbridos/elétricos
        categoria_seguro = "Elétrico / Híbrido"
    else:
        taxa_seguro = 0.042  # 4.2% para modelos convencionais/populares
        categoria_seguro = "Padrão de Mercado"

    # Carros mais antigos têm taxa ligeiramente menor ou valor piso
    seguro_anual = max(1800.0, round(car_price * taxa_seguro, 0))

    # 3. Manutenção Preventiva Anual (Revisões, pneus, óleo, suspensão, freios)
    if idade_veiculo <= 3:
        manut_base = 1800.0  # Revisões de garantia básicas
    elif idade_veiculo <= 7:
        manut_base = 3200.0  # Troca de pneus, pastilhas, correias
    else:
        manut_base = 4800.0  # Manutenções corretivas naturais (suspensão, amortecedor, fluidos)

    # Fator de quilometragem
    if quilometragem > 120000:
        manut_base *= 1.25
    elif quilometragem < 30000:
        manut_base *= 0.85

    # Fator de luxo
    if any(b in marca_upper for b in LUXURY_BRANDS):
        manut_base *= 1.75

    manutencao_anual = round(manut_base, 0)

    # 4. Combustível Mensal Estimado
    litros_mes = km_month_avg / max(km_per_liter, 1.0)
    combustivel_mensal = round(litros_mes * fuel_price, 0)
    combustivel_anual = round(combustivel_mensal * 12, 0)

    # 5. Consolidação Geral
    custo_fixo_anual = ipva_anual + seguro_anual + manutencao_anual
    custo_total_anual = round(custo_fixo_anual + combustivel_anual, 0)
    custo_total_mensal = round(custo_total_anual / 12.0, 0)

    return {
        "custo_total_mensal": custo_total_mensal,
        "custo_total_anual": custo_total_anual,
        "detalhamento_anual": {
            "ipva": ipva_anual,
            "ipva_isento": ipva_isento,
            "seguro": seguro_anual,
            "categoria_seguro": categoria_seguro,
            "manutencao": manutencao_anual,
            "combustivel": combustivel_anual,
        },
        "detalhamento_mensal": {
            "ipva": round(ipva_anual / 12.0, 0),
            "seguro": round(seguro_anual / 12.0, 0),
            "manutencao": round(manutencao_anual / 12.0, 0),
            "combustivel": combustivel_mensal,
        },
    }
