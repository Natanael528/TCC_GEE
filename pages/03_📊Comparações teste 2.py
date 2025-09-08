import streamlit as st
import ee
import geemap.foliumap as geemap 
import folium
from datetime import date, timedelta, datetime
import json
import tempfile
import pandas as pd
import altair as alt


# --- Configurações Iniciais e Autenticação do GEE ---
# Cria arquivo temporário com as credenciais
service_account_info = dict(st.secrets["earthengine"])

with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False) as f:
    json.dump(service_account_info, f)
    f.flush()
    credentials = ee.ServiceAccountCredentials(service_account_info["client_email"], f.name)
    ee.Initialize(credentials)

# --- Configuração da Página do Streamlit ---

st.set_page_config(
    layout='wide',
    page_title='HydroGEE Analytics | Início',
    initial_sidebar_state='expanded',
    menu_items={
        'About': 'Aplicativo desenvolvido por Natanael Silva Oliveira para o TCC de Ciências Atmosféricas - UNIFEI.',
        'Report a bug': 'mailto:natanaeloliveira2387@gmail.com'
    },
    page_icon='💧'
)

with open('style.css')as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html = True)


# --- CONFIGURAÇÕES DOS DADOS ---
PALETA_PRECIPITACAO = ['1621a2', '03ffff', '13ff03', 'efff00', 'ffb103', 'ff2300']

# Dicionário com informações detalhadas de cada fonte de dados
DATASETS = {
    'CHIRPS': {
        'id': 'UCSB-CHG/CHIRPS/DAILY',
        'id2': 'UCSB-CHG/CHIRPS/PENTAD',
        'band': 'precipitation',
        'band2': 'precipitation',
        'multiplier': 1,      # já vem em mm/dia
        'multiplier2': 1,     # já vem em mm/pentad
        'temp': False,
        'start_year': 1981,
        'scale': 5566,
        'name': 'CHIRPS',
        'type': 'daily',      # etiqueta para ajudar a função
    },
    'IMERG': {
        'id': 'NASA/GPM_L3/IMERG_V07',            # 30 min
        'id2': 'NASA/GPM_L3/IMERG_MONTHLY_V07',   # mensal
        'band': 'precipitation',
        'band2': 'precipitation',
        'multiplier': 0.5,    # 30 min → mm/24h (48 steps * 0.5 = 24h)
        'multiplier2': 1,     # 
        'temp': True,
        'start_year': 2000,
        'scale': 11132,
        'name': 'IMERG',
        'type': 'subdaily',
    },
    'GSMAP': {
        'id': 'JAXA/GPM_L3/GSMaP/v8/operational', # horário
        'id2': 'JAXA/GPM_L3/GSMaP/v8/operational',
        'band': 'hourlyPrecipRate',
        'band2': 'hourlyPrecipRate',
        'multiplier': 1,       # já em mm/h
        'multiplier2': 1,
        'temp': False,
        'start_year': 2000,
        'scale': 11132,
        'name': 'GSMaP',
        'type': 'hourly',
    },
    'ERA5': {
        'id': 'ECMWF/ERA5_LAND/HOURLY',
        'id2': 'ECMWF/ERA5_LAND/MONTHLY_AGGR',
        'band': 'total_precipitation',
        'band2': 'total_precipitation_sum',
        'multiplier': 1,     # em m, precisa multiplicar por 1000 para mm
        'multiplier2': 1000, # garante mm no mensal
        'temp': False,
        'start_year': 1950,
        'scale': 11132,
        'name': 'ECMWF ERA5',
        'type': 'hourly',
    }
}


# --- GEOMETRIA DO BRASIL ---
# Define a área de interesse como o polígono do Brasil
brazil_boundary = ee.FeatureCollection("USDOS/LSIB_SIMPLE/2017").filter(ee.Filter.eq('country_na', 'Brazil'))
brazil_geometry = brazil_boundary.geometry()


# --- CONFIGURAÇÕES DOS DADOS ---
PALETA_PRECIPITACAO = ['1621a2', '03ffff', '13ff03', 'efff00', 'ffb103', 'ff2300']

# Ordem fixa para exibição dos mapas e gráfico
DATASETS_PARA_COMPARAR = ['GSMAP', 'IMERG', 'CHIRPS', 'ERA5']

