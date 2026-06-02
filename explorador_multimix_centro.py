import time
import requests
from bs4 import BeautifulSoup

# 1. Lista de categorias/sessões reais do Multimix Centro para o mapeamento
categorias = [
    "comestiveis-matriz/acougue-bovino-617",
    "comestiveis-matriz/hortifruit-596",
    "comestiveis-matriz/bebidas-alcoolicas-605",
    "comestiveis-matriz/bebidas-alcoolicas-vinhos-735",
    "comestiveis-matriz/bebidas-nao-alcoolicas-611",
    "comestiveis-matriz/congelados-613",
    "comestiveis-matriz/limpeza-593",
    "comestiveis-matriz/mercearia-doce-591",
    "comestiveis-matriz/padaria-producao-da-casa-651",
    "comestiveis-matriz/padaria-industrializado-691",
    "comestiveis-matriz/produtos-para-animais-668",
    "comestiveis-matriz/peixes-633",
    "comestiveis-matriz/higiene-e-perfumaria-608",
    "comestiveis-matriz/lanchonete-630",
    "comestiveis-matriz/frios-e-laticinios-636",
    "comestiveis-matriz/alimentacao-saudavel-664",
    "comestiveis-matriz/bazar-600",
    "comestiveis-matriz/frios-e-laticinios-iogurtlinguicasmassas-819",
    "comestiveis-matriz/mercearia-salgada-azeitemassatemperos-849"
]

links_unicos = set()
arquivo_saida = "links_multimix.txt"  # Ajustado para o padrão do projeto

print("🚀 Iniciando varredura otimizada no explorador_multimix_centro.py")

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Contador global de páginas acessadas para o log
total_paginas_processadas = 0

for idx, cat in enumerate(categorias, start=1):
    page = 1
    print(f"\n📁 Processando categoria [{idx}/{len(categorias)}]: {cat}")
    
    while True:
        url = f"https://www.emporiomultimix.com.br/{cat}?page={page}"
        total_paginas_processadas += 1
        print(f"🔄 [{total_paginas_processadas}] Conectando em: {url}")
        
        try:
            response = requests.get(url, headers=headers, timeout=15)
            
            # Se a página retornar erro ou não existir, encerra a categoria
            if response.status_code != 200:
                print(f"   ↳ 🛑 Status {response.status_code}. Fim das páginas desta categoria.")
                break
                
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # ATENÇÃO SELETOR: Buscando as tags 'a' de produto. 
            # O código analisa os links que contêm a estrutura de produto do site
            links_tags = soup.find_all('a', href=True)
            
            links_pagina = []
            for tag in links_tags:
                href = tag['href']
                # Filtro para capturar apenas links que sejam de produtos internos
                if "/produto/" in href or "-p" in href: # Ajuste o termo se o padrão de URL de produto for diferente
                    if not href.startswith('http'):
                        href = f"https://www.emporiomultimix.com.br{href}"
                    links_pagina.append(href)
            
            # Remove duplicados da própria página antes de validar
            links_pagina = list(set(links_pagina))
            
            if not links_pagina:
                print("   ↳ ⚠️ Nenhum link extraído. Paginação dinâmica encerrada para esta seção.")
                break # Sai do loop 'while' da categoria e vai para a próxima
            
            # Armazena no set global do robô
            tamanho_antes = len(links_unicos)
            for link in links_pagina:
                links_unicos.add(link)
                
            novos_links = len(links_unicos) - tamanho_antes
            print(f"   ↳ ✅ Sucesso: +{novos_links} links únicos adicionados (Total acumulado: {len(links_unicos)}).")
            
            page += 1
            time.sleep(0.5) # Delay seguro contra bloqueios
            
        except Exception as e:
            print(f"   ↳ ❌ Erro de conexão/processamento: {e}")
            break

# 3. Gravação definitiva e limpa no final do pipeline
print("\n💾 Finalizando e salvando dados...")
with open(arquivo_saida, "w", encoding="utf-8") as f:
    for link in sorted(links_unicos):
        f.write(f"{link}\n")

print(f"Arquivo de saída gerado com sucesso: '{arquivo_saida}'")
print(f"📦 Total de {len(links_unicos)} links de produtos únicos armazenados!")
print("🏁 Fim do pipeline de extração para o Multimix Centro!")