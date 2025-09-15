import streamlit as st
import ee
import geemap.foliumap as geemap 
import folium
from datetime import date, timedelta, datetime
import json
import tempfile
import calendar

# Cria arquivo temporário com as credenciais
service_account_info = dict(st.secrets["earthengine"])

with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False) as f:
    json.dump(service_account_info, f)
    f.flush()
    credentials = ee.ServiceAccountCredentials(service_account_info["client_email"], f.name)
    ee.Initialize(credentials)
    
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
# --- ESTILIZAÇÃO ---
with open('style.css')as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html = True)


# --- CONFIGURAÇÕES ---
# Mover constantes para o topo para fácil acesso
PALETA_PRECIPITACAO = ['1621a2', '03ffff', '13ff03', 'efff00', 'ffb103', 'ff2300']
MESES_NOME = {i: calendar.month_name[i] for i in range(1, 13)}

# Dicionário de datasets aprimorado com parâmetros de visualização
DATASETS = {
    'CHIRPS': {
        'id': 'UCSB-CHG/CHIRPS/DAILY',
        'id2': 'UCSB-CHG/CHIRPS/PENTAD',# Usado para agregados maiores (mensal/anual)
        'band': 'precipitation',
        'multiplier': 1,
        'start_year': 1981,
        'name': 'CHIRPS',
        'vis_params': {
            'ultima_imagem': {'min': 0.1, 'max': 15, 'palette': PALETA_PRECIPITACAO},
            'diario': {'min': 0.5, 'max': 50, 'palette': PALETA_PRECIPITACAO},
            'mensal': {'min': 50, 'max': 600, 'palette': PALETA_PRECIPITACAO},
            'anual': {'min': 200, 'max': 3000, 'palette': PALETA_PRECIPITACAO},
        }
    },
    'IMERG': {
        'id': 'NASA/GPM_L3/IMERG_V07',
        'id2': 'NASA/GPM_L3/IMERG_V07', # Usa a mesma coleção para tudo
        'band': 'precipitation',
        'multiplier': 0.5, # Multiplicador para converter mm/30min para mm/dia (assumindo soma)
        'start_year': 2000,
        'name': 'IMERG',
        'vis_params': {
            'ultima_imagem': {'min': 0.1, 'max': 15, 'palette': PALETA_PRECIPITACAO},
            'diario': {'min': 0.5, 'max': 50, 'palette': PALETA_PRECIPITACAO},
            'mensal': {'min': 50, 'max': 600, 'palette': PALETA_PRECIPITACAO},
            'anual': {'min': 200, 'max': 3000, 'palette': PALETA_PRECIPITACAO},
        }
    },
    'GSMAP': {
        'id': 'JAXA/GPM_L3/GSMaP/v8/operational',
        'id2': 'JAXA/GPM_L3/GSMaP/v8/operational',
        'band': 'hourlyPrecipRate',
        'multiplier': 1, # Já está em mm/h
        'start_year': 2000,
        'name': 'GSMaP',
        'vis_params': {
            'ultima_imagem': {'min': 0.1, 'max': 10, 'palette': PALETA_PRECIPITACAO},
            'diario': {'min': 0.5, 'max': 50, 'palette': PALETA_PRECIPITACAO},
            'mensal': {'min': 50, 'max': 600, 'palette': PALETA_PRECIPITACAO},
            'anual': {'min': 200, 'max': 3000, 'palette': PALETA_PRECIPITACAO},
        }
    },
}

# --- FUNÇÕES AUXILIARES OTIMIZADAS ---

@st.cache_data

def get_ultima_data_disponivel(info, colecao_id_key='id'):
    """Busca a última data disponível de forma robusta, expandindo o intervalo caso necessário."""
    hoje = date.today()
    dias_busca = [40, 90, 180, 365, 1000]  # tentar intervalos crescentes

    colecao_id = info[colecao_id_key]

    for dias in dias_busca:
        inicio = hoje - timedelta(days=dias)
        try:
            colecao = (
                ee.ImageCollection(colecao_id)
                .filterDate(str(inicio), str(hoje + timedelta(days=1)))
                .sort("system:time_start", False)
                .limit(1)
            )
            imagem = colecao.first()
            if imagem is not None:
                timestamp = imagem.get("system:time_start").getInfo()
                return date.fromtimestamp(timestamp / 1000)
        except Exception as e:
            st.error(f"Erro ao buscar data ({dias} dias): {e}")

    return None

