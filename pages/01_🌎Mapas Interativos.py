import streamlit as st
import ee
import geemap.foliumap as geemap 
import folium
from datetime import date, timedelta, datetime
import json
import tempfile

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


with open('style.css')as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html = True)





# --- CONFIGURAÇÕES ---
PALETA_PRECIPITACAO = ['1621a2', '03ffff', '13ff03', 'efff00', 'ffb103', 'ff2300']

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
        'multiplier': 1000,  # em m, precisa multiplicar por 1000 para mm
        'multiplier2': 1000, # garante mm no mensal
        'temp': False,
        'start_year': 1950,
        'scale': 11132,
        'name': 'ECMWF ERA5',
        'type': 'hourly',
    }
}

# --- FUNÇÕES AUXILIARES ---
def desenhar_mapa(image, vis_params, titulo, legenda):
    st.write(f"**Exibindo:** {titulo}")
    mapa = geemap.Map(center=[-19, -60], zoom=4, tiles='cartodbdark_matter')
    mapa.addLayer(image, vis_params, titulo)
    mapa.add_colorbar(vis_params, label=legenda,background_color='white')
    mapa.to_streamlit(width=1920, height=800)


def soma_periodo(info, inicio, fim):
    tipo = info['type']

    colecao_base = ee.ImageCollection(info['id']) \
        .filterDate(inicio, fim) \
        .select(info['band'])

    if 'id2' in info and info['id2'] != info['id']:
        colecao_agregada = ee.ImageCollection(info['id2']) \
            .filterDate(inicio, fim) \
            .select(info['band2'])

        if tipo == 'subdaily' and info['temp']:
            # diferença em dias vira ee.Number
            dias = fim.difference(inicio, 'day')
            print(dias.getInfo())
            fator = ee.Number(info['multiplier2']).multiply(dias).multiply(24)

            colecao = colecao_agregada.map(
                lambda img: img.multiply(fator)
            )
        else:
            colecao = colecao_agregada.map(
                lambda img: img.multiply(info['multiplier2'])
            )
    else:
        if tipo == 'hourly':
            colecao = colecao_base.map(
                lambda img: img.multiply(info['multiplier'])
            )
        elif tipo == 'subdaily':
            colecao = colecao_base.map(
                lambda img: img.multiply(info['multiplier'])
            )
        elif tipo == 'daily':
            colecao = colecao_base.map(
                lambda img: img.multiply(info['multiplier'])
            )
        else:
            raise ValueError(f"Tipo desconhecido: {tipo}")

    return colecao.sum()




# --- MODOS DE ANÁLISE ---
@st.cache_data(show_spinner=True, ttl=3600)
def ultima_imagem(info):
    hoje = date.today()
    inicio = hoje - timedelta(days=40)  # buscar só nos últimos 40 dias
    colecao = ee.ImageCollection(info['id']) \
        .filterDate(str(inicio), str(hoje + timedelta(days=1))) \
        .sort('system:time_start', False)
    st.sidebar.selectbox('Imagens disponíveis nos últimos 40 dias:',
                 options=colecao.aggregate_array('system:time_start').map(lambda t: ee.Date(t).format('dd/MM/YYYY HH:mm')).getInfo(),
                 key="dataset_ultima_imagem")
    
    if colecao.size().getInfo() == 0:
        st.warning("Nenhuma imagem encontrada nos últimos 40 dias.")
        return

    img = colecao.first()
    data_img = ee.Date(img.get('system:time_start')).format('dd/MM/YYYY').getInfo()
    vis = {'min': 0, 'max': 15, 'palette': PALETA_PRECIPITACAO}

    desenhar_mapa(img.select(info['band']).updateMask(img.select(info['band']).gt(0.1)),
                  vis, f"Última Imagem - {data_img}", "Precipitação [mm]")
    


def acumulado_diario(info):
    st.sidebar.header("Filtros")

    hoje = date.today()
    inicio = hoje - timedelta(days=40)

    # Busca a última data com dados disponíveis nos últimos 40 dias
    colecao = ee.ImageCollection(info['id']) \
        .filterDate(str(inicio), str(hoje + timedelta(days=1))) \
        .sort('system:time_start', False)

    if colecao.size().getInfo() == 0:
        st.warning("Nenhum dado disponível nos últimos 40 dias.")
        return

    ultima_img = colecao.first()
    ultima_data = ee.Date(ultima_img.get('system:time_start')).format('YYYY-MM-dd').getInfo()
    ultima_data = date.fromisoformat(ultima_data)

    # Campo de seleção com a última data como padrão
    data_sel = st.sidebar.date_input(
        "Data",
        max_value=ultima_data,
        value=ultima_data
    )

    # Filtra novamente para o dia selecionado
    colecao_dia = ee.ImageCollection(info['id']) \
        .filterDate(str(data_sel), str(data_sel + timedelta(days=1))) \
        .select(info['band']) \
        .map(lambda img: img.multiply(info['multiplier']))

    if colecao_dia.size().getInfo() == 0:
        st.warning(f"Nenhum dado encontrado para {data_sel.strftime('%d/%m/%Y')}.")
        return

    img = colecao_dia.sum()
    vis = {'min': 0.5, 'max': 50, 'palette': PALETA_PRECIPITACAO}
    desenhar_mapa(
        img.updateMask(img.gt(0.5)),
        vis,
        f"Acumulado Diário - {data_sel.strftime('%d/%m/%Y')}",
        "Precipitação [mm/dia]"
    )



