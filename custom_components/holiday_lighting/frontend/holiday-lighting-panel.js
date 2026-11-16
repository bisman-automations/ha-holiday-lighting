/*
 * Holiday Lights sidebar page (1.13.0).
 *
 * One plain web component, no build step. Everything it shows comes from the
 * integration's websocket API (holiday_lighting/state), which every command
 * answers with too. It asks again every 30 seconds and whenever one of the
 * integration's entities, a light or a speaker changes.
 *
 * Everyone can use the everyday controls. Admins also get tonight's look
 * (brightness, speed, effect), Try it now, and editing holidays, which goes
 * through Home Assistant's own config flow API and its <ha-form>.
 */

const DOMAIN = "holiday_lighting";
const WS = `${DOMAIN}/`;
const REFRESH_MS = 30000;

const MODE_NAMES = {
  rotate: "Chase",
  static: "Static",
  cycle: "Whole-house cycle",
  fade: "Whole-house fade",
  twinkle: "Twinkle",
};
const STATUS_TEXT = {
  disabled: "Not enabled",
  waiting_for_dark: "Waiting for dark",
  on: "On",
  done_for_tonight: "Done for tonight",
  no_holiday: "No holiday tonight",
};
const SPEEDS = [2, 5, 10, 15, 30, 60, 120, 300, 600];
const FLOW_PREFIX = {
  subentry: `component.${DOMAIN}.config_subentries.holiday`,
  options: `component.${DOMAIN}.options`,
};

