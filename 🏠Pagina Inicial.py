# import streamlit as st
# import ee
# import geemap.foliumap as geemap 
# import folium
# from datetime import date, timedelta
# import json
# import tempfile

# # Configurações iniciais do Streamlit
# # Cria arquivo temporário com as credenciais
# service_account_info = dict(st.secrets["earthengine"])

# with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False) as f:
#     json.dump(service_account_info, f)
#     f.flush()
#     credentials = ee.ServiceAccountCredentials(service_account_info["client_email"], f.name)
#     ee.Initialize(credentials)

# # ee.Authenticate()
# # ee.Initialize(project='d2021028876')



# st.set_page_config(
#     layout='wide',
#     page_title='HydroGEE Analytics | Início',
#     initial_sidebar_state='collapsed',
#     menu_items={
#         'About': 'Aplicativo desenvolvido por Natanael Silva Oliveira para o TCC de Ciências Atmosféricas - UNIFEI.',
#         'Report a bug': 'mailto:natanaeloliveira2387@gmail.com'
#     },
#     page_icon='💧'
# )

# with open('style.css')as f:
#     st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html = True)
    
# # --- Configurações da Página e Inicialização do GEE ---
# # Bloco para inicializar o GEE de forma segura com st.secrets
# # Este bloco é executado apenas uma vez graças ao cache do Streamlit
# @st.cache_resource
# def initialize_gee():
#     try:
#         service_account_info = dict(st.secrets["earthengine"])
#         with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False) as f:
#             json.dump(service_account_info, f)
#             f.flush()
#             credentials = ee.ServiceAccountCredentials(service_account_info["client_email"], f.name)
#             ee.Initialize(credentials, project=credentials.project_id)
#         print("GEE Inicializado com sucesso.")
#     except Exception as e:
#         st.error("Ocorreu um erro ao inicializar o Google Earth Engine.")
#         st.error(f"Detalhes do erro: {e}")
#         st.stop()

# initialize_gee()


# # --- Funções de GEE em Cache para Performance ---

# # Usar o cache de dados garante que essa operação complexa do GEE
# # seja executada apenas uma vez, tornando a página inicial muito mais rápida.
# @st.cache_data
# def create_brazil_annual_map():
#     """
#     Cria e retorna um mapa geemap com a precipitação anual de 2023 para o Brasil.
#     """
#     try:
#         # Carrega os limites do Brasil
#         countries = ee.FeatureCollection('USDOS/LSIB_SIMPLE/2017')
#         brazil = countries.filter(ee.Filter.eq('country_na', 'Brazil'))

#         # Carrega a coleção CHIRPS para um ano de referência (ex: 2023)
#         precip_collection = ee.ImageCollection('UCSB-CHG/CHIRPS/PENTAD') \
#             .filter(ee.Filter.date('2023-01-01', '2023-12-31')) \
#             .select('precipitation')

#         # Soma todas as imagens para obter o acumulado anual
#         annual_precipitation = precip_collection.sum().clip(brazil)

#         # Parâmetros de visualização
#         palette = ['#1621a2', '#03ffff', '#13ff03', '#efff00', '#ffb103', '#ff2300']
#         vis_params = {'min': 200.0, 'max': 2500.0, 'palette': palette}

#         # Cria o mapa
#         m = geemap.Map(center=[-15, -55], zoom=4, tiles=None)
#         m.add_basemap('CartoDB.DarkMatter')
#         m.addLayer(
#             annual_precipitation,
#             vis_params,
#             'Precipitação Anual (2023)'
#         )
#         return m
#     except ee.ee_exception.EEException as e:
#         st.warning(f"Não foi possível gerar o mapa de exemplo. Erro no GEE: {e}")
#         return None

# # --- ESTRUTURA DA PÁGINA INICIAL ---

# # --- 1. Seção de Apresentação (Hero Section) ---
# st.title("💧 HydroGEE Analytics")
# st.markdown("##### Sua plataforma para análise de dados de precipitação com o poder do Google Earth Engine.")
# st.write("---")

# col1, col2 = st.columns([0.6, 0.4])

# with col1:
#     st.markdown("""
#     O **HydroGEE Analytics** oferece ferramentas intuitivas para explorar, visualizar e analisar padrões de chuva em todo o território brasileiro.
#     Navegue pelas nossas ferramentas na barra lateral para:

