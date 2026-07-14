import os
import re
import sys  # Captura a sessão via linha de comando
import asyncio
from datetime import datetime, timezone  # <--- Incluído timezone nativo para o formato do Supabase
import pytz  # Certifique-se de que está no seu requirements.txt ou setup do workflow
from playwright.async_api import async_playwright
from supabase import create_client, Client

# --- SUAS CREDENCIAIS DO SUPABASE REORGANIZADAS ---
SUPABASE_URL = "https://uqovffvxtskmbycldmwd.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVxb3ZmZnZ4dHNrbWJ5Y2xkbXdkIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MzkyNTgzMTEsImV4cCI6MjA1NDgzNDMxMX0.r7l72S69FidA2_D9_B98T5_vC_S-3vWreV-rGz6-RkQ"

# Inicializa o cliente do Supabase com as chaves injetadas diretamente
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- CONFIGURAÇÕES DE BANCO E RASPAGEM ---
MERCADO_ID = 1  # 1 = Centro (Os próximos distritos usarão IDs como 2, 3, 4, etc.)

BASE_URL = "https://www.emporiomultimix.com.br"
MAX_CONCURRENT_TASKS = 5  # <--- Quantidade de abas concorrentes (roda de 5 em 5)
PAUSA_ENTRE_SESSOES = 60  # <--- Pausa de 1 minuto (60s) entre o fim de uma sessão e o início de outra

# CONFIGURAÇÃO DE BLOCO (Salvar a cada 100 produtos em tempo real dentro da sessão)
TAMANHO_BLOCO_SALVAMENTO = 100
bloco_acumulador = []
lock_banco = asyncio.Lock()  # Garante segurança nas operações assíncronas
contador_salvos = 0

# Lista de todas as suas 19 sessões/categorias reais do Multimix Centro
SESSOES_PADRAO = [
    "acougue",
    "hortifruti",
    "bebidas_alcoolicas",
    "vinhos",
    "bebidas",
    "congelados",
    "limpeza",
    "mercearia_doce",
    "padaria_artesanal",
    "padaria_industrial",
    "petshop",
    "peixaria",
    "higiene",
    "lanchonete",
    "frios",
    "saudavel",
    "bazar",
    "laticinios_embutidos",
    "mercearia_salgada"
]

def extrair_valor_numerico(texto_preco):
    try:
        apenas_numeros = re.sub(r'[^\d,.]', '', texto_preco)
        if ',' in apenas_numeros:
            apenas_numeros = apenas_numeros.replace('.', '').replace(',', '.')
        return float(apenas_numeros)
    except:
        return 0.0

def extrair_nome_pelo_link(url):
    try:
        parte_final = url.split('/')[-1]
        nome_limpo = parte_final.split('?')[0]
        
        # Expressão regular para remover hífens seguidos de números no final da string
        nome_sem_id = re.sub(r'-\d+$', '', nome_limpo)
        
        nome_amigavel = nome_sem_id.replace('-', ' ').title()
        return nome_amigavel
    except:
        return "Produto Sem Nome"

def ler_dados_do_arquivo(nome_arquivo):
    produtos_links = []
    if not os.path.exists(nome_arquivo):
        print(f"❌ Erro: O arquivo '{nome_arquivo}' não foi encontrado!")
        return produtos_links
        
    print(f"✅ Arquivo de links encontrado: '{nome_arquivo}'")
    
    with open(nome_arquivo, 'r', encoding='utf-8') as f:
        for linha in f:
            linha = linha.strip()
            if linha and not linha.startswith("#"):
                if not linha.startswith("http"):
                    url_completa = BASE_URL + linha if linha.startswith("/") else BASE_URL + "/" + linha
                else:
                    url_completa = linha
                
                nome_produto = extrair_nome_pelo_link(url_completa)
                produtos_links.append({"nome": nome_produto, "url": url_completa})
                    
    urls_vistas = set()
    produtos_unicos = []
    for p in produtos_links:
        if p["url"] not in urls_vistas:
            urls_vistas.add(p["url"])
            produtos_unicos.append(p)

    return produtos_unicos

async def enviar_bloco_para_supabase():
    global bloco_acumulador, contador_salvos
    if not bloco_acumulador:
        return

    async with lock_banco:
        try:
            resposta = supabase.table("historico_precos").insert(bloco_acumulador).execute()
            
            if not resposta or not hasattr(resposta, 'data') or not resposta.data:
                print("⚠️ [Supabase] Atenção: O comando foi enviado, mas o banco retornou uma estrutura vazia.")
            else:
                contador_salvos += len(bloco_acumulador)
                print(f"💾 [Supabase] {len(bloco_acumulador)} produtos salvos! (Total gravado nesta rodada: {contador_salvos})")
            
            bloco_acumulador = []  # Limpa o bloco da memória
        except Exception as e:
            print(f"❌ ERRO CRÍTICO NO SUPABASE: {e}")
            sys.exit(1)

# Interceptador de requisições para bloquear mídias pesadas e rastreadores
async def bloquear_recursos_pesados(route):
    resource_type = route.request.resource_type
    if resource_type in ["image", "stylesheet", "font", "media"] or "google" in route.request.url or "facebook" in route.request.url:
        await route.abort()
    else:
        await route.continue_()

