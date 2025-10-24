
# -*- coding: utf-8 -*-
"""
App: Agente Fiscal – CSV/XML → SQLite → Perguntas em Português (Robusto p/ XML)
- CSV, XML, ZIP (CSV)
- XML: tenta NF-e (cabecalho/itens) ou flatten genérico
- XML loader robusto: remove BOM, ignora lixo inicial, detecta HTML/JSON/ZIP por engano, tenta encodings comuns
"""
import os as _os
import os
import io
import re
import zipfile
import sqlite3
import pandas as pd
import xmltodict
import streamlit as st

from dotenv import load_dotenv
load_dotenv()

# LangChain / LLM
from langchain_community.utilities import SQLDatabase
from langchain_openai import ChatOpenAI
from langchain_community.agent_toolkits import create_sql_agent
from langchain.globals import set_llm_cache
from langchain_community.cache import InMemoryCache

set_llm_cache(InMemoryCache())

st.set_page_config(page_title="Agente Fiscal – CSV/XML (Robusto)", layout="wide")
st.title("🧾 Agente Fiscal – CSV/XML → SQLite → Perguntas em Português")

st.markdown("""
Faça upload de **CSVs / XMLs** (ou **ZIP** com CSVs). Para **NF-e**, geramos tabelas de **cabeçalho** e **itens**.
O parser de XML agora é **mais robusto** (remove BOM, tenta múltiplos encodings, detecta HTML/ZIP por engano).
""")

api_key = os.environ.get('LLM_API_KEY')
model_name = os.environ.get('LLM_MODEL_NAME')
base_url = os.environ.get('LLM_BASE_URL')

with st.sidebar:
    st.header("⚙️ Configurações")
    db_name = st.text_input("Nome do arquivo SQLite", value="dados_fiscais.db")
    drop_and_recreate = st.checkbox("Recriar tabelas se já existirem (replace)", value=True)
    show_previews = st.checkbox("Mostrar prévia de dados após carga", value=True)

    st.markdown("---")
    st.subheader("LLM")
    st.write(f"Modelo: `{model_name or 'não definido'}`")
    st.write(f"Base URL: `{base_url or 'não definida'}`")
    if not api_key or not model_name or not base_url:
        st.warning("Defina `LLM_API_KEY`, `LLM_MODEL_NAME` e `LLM_BASE_URL` no seu .env para habilitar o agente.")

# ---------- Utils ----------
def sanitize_table_name(name: str) -> str:
    base = re.sub(r'\.[Cc][Ss][Vv]$', '', name)
    base = re.sub(r'\.[Xx][Mm][Ll]$', '', base)
    base = re.sub(r'[^0-9a-zA-Z_]+', '_', base).strip('_')
    return base.lower() or "tabela"

def read_csv_best_effort(file_like, filename: str) -> pd.DataFrame:
    encodings = [None, 'utf-8', 'latin1', 'cp1252']
    for enc in encodings:
        try:
            df = pd.read_csv(file_like, sep=None, engine="python", encoding=enc)
            return df
        except Exception:
            if hasattr(file_like, "seek"):
                file_like.seek(0)
            continue
    if hasattr(file_like, "seek"):
        file_like.seek(0)
    return pd.read_csv(file_like, sep=",", engine="python", encoding="utf-8")

def to_sql_chunks(df: pd.DataFrame, conn: sqlite3.Connection, table_name: str, if_exists_mode: str):
    chunksize = 50_000 if len(df) > 100_000 else None
    df.to_sql(table_name, conn, if_exists=if_exists_mode, index=False, chunksize=chunksize)

# ---------- Robust XML parsing ----------
def _strip_bom_and_noise(b: bytes) -> bytes:
    # Remove BOM utf-8 se houver
    if b.startswith(b'\xef\xbb\xbf'):
        b = b[3:]
    # Remove bytes de controle iniciais não imprimíveis antes do primeiro '<'
    idx = b.find(b'<')
    if idx > 0:
        head = b[:idx]
        if any(c > 0 and c < 32 for c in head):
            b = b[idx:]
    return b

def _detect_false_format(b: bytes) -> str | None:
    # Heurísticas de formato errado (HTML/JSON/ZIP) enviados como .xml
    head = b[:20].strip().lower()
    if head.startswith(b'<!doctype html') or head.startswith(b'<html'):
        return "HTML"
    if head.startswith(b'{') or head.startswith(b'['):
        return "JSON"
    if b[:2] == b'PK':  # ZIP
        return "ZIP"
    if head.startswith(b'%pdf'):
        return "PDF"
    return None

