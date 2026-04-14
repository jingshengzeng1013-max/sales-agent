(function () {
  /**
   * 与 FastAPI 同源的 API 路径。若在子路径下反代页面与接口，在 index.html 设置
   * meta[name="api-prefix"] content="/挂载前缀"（勿尾斜杠）。
   */
  function apiPath(rel) {
    const r = rel.startsWith("/") ? rel.slice(1) : rel;
    const meta = document.querySelector('meta[name="api-prefix"]');
    const raw = meta ? meta.getAttribute("content") : null;
    const prefix = (raw != null ? String(raw) : "").trim().replace(/\/+$/, "");
    if (prefix) return prefix + "/" + r;
    return "/" + r;
  }

  /** @param {Response} res */
  async function readJsonResponse(res) {
    const text = await res.text();
    if (!text) return { data: {}, text: "" };
    try {
      return { data: JSON.parse(text), text };
    } catch {
      return { data: null, text };
    }
  }

  /** range input 数值；0 合法，勿用 `|| fallback`（会把 0 当成假值）。 */
  function readRangeWeight(elementId, fallback) {
    const el = document.getElementById(elementId);
    if (!el) return fallback;
    const n = Number(el.value);
    return Number.isFinite(n) ? n : fallback;
  }

  const output = document.getElementById("output");
  const tabs = document.querySelectorAll(".tab");
  const panels = document.querySelectorAll(".panel");

  function showTab(id) {
    tabs.forEach((t) => t.classList.toggle("active", t.dataset.tab === id));
    panels.forEach((p) => p.classList.toggle("active", p.id === "panel-" + id));
    document.body.classList.toggle(
      "wide-layout",
      id === "db" || id === "compare" || id === "intel" || id === "retrieval"
    );
  }

  function goToTab(tabId) {
    const btn = document.querySelector('.tab[data-tab="' + tabId + '"]');
    if (btn) btn.click();
  }

  let dbTablesLoaded = false;
  let llmOptionsLoaded = false;
  let extractImportFilesLoaded = false;
  let intelSnapshotFilesLoaded = false;
  /** @type {{ default_provider?: string, providers?: Array<Record<string, unknown>> } | null} */
  let llmOptionsCache = null;

  function extractOutputBasename() {
    const el = document.getElementById("extract-output-suffix");
    const suf = (el && el.value ? el.value : "").trim();
    if (suf && !/^[A-Za-z0-9_-]*$/.test(suf)) return "etl/tenders_structured.json";
    const base = suf ? "tenders_structured_" + suf + ".json" : "tenders_structured.json";
    return "etl/" + base;
  }

  function updateExtractImportPreview() {
    const el = document.getElementById("extract-import-preview");
    if (el) el.textContent = "output/" + extractOutputBasename();
  }

  function isExtractImportReplace() {
    const r = document.querySelector('input[name="extract-import-mode"]:checked');
    return !!(r && r.value === "replace");
  }

  function syncExtractImportSelectToSuffix() {
    const sel = document.getElementById("extract-import-file-select");
    if (!sel || sel.options.length === 0) return;
    const want = extractOutputBasename();
    for (let i = 0; i < sel.options.length; i++) {
      if (sel.options[i].value === want) {
        sel.selectedIndex = i;
        return;
      }
    }
  }

  async function refreshExtractImportFileSelect() {
    const sel = document.getElementById("extract-import-file-select");
    if (!sel) return;
    if (window.location.protocol === "file:") {
      sel.innerHTML = "";
      const o = document.createElement("option");
      o.value = "";
      o.textContent = "需在 HTTP 下使用";
      sel.appendChild(o);
      return;
    }
    const res = await fetch(apiPath("api/output/structured-files"));
    const { data, text } = await readJsonResponse(res);
    if (!res.ok) {
      const raw =
        data && data.detail != null
          ? data.detail
          : (text || "").trim().slice(0, 300) || res.statusText;
      throw new Error(typeof raw === "string" ? raw : JSON.stringify(raw));
    }
    if (data === null) throw new Error("列表接口返回非 JSON");
    const files = data.files || [];
    sel.innerHTML = "";
    if (!files.length) {
      const o = document.createElement("option");
      o.value = "";
      o.textContent = "（暂无 tenders_structured*.json）";
      sel.appendChild(o);
      return;
    }
    files.forEach((f) => {
      const o = document.createElement("option");
      o.value = f.name;
      const cnt = f.record_count >= 0 ? f.record_count + " 条" : "?";
      o.textContent = f.name + " (" + cnt + ")";
      sel.appendChild(o);
    });
    const want = extractOutputBasename();
    let hit = false;
    for (let i = 0; i < files.length; i++) {
      if (files[i].name === want) {
        sel.value = want;
        hit = true;
        break;
      }
    }
    if (!hit && files[0]) sel.value = files[0].name;
  }

  tabs.forEach((t) => {
    t.addEventListener("click", () => {
      const id = t.dataset.tab;
      showTab(id);
      if (id === "db" && !dbTablesLoaded) {
        dbTablesLoaded = true;
        refreshDbTables();
      }
      if (id === "extract" && !llmOptionsLoaded) {
        loadLlmOptions().catch((err) => {
          setOut("加载 LLM 线路失败：" + (err.message || err), true);
        });
      }
      if (id === "extract") {
        updateExtractImportPreview();
        if (!extractImportFilesLoaded) {
          refreshExtractImportFileSelect()
            .then(() => {
              extractImportFilesLoaded = true;
            })
            .catch((err) => {
              setOut("导入文件列表加载失败：" + (err.message || err), true);
            });
        } else {
          syncExtractImportSelectToSuffix();
        }
      }
      if (id === "intel") {
        if (!llmOptionsLoaded) {
          loadLlmOptions().catch((err) => {
            setOut("加载 LLM 线路失败：" + (err.message || err), true);
          });
        }
        if (!intelSnapshotFilesLoaded) {
          refreshIntelSnapshotFiles().catch((err) => {
            const hint = document.getElementById("intel-files-hint");
            if (hint) hint.textContent = "加载失败：" + (err.message || err);
          });
        }
      }
      if (id === "compare" && !structuredFilesLoaded) {
        refreshStructuredFiles().catch((err) => {
          const hint = document.getElementById("structured-files-hint");
          if (hint) hint.textContent = "加载失败：" + (err.message || err);
        });
      }
      if (id === "retrieval") {
        refreshRetrievalStatus().catch((err) => {
          const hint = document.getElementById("retrieval-status-hint");
          if (hint) hint.textContent = "状态加载失败：" + (err.message || err);
        });
        refreshRetrievalProductSelect().catch(() => {});
      }
    });
  });

  let structuredFilesLoaded = false;

  /** —— 混合检索 FAISS + BM25 —— */
  async function refreshRetrievalStatus() {
    const hint = document.getElementById("retrieval-status-hint");
    if (!hint) return;
    if (window.location.protocol === "file:") {
      hint.textContent =
        "需在 HTTP 下使用：python webapp/server.py → http://127.0.0.1:8103/";
      return;
    }
    hint.textContent = "检测环境与索引…";
    const res = await fetch(apiPath("api/retrieval/status"));
    const { data, text } = await readJsonResponse(res);
    if (!res.ok || data === null) {
      const raw =
        data && data.detail != null
          ? data.detail
          : (text || "").trim().slice(0, 400) || res.statusText;
      hint.textContent = "状态接口错误：" + (typeof raw === "string" ? raw : JSON.stringify(raw));
      return;
    }
    const deps = data.deps || {};
    const depLine =
      "依赖：faiss=" +
      !!deps.faiss +
      " rank_bm25=" +
      !!deps.rank_bm25 +
      " embedding_api=" +
      !!deps.embedding_api;
    const idx = data.index_files || {};
    const idxLine =
      "产品索引：" +
      (idx.faiss ? "faiss✓" : "faiss✗") +
      " " +
      (idx.bm25 ? "bm25✓" : "bm25✗") +
      " " +
      (idx.metadata ? "meta✓" : "meta✗");
    const tidx = data.tender_index_files || {};
    const tidxLine =
      "招标索引：" +
      (tidx.faiss ? "faiss✓" : "faiss✗") +
      " " +
      (tidx.bm25 ? "bm25✓" : "bm25✗") +
      " " +
      (tidx.metadata ? "meta✓" : "meta✗");
    const emb = data.api_base_url ? " | API：" + data.api_base_url : "";
    const pqHint =
      data.product_query_vecs_pkl === true
        ? " | 产品query向量pkl✓"
        : data.product_query_vecs_pkl === false
          ? " | 产品query向量pkl✗"
          : "";
    const tLoaded =
      data.tender_searcher_loaded && data.tender_indexed_documents != null
        ? " | 招标检索已载入 docs=" + data.tender_indexed_documents
        : "";
    hint.textContent =
      depLine +
      " | " +
      idxLine +
      " | " +
      tidxLine +
      " | products:" +
      (data.products_count != null ? data.products_count : "?") +
      (data.searcher_loaded ? " | 产品检索已载入" : "") +
      (data.indexed_documents != null ? " docs=" + data.indexed_documents : "") +
      pqHint +
      tLoaded +
      emb +
      (data.hint ? " | 提示：" + data.hint : "");
  }

  function collectRetrievalTenderId() {
    const manual = document.getElementById("retrieval-tender-ids-manual");
    if (manual && manual.value.trim()) {
      const parts = manual.value
        .split(/[,，\s]+/)
        .map((s) => s.trim())
        .filter(Boolean);
      for (const p of parts) {
        const id = parseInt(p, 10);
        if (id > 0) return id;
      }
    }
    const sel = document.getElementById("retrieval-tender-select");
    if (sel) {
      for (const opt of sel.selectedOptions) {
        const id = parseInt(opt.value, 10);
        if (id > 0) return id;
      }
    }
    return null;
  }

  function renderRetrievalResults(items, meta) {
    const wrap = document.getElementById("retrieval-results");
    if (!wrap) return;
    let prefix = "";
    if (meta && meta.query_source === "tender" && meta.tender_id != null) {
      const qprev = meta.query != null ? String(meta.query) : "";
      const qshort = qprev;
      const queryCardHtml = buildTenderCardPreviewHtml(qshort);
      prefix =
        '<div class="retrieval-meta-block">' +
        '<p class="muted">检索查询来自数据库 <code>tenders.id=' +
        escapeHtml(String(meta.tender_id)) +
        "</code>（服务端拼接）。</p>" +
        (qshort
          ? "<div class=\"retrieval-query-built\" style=\"margin-top: 8px;\"><strong style=\"display:block; margin-bottom: 0.5rem;\">拼接串预览：</strong>" +
            (queryCardHtml ? queryCardHtml : escapeHtml(qshort)) +
            "</div>"
          : "") +
        "</div>";
    }
    if (!items || !items.length) {
      wrap.innerHTML =
        prefix +
        '<p class="muted">无匹配结果（可调低 min_score、更换查询文本或另选招标 ID）。</p>';
      return;
    }
    let html = "";
    items.forEach((it, i) => {
      const d = it.data || {};
      const name =
        d.name != null && String(d.name).trim()
          ? String(d.name)
          : it.product_id || "（无名称）";
      const desc = d.description != null ? String(d.description) : "";
      const descShort = desc.length > 320 ? desc.slice(0, 319) + "…" : desc;
      const hasMoreDesc = desc.length > 320;
      const vs =
        it.vector_score != null && it.vector_score !== undefined
          ? "vec " + Number(it.vector_score).toFixed(4)
          : "";
      const bs =
        it.bm25_score != null && it.bm25_score !== undefined
          ? "bm25 " + Number(it.bm25_score).toFixed(4)
          : "";
      const rrfRaw =
        it.rrf_raw_score != null && it.rrf_raw_score !== undefined
          ? "rrf_raw " + Number(it.rrf_raw_score).toFixed(6)
          : "";
      const sub = [vs, bs, rrfRaw].filter(Boolean).join(" · ");
      html +=
        '<article class="retrieval-card"><h4>' +
        (i + 1) +
        ". " +
        escapeHtml(name) +
        '</h4><p class="retrieval-meta">' +
        escapeHtml(it.product_id || "") +
        " · score " +
        (typeof it.score === "number" ? it.score.toFixed(4) : it.score) +
        (sub ? " · " + escapeHtml(sub) : "") +
        "</p>";
      if (descShort) {
        html += "<p class=\"retrieval-desc retrieval-desc-short\">" + escapeHtml(descShort) + "</p>";
        if (hasMoreDesc) {
          html += "<p class=\"retrieval-desc retrieval-desc-full\">" + escapeHtml(desc) + "</p>";
        }
      }
      html += "</article>";
    });
    wrap.innerHTML = prefix + html;

    setupCardClickHandlers(wrap);
  }

  async function refreshRetrievalProductSelect() {
    const sel = document.getElementById("retrieval-tenders-product-select");
    if (!sel || window.location.protocol === "file:") return;
    try {
      const res = await fetch(apiPath("api/retrieval/product-options"));
      const { data, text } = await readJsonResponse(res);
      if (!res.ok || data === null) {
        const raw =
          data && data.detail != null
            ? data.detail
            : (text || "").trim().slice(0, 400) || res.statusText;
        throw new Error(typeof raw === "string" ? raw : JSON.stringify(raw));
      }
      const cur = sel.value;
      sel.innerHTML = "";
      const opt0 = document.createElement("option");
      opt0.value = "";
      opt0.textContent = "— 请选择产品 —";
      sel.appendChild(opt0);
      const rows = data.rows || [];
      for (const r of rows) {
        const opt = document.createElement("option");
        opt.value = String(r.id);
        const nm = r.name != null ? String(r.name) : String(r.id);
        opt.textContent = nm + " (" + r.id + ")";
        sel.appendChild(opt);
      }
      if (cur && [...sel.options].some((o) => o.value === cur)) sel.value = cur;
    } catch (err) {
      setOut("产品列表加载失败：" + (err.message || err), true);
    }
  }

  /**
   * 将「采购单位：… | 项目名称：…」类预览拆成结构化 HTML（便于卡片排版）。
   */
  function buildTenderCardPreviewHtml(previewRaw) {
    const raw = (previewRaw || "").trim();
    if (!raw) return "";
    // 使用 | 分隔符拆分（兼容全角和半角）
    const parts = raw.split(/\s*[|｜]\s*/).filter(Boolean);
    if (!parts.length) return "";
    let rows = "";
    for (let pi = 0; pi < parts.length; pi++) {
      const seg = parts[pi].trim();
      if (!seg) continue;
      const cn = seg.indexOf("：");
      const en = seg.indexOf(":");
      let cut = -1;
      if (cn >= 0 && (en < 0 || (en >= 0 && cn <= en))) cut = cn;
      else if (en >= 0) cut = en;
      let label = "";
      let val = seg;
      if (cut >= 0) {
        label = seg.slice(0, cut).trim();
        val = seg.slice(cut + 1).trim();
      }
      if (!label && !val) continue;
      rows +=
        '<div class="tender-preview-row">' +
        (label
          ? '<span class="tender-preview-label">' + escapeHtml(label) + "</span>" +
            '<span class="tender-preview-value">' +
            escapeHtml(val) +
            "</span>"
          : '<span class="tender-preview-value tender-preview-value-full">' +
            escapeHtml(val) +
            "</span>") +
        "</div>";
    }
    if (!rows) return "";
    return '<div class="tender-card-preview">' + rows + '<div class="tender-preview-expand-hint muted">点击查看完整信息 →</div></div>';
  }

  /**
   * 构建产品信息卡片 HTML（当检索来源是产品时展示）。
   */
  function buildProductInfoCardHtml(productInfo) {
    if (!productInfo) return "";

    const name = productInfo.name || productInfo.product_id || "未知产品";
    const desc = productInfo.description || "";
    const queryPreview = productInfo.query_preview || "";

    let html = '<div class="product-info-card">';
    html += '<div class="product-info-header">';
    html += '<span class="product-info-icon">📦</span>';
    html += '<span class="product-info-title">检索产品：</span>';
    html += '<strong>' + escapeHtml(name) + '</strong>';
    html += '<span class="product-info-id">(' + escapeHtml(productInfo.product_id) + ')</span>';
    html += '</div>';

    if (desc) {
      const descShort = desc.length > 200 ? desc.slice(0, 199) + "…" : desc;
      html += '<div class="product-info-row">';
      html += '<span class="product-info-label">产品描述：</span>';
      html += '<span class="product-info-value">' + escapeHtml(descShort) + '</span>';
      html += '</div>';
    }

    if (queryPreview) {
      html += '<div class="product-info-row">';
      html += '<span class="product-info-label">检索查询：</span>';
      html += '<span class="product-info-value product-info-query">' + escapeHtml(queryPreview) + '</span>';
      html += '</div>';
    }

    html += '</div>';
    return html;
  }

  function renderRetrievalTendersResults(items, meta) {
    const wrap = document.getElementById("retrieval-tenders-results");
    if (!wrap) return;
    let prefix = "";
    if (meta && meta.query) {
      const qprev = String(meta.query);
      const qshort = qprev;

      // 当检索来源是产品时，使用产品信息卡片展示
      if (meta.query_source === "product" && meta.product_id && meta.product_info) {
        prefix = buildProductInfoCardHtml(meta.product_info);
      } else {
        const src =
          meta.query_source === "product" && meta.product_id
            ? "产品 <code>" + escapeHtml(String(meta.product_id)) + "</code> 拼接"
            : "手写查询";
        const queryCardHtml = buildTenderCardPreviewHtml(qshort);
        prefix =
          '<div class="retrieval-meta-block">' +
          '<p class="muted">检索来源：' +
          src +
          "。</p>" +
          '<div class="retrieval-query-built" style="margin-top: 8px;"><strong style="display:block; margin-bottom: 0.5rem;">查询预览：</strong>' +
          (queryCardHtml ? queryCardHtml : escapeHtml(qshort)) +
          "</div></div>";
      }
    }
    if (!items || !items.length) {
      wrap.innerHTML =
        prefix +
        '<p class="muted">无匹配招标（可先运行 build_tender_faiss_index.py，或调低 min_score）。</p>';
      return;
    }
    let html = "";
    items.forEach((it, i) => {
      const d = it.data || {};
      const tid = it.tender_id != null ? String(it.tender_id) : String(it.product_id || "—");
      const cardCls = "retrieval-card tender-result-card tender-id-" + tid;
      const cardAttrs = ' class="' + cardCls + '" style="--tender-card-i: ' + i + '"';
      const buyer =
        d.buyer_name_std != null && String(d.buyer_name_std).trim()
          ? String(d.buyer_name_std)
          : "";
      // 修复：确保 document_preview 字段存在且非空字符串
      const previewRaw = d.document_preview;
      const preview = (previewRaw != null && previewRaw !== "") ? String(previewRaw) : "";
      const title = buyer ? buyer + " · #" + tid : "招标 #" + tid;
      const vs =
        it.vector_score != null && it.vector_score !== undefined
          ? "vec " + Number(it.vector_score).toFixed(4)
          : "";
      const bs =
        it.bm25_score != null && it.bm25_score !== undefined
          ? "bm25 " + Number(it.bm25_score).toFixed(4)
          : "";
      const rrfRaw =
        it.rrf_raw_score != null && it.rrf_raw_score !== undefined
          ? "rrf_raw " + Number(it.rrf_raw_score).toFixed(6)
          : "";
      const scoreStr =
        typeof it.score === "number" ? it.score.toFixed(4) : String(it.score ?? "—");
      html += "<article" + cardAttrs + ">";
      html += '<header class="tender-card-head">';
      html += '<span class="tender-card-rank" aria-hidden="true">' + (i + 1) + "</span>";
      html += '<div class="tender-card-head-main">';
      html += "<h4>" + escapeHtml(title) + "</h4>";
      html += '<div style="display: flex; align-items: center; gap: 1rem;">';
      if (d.detail_url) {
        html +=
          '<a href="' + escapeHtml(d.detail_url) + '" target="_blank" rel="noopener noreferrer" class="tender-card-link" title="跳转到原始网页" onclick="event.stopPropagation();">' +
          '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: text-bottom; margin-right: 4px;"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>' +
          '查看原网页</a>';
      }
      html += '</div>';
      html += "</div>";
      html += '<div class="tender-card-scores">';
      html +=
        '<span class="score-pill score-pill-primary" title="RRF 综合分（归一化）">' +
        escapeHtml(scoreStr) +
        "</span>";
      if (rrfRaw) {
        html +=
          '<span class="score-pill" title="RRF 原始分（未归一化）">' + escapeHtml(rrfRaw) + "</span>";
      }
      if (vs) {
        html +=
          '<span class="score-pill" title="向量分支">' + escapeHtml(vs) + "</span>";
      }
      if (bs) {
        html +=
          '<span class="score-pill" title="BM25">' + escapeHtml(bs) + "</span>";
      }
      html += "</div></header>";
      if (preview) {
        html += buildTenderCardPreviewHtml(preview);
      }
      html += "</article>";
    });
    wrap.innerHTML = prefix + '<div class="tender-cards-list">' + html + "</div>";

    setupCardClickHandlers(wrap);
  }

  function initModal() {
    const modal = document.getElementById('tender-detail-modal');
    if (!modal) return;

    const closeBtn = modal.querySelector('.modal-close');
    
    const closeModal = () => {
      modal.setAttribute('aria-hidden', 'true');
      document.body.style.overflow = '';
    };

    const openModal = () => {
      modal.setAttribute('aria-hidden', 'false');
      document.body.style.overflow = 'hidden';
    };

    closeBtn.addEventListener('click', closeModal);
    modal.addEventListener('click', (e) => {
      if (e.target === modal) closeModal();
    });
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && modal.getAttribute('aria-hidden') === 'false') {
        closeModal();
      }
    });

    window.openTenderDetailModal = openModal;
    window.closeTenderDetailModal = closeModal;
  }

  function renderDetailToModal(data) {
    const modalBody = document.getElementById('modal-body');
    const modalTitle = document.getElementById('modal-title');
    
    if (!modalBody || !modalTitle) return;

    const projectName = data.project_name || data.tender_title || '招标详情';
    modalTitle.textContent = projectName;

    const fieldLabels = {
      'tender_id': '招标ID',
      'tender_title': '招标标题',
      'project_name': '项目名称',
      'buyer_name': '采购单位',
      'buyer_name_std': '标准化采购单位',
      'province': '省份',
      'city': '城市',
      'district': '区县',
      'budget': '预算金额',
      'publish_date': '发布日期',
      'tender_type': '招标类型',
      'product_keywords': '产品关键词',
      'contact_person': '联系人',
      'contact_phone': '联系电话',
      'tender_content': '招标内容',
      'project_overview': '项目概述',
      'detail_url': '详情链接',
      'source_platform': '来源平台',
      'created_at': '创建时间',
      'updated_at': '更新时间'
    };

    let html = '';
    for (const [key, value] of Object.entries(data)) {
      if (key === 'id' || value === null || value === undefined || value === '') continue;
      
      const label = fieldLabels[key] || key;
      let displayValue = String(value);
      
      if (typeof value === 'object') {
        try {
          displayValue = JSON.stringify(value, null, 2);
        } catch {
          displayValue = String(value);
        }
      }

      html += `
        <div class="detail-row">
          <div class="detail-label">${escapeHtml(label)}</div>
          <div class="detail-value">${displayValue ? escapeHtml(displayValue) : '<span class="detail-value-empty">无数据</span>'}</div>
        </div>
      `;
    }

    modalBody.innerHTML = html || '<p class="muted">暂无数据</p>';
  }

  async function loadTenderDetail(tenderId) {
    const modalBody = document.getElementById('modal-body');
    if (modalBody) {
      modalBody.innerHTML = '<div class="modal-loading muted">加载中…</div>';
    }

    window.openTenderDetailModal();

    try {
      const res = await fetch(apiPath(`api/db/tender-detail/${tenderId}`));
      const { data, text } = await readJsonResponse(res);
      
      if (!res.ok) {
        const raw = data && data.detail != null
          ? data.detail
          : (text || "").trim().slice(0, 500) || res.statusText;
        throw new Error(typeof raw === "string" ? raw : String(raw));
      }

      if (data && data.data) {
        renderDetailToModal(data.data);
      }
    } catch (err) {
      if (modalBody) {
        modalBody.innerHTML = `<p class="muted" style="color: var(--err);">加载失败：${escapeHtml(err.message || err)}</p>`;
      }
    }
  }

  function setupCardClickHandlers(container) {
    const cards = container.querySelectorAll('.tender-result-card');
    cards.forEach(card => {
      card.style.cursor = 'pointer';
      card.setAttribute('tabindex', '0');
      card.setAttribute('role', 'button');

      card.addEventListener('click', (e) => {
        if (e.target.closest('a') || e.target.closest('button')) return;
        
        const match = card.className.match(/tender-id-(\d+)/);
        let tenderId = null;
        
        if (match) {
          tenderId = match[1];
        } else {
          const rankSpan = card.querySelector('.tender-card-rank');
          if (rankSpan && rankSpan.nextElementSibling) {
            const titleText = rankSpan.nextElementSibling.textContent || '';
            const idMatch = titleText.match(/#(\d+)/);
            if (idMatch) tenderId = idMatch[1];
          }
        }
        
        if (tenderId) {
          loadTenderDetail(tenderId);
        } else {
          setOut('无法获取招标ID', true);
        }
      });

      card.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          card.click();
        }
      });
    });

    const productCards = container.querySelectorAll('.retrieval-card:not(.tender-result-card)');
    productCards.forEach(card => {
      card.style.cursor = 'pointer';
      card.setAttribute('tabindex', '0');
      card.setAttribute('role', 'button');
      card.setAttribute('aria-expanded', 'false');

      const toggleExpand = () => {
        const isExpanded = card.classList.contains('expanded');
        card.classList.toggle('expanded');
        card.setAttribute('aria-expanded', String(!isExpanded));
      };

      card.addEventListener('click', (e) => {
        if (e.target.closest('a') || e.target.closest('button')) return;
        toggleExpand();
      });

      card.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          toggleExpand();
        }
      });
    });
  }


  async function refreshStructuredFiles() {
    const listEl = document.getElementById("structured-files-list");
    const hint = document.getElementById("structured-files-hint");
    if (!listEl) return;
    if (window.location.protocol === "file:") {
      listEl.innerHTML = '<p class="muted">需要在 HTTP 下打开：在项目 get_data 目录运行 <code>python webapp/server.py</code> 后访问 <code>http://127.0.0.1:8103/</code> 。</p>';
      if (hint) hint.textContent = "勿使用 file:// 打开本页。";
      structuredFilesLoaded = true;
      return;
    }
    if (hint) hint.textContent = "加载中…";
    const res = await fetch(apiPath("api/output/structured-files"));
    const { data, text } = await readJsonResponse(res);
    if (!res.ok) {
      const rawDetail =
        data && data.detail != null
          ? data.detail
          : (text || "").trim().slice(0, 300) || res.statusText;
      const d =
        typeof rawDetail === "string" ? rawDetail : JSON.stringify(rawDetail);
      if (res.status === 404) {
        throw new Error(
          "列表接口 404（Not Found）。请重启 webapp/server.py 后再试；若挂在子路径反代，请设置 index.html 中 api-prefix。" +
            " 详情：" +
            d
        );
      }
      throw new Error(d);
    }
    if (data === null) {
      throw new Error("列表接口返回非 JSON，请检查反代是否截断或指向了错误服务。");
    }
    listEl.innerHTML = "";
    const files = data.files || [];
    if (!files.length) {
      listEl.innerHTML = '<p class="muted">未发现 tenders_structured*.json（可先跑结构化抽取）。</p>';
      if (hint) hint.textContent = data.output_dir || "";
      structuredFilesLoaded = true;
      return;
    }
    files.forEach((f) => {
      const row = document.createElement("label");
      row.className = "compare-file-row";
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.value = f.name;
      cb.name = "structured-file";
      const meta = document.createElement("span");
      const cnt =
        f.record_count >= 0 ? `${f.record_count} 条` : "无法解析";
      meta.textContent = `${f.name}  ·  ${cnt}  ·  ${f.mtime_iso}  ·  ${f.size_bytes} B`;
      row.appendChild(cb);
      row.appendChild(meta);
      listEl.appendChild(row);
    });
    if (hint) {
      hint.textContent = `目录：${data.output_dir}  ·  共 ${files.length} 个文件`;
    }
    structuredFilesLoaded = true;
  }

  async function refreshIntelSnapshotFiles() {
    const listEl = document.getElementById("intel-files-list");
    const hint = document.getElementById("intel-files-hint");
    if (!listEl) return;
    if (window.location.protocol === "file:") {
      listEl.innerHTML =
        '<p class="muted">需在 HTTP 下打开控制台后才能加载列表。</p>';
      if (hint) hint.textContent = "";
      intelSnapshotFilesLoaded = true;
      return;
    }
    if (hint) hint.textContent = "加载中…";
    const res = await fetch(apiPath("api/output/intel-files"));
    const { data, text } = await readJsonResponse(res);
    if (!res.ok) {
      const rawDetail =
        data && data.detail != null
          ? data.detail
          : (text || "").trim().slice(0, 300) || res.statusText;
      throw new Error(typeof rawDetail === "string" ? rawDetail : JSON.stringify(rawDetail));
    }
    if (data === null) throw new Error("intel-files 返回非 JSON");
    listEl.innerHTML = "";
    const files = data.files || [];
    if (!files.length) {
      listEl.innerHTML =
        '<p class="muted">未发现 sales_intel_leads*.json（需曾手动导出或旧版保存过快照）。</p>';
      if (hint) hint.textContent = data.output_dir || "";
      intelSnapshotFilesLoaded = true;
      return;
    }
    files.forEach((f) => {
      const row = document.createElement("label");
      row.className = "compare-file-row";
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.value = f.name;
      cb.name = "intel-snapshot-file";
      const meta = document.createElement("span");
      const cnt = f.record_count >= 0 ? `${f.record_count} 条` : "无法解析";
      meta.textContent = `${f.name}  ·  ${cnt}  ·  ${f.mtime_iso}  ·  ${f.size_bytes} B`;
      row.appendChild(cb);
      row.appendChild(meta);
      listEl.appendChild(row);
    });
    if (hint) {
      hint.textContent = `目录：${data.output_dir}  ·  共 ${files.length} 个快照`;
    }
    intelSnapshotFilesLoaded = true;
  }

  function selectedIntelCompareFiles() {
    const listEl = document.getElementById("intel-files-list");
    if (!listEl) return [];
    return Array.from(
      listEl.querySelectorAll('input[name="intel-snapshot-file"]:checked')
    ).map((x) => x.value);
  }

  function selectedCompareFiles() {
    const listEl = document.getElementById("structured-files-list");
    if (!listEl) return [];
    return Array.from(listEl.querySelectorAll('input[type="checkbox"]:checked')).map((x) => x.value);
  }

  function escapeHtmlCompare(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function renderCompareResult(data) {
    const wrap = document.getElementById("compare-table-wrap");
    const status = document.getElementById("compare-status");
    if (!wrap) return;
    wrap.innerHTML = "";
    const rows = data.rows || [];
    const fields = data.fields || [];
    const files = data.files || [];
    if (status) {
      status.textContent = `对比 ${files.length} 个文件，${rows.length} 条 tender（${data.intersection_only ? "交集" : "并集"}，目录内共 ${data.total_ids_in_selection} 个 ID，截取前 ${data.truncated_to} 条）`;
    }
    if (!rows.length) {
      wrap.innerHTML = '<p class="muted">没有可展示的数据（可取消「仅共同 tender」或检查 JSON 是否含 tender_id）。</p>';
      return;
    }
    rows.forEach((row) => {
      const tid = row.tender_id;
      const byFile = row.by_file || {};
      const block = document.createElement("div");
      block.className = "compare-block";
      const h = document.createElement("h3");
      h.textContent = `tender_id = ${tid}`;
      block.appendChild(h);
      const scroll = document.createElement("div");
      scroll.className = "compare-table-scroll";
      let html = '<table class="compare-table"><thead><tr><th class="col-field">字段</th>';
      files.forEach((fn) => {
        html += "<th>" + escapeHtmlCompare(fn) + "</th>";
      });
      html += "</tr></thead><tbody>";
      fields.forEach((fld) => {
        html += "<tr><td class=\"col-field\">" + escapeHtmlCompare(fld) + "</td>";
        files.forEach((fn) => {
          const cell = byFile[fn] ? byFile[fn][fld] : null;
          if (cell === null || cell === undefined) {
            html += '<td class="cell-missing">—</td>';
          } else {
            html += "<td>" + escapeHtmlCompare(cell) + "</td>";
          }
        });
        html += "</tr>";
      });
      html += "</tbody></table>";
      scroll.innerHTML = html;
      block.appendChild(scroll);
      wrap.appendChild(block);
    });
  }

  function renderIntelCompareResult(data) {
    const wrap = document.getElementById("intel-compare-table-wrap");
    const status = document.getElementById("intel-compare-status");
    if (!wrap) return;
    wrap.innerHTML = "";
    const rows = data.rows || [];
    const fields = data.fields || [];
    const files = data.files || [];
    if (status) {
      status.textContent = `对比 ${files.length} 个快照，${rows.length} 条线索（${
        data.intersection_only ? "交集" : "并集"
      }，共 ${data.total_ids_in_selection} 个对齐键，截取前 ${data.truncated_to} 条）`;
    }
    if (!rows.length) {
      wrap.innerHTML =
        '<p class="muted">没有可展示的数据（可取消「仅共同线索」或检查快照中是否含 customer_name / project_name）。</p>';
      return;
    }
    rows.forEach((row) => {
      const tid = row.tender_id;
      const byFile = row.by_file || {};
      const block = document.createElement("div");
      block.className = "compare-block";
      const h = document.createElement("h3");
      h.textContent = `线索：${tid}`;
      block.appendChild(h);
      const scroll = document.createElement("div");
      scroll.className = "compare-table-scroll";
      let html = '<table class="compare-table"><thead><tr><th class="col-field">字段</th>';
      files.forEach((fn) => {
        html += "<th>" + escapeHtmlCompare(fn) + "</th>";
      });
      html += "</tr></thead><tbody>";
      fields.forEach((fld) => {
        html += "<tr><td class=\"col-field\">" + escapeHtmlCompare(fld) + "</td>";
        files.forEach((fn) => {
          const cell = byFile[fn] ? byFile[fn][fld] : null;
          if (cell === null || cell === undefined) {
            html += '<td class="cell-missing">—</td>';
          } else {
            html += "<td>" + escapeHtmlCompare(cell) + "</td>";
          }
        });
        html += "</tr>";
      });
      html += "</tbody></table>";
      scroll.innerHTML = html;
      block.appendChild(scroll);
      wrap.appendChild(block);
    });
  }

  const btnStructuredRefresh = document.getElementById("btn-structured-files-refresh");
  if (btnStructuredRefresh) {
    btnStructuredRefresh.addEventListener("click", async () => {
      structuredFilesLoaded = false;
      try {
        await refreshStructuredFiles();
      } catch (err) {
        const hint = document.getElementById("structured-files-hint");
        if (hint) hint.textContent = String(err.message || err);
      }
    });
  }

  const formCompare = document.getElementById("form-compare");
  if (formCompare) {
    formCompare.addEventListener("submit", async (e) => {
      e.preventDefault();
      const files = selectedCompareFiles();
      const status = document.getElementById("compare-status");
      const wrap = document.getElementById("compare-table-wrap");
      if (files.length < 1) {
        if (status) status.textContent = "请至少勾选一个 JSON 文件。";
        return;
      }
      if (status) status.textContent = "请求对比…";
      if (wrap) wrap.innerHTML = "";
      try {
        const res = await fetch(apiPath("api/output/structured/compare"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            files,
            max_tenders: Number(document.getElementById("compare-max-tenders").value) || 40,
            intersection_only: document.getElementById("compare-intersection").checked,
          }),
        });
        const { data, text } = await readJsonResponse(res);
        if (!res.ok) {
          const d =
            data && data.detail != null
              ? data.detail
              : (text || "").trim().slice(0, 300) || res.statusText;
          throw new Error(typeof d === "string" ? d : JSON.stringify(d));
        }
        if (data === null) {
          throw new Error("对比接口返回非 JSON");
        }
        renderCompareResult(data);
      } catch (err) {
        if (status) status.textContent = "错误：" + (err.message || err);
      }
    });
  }

  function syncExtractModelFromProvider() {
    const sel = document.getElementById("extract-provider");
    const modelEl = document.getElementById("extract-model");
    const datalist = document.getElementById("extract-model-list");
    if (!sel || !modelEl || !llmOptionsCache) return;
    const pid = sel.value;
    if (!pid) return;
    const p = (llmOptionsCache.providers || []).find((x) => x.id === pid);
    if (p && typeof p.default_model === "string" && p.default_model) {
      modelEl.value = p.default_model;
    }
    // 更新 datalist 选项
    if (p && Array.isArray(p.models) && p.models.length > 0) {
      datalist.innerHTML = "";
      p.models.forEach((m) => {
        const opt = document.createElement("option");
        opt.value = m.id;
        opt.textContent = m.name;
        datalist.appendChild(opt);
      });
    }
  }

  async function loadLlmOptions() {
    const res = await fetch(apiPath("api/llm/options"));
    const { data } = await readJsonResponse(res);
    if (data === null) throw new Error("LLM 选项接口返回非 JSON");
    if (!res.ok) {
      const detail = data.detail != null ? data.detail : res.statusText;
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    llmOptionsCache = data;
    const fillProviderSelect = (selId) => {
      const sel = document.getElementById(selId);
      if (!sel) return;
      sel.innerHTML = "";
      const auto = document.createElement("option");
      auto.value = "";
      auto.textContent = "自动（按模型名推断线路）";
      sel.appendChild(auto);
      (data.providers || []).forEach((p) => {
        const o = document.createElement("option");
        o.value = p.id;
        const ok = p.configured !== false;
        o.textContent = ok ? p.label : p.label + "（未配置或未就绪）";
        sel.appendChild(o);
      });
      const def = data.default_provider || "deepseek";
      if ([...sel.options].some((opt) => opt.value === def)) {
        sel.value = def;
      } else {
        sel.value = "";
      }
    };
    fillProviderSelect("extract-provider");
    // 初始化模型列表
    const datalist = document.getElementById("extract-model-list");
    if (datalist && data.providers) {
      datalist.innerHTML = "";
      data.providers.forEach((p) => {
        if (Array.isArray(p.models)) {
          p.models.forEach((m) => {
            const opt = document.createElement("option");
            opt.value = m.id;
            opt.textContent = m.name;
            datalist.appendChild(opt);
          });
        }
      });
    }
    syncExtractModelFromProvider();
    llmOptionsLoaded = true;
  }

  function setOut(text, isError) {
    output.textContent = text;
    output.classList.toggle("error", !!isError);
  }

  document.getElementById("btn-clear-output").addEventListener("click", () => {
    setOut("已清空。", false);
  });

  function appendOrSet(accumRef, chunk, isError) {
    const next = accumRef.value + chunk;
    accumRef.value = next;
    output.textContent = next;
    output.classList.toggle("error", !!isError);
    output.scrollTop = output.scrollHeight;
  }

  /** @param {string} path @param {Record<string, unknown>} jsonBody */
  async function consumeSsePost(path, jsonBody) {
    const accum = { value: "" };
    appendOrSet(accum, "连接流式接口…\n", false);
    const res = await fetch(path, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      },
      body: JSON.stringify(jsonBody),
    });
    if (!res.ok) {
      let msg = res.statusText || String(res.status);
      try {
        const j = await res.json();
        if (j.detail != null) {
          msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail, null, 2);
        }
      } catch (_) {
        try {
          msg = await res.text();
        } catch (_) {}
      }
      throw new Error(msg);
    }
    if (!res.body) {
      throw new Error("响应无 body");
    }
    const reader = res.body.getReader();
    const dec = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += dec.decode(value, { stream: true });
      let sep;
      while ((sep = buffer.indexOf("\n\n")) >= 0) {
        const block = buffer.slice(0, sep);
        buffer = buffer.slice(sep + 2);
        for (const line of block.split("\n")) {
          if (!line.startsWith("data: ")) continue;
          let obj;
          try {
            obj = JSON.parse(line.slice(6));
          } catch {
            continue;
          }
          if (obj.type === "log" && obj.text != null) {
            appendOrSet(accum, obj.text, false);
          } else if (obj.type === "error") {
            appendOrSet(accum, "\n\n[错误] " + (obj.message || "") + "\n", true);
            if (obj.log_file) appendOrSet(accum, "日志文件: " + obj.log_file + "\n", true);
          } else if (obj.type === "done") {
            appendOrSet(accum, "\n\n--- 结果 JSON ---\n" + JSON.stringify(obj.result, null, 2) + "\n", false);
            if (obj.log_file) appendOrSet(accum, "\n(会话日志: " + obj.log_file + ")\n", false);
          }
        }
      }
    }
  }

  document
    .getElementById("btn-pipeline-goto-crawl")
    ?.addEventListener("click", () => goToTab("crawl"));
  document
    .getElementById("btn-pipeline-goto-extract")
    ?.addEventListener("click", () => goToTab("extract"));
  document
    .getElementById("btn-pipeline-goto-db")
    ?.addEventListener("click", () => goToTab("db"));
  document
    .getElementById("btn-pipeline-goto-compare")
    ?.addEventListener("click", () => goToTab("compare"));
  document
    .getElementById("btn-pipeline-goto-retrieval")
    ?.addEventListener("click", () => goToTab("retrieval"));

  const btnIntelFilesRefresh = document.getElementById("btn-intel-files-refresh");
  if (btnIntelFilesRefresh) {
    btnIntelFilesRefresh.addEventListener("click", async () => {
      intelSnapshotFilesLoaded = false;
      try {
        await refreshIntelSnapshotFiles();
      } catch (err) {
        const hint = document.getElementById("intel-files-hint");
        if (hint) hint.textContent = String(err.message || err);
      }
    });
  }

  const formIntelCompare = document.getElementById("form-intel-compare");
  if (formIntelCompare) {
    formIntelCompare.addEventListener("submit", async (e) => {
      e.preventDefault();
      const files = selectedIntelCompareFiles();
      const status = document.getElementById("intel-compare-status");
      const wrap = document.getElementById("intel-compare-table-wrap");
      if (files.length < 1) {
        if (status) status.textContent = "请至少勾选一个快照文件。";
        return;
      }
      if (status) status.textContent = "请求对比…";
      if (wrap) wrap.innerHTML = "";
      try {
        const res = await fetch(apiPath("api/output/intel/compare"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            files,
            max_rows: Number(document.getElementById("intel-compare-max-rows").value) || 40,
            intersection_only: document.getElementById("intel-compare-intersection").checked,
          }),
        });
        const { data, text } = await readJsonResponse(res);
        if (!res.ok) {
          const d =
            data && data.detail != null
              ? data.detail
              : (text || "").trim().slice(0, 300) || res.statusText;
          throw new Error(typeof d === "string" ? d : JSON.stringify(d));
        }
        if (data === null) throw new Error("对比接口返回非 JSON");
        renderIntelCompareResult(data);
      } catch (err) {
        if (status) status.textContent = "错误：" + (err.message || err);
      }
    });
  }

  async function loadCrawlDefaults() {
    const res = await fetch(apiPath("api/crawl/defaults"));
    if (!res.ok) throw new Error("拉取默认配置失败");
    const data = await res.json();
    const d = data.defaults || {};
    const set = (id, v) => {
      const el = document.getElementById(id);
      if (el && v !== undefined && v !== null) el.value = v;
    };
    set("crawl-keyword", d.keyword);
    set("crawl-base-url", d.base_url);
    set("crawl-delay-min", d.delay_min);
    set("crawl-delay-max", d.delay_max);
    set("crawl-max-pages", d.max_pages);
    set("crawl-timeout", d.timeout);
    set("crawl-searchtype", d.searchtype);
    set("crawl-bid-sort", d.bidSort);
    set("crawl-time-type", d.time_type);
    set("crawl-start-time", d.start_time);
    set("crawl-end-time", d.end_time || "");
    set("crawl-detail-limit", d.detail_limit);
    set("crawl-detail-dmin", d.detail_delay_min);
    set("crawl-detail-dmax", d.detail_delay_max);
    set("crawl-detail-timeout", d.detail_timeout);
    set("crawl-json-path", d.json_path || "");
    document.getElementById("crawl-run-list").checked = !!d.run_list;
    document.getElementById("crawl-run-import").checked = !!d.run_import;
    document.getElementById("crawl-run-detail").checked = !!d.run_detail;
  }

  document.getElementById("btn-crawl-defaults").addEventListener("click", async () => {
    try {
      await loadCrawlDefaults();
      setOut("已填充爬虫默认参数（来自 config）", false);
    } catch (err) {
      setOut(String(err.message || err), true);
    }
  });

  const extractProv = document.getElementById("extract-provider");
  if (extractProv) {
    extractProv.addEventListener("change", syncExtractModelFromProvider);
  }
  const btnExtractLlmRefresh = document.getElementById("btn-extract-llm-refresh");
  if (btnExtractLlmRefresh) {
    btnExtractLlmRefresh.addEventListener("click", async () => {
      llmOptionsLoaded = false;
      try {
        await loadLlmOptions();
        setOut("已刷新 LLM 线路（.env 中的默认模型与 base_url）。", false);
      } catch (err) {
        setOut(String(err.message || err), true);
      }
    });
  }

  const sufExtract = document.getElementById("extract-output-suffix");
  if (sufExtract) {
    sufExtract.addEventListener("input", () => {
      updateExtractImportPreview();
      syncExtractImportSelectToSuffix();
    });
  }

  const btnExtractImportRefresh = document.getElementById("btn-extract-import-refresh");
  if (btnExtractImportRefresh) {
    btnExtractImportRefresh.addEventListener("click", async () => {
      try {
        await refreshExtractImportFileSelect();
        extractImportFilesLoaded = true;
        syncExtractImportSelectToSuffix();
        setOut("已刷新 output 下 tenders_structured*.json 列表。", false);
      } catch (err) {
        setOut(String(err.message || err), true);
      }
    });
  }

  const btnImportStructuredOnly = document.getElementById("btn-import-structured-only");
  if (btnImportStructuredOnly) {
    btnImportStructuredOnly.addEventListener("click", async () => {
      setOut("", false);
      const sel = document.getElementById("extract-import-file-select");
      const bn = sel && sel.value ? String(sel.value).trim() : "";
      if (!bn) {
        setOut("请先点击「刷新列表」并选择要导入的 JSON。", true);
        return;
      }
      try {
        await consumeSsePost(apiPath("api/import/structured/stream"), {
          import_basename: bn,
          replace: isExtractImportReplace(),
        });
      } catch (err) {
        setOut(String(err.message || err), true);
      }
    });
  }

  const formExtract = document.getElementById("form-extract");
  if (formExtract) {
    formExtract.addEventListener("submit", async (e) => {
      e.preventDefault();
      setOut("", false);
      const body = {
        limit: Number(document.getElementById("extract-limit").value) || 20,
        use_llm: document.getElementById("extract-use-llm").checked,
        provider: (document.getElementById("extract-provider").value || "").trim(),
        model: (document.getElementById("extract-model").value || "").trim() || "deepseek-chat",
        run_import: document.getElementById("extract-run-import").checked,
        import_replace: isExtractImportReplace(),
        output_suffix: (document.getElementById("extract-output-suffix").value || "").trim(),
      };
      try {
        await consumeSsePost(apiPath("api/extract/structured/stream"), body);
      } catch (err) {
        setOut(String(err.message || err), true);
      }
    });
  }

  document.getElementById("form-crawl").addEventListener("submit", async (e) => {
    e.preventDefault();
    setOut("", false);
    const num = (id, fallback) => {
      const raw = document.getElementById(id).value.trim();
      if (raw === "") return fallback;
      const n = Number(raw);
      return Number.isFinite(n) ? n : fallback;
    };
    const body = {
      keyword: document.getElementById("crawl-keyword").value.trim(),
      base_url: document.getElementById("crawl-base-url").value.trim(),
      delay_min: num("crawl-delay-min", 2),
      delay_max: num("crawl-delay-max", 5),
      max_pages: num("crawl-max-pages", 3),
      timeout: num("crawl-timeout", 30),
      searchtype: document.getElementById("crawl-searchtype").value.trim(),
      bidSort: document.getElementById("crawl-bid-sort").value.trim(),
      time_type: document.getElementById("crawl-time-type").value.trim(),
      start_time: document.getElementById("crawl-start-time").value.trim(),
      end_time: document.getElementById("crawl-end-time").value.trim(),
      detail_limit: num("crawl-detail-limit", 0),
      detail_delay_min: num("crawl-detail-dmin", 2),
      detail_delay_max: num("crawl-detail-dmax", 5),
      detail_timeout: num("crawl-detail-timeout", 30),
      run_list: document.getElementById("crawl-run-list").checked,
      run_import: document.getElementById("crawl-run-import").checked,
      run_detail: document.getElementById("crawl-run-detail").checked,
      json_path: document.getElementById("crawl-json-path").value.trim(),
    };
    try {
      await consumeSsePost(apiPath("api/crawl/workflow/stream"), body);
    } catch (err) {
      setOut(String(err.message || err), true);
    }
  });

  /* —— SQLite 浏览 —— */
  const dbTableSelect = document.getElementById("db-table-select");
  const dbStatus = document.getElementById("db-status");
  const dbTableWrap = document.getElementById("db-table-wrap");

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  async function refreshDbTables() {
    if (!dbTableSelect) return;
    if (window.location.protocol === "file:") {
      if (dbStatus)
        dbStatus.textContent =
          "勿使用 file:// 打开本页。请在项目 get_data 下运行 python webapp/server.py，访问 http://127.0.0.1:8103/";
      setOut(
        "SQLite 浏览需在 HTTP 下打开：python webapp/server.py → http://127.0.0.1:8103/",
        true
      );
      return;
    }
    if (dbStatus) dbStatus.textContent = "加载表列表…";
    try {
      const res = await fetch(apiPath("api/db/tables"));
      const { data } = await readJsonResponse(res);
      if (data === null) throw new Error("表列表接口返回非 JSON");
      if (!res.ok) {
        const detail = data.detail != null ? data.detail : res.statusText;
        throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
      }
      dbTableSelect.innerHTML = "";
      const tables = data.tables || [];
      if (!tables.length) {
        const o = document.createElement("option");
        o.value = "";
        o.textContent = "（无表）";
        dbTableSelect.appendChild(o);
        const msg =
          (data.db_path || "") + " — " + (data.hint || "当前无任何用户表");
        if (dbStatus) dbStatus.textContent = msg;
        setOut("SQLite 表列表：0 张。" + (data.hint ? " " + data.hint : ""), false);
        return;
      }
      tables.forEach((name) => {
        const o = document.createElement("option");
        o.value = name;
        o.textContent = name;
        dbTableSelect.appendChild(o);
      });
      const line =
        "库：" + data.db_path + "，共 " + tables.length + " 张表（选择表后点「加载数据」）";
      if (dbStatus) dbStatus.textContent = line;
      setOut("SQLite：" + tables.length + " 张表已加载到下拉框。", false);
    } catch (err) {
      const emsg = err.message || err;
      if (dbStatus) dbStatus.textContent = "错误：" + emsg;
      setOut("加载表列表失败：" + emsg, true);
    }
  }

  function renderDbTable(data) {
    const cols = data.columns || [];
    const rows = data.rows || [];
    if (!cols.length) {
      dbTableWrap.innerHTML = '<p class="muted">该表无列。</p>';
      return;
    }
    let html = '<table class="db-table"><thead><tr>';
    cols.forEach((c) => {
      html += "<th>" + escapeHtml(c) + "</th>";
    });
    html += "</tr></thead><tbody>";
    rows.forEach((row) => {
      html += "<tr>";
      cols.forEach((c) => {
        const v = row[c];
        if (v === null || v === undefined) {
          html += '<td><div class="db-cell-content cell-null">NULL</div></td>';
        } else {
          html += '<td><div class="db-cell-content">' + escapeHtml(v) + "</div></td>";
        }
      });
      html += "</tr>";
    });
    html += "</tbody></table>";
    if (!rows.length) {
      html += '<p class="muted" style="padding:0.75rem">0 行（可调整 offset 或表为空）。</p>';
    }
    dbTableWrap.innerHTML = html;
  }

  async function loadDbRows() {
    if (!dbTableSelect) return;
    const table = dbTableSelect.value;
    if (!table) {
      if (dbStatus) dbStatus.textContent = "请先刷新表列表并选择表";
      setOut("数据库：请先在上方选择表或点击「刷新表列表」。", true);
      return;
    }
    const limit = Number(document.getElementById("db-limit").value) || 50;
    const offset = Number(document.getElementById("db-offset").value) || 0;
    if (dbStatus) dbStatus.textContent = "加载中…";
    try {
      const q = new URLSearchParams({ limit: String(limit), offset: String(offset) });
      const res = await fetch(apiPath("api/db/table/" + encodeURIComponent(table) + "?" + q));
      const { data } = await readJsonResponse(res);
      if (data === null) throw new Error("表数据接口返回非 JSON");
      if (!res.ok) {
        const detail = data.detail != null ? data.detail : res.statusText;
        throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
      }
      renderDbTable(data);
      const n = (data.rows || []).length;
      const total = data.total != null ? data.total : 0;
      const end = total === 0 ? 0 : Math.min(offset + n, total);
      const start = n === 0 ? 0 : offset + 1;
      const statusLine =
        "库：" +
        data.db_path +
        " | 表：" +
        data.table +
        " | 行：" +
        start +
        "–" +
        end +
        " / 共 " +
        total +
        " 条";
      if (dbStatus) dbStatus.textContent = statusLine;
      setOut(
        "已加载表 " + data.table + "：" + start + "–" + end + " / 共 " + total + " 条。",
        false
      );
    } catch (err) {
      dbTableWrap.innerHTML = "";
      const emsg = err.message || err;
      if (dbStatus) dbStatus.textContent = "错误：" + emsg;
      setOut("加载表数据失败：" + emsg, true);
    }
  }

  const formDb = document.getElementById("form-db");
  if (formDb) formDb.addEventListener("submit", (e) => e.preventDefault());
  const btnDbRefresh = document.getElementById("btn-db-refresh-tables");
  const btnDbLoad = document.getElementById("btn-db-load");
  if (btnDbRefresh) btnDbRefresh.addEventListener("click", () => refreshDbTables());
  if (btnDbLoad) btnDbLoad.addEventListener("click", () => loadDbRows());

  const btnRetrievalLoadTenders = document.getElementById("btn-retrieval-load-tenders");
  if (btnRetrievalLoadTenders) {
    btnRetrievalLoadTenders.addEventListener("click", async () => {
      const sel = document.getElementById("retrieval-tender-select");
      if (!sel) return;
      try {
        const res = await fetch(apiPath("api/intel/tender-options?limit=300"));
        const data = await res.json();
        if (!res.ok) {
          const msg =
            (data && data.detail != null
              ? data.detail
              : res.statusText) || "请求失败";
          throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
        }
        sel.innerHTML = "";
        const rows = data.rows || [];
        for (const r of rows) {
          const opt = document.createElement("option");
          opt.value = String(r.id);
          opt.textContent = r.label || "#" + r.id;
          sel.appendChild(opt);
        }
        setOut("混合检索：已加载 " + rows.length + " 条已结构化招标。", false);
      } catch (err) {
        setOut(String(err.message || err), true);
      }
    });
  }

  const formRetrieval = document.getElementById("form-retrieval");
  if (formRetrieval) {
    formRetrieval.addEventListener("submit", async (e) => {
      e.preventDefault();
      const qel = document.getElementById("retrieval-query");
      const query = (qel && qel.value ? qel.value : "").trim();
      const tenderId = collectRetrievalTenderId();
      if (!tenderId && !query) {
        setOut("混合检索：请从数据库选择/填写招标 ID，或输入查询文本。", true);
        return;
      }
      const topK = Number(document.getElementById("retrieval-top-k").value) || 10;
      const minScore = Number(document.getElementById("retrieval-min-score").value) || 0;
      const useVector = document.getElementById("retrieval-use-vector").checked;
      const useBm25 = document.getElementById("retrieval-use-bm25").checked;
      const vectorWeight = readRangeWeight("retrieval-vector-weight", 0.5);
      const bm25Weight = readRangeWeight("retrieval-bm25-weight", 0.5);
      setOut("混合检索请求已发送（首次可能加载模型，请稍候）…", false);
      const wrapBusy = document.getElementById("retrieval-results");
      if (wrapBusy) wrapBusy.innerHTML = '<p class="muted">检索中…</p>';
      try {
        const payload = {
          query,
          top_k: topK,
          min_score: minScore,
          use_vector: useVector,
          use_bm25: useBm25,
          vector_weight: vectorWeight,
          bm25_weight: bm25Weight,
        };
        if (tenderId != null) payload.tender_id = tenderId;
        const res = await fetch(apiPath("api/retrieval/search"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const { data, text } = await readJsonResponse(res);
        if (!res.ok) {
          let raw =
            data && data.detail != null
              ? data.detail
              : (text || "").trim().slice(0, 500) || res.statusText;
          if (typeof raw === "object") raw = JSON.stringify(raw);
          throw new Error(typeof raw === "string" ? raw : String(raw));
        }
        if (data === null) throw new Error("检索接口返回非 JSON");
        const results = data.results || [];
        const srcNote =
          data.query_source === "tender" && data.tender_id != null
            ? "（来自 tender #" + data.tender_id + "）"
            : "";
        setOut("混合检索完成，命中 " + results.length + " 条" + srcNote + "。", false);
        renderRetrievalResults(results, {
          query_source: data.query_source,
          tender_id: data.tender_id,
          query: data.query,
        });
      } catch (err) {
        setOut("混合检索失败：" + (err.message || err), true);
        const wrapErr = document.getElementById("retrieval-results");
        if (wrapErr) wrapErr.innerHTML = "";
      }
    });
  }
  const btnRetrievalRefresh = document.getElementById("btn-retrieval-refresh-status");
  if (btnRetrievalRefresh) {
    btnRetrievalRefresh.addEventListener("click", () => {
      refreshRetrievalStatus().catch(() => {});
    });
  }

  const retTendersResults = document.getElementById("retrieval-tenders-results");

  const btnRetrievalTendersLoadProducts = document.getElementById("btn-retrieval-tenders-load-products");
  if (btnRetrievalTendersLoadProducts) {
    btnRetrievalTendersLoadProducts.addEventListener("click", () => {
      refreshRetrievalProductSelect().catch(() => {});
    });
  }

  const formRetrievalTenders = document.getElementById("form-retrieval-tenders");
  if (formRetrievalTenders) {
    formRetrievalTenders.addEventListener("submit", async (e) => {
      e.preventDefault();
      const sel = document.getElementById("retrieval-tenders-product-select");
      const productId = sel && sel.value ? sel.value.trim() : "";
      if (!productId) {
        setOut("请选择一个产品。", true);
        return;
      }
      const query = ""; // No handwritten query anymore
      const topK = Number(document.getElementById("retrieval-tenders-top-k").value) || 10;
      const minScore = Number(document.getElementById("retrieval-tenders-min-score").value) || 0;
      const useVector = document.getElementById("retrieval-tenders-use-vector").checked;
      const useBm25 = document.getElementById("retrieval-tenders-use-bm25").checked;
      const vectorWeight = readRangeWeight("retrieval-tenders-vector-weight", 0.5);
      const bm25Weight = readRangeWeight("retrieval-tenders-bm25-weight", 0.5);
      setOut("招标库检索请求已发送…", false);
      const wrapBusy = document.getElementById("retrieval-tenders-results");
      if (wrapBusy) wrapBusy.innerHTML = '<p class="muted">检索中…</p>';
      try {
        const payload = {
          product_id: productId,
          top_k: topK,
          min_score: minScore,
          use_vector: useVector,
          use_bm25: useBm25,
          vector_weight: vectorWeight,
          bm25_weight: bm25Weight,
        };
        const res = await fetch(apiPath("api/retrieval/search-tenders"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const { data, text } = await readJsonResponse(res);
        if (!res.ok) {
          let raw =
            data && data.detail != null
              ? data.detail
              : (text || "").trim().slice(0, 500) || res.statusText;
          if (typeof raw === "object") raw = JSON.stringify(raw);
          throw new Error(typeof raw === "string" ? raw : String(raw));
        }
        if (data === null) throw new Error("接口返回非 JSON");
        const results = data.results || [];
        const note =
          data.query_source === "product" && data.product_id
            ? "（产品 " + data.product_id + "）"
            : "";
        setOut("招标库检索完成，命中 " + results.length + " 条" + note + "。", false);
        renderRetrievalTendersResults(results, {
          query: data.query,
          query_source: data.query_source,
          product_id: data.product_id,
          product_info: data.product_info,
        });
      } catch (err) {
        setOut("招标库检索失败：" + (err.message || err), true);
        const wrapErr = document.getElementById("retrieval-tenders-results");
        if (wrapErr) wrapErr.innerHTML = "";
      }
    });
  }

  // Add event listeners for sliders to sync their values (sum = 1.0)
  function syncSliders(id1, valId1, id2, valId2) {
    const s1 = document.getElementById(id1);
    const v1 = document.getElementById(valId1);
    const s2 = document.getElementById(id2);
    const v2 = document.getElementById(valId2);

    if (s1 && v1 && s2 && v2) {
      s1.addEventListener("input", (e) => {
        let val = parseFloat(e.target.value);
        v1.textContent = val.toFixed(1);
        let otherVal = 1.0 - val;
        s2.value = otherVal.toFixed(1);
        v2.textContent = otherVal.toFixed(1);
      });
      s2.addEventListener("input", (e) => {
        let val = parseFloat(e.target.value);
        v2.textContent = val.toFixed(1);
        let otherVal = 1.0 - val;
        s1.value = otherVal.toFixed(1);
        v1.textContent = otherVal.toFixed(1);
      });
    }
  }

  syncSliders(
    "retrieval-vector-weight", "retrieval-vector-weight-val",
    "retrieval-bm25-weight", "retrieval-bm25-weight-val"
  );
  syncSliders(
    "retrieval-tenders-vector-weight", "retrieval-tenders-vector-weight-val",
    "retrieval-tenders-bm25-weight", "retrieval-tenders-bm25-weight-val"
  );

  // 初始化模态框
  initModal();

  // 默认页签为「销售情报」时，不点其他 Tab 也会拉取线路；失败时保留 HTML 预设选项。
  if (window.location.protocol !== "file:") {
    loadLlmOptions().catch(() => {});
  }
})();
