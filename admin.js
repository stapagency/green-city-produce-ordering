var pendingAccounts = document.getElementById("pendingAccounts");
var adminCatalog = document.getElementById("adminCatalog");
var settingsForm = document.getElementById("settingsForm");
var settingsStatus = document.getElementById("settingsStatus");
var productForm = document.getElementById("productForm");
var productStatus = document.getElementById("productStatus");
var customerAccounts = document.getElementById("customerAccounts");
var refreshCustomersButton = document.getElementById("refreshCustomers");
var logoutButton = document.getElementById("logoutButton");

function approveAccount(username) {
  fetch("/api/admin/approve-user", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: username })
  }).then(function() {
    loadPendingAccounts();
  });
}

function bindAdminActions() {
  var approveButtons = document.querySelectorAll(".approve-account");
  for (var i = 0; i < approveButtons.length; i += 1) {
    approveButtons[i].addEventListener("click", function(event) {
      approveAccount(event.currentTarget.getAttribute("data-username"));
    });
  }

  var removeButtons = document.querySelectorAll(".remove-product");
  for (var j = 0; j < removeButtons.length; j += 1) {
    removeButtons[j].addEventListener("click", function(event) {
      var button = event.currentTarget;
      fetch("/api/admin/catalog/remove", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          category: button.getAttribute("data-category"),
          parent_name: button.getAttribute("data-parent"),
          item_name: button.getAttribute("data-item")
        })
      }).then(function() {
        loadCatalog();
      });
    });
  }
}

function loadPendingAccounts() {
  fetch("/api/admin/pending-users")
    .then(function(response) { return response.json(); })
    .then(function(data) {
      if (!data.users.length) {
        pendingAccounts.innerHTML = "<p>No accounts waiting for approval.</p>";
      } else {
        window.location.reload();
      }
    });
}

function loadCatalog() {
  window.location.reload();
}

settingsForm.addEventListener("submit", function(event) {
  event.preventDefault();
  var formData = new FormData(settingsForm);
  fetch("/api/admin/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      contact_phone: formData.get("contact_phone"),
      contact_message: formData.get("contact_message")
    })
  })
    .then(function(response) {
      return response.json().then(function(result) {
        return { ok: response.ok, result: result };
      });
    })
    .then(function(data) {
      if (!data.ok) {
        settingsStatus.textContent = data.result.error || "Unable to save contact info.";
        return;
      }
      settingsStatus.textContent = "Contact info updated.";
    });
});

productForm.addEventListener("submit", function(event) {
  event.preventDefault();
  var formData = new FormData(productForm);
  fetch("/api/admin/catalog/add", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      category: formData.get("category"),
      parent_name: formData.get("parent_name"),
      item_name: formData.get("item_name"),
      details: formData.get("details"),
      units: formData.get("units")
    })
  })
    .then(function(response) {
      return response.json().then(function(result) {
        return { ok: response.ok, result: result };
      });
    })
    .then(function(data) {
      if (!data.ok) {
        productStatus.textContent = data.result.error || "Unable to add product.";
        return;
      }
      productStatus.textContent = "Product added.";
      productForm.reset();
      loadCatalog();
    });
});

logoutButton.addEventListener("click", function() {
  fetch("/api/logout", { method: "POST" }).then(function() {
    window.location.href = "/login";
  });
});

refreshCustomersButton.addEventListener("click", function() {
  window.location.reload();
});

bindAdminActions();