def _safe_xml_to_dict(raw_bytes: bytes):
    b = _strip_bom_and_noise(raw_bytes)
    bogus = _detect_false_format(b)
    if bogus:
        raise RuntimeError(f"O arquivo enviado parece ser {bogus}, não XML válido.")
    # Tenta múltiplos encodings
    candidates = [None, 'utf-8', 'latin1', 'cp1252']
    last_err = None
    for enc in candidates:
        try:
            if enc is None:
                return xmltodict.parse(b)
            else:
                return xmltodict.parse(b.decode(enc, errors='ignore'))
        except Exception as e:
            last_err = e
            continue
    raise RuntimeError(f"XML inválido: {last_err}")

def _flatten_dict(d, parent_key="", sep="__"):
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else str(k)
        if isinstance(v, dict):
            items.extend(_flatten_dict(v, new_key, sep=sep).items())
        elif isinstance(v, list):
            parts = []
            for it in v:
                if isinstance(it, dict):
                    parts.append(",".join(f"{a}:{b}" for a,b in _flatten_dict(it).items()))
                else:
                    parts.append(str(it))
            items.append((new_key, " | ".join(parts)))
        else:
            items.append((new_key, v))
    return dict(items)

def _is_nfe(xmlobj: dict) -> bool:
    return bool((isinstance(xmlobj, dict) and ('nfeProc' in xmlobj or 'NFe' in xmlobj or 'procNFe' in xmlobj)))

def _extract_nfe_roots(xmlobj: dict):
    node = None
    if 'nfeProc' in xmlobj:
        node = xmlobj['nfeProc']
    elif 'procNFe' in xmlobj:
        node = xmlobj['procNFe']
    else:
        node = xmlobj
    if isinstance(node, dict) and 'NFe' in node:
        node = node['NFe']
    if isinstance(node, dict) and 'infNFe' in node:
        return node['infNFe']
    return None

def parse_xml_to_tables(file_bytes: bytes, filename: str):
    # ... seu código que chama _safe_xml_to_dict/file parsing ...
    xmlobj = _safe_xml_to_dict(file_bytes)  # ou xmltodict.parse(..) se você usa essa

    tables = []
    base_name = sanitize_table_name(filename)

    # >>> NOVO: detecta XML "Envio -> detList -> det -> prod"
    if _is_envio_generico(xmlobj):
        return parse_envio_generico(xmlobj, filename)
    # <<< FIM NOVO

    # ... depois mantém a sua lógica de NF-e ...
    if _is_nfe(xmlobj):
        # (mantém o que você já tem para nfeProc/NFe/infNFe)
        ...
    else:
        # fallback flatten genérico (como já estava)
        flat = _flatten_dict(xmlobj)
        df_one = pd.DataFrame([flat])
        tables.append((base_name, df_one))
        return tables

def extract_zip_and_return_csvs(file_bytes: bytes):
    out = []
    with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
        for info in zf.infolist():
            if not info.is_dir() and info.filename.lower().endswith(".csv"):
                with zf.open(info, 'r') as f:
                    out.append((os.path.basename(info.filename), f.read()))
    return out
def _is_envio_generico(xmlobj: dict) -> bool:
    """
    Detecta XML no formato:
      Envio
        └─ detList
            └─ det (lista)
                └─ prod (dict com cProd, xProd, qCom, vUnCom, vProd)
    """
    if not isinstance(xmlobj, dict):
        return False
    raiz = xmlobj.get('Envio') or xmlobj.get('envio') or xmlobj.get('ENVIO')
    if not isinstance(raiz, dict):
        return False
    det_list = raiz.get('detList') or raiz.get('DetList') or raiz.get('DETList')
    if not isinstance(det_list, dict):
        return False
    det = det_list.get('det') or det_list.get('Det') or det_list.get('DET')
    return bool(det)

def _to_float(x):
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip()
    if s == '':
        return None
    # aceita "1.234,56" ou "1234.56"
    s = s.replace('.', '').replace(',', '.') if ',' in s and '.' in s else s.replace(',', '.')
    try:
        return float(s)
    except:
        return None

