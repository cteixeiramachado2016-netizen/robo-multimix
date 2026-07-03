<?php
// robo-multimix/painel.php
if ($_SERVER['REQUEST_METHOD'] !== 'POST' || empty($_POST['lista_produtos'])) {
    header('Location: buscar.php');
    exit;
}

// 1. Captura a lista vinda do buscar.php e limpa as linhas
$lista_texto = trim($_POST['lista_produtos']);
$produtos_pesquisados = array_filter(array_map('trim', explode("\n", $lista_texto)));

// 2. Credenciais do seu Supabase (100% Preenchidas)
$supabase_url = 'https://zlwcizhknyuvaquwikft.supabase.co';
$supabase_key = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inpsd2Npemhrbnl1dmFxdXdpa2Z0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzk4ODM1NDQsImV4cCI6MjA5NTQ1OTU0NH0.43YWLUCG5nesLY8yW3l0oe0dbdkwmNuUXS5KnN72suo';
$tabela = 'historico_precos';

// 3. Consulta a tabela historico_precos
$url = $supabase_url . '/rest/v1/' . $tabela . '?select=mercado,produto,valor_numerico,preco_texto,data_coleta&order=data_coleta.desc';

$ch = curl_init($url);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_HTTPHEADER, [
    'apikey: ' . $supabase_key,
    'Authorization: Bearer ' . $supabase_key
]);

$response = curl_exec($ch);
$http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
curl_close($ch);

$dados_banco = [];
if ($http_code == 200) {
    $dados_banco = json_decode($response, true);
}

// 4. Cruzamento dos produtos digitados com os dados do robô
$resultados_por_mercado = [];
foreach ($produtos_pesquisados as $termo_usuario) {
    if (empty($termo_usuario)) continue;

    foreach ($dados_banco as $item_banco) {
        if (mb_stripos($item_banco['produto'], $termo_usuario) !== false) {
            $nome_mercado = $item_banco['mercado'];
            
            if (!isset($resultados_por_mercado[$nome_mercado][$termo_usuario])) {
                $resultados_por_mercado[$nome_mercado][$termo_usuario] = [
                    'produto_encontrado' => $item_banco['produto'],
                    'preco_texto' => $item_banco['preco_texto'],
                    'valor' => (float)$item_banco['valor_numerico']
                ];
            }
        }
    }
}

// 5. Montagem do ranking de economia
$ranking_mercados = [];
foreach ($resultados_por_mercado as $mercado => $itens_encontrados) {
    $total_carrinho = 0;
    foreach ($itens_encontrados as $item) {
        $total_carrinho += $item['valor'];
    }

    $ranking_mercados[] = [
        'mercado' => $mercado,
        'total' => $total_carrinho,
        'quantidade' => count($itens_encontrados)
    ];
}

usort($ranking_mercados, function ($a, $b) {
    return $a['total'] <=> $b['total'];
});
?>

<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Resultado do Comparativo - Club Help</title>
    <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
</head>
<body class="bg-gray-50 flex flex-col min-h-screen">

    <header class="bg-white shadow-sm py-4 px-6 border-b border-gray-200">
        <div class="max-w-4xl mx-auto flex justify-between items-center">
            <h1 class="text-xl font-bold text-gray-800">Help Escambo <span class="text-sm font-normal text-blue-600">Prime</span></h1>
            <a href="buscar.php" class="text-sm text-blue-600 hover:underline">← Voltar para a Busca</a>
        </div>
    </header>

    <main class="flex-grow max-w-4xl w-full mx-auto p-6 space-y-6">
        <h2 class="text-2xl font-bold text-gray-900">Resultado do Seu Carrinho</h2>
        
        <?php if (empty($ranking_mercados)): ?>
            <div class="bg-yellow-50 border border-yellow-200 text-yellow-800 p-4 rounded-lg">
                Nenhum dos produtos da sua lista foi encontrado na tabela do Supabase hoje. Tente termos mais simples!
            </div>
        <?php else: ?>
            <div class="bg-green-600 text-white rounded-xl shadow-lg p-6">
                <span class="bg-green-800 text-xs uppercase px-2 py-1 rounded font-bold">Melhor Opção Econômica 🎯</span>
                <h3 class="text-3xl font-black mt-2"><?php echo htmlspecialchars($ranking_mercados[0]['mercado']); ?></h3>
                <p class="text-green-100 mt-1">Total estimado para a sua lista:</p>
                <div class="text-4xl font-mono font-bold mt-2">R$ <?php echo number_format($ranking_mercados[0]['total'], 2, ',', '.'); ?></div>
                <p class="text-xs text-green-200 mt-2">*Encontrou <?php echo $ranking_mercados[0]['quantidade']; ?> itens da sua lista.</p>
            </div>

            <div class="space-y-4">
                <h4 class="text-lg font-bold text-gray-800">Comparativo entre os Estabelecimentos:</h4>
                
                <?php foreach ($ranking_mercados as $index => $item_ranking): ?>
                    <div class="bg-white rounded-lg shadow border border-gray-200 p-4 flex justify-between items-center">
                        <div>
                            <h5 class="font-bold text-gray-800"><?php echo htmlspecialchars($item_ranking['mercado']); ?></h5>
                            <p class="text-xs text-gray-500"><?php echo $item_ranking['quantidade']; ?> itens correspondidos</p>
                        </div>
                        <div class="text-right">
                            <span class="text-xl font-mono font-bold text-gray-900">R$ <?php echo number_format($item_ranking['total'], 2, ',', '.'); ?></span>
                            <?php if ($index > 0): ?>
                                <p class="text-xs text-red-500 font-medium">+ R$ <?php echo number_format($item_ranking['total'] - $ranking_mercados[0]['total'], 2, ',', '.'); ?></p>
                            <?php endif; ?>
                        </div>
                    </div>
                <?php endforeach; ?>
            </div>
        <?php endif; ?>
    </main>

    <footer class="text-center py-4 text-xs text-gray-400 border-t border-gray-200 bg-white">
        &copy; 2026 Help Escambo - Inteligência de Mercado em Petrópolis.
    </footer>

</body>
</html>
