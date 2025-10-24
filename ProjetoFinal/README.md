# 🪪 Licença
Distribuído sob a licença **MIT License**.  
Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

# 🤖 Agente Fiscal – Projeto Final I2A2

### 🧭 Visão Geral
O **Agente Fiscal** é uma aplicação que permite carregar dados fiscais estruturados (CSV, ZIP ou XML), armazená-los automaticamente em um banco SQLite e realizar consultas em **linguagem natural em português**.  
O agente converte as perguntas em SQL, executa e retorna resultados em formato de tabela, facilitando a criação de KPIs contábeis e fiscais.

---

### ⚙️ Tecnologias Utilizadas
- **Python 3.11+**
- **Streamlit** (interface)
- **LangChain + LLM** (interpretação de linguagem natural)
- **SQLite** (banco local)
- **Pandas, xmltodict, zipfile** (processamento de dados)

---

### 🧩 Estrutura do Repositório
📦 ProjetoFinal/
┣ 📂 ArquivosExemplos/ → exemplos de CSV/XML para teste
┣ 📂 TrabalhoFinal/ → artefatos da entrega (PDF, PPTX, MP4)
┣ 📜 app.py → aplicação principal (Streamlit)
┣ 📜 requirements.txt → dependências
┣ 📜 EXAMPLE.env → modelo de variáveis de ambiente
┣ 📜 README.md → este arquivo
┗ 📜 .gitignore / .gitkeep → controle de versão

---

### 🚀 Como Executar a Aplicação (passo a passo)

#### 1️⃣ Preparar o ambiente
```bash
# criar e ativar ambiente virtual (opcional)
python -m venv .venv
.\.venv\Scripts\activate       # Windows
# ou
source .venv/bin/activate      # Linux/Mac

# instalar dependências
pip install -r requirements.txt
2️⃣ Configurar o arquivo .env
Crie um arquivo chamado .env na raiz do projeto com as seguintes variáveis (use o EXAMPLE.env como modelo):
LLM_API_KEY=SEU_TOKEN_AQUI
LLM_MODEL_NAME=gpt-4o-mini
LLM_BASE_URL=https://api.openai.com/v1
3️⃣ Rodar a aplicação
streamlit run app.py
4️⃣ Usar a aplicação
1.	Na interface, envie seus arquivos CSV, XML ou ZIP.
2.	O sistema cria automaticamente as tabelas no banco SQLite (dados_fiscais.db).
3.	Faça perguntas em português — ex:
o	“Quais os 5 produtos mais vendidos?”
o	“Total de faturamento por mês”
4.	Veja os resultados direto na tela.
________________________________________
📊 Resultados e Benefícios
•	Ingestão automática e universal de dados fiscais (CSV/XML).
•	Consultas inteligentes em linguagem natural.
•	Base pronta para relatórios e dashboards em BI.
•	Integração futura com ERPs e validações fiscais.
________________________________________
🧱 Arquitetura Simplificada
[Streamlit UI] 
     ↓
[Parser CSV/XML]
     ↓
[SQLite Database]
     ↓
[LangChain + LLM]
     ↓
[Consultas PT-BR → SQL → Resultado]
