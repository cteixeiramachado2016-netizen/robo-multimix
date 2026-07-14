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

# --- CONFIGURAÇÕES DO SISTEMA ---
MERCADO_ID = 1  # Centro
ARQUIVO_FONTE = "links_multimix.txt"  # O arquivo gerado automaticamente pelo Explorador
BASE_URL = "https://www.emporiomultimix.com.br"

# --- CONTROLE DE CONCORRÊNCIA E LOTES ---
MAX_CONCURRENT_TASKS = 5  # Abre exatamente de 5 em 5 abas simultâneas
TAMANHO_LOTE = 100         # Processa e salva no Supabase em blocos de 100 em 100 produtos
PAUSA_ENTRE_LOTES = 60     # Pausa de 1 minuto (60s) após processar e salvar cada lote de 100

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

def ler_links_consolidados():
    produtos_links = []
    if not os.path.exists(ARQUIVO_FONTE):
        print(f"❌ Erro Crítico: O arquivo de entrada '{ARQUIVO_FONTE}' não foi encontrado!")
        sys.exit(1)
        
    with open(ARQUIVO_FONTE, 'r', encoding='utf-8') as f:
        for linha in f:
            linha = linha.strip()
            if linha and not linha.startswith("#"):
                if not linha.startswith("http"):
                    url_completa = BASE_URL + linha if linha.startswith("/") else BASE_URL + "/" + linha
                else:
                    url_completa = linha
                
                nome_produto = extrair_nome_pelo_link(url_completa)
                produtos_links.append({"nome": nome_produto, "url": url_completa})
                    
    # Remove duplicados mantendo a ordem
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
                # Localizadores robustos compatíveis com a estrutura do Multimix
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

async def main():
    fuso_brasilia = pytz.timezone('America/Sao_Paulo')
    hora_inicio = datetime.now(fuso_brasilia).strftime('%d/%m/%Y %H:%M:%S')

    # Lê todos os ~5.064 produtos do arquivo único links_multimix.txt
    todos_produtos = ler_links_consolidados()
    total_total = len(todos_produtos)

    print("-" * 60)
    print(f"⏰ Horário de início do Robô: {hora_inicio}")
    print(f"🚀 Total de links carregados de '{ARQUIVO_FONTE}': {total_total}")
    print(f"🔄 Concorrência ativa: {MAX_CONCURRENT_TASKS} abas simultâneas")
    print(f"📦 Tamanho do lote de salvamento: {TAMANHO_LOTE} itens")
    print(f"💤 Intervalo de segurança: {PAUSA_ENTRE_LOTES} segundos entre lotes")
    print("-" * 60)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        # Processa os produtos divididos em lotes de 100
        for i in range(0, total_total, TAMANHO_LOTE):
            lote_atual = todos_produtos[i : i + TAMANHO_LOTE]
            dados_lote = []
            
            print(f"\n📦 [Lote] Iniciando processamento do item {i+1} ao {min(i+TAMANHO_LOTE, total_total)}...")

            sem = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
            
            # Dispara concorrentemente de 5 em 5 abas os links do lote atual
            tarefas = [
                raspar_produto_individual(sem, context, item, i + idx, total_total, dados_lote)
                for idx, item in enumerate(lote_atual, start=1)
            ]
            await asyncio.gather(*tarefas)

            # Grava no banco de dados Supabase as novas colunas configuradas
            if dados_lote:
                try:
                    print(f"💾 Enviando bloco de {len(dados_lote)} produtos salvos para o Supabase...")
                    supabase.table("historico_precos").insert(dados_lote).execute()
                    print(f"✅ Gravação do lote concluída com sucesso no banco!")
                except Exception as e:
                    print(f"❌ Erro ao salvar lote no Supabase: {e}")

            # Aplica a pausa estruturada de 1 minuto, a menos que seja o último lote do arquivo
            if i + TAMANHO_LOTE < total_total:
                print(f"⏳ Pausa estruturada de {PAUSA_ENTRE_LOTES} segundos para respiro do servidor...")
                await asyncio.sleep(PAUSA_ENTRE_LOTES)
                print("⏰ Fim da pausa. Iniciando próximo lote...\n")

        await context.close()
        await browser.close()

    print("\n🎉 Varredura de preços concluída de ponta a ponta!")

if __name__ == "__main__":
    asyncio.run(main())
