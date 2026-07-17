import time
import requests
import os
from bs4 import BeautifulSoup

# Caminhos dos arquivos
arquivo_entrada = "links_multimix_centro.txt"
arquivo_saida = "links_multimix.txt"

links_unicos = set()

print("🚀 Iniciando varredura otimizada no explorador_multimix_centro.py")

# Verificar se o arquivo com as sessões existe antes de iniciar
if not os.path.exists(arquivo_entrada):
    print(f"❌ Erro crítico: O arquivo de entrada '{arquivo_entrada}' não foi encontrado!")
    exit()

# 1. Carregar as URLs de sessões do arquivo de texto de forma limpa
urls_para_raspar = []
with open(arquivo_entrada, "r", encoding="utf-8") as f:
    for linha in f:
        linha = linha.strip()
        # Ignora linhas vazias ou comentários de sessão (linhas que começam com #)
        if not linha or linha.startswith("#"):
            continue
        urls_para_raspar.append(linha)

total_urls = len(urls_para_raspar)
print(f"📂 Carregados {total_urls} links de páginas/sessões para processamento.")

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

domínio_base = "https://www.emporiomultimix.com.br"

# 2. Varredura link por link baseado no arquivo de entrada
for idx, url in enumerate(urls_para_raspar, start=1):
    print(f"\n🔄 [{idx}/{total_urls}] Conectando em: {url}")
    
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
                # 🔧 AJUSTE AQUI: Garante que todos os links comecem com o domínio completo
                if not href.startswith("http"):
                    # Se o link começar com barra "/", junta com o domínio
                    if href.startswith("/"):
                        href = f"{domínio_base}{href}"
                    else:
                        href = f"{domínio_base}/{href}"
                
                links_pagina.append(href)
        
        links_pagina = list(set(links_pagina))
        
        if not links_pagina:
            print("   ↳ ⚠️ Nenhum link de produto extraído desta página.")
            continue
        
        # Medição de novos links reais injetados no set global
        tamanho_antes = len(links_unicos)
        for link in links_pagina:
            links_unicos.add(link)
            
        novos_links = len(links_unicos) - tamanho_antes
        print(f"   ↳ ✅ Sucesso: +{novos_links} novos links de produtos únicos (Total acumulado: {len(links_unicos)}).")
        
        # Intervalo amigável para evitar bloqueio do servidor
        time.sleep(1.0)
        
    except Exception as e:
        print(f"   ↳ ❌ Erro de conexão/processamento: {str(e)[:50]}")
        continue

# 3. Gravação definitiva no arquivo final links_multimix.txt
print("\n💾 Finalizando e checando integridade dos dados...")

if len(links_unicos) > 0:
    with open(arquivo_saida, "w", encoding="utf-8") as f:
        for link in sorted(links_unicos):
            f.write(f"{link}\n")
    print(f"✅ Arquivo de saída gerado com sucesso: '{arquivo_saida}'")
    print(f"📦 Total de {len(links_unicos)} links de produtos únicos armazenados!")
else:
    print("❌ Falha crítica: Nenhum link foi capturado nesta rodada. O arquivo antigo foi preservado por segurança.")

print("🏁 Fim do pipeline de extração para o Multimix Centro!")