const STYLE = `
  :host {
    display: block;
    min-height: 100%;
    background: var(--primary-background-color, #111318);
    color: var(--primary-text-color, #e1e1e1);
    font-family: var(--paper-font-body1_-_font-family, inherit);
    --hl-radius: 14px;
  }
  * { box-sizing: border-box; }
  .wrap { max-width: 1080px; margin: 0 auto; padding: 16px; }
  header { display: flex; flex-wrap: wrap; align-items: center; gap: 10px 16px; margin-bottom: 12px; }
  header .menu { display: none; }
  h1 { font-size: 24px; font-weight: 500; margin: 0; flex: 1 1 auto; color: inherit; }
  h2 { font-size: 16px; font-weight: 500; margin: 0 0 10px; display: flex; align-items: center; gap: 8px; }
  h2 .grow { flex: 1; }
  .switch { display: inline-flex; align-items: center; gap: 8px; cursor: pointer; font-size: 14px; user-select: none; }
  .switch input { position: absolute; opacity: 0; width: 1px; height: 1px; }
  .switch .track {
    width: 40px; height: 22px; border-radius: 11px; position: relative;
    background: var(--switch-unchecked-track-color, #9e9e9e); transition: background .2s;
  }
  .switch .track::after {
    content: ""; position: absolute; top: 2px; left: 2px; width: 18px; height: 18px; border-radius: 50%;
    background: #fff; transition: transform .2s; box-shadow: 0 1px 3px rgba(0,0,0,.4);
  }
  .switch input:checked + .track { background: var(--primary-color, #03a9f4); }
  .switch input:checked + .track::after { transform: translateX(18px); }
  .switch input:focus-visible + .track { outline: 2px solid var(--primary-color, #03a9f4); outline-offset: 2px; }
  select, input[type=time], input[type=number] {
    font: inherit; font-size: 14px; min-height: 36px; padding: 4px 10px; border-radius: 10px;
    background: var(--card-background-color, #fff); color: var(--primary-text-color, #1c1c1c);
    border: 1px solid var(--divider-color, #e0e0e0);
  }
  input[type=range] { width: 100%; accent-color: var(--primary-color, #03a9f4); }
  .theme { display: inline-flex; align-items: center; gap: 8px; font-size: 14px; }

  .stage {
    position: relative; border-radius: var(--hl-radius); padding: 22px 16px 16px;
    background: radial-gradient(ellipse at top, #1d2233 0%, #0b0d14 75%);
    color: #e9ecf5; overflow: hidden; min-height: 170px;
  }
  .stage-top { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 12px; margin-bottom: 18px; }
  .stage-top .name { font-size: 20px; font-weight: 500; }
  .stage-top .status { font-size: 14px; opacity: .75; }
  .stage-top .swatches { margin-left: auto; }
  .banner {
    display: flex; flex-wrap: wrap; align-items: center; gap: 8px 12px; font-size: 13px;
    margin: -6px 0 16px; padding: 8px 12px; border-radius: 10px;
    background: rgba(255,255,255,.08); border: 1px solid rgba(255,255,255,.14);
  }
  .banner .grow { flex: 1; min-width: 160px; }
  .banner button { color: #e9ecf5; background: rgba(255,255,255,.12); border-color: rgba(255,255,255,.25); }
  .bulbs { display: flex; flex-wrap: wrap; justify-content: center; gap: 18px 20px; }
  .bulb {
    display: flex; flex-direction: column; align-items: center; width: 88px; cursor: pointer;
    background: none; border: 0; color: inherit; font: inherit; padding: 4px; border-radius: 12px;
  }
  .bulb:hover { background: rgba(255,255,255,.05); }
  .bulb:focus-visible { outline: 2px solid var(--primary-color, #03a9f4); }
  .glow {
    width: 42px; height: 52px; border-radius: 50% 50% 46% 46% / 60% 60% 40% 40%;
    background: #2a2e3b; border: 1px solid #3b4050;
    transition: background-color var(--t, 1.4s) ease, box-shadow var(--t, 1.4s) ease, opacity .4s;
  }
  .bulb.lit .glow {
    background: var(--c); border-color: transparent;
    box-shadow: 0 0 14px 4px var(--c), 0 0 34px 10px color-mix(in srgb, var(--c) 45%, transparent);
  }
  .bulb.dim .glow { opacity: .35; }
  .bulb.manual .glow { background: repeating-linear-gradient(45deg, #2a2e3b 0 6px, #4a4f60 6px 12px); }
  .bulb.out .glow { background: transparent; border: 1px dashed #6b7080; }
  .bulb.gone .glow { opacity: .4; }
  .label {
    margin-top: 8px; font-size: 13px; line-height: 1.25; text-align: center;
    display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
    overflow: hidden; max-width: 100%; opacity: .9;
  }
  .sub { font-size: 12px; opacity: .65; text-align: center; }

  .actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
  button {
    font: inherit; font-size: 14px; cursor: pointer; padding: 8px 14px; min-height: 38px; border-radius: 19px;
    background: var(--card-background-color, #fff); color: var(--primary-text-color, #1c1c1c);
    border: 1px solid var(--divider-color, #e0e0e0);
  }
  button:hover:not(:disabled) { border-color: var(--primary-color, #03a9f4); }
  button:focus-visible { outline: 2px solid var(--primary-color, #03a9f4); outline-offset: 2px; }
  button:disabled { opacity: .5; cursor: default; }
  button.primary { background: var(--primary-color, #03a9f4); color: var(--text-primary-color, #fff); border-color: transparent; }
  button.small { min-height: 32px; padding: 4px 12px; font-size: 13px; }
  button.link { background: none; border: 0; padding: 4px 6px; min-height: 0; color: var(--primary-color, #03a9f4); }
  button.danger { color: var(--error-color, #db4437); }
  .note { margin-top: 8px; font-size: 13px; min-height: 18px; opacity: .85; }
  .note.error { color: var(--error-color, #db4437); opacity: 1; }

  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 14px; margin-top: 14px; align-items: start; }
  .card {
    background: var(--card-background-color, #fff); color: var(--primary-text-color, #1c1c1c);
    border-radius: var(--hl-radius); padding: 14px 16px;
    box-shadow: var(--ha-card-box-shadow, none); border: 1px solid var(--divider-color, #e0e0e0);
    min-width: 0;
  }
  .card.wide { grid-column: 1 / -1; }
  .card:empty { display: none; }
  .muted { color: var(--secondary-text-color, #727272); font-size: 13px; }
  .row { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
  .row + .row { margin-top: 10px; }
  .big { font-size: 22px; font-weight: 500; }
  .tag {
    display: inline-block; font-size: 12px; padding: 2px 8px; border-radius: 10px;
    background: color-mix(in srgb, var(--primary-color, #03a9f4) 15%, transparent);
    color: var(--primary-text-color, #1c1c1c);
  }
  .tag.warn { background: color-mix(in srgb, var(--warning-color, #ffa600) 22%, transparent); }

  .swatches { display: inline-flex; gap: 3px; vertical-align: middle; }
  .swatches i { width: 14px; height: 14px; border-radius: 50%; display: inline-block; border: 1px solid rgba(127,127,127,.35); }
  .swatches.lg i { width: 18px; height: 18px; }

  /* Tonight's timeline */
  .timeline { position: relative; height: 76px; margin: 6px 4px 4px; }
  .timeline .bar {
    position: absolute; top: 34px; left: 0; right: 0; height: 8px; border-radius: 4px;
    background: linear-gradient(90deg, #f4b860 0%, #6b5ca5 18%, #1f2a4d 40%, #10172b 100%);
    opacity: .85;
  }
  .timeline .lit {
    position: absolute; top: 32px; height: 12px; border-radius: 6px;
    background: linear-gradient(90deg, #ff6b6b, #ffd93d, #6bcb77, #4d96ff);
    box-shadow: 0 0 10px rgba(255, 217, 61, .5);
  }
  .timeline .mark { position: absolute; top: 0; transform: translateX(-50%); text-align: center; font-size: 11px; white-space: nowrap; }
  .timeline .mark.below { top: 48px; }
  .timeline .mark b { display: block; font-weight: 500; }
  .timeline .tick { position: absolute; top: 28px; width: 2px; height: 20px; background: var(--primary-text-color, #1c1c1c); opacity: .5; transform: translateX(-50%); }
  .timeline .now { position: absolute; top: 26px; width: 3px; height: 24px; border-radius: 2px; background: var(--error-color, #db4437); transform: translateX(-50%); }
  .reason { font-size: 14px; margin-top: 8px; }
  .fields { display: grid; grid-template-columns: 1fr 1fr; gap: 4px 10px; margin-top: 12px; }
  .fields select { width: 100%; }

  /* Lists */
  .list { display: flex; flex-direction: column; }
  .item { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 12px; padding: 10px 0; border-top: 1px solid var(--divider-color, #e0e0e0); }
  .item:first-child { border-top: 0; padding-top: 2px; }
  .item .main { flex: 1 1 180px; min-width: 0; }
  .item .title { font-weight: 500; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
  .item .btns { display: flex; flex-wrap: wrap; gap: 6px; }

  /* Coming up */
  .countdown { font-size: 15px; margin-bottom: 10px; }
  .days { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 6px; }
  .day {
    border-radius: 10px; padding: 6px 4px; text-align: center; font-size: 12px; min-height: 58px;
    border: 1px solid var(--divider-color, #e0e0e0);
  }
  .day.today { border-color: var(--primary-color, #03a9f4); box-shadow: inset 0 0 0 1px var(--primary-color, #03a9f4); }
  .day .n { font-size: 15px; font-weight: 500; }
  .day .h { margin-top: 4px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; opacity: .8; }
  .day .swatches i { width: 9px; height: 9px; }

  /* Dialogs */
  .dialog-host {
    position: fixed; inset: 0; z-index: 10; display: flex; align-items: center; justify-content: center;
    background: rgba(0,0,0,.5); padding: 16px;
  }
  .dialog {
    width: min(560px, 100%); max-height: calc(100vh - 32px); overflow: auto;
    background: var(--card-background-color, #fff); color: var(--primary-text-color, #1c1c1c);
    border-radius: 18px; padding: 18px 20px; box-shadow: 0 10px 40px rgba(0,0,0,.4);
  }
  .dialog h3 { margin: 0 0 10px; font-size: 18px; font-weight: 500; }
  .dialog .foot { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 8px; margin-top: 16px; }
  .dialog p { margin: 0 0 10px; line-height: 1.4; }
  .dialog .flow-menu { display: flex; flex-direction: column; gap: 8px; }
  .dialog .flow-menu button { text-align: left; border-radius: 12px; }
  .field-error { color: var(--error-color, #db4437); }
  .big-swatch { width: 48px; height: 48px; border-radius: 50%; border: 1px solid rgba(127,127,127,.35); flex: none; }

  .msg { padding: 24px; text-align: center; opacity: .8; }
  .skeleton {
    background: linear-gradient(90deg, rgba(255,255,255,.06) 25%, rgba(255,255,255,.16) 50%, rgba(255,255,255,.06) 75%);
    background-size: 200% 100%; animation: shimmer 1.4s ease-in-out infinite; border-radius: 8px;
  }
  .skeleton.bulb-ph { width: 42px; height: 52px; border-radius: 50%; }
  .skeleton.line { height: 14px; width: 60%; margin: 6px auto; }
  @keyframes shimmer { 0% { background-position: 100% 0; } 100% { background-position: -100% 0; } }

  @media (max-width: 600px) {
    .wrap { padding: 10px; }
    h1 { font-size: 20px; }
    header .menu { display: inline-flex; }
    .bulb { width: 70px; }
    .glow { width: 34px; height: 42px; }
    .grid { grid-template-columns: 1fr; gap: 10px; }
    .card { padding: 12px; }
    .actions button { flex: 1 1 calc(50% - 8px); }
    .stage-top .swatches { margin-left: 0; }
    .days { gap: 4px; }
    .day { padding: 4px 2px; min-height: 50px; }
    .day .h { display: none; }
  }
  @media (prefers-reduced-motion: reduce) {
    .glow, .skeleton, .switch .track, .switch .track::after { transition: none; animation: none; }
  }
`;

const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const toDate = (iso) => {
  if (!iso) return null;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : d;
};
// A time, with the weekday when it isn't within the next 18 hours.
const fmtTime = (iso) => {
  const d = toDate(iso);
  if (!d) return "—";
  const time = d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  const hours = Math.abs(d - Date.now()) / 3600000;
  return hours < 18 ? time : `${d.toLocaleDateString([], { weekday: "short" })} ${time}`;
};
const clock = (iso) => {
  const d = toDate(iso);
  return d ? d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) : "—";
};
const localDay = (isoDate) => {
  const [y, m, d] = String(isoDate).split("-").map(Number);
  return new Date(y, m - 1, d);
};
const fmtDay = (isoDate, opts = { weekday: "short", month: "short", day: "numeric" }) =>
  isoDate ? localDay(isoDate).toLocaleDateString([], opts) : "";
