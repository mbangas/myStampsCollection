/**
 * Selos do Mundo – JavaScript principal
 */

document.addEventListener('DOMContentLoaded', () => {

    // ── Auto-dismiss de alertas após 5 segundos ──────────────────
    document.querySelectorAll('.alert.alert-dismissible').forEach(alerta => {
        setTimeout(() => {
            const instancia = bootstrap.Alert.getOrCreateInstance(alerta);
            instancia.close();
        }, 5000);
    });

    // ── Confirmação de remoção de itens ──────────────────────────
    document.querySelectorAll('[data-confirm]').forEach(btn => {
        btn.addEventListener('click', e => {
            const mensagem = btn.dataset.confirm || 'Tens a certeza?';
            if (!confirm(mensagem)) {
                e.preventDefault();
            }
        });
    });

    // ── Tooltip do Bootstrap ─────────────────────────────────────
    document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(el => {
        new bootstrap.Tooltip(el);
    });

});
