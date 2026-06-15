import streamlit as st
from supabase import create_client, Client
import os
from dotenv import load_dotenv

# 1. CONEXÃO COM O SUPABASE
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

@st.cache_resource
def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase: Client = init_supabase()

st.set_page_config(page_title="Club Help - Painel do Assinante", page_icon="🛒", layout="wide")

# Inicialização de variáveis de sessão do Streamlit
if "user" not in st.session_state:
    st.session_state.user = None
if "lista_ativa_id" not in st.session_state:
    st.session_state.lista_ativa_id = None

# Funções de Autenticação
def fazer_login(email, password):
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        st.session_state.user = res.user
        st.success("Login realizado com sucesso!")
        st.rerun()
    except Exception as e:
        st.error("Erro ao autenticar: Verifique seu e-mail e senha.")

def fazer_logout():
    supabase.auth.sign_out()
    st.session_state.user = None
    st.session_state.lista_ativa_id = None
    st.rerun()

# =======================================================
# TELA DE LOGIN
# =======================================================
if st.session_state.user is None:
    st.title("🏆 Club Help")
    st.subheader("Painel do Assinante - Economia Inteligente")
    with st.form("login_form"):
        email = st.text_input("E-mail cadastrado")
        senha = st.text_input("Senha", type="password")
        if st.form_submit_button("Entrar no Painel"):
            fazer_login(email, senha)

# =======================================================
# PAINEL DO ASSINANTE (LOGADO)
# =======================================================
else:
    # Barra Superior
    col_user, col_out = st.columns([8, 2])
    with col_user:
        st.write(f"Conectado como: **{st.session_state.user.email}**")
    with col_out:
        if st.button("Sair / Logout"):
            fazer_logout()

    st.title("🛒 Monte sua Lista & Compare Preços")
    
    # ---------------------------------------------------
    # FLUXO 1: GERENCIAR OU CRIAR LISTA
    # ---------------------------------------------------
    st.subheader("1. Escolha ou Crie uma Lista")
    
    # AJUSTE DE SEGURANÇA: Filtrando as listas apenas do usuário logado
    listas_query = supabase.table("listas").select("id, nome_lista").eq("user_id", st.session_state.user.id).execute()
    listas_existentes = listas_query.data
    
    col_lista1, col_lista2 = st.columns([5, 5])
    
    with col_lista1:
        if listas_existentes:
            opcoes_lista = {l["nome_lista"]: l["id"] for l in listas_existentes}
            lista_selecionada = st.selectbox("Suas Listas Salvas:", list(opcoes_lista.keys()))
            st.session_state.lista_ativa_id = opcoes_lista[lista_selecionada]
        else:
            st.warning("Você ainda não tem nenhuma lista criada.")
            st.session_state.lista_ativa_id = None
            
    with col_lista2:
        with st.form("nova_lista_form"):
            nome_nova_lista = st.text_input("Nome para uma Nova Lista (ex: Compras da Semana)")
            if st.form_submit_button("Criar Nova Lista"):
                if nome_nova_lista:
                    nova_l = supabase.table("listas").insert({
                        "user_id": st.session_state.user.id,
                        "nome_lista": nome_nova_lista
                    }).execute()
                    st.success(f"Lista '{nome_nova_lista}' criada!")
                    st.rerun()

    # ---------------------------------------------------
    # FLUXO 2: BUSCA DE PRODUTOS E ADIÇÃO
    # ---------------------------------------------------
    if st.session_state.lista_ativa_id:
        st.write("---")
        
        # Criamos duas colunas em layout largo: Esquerda para adicionar / Direita para ver o carrinho
        col_adicionar, col_carrinho = st.columns([4, 6])
        
        with col_adicionar:
            st.subheader("2. Adicione Produtos")
            busca_termo = st.text_input("Digite o nome do produto (Ex: Leite, Arroz):")
            
            if busca_termo:
                produtos_encontrados = supabase.table("historico_precos") \
                    .select("produto") \
                    .ilike("produto", f"%{busca_termo}%") \
                    .execute()
                
                nomes_produtos = list(set([p["produto"] for p in produtos_encontrados.data]))
                
                if nomes_produtos:
                    produto_escolhido = st.selectbox("Produtos encontrados no mercado:", nomes_produtos)
                    qtd = st.number_input("Quantidade:", min_value=1, value=1, step=1)
                    
                    if st.button("➕ Adicionar à Lista"):
                        ref_prod = supabase.table("historico_precos").select("id").eq("produto", produto_escolhido).limit(1).execute()
                        if ref_prod.data:
                            id_do_produto = ref_prod.data[0]["id"]
                            
                            supabase.table("itens_lista").insert({
                                "lista_id": st.session_state.lista_ativa_id,
                                "produto_id": id_do_produto,
                                "quantidade": qtd
                            }).execute()
                            st.success(f"{produto_escolhido} (x{qtd}) adicionado!")
                            st.rerun() # Recarrega a tela para atualizar o carrinho ao lado
                else:
                    st.error("Nenhum produto encontrado com esse nome.")

        # ---------------------------------------------------
        # FLUXO 3: CARRINHO ATUAL E CÁLCULO DE VALORES
        # ---------------------------------------------------
        with col_carrinho:
            st.subheader("📋 Itens na Lista Atual")
            
            # Faz o "Join" trazendo os itens da lista juntamente com o preço e mercado do histórico_precos
            itens_query = supabase.table("itens_lista") \
                .select("id, quantidade, historico_precos(produto, preco, mercado)") \
                .eq("lista_id", st.session_state.lista_ativa_id) \
                .execute()
            
            itens_na_lista = itens_query.data
            
            if itens_na_lista:
                total_geral = 0.0
                
                # Exibe cabeçalho da tabela de conferência
                for item in itens_na_lista:
                    info_produto = item.get("historico_precos", {})
                    nome_p = info_produto.get("produto", "Desconhecido")
                    preco_u = info_produto.get("preco", 0.0)
                    mercado = info_produto.get("mercado", "Não informado")
                    quantidade = item.get("quantidade", 1)
                    subtotal = preco_u * quantidade
                    total_geral += subtotal
                    
                    # Cria linhas de exibição com botão para remover item
                    col_item_nome, col_item_qtd, col_item_sub, col_item_del = st.columns([4, 2, 2, 2])
                    col_item_nome.write(f"**{nome_p}**\n_{mercado}_")
                    col_item_qtd.write(f"{quantidade}x R$ {preco_u:.2f}")
                    col_item_sub.write(f"R$ {subtotal:.2f}")
                    
                    if col_item_del.button("🗑️", key=f"del_{item['id']}"):
                        supabase.table("itens_lista").delete().eq("id", item["id"]).execute()
                        st.toast(f"Item removido.")
                        st.rerun()
                
                st.write("---")
                # Caixa de destaque com o valor total calculado
                st.metric(label="Valor Total Estimado do Carrinho", value=f"R$ {total_geral:.2f}")
                st.info("💡 Dica do Club Help: Esse valor considera as últimas coletas do seu robô em Petrópolis!")
                
            else:
                st.info("Sua lista selecionada está vazia. Busque produtos ao lado para preenchê-la.")
