/* ==========================================================================
   AI Library — field-guide instruments

   Loaded only by a `type: "guide"` page that lists it in the content JSON's
   "scripts" array. Every widget bails out when its root element is absent, so
   one file can serve more than one guide.

   Two rules this file exists to keep:

   1. No colour literals. Everything paintable comes from a --fg-* custom
      property in assets/style.css and is re-read whenever the theme flips,
      so the heatmap and the token chips invert with the page instead of
      staying stuck in light mode.
   2. No network. Every number on the page is computed here, from the formula
      the surrounding prose just described.
   ========================================================================== */

(function () {
  "use strict";

  if (!document.querySelector(".fg")) return;

  function $(sel, scope) { return (scope || document).querySelector(sel); }
  function $$(sel, scope) {
    return Array.prototype.slice.call((scope || document).querySelectorAll(sel));
  }
  function text(sel, value) { var el = $(sel); if (el) el.textContent = value; }

  /* --- Palette ----------------------------------------------------------
     Custom properties come back as their specified token, so "#3a4a9e" or
     "30% 90%" rather than a resolved colour. Parse what we need, cache it,
     and drop the cache when the theme changes.
     ------------------------------------------------------------------ */

  var palette = null;

  function readPalette() {
    var cs = getComputedStyle(document.documentElement);
    function prop(name) { return cs.getPropertyValue(name).trim(); }
    return {
      indigo: prop("--fg-indigo"),
      magenta: prop("--fg-magenta"),
      rule: prop("--rule-strong"),
      teal: prop("--teal"),
      ink: prop("--ink"),
      accent: prop("--accent"),
      chipSL: prop("--fg-chip-sl") || "30% 90%",
      cellOff: prop("--fg-cell-off"),
      heat: [rgb(prop("--fg-heat-lo")), rgb(prop("--fg-heat-mid")), rgb(prop("--fg-heat-hi"))]
    };
  }
  function pal() { if (!palette) palette = readPalette(); return palette; }

  function rgb(value) {
    var m = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(value);
    if (m) {
      var h = m[1];
      if (h.length === 3) h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2];
      return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
    }
    var parts = value.replace(/^rgba?\(|\)$/g, "").split(/[\s,/]+/);
    return [+parts[0] || 0, +parts[1] || 0, +parts[2] || 0];
  }

  function lerp(a, b, t) { return a + (b - a) * t; }

  /* A two-stop ramp: quiet background → mid → hot. Rows of an attention
     matrix are mostly near zero, so the interesting range is the top half. */
  function heat(v) {
    var stops = pal().heat;
    v = Math.max(0, Math.min(1, v));
    var from, to, t;
    if (v < 0.5) { from = stops[0]; to = stops[1]; t = v / 0.5; }
    else { from = stops[1]; to = stops[2]; t = (v - 0.5) / 0.5; }
    return "rgb(" + Math.round(lerp(from[0], to[0], t)) + "," +
                    Math.round(lerp(from[1], to[1], t)) + "," +
                    Math.round(lerp(from[2], to[2], t)) + ")";
  }

  /* --- Maths ------------------------------------------------------------ */

  function hash(s) {
    var h = 2166136261;
    for (var i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
    return h >>> 0;
  }

  /* Deterministic PRNG, so a given token always gets the same "embedding"
     and the same routing decision across reloads. */
  function rng(seed) {
    return function () {
      seed |= 0; seed = (seed + 0x6D2B79F5) | 0;
      var t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  /* Masked positions arrive as -Infinity and must contribute exactly zero
     without poisoning the max-subtraction that keeps exp() in range. */
  function softmax(values, T) {
    T = T || 1;
    var finite = values.filter(isFinite);
    var max = finite.length ? Math.max.apply(null, finite) : 0;
    var exps = values.map(function (v) {
      return isFinite(v) ? Math.exp((v - max) / Math.max(T, 1e-6)) : 0;
    });
    var sum = exps.reduce(function (a, b) { return a + b; }, 0) || 1;
    return exps.map(function (v) { return v / sum; });
  }

  function entropy(probs) {
    var h = 0;
    probs.forEach(function (p) { if (p > 1e-9) h -= p * Math.log(p) / Math.LN2; });
    return h;
  }

  function fmt(n, d) {
    return n.toLocaleString(undefined, { maximumFractionDigits: d === undefined ? 2 : d });
  }
  function bytes(b) {
    if (b >= 1e12) return fmt(b / 1e12, 2) + " TB";
    if (b >= 1e9) return fmt(b / 1e9, 2) + " GB";
    if (b >= 1e6) return fmt(b / 1e6, 1) + " MB";
    return fmt(b / 1e3, 0) + " KB";
  }
  /* Parameter counts are counts, not bytes — they get their own formatter
     rather than borrowing bytes() and stripping the units afterwards. */
  function pcount(n) {
    if (n >= 1e9) return fmt(n / 1e9, 2) + "B";
    if (n >= 1e6) return fmt(n / 1e6, 1) + "M";
    return fmt(n / 1e3, 0) + "K";
  }
  function esc(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  /* --- Tokenizer --------------------------------------------------------
     A greedy longest-match against a fixed word list. Not BPE — the merge
     table is a stand-in — but it reproduces the behaviour that matters here:
     common words survive whole, rare ones shatter, and a leading space is
     part of the token.
     ------------------------------------------------------------------ */

  var VOCAB = ("the of and to in a is that it for on with as was at by an be this have from or one had not " +
    "but what all were when we there can your which their said if do will each about how up out them then " +
    "she many some so these would other into has more her two like him time see no could make than first " +
    "been its who now people my made over did down only way find use may water long little very after words " +
    "called just where most know get through back much before go good new write our used me man too any day " +
    "same right look think also around another came come work three must because does part even place well " +
    "such here take why things help put years different away again off went old number great tell men say " +
    "small every found still between name should home big give air line set own under read last never us " +
    "left end along while might next sound below saw something thought both few those always looked show " +
    "large often together asked house world going want school important until form food keep children feet " +
    "land side without boy once animals life enough took sometimes four head above kind began almost live " +
    "page got earth need far hand high year mother light country father let night following picture being " +
    "study second eyes soon times story boys since white days ever paper hard near sentence better best " +
    "across during today others however sure means knew try told young miles sun ways thing whole hear " +
    "example heard several change answer room sea against top turned learn point city play toward five " +
    "himself usually money seen car morning upon family leave although idea eat body music color stand " +
    "questions fish area mark dog horse birds problem complete piece order red door become ship short hours " +
    "black products happened measure remember early waves reached listen wind rock space covered fast hold " +
    "step passed vowel true hundred pattern numeral table north slowly map farm pulled draw voice cold cried " +
    "plan notice south sing war ground fall king town unit figure certain field travel wood fire done " +
    "english road half ten fly gave box finally wait correct quickly person shown minutes strong verb stars " +
    "front feel fact inches street decided contain course surface produce building ocean class note nothing " +
    "rest carefully scientists inside wheels stay green known island week less machine base ago stood plane " +
    "system behind ran round boat game force brought understand warm common bring explain dry though " +
    "language shape deep thousands yes clear equation yet government filled heat full hot check object rule " +
    "among noun power cannot able six size dark ball material special heavy fine pair circle include built " +
    "ing ed er est ly tion ness ment ful able ous ive al ic ish ize pre re un dis mis non over sub inter " +
    "trans anti auto bio geo tele micro multi semi super ultra " +
    "token model context vector matrix layer neural network attention head prompt agent sample entropy " +
    "logit cache tensor gradient embed decode encode infer parameter softmax query key value residual " +
    "expert route sparse dense window retrieve rank index chunk score eval judge loop tool trace budget " +
    "prefill compute train weight bias norm rotary position " +
    /* The words the demo sentences are built from. Without these the stand-in
       merge table shatters "board" into b|o|a|rd, which is a fair illustration
       of what happens to a rare word and a terrible one to hang the attention
       and routing demos on — those chapters are about relationships between
       words, and single letters have none. */
    "art board approve cheap delicate engineer rout decide wake").split(/\s+/);

  var VSET = {};
  VOCAB.forEach(function (w) { if (w) VSET[w] = 1; });

  function tokenize(input) {
    if (!input) return [];
    var chunks = input.match(/'[a-z]{1,2}| ?[A-Za-z]+| ?[0-9]+| ?[^\sA-Za-z0-9]+|\s+/g) || [];
    var out = [];
    chunks.forEach(function (raw) {
      var lead = raw.charAt(0) === " " ? " " : "";
      var core = lead ? raw.slice(1) : raw;
      if (!/[A-Za-z]/.test(core) || core.length <= 2) { out.push(lead + core); return; }
      var rest = core, first = true;
      while (rest.length) {
        var cut = 0;
        for (var L = Math.min(rest.length, 12); L >= 1; L--) {
          if (VSET[rest.slice(0, L).toLowerCase()] || L === 1) { cut = L; break; }
        }
        /* Never leave a one-character orphan behind: a real merge table would
           have absorbed it, and a trailing single letter reads as a bug. */
        if (cut === rest.length - 1) cut = rest.length;
        out.push((first ? lead : "") + rest.slice(0, cut));
        rest = rest.slice(cut);
        first = false;
      }
    });
    return out.map(function (t) { return { text: t, id: hash(t) % 50257 }; });
  }

  function embed(token, d) {
    d = d || 8;
    var r = rng(hash(token.text) ^ 0x9E37);
    var v = [];
    for (var i = 0; i < d; i++) v.push(r() * 2 - 1);
    return v;
  }

  /* --- Widget registry --------------------------------------------------
     Every widget hands back its render function so a theme change can repaint
     the lot. Nothing here reads the DOM for colour, so a repaint is cheap.
     ------------------------------------------------------------------ */

  var renderers = [];
  function register(fn) { renderers.push(fn); fn(); }

  function repaint() {
    palette = null;
    renderers.forEach(function (fn) { fn(); });
  }

  new MutationObserver(repaint).observe(document.documentElement, {
    attributes: true, attributeFilter: ["data-theme"]
  });
  var mq = window.matchMedia("(prefers-color-scheme: dark)");
  if (mq.addEventListener) mq.addEventListener("change", repaint);
  else if (mq.addListener) mq.addListener(repaint);

  function press(btn, on) { btn.setAttribute("aria-pressed", on ? "true" : "false"); }
  function isOn(btn) { return btn.getAttribute("aria-pressed") === "true"; }

  /* Wire a group of buttons as a single-choice control, returning the current
     value. Used for the precision pickers and the attention head selector. */
  function radioGroup(selector, onPick) {
    $$(selector).forEach(function (btn) {
      btn.addEventListener("click", function () {
        $$(selector).forEach(function (other) { press(other, other === btn); });
        onPick(btn.getAttribute("data-value"));
      });
    });
  }

  function bind(ids, fn) {
    ids.forEach(function (id) {
      var el = $(id);
      if (el) el.addEventListener("input", fn);
    });
  }

  function num(id) { return parseFloat($(id).value); }
  function int(id) { return parseInt($(id).value, 10); }

  /* ====================================================================
     01 — Tokenizer and embedding
     ==================================================================== */

  (function () {
    var host = $("#fg-tok");
    if (!host) return;
    var input = $("#fg-tok-in"), out = $("#fg-tok-out"), emb = $("#fg-tok-emb");
    var selected = 0, tokens = [];

    function renderEmbedding() {
      var t = tokens[selected];
      text("#fg-tok-emblabel", t ? 'Embedding of "' + t.text.trim() + '"' : "Embedding");
      emb.innerHTML = "";
      if (!t) return;
      embed(t).forEach(function (v) {
        var cell = document.createElement("div");
        cell.style.flex = "1";
        cell.style.textAlign = "center";
        var swatch = document.createElement("div");
        swatch.style.height = "52px";
        swatch.style.borderRadius = "4px";
        swatch.style.background = heat((v + 1) / 2);
        var label = document.createElement("div");
        label.className = "fg__tokid";
        label.textContent = v.toFixed(2);
        cell.appendChild(swatch);
        cell.appendChild(label);
        emb.appendChild(cell);
      });
    }

    function render() {
      var value = input.value;
      tokens = tokenize(value);
      if (selected >= tokens.length) selected = 0;
      text("#fg-tok-chars", value.length);
      text("#fg-tok-count", tokens.length);
      text("#fg-tok-ratio", (value.length / Math.max(tokens.length, 1)).toFixed(2) + " ch/tok");

      var colours = pal();
      out.innerHTML = "";
      tokens.forEach(function (t, i) {
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "fg__tokbtn";
        btn.setAttribute("aria-pressed", i === selected ? "true" : "false");
        btn.setAttribute("aria-label",
          "Token " + (i + 1) + ": " + (t.text.trim() || "space") + ", id " + t.id);
        var background = i === selected
          ? colours.indigo
          : "hsl(" + ((t.id * 37) % 360) + " " + colours.chipSL + ")";
        btn.innerHTML =
          '<span class="fg__tok" style="background:' + background +
          (i === selected ? ";color:" + "var(--bg-raised)" : "") + '">' +
          esc(t.text.replace(/^ /, "·")) + "</span>" +
          '<span class="fg__tokid" aria-hidden="true">' + t.id + "</span>";
        btn.addEventListener("click", function () { selected = i; render(); });
        out.appendChild(btn);
      });
      renderEmbedding();
    }

    input.addEventListener("input", function () { selected = 0; render(); });
    register(render);
  }());

  /* ====================================================================
     02 — Attention
     ==================================================================== */

  (function () {
    var host = $("#fg-attn");
    if (!host) return;
    var input = $("#fg-attn-in"), grid = $("#fg-attn-grid"), temp = $("#fg-attn-temp");
    var head = 0;

    function render() {
      var tokens = tokenize(input.value).slice(0, 14);
      var n = tokens.length, d = 8;
      var causal = isOn($("#fg-attn-causal"));
      var scaled = isOn($("#fg-attn-scaled"));
      var positional = isOn($("#fg-attn-pos"));
      var T = parseFloat(temp.value);

      text("#fg-attn-tempv", T.toFixed(2));
      text("#fg-attn-t", T.toFixed(2));
      text("#fg-attn-head", "#" + head);
      text("#fg-attn-posv", positional ? "on" : "off");
      text("#fg-attn-meta", "head " + head + " · " + n + " tokens");

      grid.innerHTML = "";
      if (!n) { text("#fg-attn-h", "—"); return; }

      var r = rng(1234 + head * 977);
      function weights() {
        var m = [];
        for (var i = 0; i < d; i++) {
          var row = [];
          for (var j = 0; j < d; j++) row.push((r() * 2 - 1) / Math.sqrt(d));
          m.push(row);
        }
        return m;
      }
      var Wq = weights(), Wk = weights();

      /* Additive sinusoidal position, the pre-RoPE scheme. Kept because it can
         be switched off in one line, which is the whole point of the toggle. */
      var E = tokens.map(function (t, p) {
        return embed(t).map(function (v, i) {
          if (!positional) return v;
          return v + 0.55 * Math.sin(p / Math.pow(120, i / d) + (i % 2 ? Math.PI / 2 : 0));
        });
      });
      function project(M) {
        return E.map(function (e) {
          var o = [];
          for (var j = 0; j < d; j++) {
            var s = 0;
            for (var i = 0; i < d; i++) s += e[i] * M[i][j];
            o.push(s);
          }
          return o;
        });
      }
      var Q = project(Wq), K = project(Wk);

      var attn = Q.map(function (q, i) {
        return softmax(K.map(function (k, j) {
          if (causal && j > i) return -Infinity;
          var dot = 0;
          for (var x = 0; x < d; x++) dot += q[x] * k[x];
          return scaled ? dot / Math.sqrt(d) : dot * 3;
        }), T);
      });

      text("#fg-attn-h", entropy(attn[n - 1] || []).toFixed(2) + " bits");

      grid.setAttribute("role", "img");
      grid.setAttribute("aria-label",
        "Attention heatmap, head " + head + ", " + n + " by " + n + " tokens. Each row is one " +
        "token's attention over the sentence and sums to 1." +
        (causal ? " A causal mask hides everything to the right of the diagonal." : ""));

      var wrap = document.createElement("div");
      wrap.style.display = "grid";
      wrap.style.gridTemplateColumns = "minmax(3.5rem, 5rem) 1fr";
      wrap.style.gap = "6px";
      wrap.appendChild(document.createElement("div"));

      var colHead = document.createElement("div");
      colHead.className = "fg__heat";
      colHead.style.gridTemplateColumns = "repeat(" + n + ",1fr)";
      tokens.forEach(function (t) {
        var cell = document.createElement("div");
        cell.className = "fg__axl";
        cell.style.transform = "rotate(-52deg)";
        cell.style.transformOrigin = "left bottom";
        cell.style.height = "46px";
        cell.textContent = t.text.trim();
        colHead.appendChild(cell);
      });
      wrap.appendChild(colHead);

      attn.forEach(function (row, i) {
        var label = document.createElement("div");
        label.className = "fg__axl";
        label.style.textAlign = "right";
        label.style.alignSelf = "center";
        label.textContent = tokens[i].text.trim();
        wrap.appendChild(label);

        var line = document.createElement("div");
        line.className = "fg__heat";
        line.style.gridTemplateColumns = "repeat(" + n + ",1fr)";
        row.forEach(function (v, j) {
          var cell = document.createElement("div");
          cell.className = "fg__cell";
          cell.style.background = heat(v);
          cell.title = tokens[i].text.trim() + " → " + tokens[j].text.trim() +
            ": " + (v * 100).toFixed(1) + "%";
          line.appendChild(cell);
        });
        wrap.appendChild(line);
      });
      grid.appendChild(wrap);
    }

    $$("[data-fg-head]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        head = parseInt(btn.getAttribute("data-fg-head"), 10);
        $$("[data-fg-head]").forEach(function (other) { press(other, other === btn); });
        render();
      });
    });
    ["#fg-attn-causal", "#fg-attn-scaled", "#fg-attn-pos"].forEach(function (sel) {
      $(sel).addEventListener("click", function () { press($(sel), !isOn($(sel))); render(); });
    });
    input.addEventListener("input", render);
    temp.addEventListener("input", render);
    register(render);
  }());

  /* ====================================================================
     03 — Mixture of experts
     ==================================================================== */

  (function () {
    var host = $("#fg-moe");
    if (!host) return;

    /* Attention, embeddings and any always-on shared expert run for every
       token no matter how the router decides. Naming that share is the
       difference between "6% sparse" and "14% of the weights active", which
       are both true and were previously reported as if they were the same
       number. */
    var ALWAYS_ON = 0.08;

    var sentence = tokenize("Routing decides which experts wake up for each token").slice(0, 9);
    var tokenIndex = 0;
    var row = $("#fg-moe-toks");

    sentence.forEach(function (t, i) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "fg__btn";
      btn.textContent = t.text.trim();
      btn.setAttribute("aria-pressed", i === 0 ? "true" : "false");
      btn.addEventListener("click", function () {
        tokenIndex = i;
        Array.prototype.forEach.call(row.children, function (other, j) { press(other, j === i); });
        render();
      });
      row.appendChild(btn);
    });

    function render() {
      var experts = int("#fg-moe-experts");
      $("#fg-moe-topk").max = Math.min(32, experts);
      var topk = Math.min(int("#fg-moe-topk"), experts);
      var total = int("#fg-moe-total");

      text("#fg-moe-expertsv", experts);
      text("#fg-moe-topkv", topk);
      text("#fg-moe-totalv", total + "B");

      var r = rng(hash((sentence[tokenIndex] || { text: "x" }).text));
      var scores = [];
      for (var i = 0; i < experts; i++) scores.push([r(), i]);
      scores.sort(function (a, b) { return b[0] - a[0]; });
      var chosen = {};
      scores.slice(0, topk).forEach(function (s) { chosen[s[1]] = 1; });

      var colours = pal();
      var grid = $("#fg-moe-grid");
      grid.innerHTML = "";
      for (var j = 0; j < experts; j++) {
        var cell = document.createElement("div");
        cell.className = "fg__ex";
        if (chosen[j]) cell.style.background = colours.magenta;
        grid.appendChild(cell);
      }
      grid.setAttribute("aria-label",
        topk + " of " + experts + " experts activated for the token “" +
        (sentence[tokenIndex] || { text: "" }).text.trim() + "”");

      var sparsity = topk / experts;
      var activeShare = ALWAYS_ON + (1 - ALWAYS_ON) * sparsity;
      var active = total * activeShare;

      text("#fg-moe-e", experts);
      text("#fg-moe-k", topk);
      text("#fg-moe-s", (sparsity * 100).toFixed(1) + "%");
      text("#fg-moe-a", fmt(active, 0) + "B");
      text("#fg-moe-tok", '"' + (sentence[tokenIndex] || { text: "" }).text.trim() + '"');
      text("#fg-moe-btot", fmt(total, 0) + "B");
      text("#fg-moe-bactv", fmt(active, 1) + "B");
      $("#fg-moe-bact").style.width = Math.max(1.5, activeShare * 100) + "%";
      $("#fg-moe-bact").style.background = colours.magenta;

      text("#fg-moe-note",
        "The router picks " + (sparsity * 100).toFixed(1) + "% of the experts, but that is not the " +
        "share of the model that runs: attention, embeddings and any always-on shared expert — " +
        "about " + (ALWAYS_ON * 100).toFixed(0) + "% here — fire for every token regardless. " +
        "So " + (activeShare * 100).toFixed(1) + "% of the weights are active while 100% of them " +
        "still sit in VRAM. That gap is the entire pitch, and the reason a sparsity number and an " +
        "active-parameter count never match.");
    }

    bind(["#fg-moe-experts", "#fg-moe-topk", "#fg-moe-total"], render);
    register(render);
  }());

  /* ====================================================================
     04 — Sampling
     ==================================================================== */

  (function () {
    var host = $("#fg-sample");
    if (!host) return;

    var CANDIDATES = [
      ["quiet", 4.9], ["dark", 4.1], ["empty", 3.6], ["cold", 3.4],
      ["still", 3.1], ["silent", 2.6], ["vast", 2.0], ["warm", 1.6],
      ["blue", 1.1], ["furious", 0.4], ["municipal", -0.6], ["banana", -2.4]
    ];
    var bars = $("#fg-sample-bars"), result = $("#fg-sample-result");
    var distribution = [];

    function render() {
      var T = num("#fg-sample-t"), k = int("#fg-sample-k"), p = num("#fg-sample-p");
      text("#fg-sample-t-v", T.toFixed(2));
      text("#fg-sample-k-v", k);
      text("#fg-sample-p-v", p.toFixed(2));
      text("#fg-sample-tv", T.toFixed(2));

      var probs = softmax(CANDIDATES.map(function (c) { return c[1]; }), T);
      var kept = CANDIDATES.map(function () { return true; });
      var order = probs.map(function (v, i) { return [v, i]; })
                       .sort(function (a, b) { return b[0] - a[0]; });

      order.forEach(function (o, rank) { if (rank >= k) kept[o[1]] = false; });

      /* Nucleus: walk the sorted candidates and stop once the mass reaches p.
         The token that crosses the line is kept, which is the standard
         reading of "the smallest set whose probability sums to at least p". */
      var cumulative = 0;
      order.forEach(function (o) {
        if (!kept[o[1]]) return;
        if (cumulative >= p) kept[o[1]] = false;
        else cumulative += o[0];
      });

      var mass = 0;
      order.forEach(function (o) { if (kept[o[1]]) mass += o[0]; });

      distribution = CANDIDATES.map(function (c, i) {
        return { token: c[0], prob: probs[i], kept: kept[i], final: kept[i] ? probs[i] / mass : 0 };
      });

      text("#fg-sample-kept",
        distribution.filter(function (d) { return d.kept; }).length + " / " + CANDIDATES.length);
      text("#fg-sample-h",
        entropy(distribution.map(function (d) { return d.final; })).toFixed(2) + " bits");

      var colours = pal();
      bars.innerHTML = "";
      distribution.forEach(function (d) {
        var shown = d.kept ? d.final : d.prob;
        var line = document.createElement("div");
        line.className = "fg__barrow";
        line.style.opacity = d.kept ? 1 : 0.35;
        line.innerHTML =
          "<span>" + esc(d.token) + "</span>" +
          '<div class="fg__bar" style="width:' + Math.max(0.5, shown * 100) + "%;background:" +
          (d.kept ? colours.indigo : colours.rule) + '"></div>' +
          "<em>" + (shown * 100).toFixed(1) + "%</em>";
        bars.appendChild(line);
      });

      result.hidden = true;
      text("#fg-sample-drawn", "—");
    }

    $("#fg-sample-draw").addEventListener("click", function () {
      var u = Math.random(), cumulative = 0, picked = distribution[0].token;
      for (var i = 0; i < distribution.length; i++) {
        cumulative += distribution[i].final;
        if (u <= cumulative) { picked = distribution[i].token; break; }
      }
      result.hidden = false;
      result.textContent = "the room was " + picked;
      text("#fg-sample-drawn", picked);
    });

    bind(["#fg-sample-t", "#fg-sample-k", "#fg-sample-p"], render);
    register(render);
  }());

  /* ====================================================================
     05 — KV cache, and the prefill/decode cost curves
     ==================================================================== */

  (function () {
    var host = $("#fg-kv");
    if (!host) return;
    var precision = 2;

    radioGroup("#fg-kv-prec .fg__btn", function (value) {
      precision = parseFloat(value);
      render();
    });

    function render() {
      var ctx = int("#fg-kv-c"), layers = int("#fg-kv-l"), batch = int("#fg-kv-b");
      var queryHeads = int("#fg-kv-q");
      $("#fg-kv-kvh").max = queryHeads;
      var kvHeads = Math.min(int("#fg-kv-kvh"), queryHeads);
      var dim = int("#fg-kv-d");

      text("#fg-kv-c-v", ctx + "K tokens");
      text("#fg-kv-l-v", layers);
      text("#fg-kv-b-v", batch);
      text("#fg-kv-q-v", queryHeads);
      text("#fg-kv-kvh-v", kvHeads);
      text("#fg-kv-d-v", dim);

      /* 2 (a key and a value) × layers × kv_heads × head_dim × tokens × batch
         × bytes_per_value. Every term is a multiplier. */
      var kv = 2 * layers * kvHeads * dim * ctx * 1024 * batch * precision;
      var mha = 2 * layers * queryHeads * dim * ctx * 1024 * batch * precision;

      text("#fg-kv-ctx", ctx + "K");
      text("#fg-kv-total", bytes(kv));
      text("#fg-kv-save", (mha / kv).toFixed(1) + "× saved");
      text("#fg-kv-per", bytes(kv / (ctx * 1024) * 1000));
      text("#fg-kv-headline", bytes(kv));
      text("#fg-kv-mha", bytes(mha));
      text("#fg-kv-gqa", bytes(kv));
      $("#fg-kv-gqabar").style.width = Math.max(1.5, kv / mha * 100) + "%";
      $("#fg-kv-gqabar").style.background = pal().magenta;
    }

    bind(["#fg-kv-c", "#fg-kv-l", "#fg-kv-b", "#fg-kv-q", "#fg-kv-kvh", "#fg-kv-d"], render);
    register(render);
  }());

  (function () {
    var chart = $("#fg-cost");
    if (!chart) return;

    /* Two independent curves, drawn side by side per column.

       Each series is scaled to its OWN maximum, so the chart shows the shape
       of each curve and nothing else. Sharing one scale — as an earlier
       version did — invites reading the point where the bars cross as the
       context length at which prefill starts costing more than decode, and
       that crossing is an artifact of the units, not a fact about hardware.
       Prefill FLOPs and decode FLOPs are not the same quantity and the honest
       comparison is curvature: one bows, the other is a ramp. */
    function render() {
      var colours = pal();
      var points = [];
      for (var i = 1; i <= 9; i++) {
        var k = i * 128;
        points.push({ k: k, prefill: Math.pow(k / 1024, 2), decode: k / 1024 });
      }
      var maxPrefill = points[points.length - 1].prefill;
      var maxDecode = points[points.length - 1].decode;

      chart.style.gridTemplateColumns = "repeat(" + points.length + ",1fr)";
      chart.innerHTML = "";
      points.forEach(function (p) {
        var col = document.createElement("div");
        col.className = "fg__chartcol";
        col.innerHTML =
          '<div class="fg__chartbars">' +
            '<i style="height:' + (p.prefill / maxPrefill * 100) + "%;background:" +
              colours.indigo + '"></i>' +
            '<i style="height:' + (p.decode / maxDecode * 100) + "%;background:" +
              colours.teal + '"></i>' +
          "</div>" +
          '<div class="fg__chartlbl">' + p.k + "K</div>";
        chart.appendChild(col);
      });
      chart.setAttribute("role", "img");
      chart.setAttribute("aria-label",
        "Two cost curves against context length from 128K to 1152K, each scaled to its own " +
        "maximum so only the shape is comparable. The prefill series starts near zero and bows " +
        "upward, reaching a quarter of its height only around 512K, because its attention term " +
        "grows with the square of the length. The decode series is a straight ramp, growing in " +
        "proportion to length.");
    }
    register(render);
  }());

  /* ====================================================================
     07 — LoRA and quantization
     ==================================================================== */

  (function () {
    var host = $("#fg-lora");
    if (!host) return;
    var precision = 2, targetFFN = false;
    var ffnBtn = $("#fg-lora-ffn");

    radioGroup("#fg-lora-prec .fg__btn", function (value) {
      precision = parseFloat(value);
      render();
    });

    ffnBtn.addEventListener("click", function () {
      targetFFN = !targetFFN;
      press(ffnBtn, targetFFN);
      render();
    });

    function render() {
      var P = int("#fg-lora-p"), D = int("#fg-lora-dm");
      var L = int("#fg-lora-l"), r = int("#fg-lora-rank");

      text("#fg-lora-p-v", P + "B params");
      text("#fg-lora-dm-v", D);
      text("#fg-lora-l-v", L);
      text("#fg-lora-rank-v", r);

      /* Four attention projections (q, k, v, o), plus three more in the
         feed-forward block (gate, up, down) when it is targeted too. */
      var matrices = targetFFN ? 7 : 4;
      ffnBtn.textContent = "Also target FFN (" + matrices + " matrices/layer)";

      /* Each adapted matrix carries a d×r and an r×d, so 2·r·d trainable
         parameters instead of the d² it replaces. */
      var trainable = L * matrices * 2 * r * D;
      var totalParams = P * 1e9;

      /* Mixed-precision AdamW: fp16 weights, an fp32 master copy, two
         optimizer moments and the gradients — about 16 bytes per parameter. */
      var full = totalParams * 16;
      var lora = totalParams * precision + trainable * 16;
      var share = trainable / totalParams * 100;
      var shareText = share < 0.01 ? share.toExponential(1) : share.toFixed(3);

      text("#fg-lora-r", r);
      text("#fg-lora-share", shareText + "%");
      text("#fg-lora-full", bytes(full));
      text("#fg-lora-lorav", bytes(lora));
      text("#fg-lora-ratio", (full / lora).toFixed(1) + "× less memory");
      text("#fg-lora-bfull", bytes(full));
      text("#fg-lora-blorav", bytes(lora));
      text("#fg-lora-btrv", pcount(trainable));

      var colours = pal();
      $("#fg-lora-blora").style.width = Math.max(1.5, lora / full * 100) + "%";
      $("#fg-lora-blora").style.background = colours.magenta;
      $("#fg-lora-btr").style.width = Math.max(0.4, share) + "%";
      $("#fg-lora-btr").style.background = colours.indigo;

      text("#fg-lora-note",
        "Full fine-tuning holds weights, gradients and two optimizer moments — roughly 16 bytes " +
        "per parameter under mixed-precision AdamW. LoRA holds the frozen base at inference " +
        "precision and pays that tax on only " + shareText + "% of it. Adapters come out small " +
        "enough to keep dozens per base model and swap them per customer.");
    }

    bind(["#fg-lora-p", "#fg-lora-dm", "#fg-lora-l", "#fg-lora-rank"], render);
    register(render);
  }());

  /* ====================================================================
     09 — Context budget
     ==================================================================== */

  (function () {
    var host = $("#fg-budget");
    if (!host) return;

    var SEGMENTS = [
      ["System prompt", "#fg-bg-sys", "ink"],
      ["Tool definitions", "#fg-bg-tools", "indigo"],
      ["Retrieved documents", "#fg-bg-docs", "teal"],
      ["Conversation history", "#fg-bg-hist", "magenta"],
      ["Output reserve", "#fg-bg-res", "accent"]
    ];

    function render() {
      var colours = pal();
      var window_ = int("#fg-bg-w");
      var values = SEGMENTS.map(function (s) { return int(s[1]); });

      text("#fg-bg-w-v", window_ + "K");
      SEGMENTS.forEach(function (s, i) { text(s[1] + "-v", values[i] + "K"); });

      var used = values.reduce(function (a, b) { return a + b; }, 0);
      text("#fg-bg-win", window_ + "K");
      text("#fg-bg-used", fmt(used, 0) + "K");
      text("#fg-bg-fill", (used / window_ * 100).toFixed(0) + "%");
      text("#fg-bg-head", fmt(Math.max(0, window_ - used), 0) + "K");
      text("#fg-bg-headline", fmt(used, 0) + "K / " + window_ + "K");

      var stack = $("#fg-bg-stack"), legend = $("#fg-bg-legend");
      stack.innerHTML = "";
      legend.innerHTML = "";
      SEGMENTS.forEach(function (s, i) {
        var colour = colours[s[2]];
        var seg = document.createElement("div");
        seg.style.width = Math.min(100, values[i] / window_ * 100) + "%";
        seg.style.background = colour;
        seg.title = s[0] + ": " + values[i] + "K";
        stack.appendChild(seg);

        var item = document.createElement("span");
        item.innerHTML = '<i style="background:' + colour + '"></i>' + esc(s[0]) + " " + values[i] + "K";
        legend.appendChild(item);
      });
      stack.setAttribute("aria-label",
        "Context budget: " + fmt(used, 0) + "K of " + window_ + "K allocated. " +
        SEGMENTS.map(function (s, i) { return s[0] + " " + values[i] + "K"; }).join(", ") + ".");

      text("#fg-bg-status", used > window_
        ? "OVERFLOW — " + fmt(used - window_, 0) + "K past the hard limit. Something gets " +
          "truncated, usually the oldest history, and usually without telling you."
        : "Fits, with " + fmt(window_ - used, 0) + "K to spare. Fitting is not the same as being " +
          "used well — see chapter 06 on how retrieval accuracy falls as the span grows.");
    }

    bind(["#fg-bg-w"].concat(SEGMENTS.map(function (s) { return s[1]; })), render);
    register(render);
  }());

  /* ====================================================================
     10 — Retrieval
     ==================================================================== */

  (function () {
    var host = $("#fg-rag");
    if (!host) return;

    var CORPUS = [
      { id: "POL-04", title: "Return window", body: "Sarmisoft accepts returns within 21 days of delivery. Items opened but undamaged incur a 15% restocking fee. Custom-configured units are final sale and cannot be returned under any circumstance." },
      { id: "POL-09", title: "Shipping tiers", body: "Standard shipping is 4-6 business days and free above 400 RON. Express is 1-2 business days at a flat 65 RON. We do not ship to PO boxes or to addresses outside the EU." },
      { id: "POL-12", title: "Warranty", body: "Hardware carries a 24-month warranty covering manufacturing defects. Water damage, unauthorised repair, and cosmetic wear are excluded. Warranty claims require the original order number." },
      { id: "POL-17", title: "Bulk orders", body: "Orders above 20 units qualify for tiered pricing: 8% off at 20 units, 14% at 50, 20% at 100. Bulk orders ship on a 3-week lead time and require 50% payment upfront." },
      { id: "POL-23", title: "Account deletion", body: "Users may request account deletion in writing. Transaction records are retained for 5 years for tax purposes; all other personal data is purged within 30 days of the request." }
    ];
    var STOP = {};
    "the a an is are was were of to in for on and or do i we you it be can with my what how"
      .split(" ").forEach(function (w) { STOP[w] = 1; });

    function terms(s) {
      return (s.toLowerCase().match(/[a-z]{3,}/g) || []).filter(function (w) { return !STOP[w]; });
    }

    /* Document frequency over the corpus, computed once — it does not depend
       on the query. */
    var docTerms = CORPUS.map(function (d) { return terms(d.title + " " + d.body); });
    var df = {};
    docTerms.forEach(function (list) {
      var seen = {};
      list.forEach(function (w) {
        if (!seen[w]) { seen[w] = 1; df[w] = (df[w] || 0) + 1; }
      });
    });

    var bars = $("#fg-rag-bars");

    function render() {
      var k = int("#fg-rag-k");
      text("#fg-rag-k-v", k);
      text("#fg-rag-topk", k);

      var queryTerms = terms($("#fg-rag-q").value);
      var ranked = CORPUS.map(function (d, i) {
        var set = {};
        docTerms[i].forEach(function (w) { set[w] = 1; });
        var hits = queryTerms.filter(function (w) { return set[w]; });
        var score = hits.reduce(function (acc, w) {
          return acc + Math.log(CORPUS.length / (1 + (df[w] || 0))) + 1;
        }, 0);
        return {
          id: d.id,
          title: d.title,
          score: hits.length ? score / Math.sqrt(docTerms[i].length) : 0
        };
      }).sort(function (a, b) { return b.score - a.score; });

      var top = ranked.slice(0, k).filter(function (d) { return d.score > 0; });
      text("#fg-rag-top", top.map(function (d) { return d.id; }).join(" ") || "none");

      var colours = pal();
      var best = Math.max(ranked[0].score, 0.001);
      bars.innerHTML = "";
      ranked.forEach(function (d, i) {
        var on = i < k && d.score > 0;
        var line = document.createElement("div");
        line.className = "fg__barrow";
        line.style.opacity = on ? 1 : 0.35;
        line.innerHTML =
          "<span>" + esc(d.id) + " " + esc(d.title) + "</span>" +
          '<div class="fg__bar" style="width:' + Math.max(1, d.score / best * 100) +
          "%;background:" + (on ? colours.teal : colours.rule) + '"></div>' +
          "<em>" + d.score.toFixed(2) + "</em>";
        bars.appendChild(line);
      });
    }

    bind(["#fg-rag-q", "#fg-rag-k"], render);
    register(render);
  }());
}());
