import streamlit as st
import ee
import geemap.foliumap as geemap 
from streamlit_folium import folium_static
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
                   initial_sidebar_state='collapsed',
                   menu_items={'About': 'Aplicativo desenvolvido por Natanael Silva Oliveira para o projeto de TCC do curso de Ciências Atmosféricas da Universidade Federal de Itajubá - UNIFEI.',
                                 'Report a bug': 'mailto: natanaeloliveira2387@gmail.com'},
                   page_icon='🌧️')


st.sidebar.title('Menu')

# datain = st.sidebar.date_input("Data Inicial",  max_value= date.today() - timedelta(days=62))
# datafi = st.sidebar.date_input("Data Final", max_value= date.today() - timedelta(days=61))

# # Converte as datas para strings no formato 'YYYY-MM-DD'
# datain_str = datain.strftime('%Y-%m-%d')
# datafi_str = datafi.strftime('%Y-%m-%d')

# # Carrega dados CHIRPS
# chirps = ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY') \
#            .select('precipitation') \
#            .filterDate(datain_str, datafi_str)
           


# # Paleta de cores
# vis = {
#     'min': 0,
#     'max': 100,
#     'palette': ['000080', '0000d9', '4000ff', '8000ff', '0080ff', '00ffff', '00ff80',
#                 '80ff00', 'daff00', 'ffff00', 'fff500', 'ffda00', 'ffb000', 'ffa400',
#                 'ff4f00', 'ff2500', 'ff0a00', 'ff00ff']
# }

# # Cria o mapa
# Map = geemap.Map(center=[-19, -60], zoom=4, tiles='cartodbdark_matter')
# Map.addLayer(chirps.sum(), vis, 'Precipitação - 2024')
# Map.add_colorbar(vis, label='Precipitação [mm/ano]')
#Map.to_streamlit(width=1500, height=700)




datafi = st.sidebar.date_input("Data", max_value= date.today())


# # Converte as datas para strings no formato 'YYYY-MM-DD'
datain_str = datafi - timedelta(days=1)

datain_str = datain_str.strftime('%Y-%m-%d')
datafi_str = datafi.strftime('%Y-%m-%d')


# Carrega o dataset GPM
dataset = ee.ImageCollection('JAXA/GPM_L3/GSMaP/v8/operational') \
    .filter(ee.Filter.date(datain_str, datafi_str))
    


# Seleciona a taxa de precipitação horária
precipitation = dataset.select('hourlyPrecipRate')

# Configura a visualização
precipitationVis = {
    'min': 2,
    'max': 150.0,
    'palette': ['1621a2','03ffff', '13ff03', 'efff00', 'ffb103', 'ff2300']}

# Cria o mapa
Map = geemap.Map(center=[-19, -60], zoom=4, tiles='cartodbdark_matter')
Map.addLayer(precipitation.sum().updateMask(precipitation.sum().gt(2)), precipitationVis, 'Precipitação Horária', opacity=1)


Map.add_colorbar(precipitationVis, background_color='white', step= 20, label='Precipitação [mm/h]')
Map.to_streamlit(width=1820, height=900)

