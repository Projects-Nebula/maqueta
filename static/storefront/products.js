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

  function feedback(message, tone) {
    if (window.AppFeedback) window.AppFeedback.show(message, { tone: tone || "info" });
  }

  function escapeHtml(value) {
    var div = document.createElement("div");
    div.textContent = value;
    return div.innerHTML;
  }

  async function responseError(response, fallback) {
    var data = await response.json().catch(function () { return {}; });
    var detail = data.detail || data.error || data.message;
    return detail ? fallback + " " + detail : fallback;
  }

  var form = document.getElementById("productForm");
  var list = document.getElementById("productList");
  var createButton = document.getElementById("createProductButton");
  if (!form || !list) return;

  function renderProducts(products) {
    list.innerHTML = "";
    list.setAttribute("aria-busy", "false");
    if (!products.length) {
      list.innerHTML = '<p class="empty-state">Todavía no creaste ningún producto. El formulario de arriba es el primer paso.</p>';
      return;
    }
    products.forEach(function (p) {
      var row = document.createElement("div");
      row.className = "product-row";

      if (p.image_url) {
        var img = document.createElement("img");
        img.src = p.image_url;
        img.alt = p.name;
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

      var actions = document.createElement("div");
      actions.className = "product-actions";

      var toggleBtn = document.createElement("button");
      toggleBtn.type = "button";
      toggleBtn.className = "btn";
      toggleBtn.textContent = p.is_active ? "Desactivar" : "Activar";
      toggleBtn.addEventListener("click", function () {
        toggleActive(p, toggleBtn);
      });
      actions.appendChild(toggleBtn);

      var deleteBtn = document.createElement("button");
      deleteBtn.type = "button";
      deleteBtn.className = "btn danger";
      deleteBtn.textContent = "Eliminar";
      deleteBtn.addEventListener("click", function () {
        deleteProduct(p, deleteBtn);
      });
      actions.appendChild(deleteBtn);
      row.appendChild(actions);

      list.appendChild(row);
    });
  }

  async function loadProducts() {
    list.setAttribute("aria-busy", "true");
    list.innerHTML = '<p class="empty-state">Cargando productos…</p>';
    try {
      var response = await fetch("/api/products/", { credentials: "same-origin" });
      if (!response.ok) throw new Error(await responseError(response, "No se pudo cargar la lista."));
      renderProducts(await response.json());
    } catch (error) {
      list.setAttribute("aria-busy", "false");
      list.innerHTML = '<p class="empty-state">No se pudieron cargar los productos. Intentá nuevamente.</p>';
      feedback(error.message || "No se pudieron cargar los productos.", "error");
    }
  }

  async function toggleActive(product, button) {
    button.disabled = true;
    var originalLabel = button.textContent;
    button.textContent = "Guardando…";
    try {
      var response = await fetch("/api/products/" + product.id + "/", {
        method: "PATCH",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrfToken() },
        body: JSON.stringify({ is_active: !product.is_active }),
      });
      if (!response.ok) throw new Error(await responseError(response, "No se pudo actualizar el producto."));
      feedback(product.is_active ? "Producto desactivado." : "Producto activado.", "success");
      await loadProducts();
    } catch (error) {
      button.disabled = false;
      button.textContent = originalLabel;
      feedback(error.message || "No se pudo actualizar el producto.", "error");
    }
  }

  async function deleteProduct(product, button) {
    if (!confirm("¿Eliminar " + product.name + "?")) return;
    button.disabled = true;
    button.textContent = "Eliminando…";
    try {
      var response = await fetch("/api/products/" + product.id + "/", {
        method: "DELETE",
        credentials: "same-origin",
        headers: { "X-CSRFToken": getCsrfToken() },
      });
      if (!response.ok) throw new Error(await responseError(response, "No se pudo eliminar el producto."));
      feedback("Producto eliminado.", "success");
      await loadProducts();
    } catch (error) {
      button.disabled = false;
      button.textContent = "Eliminar";
      feedback(error.message || "No se pudo eliminar el producto.", "error");
    }
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
    if (!response.ok) throw new Error(await responseError(response, "No se pudo subir la imagen."));
    return (await response.json()).id;
  }

  function bindFileName(inputId) {
    var input = document.getElementById(inputId);
    var label = document.querySelector('[data-file-name="' + inputId + '"]');
    if (!input || !label) return;
    input.addEventListener("change", function () {
      label.textContent = input.files && input.files[0]
        ? input.files[0].name
        : "Ningún archivo seleccionado";
    });
  }

  bindFileName("productImage");
  bindFileName("productFile");

  form.addEventListener("submit", async function (event) {
    event.preventDefault();
    if (!form.reportValidity()) return;

    var name = document.getElementById("productName").value.trim();
    var description = document.getElementById("productDescription").value.trim();
    var price = document.getElementById("productPrice").value;
    var imageFile = document.getElementById("productImage").files[0];
    var digitalFile = document.getElementById("productFile").files[0];
    if (!name || !price) return;

    createButton.disabled = true;
    createButton.textContent = "Creando…";
    try {
      var imageId = null;
      if (imageFile) imageId = await uploadImage(imageFile);

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
      if (!response.ok) throw new Error(await responseError(response, "No se pudo crear el producto."));
      form.reset();
      document.querySelectorAll("[data-file-name]").forEach(function (label) {
        label.textContent = "Ningún archivo seleccionado";
      });
      feedback("Producto creado correctamente.", "success");
      await loadProducts();
    } catch (error) {
      feedback(error.message || "No se pudo crear el producto.", "error");
    } finally {
      createButton.disabled = false;
      createButton.textContent = "Crear producto";
    }
  });

  loadProducts();
})();
