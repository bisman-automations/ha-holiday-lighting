/*
 * Holiday Lights sidebar panel.
 *
 * Reads the integration's own sensors from hass.states (no extra API):
 *   sensor.holiday_lighting_status, sensor.holiday_lighting_active_holiday,
 *   sensor.holiday_lighting_lights_on_at, sensor.holiday_lighting_lights_off_at,
 *   and one light-color sensor per light (attributes: light, hex, shown_as).
 */

const STATUS = "sensor.holiday_lighting_status";
const ACTIVE = "sensor.holiday_lighting_active_holiday";
const ON_AT = "sensor.holiday_lighting_lights_on_at";
const OFF_AT = "sensor.holiday_lighting_lights_off_at";

const STYLE = `
  :host {
    display: block;
    min-height: 100%;
    background: var(--primary-background-color, #111318);
    color: var(--primary-text-color, #e1e1e1);
    font-family: var(--paper-font-body1_-_font-family, inherit);
  }
  .wrap { max-width: 720px; margin: 0 auto; padding: 16px; box-sizing: border-box; }
  .stage {
    position: relative;
    border-radius: 16px;
    padding: 28px 16px 20px;
    background: radial-gradient(ellipse at top, #1d2233 0%, #0b0d14 75%);
    color: #e9ecf5;
    overflow: hidden;
    min-height: 150px;
  }
  .bulbs { display: flex; flex-wrap: wrap; justify-content: center; gap: 18px 22px; }
  .bulb { display: flex; flex-direction: column; align-items: center; width: 88px; }
  .glow {
    width: 42px; height: 52px; border-radius: 50% 50% 46% 46% / 60% 60% 40% 40%;
    background: #2a2e3b;
    border: 1px solid #3b4050;
    transition: background-color 1.4s ease, box-shadow 1.4s ease, border-color 1.4s ease;
  }
  .bulb.lit .glow {
    background: var(--c);
    border-color: transparent;
    box-shadow: 0 0 14px 4px var(--c), 0 0 34px 10px color-mix(in srgb, var(--c) 45%, transparent);
  }
  .bulb.manual .glow {
    background: repeating-linear-gradient(45deg, #2a2e3b 0 6px, #4a4f60 6px 12px);
  }
  .label {
    margin-top: 8px; font-size: 13px; text-align: center;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 100%;
    opacity: 0.9;
  }
  .sub { font-size: 12px; opacity: 0.65; text-align: center; }
  .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-top: 16px; }
  .card {
    background: var(--card-background-color, #fff);
    color: var(--primary-text-color);
    border-radius: 12px; padding: 14px 16px;
    box-shadow: var(--ha-card-box-shadow, none);
    border: 1px solid var(--divider-color, #e0e0e0);
  }
  .card .k { font-size: 12px; opacity: 0.6; text-transform: uppercase; letter-spacing: .04em; }
  .card .v { font-size: 17px; margin-top: 4px; word-break: break-word; }
  h1 { font-size: 22px; font-weight: 500; margin: 0 0 12px; color: inherit; }
  .msg { padding: 24px; text-align: center; opacity: 0.8; }

  /* Loading: shimmering placeholders in the same layout. */
  .skeleton {
    background: linear-gradient(90deg, rgba(255,255,255,0.06) 25%, rgba(255,255,255,0.16) 50%, rgba(255,255,255,0.06) 75%);
    background-size: 200% 100%;
    animation: shimmer 1.4s ease-in-out infinite;
    border-radius: 8px;
  }
  .skeleton.bulb-ph { width: 42px; height: 52px; border-radius: 50%; }
  .skeleton.line { height: 14px; width: 60%; margin: 6px auto; }
  .card.skeleton-card { background: var(--card-background-color, #fff); border: 1px solid var(--divider-color, #e0e0e0); }
  .card.skeleton-card .skeleton { height: 16px; width: 70%; margin: 4px 0; background: linear-gradient(90deg, rgba(0,0,0,0.06) 25%, rgba(0,0,0,0.14) 50%, rgba(0,0,0,0.06) 75%); background-size: 200% 100%; }
  .card.skeleton-card .skeleton.small { width: 40%; height: 10px; }
  @keyframes shimmer { 0% { background-position: 100% 0; } 100% { background-position: -100% 0; } }

  @media (prefers-reduced-motion: reduce) {
    .glow, .skeleton { transition: none; animation: none; }
  }
`;

const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const timeText = (state) => {
  if (!state || state.state === "unknown" || state.state === "unavailable") return "—";
  const d = new Date(state.state);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString([], { weekday: "short", hour: "numeric", minute: "2-digit" });
};

const isLight = (s) => s && s.attributes && "light" in s.attributes && "hex" in s.attributes;

class HolidayLightingPanel extends HTMLElement {
  constructor() {
    super();
    this._hass = undefined;
    this._built = false;
    this._lightKeys = "";
    this._lastKey = "";
    this._bulbs = new Map();
  }

