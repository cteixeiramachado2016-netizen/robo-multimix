import os
import re
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from supabase import create_client, Client

# 1. Carrega as chaves do seu arquivo personalizado e organizado
load_dotenv("credenciais_supabase.env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
# Na nuvem com RLS ativo, usamos a SERVICE_KEY se disponível, ou a KEY padrão
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ Erro: Chaves do Supabase não encontradas no arquivo credenciais_supabase.env!")
    exit(1)

# Inicializa o cliente do Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- CONFIGURAÇÕES DE ARQUIVOS ---
FILE_LINKS = "links_multimix.txt"
INFO_MERCADO = "Mercado Multimix - Rua Marechal Deodoro centro Petrópolis - RJ (Geral)"
BASE_URL = "https://www.emporiomultimix.com.br"

# Controla quantos links abrem ao mesmo tempo (2 é perfeito para estabilidade)
MAX_CONCURRENT_TASKS = 2

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

def ler_dados_do_arquivo():
    produtos_links = []
    if not os.path.exists(FILE_LINKS):
        print(f"❌ Erro: O arquivo '{FILE_LINKS}' não foi encontrado!")
        return produtos_links
        
    print(f"✅ Arquivo de links encontrado: '{FILE_LINKS}'")
    
    with open(FILE_LINKS, 'r', encoding='utf-8') as f:
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

async def raspar_produto_individual(sem, browser, item, idx, total_itens):
    """Roda de forma assíncrona respeitando o limite do semáforo"""
    async with sem:
        url = item["url"]
        nome = item["nome"]
        
        # Cria um contexto isolado por aba (economiza muita memória)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        page.set_default_timeout(35000)
        
        try:
            await page.goto(url, wait_until="domcontentloaded")
            # Espera os elementos carregarem/estabilizarem
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
            
            return {
                "mercado": INFO_MERCADO,
                "produto": nome,
                "preco_texto": preco_txt,
                "valor_numerico": valor,
                "url_produto": url
            }
            
        except Exception as e:
            print(f"❌ [{idx}/{total_itens}] Erro no item {nome[:25]}... | {str(e)[:40]}")
            return None
        finally:
            await page.close()
            await context.close()

async def realizar_raspagem_async():
    itens_para_rodar = ler_dados_do_arquivo()
    if not itens_para_rodar: 
        print("⚠️ Nenhum produto para processar.")
        return

    total_itens = len(itens_para_rodar)
    
    print(f"\n🚀 {INFO_MERCADO} (Modo Assíncrono Nuvem + Supabase)")
    print(f"Total de itens para processar: {total_itens}")
    print(f"Tarefas simultâneas: {MAX_CONCURRENT_TASKS}")
    print("-" * 60)

    # O semáforo impede que o script abra mais do que 2 abas por vez
    sem = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        # Cria a lista de tarefas assíncronas
        tarefas = [
            raspar_produto_individual(sem, browser, item, idx, total_itens)
            for idx, item in enumerate(itens_para_rodar, start=1)
        ]
        
        # Executa todas em paralelo e aguarda os resultados
        resultados = await asyncio.gather(*tarefas)
        await browser.close()
        
    # Filtra os itens que falharam (retornaram None)
    dados_para_salvar = [r for r in resultados if r is not None]

    # --- SALVAR NO SUPABASE (BANCO DE DADOS NA NUVEM EM SÃO PAULO) ---
    if dados_para_salvar:
        print(f"\n💾 Enviando {len(dados_para_salvar)} dados coletados para o Supabase em São Paulo...")
        try:
            tamanho_bloco = 500
            for i in range(0, len(dados_para_salvar), tamanho_bloco):
                bloco = dados_para_salvar[i:i + tamanho_bloco]
                supabase.table("historico_precos").insert(bloco).execute()
                print(f"✅ Bloco de {len(bloco)} itens enviado com sucesso!")
                
            print("\n🎉 Todos os dados foram salvos na nuvem com sucesso!")
        except Exception as e:
            print(f"❌ Erro ao salvar dados no Supabase: {e}")
    else:
        print("\n⚠️ Nenhum dado válido foi coletado para salvar.")

if __name__ == "__main__":
    # Inicia o loop de eventos assíncronos do Python
    asyncio.run(realizar_raspagem_async())