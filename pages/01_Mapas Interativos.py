import streamlit as st
import ee
import geemap.foliumap as geemap 
import folium
from datetime import date, timedelta
import json
import tempfile

# Cria arquivo temporário com as credenciais
service_account_info = dict(st.secrets["earthengine"])

with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False) as f:
    json.dump(service_account_info, f)
    f.flush()
    credentials = ee.ServiceAccountCredentials(service_account_info["client_email"], f.name)
    ee.Initialize(credentials)
    
st.set_page_config(layout='wide',
                   page_title='Chuva GEE',
                   initial_sidebar_state='expanded',
                   menu_items={'About': 'Aplicativo desenvolvido por Natanael Silva Oliveira para o projeto de TCC do curso de Ciências Atmosféricas da Universidade Federal de Itajubá - UNIFEI.',
                                 'Report a bug': 'mailto: natanaeloliveira2387@gmail.com'},
                   page_icon='🌧️')


with open('TCC_GEE/style.css')as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html = True)

st.sidebar.title('Menu')




genre = st.sidebar.radio(
    "Escolha a opção de precipitação:",
    ["***Instantâneo***","***Diário***", "***Mensal***", "***Anual***"],
    captions=[
        "Última imagem fornecida.",
        "Acumulado diário.",
        "Acumulado mensal.",
        "Acumulado anual.",
    ],
)

if genre == "***Diário***":
    
    # --- Barra Lateral ---
    st.sidebar.header("Filtros")

    datafi = st.sidebar.date_input("Data", max_value= date.today() -  timedelta(days=1))


    # # Converte as datas para strings no formato 'YYYY-MM-DD'
    datain_str = datafi - timedelta(days=1)

    datain_str = datain_str.strftime('%Y-%m-%d')
    datafi_str = datafi.strftime('%Y-%m-%d')
    
    st.write("Você selecionou o acumulado diário para o dia **{}**".format(datafi_str))

    # Carrega o dataset GPM
    dataset = ee.ImageCollection('NASA/GPM_L3/IMERG_V07') \
        .filter(ee.Filter.date(datain_str, datafi_str))
        

    
    
    # Seleciona a taxa de precipitação horária
    precipitation = dataset.select('precipitation')

    # Configura a visualização
    precipitationVis = {
        'min': 1,
        'max': 100.0,
        'palette': ['1621a2','03ffff', '13ff03', 'efff00', 'ffb103', 'ff2300']}


    #st.write("Precipitação média no ponto selecionado: {:.2f} mm/h".format(precipitation.get('precipitation').getInfo()))
    # Cria o mapa
    Map = geemap.Map(center=[-19, -60], zoom=4, tiles='cartodbdark_matter')
    Map.addLayer(precipitation.sum().updateMask(precipitation.sum().gt(0.5)), precipitationVis, 'Precipitação Horária', opacity=1)

    Map.add_colorbar(precipitationVis, background_color='white', step= 20, label='Precipitação [mm/dia]')
    Map.to_streamlit(width=1820, height=900)
    

elif genre == "***Mensal***":
    
    

    # --- Barra Lateral ---
    st.sidebar.header("Filtros")
    ano = st.sidebar.number_input(
        "Selecione o ano:", 
        min_value=2000, 
        max_value=date.today().year, 
        value=date.today().year
    )

    mes_nome = st.sidebar.selectbox("Selecione o mês:",
        ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", 
        "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"],
        index=date.today().month - 1 # Começa no mês atual
    )

    # --- Lógica Principal ---
    # Converte o nome do mês para número (1 a 12)
    mes_num = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", 
            "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"].index(mes_nome) + 1
    
    st.write("Você selecionou o acumulado mensal.  **{}** de **{}**".format(mes_nome, ano))

    # Usa a abordagem robusta do GEE para definir o período
    start_date = ee.Date.fromYMD(ano, mes_num, 1)
    end_date = start_date.advance(1, 'month')

    # Carrega a coleção de imagens GPM e filtra pelo intervalo de datas correto
    dataset = ee.ImageCollection('NASA/GPM_L3/IMERG_V07') \
        .filterDate(start_date, end_date)
        
    # Seleciona a banda de precipitação e calcula o acumulado mensal para todo o globo

    # transforma de mm/h para mm/0.5h
    imerge_mes = dataset.map(lambda img: img.multiply(0.5).copyProperties(img, img.propertyNames()))
    
    # soma a chuva do mês, ficando a unidade em mm/mês
    imerge_mes = imerge_mes.select('precipitation').sum()
    
    # Ajusta a escala para um acumulado mensal em mm
    precipitationVis = {
        'min': 50.0,
        'max': 400.0, # Um valor máximo realista para chuvas mensais
        'palette': ['1621a2','03ffff', '13ff03', 'efff00', 'ffb103', 'ff2300']
    }

    # Cria o mapa, com um zoom mais afastado para a visualização global
    Map = geemap.Map(center=[-19, -60], zoom=4, tiles='cartodbdark_matter')

    # Adiciona a camada de precipitação mensal
    Map.addLayer(
        imerge_mes.updateMask(imerge_mes.gt(50)),  # Máscara para mostrar apenas áreas com mais de 50mm
        precipitationVis, 
        f'Precipitação {mes_nome}/{ano}'
    )

    # Adiciona a legenda com o rótulo e unidade corretos
    Map.add_colorbar(
        precipitationVis, 
        label='Precipitação Acumulada [mm/mês]', 
        orientation='vertical', 
        layer_name=f'Precipitação {mes_nome}/{ano}',
        background_color='white'
    )
    Map.to_streamlit(width=1820, height=900)
    
