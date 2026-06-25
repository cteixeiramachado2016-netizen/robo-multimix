import os
import uuid
from supabase import create_client, Client
import mercadopago

# ==========================================
# 1. CONFIGURAÇÃO DAS CREDENCIAIS (GITHUB SECRETS)
# ==========================================
# Supabase
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

# Mercado Pago (Lembre-se de adicionar este Secret no GitHub também!)
MERCADO_PAGO_TOKEN = os.environ.get("MERCADO_PAGO_ACCESS_TOKEN")

# Inicializa os clientes
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
sdk = mercadopago.SDK(MERCADO_PAGO_TOKEN)

# ==========================================
# 2. FUNÇÃO PARA GERAR PIX E SALVAR NO BANCO
# ==========================================
def criar_pedido_pix(email_cliente: str, nome_cliente: str, sobrenome_cliente: str):
    # Gera um ID único para a transação no seu sistema
    id_pedido_interno = str(uuid.uuid4())
    
    # Dados da requisição para o Mercado Pago
    payment_data = {
        "transaction_amount": 15.00,
        "description": "Assinatura Club Help",
        "payment_method_id": "pix",
        "payer": {
            "email": email_cliente,
            "first_name": nome_cliente,
            "last_name": sobrenome_cliente,
        },
        # O external_reference liga o pagamento do Mercado Pago ao ID do seu banco
        "external_reference": id_pedido_interno 
    }

    try:
        # 1. Cria o pagamento no Mercado Pago
        payment_response = sdk.payment().create(payment_data)
        pagamento = payment_response["response"]
        
        # Extrai os dados necessários para o cliente pagar
        id_mercado_pago = pagamento["id"]
        qrcode_copia_cola = pagamento["point_of_interaction"]["transaction_data"]["qr_code"]
        qrcode_imagem_base64 = pagamento["point_of_interaction"]["transaction_data"]["qr_code_base64"]
        
        # 2. Prepara os dados para salvar na tabela 'transacoes_pesquisas' (ou sua tabela correspondente)
        dados_transacao = {
            "id": id_pedido_interno,
            "provedor_id": str(id_mercado_pago),
            "status": "pending",
            "valor": 15.00,
            "cliente_email": email_cliente,
            "qrcode_pix": qrcode_copia_cola,
            "criado_em": "now()" # O Supabase/PostgreSQL interpreta para salvar o timestamp atual
        }
        
        # 3. Insere o registro no Supabase
        # Ajuste o nome da tabela ('transacoes_pesquisas') se necessário
        supabase.table("transacoes_pesquisas").insert(dados_transacao).execute()
        
        print(f"✅ Pedido {id_pedido_interno} criado com sucesso!")
        return {
            "sucesso": True,
            "id_pedido": id_pedido_interno,
            "pix_copia_cola": qrcode_copia_cola,
            "pix_base64": qrcode_imagem_base64
        }

    except Exception as e:
        print(f"❌ Erro ao processar pedido: {e}")
        return {"sucesso": False, "erro": str(e)}

# ==========================================
# EXEMPLO DE EXECUÇÃO
# ==========================================
if __name__ == "__main__":
    # Teste de criação de pedido
    resultado = criar_pedido_pix(
        email_cliente="cliente_teste@email.com",
        nome_cliente="Fulano",
        sobrenome_cliente="de Tal"
    )
    
    if resultado["sucesso"]:
        print("\n--- DADOS PARA O CLIENTE ---")
        print(f"Código Copia e Cola: {resultado['pix_copia_cola']}\n")
