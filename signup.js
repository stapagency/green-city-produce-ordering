var signupForm = document.getElementById("signupForm");
var signupStatus = document.getElementById("signupStatus");

signupForm.addEventListener("submit", function(event) {
  event.preventDefault();
  var formData = new FormData(signupForm);
  var payload = {
    customer_name: formData.get("customer_name"),
    company_name: formData.get("company_name"),
    phone: formData.get("phone"),
    email: formData.get("email"),
    username: formData.get("username"),
    password: formData.get("password")
  };

  fetch("/api/signup", {
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
        signupStatus.textContent = data.result.error || "Unable to create account.";
        return;
      }
      signupStatus.textContent = data.result.message || "Account created. It must be approved before login.";
      signupForm.reset();
    })
    .catch(function() {
      signupStatus.textContent = "Unable to create account.";
    });
});