# --- FUNÇÕES AUXILIARES ---

def desenhar_mapa_em_coluna(coluna, image, vis_params, titulo, legenda):
    """Renderiza um mapa geemap dentro de uma coluna específica do Streamlit."""
    with coluna:
        st.subheader(titulo)
        mapa = geemap.Map(center=[-15.78, -55.92], zoom=3, tiles='cartodbdark_matter')
        mapa.add_basemap('HYBRID')
        
        # --- LINHA CORRIGIDA ---
        # Trocado 'add_ee_layer' por 'addLayer' e 'white' por '#FFFFFF'
        mapa.addLayer(brazil_boundary, {'color': 'FFFFFF', 'width': 1}, 'Fronteira Brasil')

        try:
            band_name = vis_params.get('bands', image.bandNames().get(0).getInfo())
            masked_image = image.select(band_name).updateMask(image.select(band_name).gt(vis_params['min']))
            # Clipa a imagem para o Brasil e adiciona ao mapa
            mapa.addLayer(masked_image.clip(brazil_geometry), vis_params, titulo)
            mapa.add_colorbar(vis_params, label=legenda, background_color='white', height=300)
        except Exception as e:
            st.warning(f"Pode não haver dados para o período selecionado.")
            
        mapa.to_streamlit(height=500)

def obter_soma_periodo(info, inicio, fim):
    colecao = ee.ImageCollection(info['id']).filterDate(inicio, fim).select(info['band'])

    # Casos especiais com coleção mensal/pentadal
    if 'id2' in info and (info['id2'] != info['id']) and (info['type'] in ['monthly', 'pentad']):
        colecao = ee.ImageCollection(info['id2']).filterDate(inicio, fim).select(info['band2'])
        return colecao.sum().multiply(info['multiplier2'])

    # IMERG: mm/h → mm/30min → mm/dia
    if info['name'] == "IMERG":
        colecao = colecao.map(lambda img: img.multiply(0.5))
        return colecao.sum()

    # ERA5: m → mm
    if info['name'] == "ECMWF ERA5":
        colecao = colecao.map(lambda img: img.multiply(1000))
        return colecao.sum()

    # GSMaP: já em mm/h → precisa multiplicar por 1h
    if info['name'] == "GSMaP":
        colecao = colecao.map(lambda img: img.multiply(1))
        return colecao.sum()

    # CHIRPS diário: já vem pronto em mm/dia
    if info['name'] == "CHIRPS":
        return colecao.sum()

    # fallback
    return colecao.sum().multiply(info['multiplier'])

def obter_dados_para_grafico(info, inicio, fim, regiao, modo):
    """Extrai a série temporal de precipitação média para uma região de interesse."""
    # Aumenta a escala para cálculos regionais para otimizar a performance
    escala_regional = 25000 # 25km

    def calcular_media_regional(img):
        # Calcula a média da precipitação para a região do Brasil
        valor = img.reduceRegion(
            reducer=ee.Reducer.mean(), 
            geometry=regiao, 
            scale=escala_regional,
            maxPixels=1e9
        ).get(img.bandNames().get(0))
        
        return ee.Feature(None, {
            'date': img.date().format('YYYY-MM-dd'),
            'precipitacao': ee.Number(valor).multiply(info['multiplier'])
        })

    if modo == "Diário":
        img_soma = obter_soma_periodo(info, inicio, fim)
        valor = img_soma.reduceRegion(
            reducer=ee.Reducer.mean(), 
            geometry=regiao, 
            scale=escala_regional,
            maxPixels=1e9
        ).get(img_soma.bandNames().get(0))
        valor_num = ee.Number(valor).getInfo()
        return pd.DataFrame([{'dataset': info['name'], 'precipitacao': valor_num if valor_num is not None else 0}])

    elif modo == "Mensal":
        colecao_diaria = ee.ImageCollection(info['id']).filterDate(inicio, fim).select(info['band'])
        dados = colecao_diaria.map(calcular_media_regional).getInfo()

    elif modo == "Anual":
        meses = ee.List.sequence(1, 12)
        def soma_mensal(mes):
            start_mes = ee.Date.fromYMD(inicio.get('year'), mes, 1)
            end_mes = start_mes.advance(1, 'month')
            soma_mes = obter_soma_periodo(info, start_mes, end_mes)
            valor = soma_mes.reduceRegion(
                reducer=ee.Reducer.mean(), 
                geometry=regiao, 
                scale=escala_regional,
                maxPixels=1e9
            ).get(soma_mes.bandNames().get(0))
            return ee.Feature(None, {'date': start_mes.format('YYYY-MM'), 'precipitacao': ee.Number(valor)})
        dados = meses.map(soma_mensal).getInfo()

    precipitacoes = [f['properties'] for f in dados['features']]
    df = pd.DataFrame(precipitacoes)
    if df.empty: return pd.DataFrame({'date': [], 'precipitacao': []})
        
    df['precipitacao'] = pd.to_numeric(df['precipitacao'], errors='coerce').fillna(0)
    df['dataset'] = info['name']
    df['date'] = pd.to_datetime(df['date'])
    return df


