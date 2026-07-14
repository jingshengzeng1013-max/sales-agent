(function () {
  const state = {
    products: [],
    productInfo: null,
    results: [],
    profiles: new Map(),
    salesSuggestions: new Map(),
    selectedIndex: null,
  };

  const els = {};

  function $(id) {
    return document.getElementById(id);
  }

  function apiBase() {
    const metaBase = document.querySelector('meta[name="api-base"]');
    if (metaBase && metaBase.content) return metaBase.content.replace(/\/+$/, "");

    const portMeta = document.querySelector('meta[name="api-port"]');
    const port = portMeta && portMeta.content ? portMeta.content : "8103";
    if (window.location.protocol === "file:") return "http://127.0.0.1:" + port;
    const host = window.location.hostname || "127.0.0.1";
    return window.location.protocol + "//" + host + ":" + port;
  }

  function apiPath(path) {
    const rel = path.startsWith("/") ? path : "/" + path;
    return apiBase() + rel;
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  async function readJson(res) {
    const text = await res.text();
    let data = {};
    if (text) {
      try {
        data = JSON.parse(text);
      } catch {
        throw new Error("接口返回非 JSON");
      }
    }
    if (!res.ok) {
      const detail = data && data.detail != null ? data.detail : text || res.statusText;
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    return data;
  }

  function setStatus(message, isError) {
    els.statusLine.textContent = message || "";
    els.statusLine.classList.toggle("error", !!isError);
  }

  function setLoading(isLoading) {
    els.searchButton.disabled = isLoading;
    els.searchButton.textContent = isLoading ? "检索中..." : "检索";
  }

  function fillSelect(select, rows, placeholder, mapRow) {
    const current = select.value;
    select.innerHTML = "";
    const first = document.createElement("option");
    first.value = "";
    first.textContent = placeholder;
    select.appendChild(first);

    rows.forEach((row) => {
      const option = document.createElement("option");
      const mapped = mapRow(row);
      option.value = mapped.value;
      option.textContent = mapped.label;
      select.appendChild(option);
    });

    if (current && Array.from(select.options).some((o) => o.value === current)) {
      select.value = current;
    }
  }

  async function loadOptions() {
    setStatus("正在加载选项...");
    const [productData, filterData] = await Promise.all([
      fetch(apiPath("/api/retrieval/product-options")).then(readJson),
      fetch(apiPath("/api/retrieval/filter-options")).then(readJson),
    ]);

    state.products = productData.rows || [];
    fillSelect(els.productSelect, state.products, "请选择产品", (row) => {
      const name = row.name || row.id || "未命名产品";
      return {
        value: String(row.id || ""),
        label: row.id ? name + " (" + row.id + ")" : name,
      };
    });

    fillSelect(els.provinceSelect, filterData.provinces || [], "全部地区", (name) => ({
      value: String(name),
      label: String(name),
    }));

    fillSelect(els.noticeTypeSelect, filterData.notice_types || [], "全部公告", (name) => ({
      value: String(name),
      label: String(name),
    }));

    setStatus("");
  }

  function productName(productInfo) {
    if (!productInfo) return "";
    return productInfo.name || productInfo.product_name || productInfo.product_id || productInfo.uuid || productInfo.id || "";
  }

  function selectedProductName() {
    const product = state.products.find((p) => String(p.id) === els.productSelect.value);
    return product ? product.name || product.id : "";
  }

  function resultData(item) {
    return item && item.data && typeof item.data === "object" ? item.data : {};
  }

  function customerName(item) {
    const data = resultData(item);
    return data.buyer_name_std || data.buyer_name || data.customer_name || "未知客户";
  }

  function projectName(item) {
    const data = resultData(item);
    return data.project_name_std || data.project_name || data.document_preview || "未命名项目";
  }

  function formatScore(score) {
    const n = Number(score);
    return Number.isFinite(n) ? n.toFixed(4) : "0.0000";
  }

  function formatBudget(value, fallback) {
    const source = value != null && value !== "" ? value : fallback;
    const n = Number(source);
    if (!Number.isFinite(n) || n <= 0) return "预算未知";
    if (n >= 10000) return (n / 10000).toFixed(2) + " 万元";
    return n.toFixed(0) + " 元";
  }

  function formatDate(value) {
    const text = String(value || "").trim();
    return text ? text.slice(0, 10) : "日期未知";
  }

  async function loadProfileForResult(item) {
    const name = customerName(item);
    if (!name || name === "未知客户" || state.profiles.has(name)) return;
    try {
      const profile = await fetch(apiPath("/api/customer/profile/" + encodeURIComponent(name))).then(readJson);
      state.profiles.set(name, profile);
    } catch {
      state.profiles.set(name, null);
    }
  }

  async function submitSearch(event) {
    event.preventDefault();
    const productId = els.productSelect.value;
    if (!productId) {
      setStatus("请选择产品。", true);
      return;
    }

    setLoading(true);
    setStatus("正在检索匹配客户...");
    els.resultsList.innerHTML = "";
    els.resultSummary.hidden = true;

    try {
      const payload = {
        product_id: productId,
        province: els.provinceSelect.value || null,
        notice_type: els.noticeTypeSelect.value || null,
        top_k: Number(els.topKSelect.value) || 20,
        min_score: 0,
        use_vector: true,
        use_bm25: true,
        vector_weight: 0.5,
        bm25_weight: 0.5,
        sort_by: "score",
      };

      const data = await fetch(apiPath("/api/retrieval/search-tenders"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      }).then(readJson);

      state.productInfo = data.product_info || { name: selectedProductName(), product_id: productId };
      state.results = (data.results || []).slice().sort((a, b) => Number(b.score || 0) - Number(a.score || 0));
      state.profiles.clear();
      await Promise.all(state.results.map(loadProfileForResult));
      renderResults();
      setStatus(state.results.length ? "" : "未找到匹配客户。");
    } catch (err) {
      setStatus("检索失败：" + (err.message || err), true);
    } finally {
      setLoading(false);
    }
  }

  function renderResults() {
    els.summaryCount.textContent = String(state.results.length);
    els.summaryProduct.textContent = productName(state.productInfo) || selectedProductName();
    els.resultSummary.hidden = false;

    if (!state.results.length) {
      els.resultsList.innerHTML = '<p class="empty-state">暂无匹配结果</p>';
      return;
    }

    els.resultsList.innerHTML = state.results
      .map((item, index) => {
        const data = resultData(item);
        const profile = state.profiles.get(customerName(item));
        const contacts = profile && profile.contact_info ? profile.contact_info.contacts || [] : [];
        const contactText = contacts.length
          ? contacts
              .slice(0, 2)
              .map((c) => [c.name, c.phone].filter(Boolean).join(" "))
              .join(" / ")
          : data.contact_person || data.contact_phone || "暂无联系人";
        const place = [data.province, data.city].filter(Boolean).join(" ");
        const tags = [
          data.status || "",
          place,
          formatDate(data.publish_date || data.latest_publish_date),
        ].filter(Boolean);

        return (
          '<button class="result-card" type="button" data-index="' +
          index +
          '">' +
          '<div class="card-main">' +
          '<span class="rank">' +
          (index + 1) +
          "</span>" +
          '<div class="card-copy">' +
          '<h2 class="card-title">' +
          escapeHtml(customerName(item)) +
          "</h2>" +
          '<p class="card-subtitle">' +
          escapeHtml(projectName(item)) +
          "</p>" +
          '<div class="meta-row">' +
          '<span class="score">匹配 ' +
          escapeHtml(formatScore(item.score)) +
          "</span>" +
          '<span class="budget">' +
          escapeHtml(formatBudget(data.budget_amount, data.total_budget)) +
          "</span>" +
          "</div>" +
          '<div class="tag-row">' +
          tags.map((tag) => '<span class="tag">' + escapeHtml(tag) + "</span>").join("") +
          "</div>" +
          '<div class="customer-strip">联系人：' +
          escapeHtml(contactText) +
          "</div>" +
          "</div>" +
          "</div>" +
          "</button>"
        );
      })
      .join("");

    els.resultsList.querySelectorAll("[data-index]").forEach((card) => {
      card.addEventListener("click", () => openDetail(Number(card.dataset.index), true));
    });
  }

  function openDetail(index, pushHistory) {
    state.selectedIndex = index;
    const item = state.results[index];
    if (!item) return;
    els.searchView.classList.remove("active");
    els.detailView.classList.add("active");
    els.headerBack.style.visibility = "visible";
    els.detailScore.textContent = "匹配 " + formatScore(item.score);
    renderDetail(item);
    loadSalesSuggestions(item);
    window.scrollTo({ top: 0, behavior: "instant" });
    if (pushHistory) history.pushState({ view: "detail", index }, "", "#detail-" + index);
  }

  function showSearch(pushHistory) {
    els.detailView.classList.remove("active");
    els.searchView.classList.add("active");
    els.headerBack.style.visibility = "hidden";
    if (pushHistory) history.pushState({ view: "search" }, "", window.location.pathname);
  }

  function renderDetail(item) {
    const data = resultData(item);
    const name = customerName(item);
    const profile = state.profiles.get(name);
    const basic = profile && profile.basic_info ? profile.basic_info : {};
    const value = profile && profile.value_profile ? profile.value_profile : {};
    const demand = profile && profile.demand_profile ? profile.demand_profile : {};
    const contacts = profile && profile.contact_info ? profile.contact_info.contacts || [] : [];
    const keywords = demand.tech_keywords || data.product_keywords || [];
    const summaries = demand.technical_summaries || [data.technical_requirements_summary, data.content_summary].filter(Boolean);
    const historyItems = profile && profile.history_tenders ? profile.history_tenders.slice(0, 4) : [];
    const sourceUrl = data.detail_url || (historyItems[0] && historyItems[0].url);

    els.detailContent.innerHTML =
      '<h2 class="detail-title">' +
      escapeHtml(projectName(item)) +
      "</h2>" +
      section(
        "基本信息",
        table([
          ["采购单位", name],
          ["检索产品", productName(state.productInfo) || selectedProductName()],
          ["地区", [data.province || basic.province, data.city || basic.city].filter(Boolean).join(" ") || "未知"],
          ["公告日期", formatDate(data.publish_date || data.latest_publish_date)],
          ["预算", formatBudget(data.budget_amount, data.total_budget)],
          ["项目状态", data.status || "未知"],
        ])
      ) +
      section(
        "客户画像",
        table([
          ["客户类型", basic.customer_type || (profile && profile.has_tender_data ? "政府客户" : "未知")],
          ["历史招标", value.tender_count != null ? value.tender_count + " 次" : "未知"],
          ["累计预算", formatBudget(value.total_budget)],
          ["平均机会分", value.avg_opportunity_score != null ? String(value.avg_opportunity_score) : "未知"],
        ]) +
          chipList(keywords)
      ) +
      section("联系人", contactList(contacts, data)) +
      section("销售建议", '<div class="sales-advice" id="sales-advice-content">正在生成销售建议...</div>') +
      section("项目摘要", paragraphList(summaries)) +
      (historyItems.length ? section("历史公告", historyList(historyItems)) : "") +
      (sourceUrl
        ? section("公告原文", '<a class="source-link" href="' + escapeHtml(sourceUrl) + '" target="_blank" rel="noopener noreferrer">查看原网页</a>')
        : "");
  }

  function salesSuggestionKey(item) {
    return [item.tender_id || item.product_id || projectName(item), customerName(item)].join("::");
  }

  function buildSalesSuggestionProjectData(item) {
    const data = resultData(item);
    const name = customerName(item);
    const product = productName(state.productInfo) || selectedProductName();
    return {
      ...data,
      project_name_std: data.project_name_std || data.project_name || projectName(item),
      project_name: data.project_name || data.project_name_std || projectName(item),
      buyer_name: data.buyer_name || data.buyer_name_std || name,
      buyer_name_std: data.buyer_name_std || data.buyer_name || name,
      total_budget: data.total_budget || data.budget_amount || 0,
      budget_amount: data.budget_amount || data.total_budget || 0,
      product_keywords: data.product_keywords || (product ? [product] : []),
      matched_product_name: product,
      match_score: item.score,
    };
  }

  async function loadSalesSuggestions(item) {
    const container = $("sales-advice-content");
    if (!container) return;

    const key = salesSuggestionKey(item);
    if (state.salesSuggestions.has(key)) {
      renderSalesSuggestions(state.salesSuggestions.get(key));
      return;
    }

    container.classList.remove("error");
    container.innerHTML = '<p class="advice-loading">正在生成销售建议...</p>';

    try {
      const data = await fetch(apiPath("/api/analysis/sales-suggestions"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_data: buildSalesSuggestionProjectData(item),
          customer_name: customerName(item),
        }),
      }).then(readJson);

      const suggestions = typeof data.suggestions === "string" ? data.suggestions : "";
      state.salesSuggestions.set(key, suggestions);
      if (state.selectedIndex != null && state.results[state.selectedIndex] === item) {
        renderSalesSuggestions(suggestions);
      }
    } catch (err) {
      if (state.selectedIndex != null && state.results[state.selectedIndex] === item) {
        renderSalesSuggestionError(item, err);
      }
    }
  }

  function renderSalesSuggestions(markdown) {
    const container = $("sales-advice-content");
    if (!container) return;

    const text = String(markdown || "").trim();
    container.classList.remove("error");
    if (!text) {
      container.innerHTML = '<p class="empty-state">暂无销售建议</p>';
      return;
    }
    container.innerHTML = renderSuggestionMarkdown(text);
  }

  function renderSalesSuggestionError(item, err) {
    const container = $("sales-advice-content");
    if (!container) return;
    container.classList.add("error");
    container.innerHTML =
      '<p>销售建议生成失败：' +
      escapeHtml(err && err.message ? err.message : err) +
      "</p>" +
      '<button class="secondary-button" id="retry-sales-advice" type="button">重新生成</button>';
    const retry = $("retry-sales-advice");
    if (retry) retry.addEventListener("click", () => loadSalesSuggestions(item));
  }

  function renderSuggestionMarkdown(markdown) {
    const lines = String(markdown || "").split(/\r?\n/);
    let html = "";
    let inList = false;

    function closeList() {
      if (inList) {
        html += "</ul>";
        inList = false;
      }
    }

    lines.forEach((line) => {
      const raw = line.trim();
      if (!raw) {
        closeList();
        return;
      }

      const heading = raw.match(/^(#{2,4})\s+(.+)$/);
      if (heading) {
        closeList();
        html += '<h4 class="advice-heading">' + escapeHtml(heading[2]) + "</h4>";
        return;
      }

      const bullet = raw.match(/^[-*]\s+(.+)$/) || raw.match(/^\d+[.)]\s+(.+)$/);
      if (bullet) {
        if (!inList) {
          html += '<ul class="advice-list">';
          inList = true;
        }
        html += "<li>" + inlineMarkdown(bullet[1]) + "</li>";
        return;
      }

      closeList();
      html += '<p class="advice-paragraph">' + inlineMarkdown(raw) + "</p>";
    });

    closeList();
    return html || '<p class="empty-state">暂无销售建议</p>';
  }

  function inlineMarkdown(text) {
    return escapeHtml(text)
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/`([^`]+)`/g, "<code>$1</code>");
  }

  function section(title, body) {
    return '<section class="detail-section"><h3>' + escapeHtml(title) + "</h3>" + body + "</section>";
  }

  function table(rows) {
    return (
      '<div class="info-table">' +
      rows
        .map(
          (row) =>
            '<div class="info-row"><div class="info-label">' +
            escapeHtml(row[0]) +
            '</div><div class="info-value">' +
            escapeHtml(row[1] || "未知") +
            "</div></div>"
        )
        .join("") +
      "</div>"
    );
  }

  function chipList(values) {
    const list = (values || []).filter(Boolean).slice(0, 12);
    if (!list.length) return "";
    return '<div class="chips" style="margin-top:12px">' + list.map((v) => '<span class="chip">' + escapeHtml(v) + "</span>").join("") + "</div>";
  }

  function contactList(contacts, data) {
    const list = contacts && contacts.length ? contacts : [{ name: data.contact_person, phone: data.contact_phone }];
    const filtered = list.filter((c) => c && (c.name || c.phone));
    if (!filtered.length) return '<p class="empty-state">暂无联系人</p>';
    return (
      '<div class="contact-grid">' +
      filtered
        .slice(0, 6)
        .map((c) => {
          const phone = c.phone || "";
          return (
            '<div class="contact-card"><strong>' +
            escapeHtml(c.name || "联系人") +
            "</strong><span>" +
            escapeHtml(c.position || c.source || "") +
            "</span>" +
            (phone ? '<p><a href="tel:' + escapeHtml(phone) + '">' + escapeHtml(phone) + "</a></p>" : "") +
            "</div>"
          );
        })
        .join("") +
      "</div>"
    );
  }

  function paragraphList(values) {
    const list = (values || []).filter(Boolean).slice(0, 5);
    if (!list.length) return '<p class="empty-state">暂无摘要</p>';
    return '<ul class="paragraph-list">' + list.map((v) => "<li>" + escapeHtml(v) + "</li>").join("") + "</ul>";
  }

  function historyList(items) {
    return (
      '<ul class="paragraph-list">' +
      items
        .map((item) => {
          const title = item.project_name || "历史公告";
          const suffix = [formatDate(item.date), formatBudget(item.budget)].filter(Boolean).join(" · ");
          const label = escapeHtml(title + (suffix ? "｜" + suffix : ""));
          return item.url
            ? '<li><a class="source-link" href="' + escapeHtml(item.url) + '" target="_blank" rel="noopener noreferrer">' + label + "</a></li>"
            : "<li>" + label + "</li>";
        })
        .join("") +
      "</ul>"
    );
  }

  function bind() {
    els.searchView = $("search-view");
    els.detailView = $("detail-view");
    els.productSelect = $("product-select");
    els.provinceSelect = $("province-select");
    els.noticeTypeSelect = $("notice-type-select");
    els.topKSelect = $("top-k-select");
    els.searchForm = $("search-form");
    els.searchButton = $("search-button");
    els.resultSummary = $("result-summary");
    els.summaryCount = $("summary-count");
    els.summaryProduct = $("summary-product");
    els.statusLine = $("status-line");
    els.resultsList = $("results-list");
    els.detailBack = $("detail-back");
    els.headerBack = $("header-back");
    els.detailScore = $("detail-score");
    els.detailContent = $("detail-content");

    els.headerBack.style.visibility = "hidden";
    els.searchForm.addEventListener("submit", submitSearch);
    els.detailBack.addEventListener("click", () => history.back());
    els.headerBack.addEventListener("click", () => history.back());
    window.addEventListener("popstate", () => showSearch(false));
  }

  document.addEventListener("DOMContentLoaded", () => {
    bind();
    loadOptions().catch((err) => setStatus("选项加载失败：" + (err.message || err), true));
  });
})();
