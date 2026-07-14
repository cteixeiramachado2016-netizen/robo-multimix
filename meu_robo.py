No código que analisamos anteriormente, o envio estava sendo feito **de uma vez só no final do script** (enviando a lista inteira de `resultados` após fechar o navegador), e não em blocos de 100 em 100.

Se a sua lista de links for muito grande, enviar tudo de uma vez pode estourar o limite de requisição do Supabase ou fazer você perder todo o progresso se o robô cair no meio do caminho.

Para resolver isso, estruturei o envio em lotes (chunks) de **100 em 100 itens**. Assim, à medida que o robô vai coletando, ele já vai salvando e limpando a memória.

Aqui está o `meu_robo.py` ajustado com essa lógica de salvamento em lotes:

```python
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
TAMANHO_LOTE = 100  # Define o tamanho do bloco para salvamento

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

def salvar_no_supabase(dados):
    """Função auxiliar para fazer o envio síncrono e seguro dos blocos."""
    try:
        supabase.table("teste_seletores_log").insert(dados).execute()
        print(f"💾 Lote de {len(dados)} registros gravados com sucesso no Supabase!")
        return True
    except Exception as e:
        print(f"❌ Erro ao salvar lote no Supabase: {e}")
        return False

async def main():
    links = ler_links_teste()
    if not links:
        print("⚠️ Nenhum link de teste encontrado no arquivo.")
        return
        
    total_links = len(links)
    print(f"🧪 Iniciando raspagem para {total_links} URLs...")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        resultados_lote = []
        
        for idx, url in enumerate(links, start=1):
            res = await testar_link(browser, url, idx, total_links)
            if res:
                resultados_lote.append(res)
            
            # Quando atingir o tamanho do lote (100), envia e limpa a lista temporária
            if len(resultados_lote) >= TAMANHO_LOTE:
                print(f"📦 Limiar de {TAMANHO_LOTE} itens atingido. Enviando lote para o banco...")
                salvar_no_supabase(resultados_lote)
                resultados_lote = []  # Esvazia a lista para o próximo lote
                
        await browser.close()
        
        # Envia o que sobrou no último lote (caso o total não seja múltiplo exato de 100)
        if resultados_lote:
            print(f"📦 Enviando lote final restante de {len(resultados_lote)} itens...")
            salvar_no_supabase(resultados_lote)

if __name__ == "__main__":
    asyncio.run(main())

```

### O que mudou com essa implementação de lotes:

* **Variável `TAMANHO_LOTE = 100**`: Define de forma simples o limite do bloco.
* **Função `salvar_no_supabase**`: Isolei o bloco de envio para manter o loop principal limpo e legível.
* **Envio em tempo de execução**: O robô não espera mais terminar de ler todos os links para salvar. A cada 100 links processados, ele joga os dados no Supabase.
* **Tratamento de sobra**: Se você tiver 250 links, ele vai salvar dois lotes de 100 durante a execução e um lote final de 50 após o encerramento do navegador.
