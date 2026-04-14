document.addEventListener('DOMContentLoaded', function () {
    const inputs = document.querySelectorAll('.live-search');

    inputs.forEach(input => {
        let timer = null;

        input.addEventListener('keyup', function () {
            clearTimeout(timer);

            timer = setTimeout(() => {
                const url = input.dataset.url;
                const target = document.querySelector(input.dataset.target);
                const query = input.value;

                fetch(`${url}?q=${encodeURIComponent(query)}`, {
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                })
                .then(response => response.text())
                .then(html => {
                    target.innerHTML = html;
                });
            }, 250);
        });
    });
});