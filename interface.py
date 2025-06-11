import streamlit as st
from agente import responder

# Configurações da página
st.set_page_config(page_title="Agente de Notas Fiscais", layout="centered")

st.title("📊 Agente de Notas Fiscais")
st.markdown("Faça uma pergunta sobre os dados das notas fiscais. A resposta será gerada automaticamente usando IA.")

# Campo de pergunta
pergunta = st.text_input("Digite sua pergunta", placeholder="Exemplo: Qual fornecedor recebeu o maior valor?")

# Quando o usuário envia uma pergunta
if pergunta:
    with st.spinner("Consultando os dados..."):
        resposta = responder("Responda em português: " + pergunta)
    st.success("Resposta:")
    st.write(resposta)
