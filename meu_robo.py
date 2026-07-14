import os
import re
import sys
import asyncio
from datetime import datetime, timezone
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from supabase import create_client, Client

# Carrega credenciais
load_dotenv("credenciais_supabase.env")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ Erro: Chaves do Supabase não encontradas!")
    exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

ARQUIVO_TESTE = "links_multimix_teste.txt"
BASE_URL = "https://www.emporiomultimix.com.br"

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
        return nome_amigavel if len(nome_amigavel.strip()) > 0 else "Produto Sem Nome"
    except:
        return "Produto Sem Nome"

def ler_links_teste():
    links = []
    if not os.path.exists(ARQUIVO_TESTE):
        print(f"❌ Erro: Arquivo {ARQUIVO_TESTE} não encontrado!")
        return links
    
    with open(ARQUIVO_TESTE, 'r', encoding='utf-8') as f:
        for java_line in f:
            java_line = java_line.strip()
            if java_line and not java_line.startswith("#"):
                if not java_line.startswith("http"):
                    url = BASE_URL + java_line if java_line.startswith("/") else BASE_URL + "/" + java_line
                else:
                    url = java_line
                links.append(url)
    return list(set(links))

async def testar_link(browser, url, idx, total):
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    page = await context.new_page()
    page.set_default_timeout(20000)
    
    resultado_salvar = None
    
    try:
        print(f"🔄 [{idx}/{total}] Acessando: {url}")
        await page.goto(url, wait_until="load")
        
        nome_produto = extrair_nome_pelo_link(url)
        preco_detectado = "R$ 0,00"
        valor_numerico = 0.0
        
        try:
            elemento = page.locator("span:has-text('R$')").first
            await elemento.wait_for(state="visible", timeout=5000)
            texto = await elemento.inner_text()
            texto_limpo = texto.strip().split('\n')[0]
            
            temp_valor = extrair_valor_numerico(texto_limpo)
            if temp_valor > 0.0:
                preco_detectado = texto_limpo
                valor_numerico = temp_valor
        except Exception as e:
            print(f"⚠️ Falha ao ler preço no link {url}: {str(e)[:40]}")

        resultado_salvar = {
            "produto": nome_produto,
            "valor_numerico": valor_numerico,
            "mercado_id": "1", # Mercado Centro
            "data_robo": datetime.now(timezone.utc).isoformat()
        }
        
        if valor_numerico > 0.0:
            print(f"✅ SUCESSO: '{nome_produto[:30]}' | Preço: {preco_detectado}")
        else:
            print(f"❌ FALHA: Não foi possível extrair preço para {url}")
            
    except Exception as e:
        print(f"💥 Erro crítico ao testar URL: {str(e)[:50]}")
    finally:
        await page.close()
        await context.close()
        
    return resultado_salvar

async def main():
    links = ler_links_teste()
    if not links:
        print("⚠️ Nenhum link de teste encontrado no arquivo.")
        return
        
    print(f"🧪 Iniciando testes de controle para {len(links)} URLs...")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        resultados = []
        
        for idx, url in enumerate(links, start=1):
            res = await testar_link(browser, url, idx, len(links))
            if res: # Salvamos mesmo se o preço for 0 para registrar a falha (assim como o de teste faz)
                resultados.append(res)
                
        await browser.close()
        
        # Envia resultados direto para o Supabase (Correção aplicada aqui)
        if resultados:
            try:
                # Mudança para a chamada síncrona direta que funciona de forma estável
                supabase.table("teste_seletores_log").insert(resultados).execute()
                print(f"💾 {len(resultados)} relatórios gravados no banco com sucesso!")
            except Exception as e:
                print(f"❌ Erro ao salvar logs no Supabase: {e}")

if __name__ == "__main__":
    asyncio.run(main())
