import time
import requests
import os
from bs4 import BeautifulSoup
from urllib.parse import urlparse

# Caminhos dos arquivos atualizados para a nova padronização
arquivo_entrada = "01_links_multimix_centro.txt"
arquivo_saida = "02_links_multimix_centro.txt"

# Dicionário para agrupar os links por sessão
dados_por_sessao = {}

print("🚀 Iniciando varredura organizada de produtos no 02_explorador_multimix_centro.py")

# Verificar se o arquivo de entrada existe antes de iniciar
if not os.path.exists(arquivo_entrada):
    print(f"❌ Erro crítico: O arquivo de entrada '{arquivo_entrada}' não foi encontrado!")
    exit()

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

dominio_base = "https://www.emporiomultimix.com.br"

# 1. Ler o arquivo de entrada linha por linha e identificar sessões dinamicamente pela URL
urls_tarefa = []
sessao_atual = "Geral"

with open(arquivo_entrada, "r", encoding="utf-8") as f:
    for linha in f:
        linha = linha.strip()
        if not linha:
            continue
        
        # Se houver marcação explícita de sessão no arquivo
        if linha.startswith("#"):
            sessao_atual = linha.replace("#", "").replace("SESSAO:", "").strip()
            continue
            
        # Caso contrário, tenta deduzir a sessão pelo nome que vem na URL (ex: /comestiveis-matriz/hortifruit-596)
        try:
            parsed_url = urlparse(linha)
            partes_path = [p for p in parsed_url.path.split('/') if p and p != "comestiveis-matriz"]
            if partes_path:
                sessao_atual = partes_path[0].replace("-", " ").title()
        except:
            pass
            
        urls_tarefa.append((linha, sessao_atual))

total_urls = len(urls_tarefa)
print(f"📂 Carregados {total_urls} links de páginas de categorias para varredura.")

# 2. Varredura e extração usando requests e BeautifulSoup
for idx, (url, sessao) in enumerate(urls_tarefa, start=1):
    print(f"\n🔍 [{idx}/{total_urls}] Processando para [{sessao}] -> Conectando em: {url}")
    
    if sessao not in dados_por_sessao:
        dados_por_sessao[sessao] = set()
        
    try:
        response = requests.get(url, headers=headers, timeout=20)
        
        if response.status_code != 200:
            print(f"   ↳ 🛑 Status {response.status_code}. Falha ao acessar página.")
            continue
            
        soup = BeautifulSoup(response.text, 'html.parser')
        links_tags = soup.find_all('a', href=True)
        
        links_pagina = []
        for tag in links_tags:
            href = tag['href'].strip()
            
            # Filtro para capturar apenas links de produtos reais
            if "/produto/" in href or "-p" in href:
                if not href.startswith("http"):
                    if href.startswith("/"):
                        href = f"{dominio_base}{href}"
                    else:
                        href = f"{dominio_base}/{href}"
                
                # Remove parâmetros de rastreamento da URL do produto
                href_limpo = href.split('?')[0]
                links_pagina.append(href_limpo)
        
        links_pagina = set(links_pagina)
        
        if not links_pagina:
            print("   ↳ ⚠️ Nenhum link de produto extraído desta página.")
            continue
        
        tamanho_antes = len(dados_por_sessao[sessao])
        for link in links_pagina:
            dados_por_sessao[sessao].add(link)
            
        novos_links = len(dados_por_sessao[sessao]) - tamanho_antes
        print(f"   ↳ ✅ Sucesso: +{novos_links} novos links adicionados à sessão [{sessao}].")
        
        time.sleep(0.5)
        
    except Exception as e:
        print(f"   ↳ ❌ Erro de conexão/processamento: {str(e)[:50]}")
        continue

# 3. Gravação definitiva e estruturada no arquivo final da Etapa 02
print("\n💾 Finalizando e estruturando arquivo de saída...")

total_total_links = sum(len(links) for links in dados_por_sessao.values())

if total_total_links > 0:
    with open(arquivo_saida, "w", encoding="utf-8") as f:
        for sessao, links in sorted(dados_por_sessao.items()):
            if links:
                f.write(f"\n# SESSAO: {sessao}\n")
                for link in sorted(links):
                    f.write(f"{link}\n")
                    
    print(f"✅ Arquivo de saída '{arquivo_saida}' gerado com absoluto sucesso!")
    print(f"📦 Total de {total_total_links} links de produtos únicos distribuídos por suas respectivas sessões!")
else:
    print("❌ Falha crítica: Nenhum link foi capturado nesta rodada.")

print("🏁 Fim do pipeline da Etapa 02!")
