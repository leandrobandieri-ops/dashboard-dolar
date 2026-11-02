import dash
from dash import dcc, html, Input, Output, State, dash_table
import plotly.graph_objects as go
import requests
import sqlite3
import pandas as pd
from datetime import datetime
import os

# ---------------------------------------------------------
# 1. Banco de Dados (SQLite)
# ---------------------------------------------------------
DB_FILE = "aportes.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS aportes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,
            usd_valor REAL NOT NULL,
            custo_brl REAL NOT NULL
        )
    ''')
    cursor.execute("SELECT COUNT(*) FROM aportes")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO aportes (data, usd_valor, custo_brl) VALUES (?, ?, ?)",
                       ("2026-10-01", 100.0, 580.0))
    conn.commit()
    conn.close()

def carregar_aportes():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT id, data as Data, usd_valor as USD, custo_brl as BRL FROM aportes", conn)
    conn.close()
    return df

def salvar_aporte(data, usd, brl):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO aportes (data, usd_valor, custo_brl) VALUES (?, ?, ?)", (data, usd, brl))
    conn.commit()
    conn.close()

init_db()

# ---------------------------------------------------------
# 2. APIs de Cotação
# ---------------------------------------------------------
def obter_cotacao_dolar():
    try:
        url = "https://economia.awesomeapi.com.br/last/USD-BRL"
        response = requests.get(url, timeout=5)
        data = response.json()
        return float(data["USDBRL"]["bid"])
    except Exception:
        return 5.44

def obter_ipca_acumulado():
    try:
        url = "https://api.sidra.ibge.gov.br/values/t/1737/n1/all/v/63/p/last%201"
        response = requests.get(url, timeout=5)
        data = response.json()
        return float(data[1]["V"]) / 100.0
    except Exception:
        return 0.0032

# ---------------------------------------------------------
# 3. App Dash & Servidor Gunicorn
# ---------------------------------------------------------
app = dash.Dash(__name__)
server = app.server  # <-- Linha crucial exigida pelo Render/Gunicorn

estilo_cartao = {
    'backgroundColor': '#1e293b',
    'padding': '20px',
    'borderRadius': '10px',
    'width': '30%',
    'textAlign': 'center',
    'boxShadow': '0 4px 6px rgba(0, 0, 0, 0.3)'
}

estilo_input = {
    'backgroundColor': '#0f172a',
    'color': 'white',
    'border': '1px solid #334155',
    'padding': '10px',
    'borderRadius': '6px',
    'marginBottom': '10px',
    'width': '100%'
}

app.layout = html.Div(style={'backgroundColor': '#0f172a', 'color': 'white', 'padding': '30px', 'fontFamily': 'Segoe UI, sans-serif', 'minHeight': '100vh'}, children=[
    
    html.H2("Dashboard de Investimentos - USD vs IPCA", style={'textAlign': 'center', 'marginBottom': '30px'}),
    
    html.Div(id='cards-container', style={'display': 'flex', 'justifyContent': 'space-between', 'marginBottom': '30px'}),
    
    html.Div(style={'display': 'flex', 'gap': '20px', 'marginBottom': '30px'}, children=[
        
        html.Div(style={'backgroundColor': '#1e293b', 'padding': '20px', 'borderRadius': '10px', 'width': '35%'}, children=[
            html.H3("Registrar Novo Aporte", style={'marginTop': '0', 'marginBottom': '20px'}),
            
            html.Label("Data do Aporte:"),
            dcc.Input(id='input-data', type='text', value=datetime.today().strftime('%Y-%m-%d'), style=estilo_input),
            
            html.Label("Valor Comprado (USD):"),
            dcc.Input(id='input-usd', type='number', value=100, style=estilo_input),
            
            html.Label("Custo Total Pago (BRL):"),
            dcc.Input(id='input-brl', type='number', value=580, style=estilo_input),
            
            html.Button("Salvar Aporte", id='btn-salvar', n_clicks=0, style={
                'backgroundColor': '#2563eb', 'color': 'white', 'border': 'none', 'padding': '12px',
                'borderRadius': '6px', 'cursor': 'pointer', 'width': '100%', 'fontWeight': 'bold', 'marginTop': '10px'
            }),
            html.Div(id='msg-status', style={'marginTop': '10px', 'color': '#4ade80', 'textAlign': 'center'})
        ]),
        
        html.Div(style={'backgroundColor': '#1e293b', 'padding': '20px', 'borderRadius': '10px', 'width': '65%'}, children=[
            html.H3("Histórico de Aportes Salvos", style={'marginTop': '0', 'marginBottom': '15px'}),
            dash_table.DataTable(
                id='tabela-historico',
                columns=[
                    {'name': 'ID', 'id': 'id'},
                    {'name': 'Data', 'id': 'Data'},
                    {'name': 'USD', 'id': 'USD'},
                    {'name': 'Custo (BRL)', 'id': 'BRL'}
                ],
                style_header={'backgroundColor': '#0f172a', 'color': 'white', 'fontWeight': 'bold'},
                style_cell={'backgroundColor': '#1e293b', 'color': 'white', 'textAlign': 'center', 'border': '1px solid #334155'},
                page_size=5
            )
        ])
    ]),
    
    dcc.Graph(id='grafico-desempenho')
])

# ---------------------------------------------------------
# 4. Callbacks
# ---------------------------------------------------------
@app.callback(
    [Output('tabela-historico', 'data'),
     Output('cards-container', 'children'),
     Output('grafico-desempenho', 'figure'),
     Output('msg-status', 'children')],
    [Input('btn-salvar', 'n_clicks')],
    [State('input-data', 'value'),
     State('input-usd', 'value'),
     State('input-brl', 'value')]
)
def atualizar_dashboard(n_clicks, data, usd, brl):
    msg = ""
    if n_clicks > 0 and usd and brl:
        salvar_aporte(data, float(usd), float(brl))
        msg = "Aporte salvo com sucesso!"
    
    df = carregar_aportes()
    dolar_atual = obter_cotacao_dolar()
    taxa_ipca = obter_ipca_acumulado()
    
    total_usd = df['USD'].sum()
    total_custo_brl = df['BRL'].sum()
    pm_efetivo = total_custo_brl / total_usd if total_usd > 0 else 0
    
    valor_atual_brl = total_usd * dolar_atual
    custo_corrigido_ipca = total_custo_brl * (1 + taxa_ipca)
    perda_real = valor_atual_brl - custo_corrigido_ipca
    
    cards = [
        html.Div([
            html.H4("Preço Médio Pago", style={'margin': '0 0 10px 0', 'color': '#94a3b8'}), 
            html.H2(f"R$ {pm_efetivo:.2f}", style={'margin': '0', 'color': '#f8fafc'})
        ], style=estilo_cartao),
        
        html.Div([
            html.H4("Dólar Atual (API)", style={'margin': '0 0 10px 0', 'color': '#94a3b8'}), 
            html.H2(f"R$ {dolar_atual:.2f}", style={'margin': '0', 'color': '#2a9d8f'})
        ], style=estilo_cartao),
        
        html.Div([
            html.H4("Resultado Real vs IPCA", style={'margin': '0 0 10px 0', 'color': '#94a3b8'}), 
            html.H2(f"R$ {perda_real:.2f}", style={'margin': '0', 'color': '#ef4444' if perda_real < 0 else '#2a9d8f'})
        ], style=estilo_cartao)
    ]
    
    valores = [total_custo_brl, custo_corrigido_ipca, valor_atual_brl]
    categorias = ['Custo Total Pago', 'Alvo IPCA', 'Valor Atual em Carteira']
    cores = ['#5e60ce', '#fb8500', '#2a9d8f']
    
    fig = go.Figure(data=[
        go.Bar(x=categorias, y=valores, marker_color=cores, text=[f"R$ {v:.2f}" for v in valores], textposition='auto')
    ])
    
    fig.update_layout(
        template='plotly_dark',
        title=f'Consolidado da Carteira ({total_usd:.2f} USD Investidos)',
        paper_bgcolor='#0f172a',
        plot_bgcolor='#0f172a',
        margin=dict(l=40, r=40, t=60, b=40),
        yaxis=dict(title='Valor (R$)')
    )
    
    return df.to_dict('records'), cards, fig, msg

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8050))
    app.run(host='0.0.0.0', port=port)
