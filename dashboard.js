var profileForm = document.getElementById("profileForm");
var profileStatus = document.getElementById("profileStatus");
var accountSummary = document.getElementById("accountSummary");
var orderHistory = document.getElementById("orderHistory");
var invoiceList = document.getElementById("invoiceList");
var reportCards = document.getElementById("reportCards");
var refreshHistoryButton = document.getElementById("refreshHistory");
var refreshInvoicesButton = document.getElementById("refreshInvoices");
var refreshReportsButton = document.getElementById("refreshReports");
var logoutButton = document.getElementById("logoutButton");

function renderHistory(orders) {
  if (!orders.length) {
    orderHistory.className = "history-list empty";
    orderHistory.innerHTML = "<p>No past orders yet.</p>";
    return;
  }

  orderHistory.className = "history-list";
  orderHistory.innerHTML = "";

  for (var i = 0; i < orders.length; i += 1) {
    var order = orders[i];
    var row = document.createElement("article");
    row.className = "history-row";

    var itemSummary = [];
    for (var j = 0; j < order.items.length && j < 3; j += 1) {
      itemSummary.push(order.items[j].quantity + " " + order.items[j].unit + " " + order.items[j].name);
    }
    if (order.items.length > 3) {
      itemSummary.push("+" + (order.items.length - 3) + " more");
    }

    row.innerHTML = [
      '<div class="history-meta">',
      "<strong>Order " + order.id + "</strong>",
      "<span>" + (order.delivery_date || "No delivery date") + "</span>",
      "<span>" + order.created_at + "</span>",
      "</div>",
      '<div class="history-summary">',
      "<span>" + order.item_count + " items</span>",
      "<span>" + (order.status || "saved") + "</span>",
      "</div>",
      '<p class="history-items">' + itemSummary.join(" | ") + "</p>"
    ].join("");

    orderHistory.appendChild(row);
  }
}

function renderInvoices(invoices) {
  if (!invoices.length) {
    invoiceList.className = "history-list empty";
    invoiceList.innerHTML = "<p>No invoices yet.</p>";
    return;
  }

  invoiceList.className = "history-list";
  invoiceList.innerHTML = "";

  for (var i = 0; i < invoices.length; i += 1) {
    var invoice = invoices[i];
    var row = document.createElement("article");
    row.className = "history-row invoice-row";
    row.innerHTML = [
      '<div class="history-meta">',
      "<strong>Invoice for Order " + invoice.order_id + "</strong>",
      "<span>" + (invoice.delivery_date || "No delivery date") + "</span>",
      "</div>",
      '<div class="history-summary">',
      "<span>" + invoice.status + "</span>",
      "<span>" + invoice.item_count + " items</span>",
      "</div>",
      '<p class="history-items">Invoice is issued on delivery and remains linked to this order record.</p>'
    ].join("");
    invoiceList.appendChild(row);
  }
}

function loadAccount() {
  fetch("/api/me")
    .then(function(response) {
      if (!response.ok) {
        window.location.href = "/login";
        return null;
      }
      return response.json();
    })
    .then(function(data) {
      if (!data || !data.user) {
        return;
      }
      accountSummary.textContent = data.user.company_name + " | " + data.user.customer_name;
      profileForm.elements.customer_name.value = data.user.customer_name;
      profileForm.elements.company_name.value = data.user.company_name;
      profileForm.elements.phone.value = data.user.phone;
      profileForm.elements.email.value = data.user.email;
    });
}

function loadHistory() {
  orderHistory.className = "history-list empty";
  orderHistory.innerHTML = "<p>Loading past orders...</p>";
  fetch("/api/account/orders")
    .then(function(response) {
      if (!response.ok) {
        return { orders: [] };
      }
      return response.json();
    })
    .then(function(data) {
      renderHistory(data.orders || []);
    });
}

function loadInvoices() {
  invoiceList.className = "history-list empty";
  invoiceList.innerHTML = "<p>Loading invoices...</p>";
  fetch("/api/account/invoices")
    .then(function(response) {
      if (!response.ok) {
        return { invoices: [] };
      }
      return response.json();
    })
    .then(function(data) {
      renderInvoices(data.invoices || []);
    });
}

function loadReports() {
  reportCards.innerHTML = "<p>Loading reports...</p>";
  fetch("/api/account/reports")
    .then(function(response) {
      if (!response.ok) {
        return { html: "<p>No report data yet.</p>" };
      }
      return response.json();
    })
    .then(function(data) {
      reportCards.innerHTML = data.html || "<p>No report data yet.</p>";
    });
}

profileForm.addEventListener("submit", function(event) {
  event.preventDefault();
  var formData = new FormData(profileForm);
  var payload = {
    customer_name: formData.get("customer_name"),
    company_name: formData.get("company_name"),
    phone: formData.get("phone"),
    email: formData.get("email")
  };

  fetch("/api/account/profile", {
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
        profileStatus.textContent = data.result.error || "Unable to save changes.";
        return;
      }
      profileStatus.textContent = "Account details updated.";
      accountSummary.textContent = data.result.user.company_name + " | " + data.result.user.customer_name;
      loadHistory();
      loadInvoices();
      loadReports();
    })
    .catch(function() {
      profileStatus.textContent = "Unable to save changes.";
    });
});

refreshHistoryButton.addEventListener("click", function() {
  loadHistory();
});

refreshInvoicesButton.addEventListener("click", function() {
  loadInvoices();
});

refreshReportsButton.addEventListener("click", function() {
  loadReports();
});

logoutButton.addEventListener("click", function() {
  fetch("/api/logout", { method: "POST" }).then(function() {
    window.location.href = "/login";
  });
});

loadAccount();
loadHistory();
loadInvoices();
loadReports();
