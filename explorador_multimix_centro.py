import time
import requests
import os
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
arquivo_saida = "links_multimix.txt"  # Ajustado fixo para alimentar o meu_robo.py

print("🚀 Iniciando varredura otimizada no explorador_multimix_centro.py")

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

total_paginas_processadas = 0

for idx, cat in enumerate(categorias, start=1):
    page = 1
    print(f"\n📁 Processando categoria [{idx}/{len(categorias)}]: {cat}")
    
    while True:
        url = f"https://www.emporiomultimix.com.br/{cat}?page={page}"
        total_paginas_processadas += 1
        print(f"🔄 [{total_paginas_processadas}] Conectando em: {url}")
        
        try:
            response = requests.get(url, headers=headers, timeout=20)
            
            # Se a página retornar erro (Ex: 404), encerra a paginação desta categoria
            if response.status_code != 200:
                print(f"   ↳ 🛑 Status {response.status_code}. Fim das páginas desta categoria.")
                break
                
            soup = BeautifulSoup(response.text, 'html.parser')
            links_tags = soup.find_all('a', href=True)
            
            links_pagina = []
            for tag in links_tags:
                href = tag['href'].strip()
                
                # Filtro inteligente para capturar links internos de produtos
                if "/produto/" in href or "-p" in href:
                    # Padroniza salvando apenas a rota limpa (o meu_robo.py monta o domínio se precisar)
                    if href.startswith("https://www.emporiomultimix.com.br"):
                        href = href.replace("https://www.emporiomultimix.com.br", "")
                    
                    if href.startswith("/"):
                        links_pagina.append(href)
            
            # Remove duplicados da página atual
            links_pagina = list(set(links_pagina))
            
            if not links_pagina:
                print("   ↳ ⚠️ Nenhum link de produto extraído. Mudança de padrão ou fim da seção.")
                break
            
            # Armazena no set principal
            tamanho_antes = len(links_unicos)
            for link in links_pagina:
                links_unicos.add(link)
                
            novos_links = len(links_unicos) - tamanho_antes
            print(f"   ↳ ✅ Sucesso: +{novos_links} links únicos adicionados (Total acumulado: {len(links_unicos)}).")
            
            page += 1
            time.sleep(1.0) # Delay de 1 segundo (Ideal para ambiente cloud do GitHub Actions não ser bloqueado)
            
        except Exception as e:
            print(f"   ↳ ❌ Erro de conexão/processamento: {str(e)[:50]}")
            break

# 3. Gravação definitiva e inteligente no final do pipeline
print("\n💾 Finalizando e checando integridade dos dados...")

# 🛡️ TRAVA DE SEGURANÇA: Se por algum problema de conexão o robô ler 0 links, 
# ele NÃO joga por cima do arquivo antigo para não apagar o seu arquivo diário ativo.
if len(links_unicos) > 0:
    with open(arquivo_saida, "w", encoding="utf-8") as f:
        for link in sorted(links_unicos):
            f.write(f"{link}\n")
    print(f"✅ Arquivo de saída gerado com sucesso: '{arquivo_saida}'")
    print(f"📦 Total de {len(links_unicos)} links de produtos únicos armazenados!")
else:
    print("❌ Falha crítica: Nenhum link foi capturado nesta rodada. O arquivo antigo foi preservado por segurança.")

print("🏁 Fim do pipeline de extração para o Multimix Centro!")
