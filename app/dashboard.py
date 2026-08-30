import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import asyncio
from pathlib import Path
import sys

# Adicionar pasta raiz ao path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from database.db_manager import DatabaseManager
from analytics.metrics import MarketAnalytics
from crawler.scraper import WebmotorsScraper
from crawler.orchestrator import NationalCrawlerOrchestrator
from config.settings import TARGET_BRANDS, ALL_UFS, UFS_TIER_1, UFS_TIER_2, UFS_TIER_3

# Configuração da Página
st.set_page_config(
    page_title="WebMotors Analytics Pro - Nacional",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Estilização CSS Customizada (Modern Dark / Glassmorphism)
st.markdown(
    """
    <style>
        .metric-card {
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            padding: 16px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            text-align: center;
        }
        .metric-value {
            font-size: 26px;
            font-weight: 700;
            color: #38bdf8;
            margin-top: 4px;
        }
        .metric-label {
            font-size: 13px;
            color: #94a3b8;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .badge-oportunidade {
            background-color: #10b981;
            color: white;
            padding: 4px 8px;
            border-radius: 6px;
            font-weight: 600;
        }
        .badge-spread {
            background-color: #8b5cf6;
            color: white;
            padding: 4px 8px;
            border-radius: 6px;
            font-weight: 600;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# Instâncias
db = DatabaseManager()

# Sidebar
st.sidebar.title("🚗 WebMotors Pro")
st.sidebar.caption("Inteligência e Arbitragem Automotiva Nacional")

aba = st.sidebar.radio(
    "Navegação",
    [
        "📊 Visão Geral do Mercado",
        "🗺️ Comparativo Regional & Arbitragem",
        "🎯 Radar de Barganhas",
        "📉 Curva de Depreciação",
        "⚙️ Coletor em Escala",
    ],
)

# Carregar Dados
@st.cache_data(ttl=60)
def carregar_dados():
    df = db.get_dataframe("SELECT * FROM anuncios WHERE status = 'ATIVO'")
    if not df.empty and "estado" in df.columns:
        df["uf_sigla"] = df["estado"].str.extract(r"\(([A-Z]{2})\)")[0].fillna(df["estado"]).str.strip().str.upper()
    return df

df_raw = carregar_dados()

# Filtros Globais na Sidebar
if not df_raw.empty:
    st.sidebar.markdown("---")
    st.sidebar.subheader("Filtros Globais")
    
    ufs_disponiveis = sorted([str(u) for u in df_raw["uf_sigla"].dropna().unique()])
    sel_ufs = st.sidebar.multiselect("Estados (UFs)", ufs_disponiveis, default=[])

    marcas_disponiveis = sorted([str(m) for m in df_raw["marca"].dropna().unique()])
    sel_marcas = st.sidebar.multiselect("Marcas", marcas_disponiveis, default=[])

    df_anuncios = df_raw.copy()
    if sel_ufs:
        df_anuncios = df_anuncios[df_anuncios["uf_sigla"].isin(sel_ufs)]
    if sel_marcas:
        df_anuncios = df_anuncios[df_anuncios["marca"].isin(sel_marcas)]
else:
    df_anuncios = df_raw.copy()


# -------------------------------------------------------------
# ABA 1: VISÃO GERAL DO MERCADO
# -------------------------------------------------------------
if aba == "📊 Visão Geral do Mercado":
    st.title("📊 Painel Geral de Mercado Webmotors")
    st.markdown("Visão consolidada de inventário, preços médios e distribuição de estoque.")

    if df_anuncios.empty:
        st.warning("Nenhum anúncio encontrado com os filtros selecionados. Acesse a aba **'⚙️ Coletor em Escala'** para expandir a base.")
    else:
        # Métricas no Topo
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.markdown(
                f"""<div class="metric-card"><div class="metric-label">Veículos no Filtro</div><div class="metric-value">{len(df_anuncios):,}</div></div>""",
                unsafe_allow_html=True,
            )
        with col2:
            st.markdown(
                f"""<div class="metric-card"><div class="metric-label">Preço Médio</div><div class="metric-value">R$ {df_anuncios['preco'].mean():,.0f}</div></div>""",
                unsafe_allow_html=True,
            )
        with col3:
            st.markdown(
                f"""<div class="metric-card"><div class="metric-label">KM Média</div><div class="metric-value">{df_anuncios['quilometragem'].mean():,.0f} km</div></div>""",
                unsafe_allow_html=True,
            )
        with col4:
            st.markdown(
                f"""<div class="metric-card"><div class="metric-label">Marcas Ativas</div><div class="metric-value">{df_anuncios['marca'].nunique()}</div></div>""",
                unsafe_allow_html=True,
            )
        with col5:
            st.markdown(
                f"""<div class="metric-card"><div class="metric-label">Estados Cobertos</div><div class="metric-value">{df_anuncios['uf_sigla'].nunique()}</div></div>""",
                unsafe_allow_html=True,
            )

        st.markdown("---")

        col_g1, col_g2 = st.columns([1, 1])

        with col_g1:
            st.subheader("Top Marcas com Maior Estoque")
            top_marcas = df_anuncios["marca"].value_counts().head(10).reset_index()
            top_marcas.columns = ["Marca", "Quantidade"]
            fig_marcas = px.bar(
                top_marcas,
                x="Marca",
                y="Quantidade",
                color="Quantidade",
                color_continuous_scale="Blues",
                text="Quantidade",
            )
            fig_marcas.update_layout(showlegend=False, margin=dict(l=20, r=20, t=30, b=20))
            st.plotly_chart(fig_marcas, use_container_width=True)

        with col_g2:
            st.subheader("Distribuição por Faixa de Preço")
            fig_preco = px.histogram(
                df_anuncios,
                x="preco",
                nbins=30,
                color_discrete_sequence=["#38bdf8"],
                labels={"preco": "Preço (R$)"},
            )
            fig_preco.update_layout(margin=dict(l=20, r=20, t=30, b=20))
            st.plotly_chart(fig_preco, use_container_width=True)

        st.subheader("Relação Preço vs. Quilometragem")
        fig_scatter = px.scatter(
            df_anuncios,
            x="quilometragem",
            y="preco",
            color="marca",
            hover_data=["modelo", "ano_modelo", "uf_sigla"],
            labels={"quilometragem": "Quilometragem (KM)", "preco": "Preço (R$)"},
        )
        fig_scatter.update_layout(margin=dict(l=20, r=20, t=30, b=20))
        st.plotly_chart(fig_scatter, use_container_width=True)


# -------------------------------------------------------------
# ABA 2: COMPARATIVO REGIONAL & ARBITRAGEM
# -------------------------------------------------------------
elif aba == "🗺️ Comparativo Regional & Arbitragem":
    st.title("🗺️ Comparativo Regional & Arbitragem Interestadual")
    st.markdown("Identifique discrepâncias de preço entre diferentes estados para comprar mais barato e vender com maior margem.")

    if df_raw.empty:
        st.warning("Base de dados vazia. Execute o coletor para obter dados de múltiplos estados.")
    else:
        df_reg = MarketAnalytics.resumo_regional(df_anuncios)
        
        if not df_reg.empty:
            col_r1, col_r2 = st.columns([1, 1])
            with col_r1:
                st.subheader("Preço Médio por Estado (UF)")
                fig_uf_preco = px.bar(
                    df_reg,
                    x="uf_sigla",
                    y="preco_medio",
                    color="preco_medio",
                    color_continuous_scale="Viridis",
                    labels={"uf_sigla": "UF", "preco_medio": "Preço Médio (R$)"},
                    text_auto=".2s",
                )
                fig_uf_preco.update_layout(showlegend=False, margin=dict(l=20, r=20, t=30, b=20))
                st.plotly_chart(fig_uf_preco, use_container_width=True)

            with col_r2:
                st.subheader("Participação de Estoque por UF")
                fig_uf_pie = px.pie(
                    df_reg,
                    names="uf_sigla",
                    values="total_veiculos",
                    hole=0.4,
                    color_discrete_sequence=px.colors.sequential.Plasma,
                )
                fig_uf_pie.update_layout(margin=dict(l=20, r=20, t=30, b=20))
                st.plotly_chart(fig_uf_pie, use_container_width=True)

        st.markdown("---")
        st.subheader("💰 Radar de Arbitragem Interestadual (Spread de Preços)")
        st.caption("Veículos com mesmo Modelo e Ano presentes em 2 ou mais estados diferentes.")

        df_arb = MarketAnalytics.calcular_arbitragem_interestadual(df_raw, min_amostras_uf=1)

        if df_arb.empty:
            st.info("Ainda não há amostras suficientes do mesmo modelo/ano em múltiplos estados para calcular a arbitragem. Execute o coletor para outros estados (Tier 1) para habilitar esta análise!")
        else:
            st.dataframe(
                df_arb.rename(
                    columns={
                        "marca": "Marca",
                        "modelo": "Modelo",
                        "ano_modelo": "Ano",
                        "uf_menor_preco": "UF Mais Barata",
                        "preco_menor": "Preço Mín (R$)",
                        "uf_maior_preco": "UF Mais Cara",
                        "preco_maior": "Preço Máx (R$)",
                        "spread_reais": "Diferença (R$)",
                        "spread_percentual": "Spread (%)",
                    }
                ).style.format(
                    {
                        "Preço Mín (R$)": "R$ {:,.2f}",
                        "Preço Máx (R$)": "R$ {:,.2f}",
                        "Diferença (R$)": "R$ {:,.2f}",
                        "Spread (%)": "{:.1f}%",
                    }
                ),
                use_container_width=True,
            )


# -------------------------------------------------------------
# ABA 3: RADAR DE BARGANHAS
# -------------------------------------------------------------
elif aba == "🎯 Radar de Barganhas":
    st.title("🎯 Radar de Barganhas Automotivas")
    st.markdown("Algoritmo que compara o anúncio individual com a média de mercado do mesmo modelo/ano.")

    if df_anuncios.empty:
        st.warning("Nenhum dado disponível para análise.")
    else:
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            margem_min = st.slider("Desconto Mínimo em relação à média (%)", 5, 40, 10) / 100.0
        with col_f2:
            min_amostras = st.slider("Amostras Mínimas da Categoria no Banco", 2, 10, 2)

        oportunidades = MarketAnalytics.calcular_radar_oportunidades(
            df_anuncios, min_amostras=min_amostras, margem_desconto_min=margem_min
        )

        if oportunidades.empty:
            st.info("Nenhuma oportunidade encontrada com esses parâmetros de filtro. Tente reduzir o desconto mínimo ou aumentar a base de dados.")
        else:
            st.success(f"Encontradas **{len(oportunidades)}** oportunidades de compra abaixo do preço médio de mercado!")

            for _, car in oportunidades.head(15).iterrows():
                with st.container():
                    col_img, col_info, col_price = st.columns([1.2, 2.5, 1.3])
                    
                    with col_img:
                        if car.get("foto_url"):
                            st.image(car["foto_url"], use_container_width=True)
                        else:
                            st.image("https://via.placeholder.com/300x200?text=Sem+Foto", use_container_width=True)

                    with col_info:
                        st.subheader(f"{car['marca']} {car['modelo']}")
                        st.caption(f"{car.get('versao', '')} • Ano: {int(car['ano_modelo'])} • KM: {car['quilometragem']:,.0f} km")
                        st.write(f"📍 **{car['cidade']} - {car.get('uf_sigla', car['estado'])}** | Vendedor: **{car['tipo_vendedor']}**")
                        st.markdown(f"[Ver Anúncio no Webmotors]({car['url_anuncio']})")

                    with col_price:
                        st.markdown(f"### R$ {car['preco']:,.2f}")
                        st.markdown(f"Média Categoria: **R$ {car['preco_medio_categoria']:,.2f}**")
                        st.markdown(
                            f"""<span class="badge-oportunidade">-{car['desconto_percentual']:.1f}% (Economia R$ {car['diferenca_valor']:,.0f})</span>""",
                            unsafe_allow_html=True,
                        )

                    st.divider()


# -------------------------------------------------------------
# ABA 4: CURVA DE DEPRECIAÇÃO
# -------------------------------------------------------------
elif aba == "📉 Curva de Depreciação":
    st.title("📉 Curva de Depreciação de Modelos")
    st.markdown("Acompanhe o comportamento de desvalorização dos modelos ao longo dos anos.")

    if df_anuncios.empty:
        st.warning("Nenhum dado disponível.")
    else:
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            marcas_disp = sorted(df_anuncios["marca"].unique())
            sel_marca = st.selectbox("Selecione a Marca", marcas_disp)

        with col_m2:
            modelos_disp = sorted(df_anuncios[df_anuncios["marca"] == sel_marca]["modelo"].unique())
            sel_modelo = st.selectbox("Selecione o Modelo", modelos_disp)

        if sel_marca and sel_modelo:
            curva = MarketAnalytics.curva_depreciacao(df_anuncios, sel_marca, sel_modelo)
            if curva.empty or len(curva) < 2:
                st.info(f"Amostra insuficiente de anos para traçar a curva do modelo {sel_marca} {sel_modelo} ({len(curva)} ano disponível).")
            else:
                fig_dep = px.line(
                    curva,
                    x="ano_modelo",
                    y="preco_medio",
                    markers=True,
                    title=f"Curva de Preço Médio por Ano: {sel_marca} {sel_modelo}",
                    labels={"ano_modelo": "Ano Modelo", "preco_medio": "Preço Médio (R$)"},
                )
                fig_dep.update_traces(line_color="#0284c7", line_width=3)
                st.plotly_chart(fig_dep, use_container_width=True)

                st.dataframe(
                    curva.rename(
                        columns={
                            "ano_modelo": "Ano Modelo",
                            "preco_medio": "Preço Médio (R$)",
                            "preco_min": "Mínimo (R$)",
                            "preco_max": "Máximo (R$)",
                            "km_media": "KM Média",
                            "total_veiculos": "Total Anúncios",
                        }
                    ).style.format(
                        {
                            "Preço Médio (R$)": "R$ {:,.2f}",
                            "Mínimo (R$)": "R$ {:,.2f}",
                            "Máximo (R$)": "R$ {:,.2f}",
                            "KM Média": "{:,.0f} km",
                        }
                    ),
                    use_container_width=True,
                )


# -------------------------------------------------------------
# ABA 5: COLETOR EM ESCALA (ORQUESTRADOR)
# -------------------------------------------------------------
elif aba == "⚙️ Coletor em Escala":
    st.title("⚙️ Painel do Coletor Nacional & Serviço Horário")
    st.markdown("Gerencie o serviço de sincronização contínua a cada hora e dispare coletas manuais sob demanda.")

    # ---------------------------------------------------------
    # PAINEL DO SERVIÇO DAEMON HORÁRIO
    # ---------------------------------------------------------
    st.subheader("⏰ Status do Serviço de Atualização Horária (Daemon)")
    
    pid_file = DATA_DIR / "daemon.pid"
    status_file = DAEMON_STATUS_PATH
    is_daemon_running = False
    daemon_pid = None

    if pid_file.exists():
        try:
            with open(pid_file, "r") as f:
                daemon_pid = int(f.read().strip())
            os.kill(daemon_pid, 0)
            is_daemon_running = True
        except (OSError, ValueError):
            is_daemon_running = False

    daemon_data = {}
    if status_file.exists():
        try:
            with open(status_file, "r", encoding="utf-8") as f:
                daemon_data = json.load(f)
        except Exception:
            pass

    col_d1, col_d2, col_d3, col_d4 = st.columns(4)
    with col_d1:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">Estado do Serviço</div>
                <div class="metric-value" style="color: {'#10b981' if is_daemon_running else '#f43f5e'};">
                    {'🟢 ATIVO' if is_daemon_running else '🔴 PARADO'}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_d2:
        intervalo = daemon_data.get("intervalo_minutos", 60)
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">Frequência</div>
                <div class="metric-value">A cada {intervalo}m</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_d3:
        proximo_raw = daemon_data.get("proximo_ciclo")
        proximo_txt = proximo_raw.split("T")[-1][:5] if proximo_raw and "T" in proximo_raw else "N/A"
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">Próximo Ciclo</div>
                <div class="metric-value">{proximo_txt}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_d4:
        ciclos = daemon_data.get("ciclos_completados", 0)
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">Ciclos Concluídos</div>
                <div class="metric-value">{ciclos}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Histórico de Execuções Recentes no DuckDB
    st.markdown("#### Histórico de Ciclos Horários")
    df_hist = db.get_historico_execucoes(limit=5)
    if df_hist.empty:
        st.info("Nenhuma execução registrada na tabela execucoes_crawler ainda.")
    else:
        st.dataframe(
            df_hist.rename(
                columns={
                    "id_execucao": "ID Execução",
                    "data_inicio": "Início",
                    "data_fim": "Fim",
                    "uf": "UF",
                    "marca": "Marca",
                    "total_anuncios_processados": "Processados",
                    "novos_anuncios": "Novos",
                    "anuncios_atualizados": "Atualizados",
                    "status": "Status",
                }
            ),
            use_container_width=True,
        )

    st.markdown("---")

    # ---------------------------------------------------------
    # DISPARO MANUAL SOB DEMANDA
    # ---------------------------------------------------------
    st.subheader("🚀 Disparo Manual Sob Demanda")
    tipo_operacao = st.radio(
        "Modalidade de Coleta Manual",
        ["🌍 Expansão Nacional em Lote (Recomendado)", "🎯 Coleta Pontual Específica"],
        horizontal=True,
    )

    if tipo_operacao == "🌍 Expansão Nacional em Lote (Recomendado)":
        col_t1, col_t2, col_t3 = st.columns(3)
        with col_t1:
            tier_escolhido = st.selectbox(
                "Grupo de Estados (UFs)",
                [
                    "Tier 1 (SP, RJ, MG, PR, SC, RS - 80% do estoque)",
                    "Tier 2 (BA, GO, DF, PE, CE, ES, MT, MS)",
                    "Tier 3 (Norte e Demais Estados)",
                    "Todas as 27 UFs do Brasil",
                ],
                index=0,
            )
        with col_t2:
            cat_marcas = st.selectbox(
                "Categoria de Marcas",
                [
                    "Marcas de Maior Volume (14 principais)",
                    "Marcas de Luxo e Premium (BMW, Audi, Porsche, etc.)",
                    "Elétricos e Híbridos (BYD, GWM)",
                    "Catálogo Completo (Todas as categorias)",
                    "Sem filtro de marca (Estoque Geral da UF)",
                ],
                index=0,
            )
        with col_t3:
            pags_shard = st.slider("Páginas por Shard", min_value=1, max_value=10, value=3)

        col_b1, col_b2 = st.columns([1, 1])
        with col_b1:
            btn_executar = st.button("🚀 Iniciar Expansão Nacional Agora", type="primary")
        with col_b2:
            limpar_cp = st.checkbox("Reiniciar do zero (limpar checkpoints anteriores)", value=False)

        if btn_executar:
            tier_code = "1" if "Tier 1" in tier_escolhido else ("2" if "Tier 2" in tier_escolhido else ("3" if "Tier 3" in tier_escolhido else "all"))
            brand_code = "volume" if "Volume" in cat_marcas else ("luxury" if "Luxo" in cat_marcas else ("ev" if "Elétricos" in cat_marcas else ("none" if "Sem filtro" in cat_marcas else "all")))

            with st.status("Executando Varredura Nacional...", expanded=True) as status:
                st.write(f"Configurando Shards: Tier={tier_code.upper()}, Marcas={brand_code.upper()}...")
                orchestrator = NationalCrawlerOrchestrator(db)
                
                if limpar_cp:
                    orchestrator.checkpoint_mgr.clear()

                shards = orchestrator.build_shards(tier=tier_code, brands_category=brand_code)
                st.write(f"Total de {len(shards)} partições mapeadas. Coletando...")

                try:
                    resultado = asyncio.run(
                        orchestrator.run(
                            shards=shards,
                            pages_per_shard=pags_shard,
                            resume=not limpar_cp,
                        )
                    )
                    status.update(label="Varredura finalizada com sucesso!", state="complete", expanded=False)
                    st.success(
                        f"🎉 Coleta concluída! {resultado['total_coletados']} anúncios processados, "
                        f"{resultado['novos_inseridos']} novos veículos salvos no DuckDB ({resultado['shards_concluidos']}/{resultado['total_shards']} shards finalizados)."
                    )
                    st.cache_data.clear()
                except Exception as e:
                    status.update(label="Falha na execução.", state="error")
                    st.error(f"Erro: {e}")

    else:
        # Coleta pontual
        col_c1, col_c2, col_c3 = st.columns(3)
        with col_c1:
            uf_coleta = st.selectbox("Estado (UF)", [u.upper() for u in ALL_UFS], index=0)
        with col_c2:
            marca_coleta = st.selectbox("Marca", ["TODAS"] + TARGET_BRANDS, index=0)
        with col_c3:
            paginas_coleta = st.slider("Qtd. de Páginas", min_value=1, max_value=20, value=3)

        if st.button("🚀 Iniciar Coleta Pontual", type="primary"):
            with st.status("Executando Coleta...", expanded=True) as status:
                scraper = WebmotorsScraper(db)
                marca_param = None if marca_coleta == "TODAS" else marca_coleta.lower()

                try:
                    resultado = asyncio.run(
                        scraper.run_collector(
                            uf=uf_coleta.lower(),
                            marca=marca_param,
                            max_paginas=paginas_coleta,
                            mode="api",
                            headless=True,
                        )
                    )
                    status.update(label="Coleta concluída!", state="complete", expanded=False)
                    st.success(
                        f"🎉 Sucesso! {resultado['total_coletados']} anúncios processados, "
                        f"{resultado['novos_inseridos']} novos veículos gravados."
                    )
                    st.cache_data.clear()
                except Exception as e:
                    status.update(label="Falha na coleta.", state="error")
                    st.error(f"Erro: {e}")
