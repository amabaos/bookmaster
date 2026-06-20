// Подтверждение опасных действий
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-confirm]').forEach(el => {
        el.addEventListener('click', e => {
            if (!confirm(el.dataset.confirm)) e.preventDefault();
        });
    });

    // Активные табы по URL hash или ?tab=
    const params = new URLSearchParams(location.search);
    const tab = params.get('tab') || location.hash.replace('#', '');
    if (tab) {
        document.querySelectorAll('.tab').forEach(t => {
            t.classList.toggle('active', t.dataset.tab === tab);
        });
        document.querySelectorAll('.tab-pane').forEach(p => {
            p.style.display = p.id === tab ? '' : 'none';
        });
    }

    // Клик по табу
    document.querySelectorAll('.tab[data-tab]').forEach(t => {
        t.addEventListener('click', e => {
            e.preventDefault();
            const target = t.dataset.tab;
            document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
            t.classList.add('active');
            document.querySelectorAll('.tab-pane').forEach(p => {
                p.style.display = p.id === target ? '' : 'none';
            });
            history.replaceState(null, '', `?tab=${target}`);
        });
    });
});
