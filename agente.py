from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.ollama import Ollama
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, Settings

# Corrigir: usar o system_prompt diretamente no Ollama
Settings.llm = Ollama(
    model="llama3",
    request_timeout=300,
    system_prompt="Você é um assistente de dados que responde sempre em português. Seja objetivo e claro."
)
Settings.embed_model = HuggingFaceEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")

def construir_index(diretorio: str):
    documentos = SimpleDirectoryReader(diretorio).load_data()
    index = VectorStoreIndex.from_documents(documentos)
    return index

index = construir_index("data")
perguntador = index.as_query_engine()

def responder(pergunta: str) -> str:
    resposta = perguntador.query(pergunta)
    return str(resposta)