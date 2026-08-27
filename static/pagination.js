(function () {
    const defaultPageSizes = [10, 20, 50, 100];

    window.createClientPagination = function createClientPagination(options) {
        const settings = {
            rowSelector: options.rowSelector,
            searchSelector: options.searchSelector,
            pageSizeSelector: options.pageSizeSelector,
            resultCountSelector: options.resultCountSelector,
            pageStatusSelector: options.pageStatusSelector,
            previousSelector: options.previousSelector,
            nextSelector: options.nextSelector,
            storageKey: options.storageKey || 'client-pagination-page-size'
        };
        const rows = Array.from(document.querySelectorAll(settings.rowSelector));
        const searchInput = document.querySelector(settings.searchSelector);
        const pageSizeSelect = document.querySelector(settings.pageSizeSelector);
        const resultCount = document.querySelector(settings.resultCountSelector);
        const pageStatus = document.querySelector(settings.pageStatusSelector);
        const previousButton = document.querySelector(settings.previousSelector);
        const nextButton = document.querySelector(settings.nextSelector);
        let currentPage = 1;

        if (!searchInput || !pageSizeSelect || !resultCount || !pageStatus || !previousButton || !nextButton) {
            return;
        }

        const savedPageSize = Number.parseInt(localStorage.getItem(settings.storageKey), 10);
        const availablePageSizes = Array.from(pageSizeSelect.options).map((option) => Number(option.value));
        const pageSizes = availablePageSizes.length ? availablePageSizes : defaultPageSizes;
        if (pageSizes.includes(savedPageSize)) {
            pageSizeSelect.value = String(savedPageSize);
        }

        function render() {
            const query = searchInput.value.trim().toLowerCase();
            const matchingRows = rows.filter((row) => (row.dataset.search || '').includes(query));
            const pageSize = Number(pageSizeSelect.value) || 50;
            const pageCount = Math.max(1, Math.ceil(matchingRows.length / pageSize));
            currentPage = Math.min(currentPage, pageCount);
            const start = (currentPage - 1) * pageSize;
            const visibleRows = new Set(matchingRows.slice(start, start + pageSize));

            rows.forEach((row) => {
                row.hidden = !visibleRows.has(row);
            });
            resultCount.textContent = `${matchingRows.length} item${matchingRows.length === 1 ? '' : 's'}`;
            pageStatus.textContent = `Page ${currentPage} of ${pageCount}`;
            previousButton.disabled = currentPage === 1;
            nextButton.disabled = currentPage === pageCount;
        }

        searchInput.addEventListener('input', () => {
            currentPage = 1;
            render();
        });
        pageSizeSelect.addEventListener('change', () => {
            localStorage.setItem(settings.storageKey, pageSizeSelect.value);
            currentPage = 1;
            render();
        });
        previousButton.addEventListener('click', () => {
            currentPage -= 1;
            render();
        });
        nextButton.addEventListener('click', () => {
            currentPage += 1;
            render();
        });
        render();
    };
})();