#     - **Visualizar mapas** de precipitação em diferentes escalas de tempo (instantâneo, diário, mensal e anual).
#     - **Gerar gráficos e séries temporais** para análises detalhadas por estado ou município.

#     Tudo isso processado em nuvem, de forma rápida e eficiente.
#     """)
#     st.info("👈 **Para começar, escolha uma das ferramentas de análise na barra lateral à esquerda.**", icon="💡")


# with col2:
#     with st.spinner("Carregando mapa de exemplo..."):
#         mapa_exemplo = create_brazil_annual_map()
#         if mapa_exemplo:
#             mapa_exemplo.to_streamlit(height=400)



# st.write("---")


# # --- 2. Seção de Funcionalidades ---
# st.header("Nossas Ferramentas de Análise")
# st.write("")

# c1, c2 = st.columns(2)

# with c1:
#     with st.container(border=True):
#         st.markdown("#### 🗺️ Visualizador de Mapas")
#         st.write("""
#         Visualize a distribuição espacial da precipitação em todo o Brasil. Ideal para entender a cobertura e intensidade dos eventos de chuva.
#         - **Escalas:** Instantânea, Diária, Mensal e Anual.
#         - **Fontes:** GPM IMERG (alta resolução temporal) e CHIRPS (longo período histórico).
#         - **Recursos:** Mapa interativo com zoom, legenda e seleção de período.
#         """)

# with c2:
#     with st.container(border=True):
#         st.markdown("#### 📊 Análise por Região")
#         st.write("""
#         Extraia dados quantitativos para uma localidade específica e analise o comportamento da chuva ao longo do tempo.
#         - **Seleção:** Escolha qualquer estado ou município do Brasil.
#         - **Gráficos:** Precipitação total anual e climatologia média mensal.
#         - **Objetivo:** Identificar tendências, sazonalidade e anomalias.
#         """)

# st.write("---")

# # --- 3. Seção sobre as Fontes de Dados ---
# st.header("Fontes de Dados Confiáveis")
# st.write("")

# d1, d2 = st.columns(2)

# with d1:
#      with st.container(border=True):
#         st.subheader("GPM IMERG")
#         st.write("""
#         O *Integrated Multi-satellitE Retrievals for GPM* é um produto de alta resolução da NASA que fornece estimativas de precipitação a cada 30 minutos.
#         É ideal para a análise de eventos de chuva de curta duração.
#         - **Resolução Espacial:** ~10 km
#         - **Disponibilidade:** 2000-Presente
#         """)

# with d2:
#     with st.container(border=True):
#         st.subheader("CHIRPS PENTAD")
#         st.write("""
#         O *Climate Hazards Group InfraRed Precipitation with Station data* é um banco de dados de mais de 40 anos, combinando dados de satélite com observações de estações.
#         É excelente para análises climatológicas e estudos de longo prazo.
#         - **Resolução Espacial:** ~5.5 km
#         - **Disponibilidade:** 1981-Presente
#         """)

# # --- 4. Seção de Instruções ---
# with st.expander("🤔 Como usar o aplicativo? (Clique para expandir)"):
#     st.markdown("""
#         1.  **Navegue na barra lateral:** Escolha entre `Visualizador de Mapas` ou `Análise por Região`.
#         2.  **Configure os filtros:** Dependendo da ferramenta, você definirá o período (data, mês, ano) ou a localidade (estado, município).
#         3.  **Execute a Análise:** Os dados serão processados no Google Earth Engine e exibidos na tela.
#         4.  **Interaja com os resultados:** Use o zoom nos mapas, passe o mouse sobre os gráficos para ver valores e explore os dados gerados.
#     """)

# # --- 5. Rodapé ---
# st.markdown("---")
# st.markdown(
#     """
#     <div style="text-align: center; color: grey;">
#         Desenvolvido com ❤️ por Natanael Silva Oliveira | TCC Ciências Atmosféricas - UNIFEI 2025
#     </div>
#     """,
#     unsafe_allow_html=True
# )




import streamlit as st
import ee
import geemap.foliumap as geemap
import json
import tempfile

# --- Configuração da Página e Estilo ---
st.set_page_config(
    layout='wide',
    page_title='HydroGEE Analytics | Início',
    initial_sidebar_state='collapsed',
    menu_items={
        'About': 'Aplicativo desenvolvido por Natanael Silva Oliveira para o TCC de Ciências Atmosféricas - UNIFEI.',
        'Report a bug': 'mailto:natanaeloliveira2387@gmail.com'
    },
    page_icon='💧'
)

