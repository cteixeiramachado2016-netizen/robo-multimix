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

# Configurações do Teste
ARQUIVO_TESTE = "links_multimix_teste.txt"
BASE_URL = "https://www.emporiomultimix.com.br"

# Lista de seletores para testar em ordem de prioridade
SELETORES_PRECO_TESTE = [
    "span:has-text('R$')", 
    ".precoPor", 
    ".price", 
    ".product-price", 
    "strong:has-text('R$')"
]

def extrair_valor_numerico(texto_preco):
    try:
        apenas_numeros = re.sub(r'[^\d,.]', '', texto_preco)
        if ',' in apenas_numeros:
            apenas_numeros = apenas_numeros.replace('.', '').replace(',', '.')
        return float(apenas_numeros)
    except:
        return 0.0

def ler_links_teste():
    links = []
    if not os.path.exists(ARQUIVO_TESTE):
        print(f"❌ Erro: Arquivo {ARQUIVO_TESTE} não encontrado!")
        return links
    
    with open(ARQUIVO_TESTE, 'r', encoding='utf-8') as f:
        for linha in f:
            linha = linha.strip()
            if linha and not linha.startswith("#"):
                if not linha.startswith("http"):
                    url = BASE_URL + linha if linha.startswith("/") else BASE_URL + "/" + linha
                else:
                    url = linha
                links.append(url)
    return list(set(links)) # Remove duplicados na leitura

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
        
        # 1. Tenta capturar o Título de forma flexível
        nome_produto = "Desconhecido"
        try:
            tag_titulo = page.locator("h1, .product-name, [class*='title'], h2").first
            await tag_titulo.wait_for(state="visible", timeout=3000)
            nome_real = await tag_titulo.inner_text()
            if nome_real:
                nome_produto = nome_real.strip()
        except:
            pass
            
        # 2. Testa os seletores de preço UM POR UM (para ao achar o primeiro válido)
        seletor_vencedor = "Nenhum"
        preco_detectado = "R$ 0,00"
        valor_numerico = 0.0
        
        for seletor in SELETORES_PRECO_TESTE:
            try:
                elemento = page.locator(seletor).first
                await elemento.wait_for(state="visible", timeout=3000)
                texto = await elemento.inner_text()
                texto_limpo = texto.strip().split('\n')[0]
                
                temp_valor = extrair_valor_numerico(texto_limpo)
                if temp_valor > 0.0:
                    seletor_vencedor = seletor
                    preco_detectado = texto_limpo
                    valor_numerico = temp_valor
                    break # ENCONTROU O SELETOR CERTO! Interrompe o loop de testes para este link
            except:
                continue

        # Estrutura os dados para salvar
        resultado_salvar = {
            "url": url,
            "produto": nome_produto,
            "seletor_usado": seletor_vencedor,
            "preco_capturado": preco_detectado,
            "valor_numerico": valor_numerico,
            "sucesso": valor_numerico > 0.0,
            "data_teste": datetime.now(timezone.utc).isoformat()
        }
        
        if resultado_salvar["sucesso"]:
            print(f"✅ SUCESSO: '{nome_produto[:30]}' | Seletor: {seletor_vencedor} | Preço: {preco_detectado}")
        else:
            print(f"❌ FALHA: Não foi possível extrair preço para {url}")
            
    except Exception as e:
        print(f"💥 Erro crítico ao testar URL: {str(e)[:50]}")
        resultado_salvar = {
            "url": url,
            "produto": "Erro de Conexão",
            "seletor_usado": "Erro",
            "preco_capturado": "R$ 0,00",
            "valor_numerico": 0.0,
            "sucesso": False,
            "data_teste": datetime.now(timezone.utc).isoformat()
        }
    finally:
        await page.close()
        await context.close()
        
    return resultado_salvar

async def main():
    links = ler_links_teste()
    if not links:
        print("⚠️ Nenhum link de teste encontrado no arquivo.")
        return
        
    print(f"🧪 Iniciando testes para {len(links)} URLs de controle...")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        resultados = []
        
        for idx, url in enumerate(links, start=1):
            res = await testar_link(browser, url, idx, len(links))
            if res:
                resultados.append(res)
                
        await browser.close()
        
        # Envia resultados para a tabela do Supabase
        if resultados:
            try:
                await asyncio.to_thread(
                    supabase.table("teste_seletores_log").insert(resultados).execute
                )
                print(f"💾 {len(resultados)} relatórios de teste salvos em 'teste_seletores_log'!")
            except Exception as e:
                print(f"❌ Erro ao salvar logs no Supabase: {e}")

if __name__ == "__main__":
    asyncio.run(main())