def parse_envio_generico(xmlobj: dict, filename: str):
    """
    Converte o XML 'Envio -> detList -> det -> prod' em:
      <base>_cabecalho (1 linha, se existirem metadados no topo)
      <base>_itens (cProd, xProd, qCom, vUnCom, vProd)
    """
    import pandas as _pd

    base_name = sanitize_table_name(filename)

    raiz = xmlobj.get('Envio') or xmlobj.get('envio') or xmlobj.get('ENVIO')
    det_list = raiz.get('detList') or raiz.get('DetList') or raiz.get('DETList')
    det = det_list.get('det') or det_list.get('Det') or det_list.get('DET')

    if isinstance(det, dict):
        det = [det]
    det = det or []

    # Tenta capturar alguns campos de topo para cabecalho (se existirem)
    possiveis_topo = ['idEnvio','data','numero','serie','cliente','cnpjCliente','observacao']
    cab = {k: raiz.get(k) for k in possiveis_topo if k in raiz}
    #cab_df = _pd.DataFrame([cab]) if cab else _pd.DataFrame([{}])
    cab_df = _pd.DataFrame([{'arquivo': _os.path.basename(filename)}])
    cab_name = f"{base_name}_cabecalho"

    # Itens
    rows = []
    for d in det:
        prod = d.get('prod', {}) if isinstance(d, dict) else {}
        row = {
            'cProd': prod.get('cProd') or prod.get('codigo') or prod.get('cod'),
            'xProd': prod.get('xProd') or prod.get('descricao') or prod.get('nome'),
            'qCom': _to_float(prod.get('qCom') or prod.get('quantidade') or prod.get('qtd')),
            'vUnCom': _to_float(prod.get('vUnCom') or prod.get('valorUnit') or prod.get('precoUnit')),
            'vProd': _to_float(prod.get('vProd') or prod.get('valorTotal') or prod.get('total')),
        }
        rows.append(row)

    itens_df = _pd.DataFrame(rows) if rows else _pd.DataFrame(columns=['cProd','xProd','qCom','vUnCom','vProd'])
    itens_name = f"{base_name}_itens"

    # saneia nomes de colunas (sem espaços)
    cab_df.columns = [re.sub(r'\s+','_', str(c)) for c in cab_df.columns]
    itens_df.columns = [re.sub(r'\s+','_', str(c)) for c in itens_df.columns]

    # garante tipos numéricos
    for col in ['qCom','vUnCom','vProd']:
        if col in itens_df.columns:
            itens_df[col] = itens_df[col].apply(_to_float)

    return [(cab_name, cab_df), (itens_name, itens_df)]
# ---------- Upload ----------
st.subheader("📤 Upload de CSV(s)/XML(s) ou ZIP (CSV)")
uploads = st.file_uploader("Selecione um ou múltiplos arquivos", type=["csv", "zip", "xml"], accept_multiple_files=True)
loaded_tables = []

if uploads:
    with st.spinner("Carregando dados para o SQLite..."):
        conn = sqlite3.connect(db_name)
        for up in uploads:
            fname = up.name
            if fname.lower().endswith(".zip"):
                try:
                    csv_list = extract_zip_and_return_csvs(up.read())
                    if not csv_list:
                        st.warning(f"ZIP '{fname}' não contém CSVs.")
                        continue
                    for inner_name, content in csv_list:
                        try:
                            table_name = sanitize_table_name(inner_name)
                            df = read_csv_best_effort(io.BytesIO(content), inner_name)
                            if drop_and_recreate:
                                try: conn.execute(f"DROP TABLE IF EXISTS [{table_name}]")
                                except Exception: pass
                            to_sql_chunks(df, conn, table_name, if_exists_mode='replace' if drop_and_recreate else 'append')
                            loaded_tables.append(table_name)
                            if show_previews:
                                st.caption(f"Prévia: **{table_name}** (de {inner_name})")
                                st.dataframe(pd.read_sql_query(f"SELECT * FROM [{table_name}] LIMIT 50;", conn))
                        except Exception as e:
                            st.error(f"Falha ao carregar '{inner_name}' do ZIP '{fname}': {e}")
                except zipfile.BadZipFile:
                    st.error(f"Arquivo '{fname}' não é um ZIP válido.")
            elif fname.lower().endswith(".xml"):
                try:
                    tables = parse_xml_to_tables(up.read(), fname)
                    for tname, tdf in tables:
                        if drop_and_recreate:
                            try: conn.execute(f"DROP TABLE IF EXISTS [{tname}]")
                            except Exception: pass
                        to_sql_chunks(tdf, conn, tname, if_exists_mode='replace' if drop_and_recreate else 'append')
                        loaded_tables.append(tname)
                        if show_previews:
                            st.caption(f"Prévia: **{tname}** (de {fname})")
                            st.dataframe(pd.read_sql_query(f"SELECT * FROM [{tname}] LIMIT 50;", conn))
                except Exception as e:
                    st.error(f"Falha ao carregar XML '{fname}': {e}")
            else:
                try:
                    table_name = sanitize_table_name(fname)
                    df = read_csv_best_effort(io.BytesIO(up.read()), fname)
                    if drop_and_recreate:
                        try: conn.execute(f"DROP TABLE IF EXISTS [{table_name}]")
                        except Exception: pass
                    to_sql_chunks(df, conn, table_name, if_exists_mode='replace' if drop_and_recreate else 'append')
                    loaded_tables.append(table_name)
                    if show_previews:
                        st.caption(f"Prévia: **{table_name}** (de {fname})")
                        st.dataframe(pd.read_sql_query(f"SELECT * FROM [{table_name}] LIMIT 50;", conn))
                except Exception as e:
                    st.error(f"Falha ao carregar '{fname}': {e}")
        conn.commit()
        conn.close()

    if loaded_tables:
        st.success(f"✅ Tabelas carregadas/atualizadas: {', '.join(loaded_tables)}")
    else:
        st.warning("Nenhuma tabela foi criada.")

