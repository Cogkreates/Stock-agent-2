/* AAvisit tracker. Add to any website:
   <script src="https://YOUR-SITE/tracker.js" data-site="YOUR_SITE_CODE" async></script> */
(function () {
  var CONFIG = {
    ENDPOINT: "YOUR_MOMEN_GRAPHQL_ENDPOINT",
    VISIT_TABLE: "ud_visit_a34c37",
    VISIT_SITE_FIELD: "ud_site_id_010e69",   // leave empty to auto-detect, or paste the API name of the Site_Id column
    HEARTBEAT_MS: 10000
  };
  var F = { visitor: "ud_visitor_id_d9b34e", country: "ud_country_a82290", page: "ud_page_161689", duration: "ud_duration_7c678d", visitedAt: "ud_visited_at_3b6084" };

  var me = document.currentScript || document.querySelector("script[data-site]");
  var SITE = me && me.getAttribute("data-site");
  function status(t) { var el = document.getElementById("aavisit-status"); if (el) el.textContent = "AAvisit: " + t; }
  if (!SITE) { console.warn("AAvisit: missing data-site"); status("missing data-site"); return; }

  function gql(query, variables) {
    return fetch(CONFIG.ENDPOINT, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ query: query, variables: variables || {} }), keepalive: true })
      .then(function (r) { return r.json(); });
  }

  function siteField() {
    if (CONFIG.VISIT_SITE_FIELD) return Promise.resolve(CONFIG.VISIT_SITE_FIELD);
    var c = null; try { c = localStorage.getItem("aavisit_site_field"); } catch (e) {}
    if (c) return Promise.resolve(c);
    return gql('{ __type(name: "' + CONFIG.VISIT_TABLE + '") { fields { name } } }').then(function (res) {
      var f = (res && res.data && res.data.__type && res.data.__type.fields || []).map(function (x) { return x.name; });
      var hit = f.filter(function (n) { return /^ud_site_id_[0-9a-f]{6}$/.test(n); })[0] || f.filter(function (n) { return /site/i.test(n); })[0];
      if (!hit) throw new Error("Could not find the Site_Id column");
      try { localStorage.setItem("aavisit_site_field", hit); } catch (e) {}
      return hit;
    });
  }

  function visitorId() {
    var k = "aavisit_vid", id = null;
    try { id = localStorage.getItem(k); } catch (e) {}
    if (!id) { id = "v_" + Math.random().toString(36).slice(2) + Date.now().toString(36); try { localStorage.setItem(k, id); } catch (e) {} }
    return id;
  }

  function withTimeout(p, ms) { return Promise.race([p, new Promise(function (_, rej) { setTimeout(function () { rej(new Error("timeout")); }, ms); })]); }

  function getCountry() {
    return withTimeout(fetch("https://ipapi.co/json/").then(function (r) { return r.json(); }), 3000)
      .then(function (d) { if (!d.country_name) throw 0; return d.country_name; })
      .catch(function () {
        return withTimeout(fetch("https://api.country.is/").then(function (r) { return r.json(); }), 3000)
          .then(function (d) { try { return new Intl.DisplayNames(["en"], { type: "region" }).of(d.country); } catch (e) { return d.country || "Unknown"; } })
          .catch(function () { return "Unknown"; });
      });
  }

  var T = CONFIG.VISIT_TABLE, start = Date.now(), rowId = null;

  Promise.all([getCountry(), siteField()]).then(function (r) {
    var country = r[0], sf = r[1];
    var obj = {};
    obj[sf] = SITE;
    obj[F.visitor] = visitorId();
    obj[F.country] = country;
    obj[F.page] = location.pathname;
    obj[F.duration] = "0";
    obj[F.visitedAt] = new Date().toISOString();
    var insert = "mutation($object: " + T + "_insert_input!) { insert_" + T + "_one(object: $object) { id } }";
    return gql(insert, { object: obj }).then(function (res) {
      var row = res && res.data && res.data["insert_" + T + "_one"];
      if (!row) { status("insert failed: " + JSON.stringify(res).slice(0, 160)); return; }
      rowId = row.id;
      status("tracking visit #" + rowId + " from " + country);
      setInterval(beat, CONFIG.HEARTBEAT_MS);
    });
  }).catch(function (e) { status("error: " + e.message); });

  function beat() {
    if (!rowId || document.hidden) return;
    var secs = Math.round((Date.now() - start) / 1000);
    var update = "mutation($id: bigint!, $set: " + T + "_set_input!) { update_" + T + "_by_pk(pk_columns: {id: $id}, _set: $set) { id } }";
    var set = {}; set[F.duration] = String(secs);
    gql(update, { id: rowId, set: set }).then(function (res) {
      if (res && res.errors) status("update failed"); else status("visit #" + rowId + " · " + secs + "s on page");
    });
  }
  window.addEventListener("pagehide", beat);
})();