elif genre == "***Anual***":

    

    # --- Barra Lateral ---
    st.sidebar.header("Filtros")
    ano = st.sidebar.number_input(
        "Selecione o ano:", 
        min_value=2000, 
        max_value=date.today().year, 
        value=date.today().year
    )

    # --- Lógica Principal ---
    # Define o período de interesse para o ano inteiro
    datain = date(ano, 1, 1)
    datafi = date(ano, 12, 31)

    # Converte as datas para strings no formato 'YYYY-MM-DD' para o filtro do GEE
    datain_str = datain.strftime('%Y-%m-%d')
    datafi_str = datafi.strftime('%Y-%m-%d')

    st.write("Você selecionou o acumulado anual, focado no Brasil para o ano de **{}**".format(ano))

    # **NOVA ETAPA:** Carrega os limites dos países e filtra para obter o Brasil
    countries = ee.FeatureCollection('USDOS/LSIB_SIMPLE/2017')
    brazil = countries.filter(ee.Filter.eq('country_na', 'Brazil'))

    # Carrega a coleção de imagens GPM e filtra por data
    dataset = ee.ImageCollection('NASA/GPM_L3/IMERG_V07') \
        .filter(ee.Filter.date(datain_str, datafi_str))

    # Seleciona a banda de precipitação
    precipitation_collection = dataset.select('precipitation')

    # Soma todas as imagens da coleção para obter o acumulado anual
    annual_precipitation = precipitation_collection.sum()

    # **NOVA ETAPA:** Recorta a imagem de precipitação usando o limite do Brasil
    brazil_precipitation = annual_precipitation.clip(brazil)

    # Ajusta os parâmetros de visualização para um acumulado anual (mm)
    precipitationVis = {
        'min': 200.0,
        'max': 3000.0,
        'palette': ['1621a2', '03ffff', '13ff03', 'efff00', 'ffb103', 'ff2300']
    }

    # Cria o mapa, centralizado no Brasil
    Map = geemap.Map(center=[-15, -55], zoom=4, tiles='cartodbdark_matter')

    # Adiciona a camada de precipitação anual recortada para o Brasil
    # Usamos uma máscara para mostrar apenas áreas com mais de 200mm de chuva anual
    Map.addLayer(
        brazil_precipitation.updateMask(brazil_precipitation.gt(200)), 
        precipitationVis, 
        f'Precipitação Acumulada {ano} - Brasil'
    )

    # Adiciona a legenda com o rótulo e unidade corretos
    Map.add_colorbar(
        precipitationVis, 
        label='Precipitação Acumulada [mm/ano]', 
        orientation='vertical', 
        layer_name=f'Precipitação Acumulada {ano} - Brasil',
        background_color='white'
    )
    Map.to_streamlit(width=1820, height=900)
    
else:
    st.write("Você selecionou o acumulado instantâneo.")

    # --- Barra Lateral ---
    st.sidebar.header("Filtros")
    datafi = st.sidebar.date_input("Data", max_value= date.today() -  timedelta(days=0))

    # Converte as datas para strings no formato 'YYYY-MM-DD'
    datain_str = datafi - timedelta(days=1)
    datain_str = datain_str.strftime('%Y-%m-%d')
    datafi_str = datafi.strftime('%Y-%m-%d')

    # Carrega o dataset GPM
    dataset = ee.ImageCollection('NASA/GPM_L3/IMERG_V07') \
        .filter(ee.Filter.date(datain_str, datafi_str))
    
    # Ordena o dataset pela data e seleciona a primeira imagem (mais recente)
    dataset = dataset.sort('system:time_start', False).first()
    # Seleciona a taxa de precipitação horária
    precipitation = dataset.select('precipitation')

    # Configura a visualização
    precipitationVis = {
        'min': 1,
        'max': 30.0,
        'palette': ['1621a2','03ffff', '13ff03', 'efff00', 'ffb103', 'ff2300']}

    # Cria o mapa
    Map = geemap.Map(center=[-19, -60], zoom=4, tiles='cartodbdark_matter')
    Map.addLayer(precipitation.updateMask(precipitation.gt(0.5)), precipitationVis, 'Precipitação Horária', opacity=1)

    Map.add_colorbar(precipitationVis, background_color='white', step= 20, label='Precipitação [mm/h]')
    Map.to_streamlit(width=1820, height=900)