# ---------- Explorar DB ----------
st.subheader("🗄️ Exploração do Banco")
if os.path.exists(db_name):
    conn = sqlite3.connect(db_name)
    try:
        tables = pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;", conn)['name'].tolist()
    except Exception:
        tables = []
    col1, col2 = st.columns(2)
    with col1:
        st.write("**Tabelas detectadas**")
        st.write(tables or "—")
    with col2:
        chosen = st.selectbox("Ver schema (PRAGMA)", options=["—"] + tables, index=0)
        if chosen and chosen != "—":
            try:
                schema_df = pd.read_sql_query(f"PRAGMA table_info([{chosen}]);", conn)
                st.dataframe(schema_df, use_container_width=True)
            except Exception as e:
                st.error(f"Erro ao obter schema: {e}")
    conn.close()
else:
    st.info("Crie o banco carregando arquivos.")

# ---------- Agente ----------
# ============= Agente NL → SQL (com extração segura de SQL) =============
st.subheader("🤖 Faça sua pergunta em Português")
prompt = st.text_input(
    "Exemplos: 'Qual o total de faturamento por mês?', 'Quais os 10 produtos mais vendidos?'"
)

if prompt:
    if not api_key or not model_name or not base_url:
        st.error("Defina `LLM_API_KEY`, `LLM_MODEL_NAME` e `LLM_BASE_URL` no .env para usar o agente.")
    else:
        database_uri = f"sqlite:///{db_name}"
        db = SQLDatabase.from_uri(database_uri)

        llm = ChatOpenAI(
            api_key=api_key,
            model=model_name,
            base_url=base_url,
            temperature=0,
            verbose=True,
        )

        CUSTOM_PREFIX = """Você é um gerador de SQL para SQLite.
Regras:
- Responda SOMENTE com SQL cru (apenas SELECT), sem explicações, sem markdown, sem cercas ```sql.
- Use os nomes de tabelas e colunas exatamente como existem no banco.
- Se precisar agregar, use SUM/COUNT e agrupe corretamente.
- Se a pergunta for ambígua, faça a melhor suposição razoável e gere o SELECT assim mesmo.
"""
           
        agente = create_sql_agent(
            llm,
            db=db,
            agent_type="tool-calling",
            verbose=True,
            prefix=CUSTOM_PREFIX            
        )

        import re, sqlite3

        # 1) Pedimos só o SQL cru (mas se vier texto, vamos higienizar)
        raw = agente.invoke(
            f"Pergunta: {prompt}\n"
            "Gere APENAS a consulta SQL para SQLite. Somente o SELECT; nada de texto extra."
        )
        response_text = (raw.get("output") or "").strip()

        # 2) Extrair somente o SQL:
        #    - se vier bloco ```sql ... ```, pega só o conteúdo
        #    - se vier texto + SQL, captura a partir do primeiro SELECT
        m_code = re.search(r"```sql\s*([\s\S]*?)```", response_text, re.IGNORECASE)
        sql_text = (m_code.group(1) if m_code else response_text).strip()
        m_select = re.search(r"(?is)\bselect\b[\s\S]*", sql_text)
        sql_text = (m_select.group(0) if m_select else sql_text).strip()
        if not sql_text.lower().lstrip().startswith("select"):
            raise ValueError("O modelo não retornou um SELECT. Recebido: " + response_text[:160])
        if not sql_text.rstrip().endswith(";"):
            sql_text += ";"

        st.markdown("**🔍 Consulta SQL gerada (pós-limpeza):**")
        st.code(sql_text, language="sql")

        # 3) Executar com SQLite e exibir resultado
        try:
            conn = sqlite3.connect(db_name)
            df_result = pd.read_sql_query(sql_text, conn)
            conn.close()

            if len(df_result) > 0:
                st.success("✅ Resultado da consulta:")
                st.dataframe(df_result, use_container_width=True)
            else:
                st.warning("A consulta foi executada, mas não retornou linhas.")
        except Exception as e:
            st.error(f"Erro ao executar a consulta SQL: {e}")

# ---------- SQL manual ----------
st.markdown("---")
st.subheader("🧪 (Opcional) Executar SQL manualmente")
sql_manual = st.text_area("Digite um SELECT para testar diretamente no SQLite", value="", height=120, placeholder="SELECT * FROM minha_tabela LIMIT 20;")
if st.button("Executar SQL") and sql_manual.strip():
    try:
        conn = sqlite3.connect(db_name)
        df = pd.read_sql_query(sql_manual, conn)
        conn.close()
        st.dataframe(df, use_container_width=True)
    except Exception as e:
        st.error(f"Erro ao executar o SQL: {e}")
