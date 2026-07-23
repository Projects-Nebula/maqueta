/* Owner's product management page — list/create/toggle/delete against
 * /api/products/. Reuses the existing wizard-image-upload endpoint for the
 * product image (same UploadedAsset model, no new image pipeline needed).
 */
(function () {
  "use strict";

  function getCsrfToken() {
    var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  var form = document.getElementById("productForm");
  var list = document.getElementById("productList");
  if (!form || !list) return;

  function renderProducts(products) {
    list.innerHTML = "";
    if (!products.length) {
      list.innerHTML = '<p class="empty-state">Todavía no creaste ningún producto.</p>';
      return;
    }
    products.forEach(function (p) {
      var row = document.createElement("div");
      row.className = "product-row";

      if (p.image_url) {
        var img = document.createElement("img");
        img.src = p.image_url;
        img.alt = "";
        row.appendChild(img);
      }

      var info = document.createElement("div");
      info.className = "product-info";
      var priceLabel = "$" + (p.price_cents / 100).toFixed(2);
      info.innerHTML =
        "<h3>" + escapeHtml(p.name) + "</h3><p>" + priceLabel +
        (p.has_digital_file ? " · descargable" : "") +
        (p.is_active ? "" : " · inactivo") + "</p>";
      row.appendChild(info);

      var toggleBtn = document.createElement("button");
      toggleBtn.type = "button";
      toggleBtn.className = "btn small";
      toggleBtn.textContent = p.is_active ? "Desactivar" : "Activar";
      toggleBtn.addEventListener("click", function () {
        toggleActive(p);
      });
      row.appendChild(toggleBtn);

      var deleteBtn = document.createElement("button");
      deleteBtn.type = "button";
      deleteBtn.className = "btn danger";
      deleteBtn.textContent = "Eliminar";
      deleteBtn.addEventListener("click", function () {
        deleteProduct(p);
      });
      row.appendChild(deleteBtn);

      list.appendChild(row);
    });
  }

  function escapeHtml(value) {
    var div = document.createElement("div");
    div.textContent = value;
    return div.innerHTML;
  }

  async function loadProducts() {
    var response = await fetch("/api/products/", { credentials: "same-origin" });
    if (response.ok) renderProducts(await response.json());
  }

  async function toggleActive(product) {
    await fetch("/api/products/" + product.id + "/", {
      method: "PATCH",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrfToken() },
      body: JSON.stringify({ is_active: !product.is_active }),
    });
    loadProducts();
  }

  async function deleteProduct(product) {
    if (!confirm("¿Eliminar " + product.name + "?")) return;
    await fetch("/api/products/" + product.id + "/", {
      method: "DELETE",
      credentials: "same-origin",
      headers: { "X-CSRFToken": getCsrfToken() },
    });
    loadProducts();
  }

  async function uploadImage(file) {
    var formData = new FormData();
    formData.append("file", file);
    var response = await fetch("/api/user-templates/wizard-images/", {
      method: "POST",
      credentials: "same-origin",
      headers: { "X-CSRFToken": getCsrfToken() },
      body: formData,
    });
    if (!response.ok) return null;
    return (await response.json()).id;
  }

  form.addEventListener("submit", async function (event) {
    event.preventDefault();
    var name = document.getElementById("productName").value.trim();
    var description = document.getElementById("productDescription").value.trim();
    var price = document.getElementById("productPrice").value;
    var imageFile = document.getElementById("productImage").files[0];
    var digitalFile = document.getElementById("productFile").files[0];
    if (!name || !price) return;

    var imageId = null;
    if (imageFile) {
      imageId = await uploadImage(imageFile);
      if (!imageId) {
        alert("No se pudo subir la imagen.");
        return;
      }
    }

    var body = new FormData();
    body.append("name", name);
    body.append("description", description);
    body.append("price_cents", price);
    if (imageId) body.append("image", imageId);
    if (digitalFile) body.append("digital_file", digitalFile);

    var response = await fetch("/api/products/", {
      method: "POST",
      credentials: "same-origin",
      headers: { "X-CSRFToken": getCsrfToken() },
      body: body,
    });
    if (!response.ok) {
      var data = await response.json().catch(function () { return {}; });
      alert("No se pudo crear el producto: " + JSON.stringify(data));
      return;
    }
    form.reset();
    loadProducts();
  });

  loadProducts();
})();
