import json
import streamlit as st

st.set_page_config(
    page_title="Reddit Chat Delete/Hide Script Generator",
    page_icon="🧹",
    layout="centered"
)

st.title("Reddit Chat Delete/Hide Script Generator")
st.caption("Generate a selected-chat delete/hide script, then paste it into Reddit's DevTools Console.")

st.warning(
    "Hosted Streamlit apps cannot directly control reddit.com in your browser. "
    "This app generates JavaScript that you paste into the Console on a Reddit chat page."
)

username = st.text_input("Reddit username", placeholder="without u/")

speed = st.slider(
    "Max deletes per minute",
    min_value=20,
    max_value=120,
    value=60,
    step=10
)

retry_rounds = st.slider(
    "Max retry rounds per chat",
    min_value=2,
    max_value=20,
    value=6,
    step=1,
    help="The script retries messages that remain visible after a delete attempt."
)

no_progress_rounds = st.slider(
    "Stop after this many no-progress rounds",
    min_value=1,
    max_value=6,
    value=2,
    step=1,
    help="Stops a chat if the same visible message refuses to delete."
)

hide_after_delete = st.checkbox(
    "Hide selected chats after cleaning",
    value=True,
    help="After cleaning, the script will click the top-right gear, then Hide chat, then Yes, Hide."
)

generate = st.button(
    "Generate selected-chat delete/hide script",
    type="primary",
    use_container_width=True
)

