import os
import re
import sys
import asyncio
from datetime import datetime, timezone
import pytz
from playwright.async_api import async_playwright
from supabase import create_client, Client

# --- SUAS CREDENCIAIS OFICIAIS DO SUPABASE ---
SUPABASE_URL = "https://uqovffvxtskmbycldmwd.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVxb3ZmZnZ4dHNrbWJ5Y2xkbXdkIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MzkyNTgzMTEsImV4cCI6MjA1NDgzNDMxMX0.r7l72S69FidA2_D9_B98T5_vC_S-3vWreV-rGz6-RkQ"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

MERCADO_ID = 1  # Centro
BASE_URL = "https://www.emporiomultimix.com.br"

# Controle de Fluxo solicitado por você
MAX_CONCURRENT_TASKS = 5  # <--- Abre exatamente de 5 em 5 abas simultâneas
PAUSA_ENTRE_SESSOES = 60  # <--- Pausa de 1 minuto (60s) entre cada arquivo de sessão

# Lista ordenada das suas 19 sessões reais
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

async def bloquear_recursos_pesados(route):
    resource_type = route.request.resource_type
    if resource_type in ["image", "stylesheet", "font", "media"] or "google" in route.request.url or "facebook" in route.request.url:
        await route.abort()
    else:
        await route.continue_()

async def raspar_produto_individual(sem, context, item, idx, total_itens, lista_acumuladora):
    """Executa a raspagem de um link respeitando o semáforo limite de 5 abas"""
    async with sem:
        url = item["url"]
        nome = item["nome"]
        
        page = await context.new_page()
        page.set_default_timeout(15000)
        await page.route("**/*", bloquear_recursos_pesados)
        
        try:
            response = await page.goto(url, wait_until="domcontentloaded")
            if response and response.status >= 500:
                print(f"⚠️ [{idx}/{total_itens}] Erro {response.status} no servidor.")
                return

            tag_h1 = page.locator("h1").first
            try:
                await tag_h1.wait_for(state="visible", timeout=3000)
                nome_real = await tag_h1.inner_text()
                if nome_real.strip():
                    nome = nome_real.strip()
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
            print(f"[{idx}/{total_itens}] Coletado: {nome[:35]:<35} | {preco_txt}")
            
            if valor > 0.0:
                lista_acumuladora.append({
                    "produto": nome,
                    "valor_numerico": valor,
                    "mercado_id": MERCADO_ID,
                    "data_robo": datetime.now(timezone.utc).isoformat()
                })
            
        except Exception as e:
            print(f"❌ [{idx}/{total_itens}] Erro no link: {nome[:20]}... | {str(e)[:40]}")
        finally:
            await page.close()

async def realizar_raspagem_sessao(context, nome_arquivo):
    """Processa a sessão inteira do arquivo e grava de uma vez no final da sessão"""
    itens_para_rodar = ler_dados_do_arquivo(nome_arquivo)
    if not itens_para_rodar:
        return False

    total_itens = len(itens_para_rodar)
    print(f"\n📂 Processando Sessão: {nome_arquivo} | {total_itens} links encontrados.")

    sem = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
    dados_sessao = []

    # Dispara a raspagem concorrente de 5 em 5 abas dentro da sessão atual
    tarefas = [
        raspar_produto_individual(sem, context, item, idx, total_itens, dados_sessao)
        for idx, item in enumerate(itens_para_rodar, start=1)
    ]
    await asyncio.gather(*tarefas)

    # Grava todos os dados coletados desta sessão no Supabase de uma vez só
    if dados_sessao:
        try:
            print(f"💾 Enviando {len(dados_sessao)} produtos de '{nome_arquivo}' para o Supabase...")
            supabase.table("historico_precos").insert(dados_sessao).execute()
            print(f"✅ Sessão '{nome_arquivo}' salva com sucesso no banco!")
        except Exception as e:
            print(f"❌ Erro ao salvar dados no Supabase: {e}")
            
    return True

async def main():
    fuso_brasilia = pytz.timezone('America/Sao_Paulo')
    hora_inicio = datetime.now(fuso_brasilia).strftime('%d/%m/%Y %H:%M:%S')

    if len(sys.argv) > 1:
        categoria = sys.argv[1].strip().lower()
        arquivos_fila = [f"links_{categoria}.txt"]
        modo_unico = True
        print(f"📂 Rodando categoria única de forma manual: {categoria.upper()}")
    else:
        arquivos_fila = [f"links_{cat}.txt" for cat in SESSOES_PADRAO]
        modo_unico = False
        print("📂 Iniciando varredura sequencial completa das 19 sessões...")

    print("-" * 60)
    print(f"⏰ Horário de início: {hora_inicio}")
    print(f"🔄 Concorrência ativa: {MAX_CONCURRENT_TASKS} abas simultâneas")
    print("-" * 60)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        total_arquivos = len(arquivos_fila)
        for index, arquivo in enumerate(arquivos_fila):
            # Executa a raspagem completa da sessão atual
            sucesso = await realizar_raspagem_sessao(context, arquivo)

            # Só aplica a pausa de 1 minuto se houver mais sessões para rodar na fila sequencial
            if sucesso and not modo_unico and index < total_arquivos - 1:
                print(f"⏳ Pausa estruturada: aguardando {PAUSA_ENTRE_SESSOES} segundos antes da próxima sessão...")
                await asyncio.sleep(PAUSA_ENTRE_SESSOES)
                print("⏰ Fim do intervalo. Retomando varredura...\n")

        await context.close()
        await browser.close()

    print("\n🎉 Varredura finalizada!")

if __name__ == "__main__":
    asyncio.run(main())
