/* ==========================================================================
   AI Library — shared behaviour
   Loaded by both index.html and every resource page. Each block bails out
   early when its markup isn't present, so one file serves both page types.
   ========================================================================== */

(function () {
  "use strict";

  /* --- Theme -----------------------------------------------------------
     The inline snippet in <head> has already applied the stored choice, so
     there is no flash. Here we only wire the toggle.
     ------------------------------------------------------------------ */

  function currentTheme() {
    var explicit = document.documentElement.getAttribute("data-theme");
    if (explicit) return explicit;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  var toggle = document.querySelector(".theme-toggle");
  if (toggle) {
    toggle.addEventListener("click", function () {
      var next = currentTheme() === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      try { localStorage.setItem("ail-theme", next); } catch (e) { /* private mode */ }
      toggle.setAttribute("aria-label", "Switch to " + (next === "dark" ? "light" : "dark") + " theme");
    });
  }

  /* --- Reading progress ------------------------------------------------ */

  var bar = document.getElementById("progress");
  if (bar) {
    var ticking = false;
    var update = function () {
      var h = document.documentElement;
      var scrollable = h.scrollHeight - h.clientHeight;
      var pct = scrollable > 0 ? (h.scrollTop / scrollable) * 100 : 0;
      bar.style.width = pct.toFixed(2) + "%";
      ticking = false;
    };
    window.addEventListener("scroll", function () {
      if (!ticking) { ticking = true; window.requestAnimationFrame(update); }
    }, { passive: true });
    update();
  }

  /* --- TOC: highlight the section you're reading ----------------------- */

  var tocLinks = document.querySelectorAll(".toc a[href^='#']");
  if (tocLinks.length && "IntersectionObserver" in window) {
    var byId = {};
    var targets = [];
    Array.prototype.forEach.call(tocLinks, function (a) {
      var el = document.getElementById(a.getAttribute("href").slice(1));
      if (el) { byId[el.id] = a; targets.push(el); }
    });

    // Track which sections are on screen and mark the topmost one.
    var visible = new Set();
    var obs = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) visible.add(en.target.id);
        else visible.delete(en.target.id);
      });
      var first = null;
      for (var i = 0; i < targets.length; i++) {
        if (visible.has(targets[i].id)) { first = targets[i].id; break; }
      }
      Array.prototype.forEach.call(tocLinks, function (a) { a.classList.remove("is-current"); });
      if (first && byId[first]) byId[first].classList.add("is-current");
    }, { rootMargin: "-72px 0px -60% 0px", threshold: 0 });

    targets.forEach(function (t) { obs.observe(t); });
  }

  /* --- Index: search, tag filter, sort ---------------------------------
     Reads window.LIBRARY, which rebuild_index.py bakes into index.html as an
     inline array. Inline rather than fetched so the page behaves identically
     over file:// and over GitHub Pages.
     ------------------------------------------------------------------ */

  var list = document.getElementById("cards");
  if (!list || !window.LIBRARY) return;

  var items = window.LIBRARY.slice();
  var searchInput = document.getElementById("search");
  var sortSelect = document.getElementById("sort");
  var tagbar = document.getElementById("tagbar");
  var countEl = document.getElementById("count");
  var activeTags = new Set();

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function haystack(it) {
    if (it._hay) return it._hay;
    it._hay = [it.title, it.authors, it.hook, it.venue, (it.tags || []).join(" "), it.year]
      .join(" ").toLowerCase();
    return it._hay;
  }

  function matches(it, query) {
    if (activeTags.size) {
      var tags = it.tags || [];
      // AND across selected tags: narrowing should actually narrow.
      for (var t of activeTags) if (tags.indexOf(t) === -1) return false;
    }
    if (!query) return true;
    var hay = haystack(it);
    return query.split(/\s+/).every(function (term) { return hay.indexOf(term) !== -1; });
  }

  function sorted(arr) {
    var mode = sortSelect ? sortSelect.value : "added";
    var out = arr.slice();
    out.sort(function (a, b) {
      if (mode === "year") return (b.year || 0) - (a.year || 0);
      if (mode === "read") return (b.read_minutes || 0) - (a.read_minutes || 0);
      if (mode === "title") return String(a.title).localeCompare(String(b.title));
      return String(b.added || "").localeCompare(String(a.added || ""));
    });
    return out;
  }

  function cardHTML(it) {
    var TYPES = { paper: "Paper", article: "Article", guide: "Guide" };
    var type = TYPES[it.type] ? it.type : "paper";
    var typeLabel = TYPES[type];
    var byline = [it.authors, it.venue, it.year].filter(Boolean).join(" · ");
    var tags = (it.tags || []).map(function (t) {
      return '<li class="tag">' + esc(t) + "</li>";
    }).join("");

    return '<li class="card">' +
      '<a class="card__link" href="' + esc(it.page) + '">' +
        '<span class="card__top">' +
          '<span class="badge badge--' + type + '">' + typeLabel + "</span>" +
          '<span class="card__read">' + esc(it.read_minutes || "?") + " min read</span>" +
        "</span>" +
        '<h2 class="card__title">' + esc(it.title) + "</h2>" +
        (byline ? '<p class="card__byline">' + esc(byline) + "</p>" : "") +
        '<p class="card__hook">' + esc(it.hook) + "</p>" +
      "</a>" +
      (tags ? '<ul class="card__tags">' + tags + "</ul>" : "") +
      "</li>";
  }

  function emptyHTML(reason) {
    if (reason === "library") {
      return '<li class="empty"><strong>The library is empty.</strong>' +
        "Drop a PDF into <code>inbox/</code> and run <code>/add-resource</code> to add the first one.</li>";
    }
    return '<li class="empty"><strong>Nothing matches those filters.</strong>' +
      "Try a different search term, or clear the selected tags.</li>";
  }

  function render() {
    if (!items.length) {
      list.innerHTML = emptyHTML("library");
      if (countEl) countEl.textContent = "No resources yet";
      return;
    }

    var q = searchInput ? searchInput.value.trim().toLowerCase() : "";
    var shown = sorted(items.filter(function (it) { return matches(it, q); }));

    list.innerHTML = shown.length ? shown.map(cardHTML).join("") : emptyHTML("filter");

    if (countEl) {
      countEl.textContent = shown.length === items.length
        ? items.length + (items.length === 1 ? " resource" : " resources")
        : "Showing " + shown.length + " of " + items.length;
    }
  }

  // Tag chips, counted from what's actually in the library.
  if (tagbar) {
    var counts = {};
    items.forEach(function (it) {
      (it.tags || []).forEach(function (t) { counts[t] = (counts[t] || 0) + 1; });
    });
    var names = Object.keys(counts).sort(function (a, b) {
      return counts[b] - counts[a] || a.localeCompare(b);
    });
    tagbar.innerHTML = names.map(function (t) {
      return '<button class="chip" type="button" aria-pressed="false" data-tag="' + esc(t) + '">' +
        esc(t) + '<span class="chip__n">' + counts[t] + "</span></button>";
    }).join("");

    tagbar.addEventListener("click", function (ev) {
      var chip = ev.target.closest(".chip");
      if (!chip) return;
      var tag = chip.dataset.tag;
      if (activeTags.has(tag)) { activeTags.delete(tag); chip.setAttribute("aria-pressed", "false"); }
      else { activeTags.add(tag); chip.setAttribute("aria-pressed", "true"); }
      render();
    });
  }

  if (searchInput) searchInput.addEventListener("input", render);
  if (sortSelect) sortSelect.addEventListener("change", render);

  render();
})();