JS_TEMPLATE = r"""
// Reddit Selected-Chat Own-Message Delete + Hide
// Important fix in this version:
// - It will NOT count a message as deleted just because the DOM re-rendered.
// - It waits for the "Delete this message?" popup to close.
// - It verifies the same message signature is gone before counting success.
// - It closes a stuck delete popup before moving to hide.
// - It does not try to hide unless the chat actually opened.
// - Deletes only YOUR sent Reddit chat messages.
// - Does NOT delete Reddit comments.
// - Does NOT delete Reddit posts.

(async () => {
  const USERNAME = __USERNAME_JSON__;
  const MAX_DELETES_PER_MINUTE = __MAX_DELETES__;
  const MAX_RETRY_ROUNDS_PER_CHAT = __MAX_RETRY_ROUNDS__;
  const MAX_NO_PROGRESS_ROUNDS = __MAX_NO_PROGRESS_ROUNDS__;
  const HIDE_AFTER_DELETE = __HIDE_AFTER_DELETE__;

  const DELETE_DELAY_MS = Math.ceil(60000 / MAX_DELETES_PER_MINUTE);
  const SHORT_DELAY_MS = 120;
  const MENU_DELAY_MS = 220;
  const SCROLL_DELAY_MS = 700;
  const CHAT_SWITCH_DELAY_MS = 1500;
  const SIDEBAR_RECOVERY_DELAY_MS = 1100;
  const HIDE_DELAY_MS = 1300;
  const CONFIRM_TIMEOUT_MS = 9000;
  const GONE_CHECK_TIMEOUT_MS = 4500;
  const GONE_CHECK_INTERVAL_MS = 200;

  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  const safeString = (value) => {
    try {
      if (value === null || value === undefined) return "";
      if (typeof value === "string") return value;
      if (typeof value === "number" || typeof value === "boolean") return String(value);

      if (typeof value === "object") {
        if ("baseVal" in value) return String(value.baseVal || "");
        if ("animVal" in value) return String(value.animVal || "");
        if ("value" in value) return String(value.value || "");
      }

      return String(value);
    } catch {
      return "";
    }
  };

  const escapeRegExp = (value) =>
    safeString(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

  const cleanText = (text) =>
    safeString(text).replace(/\s+/g, " ").trim();

  const normalizeText = (text) =>
    cleanText(text).toLowerCase();

  const getAttributeSafe = (el, name) => {
    try {
      if (!el || !el.getAttribute) return "";
      return safeString(el.getAttribute(name));
    } catch {
      return "";
    }
  };

  const getHrefSafe = (el) => {
    try {
      if (!el) return "";
      return safeString(el.href) || getAttributeSafe(el, "href");
    } catch {
      return "";
    }
  };

  const sidebarRight = () =>
    Math.min(440, Math.max(285, window.innerWidth * 0.42));

  const deepNodes = function* (root = document) {
    yield root;

    if (root instanceof Element && root.shadowRoot) {
      yield* deepNodes(root.shadowRoot);
    }

    const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT);

    while (walker.nextNode()) {
      const el = walker.currentNode;
      yield el;

      if (el.shadowRoot) {
        yield* deepNodes(el.shadowRoot);
      }
    }
  };

  const deepQueryAll = (selector, root = document) => {
    const out = [];

    for (const node of deepNodes(root)) {
      if (!node.querySelectorAll) continue;

      try {
        out.push(...node.querySelectorAll(selector));
      } catch {}
    }

    return [...new Set(out)];
  };

  const isVisible = (el) => {
    if (!el || !(el instanceof Element)) return false;

    try {
      const r = el.getBoundingClientRect();
      const s = getComputedStyle(el);

      return (
        r.width > 0 &&
        r.height > 0 &&
        s.display !== "none" &&
        s.visibility !== "hidden" &&
        s.opacity !== "0"
      );
    } catch {
      return false;
    }
  };

  const localQuery = (root, selector) => {
    const walk = (node) => {
      if (!node) return null;

      if (node.querySelector) {
        try {
          const found = node.querySelector(selector);
          if (found) return found;
        } catch {}
      }

      if (node.shadowRoot) {
        const found = walk(node.shadowRoot);
        if (found) return found;
      }

      for (const child of node.children || []) {
        const found = walk(child);
        if (found) return found;
      }

      return null;
    };

    return walk(root);
  };

  const getReadableText = (el) => {
    if (!el) return "";

    const values = [
      safeString(el.innerText),
      safeString(el.textContent),
      getAttributeSafe(el, "aria-label"),
      getAttributeSafe(el, "title"),
      getHrefSafe(el)
    ];

    return values.find((v) => cleanText(v))?.trim() || "";
  };

  const getElementHref = (el) => {
    const link = localQuery(el, "a");
    return getHrefSafe(el) || getHrefSafe(link) || "";
  };

  const clickElementOrClickableAncestor = (el) => {
    if (!el) return false;

    const clickable = el.closest?.(
      'button, [role="button"], [role="menuitem"], a, rs-button, rs-menu-item, rs-dropdown-item'
    );

    if (clickable && isVisible(clickable)) {
      clickable.click();
      return true;
    }

    el.click();
    return true;
  };

  const clickAt = (x, y) => {
    const el = document.elementFromPoint(x, y);
    if (!el) return false;

    try {
      el.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, cancelable: true, clientX: x, clientY: y }));
      el.dispatchEvent(new MouseEvent("mousedown", { bubbles: true, cancelable: true, clientX: x, clientY: y }));
      el.dispatchEvent(new PointerEvent("pointerup", { bubbles: true, cancelable: true, clientX: x, clientY: y }));
      el.dispatchEvent(new MouseEvent("mouseup", { bubbles: true, cancelable: true, clientX: x, clientY: y }));
      el.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true, clientX: x, clientY: y }));
    } catch {
      clickElementOrClickableAncestor(el);
    }

    return true;
  };

  const clickRowByCoordinates = (rowEl, savedChat = null) => {
    if (!rowEl && savedChat?.clickX != null && savedChat?.clickY != null) {
      return clickAt(savedChat.clickX, savedChat.clickY);
    }

    if (!rowEl || !isVisible(rowEl)) return false;

    const r = rowEl.getBoundingClientRect();

    const points = [
      [Math.min(Math.max(r.left + 54, 18), Math.min(r.right - 10, sidebarRight() - 10)), r.top + r.height / 2],
      [Math.min(Math.max(r.left + 115, 18), Math.min(r.right - 10, sidebarRight() - 10)), r.top + r.height / 2],
      [Math.min(Math.max(r.left + 190, 18), Math.min(r.right - 10, sidebarRight() - 10)), r.top + r.height / 2]
    ];

    for (const [x, y] of points) {
      if (clickAt(x, y)) return true;
    }

    return clickElementOrClickableAncestor(rowEl);
  };

  const findVisibleByText = (selectors, regex) =>
    deepQueryAll(selectors)
      .filter(isVisible)
      .find((el) => regex.test(cleanText(getReadableText(el))));

  const getParentElementAcrossShadow = (el) => {
    if (!el) return null;
    if (el.parentElement) return el.parentElement;

    const root = el.getRootNode?.();
    if (root && root.host) return root.host;

    return null;
  };

  const isBadSidebarText = (text) => {
    const cleaned = normalizeText(text);

    if (!cleaned) return true;

    if (
      /^(chats|threads|select reddit chats to clean|select all|select none|cancel|delete\/hide selected chats|delete selected chats)$/.test(cleaned)
    ) {
      return true;
    }

    return /create|settings|logout|advertise|premium|popular|home|all|notifications|explore|search|close|back|help|privacy|terms|reddit recap|communities|custom feeds|hide after cleaning|found \d+ visible chat/i.test(cleaned);
  };

  const isCandidateSidebarRect = (r) => (
    r.top >= 32 &&
    r.bottom <= window.innerHeight + 20 &&
    r.left >= -8 &&
    r.left < sidebarRight() &&
    r.right > 70 &&
    r.right <= sidebarRight() + 80 &&
    r.width >= 45 &&
    r.width <= sidebarRight() + 95 &&
    r.height >= 16 &&
    r.height <= 115
  );

  const isPreferredRowRect = (r) => (
    r.left >= -8 &&
    r.left <= 42 &&
    r.right >= 180 &&
    r.right <= sidebarRight() + 80 &&
    r.width >= 175 &&
    r.height >= 38 &&
    r.height <= 100 &&
    r.top >= 32 &&
    r.bottom <= window.innerHeight + 20
  );

  const collectTextInsideRect = (rect) => {
    const fragments = [];

    for (const node of deepNodes(document)) {
      if (!(node instanceof Element)) continue;
      if (!isVisible(node)) continue;

      const r = node.getBoundingClientRect();

      const verticalOverlap =
        Math.max(0, Math.min(rect.bottom, r.bottom) - Math.max(rect.top, r.top));

      const horizontalOverlap =
        Math.max(0, Math.min(sidebarRight() + 10, r.right) - Math.max(0, r.left));

      if (verticalOverlap <= 0 || horizontalOverlap <= 0) continue;
      if (r.left < -5 || r.left > sidebarRight()) continue;
      if (r.width > sidebarRight() + 80) continue;
      if (r.height > 130) continue;

      const text = cleanText(
        safeString(node.innerText) ||
        safeString(node.textContent) ||
        getAttributeSafe(node, "aria-label") ||
        getAttributeSafe(node, "title")
      );

      if (!text || text.length > 240) continue;
      if (isBadSidebarText(text)) continue;

      fragments.push({
        text,
        top: r.top,
        left: r.left
      });
    }

    const unique = [];
    const seen = new Set();

    for (const item of fragments.sort((a, b) => {
      if (Math.abs(a.top - b.top) > 4) return a.top - b.top;
      return a.left - b.left;
    })) {
      const key = normalizeText(item.text);

      if (!key || seen.has(key)) continue;

      seen.add(key);
      unique.push(item.text);
    }

    return cleanText(unique.join(" "));
  };

  const scorePossibleChatRow = (el) => {
    if (!el || !isVisible(el)) return -Infinity;

    const r = el.getBoundingClientRect();
    if (!isCandidateSidebarRect(r)) return -Infinity;

    const ownText = cleanText(getReadableText(el));
    const rectText = collectTextInsideRect(r);
    const text = cleanText(`${ownText} ${rectText}`);

    if (!text || isBadSidebarText(text)) return -Infinity;

    const tag = safeString(el.tagName).toLowerCase();
    const role = getAttributeSafe(el, "role");

    let score = 0;

    if (isPreferredRowRect(r)) score += 900;

    score += Math.min(r.width, 380) * 3;
    score += Math.min(r.height, 95) * 5;

    if (getElementHref(el)) score += 250;
    if (text.includes("[deleted]")) score += 1200;
    if (text.includes("You:")) score += 350;

    if (/yesterday|today|jun|jul|aug|sep|oct|nov|dec|jan|feb|mar|apr|may|\d{1,2}:\d{2}\s?(am|pm)?/i.test(text)) {
      score += 250;
    }

    if (tag === "button" || tag === "a") score += 130;
    if (role === "button" || role === "link" || role === "listitem" || role === "option") score += 130;

    if (r.left > 65) score -= 300;
    if (text.length > 260) score -= 40;

    return score;
  };

  const bestSidebarRowFromElement = (startEl) => {
    let el = startEl;
    let best = null;
    let bestScore = -Infinity;
    let depth = 0;

    while (el && el !== document.body && depth < 22) {
      const score = scorePossibleChatRow(el);

      if (score > bestScore) {
        best = el;
        bestScore = score;
      }

      el = getParentElementAcrossShadow(el);
      depth++;
    }

    return bestScore > -Infinity ? best : null;
  };

  const scanSidebarRowsByAllElements = () => {
    const rows = [];

    for (const node of deepNodes(document)) {
      if (!(node instanceof Element)) continue;
      if (!isVisible(node)) continue;

      const r = node.getBoundingClientRect();

      if (
        r.left < sidebarRight() &&
        r.right > 8 &&
        r.top >= 30 &&
        r.bottom <= window.innerHeight + 25
      ) {
        const best = bestSidebarRowFromElement(node);
        if (best) rows.push(best);
      }
    }

    return rows;
  };

  const scanSidebarRowsByScreenPoints = () => {
    const rows = [];
    const seen = new Set();

    const maxX = Math.min(sidebarRight() - 8, 395);

    const sampleXs = [
      8, 16, 24, 34, 44, 54, 66, 82, 100, 124, 150,
      180, 210, 240, 270, 305, 340, 375
    ].filter((x) => x > 0 && x < maxX);

    for (let y = 34; y < window.innerHeight - 4; y += 4) {
      for (const x of sampleXs) {
        const pointEl = document.elementFromPoint(x, y);
        if (!pointEl) continue;

        const row = bestSidebarRowFromElement(pointEl);
        if (!row) continue;

        const r = row.getBoundingClientRect();
        const key = `${Math.round(r.top)}:${Math.round(r.left)}:${Math.round(r.width)}:${Math.round(r.height)}`;

        if (seen.has(key)) continue;

        seen.add(key);
        rows.push(row);
      }
    }

    return rows;
  };

  const makeFallbackRowsFromVisibleText = () => {
    const rows = [];

    for (const node of deepNodes(document)) {
      if (!(node instanceof Element)) continue;
      if (!isVisible(node)) continue;

      const r = node.getBoundingClientRect();

      if (
        r.top < 32 ||
        r.bottom > window.innerHeight + 20 ||
        r.left < -5 ||
        r.left > sidebarRight() ||
        r.right < 75 ||
        r.width > sidebarRight() + 70
      ) {
        continue;
      }

      const text = cleanText(getReadableText(node));
      if (!text || isBadSidebarText(text)) continue;

      if (
        text.includes("[deleted]") ||
        text.includes("You:") ||
        /yesterday|today|jun|jul|aug|sep|oct|nov|dec|jan|feb|mar|apr|may|\d{1,2}:\d{2}\s?(am|pm)?/i.test(text)
      ) {
        const row = bestSidebarRowFromElement(node) || node;
        rows.push(row);
      }
    }

    return rows;
  };

  const groupRowsByVisualPosition = (rawRows) => {
    const sorted = [...new Set(rawRows)]
      .filter(isVisible)
      .sort((a, b) => {
        const ar = a.getBoundingClientRect();
        const br = b.getBoundingClientRect();

        if (Math.abs(ar.top - br.top) > 6) return ar.top - br.top;
        return ar.left - br.left;
      });

    const groups = [];

    for (const el of sorted) {
      const r = el.getBoundingClientRect();
      const centerY = r.top + r.height / 2;

      const existing = groups.find((group) => {
        const overlapTop = Math.max(group.top, r.top);
        const overlapBottom = Math.min(group.bottom, r.bottom);
        const overlap = Math.max(0, overlapBottom - overlapTop);
        const smallerHeight = Math.min(group.bottom - group.top, r.height);

        const overlaps =
          smallerHeight > 0 && overlap / smallerHeight > 0.28;

        const closeCenter = Math.abs(group.centerY - centerY) < 24;

        return overlaps || closeCenter;
      });

      const candidate = {
        el,
        rect: r,
        score: scorePossibleChatRow(el)
      };

      if (existing) {
        existing.items.push(candidate);
        existing.top = Math.min(existing.top, r.top);
        existing.bottom = Math.max(existing.bottom, r.bottom);
        existing.centerY = (existing.top + existing.bottom) / 2;
      } else {
        groups.push({
          top: r.top,
          bottom: r.bottom,
          centerY,
          items: [candidate]
        });
      }
    }

    return groups.map((group) => {
      return group.items.sort((a, b) => b.score - a.score)[0];
    });
  };

  const getChatCandidates = () => {
    const rows = [
      ...scanSidebarRowsByScreenPoints(),
      ...scanSidebarRowsByAllElements(),
      ...makeFallbackRowsFromVisibleText()
    ];

    const bestRows = groupRowsByVisualPosition(rows);

    const unique = [];
    const seenTopBands = new Set();

    for (const item of bestRows) {
      const el = item.el;
      const r = item.rect;

      const rowText = collectTextInsideRect(r);
      const ownText = getReadableText(el);
      const href = getElementHref(el);

      let text = cleanText(rowText || ownText || href);

      if (!text || isBadSidebarText(text)) continue;

      const topBand = Math.round(r.top / 6);
      if (seenTopBands.has(topBand)) continue;
      seenTopBands.add(topBand);

      const normalizedText = normalizeText(text);
      const geometryKey = `${Math.round(r.top)}:${Math.round(r.left)}:${Math.round(r.width)}:${Math.round(r.height)}`;
      const key = href || `${normalizedText || text}::${geometryKey}`;

      if (normalizedText.includes("[deleted]")) {
        text = `[deleted chat] ${text}`;
      }

      unique.push({
        key,
        text,
        rawText: text,
        normalizedText,
        href,
        top: Math.round(r.top),
        bottom: Math.round(r.bottom),
        left: Math.round(r.left),
        right: Math.round(r.right),
        width: Math.round(r.width),
        height: Math.round(r.height),
        clickX: Math.round(Math.min(Math.max(r.left + 54, 18), Math.min(r.right - 10, sidebarRight() - 10))),
        clickY: Math.round(r.top + r.height / 2),
        element: el
      });
    }

    unique.sort((a, b) => a.top - b.top);

    console.log(
      "Detected chat candidates:",
      unique.map((chat, i) => ({
        number: i + 1,
        text: chat.text,
        top: chat.top,
        bottom: chat.bottom,
        left: chat.left,
        right: chat.right,
        width: chat.width,
        height: chat.height,
        clickX: chat.clickX,
        clickY: chat.clickY
      }))
    );

    return unique;
  };

  const isDeleteMessageModalOpen = () =>
    normalizeText(document.body.innerText).includes("delete this message?");

  const isHideChatModalOpen = () =>
    normalizeText(document.body.innerText).includes("hide chat?");

  const clickModalAction = async ({ modalTextRegex, actionTextRegex, actionName }) => {
    const started = Date.now();

    while (Date.now() - started < CONFIRM_TIMEOUT_MS) {
      await sleep(250);

      const bodyText = normalizeText(document.body.innerText);
      const modalOpen = modalTextRegex.test(bodyText);

      if (!modalOpen && Date.now() - started > 1000) {
        return false;
      }

      const buttons = deepQueryAll("button, [role='button'], rs-button")
        .filter(isVisible)
        .map((button) => {
          const r = button.getBoundingClientRect();
          return {
            button,
            text: normalizeText(getReadableText(button)),
            r
          };
        });

      let target = buttons.find((item) => actionTextRegex.test(item.text));

      if (!target && modalOpen) {
        const modalButtons = buttons
          .filter((item) => {
            const text = item.text;
            const r = item.r;

            return (
              r.width >= 40 &&
              r.height >= 24 &&
              r.top > 160 &&
              !/^x$|^close$|^cancel$/i.test(text)
            );
          })
          .sort((a, b) => {
            if (Math.abs(b.r.right - a.r.right) > 8) return b.r.right - a.r.right;
            return b.r.bottom - a.r.bottom;
          });

        target = modalButtons[0];
      }

      if (target) {
        console.log(`Clicking modal action: ${actionName}`);

        clickElementOrClickableAncestor(target.button);

        const waitStarted = Date.now();

        while (Date.now() - waitStarted < 5000) {
          await sleep(250);

          const afterText = normalizeText(document.body.innerText);

          if (!modalTextRegex.test(afterText)) {
            return true;
          }
        }

        console.warn(`${actionName} was clicked, but the modal is still open.`);
        return false;
      }
    }

    return false;
  };

  const confirmDeleteDialog = async () => {
    return await clickModalAction({
      modalTextRegex: /delete this message\?/i,
      actionTextRegex: /^yes,\s*delete$|^yes\s*delete$|^delete$/i,
      actionName: "Yes, Delete"
    });
  };

  const clickConfirmHideIfNeeded = async () => {
    if (!isHideChatModalOpen()) {
      await sleep(400);
    }

    if (!isHideChatModalOpen()) {
      console.log("No Hide chat confirmation popup detected.");
      return true;
    }

    return await clickModalAction({
      modalTextRegex: /hide chat\?/i,
      actionTextRegex: /^yes,\s*hide$|^yes\s*hide$|^hide$/i,
      actionName: "Yes, Hide"
    });
  };

  const isOwnMessage = (eventEl) => {
    const msg = localQuery(eventEl, ".room-message[aria-label], [aria-label]");
    const aria = getAttributeSafe(msg, "aria-label");

    return new RegExp(
      "^" + escapeRegExp(USERNAME) + "\\s+said\\b",
      "i"
    ).test(aria.trim());
  };

  const getMessageSignature = (eventEl) => {
    const msg = localQuery(eventEl, ".room-message[aria-label], [aria-label]");
    const aria = getAttributeSafe(msg, "aria-label");
    const text = cleanText(getReadableText(eventEl));

    return normalizeText(aria || text).slice(0, 500);
  };

  const getOwnMessageEvents = () =>
    deepQueryAll("rs-timeline-event")
      .filter(isVisible)
      .filter(isOwnMessage);

  const ownMessageSignatureExists = (signature) => {
    if (!signature) return false;

    return getOwnMessageEvents().some((eventEl) => {
      return getMessageSignature(eventEl) === signature;
    });
  };

  const findDeleteMenuItem = () => {
    const items = deepQueryAll(
      '[role="menuitem"], rs-menu-item, rs-dropdown-item, button'
    );

    return items.find((el) => {
      const text = getReadableText(el).toLowerCase();
      return isVisible(el) && /delete|remove message/.test(text);
    });
  };

  const closeDeleteModalIfStillOpen = async () => {
    if (!isDeleteMessageModalOpen()) return;

    console.warn("Delete modal is still open. Closing it before continuing...");

    const closeButton = deepQueryAll("button, [role='button']")
      .filter(isVisible)
      .find((button) => {
        const text = normalizeText(getReadableText(button));
        return text === "cancel" || text === "x" || text === "close";
      });

    if (closeButton) {
      clickElementOrClickableAncestor(closeButton);
      await sleep(600);
    }
  };

  const waitUntilMessageReallyGone = async ({ signature, beforeCount }) => {
    const started = Date.now();

    while (Date.now() - started < GONE_CHECK_TIMEOUT_MS) {
      await sleep(GONE_CHECK_INTERVAL_MS);

      if (isDeleteMessageModalOpen()) continue;

      const currentMessages = getOwnMessageEvents();
      const currentCount = currentMessages.length;
      const signatureStillVisible = signature
        ? currentMessages.some((msg) => getMessageSignature(msg) === signature)
        : false;

      if (!signatureStillVisible || currentCount < beforeCount) {
        return true;
      }
    }

    return false;
  };

  const deleteOne = async (eventEl) => {
    await closeDeleteModalIfStillOpen();

    const signature = getMessageSignature(eventEl);
    const beforeCount = getOwnMessageEvents().length;

    eventEl.scrollIntoView({ block: "center" });

    eventEl.dispatchEvent(
      new MouseEvent("mouseenter", {
        bubbles: true,
        cancelable: true,
        view: window
      })
    );

    await sleep(SHORT_DELAY_MS);

    const directDelete = localQuery(
      eventEl,
      [
        '[aria-label="Delete"]',
        '[title="Delete"]',
        '[data-testid="delete-message"]',
        'rs-icon-button[icon="trash"]',
        'rs-icon-button[icon="delete"]',
        'button[aria-label="Delete"]'
      ].join(",")
    );

    if (directDelete && isVisible(directDelete)) {
      directDelete.click();
    } else {
      const more = localQuery(
        eventEl,
        [
          '[aria-label="More options"]',
          '[aria-label="More"]',
          '[title="More"]',
          'button[aria-haspopup="menu"]',
          '[role="button"][aria-haspopup="menu"]',
          'rs-icon-button[icon="more"]'
        ].join(",")
      );

      if (!more || !isVisible(more)) return false;

      more.click();
      await sleep(MENU_DELAY_MS);

      const deleteItem = findDeleteMenuItem();

      if (!deleteItem) return false;

      deleteItem.click();
    }

    const confirmed = await confirmDeleteDialog();

    if (!confirmed) {
      console.warn("Delete confirmation was not completed. Not counting this as deleted.");
      return false;
    }

    const gone = await waitUntilMessageReallyGone({ signature, beforeCount });

    if (!gone) {
      console.warn("Message still appears to be visible after delete confirmation. Not counting it as deleted.");
      return false;
    }

    await sleep(DELETE_DELAY_MS);

    return true;
  };

  const findChatMessageScroller = () => {
    const scrollables = deepQueryAll("*").filter((el) => {
      try {
        const r = el.getBoundingClientRect();
        const s = getComputedStyle(el);

        return (
          isVisible(el) &&
          r.left > sidebarRight() &&
          el.scrollHeight > el.clientHeight + 50 &&
          ["auto", "scroll"].includes(s.overflowY)
        );
      } catch {
        return false;
      }
    });

    return scrollables.sort((a, b) => b.scrollHeight - a.scrollHeight)[0];
  };

  const scrollCurrentChatUp = async () => {
    const scroller = findChatMessageScroller();

    if (scroller) {
      scroller.scrollTop = 0;
    } else {
      window.scrollTo(0, 0);
    }

    await sleep(SCROLL_DELAY_MS);
  };

  const deleteCurrentChatMessages = async () => {
    let deleted = 0;
    let failed = 0;
    let retryRounds = 0;
    let noProgressRounds = 0;
    let lastRemainingSignatures = [];

    while (retryRounds < MAX_RETRY_ROUNDS_PER_CHAT) {
      retryRounds++;

      console.log(`Retry round ${retryRounds}/${MAX_RETRY_ROUNDS_PER_CHAT} for this chat...`);

      let roundDeleted = 0;
      let roundFailed = 0;

      let ownMessages = getOwnMessageEvents();

      if (ownMessages.length === 0) {
        await scrollCurrentChatUp();
        ownMessages = getOwnMessageEvents();
      }

      if (ownMessages.length === 0) {
        console.log("No visible own messages left in this chat.");
        break;
      }

      const beforeRoundSignatures = ownMessages.map(getMessageSignature);

      console.log(`Found ${ownMessages.length} visible own message(s) to try deleting.`);

      for (const msg of ownMessages) {
        const ok = await deleteOne(msg);

        if (ok) {
          deleted++;
          roundDeleted++;
          console.log(`Deleted ${deleted} total message(s) in this chat...`);
        } else {
          failed++;
          roundFailed++;
          console.log("Delete attempt failed or message remained visible.");
        }

        await closeDeleteModalIfStillOpen();
      }

      await closeDeleteModalIfStillOpen();
      await scrollCurrentChatUp();

      const remainingEvents = getOwnMessageEvents();
      const remaining = remainingEvents.length;
      const remainingSignatures = remainingEvents.map(getMessageSignature);

      console.log(
        `Round ${retryRounds} done. Deleted this round: ${roundDeleted}. Failed this round: ${roundFailed}. Remaining visible own messages: ${remaining}.`
      );

      if (remaining === 0) {
        console.log("All visible own messages are gone in this chat.");
        break;
      }

      const sameAsLast =
        lastRemainingSignatures.length === remainingSignatures.length &&
        lastRemainingSignatures.every((sig, i) => sig === remainingSignatures[i]);

      const sameAsBefore =
        beforeRoundSignatures.length === remainingSignatures.length &&
        beforeRoundSignatures.every((sig, i) => sig === remainingSignatures[i]);

      if (roundDeleted === 0 || sameAsLast || sameAsBefore) {
        noProgressRounds++;
      } else {
        noProgressRounds = 0;
      }

      lastRemainingSignatures = remainingSignatures;

      if (noProgressRounds >= MAX_NO_PROGRESS_ROUNDS) {
        console.warn("Stopping this chat because repeated rounds made no real progress.");
        break;
      }

      await sleep(700);
    }

    return { deleted, failed };
  };

  const isWelcomeScreen = () => {
    const bodyText = normalizeText(document.body.innerText);
    return bodyText.includes("welcome to chat") && bodyText.includes("start a direct or group chat");
  };

  const findChatSettingsGear = () => {
    const labeledGear = deepQueryAll(
      [
        'button[aria-label*="settings" i]',
        '[role="button"][aria-label*="settings" i]',
        'button[title*="settings" i]',
        '[title*="settings" i]',
        'rs-icon-button[icon="settings"]',
        'rs-icon-button[name="settings"]',
        'button[aria-label*="chat settings" i]',
        '[role="button"][aria-label*="chat settings" i]'
      ].join(",")
    )
      .filter(isVisible)
      .sort((a, b) => {
        const ar = a.getBoundingClientRect();
        const br = b.getBoundingClientRect();
        return br.left - ar.left;
      })[0];

    if (labeledGear) return labeledGear;

    const topRightButtons = deepQueryAll(
      [
        'button',
        '[role="button"]',
        'rs-icon-button'
      ].join(",")
    )
      .filter(isVisible)
      .filter((el) => {
        const r = el.getBoundingClientRect();

        return (
          r.top >= 0 &&
          r.top < 85 &&
          r.left > sidebarRight() &&
          r.right > window.innerWidth - 180 &&
          r.width >= 14 &&
          r.height >= 14
        );
      })
      .sort((a, b) => {
        const ar = a.getBoundingClientRect();
        const br = b.getBoundingClientRect();

        return br.right - ar.right;
      });

    return topRightButtons[0] || null;
  };

  const waitForChatOpen = async () => {
    const started = Date.now();

    while (Date.now() - started < 5000) {
      await sleep(250);

      if (!isWelcomeScreen() && findChatSettingsGear()) {
        return true;
      }

      const bodyText = normalizeText(document.body.innerText);

      if (!isWelcomeScreen() && bodyText.includes("message")) {
        return true;
      }
    }

    return false;
  };

  const tryClickBackButton = async () => {
    const possibleBackButtons = deepQueryAll(
      [
        'button[aria-label*="back" i]',
        '[role="button"][aria-label*="back" i]',
        'button[title*="back" i]',
        '[aria-label="Back"]',
        '[title="Back"]',
        'rs-icon-button[icon="back"]',
        'rs-icon-button[name="back"]'
      ].join(",")
    ).filter(isVisible);

    if (possibleBackButtons.length === 0) return false;

    possibleBackButtons[0].click();
    await sleep(SIDEBAR_RECOVERY_DELAY_MS);

    return getChatCandidates().length > 0;
  };

  const tryHistoryBack = async () => {
    try {
      history.back();
      await sleep(SIDEBAR_RECOVERY_DELAY_MS);
      return getChatCandidates().length > 0;
    } catch {
      return false;
    }
  };

  const returnToChatListIfNeeded = async () => {
    let chats = getChatCandidates();

    if (chats.length > 0) return true;

    console.warn("Chat list is not visible. Trying to return to the chat list...");

    const clickedBack = await tryClickBackButton();

    if (clickedBack) {
      console.log("Returned to chat list using a visible Back button.");
      return true;
    }

    const historyWorked = await tryHistoryBack();

    if (historyWorked) {
      console.log("Returned to chat list using browser history.");
      return true;
    }

    console.warn("Still cannot see the chat list. Widen the Reddit window or undock DevTools, then run again.");
    return false;
  };

  const findChatElementFromSavedChat = async (savedChat) => {
    await returnToChatListIfNeeded();

    const candidates = getChatCandidates();

    let match = null;

    if (savedChat.href) {
      match = candidates.find((chat) => chat.href === savedChat.href);
    }

    if (!match && savedChat.key) {
      match = candidates.find((chat) => chat.key === savedChat.key);
    }

    if (!match && savedChat.rawText) {
      const savedRaw = normalizeText(savedChat.rawText);

      match = candidates.find((chat) => {
        const currentRaw = normalizeText(chat.rawText);

        return (
          currentRaw === savedRaw ||
          currentRaw.includes(savedRaw) ||
          savedRaw.includes(currentRaw)
        );
      });
    }

    if (!match && savedChat.top != null) {
      match = candidates
        .map((chat) => ({
          chat,
          distance: Math.abs(chat.top - savedChat.top)
        }))
        .filter((x) => x.distance < 26)
        .sort((a, b) => a.distance - b.distance)[0]?.chat || null;
    }

    if (!match && savedChat.normalizedText?.includes("[deleted]")) {
      match = candidates.find((chat) => {
        return chat.normalizedText.includes("[deleted]") || chat.text.toLowerCase().includes("[deleted]");
      });
    }

    if (match && match.element && isVisible(match.element)) {
      return match.element;
    }

    return null;
  };

  const clickChat = async (savedChat) => {
    console.log(`Opening selected chat: ${savedChat.text || savedChat.rawText || savedChat.key}`);

    for (let attempt = 1; attempt <= 3; attempt++) {
      const chatEl = await findChatElementFromSavedChat(savedChat);

      if (chatEl) {
        chatEl.scrollIntoView({ block: "center" });
        await sleep(250);
        clickRowByCoordinates(chatEl, savedChat);
      } else if (savedChat.clickX != null && savedChat.clickY != null) {
        console.warn(`Could not rematch row on attempt ${attempt}. Trying saved coordinates...`);
        clickAt(savedChat.clickX, savedChat.clickY);
      } else {
        console.warn(`Could not find chat row on attempt ${attempt}.`);
        return false;
      }

      const opened = await waitForChatOpen();

      if (opened) {
        console.log("Chat opened.");
        return true;
      }

      console.warn(`Chat did not open on attempt ${attempt}. Retrying...`);
      await sleep(650);
    }

    console.warn(`Could not open chat after retries: ${savedChat.text || savedChat.rawText || savedChat.key}`);
    return false;
  };

  const openChatSettings = async () => {
    console.log("Trying to open chat settings...");

    await closeDeleteModalIfStillOpen();

    if (isWelcomeScreen()) {
      console.warn("Cannot open settings because no chat is currently open.");
      return false;
    }

    const alreadySettings = findVisibleByText(
      ['h1', 'h2', 'h3', 'div', 'span'].join(","),
      /^chat settings$/i
    );

    if (alreadySettings) {
      console.log("Already on Chat settings screen.");
      return true;
    }

    const gear = findChatSettingsGear();

    if (gear) {
      clickElementOrClickableAncestor(gear);
      await sleep(800);
      return true;
    }

    console.warn("Could not find the top-right chat settings gear.");
    return false;
  };

  const findHideChatButton = () => {
    const candidates = deepQueryAll(
      [
        '[role="button"]',
        'button',
        'rs-button',
        'rs-menu-item',
        'rs-dropdown-item',
        'div',
        'span'
      ].join(",")
    ).filter(isVisible);

    return candidates.find((el) => {
      const text = cleanText(getReadableText(el));
      return /^hide chat$/i.test(text) || /^hide$/i.test(text);
    });
  };

  const hideCurrentChat = async () => {
    console.log("Trying to hide current chat via gear → Hide chat → Yes, Hide...");

    await closeDeleteModalIfStillOpen();

    if (isWelcomeScreen()) {
      console.warn("Skipping hide because the chat did not open.");
      return false;
    }

    const openedSettings = await openChatSettings();

    if (!openedSettings) {
      console.warn("Could not open chat settings.");
      return false;
    }

    await sleep(700);

    const hideButton = findHideChatButton();

    if (!hideButton) {
      console.warn("Could not find Hide chat on the settings screen.");
      return false;
    }

    console.log("Clicking Hide chat...");
    clickElementOrClickableAncestor(hideButton);

    const confirmed = await clickConfirmHideIfNeeded();

    if (!confirmed) {
      console.warn("Hide chat confirmation was not completed.");
      return false;
    }

    await sleep(1200);

    console.log("Hide chat confirmed.");
    return true;
  };

  const showChatPicker = async () => {
    const chats = getChatCandidates();

    if (chats.length === 0) {
      alert(
        "No chats found. Make sure you are on a Reddit chat page and the left chat sidebar is visible. Try widening the window, undocking DevTools, or scrolling the sidebar, then run the script again."
      );
      return [];
    }

    return new Promise((resolve) => {
      const old = document.getElementById("reddit-chat-delete-picker");
      if (old) old.remove();

      const overlay = document.createElement("div");
      overlay.id = "reddit-chat-delete-picker";

      overlay.style.position = "fixed";
      overlay.style.inset = "0";
      overlay.style.background = "rgba(0, 0, 0, 0.65)";
      overlay.style.zIndex = "2147483647";
      overlay.style.display = "flex";
      overlay.style.alignItems = "center";
      overlay.style.justifyContent = "center";
      overlay.style.fontFamily = "Arial, sans-serif";

      const panel = document.createElement("div");
      panel.style.width = "min(900px, 92vw)";
      panel.style.maxHeight = "82vh";
      panel.style.overflow = "auto";
      panel.style.background = "#fff";
      panel.style.color = "#111";
      panel.style.borderRadius = "12px";
      panel.style.padding = "18px";
      panel.style.boxShadow = "0 10px 40px rgba(0,0,0,0.35)";

      panel.innerHTML = `
        <h2 style="margin:0 0 8px;font-size:20px;">Select Reddit chats to clean</h2>
        <p style="margin:0 0 12px;font-size:14px;line-height:1.4;">
          Found ${chats.length} visible chat item(s). Select the chats you want to process.
          This will delete only messages sent by <b>${USERNAME}</b>.
        </p>

        <p style="margin:0 0 12px;font-size:13px;line-height:1.4;color:#555;">
          This version only counts a message as deleted after the confirmation popup closes and
          the same message is no longer visible.
        </p>

        <p style="margin:0 0 12px;font-size:13px;line-height:1.4;color:#555;">
          Hide after cleaning: <b>${HIDE_AFTER_DELETE ? "ON" : "OFF"}</b>
        </p>

        <div style="display:flex;gap:8px;margin-bottom:12px;">
          <button id="rcc-select-all" style="padding:8px 10px;cursor:pointer;">Select all</button>
          <button id="rcc-select-none" style="padding:8px 10px;cursor:pointer;">Select none</button>
        </div>

        <div id="rcc-list" style="border:1px solid #ddd;border-radius:8px;overflow:hidden;"></div>

        <div style="display:flex;justify-content:flex-end;gap:10px;margin-top:14px;">
          <button id="rcc-cancel" style="padding:10px 14px;cursor:pointer;">Cancel</button>
          <button id="rcc-run" style="padding:10px 14px;cursor:pointer;background:#ff4500;color:#fff;border:0;border-radius:6px;">
            Delete/hide selected chats
          </button>
        </div>
      `;

      const list = panel.querySelector("#rcc-list");

      chats.forEach((chat, index) => {
        const row = document.createElement("label");
        row.style.display = "flex";
        row.style.alignItems = "flex-start";
        row.style.gap = "10px";
        row.style.padding = "10px";
        row.style.borderBottom = "1px solid #eee";
        row.style.cursor = "pointer";
        row.style.fontSize = "14px";

        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.checked = false;
        checkbox.dataset.index = String(index);
        checkbox.style.marginTop = "3px";

        const label = document.createElement("span");
        label.textContent = `${index + 1}. ${chat.text}`;

        row.appendChild(checkbox);
        row.appendChild(label);
        list.appendChild(row);
      });

      overlay.appendChild(panel);
      document.body.appendChild(overlay);

      const closeWith = (selected) => {
        overlay.remove();
        resolve(selected);
      };

      panel.querySelector("#rcc-select-all").onclick = () => {
        panel.querySelectorAll('input[type="checkbox"]').forEach((box) => {
          box.checked = true;
        });
      };

      panel.querySelector("#rcc-select-none").onclick = () => {
        panel.querySelectorAll('input[type="checkbox"]').forEach((box) => {
          box.checked = false;
        });
      };

      panel.querySelector("#rcc-cancel").onclick = () => {
        closeWith([]);
      };

      panel.querySelector("#rcc-run").onclick = () => {
        const selectedIndexes = [...panel.querySelectorAll('input[type="checkbox"]')]
          .filter((box) => box.checked)
          .map((box) => Number(box.dataset.index));

        const selected = selectedIndexes.map((i) => ({
          key: chats[i].key,
          text: chats[i].text,
          rawText: chats[i].rawText,
          normalizedText: chats[i].normalizedText,
          href: chats[i].href,
          top: chats[i].top,
          bottom: chats[i].bottom,
          clickX: chats[i].clickX,
          clickY: chats[i].clickY
        }));

        closeWith(selected);
      };
    });
  };

  console.log("Scanning visible chats...");
  console.log("Current URL:", location.href);
  console.log("Tip: this version verifies real delete progress and closes stuck delete popups.");
  console.log("Tip: scroll the left chat sidebar before running if you want more chats to appear.");
  console.log(`Retry settings: ${MAX_RETRY_ROUNDS_PER_CHAT} retry rounds per chat, stop after ${MAX_NO_PROGRESS_ROUNDS} no-progress rounds.`);
  console.log(`Hide after delete: ${HIDE_AFTER_DELETE ? "ON" : "OFF"}`);

  const selectedChatsRaw = await showChatPicker();

  if (!selectedChatsRaw.length) {
    console.log("No chats selected. Cancelled.");
    return;
  }

  const selectedChats = HIDE_AFTER_DELETE
    ? [...selectedChatsRaw].sort((a, b) => (b.top ?? 0) - (a.top ?? 0))
    : selectedChatsRaw;

  console.log(`Selected ${selectedChats.length} chat(s).`);
  console.log(`Speed: up to ${MAX_DELETES_PER_MINUTE} deletes per minute.`);

  let totalDeleted = 0;
  let totalFailed = 0;
  let totalHidden = 0;
  let totalHideFailed = 0;
  let totalOpenFailed = 0;
  let processedChats = 0;

  for (const chat of selectedChats) {
    const opened = await clickChat(chat);

    if (!opened) {
      totalOpenFailed++;
      console.warn(`Skipping because chat did not open: ${chat.text}`);
      continue;
    }

    processedChats++;

    console.log(`Cleaning selected chat ${processedChats}/${selectedChats.length}: ${chat.text}`);

    const result = await deleteCurrentChatMessages();

    totalDeleted += result.deleted;
    totalFailed += result.failed;

    console.log(
      `Finished chat: ${chat.text}. Deleted: ${result.deleted}. Failed/skipped attempts: ${result.failed}.`
    );

    if (HIDE_AFTER_DELETE) {
      const hidden = await hideCurrentChat();

      if (hidden) {
        totalHidden++;
        console.log(`Hidden chat: ${chat.text}`);
      } else {
        totalHideFailed++;
        console.warn(`Could not hide chat: ${chat.text}`);
      }

      await sleep(1000);
    }

    await returnToChatListIfNeeded();
  }

  console.log("Selected-chat cleanup finished.");
  console.log(`Chats processed: ${processedChats}`);
  console.log(`Chats that failed to open: ${totalOpenFailed}`);
  console.log(`Total deleted: ${totalDeleted}`);
  console.log(`Total skipped/failed delete attempts: ${totalFailed}`);
  console.log(`Total hidden: ${totalHidden}`);
  console.log(`Total hide failures: ${totalHideFailed}`);

  if (totalFailed > 0) {
    console.log("If messages failed, Reddit may not be confirming deletion. Try slower speed like 40 or 50.");
  }

  if (totalOpenFailed > 0) {
    console.log("If chats fail to open, select fewer at a time or run again after scrolling that section into view.");
  }

  if (totalHideFailed > 0) {
    console.log("If hiding failed, the chat may not have opened or Reddit's gear/settings layout changed.");
  }
})();
"""