# --- MODOS DE ANÁLISE (LÓGICA PRINCIPAL) ---

def processar_comparacao(modo, regiao_geom, **kwargs):
    """Função central que busca os dados, exibe os mapas e o gráfico."""
    st.header(f"Comparação de Precipitação - {modo}")

    col1, col2, col3, col4 = st.columns(4)
    colunas = [col1, col2, col3, col4]
    dados_mapa = {}

    for nome_dataset in DATASETS_PARA_COMPARAR:
        info = DATASETS[nome_dataset]
        try:
            if modo == "Diário":
                data_sel = kwargs['data_sel']
                inicio = ee.Date(data_sel.strftime("%Y-%m-%d"))
                fim = inicio.advance(1, 'day')
                vis = {'min': 1, 'max': 50, 'palette': PALETA_PRECIPITACAO}
                legenda = "Precipitação [mm/dia]"
            elif modo == "Mensal":
                ano, mes_idx = kwargs['ano'], kwargs['mes_idx']
                inicio = ee.Date.fromYMD(ano, mes_idx, 1)
                fim = inicio.advance(1, 'month')
                vis = {'min': 50, 'max': 600, 'palette': PALETA_PRECIPITACAO}
                legenda = "Precipitação [mm/mês]"
            elif modo == "Anual":
                ano = kwargs['ano']
                inicio = ee.Date.fromYMD(ano, 1, 1)
                fim = ee.Date.fromYMD(ano, 12, 31)
                vis = {'min': 200, 'max': 3000, 'palette': PALETA_PRECIPITACAO}
                legenda = "Precipitação [mm/ano]"
            else:
                st.error("Modo de análise desconhecido."); return

            img = obter_soma_periodo(info, inicio, fim)
            dados_mapa[nome_dataset] = {'img': img, 'vis': vis, 'legenda': legenda, 'info': info, 'inicio': inicio, 'fim': fim}
        except Exception as e:
            st.error(f"Erro ao preparar dados para {info['name']}: {e}")
            dados_mapa[nome_dataset] = None

    for i, nome_dataset in enumerate(DATASETS_PARA_COMPARAR):
        if dados_mapa.get(nome_dataset):
            dados = dados_mapa[nome_dataset]
            desenhar_mapa_em_coluna(colunas[i], dados['img'], dados['vis'], dados['info']['name'], dados['legenda'])
        else:
            with colunas[i]:
                st.subheader(DATASETS[nome_dataset]['name'])
                st.error("Não foi possível carregar os dados do mapa.")

    # --- LÓGICA DO GRÁFICO ---
    st.write("---")
    st.header("Gráfico da Precipitação Média para o Brasil")
    dfs_grafico = []
    
    with st.spinner("Calculando precipitação média para o Brasil... Isso pode levar um momento."):
        for nome_dataset in DATASETS_PARA_COMPARAR:
            if dados_mapa.get(nome_dataset):
                dados = dados_mapa[nome_dataset]
                info = dados['info']
                try:
                    df = obter_dados_para_grafico(info, dados['inicio'], dados['fim'], regiao_geom, modo)
                    dfs_grafico.append(df)
                except Exception as e:
                    st.warning(f"Não foi possível obter dados do gráfico para {info['name']}: {e}")

    if dfs_grafico:
        df_final = pd.concat(dfs_grafico, ignore_index=True)
        if not df_final.empty:
            if modo == "Diário":
                chart = alt.Chart(df_final).mark_bar().encode(
                    x=alt.X('dataset:N', title='Fonte de Dados', sort='-y'),
                    y=alt.Y('precipitacao:Q', title='Precipitação Média (mm)'),
                    color=alt.Color('dataset:N', legend=alt.Legend(title="Fonte de Dados")),
                    tooltip=['dataset', alt.Tooltip('precipitacao', format='.2f')]
                ).properties(
                    title=f"Precipitação Média no Brasil em {kwargs['data_sel'].strftime('%d/%m/%Y')}"
                )
            else:
                eixo_x_titulo = 'Dia do Mês' if modo == "Mensal" else 'Mês'
                formato_data = '%d' if modo == "Mensal" else '%b'
                chart = alt.Chart(df_final).mark_line(point=True).encode(
                    x=alt.X('date:T', title=eixo_x_titulo, axis=alt.Axis(format=formato_data)),
                    y=alt.Y('precipitacao:Q', title='Precipitação Média (mm)'),
                    color=alt.Color('dataset:N', legend=alt.Legend(title="Fonte de Dados")),
                    tooltip=[alt.Tooltip('date:T', title='Data', format='%d/%m/%Y'), alt.Tooltip('precipitacao', format='.2f'), 'dataset']
                ).properties(
                    title=f"Precipitação Média {modo} para o Brasil"
                ).interactive()
            st.altair_chart(chart, use_container_width=True)
        else:
            st.info("Nenhum dado de precipitação encontrado para o período selecionado para gerar o gráfico.")