# Carrega o estilo CSS personalizado
with open('style.css') as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# --- Inicialização Segura do Google Earth Engine ---
# Este bloco é executado apenas uma vez e fica em cache para otimizar o desempenho.
@st.cache_resource
def initialize_gee():
    try:
        service_account_info = dict(st.secrets["earthengine"])
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False) as f:
            json.dump(service_account_info, f)
            f.flush()
            credentials = ee.ServiceAccountCredentials(service_account_info["client_email"], f.name)
            # Use o project_id das credenciais para inicializar
            ee.Initialize(credentials, project=credentials.project_id)
            print("GEE Inicializado com sucesso.")
    except Exception as e:
        st.error("Ocorreu um erro ao inicializar o Google Earth Engine. Verifique as credenciais em st.secrets.")
        st.error(f"Detalhes do erro: {e}")
        st.stop()

initialize_gee()

# --- Função em Cache para Gerar o Mapa de Exemplo ---
# O cache de dados evita que o GEE processe a mesma informação repetidamente.
@st.cache_data
def create_brazil_annual_map():
    """
    Cria e retorna um mapa geemap com a precipitação anual de um ano de referência para o Brasil.
    """
    try:
        # Carrega a coleção de limites do Brasil
        countries = ee.FeatureCollection('USDOS/LSIB_SIMPLE/2017')
        brazil = countries.filter(ee.Filter.eq('country_na', 'Brazil'))

        # Carrega a coleção CHIRPS para um ano recente (ex: 2023)
        precip_collection = ee.ImageCollection('UCSB-CHG/CHIRPS/PENTAD') \
            .filter(ee.Filter.date('2023-01-01', '2023-12-31')) \
            .select('precipitation')

        # Soma todas as imagens para obter o acumulado anual e recorta para o Brasil
        annual_precipitation = precip_collection.sum().clip(brazil)

        # Parâmetros de visualização
        palette = ['#1621a2', '#03ffff', '#13ff03', '#efff00', '#ffb103', '#ff2300']
        vis_params = {'min': 200.0, 'max': 3000.0, 'palette': palette}

        # Cria o mapa com um tema escuro
        m = geemap.Map(center=[-15, -55], zoom=4, tiles=None)
        m.add_basemap('CartoDB.DarkMatter')
        m.addLayer(
            annual_precipitation,
            vis_params,
            'Precipitação Anual (2023)'
        )
        return m
    except ee.ee_exception.EEException as e:
        st.warning(f"Não foi possível gerar o mapa de exemplo. Erro no GEE: {e}")
        return None

# --- ESTRUTURA DA PÁGINA INICIAL ---

# --- 1. Seção de Apresentação (Hero Section) ---
st.title("💧 HydroGEE Analytics")
st.markdown("##### Sua plataforma para análise de dados de precipitação com o poder do Google Earth Engine.")
st.write("---")

col1, col2 = st.columns([0.6, 0.4])

with col1:
    st.markdown("""
    O **HydroGEE Analytics** oferece ferramentas intuitivas para explorar, visualizar e analisar padrões de chuva em todo o território brasileiro.
    Utilizando dados de satélite processados em nuvem, você pode gerar mapas, séries temporais e comparações de forma rápida e eficiente.

    Navegue pelas nossas ferramentas para:

    - **🗺️ Mapas Interativos:** Visualize a distribuição espacial da chuva em diferentes escalas de tempo.
    - **📈 Séries Temporais:** Extraia dados quantitativos para análises detalhadas por estado, município ou área de interesse.
    - **📊 Comparações:** Analise diferentes fontes de dados lado a lado para entender suas características e diferenças.
    """)
    st.info("👈 **Para começar, expanda o menu na barra lateral à esquerda e escolha uma das ferramentas de análise.**", icon="💡")

with col2:
    with st.spinner("Carregando mapa de exemplo..."):
        mapa_exemplo = create_brazil_annual_map()
        if mapa_exemplo:
            mapa_exemplo.to_streamlit(height=400)

st.write("---")

# --- 2. Seção de Funcionalidades ---
st.header("Nossas Ferramentas de Análise")
st.write("")