if generate:
    if not username.strip():
        st.error("Enter your Reddit username first.")
    else:
        script = (
            JS_TEMPLATE
            .replace("__USERNAME_JSON__", json.dumps(username.strip()))
            .replace("__MAX_DELETES__", str(int(speed)))
            .replace("__MAX_RETRY_ROUNDS__", str(int(retry_rounds)))
            .replace("__MAX_NO_PROGRESS_ROUNDS__", str(int(no_progress_rounds)))
            .replace("__HIDE_AFTER_DELETE__", "true" if hide_after_delete else "false")
            .strip()
        )

        st.success("Script generated.")

        st.markdown(
            """
            **How to use it:**

            1. Open Reddit Chat.
            2. Make sure the left chat sidebar is visible.
            3. Scroll the left sidebar until the chats you want are visible.
            4. Open DevTools.
            5. Go to the **Console** tab.
            6. Paste the generated script.
            7. Select the chats in the popup.
            8. Click **Delete/hide selected chats**.

            This version should stop the fake repeated “Deleted 1” loop. It only counts a delete after the popup closes and the same message is gone.
            """
        )

        st.code(script, language="javascript")

        st.download_button(
            label="Download script as .js",
            data=script,
            file_name="reddit_selected_chat_delete_hide_real_progress_fix.js",
            mime="text/javascript",
            use_container_width=True
        )
else:
    st.info("Enter your Reddit username and click the button to generate the script.")
