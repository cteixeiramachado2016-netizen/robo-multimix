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
arquivo_saida = "links_multimix.txt"

print("🚀 Iniciando varredura otimizada no explorador_multimix_centro.py")

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

total_paginas_processadas = 0

for idx, cat in enumerate(categorias, start=1):
    page = 1
    paginas_sem_novidades = 0  # <--- NOVA TRAVA DE SEGURANÇA
    print(f"\n📁 Processando categoria [{idx}/{len(categorias)}]: {cat}")
    
    while True:
        url = f"https://www.emporiomultimix.com.br/{cat}?page={page}"
        total_paginas_processadas += 1
        print(f"🔄 [{total_paginas_processadas}] Conectando em: {url}")
        
        try:
            response = requests.get(url, headers=headers, timeout=20)
            
            if response.status_code != 200:
                print(f"   ↳ 🛑 Status {response.status_code}. Fim das páginas desta categoria.")
                break
                
            soup = BeautifulSoup(response.text, 'html.parser')
            links_tags = soup.find_all('a', href=True)
            
            links_pagina = []
            for tag in links_tags:
                href = tag['href'].strip()
                
                if "/produto/" in href or "-p" in href:
                    if href.startswith("https://www.emporiomultimix.com.br"):
                        href = href.replace("https://www.emporiomultimix.com.br", "")
                    
                    if href.startswith("/"):
                        links_pagina.append(href)
            
            links_pagina = list(set(links_pagina))
            
            if not links_pagina:
                print("   ↳ ⚠️ Nenhum link de produto extraído. Fim da seção.")
                break
            
            # Medição de novos links reais injetados
            tamanho_antes = len(links_unicos)
            for link in links_pagina:
                links_unicos.add(link)
                
            novos_links = len(links_unicos) - tamanho_antes
            print(f"   ↳ ✅ Sucesso: +{novos_links} links únicos adicionados (Total acumulado: {len(links_unicos)}).")
            
            # <--- AJUSTE DA ENGRENAGEM: Se não trouxe nada de novo, liga o alerta
            if novos_links == 0:
                paginas_sem_novidades += 1
            else:
                paginas_sem_novidades = 0 # Reseta se achar algo novo
                
            # Se por 2 páginas seguidas o site repetiu dados ou trouxe zero novidades, a paginação acabou
            if paginas_sem_novidades >= 2:
                print("   ↳ 🛑 Parada preventiva: Conteúdo repetido/esgotado. Pulando categoria.")
                break
            
            page += 1
            time.sleep(1.0)
            
        except Exception as e:
            print(f"   ↳ ❌ Erro de conexão/processamento: {str(e)[:50]}")
            break

# 3. Gravação definitiva
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
