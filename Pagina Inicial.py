import streamlit as st
import ee
import geemap.foliumap as geemap 
import folium
from datetime import date, timedelta
import json
import tempfile

# Configurações iniciais do Streamlit
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


with open('style.css')as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html = True)


st.title('Análise de Dados de Chuva com Google Earth Engine')
st.markdown("""
    Este aplicativo permite visualizar dados de precipitação utilizando o Google Earth Engine. 
    Você pode selecionar uma região de interesse e um período para analisar os dados de chuva.
""")            
