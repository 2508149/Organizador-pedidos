"""
main.py - Ponto de entrada.   Execute:  streamlit run main.py
"""
import streamlit as st

# Precisa ser o primeiro comando do Streamlit.
st.set_page_config(
    page_title="Organizador de Pedidos",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="collapsed",
)

import interface  # noqa: E402  (importado depois de set_page_config)

interface.render()
