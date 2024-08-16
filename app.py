import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
import hashlib
from datetime import datetime, timedelta
import time
import yfinance as yf
import matplotlib.pyplot as plt
import requests

# Funções de utilidade
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def format_currency(value):
    return f"R${value:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

# Funções de banco de dados
def create_database():
    conn = sqlite3.connect('finfusion.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS financial_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            date DATE NOT NULL,
            description TEXT,
            amount REAL NOT NULL,
            type TEXT NOT NULL,
            payment_method TEXT,
            installments INTEGER,
            necessity TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def upload_excel(file):
    try:
        df = pd.read_excel(file)
        return df
    except Exception as e:
        st.error(f"Erro ao carregar arquivo Excel: {e}")
        return None

def download_data(symbol, start_date, end_date):
    try:
        data = yf.download(symbol, start=start_date, end=end_date)
        return data
    except BrokenPipeError:
        time.sleep(5)  # Espera de 5 segundos
        data = yf.download(symbol, start=start_date, end=end_date)
        return data

def register_user(username, password):
    with sqlite3.connect('finfusion.db') as conn:
        c = conn.cursor()
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hash_password(password)))
        conn.commit()

def verify_password(username, password):
    with sqlite3.connect('finfusion.db') as conn:
        c = conn.cursor()
        c.execute("SELECT password FROM users WHERE username=?", (username,))
        stored_password = c.fetchone()
        return stored_password and stored_password[0] == hash_password(password)

def get_financial_data(username):
    try:
        with sqlite3.connect('finfusion.db') as conn:
            c = conn.cursor()
            c.execute("SELECT id, date, description, amount, type, payment_method, installments, necessity FROM financial_data WHERE username=?", (username,))
            data = c.fetchall()
        return data if data else []
    except sqlite3.Error as e:
        st.error(f"Erro ao conectar ao banco de dados: {e}")
        return []

