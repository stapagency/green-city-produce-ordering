var loginForm = document.getElementById("loginForm");
var loginStatus = document.getElementById("loginStatus");

loginForm.addEventListener("submit", function(event) {
  event.preventDefault();
  var formData = new FormData(loginForm);
  var payload = {
    username: formData.get("username"),
    password: formData.get("password")
  };

  fetch("/api/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  })
    .then(function(response) {
      return response.json().then(function(result) {
        return { ok: response.ok, result: result };
      });
    })
    .then(function(data) {
      if (!data.ok) {
        loginStatus.textContent = data.result.error || "Unable to sign in.";
        return;
      }
      fetch("/api/me")
        .then(function(response) { return response.json(); })
        .then(function(me) {
          if (me.user && me.user.role === "admin") {
            window.location.href = "/admin";
            return;
          }
          window.location.href = "/portal";
        });
    })
    .catch(function() {
      loginStatus.textContent = "Unable to sign in.";
    });
});
