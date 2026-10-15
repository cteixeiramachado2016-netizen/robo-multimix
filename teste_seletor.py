import os
import asyncio
from playwright.async_api import async_playwright

ARQUIVO_TESTE = "links_multimix_teste.txt"
BASE_URL = "https://www.emporiomultimix.com.br"
URL_MATRIZ = "https://www.emporiomultimix.com.br/comestiveis-matriz"

async def extrair_e_mapear_categorias(page):
    print(f"🌐 Acessando a página matriz: {URL_MATRIZ}")
    await page.goto(URL_MATRIZ, wait_until="load")
    
    # Aguarda os elementos de categorias carregarem na tela
    await page.wait_for_selector("a[href*='comestiveis-matriz/']", timeout=10000)
    
    # Extrai todos los links únicos de categorias da página principal
    links_brutos = await page.eval_on_selector_all(
        "a[href*='comestiveis-matriz/']",
        "elements => elements.map(e => e.href)"
    )
    
    # Filtra apenas os links de categorias
    categorias_unicas = set()
    for link in links_brutos:
        link_limpo = link.split('?')[0]
        if link_limpo != URL_MATRIZ and "comestiveis-matriz/" in link_limpo:
            categorias_unicas.add(link_limpo)
            
    print(f"🔍 Encontradas {len(categorias_unicas)} categorias base.")
    
    links_finais_com_paginacao = []

    for cat_url in categorias_unicas:
        print(f"📂 Verificando paginação para: {cat_url}")
        
        pagina_atual = 1
        max_paginas = 10 
        
        while pagina_atual <= max_paginas:
            url_teste = f"{cat_url}?page={pagina_atual}"
            
            try:
                response = await page.goto(url_teste, wait_until="load")
                
                if response.status == 404:
                    print(f"   ❌ Página {pagina_atual} retornou 404. Fim da categoria.")
                    break
                
                conteudo_texto = await page.inner_text("body")
                if "Nenhum resultado encontrado" in conteudo_texto:
                    print(f"   ⚠️ Página {pagina_atual} está vazia ('Nenhum resultado encontrado'). Fim da categoria.")
                    break
                
                links_finais_com_paginacao.append(url_teste)
                print(f"   ✅ Válida: {url_teste}")
                pagina_atual += 1
                
            except Exception as e:
                print(f"   ❌ Erro ao testar {url_teste}: {e}")
                break

    return links_finais_com_paginacao

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        page.set_default_timeout(15000)
        
        try:
            links_gerados = await extrair_e_mapear_categorias(page)
            
            if links_gerados:
                with open(ARQUIVO_TESTE, "w", encoding="utf-8") as f:
                    for link in links_gerados:
                        f.write(f"{link}\n")
                print(f"\n💾 Sucesso! {len(links_gerados)} links salvos em '{ARQUIVO_TESTE}'.")
            else:
                print("\n❌ Nenhum link foi gerado.")
                
        except Exception as e:
            print(f"\n❌ Erro geral no robô explorador: {e}")
            
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())

