import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
import hashlib
from datetime import datetime, timedelta
import time
import yfinance as yf
import matplotlib.pyplot as plt

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
            text-align: center;
            padding: 8px;
            font-size: 10px;
        }
        </style>
        <div class="footer">
            <p>App construído por @fthec | Contato: fernandoalexthec@gmail.com</p>
            <p>Chave pix:11982170425</p>
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

        # Exibir alerta de cheque especial
        if balance < 0:
            overdraft_amount = abs(balance)
            overdraft_interest = 0.08
            interest_amount = overdraft_amount * overdraft_interest
            st.error(f"Alerta: Você está no cheque especial! Juros de 8% ao mês serão aplicados. "
                     f"Saldo: {format_currency(balance)}. Juros futuros: {format_currency(interest_amount)} por mês.")

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
        submit_button = st.form_submit_button("Adicionar")

    if submit_button:
        add_financial_data(username, date, description, amount, type, payment_method, installments, necessity)
        st.success("Dados adicionados com sucesso!")

    # Adiciona o campo de upload de Excel
    uploaded_file = st.file_uploader("Escolha uma planilha Excel", type=["xlsx"])
    if uploaded_file is not None:
        df = upload_excel(uploaded_file)
        if df is not None:
            st.dataframe(df)  # Exibe os dados carregados

    add_footer()

def financial_data_page():
    st.title('Dados Financeiros')

    username = st.session_state['username']

    financial_data = get_financial_data(username)
    if len(financial_data) == 0:
        st.warning('Nenhum dado financeiro disponível.')
        return

    st.subheader('Dados Financeiros')
    df = pd.DataFrame(financial_data, columns=['id', 'Data', 'Descrição', 'Quantia', 'Tipo', 'Método de Pagamento', 'Parcelas', 'Necessidade'])
    st.table(df.drop(columns=['id']))

    display_major_expenses(username)
    alert_overdraft_and_credit(username)

    add_footer()

def remove_data_page():
    st.title("Remover Dados Financeiros")

    username = st.session_state['username']

    financial_data = get_financial_data(username)
    if len(financial_data) == 0:
        st.warning('Nenhum dado financeiro disponível para remoção.')
        return

    st.subheader('Selecione os dados para remover')
    df = pd.DataFrame(financial_data, columns=['id', 'Data', 'Descrição', 'Quantia', 'Tipo', 'Método de Pagamento', 'Parcelas', 'Necessidade'])
    df = df.drop(columns=['id'])  # Remove a coluna 'id' para exibição
    selected_rows = st.multiselect('Escolha os dados a serem removidos', df.index, format_func=lambda x: f"{df.loc[x, 'Descrição']} - {format_currency(df.loc[x, 'Quantia'])}")

    if st.button('Remover selecionados'):
        if selected_rows:
            ids_to_remove = [financial_data[i][0] for i in selected_rows]
            remove_financial_data(ids_to_remove)
            st.success(f'Dados removidos com sucesso!')
            st.stop()  # Interrompe a execução para evitar a continuação do código, o que efetivamente recarrega a página.
        else:
            st.warning("Selecione ao menos um dado para remover.")

    add_footer()

def analysis_page():
    st.title("Análises e Gráficos")
    st.write("Aqui você pode visualizar gráficos e análises financeiras.")

    st.subheader("Análise financeira")
    df_example = pd.DataFrame({
        'Data': pd.date_range(start='2024-08-01', periods=100),
        'Valor': np.random.randn(100).cumsum()
    }).set_index('Data')
    
    fig, ax = plt.subplots()
    ax.plot(df_example.index, df_example['Valor'])
    ax.set_title("Gastos")
    ax.set_xlabel("Data")
    ax.set_ylabel("Valor")
    ax.grid(color='gray', linestyle='--', linewidth=0.5)
    ax.set_facecolor('black')
    fig.patch.set_facecolor('black')
    ax.tick_params(axis='both', colors='white')
    ax.xaxis.label.set_color('white')
    ax.yaxis.label.set_color('white')
    ax.title.set_color('white')
    
    st.pyplot(fig)

    st.subheader('Evolução do Bitcoin, Ethereum, IBOVESPA e NASDAQ')
    
    end_date = datetime.today()
    start_date = end_date - timedelta(days=180)
    
    symbols = {'Bitcoin': 'BTC-USD', 'Ethereum': 'ETH-USD', 'IBOVESPA': '^BVSP', 'NASDAQ': '^IXIC'}
    data = {}
    
    for name, symbol in symbols.items():
        data[name] = yf.download(symbol, start=start_date, end=end_date)
    
    for name, df in data.items():
        fig, ax = plt.subplots()
        ax.plot(df.index, df['Close'])
        ax.set_title(f'Evolução do {name}')
        ax.set_xlabel('Data')
        ax.set_ylabel('Preço de Fechamento')
        ax.grid(color='gray', linestyle='--', linewidth=0.5)
        ax.set_facecolor('black')
        fig.patch.set_facecolor('black')
        ax.tick_params(axis='both', colors='white')
        ax.xaxis.label.set_color('white')
        ax.yaxis.label.set_color('white')
        ax.title.set_color('white')
        
        st.pyplot(fig)

    st.subheader('Sugestões de Compra')
    for name, df in data.items():
        current_price = df['Close'].iloc[-1]
        st.write(f'Preço atual do {name}: {format_currency(current_price)}')
        if current_price < df['Close'].mean():
            st.write(f'Sugestão: Pode ser uma boa hora para comprar {name}.')
        else:
            st.write(f'Sugestão: Espere uma possível queda no preço de {name} antes de comprar.')

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

# Inicializar a aplicação
if __name__ == '__main__':
    if 'username' not in st.session_state:
        st.session_state['username'] = None
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False

    create_database()
    home()