def acumulado_mensal(info):
    st.sidebar.header("Filtros")

    hoje = date.today()

    # pega a última imagem disponível (igual no diário)
    colecao = ee.ImageCollection(info['id2'] if ('id2' in info and info['id2'] != info['id']) else info['id']) \
        .filterDate(info['start_year'], str(hoje + timedelta(days=1))) \
        .sort('system:time_start', False)

    if colecao.size().getInfo() == 0:
        st.warning("Nenhum dado mensal disponível.")
        return

    ultima_img = colecao.first()
    ultima_data = ee.Date(ultima_img.get('system:time_start')).format('YYYY-MM-dd').getInfo()
    ultima_data = date.fromisoformat(ultima_data)
    ano_default, mes_default = ultima_data.year, ultima_data.month

    ano = st.sidebar.selectbox("Ano", range(info['start_year'], hoje.year+1),
                               index=ano_default - info['start_year'])
    meses = ["Janeiro","Fevereiro","Março","Abril","Maio","Junho",
             "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]
    mes = st.sidebar.selectbox("Mês", range(1,13),
                               format_func=lambda m: meses[m-1],
                               index=mes_default-1)

    inicio = ee.Date.fromYMD(ano, mes, 1)
    fim = inicio.advance(1, 'month')

    img = soma_periodo(info, inicio, fim)
    if img.bandNames().size().getInfo() == 0:
        st.warning(f"Nenhum dado encontrado para {meses[mes-1]}/{ano}.")
        return

    vis = {'min': 50, 'max': 600, 'palette': PALETA_PRECIPITACAO}
    desenhar_mapa(img.updateMask(img.gt(50)),
                  vis, f"Acumulado Mensal - {meses[mes-1]}/{ano}", "Precipitação [mm/mês]")




def acumulado_anual(info):
    st.sidebar.header("Filtros")
    hoje = date.today()

    # pega a última imagem disponível (igual no diário)
    colecao = ee.ImageCollection(info['id2'] if ('id2' in info and info['id2'] != info['id']) else info['id']) \
        .filterDate('1980-01-01', str(hoje + timedelta(days=1))) \
        .sort('system:time_start', False)

    if colecao.size().getInfo() == 0:
        st.warning("Nenhum dado anual disponível.")
        return

    ultima_img = colecao.first()
    ultima_data = ee.Date(ultima_img.get('system:time_start')).format('YYYY-MM-dd').getInfo()
    ultima_data = date.fromisoformat(ultima_data)
    ano_default = ultima_data.year

    ano = st.sidebar.selectbox("Ano", range(info['start_year'], hoje.year+1),
                               index=ano_default - info['start_year'])

    inicio = ee.Date.fromYMD(ano, 1, 1)
    fim = ee.Date.fromYMD(ano, 12, 31)

    img = soma_periodo(info, inicio, fim)
    if img.bandNames().size().getInfo() == 0:
        st.warning(f"Nenhum dado encontrado para {ano}.")
        return

    vis = {'min': 200, 'max': 3000, 'palette': PALETA_PRECIPITACAO}
    desenhar_mapa(img.updateMask(img.gt(200)),
                  vis, f"Acumulado Anual - {ano}", "Precipitação [mm/ano]")


# --- APP ---
st.sidebar.title('Menu')
dataset = st.sidebar.selectbox('Escolha o conjunto de dados:', list(DATASETS.keys()), index=2)
info = DATASETS[dataset]

st.sidebar.divider()
modos = {
    "Última Imagem": ultima_imagem,
    "Acumulado Diário": acumulado_diario,
    "Acumulado Mensal": acumulado_mensal,
    "Acumulado Anual": acumulado_anual
}

# Se for CHIRPS, remove a opção "Última Imagem"
if dataset == "CHIRPS":
    modos.pop("Última Imagem")

modo_sel = st.sidebar.radio("Escala Temporal:", list(modos.keys()))
st.sidebar.divider()
modos[modo_sel](info)
st.sidebar.write(f"**Fonte:** {info['name']} (desde {info['start_year']})")