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

# Dicionário de URLs baseadas no seu mapeamento original
SESSÕES = {
    "acougue": "https://www.emporiomultimix.com.br/acougue",
    "hortifruti": "https://www.emporiomultimix.com.br/hortifruti",
    "bebidas_alcoolicas": "https://www.emporiomultimix.com.br/bebidas-alcoolicas",
    "vinhos": "https://www.emporiomultimix.com.br/vinhos",
    "bebidas": "https://www.emporiomultimix.com.br/bebidas",
    "congelados": "https://www.emporiomultimix.com.br/congelados",
    "limpeza": "https://www.emporiomultimix.com.br/limpeza",
    "mercearia_doce": "https://www.emporiomultimix.com.br/mercearia-doce",
    "padaria_artesanal": "https://www.emporiomultimix.com.br/padaria-artesanal",
    "padaria_industrial": "https://www.emporiomultimix.com.br/padaria-industrial",
    "petshop": "https://www.emporiomultimix.com.br/pet-shop",
    "peixaria": "https://www.emporiomultimix.com.br/peixaria",
    "higiene": "https://www.emporiomultimix.com.br/higiene-e-beleza",
    "lanchonete": "https://www.emporiomultimix.com.br/lanchonete-e-frios",
    "frios": "https://www.emporiomultimix.com.br/frios-e-laticinios",
    "saudavel": "https://www.emporiomultimix.com.br/saudavel",
    "bazar": "https://www.emporiomultimix.com.br/bazar",
    "laticinios_embutidos": "https://www.emporiomultimix.com.br/frios-e-laticinios",
    "mercearia_salgada": "https://www.emporiomultimix.com.br/mercearia-salgada"
}

def extrair_valor_numerico(texto_preco):
    try:
        apenas_numeros = re.sub(r'[^\d,.]', '', texto_preco)
        if ',' in apenas_numeros:
            apenas_numeros = apenas_numeros.replace('.', '').replace(',', '.')
        return float(apenas_numeros)
    except:
        return 0.0

async def raspar_categoria(context, nome_categoria, url_base):
    print(f"\n🚀 Iniciando raspagem da categoria: {nome_categoria.upper()}")
    page = await context.new_page()
    
    # Bloqueio simples de mídias para economizar banda do GitHub Actions
    await page.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "media", "font"] else route.continue_())
    
    try:
        await page.goto(url_base, wait_until="domcontentloaded", timeout=60000)
        
        # Rola a página para carregar os produtos (infinitescroll ou paginação dinâmica)
        for _ in range(5):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(2)
            
        # Seleciona os cards de produto de acordo com a estrutura do e-commerce da Multimix
        produtos = await page.locator(".product-item, .vtex-search-result-3-x-galleryItem").all()
        print(f"📦 Encontrados {len(produtos)} produtos em {nome_categoria.upper()}")
        
        dados_para_salvar = []
        
        for produto in produtos:
            try:
                # Busca o nome e o preço dentro de cada card
                nome_elem = produto.locator(".product-name, .vtex-product-summary-2-x-nameContainer")
                preco_elem = produto.locator(".product-price, .vtex-product-price-1-x-currencyContainer")
                
                nome = await nome_elem.inner_text() if await nome_elem.count() > 0 else "Produto Sem Nome"
                preco_txt = await preco_elem.inner_text() if await preco_elem.count() > 0 else "R$ 0,00"
                
                nome = nome.strip()
                valor = extrair_valor_numerico(preco_txt)
                
                # SÓ ADICIONA SE TIVER PREÇO VÁLIDO
                if valor > 0.0:
                    # --- AQUI ESTÁ O NOVO MAPEAMENTO DE COLUNAS IA QUE VOCÊ ME PEDIU ---
                    dados_para_salvar.append({
                        "produto": nome,
                        "valor_numerico": valor,
                        "mercado_id": MERCADO_ID,
                        "data_robo": datetime.now(timezone.utc).isoformat()
                    })
            except Exception as e:
                continue
                
        # Salva o lote da categoria no Supabase
        if dados_para_salvar:
            print(f"💾 Enviando {len(dados_para_salvar)} produtos de '{nome_categoria}' para o Supabase...")
            resposta = supabase.table("historico_precos").insert(dados_para_salvar).execute()
            print(f"✅ Gravado com sucesso!")
            
    except Exception as e:
        print(f"❌ Erro ao raspar a categoria {nome_categoria}: {e}")
    finally:
        await page.close()

async def main():
    # Detecta se rodamos uma categoria específica passada por argumento no GitHub Actions (ex: python meu_robo.py acougue)
    categoria_alvo = sys.argv[1].strip().lower() if len(sys.argv) > 1 else None
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        if categoria_alvo:
            if categoria_alvo in SESSÕES:
                await raspar_categoria(context, categoria_alvo, SESSÕES[categoria_alvo])
            else:
                print(f"❌ Categoria '{categoria_alvo}' não encontrada no mapeamento do robô.")
        else:
            # Varredura completa se nenhum argumento for passado
            for cat, url in SESSÕES.items():
                await raspar_categoria(context, cat, url)
                await asyncio.sleep(5)  # Respiro leve de 5 segundos entre categorias
                
        await context.close()
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
