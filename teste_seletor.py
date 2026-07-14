import os
import re
import asyncio
from datetime import datetime, timezone
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from supabase import create_client, Client

# Carrega credenciais do arquivo temporário do GitHub Actions
load_dotenv("credenciais_supabase.env")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

ARQUIVO_TESTE = "links_multimix_teste.txt"
BASE_URL = "https://www.emporiomultimix.com.br"

def extrair_nome_pelo_link(url):
    try:
        nome_limpo = url.split('/')[-1].split('?')[0]
        nome_sem_id = re.sub(r'-\d+$', '', nome_limpo)
        nome_amigavel = nome_sem_id.replace('-', ' ').title()
        return nome_amigavel if len(nome_amigavel.strip()) > 0 else "Produto Sem Nome"
    except:
        return "Produto Sem Nome"

def ler_links_teste():
    links = []
    if not os.path.exists(ARQUIVO_TESTE):
        return links
    with open(ARQUIVO_TESTE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                url = line if line.startswith("http") else BASE_URL + "/" + line.lstrip("/")
                links.append(url)
    return list(set(links))

async def testar_link(browser, url):
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    page = await context.new_page()
    page.set_default_timeout(15000)
    
    valor_numerico = 0.0
    nome_produto = extrair_nome_pelo_link(url)
    
    try:
        await page.goto(url, wait_until="load")
        
        # Seletor direto e sem rodeios
        elemento = page.locator("span:has-text('R$')").first
        await elemento.wait_for(state="visible", timeout=5000)
        texto = await elemento.inner_text()
        
        # Extrai o número de forma direta
        apenas_numeros = re.sub(r'[^\d,.]', '', texto)
        if ',' in apenas_numeros:
            apenas_numeros = apenas_numeros.replace('.', '').replace(',', '.')
        valor_numerico = float(apenas_numeros)
    except Exception as e:
        print(f"⚠️ Não capturou preço para {nome_produto}: {e}")
    finally:
        await page.close()
        await context.close()
        
    # Retorna o dicionário exatamente como o banco quer
    return {
        "produto": nome_produto if nome_produto else "Produto Sem Nome",
        "valor_numerico": valor_numerico if valor_numerico > 0 else 0.0,
        "mercado_id": "1",
        "data_robo": datetime.now(timezone.utc).isoformat()
    }

async def main():
    links = ler_links_teste()
    if not links:
        print("❌ Nenhum link para testar.")
        return
        
    print(f"🧪 Testando {len(links)} links...")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        resultados = []
        
        for url in links:
            dados_produto = await testar_link(browser, url)
            # Salvamos mesmo se o valor for 0.0 para você saber qual link falhou!
            resultados.append(dados_produto)
                
        await browser.close()
        
        # Grava tudo de uma vez no Supabase
        if resultados:
            try:
                # Usando chamada síncrona simples para evitar conflitos de biblioteca
                supabase.table("teste_seletores_log").insert(resultados).execute()
                print(f"💾 {len(resultados)} registros gravados com sucesso no banco!")
            except Exception as e:
                print(f"❌ Erro de gravação no Supabase: {e}")

if __name__ == "__main__":
    asyncio.run(main())
