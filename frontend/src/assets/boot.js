(function () {
  var root = document.querySelector("fm-root");
  var boot = document.getElementById("fm-boot");
  if (!boot) return;

  function showError(message) {
    boot.className = "fm-boot fm-boot-error";
    boot.innerHTML =
      '<div class="mark">FM</div>' +
      "<h1>Fair Measure could not start</h1>" +
      "<p>" +
      (message || "The app failed while loading. Check your connection and try again.") +
      "</p>" +
      '<button type="button" id="fm-boot-retry">Retry</button>';
    var retry = document.getElementById("fm-boot-retry");
    if (retry) retry.onclick = function () { window.location.reload(); };
  }

  window.__fmShowBootError = showError;

  window.addEventListener("error", function (event) {
    if (document.documentElement.classList.contains("fm-booted")) return;
    showError(event.message || "A script failed to load.");
  });

  window.addEventListener("unhandledrejection", function (event) {
    if (document.documentElement.classList.contains("fm-booted")) return;
    var reason = event.reason;
    showError(reason && reason.message ? reason.message : "A request failed before the app started.");
  });

  window.setTimeout(function () {
    if (document.documentElement.classList.contains("fm-booted")) return;
    if (root && root.childElementCount > 1) return;
    showError("The app is taking too long. The server may still be waking up — retry in a moment.");
  }, 20000);
})();