c1, c2, c3 = st.columns(3)

with c1:
    with st.container(border=True):
        st.markdown("#### 🗺️ Mapas Interativos")
        st.write("""
        Visualize a distribuição espacial da precipitação. Ideal para entender a cobertura e intensidade de eventos de chuva em todo o Brasil.
        - **Escalas:** Última imagem, Diária, Mensal e Anual.
        - **Fontes:** IMERG, GSMaP e CHIRPS.
        - **Recursos:** Mapa interativo com zoom, legenda e seleção de período.
        """)

with c2:
    with st.container(border=True):
        st.markdown("#### 📈 Séries Temporais por Região")
        st.write("""
        Extraia dados quantitativos para uma localidade específica e analise o comportamento da chuva ao longo do tempo.
        - **Seleção:** Por Estado, Município, Ponto (Lat/Lon) ou desenhando no mapa.
        - **Gráficos:** Séries diárias, mensais, climatologia e totais anuais.
        - **Objetivo:** Identificar tendências, sazonalidade e anomalias.
        """)

with c3:
    with st.container(border=True):
        st.markdown("#### 📊 Comparações")
        st.write("""
        Compare visualmente os resultados das principais fontes de dados de precipitação, lado a lado, para o mesmo período.
        - **Análise:** Compare as estimativas de chuva para o mesmo dia, mês ou ano.
        - **Fontes:** GSMaP vs. IMERG vs. CHIRPS.
        - **Utilidade:** Entender as diferenças e a sensibilidade de cada produto.
        """)

st.write("---")

# --- 3. Seção sobre as Fontes de Dados ---
st.header("Fontes de Dados Confiáveis")
st.write("Utilizamos produtos de precipitação globalmente reconhecidos e validados, processados pelo Google Earth Engine.")

d1, d2, d3 = st.columns(3)

with d1:
    with st.container(border=True):
        st.subheader("CHIRPS")
        st.write("""
        O *Climate Hazards Group InfraRed Precipitation with Station data* é um banco de dados de **mais de 40 anos**. Combina dados de satélite com milhares de estações em solo, sendo ideal para **análises climatológicas** e estudos de longo prazo.
        - **Resolução Espacial:** ~5.5 km
        - **Disponibilidade:** 1981-Presente
        """)

with d2:
    with st.container(border=True):
        st.subheader("GPM IMERG")
        st.write("""
        O *Integrated Multi-satellitE Retrievals for GPM* (NASA) é um produto de **alta resolução temporal** que fornece estimativas de chuva a cada 30 minutos. É ideal para a análise de **eventos de curta duração** e monitoramento quase em tempo real.
        - **Resolução Espacial:** ~10 km
        - **Disponibilidade:** 2000-Presente
        """)

with d3:
    with st.container(border=True):
        st.subheader("GPM GSMaP")
        st.write("""
        O *Global Satellite Mapping of Precipitation* (JAXA) é outro produto da missão GPM. Fornece dados **horários** e é conhecido por sua rapidez na disponibilização, sendo uma ótima fonte para o **acompanhamento de sistemas convectivos**.
        - **Resolução Espacial:** ~10 km
        - **Disponibilidade:** 2000-Presente
        """)

# --- 4. Seção de Instruções ---
with st.expander("🤔 Como usar o aplicativo? (Clique para expandir)"):
    st.markdown("""
        1.  **Navegue na barra lateral:** Clique no ícone `>` no canto superior esquerdo para abrir o menu e escolha entre `Mapas Interativos`, `Séries Temporais` ou `Comparações`.
        2.  **Configure os filtros:** Em cada página, um menu lateral permitirá que você defina a fonte de dados, o período (data, mês, ano) e/ou a localidade de interesse.
        3.  **Execute a Análise:** Clique no botão principal (ex: "Gerar Mapas" ou "Gerar Análise") para que os dados sejam processados no Google Earth Engine.
        4.  **Interaja com os resultados:** Use o zoom nos mapas, passe o mouse sobre os gráficos para ver valores detalhados e explore os dados gerados.
    """)

# --- 5. Rodapé ---
st.markdown("---")
st.markdown(
    """
    <div style="text-align: center; color: grey;">
        Desenvolvido por Natanael Silva Oliveira | TCC Ciências Atmosféricas - UNIFEI 2025
    </div>
    """,
    unsafe_allow_html=True
)