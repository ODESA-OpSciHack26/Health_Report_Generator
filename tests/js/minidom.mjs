/* A deliberately small DOM subset for executing the composer frontend outside a browser.
 *
 * It implements only the API surface src/composer_web/app.js uses, and it follows the
 * specifications for that surface. In particular:
 *   - Element.append(...) returns **undefined**, exactly as in a browser, so code that chains
 *     a DOM mutator fails here the same way it fails in a browser;
 *   - getElementById() returns null when the id is absent, so a missing element fails loudly.
 *
 * It is not a browser: no layout, no CSS, no event bubbling, no HTML parsing beyond the ids in
 * index.html. A pass here proves the rendering statements execute against a DOM contract; it
 * does not prove pixels, focus order or accessibility. The real-browser retest stays required.
 */

function splitClasses(value) {
  return new Set(String(value || "").split(/\s+/).filter(Boolean));
}

export class Element {
  constructor(tagName) {
    this.tagName = String(tagName || "div").toUpperCase();
    this.children = [];
    this.parentElement = null;
    this.attributes = new Map();
    this.listeners = new Map();
    this._text = "";
    this._classes = new Set();
    this.id = "";
    this.hidden = false;
    this.disabled = false;
    this.checked = false;
    this.open = false;
    this._value = "";
    this.type = "";
    this.href = "";
    this.src = "";
    this.title = "";
    this.min = "";
    this.max = "";
    this.tabIndex = -1;
    this.dataset = {};
  }

  /* A <select> reports the selected option's value, like a browser; an explicit assignment
     selects the matching option as well. */
  get value() {
    const options = (this.children || []).filter((child) => child.tagName === "OPTION");
    const selected = options.find((option) => option.selected);
    if (this.tagName === "SELECT" && selected) return selected.value;
    return this._value;
  }
  set value(next) {
    this._value = String(next);
    if (this.tagName !== "SELECT") return;
    for (const option of (this.children || []).filter((child) => child.tagName === "OPTION")) {
      option.selected = option.value === this._value;
    }
  }

  get className() { return [...this._classes].join(" "); }
  set className(value) { this._classes = splitClasses(value); }

  get textContent() {
    if (this.children.length) return this.children.map((child) => child.textContent).join("");
    return this._text;
  }
  set textContent(value) {
    this.children = [];
    this._text = value === null || value === undefined ? "" : String(value);
  }

  append(...nodes) {
    for (const node of nodes) {
      if (node === null || node === undefined) continue;
      if (typeof node === "string") { this._text += node; continue; }
      node.parentElement = this;
      this.children.push(node);
    }
    // Spec: Element.append() returns undefined. Do not return `this`.
  }

  appendChild(node) { this.append(node); return node; }

  prepend(...nodes) {
    const tail = this.children;
    const head = [];
    for (const node of nodes) {
      if (node === null || node === undefined) continue;
      if (typeof node === "string") { head.push(Object.assign(new Element("#text"), { _text: node })); continue; }
      node.parentElement = this;
      head.push(node);
    }
    this.children = head.concat(tail);
    // Spec: ParentNode.prepend() returns undefined.
  }

  replaceChildren(...nodes) {
    for (const child of this.children) child.parentElement = null;
    this.children = [];
    this._text = "";
    this.append(...nodes);
  }

  setAttribute(name, value) {
    if (name === "id") { this.id = String(value); return; }
    if (name === "class") { this.className = value; return; }
    this.attributes.set(name, String(value));
  }
  getAttribute(name) { return this.attributes.has(name) ? this.attributes.get(name) : null; }
  removeAttribute(name) { this.attributes.delete(name); }

  addEventListener(type, handler) {
    if (!this.listeners.has(type)) this.listeners.set(type, []);
    this.listeners.get(type).push(handler);
  }

  fire(type, event = {}) {
    const handlers = this.listeners.get(type) || [];
    const base = { type, target: this, preventDefault() {}, stopPropagation() {} };
    for (const handler of handlers) handler(Object.assign(base, event));
  }

  focus() { if (this.ownerDocument) this.ownerDocument.activeElement = this; }

  matches(selector) {
    if (selector.startsWith("#")) return this.id === selector.slice(1);
    if (selector.startsWith(".")) return this._classes.has(selector.slice(1));
    const data = selector.match(/^\[data-([a-z0-9-]+)="?(.*?)"?\]$/i);
    if (data) {
      const key = data[1].replace(/-([a-z])/g, (_, letter) => letter.toUpperCase());
      return this.dataset[key] === data[2];
    }
    return this.tagName === selector.toUpperCase();
  }

  querySelector(selector) {
    for (const child of this.children) {
      if (child.matches && child.matches(selector)) return child;
      const nested = child.querySelector ? child.querySelector(selector) : null;
      if (nested) return nested;
    }
    return null;
  }

  querySelectorAll(selector) {
    const found = [];
    for (const child of this.children) {
      if (child.matches && child.matches(selector)) found.push(child);
      if (child.querySelectorAll) found.push(...child.querySelectorAll(selector));
    }
    return found;
  }

  get classList() {
    const set = this._classes;
    return {
      contains: (name) => set.has(name),
      add: (name) => { set.add(name); },
      remove: (name) => { set.delete(name); },
    };
  }
}

export class Document {
  constructor() {
    this.byId = new Map();
    this.listeners = new Map();
    this.activeElement = null;
    this.body = new Element("body");
    this.body.ownerDocument = this;
  }

  createElement(tagName) {
    const element = new Element(tagName);
    element.ownerDocument = this;
    return element;
  }

  getElementById(id) {
    // Browsers resolve ids anywhere in the tree, including elements created at runtime.
    if (this.byId.has(id)) return this.byId.get(id);
    const walk = (node) => {
      for (const child of node.children || []) {
        if (child.id === id) return child;
        const hit = walk(child);
        if (hit) return hit;
      }
      return null;
    };
    return walk(this.body);
  }

  /** Register every id found in index.html, so a missing id fails like it would in a browser. */
  registerIds(html) {
    // Parse the tag that carries each id so static classes and ARIA attributes are visible to
    // checks, the way they are in a browser.
    const pattern = /<[^>]*\bid="([^"]+)"[^>]*>/g;
    let match = pattern.exec(html);
    while (match) {
      const tag = match[0];
      const element = this.createElement("div");
      element.id = match[1];
      const classes = /\bclass="([^"]*)"/.exec(tag);
      if (classes) element.className = classes[1];
      const expanded = /\baria-expanded="([^"]*)"/.exec(tag);
      if (expanded) element.setAttribute("aria-expanded", expanded[1]);
      this.byId.set(match[1], element);
      this.body.append(element);
      match = pattern.exec(html);
    }
    return this.byId.size;
  }

  addEventListener(type, handler) {
    if (!this.listeners.has(type)) this.listeners.set(type, []);
    this.listeners.get(type).push(handler);
  }

  fire(type, event = {}) {
    for (const handler of this.listeners.get(type) || []) {
      handler(Object.assign({ type, target: this }, event));
    }
  }

  querySelector(selector) { return this.body.querySelector(selector); }
  querySelectorAll(selector) { return this.body.querySelectorAll(selector); }
}
