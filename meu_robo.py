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

# Arquivo de produção com 5000+ links organizados por sessão
ARQUIVO_PRODUCAO = "links_multimix.txt"
BASE_URL = "https://www.emporiomultimix.com.br"
TAMANHO_LOTE = 100  # Envia ao Supabase em lotes de 100 para proteger a conexão

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

def ler_links_com_sessao():
    """
    Lê o arquivo de links e retorna uma lista de tuplas contendo:
    (url_do_produto, sessao_do_produto)
    Mantendo a ordem original do arquivo.
    """
    links_mapeados = []
    sessao_atual = "Geral"  # Categoria padrão caso apareça algum link antes do primeiro cabeçalho
    
    # Verifica primeiro o arquivo de produção, se não existir usa o de teste
    arquivo = ARQUIVO_PRODUCAO if os.path.exists(ARQUIVO_PRODUCAO) else "links_multimix_teste.txt"
    
    if not os.path.exists(arquivo):
        print(f"❌ Erro: Arquivo de links não encontrado!")
        return links_mapeados
    
    print(f"📖 Lendo links organizados por sessão de: {arquivo}")
    
    # Evitar adicionar links duplicados na mesma rodada
    urls_processadas = set()
    
    with open(arquivo, 'r', encoding='utf-8') as f:
        for linha in f:
            linha = linha.strip()
            
            if not linha:
                continue
            
            # Se for uma linha de sessão, atualiza a sessão corrente e passa para a próxima linha
            if linha.startswith("#"):
                sessao_atual = linha.replace("#", "").replace("SESSAO:", "").strip()
                continue
                
            # Formata a URL
            if not linha.startswith("http"):
                url = BASE_URL + linha if linha.startswith("/") else BASE_URL + "/" + linha
            else:
                url = linha
            
            # Evita duplicar o mesmo link caso ele apareça em mais de um lugar do arquivo
            if url not in urls_processadas:
                urls_processadas.add(url)
                links_mapeados.append((url, sessao_atual))
                
    return links_mapeados

async def testar_link(browser, url, sessao, idx, total):
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    page = await context.new_page()
    page.set_default_timeout(20000)
    
    resultado_salvar = None
    
    try:
        print(f"🔄 [{idx}/{total}] Acessando [{sessao}] -> {url}")
        await page.goto(url, wait_until="load")
        
        nome_produto = extrair_nome_pelo_link(url)
        preco_detectado = "R$ 0,00"
        valor_numerico = 0.0
        
        try:
            elemento = page.locator("span:has-text('R$')").first
            await elemento.wait_for(state="visible", timeout=4000)
            texto = await elemento.inner_text()
            texto_limpo = texto.strip().split('\n')[0]
            
            temp_valor = extrair_valor_numerico(texto_limpo)
            if temp_valor > 0.0:
                preco_detectado = texto_limpo
                valor_numerico = temp_valor
        except Exception as e:
            # Silencia erros de seletores comuns em produção para não poluir o log do GitHub
            pass

        # Só gera a estrutura de salvamento se o preço for maior que zero
        if valor_numerico > 0.0:
            resultado_salvar = {
                "produto": nome_produto,
                "valor_numerico": valor_numerico,
                "mercado_id": "1",
                "sessao": sessao,  # 🔑 Enviando a sessão estruturada para o banco
                "link": url,       # 🔑 Enviando o link completo para o banco
                "data_robo": datetime.now(timezone.utc).isoformat()
            }
            print(f"✅ SUCESSO: '{nome_produto[:30]}' | Preço: {preco_detectado} | Sessão: {sessao}")
            
    except Exception as e:
        print(f"💥 Erro crítico no link {url[:40]}: {str(e)[:40]}")
    finally:
        await page.close()
        await context.close()
        
    return resultado_salvar

def salvar_no_supabase(dados):
    try:
        # Enviando para a tabela de produção: historico_precos
        supabase.table("historico_precos").insert(dados).execute()
        print(f"💾 Lote de {len(dados)} registros gravados com sucesso no Supabase!")
        return True
    except Exception as e:
        print(f"❌ Erro ao salvar lote no Supabase: {e}")
        return False

async def main():
    # Agora recebemos uma lista de tuplas: [(url, sessao), ...]
    links_mapeados = ler_links_com_sessao()
    if not links_mapeados:
        print("⚠️ Nenhum link de teste ou produção encontrado.")
        return
        
    total_links = len(links_mapeados)
    print(f"🚀 Iniciando raspagem pesada para {total_links} URLs estruturadas por sessões...")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        resultados_lote = []
        
        for idx, (url, sessao) in enumerate(links_mapeados, start=1):
            res = await testar_link(browser, url, sessao, idx, total_links)
            
            # FILTRO CRÍTICO: Só adiciona se o produto foi raspado com sucesso (> 0.0)
            if res:
                resultados_lote.append(res)
            
            # Envia e esvazia a lista se atingir o tamanho do lote
            if len(resultados_lote) >= TAMANHO_LOTE:
                print(f"📦 Enviando lote de {TAMANHO_LOTE} produtos válidos ao banco...")
                salvar_no_supabase(resultados_lote)
                resultados_lote = []
                
        await browser.close()
        
        # Salva o resto que sobrou no final
        if resultados_lote:
            print(f"📦 Enviando lote final restante de {len(resultados_lote)} itens...")
            salvar_no_supabase(resultados_lote)

if __name__ == "__main__":
    asyncio.run(main())
