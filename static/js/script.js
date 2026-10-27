// Confirm before destructive actions
document.querySelectorAll("form[data-confirm]").forEach(function (form) {
  form.addEventListener("submit", function (e) {
    if (!confirm(form.dataset.confirm)) e.preventDefault();
  });
});

// Keep phone fields to digits and a leading +
document.querySelectorAll('input[type="tel"]').forEach(function (input) {
  input.addEventListener("input", function () {
    input.value = input.value.replace(/(?!^\+)[^\d]/g, "");
  });
});

// Dismiss success messages after a few seconds
setTimeout(function () {
  document.querySelectorAll(".flash.ok").forEach(function (el) { el.remove(); });
}, 4000);
