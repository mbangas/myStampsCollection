#!/bin/sh
# =============================================================================
# Script de carregamento de dados em background
# Ordem: imagens PT → catálogo ES → imagens ES
# Corre sempre em background (lançado por start_dev.sh e entrypoint.sh)
# =============================================================================

echo "🇵🇹 [BG] A iniciar download de imagens de Portugal..."
python -u tools/descarregar_imagens_pt.py

echo "🇵🇹 [BG] Imagens Portugal concluídas."
echo "🇪🇸 [BG] A importar catálogo de Espanha (StampData)..."
python -u tools/importar_selos_espanha.py --pular-se-populado

echo "🇪🇸 [BG] A iniciar download de imagens de Espanha..."
python -u tools/descarregar_imagens_es.py

echo "🇪🇸 [BG] Imagens Espanha concluídas. Carregamento total concluído."
