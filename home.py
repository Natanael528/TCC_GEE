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
                   initial_sidebar_state='expanded',
                   )

st.title('Chuva GEE')
st.markdown("teste streamlit com o GEE")

st.sidebar.title('Menu')

datain = st.sidebar.date_input("Data Inicial", max_value = date(2025, month=1, day=1))
datafi = st.sidebar.date_input("Data Final")

# Converte as datas para strings no formato 'YYYY-MM-DD'
datain_str = datain.strftime('%Y-%m-%d')
datafi_str = datafi.strftime('%Y-%m-%d')

# Carrega dados CHIRPS
chirps = ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY') \
           .select('precipitation') \
           .filterDate(datain_str, datafi_str)
           
           



# Paleta de cores
vis = {
    'min': 0,
    'max': 3000,
    'palette': ['000080', '0000d9', '4000ff', '8000ff', '0080ff', '00ffff', '00ff80',
                '80ff00', 'daff00', 'ffff00', 'fff500', 'ffda00', 'ffb000', 'ffa400',
                'ff4f00', 'ff2500', 'ff0a00', 'ff00ff']
}

# Cria o mapa
Map = geemap.Map(center=[-19, -60], zoom=4, tiles='cartodbdark_matter')
Map.addLayer(chirps.sum(), vis, 'Precipitação - 2024')
Map.add_colorbar(vis, label='Precipitação [mm/ano]', position='bottom')
Map.to_streamlit(width=1500, height=700)