async def raspar_produto_individual(sem, context, item, idx, total_itens):
    """Roda de forma assíncrona, respeitando o limite de concorrência de 5 em 5"""
    global bloco_acumulador
    async with sem:
        url = item["url"]
        nome = item["nome"]
        
        page = await context.new_page()
        page.set_default_timeout(15000)
        await page.route("**/*", bloquear_recursos_pesados)
        
        try:
            response = await page.goto(url, wait_until="domcontentloaded")
            
            if response and response.status >= 500:
                print(f"⚠️ [{idx}/{total_itens}] Pulado: Erro {response.status} no servidor.")
                return

            tag_h1 = page.locator("h1").first
            try:
                await tag_h1.wait_for(state="visible", timeout=3000)
                nome_real = await tag_h1.inner_text()
                nome_real = nome_real.strip()
                if nome_real:
                    nome = nome_real
            except:
                pass

            nome = re.sub(r'\s*\d+$', '', nome).strip()

            preco_txt = "R$ 0,00"
            try:
                elemento_preco = page.locator(".precoPor, .price, strong:has-text('R$'), text=R$").first
                await elemento_preco.wait_for(state="visible", timeout=3000)
                texto_interno = await elemento_preco.inner_text()
                preco_txt = texto_interno.strip().split('\n')[0]
            except: 
                pass

            valor = extrair_valor_numerico(preco_txt)
            
            if valor == 0.0:
                print(f"⚠️ [{idx}/{total_itens}] Alerta Gôndola: {nome[:35]:<35} | Valor veio zerado.")
            else:
                print(f"[{idx}/{total_itens}] Coletado: {nome[:40]:<40} | {preco_txt}")
            
            dados_produto = {
                "produto": nome,
                "valor_numerico": valor,
                "mercado_id": MERCADO_ID,
                "data_robo": datetime.now(timezone.utc).isoformat()
            }

            bloco_acumulador.append(dados_produto)
            
            if len(bloco_acumulador) >= TAMANHO_BLOCO_SALVAMENTO:
                await enviar_bloco_para_supabase()
            
        except Exception as e:
            print(f"❌ [{idx}/{total_itens}] Erro no item {nome[:25]}... | {str(e)[:40]}")
        finally:
            await page.close()

async def realizar_raspagem_sessao(context, nome_arquivo):
    """Executa a raspagem completa de uma única sessão de arquivos de links"""
    global bloco_acumulador
    
    itens_para_rodar = ler_dados_do_arquivo(nome_arquivo)
    if not itens_para_rodar: 
        print(f"⚠️ Nenhum produto encontrado no arquivo: {nome_arquivo}")
        return False

    total_itens = len(itens_para_rodar)
    print(f"📂 Processando Sessão: {nome_arquivo} | Itens: {total_itens}")

    sem = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
    
    # Executa todos os itens da sessão usando concorrência assíncrona de 5 em 5
    tarefas = [
        raspar_produto_individual(sem, context, item, idx, total_itens)
        for idx, item in enumerate(itens_para_rodar, start=1)
    ]
    
    await asyncio.gather(*tarefas)
        
    # Garante que qualquer dado restante no acumulador seja salvo ao final desta sessão específica
    if bloco_acumulador:
        await enviar_bloco_para_supabase()
        
    return True

async def main():
    fuso_brasilia = pytz.timezone('America/Sao_Paulo')
    hora_inicio = datetime.now(fuso_brasilia).strftime('%d/%m/%Y %H:%M:%S')
    
    # 1. Determina quais arquivos de links processar
    if len(sys.argv) > 1:
        categoria = sys.argv[1].strip().lower()
        arquivos_fila = [f"links_{categoria}.txt"]
        modo_unico = True
        print(f"📂 Modo de Categoria Única Selecionado: {categoria.upper()}")
    else:
        arquivos_fila = [f"links_{cat}.txt" for cat in SESSOES_PADRAO]
        modo_unico = False
        print("📂 Modo Varredura Geral Selecionado (Múltiplas Categorias).")

    print("-" * 60)
    print(f"⏰ [INFO] O robô começou a rodar oficialmente em: {hora_inicio}")
    print(f"🚀 Varredura Iniciada (ID do Distrito Alvo: {MERCADO_ID})")
    print(f"Fila de Arquivos: {arquivos_fila}")
    print(f"Fluxo Concorrente: {MAX_CONCURRENT_TASKS} produtos por vez")
    print(f"Pausa entre Sessões: {PAUSA_ENTRE_SESSOES} segundos")
    print("-" * 60)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        total_arquivos = len(arquivos_fila)
        for index, arquivo in enumerate(arquivos_fila):
            # Executa a raspagem completa do arquivo atual da vez
            sucesso = await realizar_raspagem_sessao(context, arquivo)
            
            # Se não for o último arquivo e a raspagem da sessão foi bem sucedida, aplica a pausa estruturada
            if sucesso and not modo_unico and index < total_arquivos - 1:
                print(f"\n⏳ Sessão de '{arquivo}' finalizada com dados salvos.")
                print(f"💤 Entrando em repouso por {PAUSA_ENTRE_SESSOES} segundos antes de iniciar o próximo arquivo...")
                await asyncio.sleep(PAUSA_ENTRE_SESSOES)
                print("⏰ Fim da pausa! Retomando varredura...\n")
                
        await context.close()
        await browser.close()
        
    print(f"\n🎉 Varredura Geral Concluída! Total Novo Gravado no Supabase nesta rodada: {contador_salvos} itens.")

if __name__ == "__main__":
    asyncio.run(main())
