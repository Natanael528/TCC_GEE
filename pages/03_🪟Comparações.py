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

}

# Ordem fixa para exibição dos mapas
DATASETS_PARA_COMPARAR = ['GSMAP', 'IMERG', 'CHIRPS']

# --- FUNÇÕES AUXILIARES ---

def desenhar_mapa_em_coluna(coluna, image, vis_params, titulo, legenda):
    """Renderiza um mapa geemap dentro de uma coluna específica do Streamlit."""
    with coluna:
        st.subheader(titulo)
        mapa = geemap.Map(center=[-19, -60], zoom=3, tiles='cartodbdark_matter')
        
        # Adiciona uma verificação para garantir que a imagem não está vazia
        try:
            # Pega o nome da banda do dicionário de visualização se possível, senão da imagem
            band_name = vis_params.get('bands', image.bandNames().get(0).getInfo())
            masked_image = image.select(band_name).updateMask(image.select(band_name).gt(vis_params['min']))
            mapa.addLayer(masked_image, vis_params, titulo)
            mapa.add_colorbar(vis_params, label=legenda, background_color='white')
        except Exception as e:
            st.warning(f"Pode não haver dados para o período selecionado.")
            
        mapa.to_streamlit(height=600)

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

    # GSMaP: já em mm/h → precisa multiplicar por 1h
    if info['name'] == "GSMaP":
        colecao = colecao.map(lambda img: img.multiply(1))
        return colecao.sum()

    # CHIRPS diário: já vem pronto em mm/dia
    if info['name'] == "CHIRPS":
        return colecao.sum()

    # fallback
    return colecao.sum().multiply(info['multiplier'])




# --- MODOS DE ANÁLISE (LÓGICA PRINCIPAL) ---

def processar_comparacao(modo, **kwargs):
    """Função central que busca os dados para os 3 datasets e os exibe em colunas."""
    st.header(f"Comparação de Precipitação - {modo}")

    col1, col2, col3 = st.columns(3)
    colunas = [col1, col2, col3]

    for i, nome_dataset in enumerate(DATASETS_PARA_COMPARAR):
        info = DATASETS[nome_dataset]
        
        try:
            if modo == "Diário":
                data_sel = kwargs['data_sel']

                inicio = ee.Date(data_sel.strftime("%Y-%m-%d"))
                fim = inicio.advance(1, 'day')
                img = obter_soma_periodo(info, inicio, fim)
                vis = {'min': 1, 'max': 50, 'palette': PALETA_PRECIPITACAO}
                legenda = "Precipitação [mm/dia]"

            elif modo == "Mensal":
                ano, mes_idx, meses = kwargs['ano'], kwargs['mes_idx'], kwargs['meses']

                inicio = ee.Date.fromYMD(ano, mes_idx, 1)
                fim = inicio.advance(1, 'month')
                img = obter_soma_periodo(info, inicio, fim)
                vis = {'min': 50, 'max': 600, 'palette': PALETA_PRECIPITACAO}
                legenda = "Precipitação [mm/mês]"

            elif modo == "Anual":
                ano = kwargs['ano']
                
                inicio = f"{ano}-01-01"
                fim = f"{ano}-12-31"
                img = obter_soma_periodo(info, inicio, fim)
                vis = {'min': 200, 'max': 3000, 'palette': PALETA_PRECIPITACAO}
                legenda = "Precipitação [mm/ano]"

            else:
                st.error("Modo de análise desconhecido.")
                return

            desenhar_mapa_em_coluna(colunas[i], img, vis, info['name'], legenda)
        
        except Exception as e:
            with colunas[i]:
                st.subheader(info['name'])
                st.error(f"Ocorreu um erro ao processar os dados para {info['name']}: {e}")

# --- INTERFACE DO USUÁRIO (SIDEBAR) ---
st.sidebar.title('Menu de Comparação')
st.sidebar.info("Selecione a escala temporal e o período. Os mapas das bases de dados GSMAP, CHIRPS e IMERG serão exibidos lado a lado.")

modo_selecionado = st.sidebar.radio(
    "Escolha a Escala Temporal:",
    ["Diário", "Mensal", "Anual"]
)

st.sidebar.header("Filtros de Período")

# O ano mínimo deve ser o da base mais antiga (CHIRPS: 1981)
ANO_INICIAL_GLOBAL = min(d['start_year'] for d in DATASETS.values())
ANO_ATUAL = date.today().year

if modo_selecionado == "Diário":
    data_selecionada = st.sidebar.date_input(
        "Data",
        max_value=date.today() - timedelta(days=1),
        value=date.today() - timedelta(days=2)
    )
    if st.sidebar.button("Gerar Mapas", use_container_width=True):
        processar_comparacao("Diário", data_sel=data_selecionada)

elif modo_selecionado == "Mensal":
    mes_passado = date.today().replace(day=1) - timedelta(days=1)
    
    ano_selecionado = st.sidebar.selectbox("Ano", range(ANO_INICIAL_GLOBAL, ANO_ATUAL + 1), index=range(ANO_INICIAL_GLOBAL, ANO_ATUAL + 1).index(mes_passado.year))
    
    meses_nomes = ["Janeiro","Fevereiro","Março","Abril","Maio","Junho",
                   "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]
    mes_selecionado_idx = st.sidebar.selectbox("Mês", range(1,13), format_func=lambda m: meses_nomes[m-1], index=mes_passado.month-1)
    
    if st.sidebar.button("Gerar Mapas", use_container_width=True):
        processar_comparacao("Mensal", ano=ano_selecionado, mes_idx=mes_selecionado_idx, meses=meses_nomes)

elif modo_selecionado == "Anual":
    ultimo_ano_completo = ANO_ATUAL - 1
    ano_selecionado = st.sidebar.selectbox("Ano", range(ANO_INICIAL_GLOBAL, ultimo_ano_completo + 1), index=range(ANO_INICIAL_GLOBAL, ultimo_ano_completo + 1).index(ultimo_ano_completo))
    if st.sidebar.button("Gerar Mapas", use_container_width=True):
        processar_comparacao("Anual", ano=ano_selecionado)
        st.sidebar.warning('Atenção: alguns plots podem demorar um pouco para carregar devido ao volume de dados anual.')




