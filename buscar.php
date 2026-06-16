<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Minha Lista de Compras - Club Help</title>
    <!-- Link para o Tailwind CSS para um visual moderno e limpo -->
    <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
</head>
<body class="bg-gray-50 flex flex-col min-h-screen">

    <!-- Header Simples -->
    <header class="bg-white shadow-sm py-4 px-6 border-b border-gray-200">
        <div class="max-w-4xl mx-auto flex justify-between items-center">
            <h1 class="text-xl font-bold text-gray-800">Help Escambo <span class="text-sm font-normal text-blue-600">Prime</span></h1>
            <a href="logout.php" class="text-sm text-gray-500 hover:text-red-600 transition">Sair</a>
        </div>
    </header>

    <!-- Área Principal -->
    <main class="flex-grow max-w-4xl w-full mx-auto p-6">
        <div class="bg-white rounded-xl shadow-md p-6 border border-gray-100">
            <h2 class="text-2xl font-bold text-gray-900 mb-2">Economize em Petrópolis</h2>
            <p class="text-gray-600 mb-6">Digite os itens que você precisa hoje. Nosso robô vai calcular qual supermercado tem o menor preço total para a sua lista.</p>

            <!-- Formulário que envia os dados para o painel.php processar -->
            <form action="painel.php" method="POST" class="space-y-4">
                <div>
                    <label for="lista_produtos" class="block text-sm font-medium text-gray-700 mb-2">
                        Sua lista de compras (Escreva um produto por linha):
                    </label>
                    <textarea 
                        id="lista_produtos" 
                        name="lista_produtos" 
                        rows="8" 
                        class="w-full rounded-lg border-gray-300 p-3 shadow-sm border focus:border-blue-500 focus:ring-1 focus:ring-blue-500 text-gray-800 placeholder-gray-400 font-mono text-sm"
                        placeholder="Exemplo:&#10;Arroz 5kg&#10;Feijão preto&#10;Leite integral&#10;Óleo de soja"
                        required></textarea>
                </div>

                <div class="flex justify-end">
                    <button 
                        type="submit" 
                        class="bg-blue-600 hover:bg-blue-700 text-white font-medium py-3 px-6 rounded-lg shadow transition duration-150 ease-in-out w-full sm:w-auto">
                        🔍 Comparar e Montar Carrinho
                    </button>
                </div>
            </form>
        </div>
    </main>

    <!-- Rodapé -->
    <footer class="text-center py-4 text-xs text-gray-400 border-t border-gray-200 bg-white">
        &copy; 2026 Help Escambo - Inteligência de Mercado em Petrópolis.
    </footer>

</body>
</html>
