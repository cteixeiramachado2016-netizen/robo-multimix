<?php
// 1. CONTEXTO E PROTEÇÃO DE SESSÃO DA HOSTINGER
if (!session_id()) session_start();

// Se o usuário não tiver uma sessão ativa (não fez login), é chutado para a tela de login
if (!isset($_SESSION['usuario_id'])) {
    header("Location: login.php");
    exit;
}
?>
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Club Help - Painel do Assinante</title>
    <!-- Bootstrap para um visual limpo, moderno e responsivo -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <!-- Biblioteca oficial do Supabase via CDN (Leve e não pesa no seu servidor) -->
    <script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>
    <style>
        .lista-resultados {
            max-height: 350px;
            overflow-y: auto;
        }
        .font-preco {
            font-family: 'Courier New', Courier, monospace;
            font-weight: bold;
        }
    </style>
</head>
<body class="bg-light">

    <!-- BARRA DE NAVEGAÇÃO SUPERIOR -->
    <nav class="navbar navbar-dark bg-dark mb-4 shadow-sm">
        <div class="container">
            <span class="navbar-brand mb-0 h1 text-success">🛒 Club Help</span>
            <div class="d-flex align-items-center gap-3">
                <span class="text-white-50">Sócio: <strong class="text-white"><?php echo htmlspecialchars($_SESSION['usuario_nome']); ?></strong></span>
                <a href="logout.php" class="btn btn-outline-danger btn-sm">Sair / Logout</a>
            </div>
        </div>
    </nav>

    <!-- CONTEÚDO PRINCIPAL (LAYOUT LARGO) -->
    <div class="container">
        <div class="row">
            
            <!-- COLUNA ESQUERDA: BUSCA DE PRODUTOS COLETADOS PELO ROBÔ -->
            <div class="col-md-5 mb-4">
                <div class="card shadow-sm p-4 border-0">
                    <h3 class="h5 mb-3 text-secondary">🔍 Pesquisar Produtos</h3>
                    <div class="mb-3">
                        <input type="text" id="busca" class="form-control form-control-lg" placeholder="Ex: Arroz, Feijão, Leite...">
                        <div class="form-text">Digite pelo menos 2 letras para o robô buscar.</div>
                    </div>
                    
                    <!-- Lista onde os resultados do Supabase vão brotar -->
                    <div id="resultados-busca" class="list-group lista-resultados"></div>
                </div>
            </div>

            <!-- COLUNA DIREITA: MONTAGEM DA LISTA DE COMPRAS E CÁLCULO -->
            <div class="col-md-7">
                <div class="card shadow-sm p-4 border-0">
                    <h3 class="h5 mb-3 text-secondary">📋 Sua Lista de Economia</h3>
                    
                    <!-- Alerta exibido quando não tem nada no carrinho -->
                    <div id="carrinho-vazio" class="alert alert-info py-3">
                        Sua lista está vazia. Use o campo de busca ao lado para adicionar os produtos!
                    </div>

                    <!-- Itens adicionados aparecem aqui -->
                    <ul id="lista-itens" class="list-group mb-3"></ul>

                    <!-- TOTALIZADOR DA LISTA -->
                    <div class="d-flex justify-content-between align-items-center border-top pt-3 mt-2">
                        <h4 class="h5 text-muted mb-0">Valor Total Estimado:</h4>
                        <span id="total-carrinho" class="fs-3 fw-bold text-success">R$ 0,00</span>
                    </div>
                </div>
            </div>

        </div>
    </div>

    <!-- REGRA DE NEGÓCIO EM JAVASCRIPT (COMUNICAÇÃO COM O SUPABASE) -->
    <script>
        // 2. CONFIGURAÇÃO DAS CREDENCIAIS DO SUPABASE
        // IMPORTANTE: Insira aqui as chaves do seu projeto do Supabase
        const SUPABASE_URL = "https://sua-url-do-supabase.supabase.co";
        const SUPABASE_KEY = "sua-chave-anon-public";
        const _supabase = supabase.createClient(SUPABASE_URL, SUPABASE_KEY);

        const inputBusca = document.getElementById('busca');
        const divResultados = document.getElementById('resultados-busca');
        const ulLista = document.getElementById('lista-itens');
        const divVazio = document.getElementById('carrinho-vazio');
        const txtTotal = document.getElementById('total-carrinho');

        // Memória local do carrinho para renderização ultra-rápida (MVP)
        let carrinho = [];

        // 3. CAPTURA A DIGITAÇÃO E BUSCA NO HISTÓRICO DO ROBÔ
        inputBusca.addEventListener('input', async (e) => {
            const termo = e.target.value.trim();
            if (termo.length < 2) { 
                divResultados.innerHTML = ''; 
                return; 
            }

            // Realiza a query na tabela 'historico_precos' usando o termo do usuário
            const { data, error } = await _supabase
                .from('historico_precos')
                .select('id, produto, preco, mercado')
                .ilike('produto', `%${termo}%`);

            if (error) {
                console.error("Erro ao consultar Supabase:", error);
                return;
            }

            divResultados.innerHTML = '';
            
            if(data.length === 0) {
                divResultados.innerHTML = '<div class="text-muted p-2">Nenhum produto encontrado em Petrópolis.</div>';
                return;
            }

            // Remove duplicados pelo nome do produto na hora de exibir as opções de escolha
            const produtosUnicos = Array.from(new Set(data.map(p => p.produto)))
                .map(nome => data.find(p => p.produto === nome));

            // Renderiza os botões de adicionar
            produtosUnicos.forEach(prod => {
                const btn = document.createElement('button');
                btn.className = "list-group-item list-group-item-action d-flex justify-content-between align-items-center border-start-0 border-end-0 rounded-0 py-2";
                btn.innerHTML = `
                    <div>
                        <strong class="text-dark">${prod.produto}</strong><br>
                        <small class="text-muted text-uppercase">${prod.mercado}</small>
                    </div>
                    <span class="badge bg-success bg-opacity-10 text-success p-2 font-preco">
                        R$ ${prod.preco.toFixed(2)} ➕
                    </span>
                `;
                btn.onclick = () => adicionarAoCarrinho(prod);
                divResultados.appendChild(btn);
            });
        });

        // 4. ADICIONAR ITEM À LISTA
        function adicionarAoCarrinho(produto) {
            const itemExistente = carrinho.find(item => item.id === produto.id);
            if (itemExistente) {
                itemExistente.quantidade += 1;
            } else {
                carrinho.push({ ...produto, quantidade: 1 });
            }
            atualizarInterfaceCarrinho();
        }

        // 5. REMOVER ITEM DA LISTA
        window.removerDoCarrinho = function(id) {
            carrinho = carrinho.filter(item => item.id !== id);
            atualizarInterfaceCarrinho();
        }

        // 6. ATUALIZA A TELA DO CARRINHO E SOMA OS VALORES
        function atualizarInterfaceCarrinho() {
            ulLista.innerHTML = '';
            let totalGeral = 0;

            if (carrinho.length === 0) {
                divVazio.style.display = 'block';
                txtTotal.innerText = 'R$ 0,00';
                return;
            }

            divVazio.style.display = 'none';

            carrinho.forEach(item => {
                const subtotal = item.preco * item.quantidade;
                totalGeral += subtotal;

                const li = document.createElement('li');
                li.className = "list-group-item d-flex justify-content-between align-items-center py-3 border-start-0 border-end-0";
                li.innerHTML = `
                    <div>
                        <h6 class="my-0 text-dark">${item.produto}</h6>
                        <small class="text-muted">${item.mercado} | Qtd: ${item.quantidade}</small>
                    </div>
                    <div class="d-flex align-items-center gap-3">
                        <span class="text-dark fw-bold font-preco">R$ ${subtotal.toFixed(2)}</span>
                        <button class="btn btn-sm btn-link text-danger p-0 text-decoration-none" onclick="removerDoCarrinho(${item.id})">🗑️</button>
                    </div>
                `;
                ulLista.appendChild(li);
            });

            txtTotal.innerText = `R$ ${totalGeral.toFixed(2)}`;
        }
    </script>
</body>
</html>
