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

// 3. Consulta a tabela historico_precos - CORRIGIDO para garantir método GET e JSON puro
$url = $supabase_url . '/rest/v1/' . $tabela . '?select=mercado,produto,valor_numerico,preco_texto,criado_em&order=criado_em.desc&limit=10000';

$ch = curl_init($url);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_CUSTOMREQUEST, 'GET'); // Força o método correto de busca para o Supabase
curl_setopt($ch, CURLOPT_HTTPHEADER, [
    'apikey: ' . $supabase_key,
    'Authorization: Bearer ' . $supabase_key,
    'Content-Type: application/json' // Alinha com o esperado pela API REST
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
            $valor_item = (float)$item_banco['valor_numerico'];
            
            // Pega sempre o menor preço daquele item dentro do mesmo mercado
            if (!isset($resultados_por_mercado[$nome_mercado][$termo_usuario]) || $valor_item < $resultados_por_mercado[$nome_mercado][$termo_usuario]['valor']) {
                $resultados_por_mercado[$nome_mercado][$termo_usuario] = [
                    'termo_usuario' => $termo_usuario,
                    'produto_encontrado' => $item_banco['produto'],
                    'valor' => $valor_item
                ];
            }
        }
    }
}

// 5. Montagem do ranking de economia com critério de desempate por quantidade
$ranking_mercados = [];
foreach ($resultados_por_mercado as $mercado => $itens_encontrados) {
    $total_carrinho = 0;
    foreach ($itens_encontrados as $item) {
        $total_carrinho += $item['valor'];
    }

    $ranking_mercados[] = [
        'mercado' => $mercado,
        'total' => $total_carrinho,
        'quantidade' => count($itens_encontrados),
        'detalhes' => $itens_encontrados
    ];
}

// Ordenação Inteligente: Primeiro quem tem MAIS ITENS, depois quem tem MENOR PREÇO
usort($ranking_mercados, function ($a, $b) {
    if ($a['quantidade'] === $b['quantidade']) {
        return $a['total'] <=> $b['total'];
    }
    return $b['quantidade'] <=> $a['quantidade'];
});

// Prepara o texto formatado para o WhatsApp com base no mercado vencedor
$texto_whatsapp = "";
if (!empty($ranking_mercados)) {
    $vencedor = $ranking_mercados[0];
    $texto_whatsapp = "*Club Help - Relatório de Economia* 🚀\n\n";
    $texto_whatsapp .= "🏆 *Melhor opção com base nos itens localizados:*\n";
    $texto_whatsapp .= "👉 *" . mb_strtoupper($vencedor['mercado']) . "*\n\n";
    $texto_whatsapp .= "📦 *Produtos incluídos na cotação:*\n";
    foreach ($vencedor['detalhes'] as $detalhe) {
        $texto_whatsapp .= "• " . $detalhe['termo_usuario'] . ": R$ " . number_format($detalhe['valor'], 2, ',', '.') . "\n";
    }
    $texto_whatsapp .= "\n💰 *Valor Total dos Itens Encontrados:* R$ " . number_format($vencedor['total'], 2, ',', '.') . "\n\n";
    $texto_whatsapp .= "Gerado automaticamente via helpescambo.com";
}
?>

<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Resultado do Comparativo - Club Help</title>
    <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
