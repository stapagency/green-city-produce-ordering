var state = {
  category: "",
  cart: []
};

var categoryTabs = document.getElementById("categoryTabs");
var catalogRoot = document.getElementById("catalog");
var searchInput = document.getElementById("searchInput");
var cartRoot = document.getElementById("cart");
var orderForm = document.getElementById("portalOrderForm");
var clearCartButton = document.getElementById("clearCart");
var saveDraftButton = document.getElementById("saveDraftButton");
var deleteDraftButton = document.getElementById("deleteDraftButton");
var statusMessage = document.getElementById("statusMessage");
var accountSummary = document.getElementById("accountSummary");
var logoutButton = document.getElementById("logoutButton");
var catalogCards = Array.prototype.slice.call(document.querySelectorAll(".item-card"));
var groupHeaders = Array.prototype.slice.call(document.querySelectorAll(".item-group-header"));
var categoryButtons = Array.prototype.slice.call(document.querySelectorAll(".tab-button"));

function setActiveCategory(category) {
  state.category = category || "";
  for (var i = 0; i < categoryButtons.length; i += 1) {
    var button = categoryButtons[i];
    button.className = button.getAttribute("data-category") === state.category ? "tab-button active" : "tab-button";
  }
  filterCards();
}

function filterCards() {
  var search = (searchInput.value || "").toLowerCase();
  var visibleCount = 0;

  for (var i = 0; i < catalogCards.length; i += 1) {
    var card = catalogCards[i];
    var matchesCategory = !state.category || card.getAttribute("data-category") === state.category;
    var text = (card.getAttribute("data-name") + " " + card.getAttribute("data-details")).toLowerCase();
    var visible = matchesCategory && text.indexOf(search) !== -1;
    card.style.display = visible ? "grid" : "none";
    if (visible) {
      visibleCount += 1;
    }
  }

  for (var j = 0; j < groupHeaders.length; j += 1) {
    var header = groupHeaders[j];
    var next = header.nextElementSibling;
    var hasVisibleChild = false;
    while (next && next.classList.contains("child-card")) {
      if (next.style.display !== "none") {
        hasVisibleChild = true;
        break;
      }
      next = next.nextElementSibling;
    }
    if (next === header.nextElementSibling) {
      header.style.display = "";
    } else {
      header.style.display = hasVisibleChild ? "block" : "none";
    }
  }

  var emptyMessage = document.getElementById("emptyCatalogMessage");
  if (!visibleCount) {
    if (!emptyMessage) {
      emptyMessage = document.createElement("p");
      emptyMessage.id = "emptyCatalogMessage";
      emptyMessage.textContent = "No items match that search.";
      catalogRoot.appendChild(emptyMessage);
    }
  } else if (emptyMessage) {
    emptyMessage.parentNode.removeChild(emptyMessage);
  }
}

function renderCart() {
  if (!state.cart.length) {
    cartRoot.className = "cart empty";
    cartRoot.innerHTML = "<p>No items added yet.</p>";
    return;
  }

  cartRoot.className = "cart";
  cartRoot.innerHTML = "";
  for (var i = 0; i < state.cart.length; i += 1) {
    (function(index) {
      var item = state.cart[index];
      var row = document.createElement("div");
      row.className = "cart-row";
      row.innerHTML = [
        "<div><strong>" + item.name + "</strong></div>",
        "<span>" + item.quantity + "</span>",
        "<span>" + item.unit + "</span>",
        '<button class="cart-remove" type="button">Remove</button>'
      ].join("");
      row.querySelector("button").addEventListener("click", function() {
        state.cart.splice(index, 1);
        renderCart();
      });
      cartRoot.appendChild(row);
    })(i);
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
    });
}

function loadDraft() {
  fetch("/api/account/draft")
    .then(function(response) {
      if (!response.ok) {
        return { draft: null };
      }
      return response.json();
    })
    .then(function(data) {
      if (!data.draft) {
        deleteDraftButton.disabled = true;
        return;
      }
      state.cart = data.draft.items || [];
      orderForm.elements.delivery_date.value = data.draft.delivery_date || "";
      orderForm.elements.notes.value = data.draft.notes || "";
      renderCart();
      deleteDraftButton.disabled = false;
      statusMessage.textContent = "A saved draft was restored.";
    });
}

function deleteDraft() {
  fetch("/api/account/draft/delete", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: "{}"
  })
    .then(function(response) {
      return response.json().then(function(result) {
        return { ok: response.ok, result: result };
      });
    })
    .then(function(data) {
      if (!data.ok) {
        statusMessage.textContent = data.result.error || "Unable to delete draft.";
        return;
      }
      deleteDraftButton.disabled = true;
      statusMessage.textContent = "Saved draft deleted.";
    })
    .catch(function() {
      statusMessage.textContent = "Unable to delete draft.";
    });
}

for (var i = 0; i < categoryButtons.length; i += 1) {
  categoryButtons[i].addEventListener("click", function(event) {
    setActiveCategory(event.currentTarget.getAttribute("data-category"));
  });
}

for (var j = 0; j < catalogCards.length; j += 1) {
  (function(card) {
    var quantityInput = card.querySelector("input");
    var unitSelect = card.querySelector("select");
    var addButton = card.querySelector(".add-button");
    addButton.addEventListener("click", function() {
      state.cart.push({
        name: addButton.getAttribute("data-item-name"),
        quantity: Number(quantityInput.value || 1),
        unit: unitSelect.value,
        notes: addButton.getAttribute("data-item-details") || ""
      });
      renderCart();
      statusMessage.textContent = addButton.getAttribute("data-item-name") + " added to the order.";
    });
  })(catalogCards[j]);
}

searchInput.addEventListener("input", filterCards);

clearCartButton.addEventListener("click", function() {
  state.cart = [];
  renderCart();
});

saveDraftButton.addEventListener("click", function() {
  if (!state.cart.length) {
    statusMessage.textContent = "Add at least one item before saving for later.";
    return;
  }

  var formData = new FormData(orderForm);
  var payload = {
    delivery_date: formData.get("delivery_date"),
    notes: formData.get("notes"),
    items: state.cart
  };

  fetch("/api/account/draft", {
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
        statusMessage.textContent = data.result.error || "Unable to save draft.";
        return;
      }
      deleteDraftButton.disabled = false;
      statusMessage.textContent = "Order saved for later.";
    })
    .catch(function() {
      statusMessage.textContent = "Unable to save draft.";
    });
});

deleteDraftButton.addEventListener("click", function() {
  deleteDraft();
});

logoutButton.addEventListener("click", function() {
  fetch("/api/logout", { method: "POST" }).then(function() {
    window.location.href = "/login";
  });
});

orderForm.addEventListener("submit", function(event) {
  event.preventDefault();
  if (!state.cart.length) {
    statusMessage.textContent = "Add at least one item before placing the order.";
    return;
  }

  var formData = new FormData(orderForm);
  var payload = {
    delivery_date: formData.get("delivery_date"),
    notes: formData.get("notes"),
    items: state.cart
  };

  fetch("/api/account/orders", {
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
        statusMessage.textContent = data.result.error || "Unable to place order.";
        return;
      }
      orderForm.reset();
      state.cart = [];
      renderCart();
      deleteDraftButton.disabled = true;
      statusMessage.textContent = "Order " + data.result.order_id + " placed. The warehouse print queue has been notified.";
    })
    .catch(function() {
      statusMessage.textContent = "Unable to place order.";
    });
});

if (categoryButtons.length) {
  setActiveCategory(categoryButtons[0].getAttribute("data-category"));
} else {
  filterCards();
}
renderCart();
loadAccount();
loadDraft();
