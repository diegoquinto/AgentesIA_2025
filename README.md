# Agente de Consulta de Notas Fiscais

Esta é uma aplicação que permite consultar informações de notas fiscais usando processamento de linguagem natural. A aplicação utiliza LangChain com OpenAI para interpretar perguntas em linguagem natural e convertê-las em consultas SQL.

## Pré-requisitos

- Python 3.8 ou superior
- Arquivo ZIP com os dados das notas fiscais (`202401_NFs.zip`) que contém:
  - `202401_NFs_Cabecalho.csv`: Arquivo com os cabeçalhos das notas fiscais
  - `202401_NFs_Itens.csv`: Arquivo com os itens das notas fiscais
  
Obs: Você só precisa ter o arquivo ZIP na pasta do projeto. A aplicação se encarregará de extrair automaticamente os arquivos CSV necessários durante a execução.

## Configuração do Ambiente

1. Clone o repositório:
```bash
git clone [URL_DO_REPOSITORIO]
cd AgentesIA-desafio2
```

2. Crie um ambiente virtual (recomendado):
```bash
python -m venv venv
.\venv\Scripts\activate  # Windows
source venv/bin/activate # Linux/Mac
```

3. Instale as dependências:
```bash
pip install -r requirements.txt
```

4. Configure as variáveis de ambiente:
   - Copie o arquivo `.env.example` para `.env` na raiz do projeto
   - Configure as variáveis de ambiente de acordo com o provedor de LLM escolhido:

Para OpenAI:
```env
LLM_API_KEY=sua_chave_api_aqui
LLM_MODEL_NAME=gpt-4
LLM_BASE_URL=https://api.openai.com/v1
```

Para outros provedores, configure as três variáveis conforme necessário:
- `LLM_API_KEY`: Sua chave de API
- `LLM_MODEL_NAME`: Nome do modelo a ser usado
- `LLM_BASE_URL`: URL base da API

## Estrutura do Projeto

```
.
├── 202401_NFs.zip            # Arquivo ZIP com os dados das notas fiscais
├── app.py                    # Aplicação principal
├── requirements.txt          # Dependências do projeto
└── notas.db                  # Banco de dados SQLite (gerado automaticamente)

Nota: Os arquivos CSV (202401_NFs_Cabecalho.csv e 202401_NFs_Itens.csv) são automaticamente 
extraídos do arquivo ZIP durante a execução da aplicação.
```

## Como Executar

1. Certifique-se de que o arquivo `202401_NFs.zip` está na raiz do projeto

2. Execute a aplicação:
```bash
streamlit run app.py
```

3. Acesse a interface web através do navegador (geralmente em http://localhost:8501)

## Funcionalidades

A aplicação permite fazer consultas em linguagem natural sobre os dados das notas fiscais. Exemplos de perguntas que podem ser feitas:

- Qual o valor total das notas fiscais emitidas em janeiro de 2024?
- Quais foram os 5 fornecedores que mais emitiram notas fiscais em valor total?
- Qual a média de itens por nota fiscal?
- Quais produtos tiveram maior volume vendido (em quantidade)?
- Qual é o ticket médio (valor médio por nota fiscal)?
- Qual o total de notas fiscais emitidas por cada CNPJ fornecedor?
- Quantas notas fiscais foram emitidas por dia ao longo de janeiro?
- Quais foram os 10 produtos mais vendidos em valor total?
- Qual o valor total de notas fiscais emitidas por tipo de operação?
- Quais notas fiscais tiveram mais de 3 itens diferentes?

## Tecnologias Utilizadas

- Python
- Streamlit (interface web)
- LangChain (processamento de linguagem natural)
- LangChain com suporte a múltiplos provedores LLM (OpenAI, Together.ai, Groq, OpenRouter)
- SQLite (banco de dados)
- Pandas (manipulação de dados)

## Observações

- A aplicação requer uma chave de API válida do provedor escolhido (OpenAI, Together.ai, Groq ou OpenRouter)
- Os dados são armazenados localmente em um banco SQLite
- O cache está ativado para melhor performance nas consultas
- Todas as três variáveis de ambiente (LLM_API_KEY, LLM_MODEL_NAME, LLM_BASE_URL) são necessárias para qualquer provedor
