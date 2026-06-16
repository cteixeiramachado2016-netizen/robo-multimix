<?php
session_start();
session_destroy(); // Mata a sessão do usuário
header("Location: login.php"); // Manda de volta para o login
exit;
?>