def desenhar_mapa(image, vis_params, titulo, legenda):
    """Função para renderizar o mapa no Streamlit."""
    st.write(f"**Exibindo:** {titulo}")
    mapa = geemap.Map(center=[-15, -55], zoom=4, tiles='cartodbdark_matter')
    mapa.addLayer(image, vis_params, titulo)
    mapa.add_colorbar(vis_params, label=legenda,background_color='white')
    mapa.to_streamlit(width=1920, height=800)

def soma_periodo(info, inicio, fim, para_agregados=False):
    """
    Função simplificada para somar imagens em um período.
    Usa 'id2' se disponível e `para_agregados` for True.
    """
    colecao_id = info['id2'] if para_agregados and 'id2' in info else info['id']
    
    colecao = ee.ImageCollection(colecao_id) \
        .filterDate(inicio, fim) \
        .select(info['band'])

    # Aplica o multiplicador uniformemente
    colecao_com_mult = colecao.map(lambda img: img.multiply(info['multiplier']))
    
    return colecao_com_mult.sum()

# --- MODOS DE ANÁLISE REATORADOS ---

def ultima_imagem(info):
    """Mostra a imagem mais recente ou permite escolher entre as últimas disponíveis."""
    st.sidebar.header("Filtros")

    ultima_data = get_ultima_data_disponivel(info)
    if not ultima_data:
        st.warning("Não foi possível encontrar imagens recentes com dados disponíveis.")
        return

    # Buscar imagens nos últimos 40 dias até a última data disponível
    inicio_busca = ultima_data - timedelta(days=40)
    colecao = (
        ee.ImageCollection(info['id'])
        .filterDate(str(inicio_busca), str(ultima_data + timedelta(days=1)))
        .sort('system:time_start', False)
    )

    imagens_disponiveis = colecao.aggregate_array("system:time_start").getInfo()
    if not imagens_disponiveis:
        st.warning("Nenhuma imagem encontrada nos últimos 40 dias.")
        return

    if st.sidebar.checkbox("Selecionar imagem manualmente"):
        # Lista formatada para o usuário
        datas_formatadas = [
            datetime.fromtimestamp(t / 1000).strftime("%d/%m/%Y %H:%M")
            for t in imagens_disponiveis
        ]

        data_sel_str = st.sidebar.selectbox(
            "Imagens disponíveis:",
            options=datas_formatadas,
            index=0,
            key="dataset_ultima_imagem"
        )

        # Converter de volta para timestamp original
        idx = datas_formatadas.index(data_sel_str)
        timestamp_sel = imagens_disponiveis[idx]

        # Seleciona a imagem correspondente
        img = colecao.filterMetadata("system:time_start", "equals", timestamp_sel).first()
        data_img = data_sel_str
    else:
        # Última imagem automaticamente
        img = colecao.first()
        if img is None:
            st.warning("Nenhuma imagem encontrada.")
            return
        data_img = ee.Date(img.get("system:time_start")).format("dd/MM/YYYY - HH:mm").getInfo()

    # Visualização
    vis = info['vis_params']['ultima_imagem']
    imagem_final = (
        img.select(info['band'])
        .multiply(info['multiplier'])
        .updateMask(img.select(info['band']).gt(vis['min']))
    )

    desenhar_mapa(
        imagem_final,
        vis,
        f"Imagem para a data - {data_img}",
        "Precipitação Instantânea"
    )


def acumulado_diario(info):
    """Calcula e exibe o acumulado diário de precipitação, pegando sempre a última data válida."""
    st.sidebar.header("Filtros")
    
    ultima_data = get_ultima_data_disponivel(info)
    if not ultima_data:
        st.warning("Não foi possível determinar a última data com dados disponíveis.")
        return
    
    # O usuário pode escolher até a última data real
    data_sel = st.sidebar.date_input("Data", max_value=ultima_data, value=ultima_data)
    
    inicio = ee.Date(data_sel.strftime('%Y-%m-%d'))
    fim = inicio.advance(1, 'day')
    
    img_soma = soma_periodo(info, inicio, fim)
    
    vis = info['vis_params']['diario']
    imagem_final = img_soma.updateMask(img_soma.gt(vis['min']))

    desenhar_mapa(
        imagem_final,
        vis,
        f"Acumulado Diário - {data_sel.strftime('%d/%m/%Y')}",
        "Precipitação [mm/dia]"
    )
    
