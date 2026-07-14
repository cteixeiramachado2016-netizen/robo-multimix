import os
import asyncio
from playwright.async_api import async_playwright
from supabase import create_client, Client

# Configurações do Supabase extraídas do ambiente do GitHub
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")

supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("✅ Conexão com o Supabase estabelecida para gravação dos testes!")
else:
    print("⚠️ Atenção: Variáveis do Supabase não encontradas. O teste rodará sem salvar no banco.")

BASE_URL = "https://www.emporiomultimix.com.br"

def ler_links_teste():
    links = []
    arquivo = "links_multimix_teste.txt"
    if not os.path.exists(arquivo):
        print(f"❌ Erro: O arquivo '{arquivo}' não foi encontrado!")
        return links
    
    with open(arquivo, 'r', encoding='utf-8') as f:
        for linha in f:
            linha = linha.strip()
            if linha and not linha.startswith("#"):
                if not linha.startswith("http"):
                    url = BASE_URL + linha if linha.startswith("/") else BASE_URL + "/" + linha
                else:
                    url = linha
                links.append(url)
    return links

async def testar_pagina(page, url):
    print(f"\n🔗 [TESTE] Acessando: {url}")
    produto_nome = "Desconhecido"
    
    try:
        await page.goto(url, wait_until="load", timeout=25000)
        
        # Tenta pegar o nome do produto
        try:
            titulo = await page.locator("h1").first.inner_text()
            produto_nome = titulo.strip()
            print(f"📦 [PRODUTO]: {produto_nome}")
        except:
            print("⚠️ Não foi possível encontrar o título do produto")

        # Nossos candidatos a seletores de preço
        seletores = [
            ".precoPor",
            ".price",
            ".product-price",
            ".precos",
            "[id*='preco']",
            "[class*='preco']",
            "[class*='price']",
            "strong:has-text('R$')",
            "span:has-text('R$')",
            "div:has-text('R$')",
            "p:has-text('R$')"
        ]
        
        for seletor in seletores:
            try:
                elemento = page.locator(seletor).first
                await elemento.wait_for(state="visible", timeout=3000)
                texto = await elemento.inner_text()
                texto_limpo = texto.strip().replace('\n', ' ')
                
                if texto_limpo:
                    print(f"   ✅ Seletor '{seletor}': '{texto_limpo}'")
                    
                    # Se o Supabase estiver ativo, salva o teste bem-sucedido no banco
                    if supabase:
                        dados_teste = {
                            "url": url,
                            "produto": produto_nome,
                            "seletor_testado": seletor,
                            "valor_encontrado": texto_limpo
                        }
                        supabase.table("teste_seletores_log").insert(dados_teste).execute()
            except Exception as e:
                pass
                
    except Exception as e:
        print(f"❌ Erro ao acessar o link: {str(e)[:50]}")

async def main():
    links = ler_links_teste()
    if not links:
        print("⚠️ Nenhum link carregado do arquivo de teste.")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        for url in links:
            await testar_pagina(page, url)
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
