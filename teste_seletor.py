import asyncio
from playwright.async_api import async_playwright

async def testar():
    async with async_playwright() as p:
        # Abrimos com headless=False localmente para você ver o navegador funcionando, se preferir
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Um link de teste da Multimix (pode substituir por qualquer um do seu arquivo)
        url_teste = "https://www.emporiomultimix.com.br/hortifruti/abacaxi"
        
        print(f"🔗 Acessando: {url_teste}")
        await page.goto(url_teste, wait_until="load")
        
        # 1. Vamos pegar o título real para confirmar que carregou
        titulo = await page.locator("h1").first.inner_text()
        print(f"📦 Produto encontrado na página: {titulo.strip()}")
        
        # 2. Vamos capturar todo o texto que contém "R$" na página para ver onde o preço está escondido
        print("\n🔍 Buscando ocorrências de 'R$' na página para analisar o HTML:")
        elementos = page.locator("text=R$")
        total = await elementos.count()
        
        for i in range(min(total, 5)):  # Mostra as primeiras 5 ocorrências de "R$"
            texto = await elementos.nth(i).inner_text()
            classe = await elementos.nth(i).get_attribute("class")
            tag = await elementos.nth(i).evaluate("node => node.tagName")
            print(f"   -> [{tag} classe='{classe}']: '{texto.strip()}'")
            
        await browser.close()

asyncio.run(testar())