def acumulado_mensal(info):
    """Calcula e exibe o acumulado mensal."""
    st.sidebar.header("Filtros")

    hoje = date.today()
    ultima_data = get_ultima_data_disponivel(info, colecao_id_key='id2')
    if not ultima_data:
        st.warning("Não foi possível determinar a última data com dados disponíveis.")
        return

    ano_default = ultima_data.year
    mes_default = ultima_data.month

    anos_disponiveis = list(range(info['start_year'], hoje.year + 1))

    # Selectbox de ano
    ano_sel = st.sidebar.selectbox(
        "Ano",
        anos_disponiveis,
        index=anos_disponiveis.index(ano_default)
    )

    # Descobre quais meses têm dado no ano selecionado
    colecao_id = info['id2'] if 'id2' in info else info['id']
    colecao_ano = (
        ee.ImageCollection(colecao_id)
        .filterDate(f"{ano_sel}-01-01", f"{ano_sel+1}-01-01")
        .select(info['band'])
    )

    # Extrair lista de meses com dados
    def get_month(img):
        return ee.Date(img.get("system:time_start")).get("month")
    
    meses_disponiveis = (
        colecao_ano.map(lambda img: ee.Feature(None, {"month": get_month(img)}))
        .aggregate_array("month")
        .distinct()
        .getInfo()
    )
    meses_disponiveis = sorted(set(meses_disponiveis))

    if not meses_disponiveis:
        st.warning(f"Não há dados disponíveis para o ano {ano_sel}.")
        return

    # Selectbox de mês, já apontando para o último disponível
    mes_sel = st.sidebar.selectbox(
        "Mês",
        meses_disponiveis,
        format_func=lambda m: MESES_NOME[m],
        index=len(meses_disponiveis) - 1
    )

    # Intervalo de tempo
    inicio = ee.Date.fromYMD(ano_sel, mes_sel, 1)
    fim = inicio.advance(1, 'month')

    img_soma = soma_periodo(info, inicio, fim, para_agregados=True)

    vis = info['vis_params']['mensal']
    imagem_final = img_soma.updateMask(img_soma.gt(vis['min']))

    desenhar_mapa(
        imagem_final,
        vis,
        f"Acumulado Mensal - {MESES_NOME[mes_sel]}/{ano_sel}",
        "Precipitação [mm/mês]"
    )


def acumulado_anual(info):
    """Calcula e exibe o acumulado anual."""
    st.sidebar.header("Filtros")
    
    hoje = date.today()
    ultima_data = get_ultima_data_disponivel(info, colecao_id_key='id2')
    if not ultima_data:
        st.warning("Não foi possível determinar a última data com dados disponíveis.")
        return
        
    ano_default = ultima_data.year
    
    anos_disponiveis = range(info['start_year'], hoje.year + 1)
    ano_sel = st.sidebar.selectbox("Ano", anos_disponiveis, index=anos_disponiveis.index(ano_default))
    
    inicio = ee.Date.fromYMD(ano_sel, 1, 1)
    fim = inicio.advance(1, 'year')

    img_soma = soma_periodo(info, inicio, fim, para_agregados=True)

    vis = info['vis_params']['anual']
    imagem_final = img_soma.updateMask(img_soma.gt(vis['min']))
    st.sidebar.warning("Os dados anuais são acumulados a partir de dados pentadais ou diários, dependendo do dataset, o que pode levar a tempos de processamento mais longos.")
    desenhar_mapa(
        imagem_final,
        vis,
        f"Acumulado Anual - {ano_sel}",
        "Precipitação [mm/ano]"
    )


# --- INTERFACE PRINCIPAL DO APP ---
st.sidebar.title('Menu de Análise')
dataset_selecionado = st.sidebar.selectbox('Escolha o conjunto de dados:', list(DATASETS.keys()), index=1)
info_dataset = DATASETS[dataset_selecionado]

st.sidebar.divider()

modos = {
    "Última Imagem": ultima_imagem,
    "Acumulado Diário": acumulado_diario,
    "Acumulado Mensal": acumulado_mensal,
    "Acumulado Anual": acumulado_anual
}

# CHIRPS Daily não é ideal para "Última Imagem" por ter latência de ~2 dias
# e o Pentad (5 dias) não representa uma "imagem instantânea".
if dataset_selecionado == "CHIRPS":
    modos.pop("Última Imagem", None)

modo_selecionado = st.sidebar.radio("Escala Temporal:", list(modos.keys()))

st.sidebar.divider()
st.sidebar.write(f"**Fonte:** {info_dataset['name']} (desde {info_dataset['start_year']})")

# Executa a função do modo selecionado
if modo_selecionado:
    st.header(f"{info_dataset['name']} - {modo_selecionado}")
    modos[modo_selecionado](info_dataset)