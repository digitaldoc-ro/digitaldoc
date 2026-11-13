// Language is encoded in the URL; both pages are generated as complete HTML.
(function () {
  function formatRon(amountMinor) {
    return (amountMinor / 100).toFixed(2) + ' RON';
  }

  function initPricingBuilder() {
    var root = document.getElementById('pricing-builder');
    if (!root) return;

    var totalEl = document.getElementById('pricing-total-value');
    var selectAll = document.getElementById('pricing-select-all-fields');
    var addons = root.querySelectorAll('[data-pricing-addon]');
    var fieldAddons = root.querySelectorAll(
      '[data-pricing-addon][data-group="fields"]'
    );

    function syncSelectAll() {
      if (!selectAll) return;
      var total = fieldAddons.length;
      var checked = 0;
      fieldAddons.forEach(function (input) {
        if (input.checked) checked += 1;
      });
      selectAll.checked = total > 0 && checked === total;
      selectAll.indeterminate = checked > 0 && checked < total;
    }

    function updateTotal() {
      var sum = 0;
      addons.forEach(function (input) {
        if (input.checked) {
          sum += Number(input.getAttribute('data-amount-minor') || 0);
        }
      });
      if (totalEl) totalEl.textContent = formatRon(sum);
      syncSelectAll();
    }

    addons.forEach(function (input) {
      input.addEventListener('change', updateTotal);
    });

    if (selectAll) {
      selectAll.addEventListener('change', function () {
        var checked = selectAll.checked;
        fieldAddons.forEach(function (input) {
          input.checked = checked;
        });
        updateTotal();
      });
    }

    updateTotal();
  }

  document.addEventListener('DOMContentLoaded', initPricingBuilder);
})();
