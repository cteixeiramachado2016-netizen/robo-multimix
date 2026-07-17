import time
import requests
import os
from bs4 import BeautifulSoup

# Caminhos dos arquivos
arquivo_entrada = "links_multimix_centro.txt"
arquivo_saida = "links_multimix.txt"

# Dicionário para agrupar os links por sessão
# Estrutura: { "Açougue Bovino": {link1, link2}, "Hortifruti": {link1, link2} }
dados_por_sessao = {}
sessao_atual = "Sem Categoria"

print("🚀 Iniciando varredura organizada por sessões no explorador_multimix_centro.py")

# Verificar se o arquivo com as sessões existe antes de iniciar
if not os.path.exists(arquivo_entrada):
    print(f"❌ Erro crítico: O arquivo de entrada '{arquivo_entrada}' não foi encontrado!")
    exit()

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

domínio_base = "https://www.emporiomultimix.com.br"

# 1. Ler o arquivo de entrada linha por linha para detectar as sessões e links
urls_tarefa = []
with open(arquivo_entrada, "r", encoding="utf-8") as f:
    for linha in f:
        linha = linha.strip()
        if not linha:
            continue
        
        # Se for uma linha de sessão (ex: # SESSAO: Açougue Bovino)
        if linha.startswith("#"):
            sessao_atual = linha.replace("#", "").replace("SESSAO:", "").strip()
            continue
            
        # Guarda a URL associada à sessão em que ela foi encontrada
        urls_tarefa.append((linha, sessao_atual))

total_urls = len(urls_tarefa)
print(f"📂 Carregados {total_urls} links de páginas mapeados por suas sessões.")

# 2. Varredura e extração
for idx, (url, sessao) in enumerate(urls_tarefa, start=1):
    print(f"\n🔍 [{idx}/{total_urls}] Processando para [{sessao}] -> Conectando em: {url}")
    
    # Inicializa o set da sessão se ainda não existir no dicionário
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
                        href = f"{domínio_base}{href}"
                    else:
                        href = f"{domínio_base}/{href}"
                
                links_pagina.append(href)
        
        # Remove duplicados da página atual antes de adicionar ao set da sessão
        links_pagina = set(links_pagina)
        
        if not links_pagina:
            print("   ↳ ⚠️ Nenhum link de produto extraído desta página.")
            continue
        
        tamanho_antes = len(dados_por_sessao[sessao])
        for link in links_pagina:
            dados_por_sessao[sessao].add(link)
            
        novos_links = len(dados_por_sessao[sessao]) - tamanho_antes
        print(f"   ↳ ✅ Sucesso: +{novos_links} novos links adicionados à sessão [{sessao}].")
        
        time.sleep(1.0)
        
    except Exception as e:
        print(f"   ↳ ❌ Erro de conexão/processamento: {str(e)[:50]}")
        continue

# 3. Gravação definitiva e estruturada por sessões no arquivo final
print("\n💾 Finalizando e estruturando arquivo de saída...")

total_total_links = sum(len(links) for links in dados_por_sessao.values())

if total_total_links > 0:
    with open(arquivo_saida, "w", encoding="utf-8") as f:
        # Passa por cada sessão coletada na ordem alfabética ou original
        for sessao, links in sorted(dados_por_sessao.items()):
            if links: # Só escreve a sessão se ela tiver algum produto
                f.write(f"\n# SESSAO: {sessao}\n")
                # Escreve todos os links daquela sessão ordenados
                for link in sorted(links):
                    f.write(f"{link}\n")
                    
    print(f"✅ Arquivo de saída '{arquivo_saida}' gerado com absoluto sucesso!")
    print(f"📦 Total de {total_total_links} links de produtos únicos distribuídos por suas respectivas sessões!")
else:
    print("❌ Falha crítica: Nenhum link foi capturado nesta rodada.")

print("🏁 Fim do pipeline de extração estruturado por sessões!")
