import os
import re
import sys  # Captura a sessão via linha de comando
import asyncio
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from supabase import create_client, Client

# 1. Carrega as chaves do seu arquivo personalizado e organizado
load_dotenv("credenciais_supabase.env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ Erro: Chaves do Supabase não encontradas!")
    exit(1)

# Inicializa o cliente do Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- CONFIGURAÇÕES DE BANCO E RASPAGEM ---
MERCADO_ID = 1  

BASE_URL = "https://www.emporiomultimix.com.br"
MAX_CONCURRENT_TASKS = 2

# CONFIGURAÇÃO DE BLOCO (Salvar a cada 100 produtos em tempo real)
TAMANHO_BLOCO_SALVAMENTO = 100
bloco_acumulador = []
lock_banco = asyncio.Lock()  # Garante segurança nas operações assíncronas
contador_salvos = 0

def extrair_valor_numerico(texto_preco):
    try:
        apenas_numeros = re.sub(r'[^\d,.]', '', texto_preco)
        if ',' in apenas_numeros:
            apenas_numeros = apenas_numeros.replace('.', '').replace(',', '.')
        return float(apenas_numeros)
    except:
        return 0.0

def extrair_nome_pelo_link(url):
    """
    Remove parâmetros de busca (?...) e limpa o ID numérico final do e-commerce (ex: -131366)
    para que o nome fique amigável e limpo no banco de dados.
    """
    try:
        parte_final = url.split('/')[-1]
        nome_limpo = parte_final.split('?')[0]
        
        # Expressão regular para remover hífens seguidos de números no final da string (o ID do mercado)
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
            link = linha.strip()
            if link and not link.startswith("#"):
                if not link.startswith("http"):
                    url_completa = BASE_URL + link if link.startswith("/") else BASE_URL + "/" + link
                else:
                    url_completa = link
                
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
    """Função interna para descarregar o bloco atual no banco de dados com estrutura limpa"""
    global bloco_acumulador, contador_salvos
    if not bloco_acumulador:
        return

    async with lock_banco:
        try:
            resposta = supabase.table("historico_precos").insert(bloco_acumulador).execute()
            
            if not resposta or not hasattr(resposta, 'data') or not resposta.data:
                print("⚠️ [Supabase] Atenção: O comando foi enviado, mas o banco retornou uma estrutura vazia.")
                print("👉 Verifique as políticas de RLS ou se a tabela possui restrições.")
            else:
                contador_salvos += len(bloco_acumulador)
                print(f"💾 [Supabase] {len(bloco_acumulador)} produtos salvos! (Total gravado nesta rodada: {contador_salvos})")
            
            bloco_acumulador = []  # Limpa o bloco da memória
        except Exception as e:
            print(f"❌ ERRO CRÍTICO NO SUPABASE: {e}")
            print("🛑 Interrompendo execução para diagnóstico do erro acima.")
            sys.exit(1)

async def raspar_produto_individual(sem, browser, item, idx, total_itens):
    """Roda de forma assíncrona, raspa e joga os dados no acumulador"""
    global bloco_acumulador
    async with sem:
        url = item["url"]
        nome = item["nome"]
        
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        # Tempo limite estendido para garantir o carregamento de scripts pesados do mercado
        page.set_default_timeout(25000)
        
        try:
            # Mudado de domcontentloaded para 'load' para garantir que os scripts de preço rodem antes da leitura
            response = await page.goto(url, wait_until="load")
            
            if response and response.status >= 500:
                print(f"⚠️ [{idx}/{total_itens}] Pulado: Erro {response.status} no servidor.")
                return

            # Captura o nome real de dentro da tag H1 do site
            tag_h1 = page.locator("h1").first
            try:
                await tag_h1.wait_for(state="visible", timeout=5000)
                nome_real = await tag_h1.inner_text()
                nome_real = nome_real.strip()
                if nome_real:
                    nome = nome_real
            except:
                pass

            # Limpa o nome capturado caso o H1 também traga o ID
            nome = re.sub(r'\s*\d+$', '', nome).strip()

            preco_txt = "R$ 0,00"
            try:
                # Seletor direcionado: tenta pegar a classe específica do preço ou seletor de forte
                # Isso impede que ele capture R$ falsos em banners ou cabeçalhos
                elemento_preco = page.locator(".precoPor, .price, strong:has-text('R$'), text=R$").first
                await elemento_preco.wait_for(state="visible", timeout=5000)
                texto_interno = await elemento_preco.inner_text()
                preco_txt = texto_interno.strip().split('\n')[0]
            except: 
                pass

            valor = extrair_valor_numerico(preco_txt)
            
            # Se capturar como 0.00, loga como um aviso para acompanhamento na gôndola
            if valor == 0.0:
                print(f"⚠️ [{idx}/{total_itens}] Alerta Gôndola: {nome[:35]:<35} | Valor veio zerado.")
            else:
                print(f"[{idx}/{total_itens}] Coletado: {nome[:40]:<40} | {preco_txt}")
            
            dados_produto = {
                "produto": nome,
                "valor_numerico": valor,
                "mercado_id": MERCADO_ID  
            }

            bloco_acumulador.append(dados_produto)
            
            if len(bloco_acumulador) >= TAMANHO_BLOCO_SALVAMENTO:
                await enviar_bloco_para_supabase()
            
        except Exception as e:
            print(f"❌ [{idx}/{total_itens}] Erro no item {nome[:25]}... | {str(e)[:40]}")
        finally:
            await page.close()
            await context.close()

async def realizar_raspagem_async(nome_arquivo):
    itens_para_rodar = ler_dados_do_arquivo(nome_arquivo)
    if not itens_para_rodar: 
        print("⚠️ Nenhum produto encontrado no arquivo.")
        return

    total_itens = len(itens_para_rodar)

    print(f"\n🚀 Iniciando Varredura Otimizada (ID do Mercado Alvo: {MERCADO_ID})")
    print(f"Alvo: {nome_arquivo} | Itens para processar: {total_itens}")
    print(f"Tarefas simultâneas: {MAX_CONCURRENT_TASKS}")
    print(f"Salvamento configurado a cada: {TAMANHO_BLOCO_SALVAMENTO} itens")
    print("-" * 60)

    sem = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        tarefas = [
            raspar_produto_individual(sem, browser, item, idx, total_itens)
            for idx, item in enumerate(itens_para_rodar, start=1)
        ]
        
        await asyncio.gather(*tarefas)
            
        if bloco_acumulador:
            await enviar_bloco_para_supabase()
                
        await browser.close()
        
    print(f"\n🎉 Processo Concluído! Total Novo Gravado no Supabase: {contador_salvos} itens.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        categoria = sys.argv[1].strip().lower()
        arquivo_alvo = f"links_{categoria}.txt"
        print(f"📂 Categoria selecionada via argumento: {categoria.upper()}")
    else:
        arquivo_alvo = "links_multimix.txt"
        print("📂 Nenhuma categoria enviada. Rodando arquivo completo padrão.")

    asyncio.run(realizar_raspagem_async(arquivo_alvo))