  set hass(hass) {
    this._hass = hass;
    this._update();
  }

  get hass() {
    return this._hass;
  }

  connectedCallback() {
    if (!this._built) this._build();
    this._update();
  }

  _build() {
    const root = this.attachShadow({ mode: "open" });
    root.innerHTML = `
      <style>${STYLE}</style>
      <div class="wrap">
        <h1>Holiday Lights</h1>
        <div id="stage" class="stage" aria-live="polite"></div>
        <div id="cards" class="cards"></div>
      </div>`;
    this._stage = root.getElementById("stage");
    this._cards = root.getElementById("cards");
    // Show placeholders until Home Assistant sends the first state update.
    const sk = this._skeleton();
    this._stage.innerHTML = sk.stage;
    this._cards.innerHTML = sk.cards;
    this._built = true;
  }

  _skeleton() {
    const bulbs = Array.from({ length: 6 }, () => '<div class="bulb"><div class="skeleton bulb-ph"></div><div class="skeleton line" style="width:70%"></div></div>').join("");
    const cards = Array.from({ length: 4 }, () => '<div class="card skeleton-card"><div class="skeleton small"></div><div class="skeleton"></div></div>').join("");
    return { stage: `<div class="bulbs" role="status" aria-label="Loading holiday lights">${bulbs}</div>`, cards };
  }

  _update() {
    if (!this._built || !this._hass) return;
    const states = this._hass.states || {};
    const count = Object.keys(states).length;

    // Still loading: no entities received yet.
    if (count === 0) {
      const sk = this._skeleton();
      this._stage.innerHTML = sk.stage;
      this._cards.innerHTML = sk.cards;
      this._bulbs.clear();
      this._lightKeys = "";
      this._lastKey = "";
      return;
    }

    const status = states[STATUS];
    if (!status) {
      this._stage.innerHTML = '<div class="msg">Holiday Lighting is not set up yet.</div>';
      this._cards.innerHTML = "";
      this._bulbs.clear();
      this._lightKeys = "";
      this._lastKey = "";
      return;
    }

    const lights = Object.values(states)
      .filter(isLight)
      .sort((a, b) => a.attributes.light.localeCompare(b.attributes.light));
    const active = states[ACTIVE];
    const onAt = states[ON_AT];
    const offAt = states[OFF_AT];

    // Skip the DOM work when nothing the panel shows has changed.
    const key = JSON.stringify([
      status.state, active?.state, active?.attributes?.next_holiday,
      onAt?.state, offAt?.state,
      lights.map((l) => [l.attributes.light, l.state, l.attributes.hex, l.attributes.shown_as, l.attributes.holiday ?? null]),
    ]);
    if (key === this._lastKey) return;
    this._lastKey = key;

    this._renderBulbs(lights);
    const activeName = active?.state && active.state !== "unknown" ? active.state : "No holiday";
    const cards = [
      ["Status", status.state],
      ["Active holiday", activeName],
      ["Lights on at", timeText(onAt)],
      ["Lights off at", timeText(offAt)],
    ];
    this._cards.innerHTML = cards
      .map(([k, v]) => `<div class="card"><div class="k">${esc(k)}</div><div class="v">${esc(v)}</div></div>`)
      .join("");
  }

  _renderBulbs(lights) {
    if (lights.length === 0) {
      this._stage.innerHTML = '<div class="msg">No lights are set up for Holiday Lighting.</div>';
      this._bulbs.clear();
      this._lightKeys = "";
      return;
    }
    const ids = lights.map((l) => l.attributes.light).join("|");
    if (ids !== this._lightKeys) {
      // The light set changed: rebuild once, then animate in place after this.
      this._lightKeys = ids;
      this._stage.innerHTML = '<div class="bulbs"></div>';
      this._bulbs.clear();
      const wrap = this._stage.firstElementChild;
      for (const light of lights) {
        const el = document.createElement("div");
        el.className = "bulb";
        el.innerHTML = '<div class="glow"></div><div class="label"></div><div class="sub"></div>';
        wrap.appendChild(el);
        this._bulbs.set(light.attributes.light, el);
      }
    }
    for (const light of lights) {
      const el = this._bulbs.get(light.attributes.light);
      if (!el) continue;
      const lit = light.attributes.hex && light.state !== "Off" && light.state !== "Manual";
      el.classList.toggle("lit", Boolean(lit));
      el.classList.toggle("manual", light.state === "Manual");
      if (lit) el.style.setProperty("--c", light.attributes.hex);
      else el.style.removeProperty("--c");
      const name = light.attributes.friendly_name || light.attributes.light;
      el.querySelector(".label").textContent = name;
      el.querySelector(".label").title = name;
      const sub = light.state === "Off" ? "Off" : light.state;
      el.querySelector(".sub").textContent = sub;
    }
  }
}

if (!customElements.get("holiday-lighting-panel")) {
  customElements.define("holiday-lighting-panel", HolidayLightingPanel);
}