const hhmm = (iso) => {
  const d = toDate(iso);
  return d ? `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}` : "";
};
const plural = (n, one, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;
const swatches = (colors, cls = "") =>
  `<span class="swatches ${cls}">${(colors || []).slice(0, 8).map((c) => `<i style="background:${esc(c)}"></i>`).join("")}</span>`;

// The same color pattern the integration uses for each step of an effect.
const effectColors = (mode, count, colors, offset) => {
  const n = colors.length;
  if (!n) return Array(count).fill(null);
  const pick = (i) => colors[(((i - offset) % n) + n) % n];
  if (mode === "static") return Array.from({ length: count }, (_, i) => colors[i % n]);
  if (mode === "cycle" || mode === "fade") return Array(count).fill(colors[offset % n]);
  if (mode === "twinkle") return Array.from({ length: count }, () => colors[Math.floor(Math.random() * n)]);
  return Array.from({ length: count }, (_, i) => pick(i));
};


// Whether the page can't be seen (another tab, or a screen that's off).
function pageHidden() {
  return typeof document !== "undefined" && Boolean(document.hidden);
}

class HolidayLightingPanel extends HTMLElement {
  constructor() {
    super();
    this._hass = undefined;
    this._state = undefined;
    this._error = undefined;
    this._built = false;
    this._sections = {};
    this._bulbs = new Map();
    this._bulbIds = "";
    this._watchKey = "";
    this._busy = false;
    this._preview = null;
    this._activeFlow = null;
    this._flowInput = {};
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (!this._built) return;
    if (first) {
      this._load();
      this._loadTranslations();
    } else if (this._watch()) {
      this._scheduleLoad();
    }
    const form = this.shadowRoot.querySelector("#flow-form");
    if (form) form.hass = hass;
  }

  get hass() {
    return this._hass;
  }

  set narrow(value) {
    this._narrow = value;
  }

  set panel(value) {
    this._panel = value;
  }

  connectedCallback() {
    if (!this._built) this._build();
    if (this._hass) {
      this._load();
      if (!this._localize) this._loadTranslations();
    }
    clearInterval(this._timer);
    this._timer = setInterval(() => {
      // The list of entities to watch is worked out again here, not on
      // every state change in the house (that's many a second).
      this._watchIds = null;
      this._load();
    }, REFRESH_MS);
  }

  disconnectedCallback() {
    if (this._onVisible) {
      document.removeEventListener("visibilitychange", this._onVisible);
      this._onVisible = null;
    }
    clearInterval(this._timer);
    clearTimeout(this._loadTimer);
    this._stopPreview(false);
  }

  // --- data ------------------------------------------------------------

  // A key of everything whose change should make the page ask again.
  _watch() {
    const states = this._hass?.states || {};
    if (!this._watchIds) {
      const extra = new Set([
        ...(this._state?.lights || []).map((l) => l.entity_id),
        ...(this._state?.music?.players || []).map((p) => p.entity_id),
      ]);
      this._watchIds = Object.keys(states).filter(
        (id) => /^(sensor|switch|select)\.holiday_lighting_/.test(id) || extra.has(id),
      );
    }
    const key = this._watchIds.map((id) => states[id]?.last_updated || "").join("|");
    if (key === this._watchKey) return false;
    this._watchKey = key;
    return true;
  }

  _scheduleLoad(delay = 500) {
    clearTimeout(this._loadTimer);
    this._loadTimer = setTimeout(() => this._load(), delay);
  }

  async _load() {
    if (!this._hass?.connection) return;
    if (pageHidden()) {
      // Nobody's looking: load once when the page is seen again.
      this._stale = true;
      if (!this._onVisible) {
        this._onVisible = () => {
          if (!pageHidden() && this._stale) this._load();
        };
        document.addEventListener("visibilitychange", this._onVisible);
      }
      return;
    }
    this._stale = false;
    try {
      const state = await this._hass.connection.sendMessagePromise({ type: `${WS}state` });
      this._error = undefined;
      this._setState(state);
    } catch (err) {
      this._error = err?.code === "not_loaded" ? "not_loaded" : err?.message || String(err);
      this._render();
    }
  }

  _setState(state) {
    const lightsChanged =
      JSON.stringify((state.lights || []).map((l) => l.entity_id)) !==
      JSON.stringify((this._state?.lights || []).map((l) => l.entity_id));
    this._state = state;
    if (lightsChanged) this._watchIds = undefined;
    this._render();
  }

  async _send(type, data = {}, done) {
    if (this._busy) return;
    this._busy = true;
    this._render();
    try {
      const state = await this._hass.connection.sendMessagePromise({ type: WS + type, ...data });
      this._busy = false;
      this._setState(state);
      this._note(done || "");
    } catch (err) {
      this._busy = false;
      this._render();
      this._note(err?.message || String(err), true);
    }
  }

  _note(text, error = false) {
    const el = this.shadowRoot.getElementById("note");
    if (!el) return;
    el.className = error ? "note error" : "note";
    el.textContent = text;
    clearTimeout(this._noteTimer);
    if (text && !error) this._noteTimer = setTimeout(() => { el.textContent = ""; }, 4000);
  }

  async _loadTranslations() {
    if (!this._hass?.loadBackendTranslation) return;
    const results = await Promise.allSettled(
      ["config_subentries", "options", "selector"].map((c) => this._hass.loadBackendTranslation(c, DOMAIN)),
    );
    const fns = results.filter((r) => r.status === "fulfilled" && r.value).map((r) => r.value);
    if (fns.length) this._localize = fns.at(-1);
  }

  _t(key, placeholders) {
    const localize = this._localize || this._hass?.localize;
    if (!localize || !key) return undefined;
    const text = localize(key, placeholders || {});
    return text && text !== key ? text : undefined;
  }

  // --- layout ----------------------------------------------------------

  _build() {
    const root = this.attachShadow({ mode: "open" });
    root.innerHTML = `
      <style>${STYLE}</style>
      <div class="wrap">
        <header>
          <ha-menu-button class="menu"></ha-menu-button>
          <h1>Holiday Lights</h1>
          <div id="top" class="row"></div>
        </header>
        <section id="stage" class="stage" aria-live="polite">
          <div class="bulbs" role="status" aria-label="Loading holiday lights">${Array.from({ length: 6 }, () =>
            '<div class="bulb"><div class="skeleton bulb-ph"></div><div class="skeleton line" style="width:70%"></div></div>').join("")}</div>
        </section>
        <div id="actions" class="actions" role="group" aria-label="Holiday light controls"></div>
        <div id="note" class="note" role="status"></div>
        <div class="grid">
          <div id="tonight" class="card"></div>
          <div id="look" class="card"></div>
          <div id="music" class="card"></div>
          <div id="coming" class="card wide"></div>
          <div id="holidays" class="card wide"></div>
          <div id="history" class="card wide"></div>
        </div>
      </div>
      <div id="dialog"></div>`;
    const menu = root.querySelector("ha-menu-button");
    if (menu) {
      menu.hass = this._hass;
      menu.narrow = true;
    }
    root.addEventListener("click", (ev) => this._onClick(ev));
    root.addEventListener("change", (ev) => this._onChange(ev));
    root.addEventListener("input", (ev) => this._onInput(ev));
    root.addEventListener("focusout", () => setTimeout(() => this._render(), 0));
    root.addEventListener("value-changed", (ev) => {
      if (ev.target.id === "flow-form") this._flowInput = ev.detail.value;
    });
    root.addEventListener("keydown", (ev) => {
      if (ev.key === "Escape" && root.querySelector(".dialog-host")) this._closeDialog();
    });
    this._built = true;
  }

  // Someone is using a slider, box or list: don't redraw under them.
  _typing() {
    const el = this.shadowRoot.activeElement;
    return Boolean(el && el.matches("input, select, textarea") && !el.closest("#dialog"));
  }

  _put(id, html) {
    if (this._sections[id] === html) return;
    const el = this.shadowRoot.getElementById(id);
    if (!el) return;
    this._sections[id] = html;
    el.innerHTML = html;
  }

  _render() {
    if (!this._built) return;
    const menu = this.shadowRoot.querySelector("ha-menu-button");
    if (menu && this._hass) menu.hass = this._hass;
    const s = this._state;
    if (!s) {
      if (this._error === "not_loaded") {
        this._put("stage", '<div class="msg">Holiday Lighting isn\'t set up yet.</div>');
      } else if (this._error) {
        this._put("stage", `<div class="msg">Couldn't load the holiday lights: ${esc(this._error)}</div>`);
      }
      return;
    }
    this._renderStage(s);
    if (this._typing()) return;
    this._put("top", this._topHtml(s));
    this._put("actions", this._actionsHtml(s));
    this._put("tonight", this._tonightHtml(s));
    this._put("look", s.is_admin && s.shown && !s.shown.default ? this._lookHtml(s) : "");
    this._put("music", s.music.players.length ? this._musicHtml(s) : "");
    this._put("coming", this._comingHtml(s));
    this._put("holidays", this._holidaysHtml(s));
    this._put("history", this._historyHtml(s));
  }

  _topHtml(s) {
    const options = [`<option value="auto" ${s.theme === "auto" ? "selected" : ""}>Auto (by date)</option>`]
      .concat(s.themes.map((t) => `<option value="${esc(t.id)}" ${s.theme === t.id ? "selected" : ""}>${esc(t.name)}</option>`))
      .join("");
    return `
      <label class="switch" title="Run the schedule">
        <input type="checkbox" data-change="enabled" ${s.enabled ? "checked" : ""} ${this._busy ? "disabled" : ""}>
        <span class="track"></span><span>Enabled</span>
      </label>
      <label class="theme">Theme
        <select data-change="theme" ${this._busy ? "disabled" : ""} aria-label="Theme">${options}</select>
      </label>`;
  }

  // --- the stage: bulbs, preview, trial --------------------------------

  _renderStage(s) {
    const stage = this.shadowRoot.getElementById("stage");
    const lights = s.lights || [];
    const ids = lights.map((l) => l.entity_id).join("|");
    if (ids !== this._bulbIds || !stage.querySelector(".stage-top")) {
      this._bulbIds = ids;
      this._bulbs.clear();
      this._sections.stage = undefined;
      stage.innerHTML = `<div class="stage-top"></div><div class="banners"></div>
        ${lights.length ? '<div class="bulbs real"></div>' : '<div class="msg">No lights are set up for Holiday Lighting.</div>'}`;
      const wrap = stage.querySelector(".bulbs");
      for (const light of lights) {
        const el = document.createElement("button");
        el.type = "button";
        el.className = "bulb";
        el.dataset.act = "bulb";
        el.dataset.id = light.entity_id;
        el.innerHTML = '<div class="glow"></div><div class="label"></div><div class="sub"></div>';
        wrap.appendChild(el);
        this._bulbs.set(light.entity_id, el);
      }
    }
    const shown = this._preview ? this._preview.holiday : s.shown;
    const status = this._preview
      ? `Preview · ${MODE_NAMES[shown.mode] || shown.mode}`
      : STATUS_TEXT[s.status] || s.status;
    const top = `<span class="name">${esc(shown ? shown.name : "No holiday")}</span>
      <span class="status">${esc(status)}</span>${shown ? swatches(shown.colors, "lg") : ""}`;
    const topEl = stage.querySelector(".stage-top");
    if (topEl && topEl.innerHTML !== top) topEl.innerHTML = top;

    const banners = [];
    if (s.trial) {
      banners.push(`<div class="banner"><span class="grow">Trying <b>${esc(s.trial.name)}</b> on your lights until ${esc(clock(s.trial.until))}, then back to normal.</span>
        ${s.is_admin ? '<button type="button" class="small" data-act="try-stop">Stop now</button>' : ""}</div>`);
    }
    if (this._preview) {
      banners.push(`<div class="banner"><span class="grow">Preview of <b>${esc(shown.name)}</b> on this page only. Your lights don't change.</span>
        <button type="button" class="small" data-act="preview-stop">Stop preview</button></div>`);
    }
    const bannerHtml = banners.join("");
    const bannerEl = stage.querySelector(".banners");
    if (bannerEl && bannerEl.innerHTML !== bannerHtml) bannerEl.innerHTML = bannerHtml;

    const preview = this._preview
      ? effectColors(this._preview.holiday.mode, lights.length, this._preview.holiday.colors, this._preview.offset)
      : null;
    lights.forEach((light, index) => {
      const el = this._bulbs.get(light.entity_id);
      if (!el) return;
      let color = light.state === "color" ? light.color : null;
      let sub = { color: light.color_name || "On", manual: "Changed by hand", off: "Off", left_out: "Left out tonight" }[light.state] || light.state;
      if (preview) {
        color = preview[index];
        sub = "Preview";
      }
      if (!light.available && !preview) sub = "Not responding";
      el.style.setProperty("--t", preview ? `${this._preview.step / 1000}s` : "1.4s");
      el.classList.toggle("lit", Boolean(color));
      el.classList.toggle("manual", !preview && light.state === "manual");
      el.classList.toggle("out", !preview && light.state === "left_out");
      el.classList.toggle("gone", !preview && !light.available);
      el.classList.toggle("dim", Boolean(preview) && this._preview.holiday.mode === "twinkle" && Math.random() < 0.25);
      if (color) el.style.setProperty("--c", color);
      else el.style.removeProperty("--c");
      const label = el.querySelector(".label");
      if (label.textContent !== light.name) {
        label.textContent = light.name;
        label.title = light.name;
      }
      el.querySelector(".sub").textContent = sub;
      el.setAttribute("aria-label", `${light.name}: ${sub}`);
    });
  }

  _startPreview(id) {
    const holiday = (this._state?.holidays || []).find((h) => h.id === id);
    if (!holiday) return;
    this._stopPreview(false);
    const step = Math.max(700, Math.min(2500, (holiday.interval || 2) * 1000));
    this._preview = { holiday, offset: 0, step };
    this._previewTimer = setInterval(() => {
      if (!this._preview) return;
      this._preview.offset += 1;
      if (this._state) this._renderStage(this._state);
    }, step);
    this._renderStage(this._state);
    this.shadowRoot.getElementById("stage").scrollIntoView({ behavior: "smooth", block: "nearest" });
    // A preview stops by itself after a minute.
    clearTimeout(this._previewEnd);
    this._previewEnd = setTimeout(() => this._stopPreview(), 60000);
  }

  _stopPreview(render = true) {
    clearInterval(this._previewTimer);
    clearTimeout(this._previewEnd);
    this._preview = null;
    if (render && this._state) this._renderStage(this._state);
  }

  // --- the four buttons ------------------------------------------------

  _actionsHtml(s) {
    const off = this._busy ? "disabled" : "";
    const lit = s.running;
    const buttons = [
      `<button type="button" class="${lit ? "" : "primary"}" data-act="press" data-action="start" ${off}>Turn on now</button>`,
      `<button type="button" data-act="press" data-action="next" ${off || (lit ? "" : "disabled")}>Next colors</button>`,
      `<button type="button" data-act="press" data-action="stop" ${off || (lit ? "" : "disabled")}>Turn off for tonight</button>`,
    ];
    if (s.default_colors) {
      buttons.push(`<button type="button" data-act="press" data-action="default" ${off}>${s.default_tonight ? "Default colors tonight ✓" : "Use default colors tonight"}</button>`);
    }
    return buttons.join("");
  }

  // --- Tonight: timeline and off time ----------------------------------

  _timelineHtml(t, s) {
    const now = toDate(t.now) || new Date();
    const sunset = toDate(t.sunset);
    const on = toDate(t.on_at) || toDate(t.next_on);
    const off = toDate(t.off_at);
    const hard = toDate(t.hard_off);
    const points = [sunset, on, off, hard].filter(Boolean);
    if (points.length < 2) return "";
    // Only tonight: drop times that belong to another night.
    const first = Math.min(...points.map(Number));
    const tonight = points.filter((p) => p - first < 20 * 3600000);
    let start = Math.min(...tonight.map(Number)) - 45 * 60000;
    let end = Math.max(...tonight.map(Number)) + 45 * 60000;
    if (now > start - 2 * 3600000 && now < start) start = Number(now) - 15 * 60000;
    if (now < end + 2 * 3600000 && now > end) end = Number(now) + 15 * 60000;
    const pos = (d) => Math.max(0, Math.min(100, ((d - start) / (end - start)) * 100));
    const marks = [];
    if (sunset && sunset - first < 20 * 3600000) marks.push(["Sunset", sunset, false]);
    if (on && on - first < 20 * 3600000) marks.push([s.timeline.on_at ? "On" : "On about", on, true]);
    if (off && off - first < 20 * 3600000) marks.push(["Off", off, false]);
    if (hard && off && Math.abs(hard - off) > 60000 && hard - first < 20 * 3600000) marks.push(["Latest", hard, true]);
    let lit = "";
    if (on && off && off > on) {
      lit = `<div class="lit" style="left:${pos(on)}%;width:${pos(off) - pos(on)}%"></div>`;
    }
    const nowMark = now >= start && now <= end ? `<div class="now" style="left:${pos(now)}%" title="Now"></div>` : "";
    return `<div class="timeline" role="img" aria-label="Tonight: ${esc(marks.map(([l, d]) => `${l} ${clock(d.toISOString())}`).join(", "))}">
      <div class="bar"></div>${lit}
      ${marks.map(([label, d, below]) => `<div class="tick" style="left:${pos(d)}%"></div>
        <div class="mark ${below ? "below" : ""}" style="left:${Math.max(6, Math.min(94, pos(d)))}%"><b>${esc(label)}</b>${esc(clock(d.toISOString()))}</div>`).join("")}
      ${nowMark}
    </div>`;
  }

  _reason(s) {
    const t = s.timeline;
    switch (s.status) {
      case "disabled":
        return "Turn on <b>Enabled</b> to let the lights come on by themselves.";
      case "no_holiday":
        return s.next ? `No holiday tonight. ${esc(s.next.name)} starts ${this._inDays(s.next.days)}.` : "No holiday tonight.";
      case "on":
        return `On since ${esc(clock(t.on_at))}, off at <b>${esc(fmtTime(t.off_at))}</b>.`;
      case "done_for_tonight":
        return `Done for tonight. Next on ${t.next_on ? `about <b>${esc(fmtTime(t.next_on))}</b>` : "when it's dark"}.`;
      case "waiting_for_dark": {
        if (!t.use_schedule) return "Not on a schedule: use <b>Turn on now</b>.";
        const parts = [];
        if (t.dark_source !== "lux") {
          parts.push(`the sun is at <b>${esc(t.elevation)}°</b> and they come on below ${esc(t.threshold)}°`);
        }
        if (t.lux_threshold != null && t.dark_source !== "sun") {
          parts.push(t.lux == null
            ? "the light sensor isn't reporting"
            : `it's <b>${esc(Math.round(t.lux))} lx</b> and they come on below ${esc(t.lux_threshold)} lx`);
        }
        const when = t.next_on ? ` About ${esc(fmtTime(t.next_on))}.` : "";
        return `Waiting for dark: ${parts.join(", or ")}.${when}`;
      }
      default:
        return "";
    }
  }

  _inDays(days) {
    if (days <= 0) return "today";
    if (days === 1) return "tomorrow";
    return `in ${days} days`;
  }

  _tonightHtml(s) {
    const t = s.timeline;
    const off = this._busy ? "disabled" : "";
    const offTime = hhmm(t.off_at) || hhmm(t.hard_off) || "23:00";
    const canChange = s.enabled && (s.status === "on" || s.status === "waiting_for_dark" || s.status === "done_for_tonight");
    let offControls = "";
    if (canChange) {
      const more = s.status === "done_for_tonight"
        ? `<button type="button" class="small" data-act="extend" data-min="60" ${off}>On for 1 more hour</button>`
        : `<button type="button" class="small" data-act="extend" data-min="30" ${off}>+30 min</button>
           <button type="button" class="small" data-act="extend" data-min="60" ${off}>+1 hour</button>
           <button type="button" class="small" data-act="extend" data-min="120" ${off}>+2 hours</button>`;
      offControls = `
        <div class="row">${more}</div>
        <div class="row">
          <label class="muted" for="offat">Off tonight at</label>
          <input id="offat" type="time" value="${esc(offTime)}" ${off}>
          <button type="button" class="small" data-act="off-at" ${off}>Set</button>
          ${t.off_tonight ? `<button type="button" class="small link" data-act="off-reset" ${off}>Usual off time</button>` : ""}
        </div>
        ${t.off_tonight ? `<div class="muted" style="margin-top:6px">Changed for tonight only.</div>` : ""}`;
    }
    return `<h2>Tonight</h2>
      ${this._timelineHtml(t, s)}
      <div class="reason">${this._reason(s)}</div>
      ${offControls}`;
  }

  // --- Tonight's look (admins) -----------------------------------------

  _lookHtml(s) {
    const h = s.shown;
    const tw = s.tweaks || {};
    const off = this._busy ? "disabled" : "";
    const brightness = tw.brightness ?? 0;
    const interval = tw.interval ?? h.interval;
    const mode = tw.mode ?? h.mode;
    const speeds = [...new Set([...SPEEDS, interval])].sort((a, b) => a - b);
    const changed = Object.keys(tw).length > 0;
    return `<h2>Tonight's look <span class="grow"></span><span class="tag">Admins</span></h2>
      <div class="row"><label class="muted" for="bri" style="min-width:84px">Brightness</label>
        <span id="bri-v" class="muted">${brightness ? `${brightness}%` : "Holiday's own"}</span></div>
      <input id="bri" type="range" min="0" max="100" step="5" value="${brightness}" data-change="brightness" ${off} aria-label="Brightness tonight">
      <div class="fields">
        <label class="muted" for="speed">Speed</label>
        <label class="muted" for="mode">Effect</label>
        <select id="speed" data-change="interval" ${off}>${speeds.map((v) => `<option value="${v}" ${v === interval ? "selected" : ""}>Every ${v < 60 ? `${v} s` : `${v / 60} min`}</option>`).join("")}</select>
        <select id="mode" data-change="mode" ${off}>${s.modes.map((m) => `<option value="${m}" ${m === mode ? "selected" : ""}>${esc(MODE_NAMES[m] || m)}</option>`).join("")}</select>
      </div>
      <div class="row" style="margin-top:12px">
        <button type="button" class="small primary" data-act="keep" ${off || (changed ? "" : "disabled")}>Keep these for ${esc(h.name)}</button>
        <button type="button" class="small" data-act="tweaks-reset" ${off || (changed ? "" : "disabled")}>Back to ${esc(h.name)}'s own</button>
      </div>
      <div class="muted" style="margin-top:6px">${changed ? "Tonight only, unless you keep them." : "Changes here last until tomorrow."}</div>`;
  }

  // --- Music -----------------------------------------------------------

  _musicHtml(s) {
    const m = s.music;
    const off = this._busy ? "disabled" : "";
    const volumes = m.players.map((p) => p.volume).filter((v) => v != null);
    const volume = volumes.length ? Math.round(volumes.reduce((a, b) => a + b, 0) / volumes.length) : 30;
    const playing = m.playing && !m.off_tonight;
    const status = playing
      ? `Playing <b>${esc(m.playing)}</b> music`
      : m.off_tonight ? "Stopped for tonight" : "Not playing";
    return `<h2>Theme music</h2>
      <div class="reason">${status}</div>
      <div class="muted">${esc(m.players.map((p) => `${p.name} (${p.state})`).join(", "))}</div>
      ${m.error ? `<div class="field-error" style="margin-top:6px">${esc(m.error)}</div>` : ""}
      <div class="row" style="margin-top:10px">
        <button type="button" class="small" data-act="music" data-action="play" ${off || (s.running ? "" : "disabled")}>${playing ? "Start again" : "Play"}</button>
        <button type="button" class="small" data-act="music" data-action="stop" ${off}>Stop for tonight</button>
      </div>
      <div class="row" style="margin-top:10px"><label class="muted" for="vol">Volume</label><span id="vol-v" class="muted">${volume}%</span></div>
      <input id="vol" type="range" min="0" max="100" step="5" value="${volume}" data-change="volume" ${off} aria-label="Music volume">`;
  }

  // --- Coming up -------------------------------------------------------

  _comingHtml(s) {
    const next = s.next;
    const countdown = next
      ? `<div class="countdown"><b>${esc(next.name)}</b> ${next.days <= 0 ? "starts today" : next.days === 1 ? "starts tomorrow" : `in <b>${next.days}</b> days`} · ${esc(fmtDay(next.date, { month: "long", day: "numeric" }))}</div>`
      : "";
    const days = (s.coming || []).map((night, i) => {
      const h = night.holiday;
      const date = localDay(night.date);
      return `<div class="day ${i === 0 ? "today" : ""}" title="${esc(fmtDay(night.date))}: ${esc(h ? h.name : "No lights")}">
        <div class="muted">${esc(i === 0 ? "Today" : date.toLocaleDateString([], { weekday: "short" }))}</div>
        <div class="n">${date.getDate()}</div>
        ${h ? swatches(h.colors.slice(0, 4)) : '<span class="muted">—</span>'}
        <div class="h">${esc(h ? h.name : "")}</div>
      </div>`;
    }).join("");
    return `<h2>Coming up</h2>${countdown}<div class="days">${days}</div>`;
  }

  // --- Holidays --------------------------------------------------------

  _whenText(h) {
    if (h.kind === "calendar") return "When your calendar says";
    if (!h.when) return "No date coming up";
    const end = fmtDay(h.when.end, { month: "short", day: "numeric" });
    if (h.when.now) return `On now, until ${end}`;
    const start = fmtDay(h.when.start, { month: "short", day: "numeric" });
    return start === end ? start : `${start} – ${end}`;
  }

  _holidaysHtml(s) {
    const admin = s.is_admin;
    const off = this._busy ? "disabled" : "";
    const rows = (s.holidays || []).map((h) => `
      <div class="item">
        ${swatches(h.colors, "lg")}
        <div class="main">
          <div class="title">${esc(h.name)}${s.shown && s.shown.id === h.id ? '<span class="tag">Tonight</span>' : ""}${h.music ? '<span class="tag">♪ Music</span>' : ""}</div>
          <div class="muted">${esc(this._whenText(h))} · ${esc(MODE_NAMES[h.mode] || h.mode)} · ${esc(plural(h.lights, "light"))}</div>
        </div>
        <div class="btns">
          <button type="button" class="small" data-act="preview" data-id="${esc(h.id)}">Preview</button>
          ${admin ? `<button type="button" class="small" data-act="try" data-id="${esc(h.id)}" ${off}>Try on the lights</button>
            <button type="button" class="small" data-act="edit" data-id="${esc(h.id)}">Edit</button>
            <button type="button" class="small link danger" data-act="remove" data-id="${esc(h.id)}" data-name="${esc(h.name)}">Remove</button>` : ""}
        </div>
      </div>`).join("");
    return `<h2>Holidays <span class="grow"></span>
        ${admin ? `<button type="button" class="small" data-act="settings">Settings</button>
          <button type="button" class="small primary" data-act="add">Add holiday</button>` : ""}</h2>
      <div class="list">${rows || '<div class="muted">No holidays yet.</div>'}</div>
      ${admin ? "" : '<div class="muted" style="margin-top:8px">Ask an admin to add or change holidays.</div>'}`;
  }

  // --- History ---------------------------------------------------------

  _historyHtml(s) {
    const nights = s.history || [];
    if (!nights.length) return `<h2>Last nights</h2><div class="muted">Nights the lights were on show up here.</div>`;
    const rows = nights.map((n) => {
      const notes = [];
      if (n.by === "button") notes.push('<span class="tag">Turned off by hand</span>');
      if (n.manual?.length) notes.push(`<span class="tag warn" title="${esc(n.manual.join(", "))}">${esc(plural(n.manual.length, "light"))} changed by hand</span>`);
      if (n.unavailable?.length) notes.push(`<span class="tag warn" title="${esc(n.unavailable.join(", "))}">${esc(plural(n.unavailable.length, "light"))} didn't respond</span>`);
      return `<div class="item">
        <div style="min-width:110px"><b>${esc(fmtDay(n.night))}</b></div>
        <div class="main"><div class="title">${swatches(n.colors)} ${esc(n.holiday)}</div>
          <div class="muted">${esc(clock(n.on))} – ${esc(clock(n.off))}</div></div>
        <div class="btns">${notes.join("")}</div>
      </div>`;
    }).join("");
    return `<h2>Last nights</h2><div class="list">${rows}</div>`;
  }

  // --- events ----------------------------------------------------------

  _onClick(ev) {
    const host = ev.target.closest(".dialog-host");
    if (host && ev.target === host) {
      this._closeDialog();
      return;
    }
    const el = ev.target.closest("[data-act], [data-menu-option]");
    if (!el || el.disabled) return;
    if (el.dataset.menuOption) {
      this._submitFlow({ next_step_id: el.dataset.menuOption });
      return;
    }
    const d = el.dataset;
    const s = this._state;
    switch (d.act) {
      case "press": {
        const done = { start: "Lights on.", next: "Next colors.", stop: "Off for tonight.", default: "Default colors tonight." };
        this._send("press", { action: d.action }, done[d.action]);
        break;
      }
      case "extend":
        this._send("off_tonight", { extend_minutes: Number(d.min) }, "Staying on longer tonight.");
        break;
      case "off-at": {
        const value = this.shadowRoot.getElementById("offat")?.value;
        if (value) this._send("off_tonight", { off_at: value }, `Off tonight at ${value}.`);
        break;
      }
      case "off-reset":
        this._send("off_tonight", { reset: true }, "Back to the usual off time.");
        break;
      case "keep":
        this._send("keep_tweaks", {}, "Saved to the holiday.").then(() => this._scheduleLoad(1500));
        break;
      case "tweaks-reset":
        this._send("tweaks", { reset: true }, "Back to the holiday's own look.");
        break;
      case "music":
        this._send("music", { action: d.action }, d.action === "play" ? "Music playing." : "Music stopped for tonight.");
        break;
      case "preview":
        this._startPreview(d.id);
        break;
      case "preview-stop":
        this._stopPreview();
        break;
      case "try":
        this._stopPreview(false);
        this._send("try", { holiday_id: d.id, minutes: 2 }, "Showing it on the lights for 2 minutes.");
        break;
      case "try-stop":
        this._send("try/stop", {}, "Back to normal.");
        break;
      case "bulb":
        this._openBulb(d.id);
        break;
      case "light":
        this._closeDialog();
        this._send("light", { entity_id: d.id, action: d.action }, {
          leave_out: "Left out tonight.", include: "Back in the show.", give_back: "Back in the show.",
        }[d.action]);
        break;
      case "edit":
        this._startFlow("subentry", "Edit holiday", { handler: [s.entry_id, "holiday"], subentry_id: d.id });
        break;
      case "add":
        this._startFlow("subentry", "Add holiday", { handler: [s.entry_id, "holiday"] });
        break;
      case "settings":
        this._startFlow("options", "Settings", { handler: s.entry_id });
        break;
      case "remove":
        this._confirmRemove(d.id, d.name);
        break;
      case "remove-yes":
        this._remove(d.id);
        break;
      case "flow-continue":
        this._submitFlow(this._flowInput || {});
        break;
      case "dialog-close":
        this._closeDialog();
        break;
      default:
        break;
    }
  }

  _onInput(ev) {
    const el = ev.target;
    if (el.id === "bri") {
      const v = Number(el.value);
      const label = this.shadowRoot.getElementById("bri-v");
      if (label) label.textContent = v ? `${v}%` : "Holiday's own";
    } else if (el.id === "vol") {
      const label = this.shadowRoot.getElementById("vol-v");
      if (label) label.textContent = `${el.value}%`;
    }
  }

  _onChange(ev) {
    const el = ev.target;
    const what = el.dataset?.change;
    if (!what) return;
    switch (what) {
      case "enabled":
        this._send("enabled", { enabled: el.checked }, el.checked ? "Enabled." : "Not enabled; lights put back.");
        break;
      case "theme":
        this._send("theme", { theme: el.value }, "Theme changed.");
        break;
      case "brightness":
        this._send("tweaks", { brightness: Number(el.value) }, "Brightness changed for tonight.");
        break;
      case "interval":
        this._send("tweaks", { interval: Number(el.value) }, "Speed changed for tonight.");
        break;
      case "mode":
        this._send("tweaks", { mode: el.value }, "Effect changed for tonight.");
        break;
      case "volume":
        this._send("music", { action: "volume", volume: Number(el.value) }, "Volume set.");
        break;
      default:
        break;
    }
    el.blur?.();
  }

  // --- dialogs ---------------------------------------------------------

  _dialog(title, body, foot = '<button type="button" data-act="dialog-close">Close</button>') {
    const host = this.shadowRoot.getElementById("dialog");
    host.innerHTML = `<div class="dialog-host"><div class="dialog" role="dialog" aria-modal="true" aria-label="${esc(title)}">
      <h3>${esc(title)}</h3><div class="body">${body}</div><div class="foot">${foot}</div></div></div>`;
    host.querySelector(".dialog button, .dialog input, .dialog select")?.focus?.();
  }

  _closeDialog() {
    this._activeFlow = null;
    this.shadowRoot.getElementById("dialog").innerHTML = "";
  }

  _openBulb(id) {
    const s = this._state;
    const light = (s?.lights || []).find((l) => l.entity_id === id);
    if (!light) return;
    const describe = {
      color: `Showing <b>${esc(light.color_name || light.color || "a color")}</b>${s.shown ? ` for ${esc(s.shown.name)}` : ""}.`,
      manual: "Someone changed this light by hand, so the show leaves it alone tonight.",
      off: light.in_show ? "Off right now. It's part of tonight's show." : "Not part of tonight's holiday.",
      left_out: "Left out of the show tonight. It's back in tomorrow.",
    }[light.state] || "";
    const swatch = light.state === "color" && light.color
      ? `<div class="big-swatch" style="background:${esc(light.color)};box-shadow:0 0 16px ${esc(light.color)}"></div>` : "";
    const buttons = [];
    if (light.state === "manual") buttons.push(`<button type="button" class="primary" data-act="light" data-action="give_back" data-id="${esc(id)}">Give back to the show</button>`);
    if (light.state === "left_out") buttons.push(`<button type="button" class="primary" data-act="light" data-action="include" data-id="${esc(id)}">Put back in the show</button>`);
    else buttons.push(`<button type="button" data-act="light" data-action="leave_out" data-id="${esc(id)}">Leave out tonight</button>`);
    buttons.push('<button type="button" data-act="dialog-close">Close</button>');
    this._dialog(light.name, `<div class="row" style="align-items:center;gap:14px">${swatch}<p style="margin:0">${describe}</p></div>
      ${light.available ? "" : '<p class="field-error" style="margin-top:10px">This light isn\'t responding.</p>'}
      <p class="muted" style="margin-top:10px">A light left out goes back to how it was before the show.</p>`, buttons.join(""));
  }

  _confirmRemove(id, name) {
    this._dialog(`Remove ${name}?`, `<p>${esc(name)} and its colors and lights will be removed. This can't be undone.</p>`,
      `<button type="button" data-act="dialog-close">Cancel</button>
       <button type="button" class="primary" data-act="remove-yes" data-id="${esc(id)}">Remove</button>`);
  }

  async _remove(id) {
    try {
      await this._hass.callWS({ type: "config_entries/subentries/delete", entry_id: this._state.entry_id, subentry_id: id });
      this._closeDialog();
      this._note("Holiday removed.");
    } catch (err) {
      this._dialog("Couldn't remove it", `<p class="field-error">${esc(err?.message || err)}</p>`);
    }
    this._scheduleLoad(1500);
  }

  // --- Home Assistant's own config flows, in a dialog ------------------

  _apiPath(kind, flowId) {
    const paths = { subentry: "config/config_entries/subentries/flow", options: "config/config_entries/options/flow" };
    return `${paths[kind]}${flowId ? `/${encodeURIComponent(flowId)}` : ""}`;
  }

  _flowKey(suffix) {
    const prefix = FLOW_PREFIX[this._activeFlow?.kind];
    return prefix ? `${prefix}.${suffix}` : "";
  }

  async _flowCall(method, flow, body) {
    return this._hass.callApi(method, this._apiPath(flow.kind, flow.flowId), body, {
      "HA-Frontend-Base": `${window.location.protocol}//${window.location.host}`,
    });
  }

  // Home Assistant loads its form element on demand; the card helpers
  // bring it in when no settings page has been opened yet.
  async _formReady() {
    if (customElements.get("ha-form")) return true;
    try {
      await window.loadCardHelpers?.();
    } catch (_err) {
      // fall through to the wait below
    }
    return Promise.race([
      customElements.whenDefined("ha-form").then(() => true),
      new Promise((resolve) => setTimeout(() => resolve(false), 4000)),
    ]);
  }

  async _startFlow(kind, title, payload) {
    const flow = { kind, title, flowId: null };
    this._activeFlow = flow;
    this._dialog(title, '<p class="muted">Opening…</p>', '<button type="button" data-act="dialog-close">Cancel</button>');
    if (!(await this._formReady())) {
      if (this._activeFlow !== flow) return;
      this._activeFlow = null;
      this._dialog(title, "<p>The form couldn't load here. Open <b>Settings → Devices &amp; services → Holiday Lighting</b> to make this change.</p>");
      return;
    }
    try {
      const step = await this._flowCall("POST", flow, payload);
      if (this._activeFlow !== flow) return;
      flow.flowId = step.flow_id;
      this._showFlowStep(step);
    } catch (err) {
      if (this._activeFlow === flow) this._flowError(err);
    }
  }

  async _submitFlow(input) {
    const flow = this._activeFlow;
    if (!flow?.flowId) return;
    const form = this.shadowRoot.querySelector("#flow-form");
    if (form?.reportValidity && !form.reportValidity()) return;
    if (form) form.disabled = true;
    try {
      const step = await this._flowCall("POST", flow, input);
      if (this._activeFlow !== flow) return;
      this._showFlowStep(step);
    } catch (err) {
      if (this._activeFlow === flow) this._flowError(err);
    }
  }

  _flowError(err) {
    this._activeFlow = null;
    this._dialog("Something went wrong", `<p class="field-error">${esc(err?.body?.message || err?.message || err)}</p>`);
  }

  _showFlowStep(step) {
    const flow = this._activeFlow;
    const placeholders = step.description_placeholders || {};
    if (step.type === "create_entry" || (step.type === "abort" && String(step.reason).endsWith("_successful"))) {
      this._activeFlow = null;
      this._dialog("Saved", "<p>Your changes are saved. The lights pick them up straight away.</p>");
      this._scheduleLoad(1500);
      return;
    }
    if (step.type === "abort") {
      this._activeFlow = null;
      const message = this._t(this._flowKey(`abort.${step.reason}`), placeholders) || String(step.reason).replaceAll("_", " ");
      this._dialog("Not changed", `<p>${esc(message)}</p>`);
      return;
    }
    if (step.type === "menu") {
      const key = `step.${step.step_id}`;
      const options = Array.isArray(step.menu_options)
        ? step.menu_options.map((o) => [o, this._t(this._flowKey(`${key}.menu_options.${o}`), placeholders) || o.replaceAll("_", " ")])
        : Object.entries(step.menu_options);
      const description = this._t(this._flowKey(`${key}.description`), placeholders);
      this._dialog(this._t(this._flowKey(`${key}.title`), placeholders) || flow.title,
        `${description ? `<p>${esc(description)}</p>` : ""}<div class="flow-menu">${options.map(([o, label]) =>
          `<button type="button" data-menu-option="${esc(o)}">${esc(label)}</button>`).join("")}</div>`,
        '<button type="button" data-act="dialog-close">Cancel</button>');
      return;
    }
    if (step.type === "form") {
      const key = `step.${step.step_id}`;
      this._flowInput = Object.fromEntries(
        step.data_schema
          .map((f) => [f.name, f.description?.suggested_value ?? f.default])
          .filter(([, v]) => v !== undefined),
      );
      const description = this._t(this._flowKey(`${key}.description`), placeholders);
      const base = step.errors?.base;
      this._dialog(this._t(this._flowKey(`${key}.title`), placeholders) || flow.title,
        `${description ? `<p>${esc(description)}</p>` : ""}
         ${base ? `<p class="field-error">${esc(this._t(this._flowKey(`error.${base}`), placeholders) || base)}</p>` : ""}
         <ha-form id="flow-form"></ha-form>`,
        `<button type="button" data-act="dialog-close">Cancel</button>
         <button type="button" class="primary" data-act="flow-continue">${step.last_step === false ? "Next" : "Save"}</button>`);
      const form = this.shadowRoot.querySelector("#flow-form");
      if (!form) return;
      form.hass = this._hass;
      form.schema = step.data_schema;
      form.data = this._flowInput;
      form.error = step.errors || undefined;
      form.computeLabel = (field) =>
        this._t(this._flowKey(`${key}.data.${field.name}`), placeholders)
        || this._t(this._flowKey(`${key}.sections.${field.name}.name`), placeholders)
        || field.name.replaceAll("_", " ");
      form.computeHelper = (field) =>
        this._t(this._flowKey(`${key}.data_description.${field.name}`), placeholders)
        || this._t(this._flowKey(`${key}.sections.${field.name}.description`), placeholders);
      form.computeError = (error) => this._t(this._flowKey(`error.${error}`), placeholders) || error;
      form.localizeValue = (k) => this._t(`component.${DOMAIN}.selector.${k}`);
      form.context = { domain: DOMAIN };
      return;
    }
    if (step.type === "progress") {
      this._dialog(flow.title, '<p class="muted">Working…</p>');
      setTimeout(async () => {
        if (this._activeFlow !== flow) return;
        try {
          this._showFlowStep(await this._flowCall("GET", flow));
        } catch (err) {
          if (this._activeFlow === flow) this._flowError(err);
        }
      }, 500);
      return;
    }
    this._flowError(new Error(`This step isn't supported here: ${step.type}`));
  }
}

if (!customElements.get("holiday-lighting-panel")) {
  customElements.define("holiday-lighting-panel", HolidayLightingPanel);
}