# --- INTERFACE DO USUÁRIO (SIDEBAR) ---
st.sidebar.title('Menu de Comparação')
st.sidebar.info("Selecione a escala e o período. Os mapas e o gráfico mostrarão dados de precipitação para todo o Brasil.")

modo_selecionado = st.sidebar.radio(
    "Escolha a Escala Temporal:",
    ["Diário", "Mensal", "Anual"],
    key="modo_temporal"
)

st.sidebar.header("Filtros de Período")

ANO_INICIAL_GLOBAL = min(d['start_year'] for d in DATASETS.values())
ANO_ATUAL = date.today().year

if modo_selecionado == "Diário":
    data_selecionada = st.sidebar.date_input(
        "Data", max_value=date.today() - timedelta(days=2), value=date.today() - timedelta(days=3)
    )
    if st.sidebar.button("Gerar Análise", use_container_width=True, key="btn_diario"):
        processar_comparacao("Diário", regiao_geom=brazil_geometry, data_sel=data_selecionada)

elif modo_selecionado == "Mensal":
    mes_passado = date.today().replace(day=1) - timedelta(days=1)
    ano_selecionado = st.sidebar.selectbox("Ano", range(ANO_INICIAL_GLOBAL, ANO_ATUAL + 1), index=range(ANO_INICIAL_GLOBAL, ANO_ATUAL + 1).index(mes_passado.year))
    meses_nomes = ["Janeiro","Fevereiro","Março","Abril","Maio","Junho","Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]
    mes_selecionado_idx = st.sidebar.selectbox("Mês", range(1,13), format_func=lambda m: meses_nomes[m-1], index=mes_passado.month-1)
    if st.sidebar.button("Gerar Análise", use_container_width=True, key="btn_mensal"):
        processar_comparacao("Mensal", regiao_geom=brazil_geometry, ano=ano_selecionado, mes_idx=mes_selecionado_idx)

elif modo_selecionado == "Anual":
    ultimo_ano_completo = ANO_ATUAL - 1
    ano_selecionado = st.sidebar.selectbox("Ano", range(ANO_INICIAL_GLOBAL, ultimo_ano_completo + 1), index=range(ANO_INICIAL_GLOBAL, ultimo_ano_completo + 1).index(ultimo_ano_completo))
    if st.sidebar.button("Gerar Análise", use_container_width=True, key="btn_anual"):
        st.sidebar.warning('Atenção: a busca de dados anuais para o gráfico pode demorar um pouco.')
        processar_comparacao("Anual", regiao_geom=brazil_geometry, ano=ano_selecionado)











