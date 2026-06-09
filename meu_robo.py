import os
import re
import sys  # Importado para capturar a sessão via linha de comando
import asyncio
from datetime import datetime
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

# --- CONFIGURAÇÕES DE ARQUIVOS E SESSÕES ---
INFO_MERCADO = "Mercado Multimix - Rua Marechal Deodoro centro Petrópolis - RJ"
BASE_URL = "https://www.emporiomultimix.com.br"
MAX_CONCURRENT_TASKS = 2

# CONFIGURAÇÃO DE BLOCO (Salvar a cada X produtos para não perder progresso)
TAMANHO_BLOCO_SALVAMENTO = 50
bloco_acumulador = []
lock_banco = asyncio.Lock()  # Garante que duas abas não tentem limpar a lista ao mesmo tempo
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
    try:
        parte_final = url.split('/')[-1]
        nome_limpo = parte_final.split('?')[0]
        nome_amigavel = nome_limpo.replace('-', ' ').title()
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
    """Função interna para descarregar o bloco atual no banco de dados"""
    global bloco_acumulador, contador_salvos
    if not bloco_acumulador:
        return

    async with lock_banco:
        try:
            # Envia o lote atual de dados
            supabase.table("historico_precos").insert(bloco_acumulador).execute()
            contador_salvos += len(bloco_acumulador)
            print(f"💾 [Supabase] {len(bloco_acumulador)} produtos salvos em tempo real! (Total gravado: {contador_salvos})")
            bloco_acumulador = []  # Limpa o bloco com sucesso
        except Exception as e:
            print(f"❌ Erro ao salvar bloco intermediário no Supabase: {e}")
            # Em caso de falha de conexão, mantemos o bloco para tentar na próxima rodada

async def raspar_produto_individual(sem, browser, item, idx, total_itens):
    """Roda de forma assíncrona, raspa e já gerencia o salvamento em tempo real"""
    global bloco_acumulador
    async with sem:
        url = item["url"]
        nome = item["nome"]
        
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        page.set_default_timeout(35000)
        
        try:
            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)
            
            try:
                tag_h1 = page.locator("h1").first
                if await tag_h1.is_visible():
                    nome_real = await tag_h1.inner_text()
                    nome_real = nome_real.strip()
                    if nome_real:
                        nome = nome_real
            except:
                pass

            preco_txt = "R$ 0,00"
            try:
                elemento_preco = page.locator("text=R$").first
                texto_interno = await elemento_preco.inner_text()
                preco_txt = texto_interno.strip().split('\n')[0]
            except: 
                pass

            valor = extrair_valor_numerico(preco_txt)
            print(f"[{idx}/{total_itens}] Coletado: {nome[:40]:<40} | {preco_txt}")
            
            dados_produto = {
                "mercado": f"{INFO_MERCADO} (Sessão)",
                "produto": nome,
                "preco_texto": preco_txt,
                "valor_numerico": valor,
                "url_produto": url
            }

            # Alimenta o bloco acumulador
            bloco_acumulador.append(dados_produto)

            # Se atingiu a meta do bloco (ex: 50 itens), dispara o salvamento assíncrono
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
        print("⚠️ Nenhum produto para processar.")
        return

    total_itens = len(itens_para_rodar)
    
    print(f"\n🚀 {INFO_MERCADO} (Modo Assíncrono com Carga em Tempo Real)")
    print(f"Alvo: {nome_arquivo} | Total de itens: {total_itens}")
    print(f"Tarefas simultâneas: {MAX_CONCURRENT_TASKS}")
    print("-" * 60)

    sem = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        tarefas = [
            raspar_produto_individual(sem, browser, item, idx, total_itens)
            for idx, item in enumerate(itens_para_rodar, start=1)
        ]
        
        # O gather continuará rodando a esteira de páginas
        await asyncio.gather(*tarefas)
        await browser.close()
        
    # --- LIMPEZA FINAL ---
    # Ao sair do loop, se sobrou algum produto no bloco (ex: os últimos 12 itens), salva eles
    if bloco_acumulador:
        print("\n📦 Salvando os últimos itens restantes no acumulador...")
        await enviar_bloco_para_supabase()
        
    print(f"\n🎉 Processo Concluído! Total Geral Gravado no Supabase: {contador_salvos} itens.")

if __name__ == "__main__":
    # REGRA DE CATEGORIA DINÂMICA:
    # Se você rodar: python meu_robo.py mercearia
    # Ele vai procurar o arquivo: links_mercearia.txt
    # Se rodar sem nada, o padrão é o arquivo antigo: links_multimix.txt
    
    if len(sys.argv) > 1:
        categoria = sys.argv[1].strip().lower()
        arquivo_alvo = f"links_{categoria}.txt"
        print(f"📂 Categoria selecionada via argumento: {categoria.upper()}")
    else:
        arquivo_alvo = "links_multimix.txt"
        print("📂 Nenhuma categoria enviada. Rodando arquivo completo padrão.")

    asyncio.run(realizar_raspagem_async(arquivo_alvo))