</head>
<body class="bg-gray-50 flex flex-col min-h-screen font-sans">

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
            <div class="bg-emerald-600 text-white rounded-2xl shadow-lg p-6 border border-emerald-700">
                <span class="bg-emerald-800 text-xs uppercase px-2 py-1 rounded font-bold tracking-wider">Melhor Opção Encontrada 🎯</span>
                <h3 class="text-2xl font-black mt-2 uppercase"><?php echo htmlspecialchars($ranking_mercados[0]['mercado']); ?></h3>
                
                <div class="my-4 bg-emerald-700/40 rounded-xl p-4 text-sm space-y-2 border border-white/10">
                    <span class="font-bold block mb-1 underline">Produtos incluídos nesta cotação:</span>
                    <?php foreach ($ranking_mercados[0]['detalhes'] as $item): ?>
                        <div class="flex justify-between border-b border-white/10 pb-1">
                            <span>• <?php echo htmlspecialchars($item['termo_usuario']); ?></span>
                            <span class="font-mono font-bold">R$ <?php echo number_format($item['valor'], 2, ',', '.'); ?></span>
                        </div>
                    <?php endforeach; ?>
                </div>

                <p class="text-emerald-100 text-xs mt-1">Valor total dos itens encontrados:</p>
                <div class="text-4xl font-mono font-black mt-1">R$ <?php echo number_format($ranking_mercados[0]['total'], 2, ',', '.'); ?></div>
                
                <button onclick="enviarWhatsApp()" class="mt-4 w-full bg-green-500 hover:bg-green-400 text-white font-bold py-3 px-4 rounded-xl flex items-center justify-center gap-2 shadow-md transition-all cursor-pointer">
                    <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24"><path d="M.057 24l1.687-6.163c-1.041-1.804-1.588-3.849-1.587-5.946C.06 5.348 5.397 0 11.966 0c3.184.001 6.177 1.24 8.43 3.496 2.253 2.256 3.491 5.253 3.491 8.442 0 6.561-5.337 11.91-11.907 11.91-2.003-.001-3.97-.504-5.729-1.464L0 24zm6.59-4.846c1.6.95 3.188 1.449 4.725 1.451 5.424 0 9.835-4.425 9.838-9.879.002-2.642-1.026-5.127-2.895-6.997-1.87-1.87-4.359-2.9-7.001-2.901-5.428 0-9.841 4.424-9.843 9.88-.001 1.636.438 3.23 1.267 4.649l-.993 3.634 3.732-.977zm11.368-6.116c-.299-.149-1.768-.874-2.043-.974-.275-.1-.475-.149-.675.149-.2.299-.775.974-.95 1.173-.175.2-.35.225-.65.075-.3-.15-1.266-.467-2.41-1.487-.89-.794-1.49-1.774-1.665-2.073-.175-.3-.019-.462.13-.611.135-.134.3-.349.45-.523.15-.174.2-.299.3-.499.1-.2.05-.375-.025-.524-.075-.15-.675-1.626-.925-2.227-.243-.584-.489-.505-.675-.514-.175-.008-.375-.01-.575-.01-.2 0-.525.075-.8.376-.275.3-.1.15-1.05 1.123s-.975 1.919-.975 3.937c0 2.019 1.465 3.961 1.665 4.23.2.27 2.881 4.4 6.98 6.17 1 .43 1.776.685 2.384.877.102.03.226.04.313.027.708-.106 2.169-.887 2.47-1.742.301-.854.301-1.587.21-1.742-.09-.153-.29-.243-.59-.393z"/></svg>
                    Compartilhar Resultado no WhatsApp
                </button>
            </div>

            <div class="space-y-4">
                <h4 class="text-lg font-bold text-gray-800">Outras Opções Analisadas:</h4>
                
                <?php foreach ($ranking_mercados as $index => $item_ranking): ?>
                    <?php if ($index === 0) continue; ?>
                    <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-4 flex justify-between items-center">
                        <div>
                            <h5 class="font-bold text-gray-800 uppercase"><?php echo htmlspecialchars($item_ranking['mercado']); ?></h5>
                            <p class="text-xs text-gray-500"><?php echo $item_ranking['quantidade']; ?> itens correspondidos</p>
                        </div>
                        <div class="text-right">
                            <span class="text-xl font-mono font-bold text-gray-900">R$ <?php echo number_format($item_ranking['total'], 2, ',', '.'); ?></span>
                            <p class="text-xs text-red-500 font-medium">+ R$ <?php echo number_format($item_ranking['total'] - $ranking_mercados[0]['total'], 2, ',', '.'); ?></p>
                        </div>
                    </div>
                <?php endforeach; ?>
            </div>
        <?php endif; ?>
    </main>

    <footer class="text-center py-4 text-xs text-gray-400 border-t border-gray-200 bg-white">
        &copy; 2026 Help Escambo - Inteligência de Mercado em Petrópolis.
    </footer>

    <script>
    function enviarWhatsApp() {
        const texto = <?php echo json_encode($texto_whatsapp); ?>;
        if (!texto) return;
        const url = `https://api.whatsapp.com/send?text=${encodeURIComponent(texto)}`;
        window.open(url, '_blank');
    }
    </script>
</body>
</html>