def add_financial_data(username, date, description, amount, type, payment_method, installments, necessity):
    with sqlite3.connect('finfusion.db') as conn:
        c = conn.cursor()
        c.execute("INSERT INTO financial_data (username, date, description, amount, type, payment_method, installments, necessity) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (username, date, description, amount, type, payment_method, installments, necessity))
        conn.commit()

def remove_financial_data(ids):
    with sqlite3.connect('finfusion.db') as conn:
        c = conn.cursor()
        if ids:  # Verifica se a lista de IDs não está vazia
            c.executemany("DELETE FROM financial_data WHERE id=?", [(id,) for id in ids])
            conn.commit()
        else:
            st.warning("Nenhum dado selecionado para remoção.")

# Funções adicionais
def calculate_total_balance(username):
    """Calcula o saldo total com base nas receitas e despesas do usuário."""
    data = get_financial_data(username)
    total_income = sum(item[3] for item in data if item[4] == "Receita")
    total_expense = sum(item[3] for item in data if item[4] == "Despesa")
    return total_income - total_expense

def display_major_expenses(username):
    """Exibe uma tabela com os maiores gastos e os gastos não essenciais."""
    data = get_financial_data(username)
    if not data:
        st.warning('Nenhum dado financeiro disponível.')
        return

    df = pd.DataFrame(data, columns=['id', 'Data', 'Descrição', 'Quantia', 'Tipo', 'Método de Pagamento', 'Parcelas', 'Necessidade'])
    major_expenses = df[df['Tipo'] == 'Despesa'].sort_values(by='Quantia', ascending=False)
    st.subheader('Maiores Gastos')
    st.dataframe(major_expenses)

    non_essential_expenses = df[(df['Necessidade'] == 'Não essencial') & (df['Tipo'] == 'Despesa')]
    st.subheader('Gastos Não Essenciais')
    st.dataframe(non_essential_expenses)

def alert_overdraft_and_credit(username):
    """Exibe alertas para cheque especial e gastos excessivos no cartão de crédito."""
    balance = calculate_total_balance(username)
    if balance < 0:
        st.error(f"Alerta: Você está no cheque especial! Juros de 8% ao mês serão aplicados. Saldo: {format_currency(balance)}")

    data = get_financial_data(username)
    if not data:
        return

    df = pd.DataFrame(data, columns=['id', 'Data', 'Descrição', 'Quantia', 'Tipo', 'Método de Pagamento', 'Parcelas', 'Necessidade'])

    credit_card_expenses = df[(df['Tipo'] == 'Despesa') & (df['Método de Pagamento'] == 'Cartão de Crédito')]['Quantia'].sum()
    credit_limit = 1000  # Defina o limite conforme necessário
    if credit_card_expenses > credit_limit:
        st.warning(f"Atenção: Seus gastos no cartão de crédito estão altos ({format_currency(credit_card_expenses)}). Limite sugerido: {format_currency(credit_limit)}.")

# Função para adicionar o footer
def add_footer():
    st.markdown(
        """
        <style>
        .footer {
            position: fixed;
            bottom: 0;
            width: 100%;
            background-color: #0000FF;
            color: white;
            text-align: left;
            padding: 2px; /* Ajuste da altura */
            font-size: 12px;
        }
        </style>
        <div class="footer">
            <p>App construído por @fthec | Contato: fernandoalexthec@gmail.com | Chave Pix: 11982170425</p>
        </div>
        """,
        unsafe_allow_html=True
    )

# Funções das páginas
def home():
    create_database()  # Garantir que o banco de dados existe
    st.title('FinFusion - Controle Financeiro')

    if 'logged_in' in st.session_state and st.session_state['logged_in']:
        username = st.session_state['username']
        # Exibir saldo líquido
        balance = calculate_total_balance(username)
        st.subheader(f'Saldo Líquido: {format_currency(balance)}')

        # Exibir navegação lateral
        sidebar_navigation()
    else:
        # Formulário de login
        st.subheader('Login')
        username = st.text_input('Usuário')
        password = st.text_input('Senha', type='password')
        if st.button('Entrar'):
            if verify_password(username, password):
                st.session_state['username'] = username
                st.session_state['logged_in'] = True
                st.experimental_rerun()  # Recarrega a página após login bem-sucedido
            else:
                st.error('Nome de usuário ou senha incorretos.')
        
        # Formulário de registro
        st.subheader('Registrar')
        new_username = st.text_input('Novo Usuário')
        new_password = st.text_input('Nova Senha', type='password')
        if st.button('Registrar'):
            register_user(new_username, new_password)
            st.success('Usuário registrado com sucesso!')
            
    add_footer()

# Função para navegação do sidebar
def sidebar_navigation():
    st.sidebar.title("Navegação")
    page = st.sidebar.selectbox("Escolha uma página", ["Inserir Dados", "Dados Financeiros", "Remover Dados", "Análises e Gráficos"])

    if page == "Inserir Dados":
        insert_data_page()
    elif page == "Dados Financeiros":
        financial_data_page()
    elif page == "Remover Dados":
        remove_data_page()
    elif page == "Análises e Gráficos":
        analysis_page()

def insert_data_page():
    st.title("Inserir Dados Financeiros")

    username = st.session_state['username']

    with st.form("data_entry_form"):
        date = st.date_input("Data")
        description = st.text_input("Descrição")
        amount = st.number_input("Quantia", min_value=0.0, format="%.2f")
        type = st.selectbox("Tipo", ["Receita", "Despesa"])
        payment_method = st.selectbox("Método de Pagamento", ["Dinheiro", "Cartão de Crédito", "Cartão de Débito", "Transferência"])
        installments = st.number_input("Parcelas", min_value=1, max_value=12, value=1)
        necessity = st.selectbox("Necessidade", ["Essencial", "Não essencial"])

        submitted = st.form_submit_button("Adicionar Dados")
        if submitted:
            add_financial_data(username, date, description, amount, type, payment_method, installments, necessity)
            st.success("Dados adicionados com sucesso!")

def financial_data_page():
    st.title("Dados Financeiros")

    username = st.session_state['username']
    data = get_financial_data(username)
    if data:
        df = pd.DataFrame(data, columns=["ID", "Data", "Descrição", "Quantia", "Tipo", "Método de Pagamento", "Parcelas", "Necessidade"])
        st.dataframe(df)
    else:
        st.warning("Nenhum dado financeiro disponível.")

def remove_data_page():
    st.title("Remover Dados Financeiros")

    username = st.session_state['username']
    data = get_financial_data(username)

    if data:
        df = pd.DataFrame(data, columns=["ID", "Data", "Descrição", "Quantia", "Tipo", "Método de Pagamento", "Parcelas", "Necessidade"])
        st.dataframe(df)

        ids_to_remove = st.multiselect("Selecione os IDs para remover", df["ID"].tolist())
        if st.button("Remover Dados"):
            remove_financial_data(ids_to_remove)
            st.success("Dados removidos com sucesso!")
            st.experimental_rerun()
    else:
        st.warning("Nenhum dado financeiro disponível.")

def analysis_page():
    st.title("Análises e Gráficos")

    username = st.session_state['username']
    display_major_expenses(username)
    alert_overdraft_and_credit(username)

# Inicia o app
home()
