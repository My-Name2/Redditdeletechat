import json
import streamlit as st

st.set_page_config(
    page_title="Reddit Chat Woodchipper Auto Delete/Hide",
    page_icon="🧹",
    layout="centered"
)

st.title("Reddit Chat Woodchipper Auto Delete/Hide")
st.caption("Generate a script that waits for each open Reddit chat, then paste it into Reddit's DevTools Console.")

st.warning(
    "Hosted Streamlit apps cannot directly control reddit.com. "
    "This app generates JavaScript that you paste into the Console on an already-open Reddit chat."
)

st.markdown(
    """
    **Use this for one chat at a time.**

    1. Open the exact Reddit chat you want to clean.
    2. Make sure the chat is open, not the **Welcome to chat** screen.
    3. Generate the script below.
    4. Paste it into DevTools → Console on Reddit.
    5. It deletes only your sent chat messages.
    6. It then automatically hides that same chat and waits for you to open another one.
    """
)

username = st.text_input("Reddit username", placeholder="without u/")

speed = st.slider(
    "Max deletes per minute",
    min_value=20,
    max_value=120,
    value=45,
    step=5,
    help="Slower is safer. Try 35–60 if Reddit popups lag."
)

max_total_attempts = st.slider(
    "Max total delete attempts",
    min_value=25,
    max_value=1000,
    value=500,
    step=25
)

max_no_progress_attempts = st.slider(
    "Stop after this many failed/no-progress delete attempts",
    min_value=1,
    max_value=20,
    value=5,
    step=1,
    help="Stops if Reddit keeps showing the same message or popups do not confirm."
)

max_empty_scroll_rounds = st.slider(
    "Stop after this many empty upward scroll rounds",
    min_value=2,
    max_value=20,
    value=8,
    step=1,
    help="The script scrolls upward to look for older messages. This controls when it gives up."
)

max_chats_to_process = st.slider(
    "Woodchipper mode: max chats to process before stopping",
    min_value=1,
    max_value=200,
    value=25,
    step=1,
    help="The script cleans/hides the currently open chat, then waits for you to open the next one."
)

wait_for_next_chat_seconds = st.slider(
    "Stop waiting for next chat after this many seconds",
    min_value=30,
    max_value=3600,
    value=900,
    step=30,
    help="After a chat is hidden, the script waits this long for you to open another chat."
)

hide_after_delete = st.checkbox(
    "Automatically hide each open chat after delete pass",
    value=True
)

generate = st.button(
    "Generate woodchipper script",
    type="primary",
    use_container_width=True
)

JS_TEMPLATE = r"""
// Reddit SINGLE Open-Chat Own-Message Delete + Automatic Hide
// Use this simple version for ONE chat only.
// 1. Open the Reddit chat you want to clean.
// 2. Paste this whole script into DevTools Console.
// 3. It deletes only YOUR sent chat messages that Reddit allows deleting.
// 4. Then it automatically hides the currently open chat through Gear -> Hide chat -> Yes, Hide.
// It does NOT delete Reddit comments.
// It does NOT delete Reddit posts.
// Stop anytime by typing this in the console:
// window.__redditSingleChatCleanupStop = true

(async () => {
  const USERNAME = __USERNAME_JSON__;
  const MAX_DELETES_PER_MINUTE = __MAX_DELETES__;
  const DELETE_DELAY_MS = Math.ceil(60000 / MAX_DELETES_PER_MINUTE);

  const MAX_TOTAL_DELETE_ATTEMPTS = __MAX_TOTAL_DELETE_ATTEMPTS__;
  const MAX_NO_PROGRESS_ATTEMPTS = __MAX_NO_PROGRESS_ATTEMPTS__;
  const MAX_EMPTY_SCROLL_ROUNDS = __MAX_EMPTY_SCROLL_ROUNDS__;
  const HIDE_AFTER_DELETE = __HIDE_AFTER_DELETE__;
  const MAX_CHATS_TO_PROCESS = __MAX_CHATS_TO_PROCESS__;
  const WAIT_FOR_NEXT_CHAT_SECONDS = __WAIT_FOR_NEXT_CHAT_SECONDS__;

  const SHORT_DELAY_MS = 150;
  const MENU_DELAY_MS = 250;
  const SCROLL_DELAY_MS = 850;
  const CONFIRM_TIMEOUT_MS = 10000;
  const GONE_TIMEOUT_MS = 5500;
  const GONE_INTERVAL_MS = 250;
  const HIDE_DELAY_MS = 1300;

  window.__redditSingleChatCleanupStop = false;

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

  const cleanText = (text) =>
    safeString(text).replace(/\s+/g, " ").trim();

  const normalizeText = (text) =>
    cleanText(text).toLowerCase();

  const escapeRegExp = (value) =>
    safeString(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

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

  const sidebarRight = () => {
    return Math.min(440, Math.max(285, window.innerWidth * 0.42));
  };

  const findVisibleByText = (selector, regex) => {
    return deepQueryAll(selector)
      .filter(isVisible)
      .find((el) => regex.test(cleanText(getReadableText(el))));
  };

  const getVisiblePageTextDeep = () => {
    try {
      const deepText = deepQueryAll(
        [
          "dialog",
          "[role='dialog']",
          "div",
          "section",
          "article",
          "h1",
          "h2",
          "h3",
          "p",
          "span",
          "button",
          "[role='button']",
          "rs-button"
        ].join(",")
      )
        .filter(isVisible)
        .map(getReadableText)
        .filter(Boolean)
        .join(" ");

      return normalizeText(`${document.body.innerText || ""} ${deepText}`);
    } catch {
      return normalizeText(document.body.innerText || "");
    }
  };

  const isDeleteMessageModalOpen = () => {
    const text = getVisiblePageTextDeep();
    return (
      text.includes("delete this message?") ||
      text.includes("it will be removed for everyone in this chat")
    );
  };

  const isHideChatModalOpen = () => {
    const text = getVisiblePageTextDeep();
    return (
      text.includes("hide chat?") ||
      text.includes("this conversation will be hidden")
    );
  };

  const getVisibleButtons = () => {
    return deepQueryAll("button, [role='button'], rs-button")
      .filter(isVisible)
      .map((button) => {
        const r = button.getBoundingClientRect();

        let background = "";

        try {
          background = getComputedStyle(button).backgroundColor || "";
        } catch {}

        return {
          button,
          text: normalizeText(getReadableText(button)),
          r,
          background
        };
      });
  };

  const clickModalAction = async ({ modalName, modalOpenCheck, exactActionRegex, looseActionRegex }) => {
    console.log(`Waiting for ${modalName} popup...`);

    const started = Date.now();

    while (Date.now() - started < CONFIRM_TIMEOUT_MS) {
      await sleep(250);

      const modalOpen = modalOpenCheck();
      const buttons = getVisibleButtons();

      // Important:
      // Prefer exact "Yes, Delete" / "Yes, Hide" buttons.
      // Do NOT click a plain "delete" menu item while the modal is open.
      let target = buttons.find((item) => exactActionRegex.test(item.text));

      if (!target && modalOpen) {
        const modalButtons = buttons
          .filter((item) => {
            const text = item.text;
            const r = item.r;

            return (
              r.width >= 40 &&
              r.height >= 24 &&
              r.top > 120 &&
              r.bottom < window.innerHeight &&
              !/^x$|^close$|^cancel$/i.test(text)
            );
          })
          .sort((a, b) => {
            const aLoose = looseActionRegex.test(a.text) ? 5000 : 0;
            const bLoose = looseActionRegex.test(b.text) ? 5000 : 0;

            const aDark = /rgb\(0,\s*0,\s*0\)|rgba\(0,\s*0,\s*0/i.test(a.background) ? 1200 : 0;
            const bDark = /rgb\(0,\s*0,\s*0\)|rgba\(0,\s*0,\s*0/i.test(b.background) ? 1200 : 0;

            const aScore = aLoose + aDark + a.r.right + a.r.bottom * 0.1;
            const bScore = bLoose + bDark + b.r.right + b.r.bottom * 0.1;

            return bScore - aScore;
          });

        target = modalButtons[0];
      }

      if (target) {
        console.log(`Clicking ${modalName} action: ${target.text || "[button]"}`);
        clickElementOrClickableAncestor(target.button);

        const closeStarted = Date.now();

        while (Date.now() - closeStarted < 7000) {
          await sleep(250);

          if (!modalOpenCheck()) {
            await sleep(400);
            console.log(`${modalName} popup closed.`);
            return true;
          }
        }

        console.warn(`${modalName} action was clicked, but the popup stayed open. Stopping before doing anything else.`);
        return false;
      }

      if (!modalOpen && Date.now() - started > 1800) {
        console.warn(`${modalName} popup was not detected.`);
        return false;
      }
    }

    console.warn(`${modalName} popup timed out.`);
    return false;
  };

  const confirmDeleteDialog = async () => {
    return await clickModalAction({
      modalName: "Delete message",
      modalOpenCheck: isDeleteMessageModalOpen,
      exactActionRegex: /^yes,\s*delete$|^yes\s*delete$/i,
      looseActionRegex: /yes|delete/i
    });
  };

  const confirmHideDialog = async () => {
    return await clickModalAction({
      modalName: "Hide chat",
      modalOpenCheck: isHideChatModalOpen,
      exactActionRegex: /^yes,\s*hide$|^yes\s*hide$/i,
      looseActionRegex: /yes|hide/i
    });
  };

  const closeDeleteModalIfStillOpen = async () => {
    if (!isDeleteMessageModalOpen()) return;

    console.warn("Delete popup is still open. Closing it before continuing...");

    const closeButton = getVisibleButtons()
      .find((item) => {
        const text = item.text;
        return text === "cancel" || text === "x" || text === "close";
      })?.button;

    if (closeButton) {
      clickElementOrClickableAncestor(closeButton);
      await sleep(700);
    }
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

    return normalizeText(aria || text).slice(0, 700);
  };

  const getOwnMessageEvents = () => {
    return deepQueryAll("rs-timeline-event")
      .filter(isVisible)
      .filter(isOwnMessage);
  };

  const findDeleteMenuItem = () => {
    const items = deepQueryAll(
      '[role="menuitem"], rs-menu-item, rs-dropdown-item, button'
    );

    return items.find((el) => {
      const text = normalizeText(getReadableText(el));
      return isVisible(el) && /delete|remove message/.test(text);
    });
  };

  const waitUntilMessageReallyGone = async ({ signature, beforeCount }) => {
    const started = Date.now();

    while (Date.now() - started < GONE_TIMEOUT_MS) {
      await sleep(GONE_INTERVAL_MS);

      if (isDeleteMessageModalOpen()) {
        continue;
      }

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

  const deleteOneMessage = async (eventEl) => {
    await closeDeleteModalIfStillOpen();

    if (!eventEl || !isVisible(eventEl)) return false;

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

      if (!more || !isVisible(more)) {
        console.warn("Could not find message More/Delete control.");
        return false;
      }

      more.click();
      await sleep(MENU_DELAY_MS);

      const deleteItem = findDeleteMenuItem();

      if (!deleteItem) {
        console.warn("Could not find Delete menu item.");
        return false;
      }

      deleteItem.click();
    }

    const confirmed = await confirmDeleteDialog();

    if (!confirmed) {
      console.warn("Delete was not confirmed. Not counting this message as deleted.");
      return false;
    }

    const gone = await waitUntilMessageReallyGone({ signature, beforeCount });

    if (!gone) {
      console.warn("Message still appears visible after confirmed delete. Not counting as deleted.");
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
      const before = scroller.scrollTop;
      scroller.scrollTop = Math.max(0, scroller.scrollTop - Math.max(500, scroller.clientHeight * 0.85));
      await sleep(SCROLL_DELAY_MS);
      return Math.abs(scroller.scrollTop - before) > 5;
    }

    const before = window.scrollY;
    window.scrollTo(0, Math.max(0, window.scrollY - 700));
    await sleep(SCROLL_DELAY_MS);
    return Math.abs(window.scrollY - before) > 5;
  };

  const deleteOpenChatMessages = async () => {
    let deleted = 0;
    let failed = 0;
    let totalAttempts = 0;
    let noProgressAttempts = 0;
    let emptyScrollRounds = 0;

    console.log("Starting single-chat delete pass...");
    console.log(`Speed: up to ${MAX_DELETES_PER_MINUTE} deletes per minute.`);
    console.log("Stop anytime with: window.__redditSingleChatCleanupStop = true");

    while (
      !window.__redditSingleChatCleanupStop &&
      totalAttempts < MAX_TOTAL_DELETE_ATTEMPTS
    ) {
      await closeDeleteModalIfStillOpen();

      const ownMessages = getOwnMessageEvents();

      if (ownMessages.length === 0) {
        const moved = await scrollCurrentChatUp();

        const afterScrollMessages = getOwnMessageEvents();

        if (afterScrollMessages.length === 0) {
          emptyScrollRounds++;

          console.log(`No visible own messages here. Empty scroll round ${emptyScrollRounds}/${MAX_EMPTY_SCROLL_ROUNDS}.`);

          if (!moved || emptyScrollRounds >= MAX_EMPTY_SCROLL_ROUNDS) {
            break;
          }

          continue;
        }

        emptyScrollRounds = 0;
      } else {
        emptyScrollRounds = 0;
      }

      const refreshedMessages = getOwnMessageEvents();

      if (refreshedMessages.length === 0) continue;

      // Delete one message at a time, then re-scan.
      const targetMessage = refreshedMessages[refreshedMessages.length - 1];

      totalAttempts++;

      console.log(`Deleting visible own message attempt ${totalAttempts}...`);

      const ok = await deleteOneMessage(targetMessage);

      if (ok) {
        deleted++;
        noProgressAttempts = 0;
        console.log(`Deleted ${deleted} message(s) in this chat.`);
      } else {
        failed++;
        noProgressAttempts++;
        console.warn(`Delete attempt failed. No-progress count ${noProgressAttempts}/${MAX_NO_PROGRESS_ATTEMPTS}.`);

        if (noProgressAttempts >= MAX_NO_PROGRESS_ATTEMPTS) {
          console.warn("Stopping delete pass because repeated attempts made no progress.");
          break;
        }

        await sleep(700);
      }
    }

    await closeDeleteModalIfStillOpen();

    return { deleted, failed, totalAttempts };
  };

  const isWelcomeScreen = () => {
    const bodyText = getVisiblePageTextDeep();
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
          r.top < 90 &&
          r.left > sidebarRight() &&
          r.right > window.innerWidth - 190 &&
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

  const openChatSettings = async () => {
    await closeDeleteModalIfStillOpen();

    if (isWelcomeScreen()) {
      console.warn("Cannot open settings because no chat appears to be open.");
      return false;
    }

    const alreadySettings = findVisibleByText(
      "h1, h2, h3, div, span",
      /^chat settings$/i
    );

    if (alreadySettings) {
      console.log("Already on Chat settings screen.");
      return true;
    }

    const gear = findChatSettingsGear();

    if (!gear) {
      console.warn("Could not find top-right chat settings gear.");
      return false;
    }

    console.log("Opening chat settings...");
    clickElementOrClickableAncestor(gear);

    const started = Date.now();

    while (Date.now() - started < 5000) {
      await sleep(250);

      const settingsHeader = findVisibleByText(
        "h1, h2, h3, div, span",
        /^chat settings$/i
      );

      if (settingsHeader) {
        console.log("Chat settings opened.");
        return true;
      }
    }

    console.warn("Clicked gear, but Chat settings did not appear.");
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
    await closeDeleteModalIfStillOpen();

    if (isWelcomeScreen()) {
      console.warn("Skipping hide because no chat appears to be open.");
      return false;
    }

    const settingsOpened = await openChatSettings();

    if (!settingsOpened) return false;

    await sleep(500);

    const hideButton = findHideChatButton();

    if (!hideButton) {
      console.warn("Could not find Hide chat button on settings screen.");
      return false;
    }

    console.log("Clicking Hide chat...");
    clickElementOrClickableAncestor(hideButton);

    const confirmed = await confirmHideDialog();

    if (!confirmed) {
      console.warn("Hide was not confirmed.");
      return false;
    }

    await sleep(HIDE_DELAY_MS);

    console.log("Hide confirmed.");
    return true;
  };

  const getCurrentChatHeaderText = () => {
    const candidates = deepQueryAll("h1, h2, h3, a, span, div")
      .filter(isVisible)
      .map((el) => {
        const r = el.getBoundingClientRect();
        const text = cleanText(getReadableText(el));

        return {
          el,
          r,
          text
        };
      })
      .filter((item) => {
        const text = item.text;
        const r = item.r;

        if (!text || text.length < 2 || text.length > 120) return false;

        const bad =
          /welcome|start new chat|message$|manage notifications|persistent messaging|pin chat|hide chat|chat settings|reddit|chats|threads/i.test(text);

        return (
          !bad &&
          r.top >= 0 &&
          r.top < 120 &&
          r.left > sidebarRight() - 20 &&
          r.right < window.innerWidth + 20
        );
      })
      .sort((a, b) => {
        const aScore =
          (a.text.startsWith("u/") ? 1000 : 0) +
          (a.r.top < 70 ? 300 : 0) -
          a.text.length;

        const bScore =
          (b.text.startsWith("u/") ? 1000 : 0) +
          (b.r.top < 70 ? 300 : 0) -
          b.text.length;

        return bScore - aScore;
      });

    return candidates[0]?.text || "";
  };

  const isChatOpenForCleanup = () => {
    if (isWelcomeScreen()) return false;
    if (isDeleteMessageModalOpen()) return true;
    if (isHideChatModalOpen()) return true;

    const hasMessageInput = deepQueryAll(
      "textarea, input, [contenteditable='true'], [role='textbox']"
    )
      .filter(isVisible)
      .some((el) => {
        const r = el.getBoundingClientRect();
        return r.left > sidebarRight() - 30 && r.top > 120;
      });

    if (hasMessageInput) return true;
    if (findChatSettingsGear()) return true;
    if (getOwnMessageEvents().length > 0) return true;
    if (getCurrentChatHeaderText()) return true;

    return false;
  };

  const getCurrentChatIdentity = () => {
    if (!isChatOpenForCleanup()) return "";

    const header = getCurrentChatHeaderText();
    const visibleOwnMessages = getOwnMessageEvents()
      .slice(-2)
      .map(getMessageSignature)
      .join(" || ");

    return normalizeText(
      [
        location.href,
        header,
        visibleOwnMessages
      ].join(" :: ")
    );
  };

  const waitForChatToSettle = async () => {
    await sleep(900);

    const first = getCurrentChatIdentity();

    await sleep(700);

    const second = getCurrentChatIdentity();

    return second || first;
  };

  const waitForNextOpenChat = async (lastProcessedIdentity) => {
    const started = Date.now();
    let lastLog = 0;

    while (!window.__redditSingleChatCleanupStop) {
      const elapsedSeconds = Math.floor((Date.now() - started) / 1000);

      if (elapsedSeconds > WAIT_FOR_NEXT_CHAT_SECONDS) {
        console.warn(`Timed out waiting for another chat after ${WAIT_FOR_NEXT_CHAT_SECONDS} seconds.`);
        return null;
      }

      if (isChatOpenForCleanup()) {
        const identity = await waitForChatToSettle();

        if (identity && identity !== lastProcessedIdentity) {
          console.log("Detected an open chat to woodchip.");
          return {
            identity
          };
        }
      }

      if (Date.now() - lastLog > 5000) {
        const remaining = WAIT_FOR_NEXT_CHAT_SECONDS - elapsedSeconds;
        console.log(`Waiting for you to open another chat... ${remaining}s left. Stop with: window.__redditSingleChatCleanupStop = true`);
        lastLog = Date.now();
      }

      await sleep(1000);
    }

    return null;
  };

  const waitUntilCurrentChatChangesOrCloses = async (processedIdentity) => {
    const started = Date.now();

    while (Date.now() - started < 8000) {
      await sleep(500);

      const currentIdentity = getCurrentChatIdentity();

      if (!currentIdentity || currentIdentity !== processedIdentity || isWelcomeScreen()) {
        return true;
      }
    }

    return false;
  };

  const processCurrentlyOpenChat = async (chatNumber, chatIdentity) => {
    console.log(`Woodchipper pass ${chatNumber}/${MAX_CHATS_TO_PROCESS} started.`);
    console.log(`Current chat identity: ${chatIdentity.slice(0, 180)}`);

    const deleteResult = await deleteOpenChatMessages();

    console.log("Delete pass finished.");
    console.log(`Deleted: ${deleteResult.deleted}`);
    console.log(`Failed/skipped delete attempts: ${deleteResult.failed}`);
    console.log(`Total delete attempts: ${deleteResult.totalAttempts}`);

    if (window.__redditSingleChatCleanupStop) {
      console.warn("Stopped by user before hide step.");
      return {
        hidden: false,
        stopped: true
      };
    }

    if (!HIDE_AFTER_DELETE) {
      console.log("Automatic hide disabled in Streamlit settings.");
      return {
        hidden: false,
        stopped: false
      };
    }

    console.log("Automatic hide is enabled. Hiding this chat now...");

    const hidden = await hideCurrentChat();

    if (hidden) {
      console.log("Current chat was hidden.");
      await waitUntilCurrentChatChangesOrCloses(chatIdentity);

      return {
        hidden: true,
        stopped: false
      };
    }

    console.warn("Delete pass finished, but hiding failed. Try hiding manually from Gear -> Hide chat.");

    return {
      hidden: false,
      stopped: false
    };
  };

  console.log("Single-chat woodchipper started.");
  console.log("Open one chat, let it delete/hide, then open the next chat.");
  console.log(`Username: ${USERNAME}`);
  console.log(`Max chats to process: ${MAX_CHATS_TO_PROCESS}`);
  console.log(`Waiting up to ${WAIT_FOR_NEXT_CHAT_SECONDS}s for each next chat.`);
  console.log("Stop anytime with: window.__redditSingleChatCleanupStop = true");

  let processedCount = 0;
  let lastProcessedIdentity = "";
  let totalDeletedAcrossChats = 0;
  let totalFailedAcrossChats = 0;
  let totalHiddenAcrossChats = 0;

  while (
    !window.__redditSingleChatCleanupStop &&
    processedCount < MAX_CHATS_TO_PROCESS
  ) {
    const nextChat = await waitForNextOpenChat(lastProcessedIdentity);

    if (!nextChat) {
      break;
    }

    processedCount++;

    const beforeDeletedLineCount = 0;

    const result = await processCurrentlyOpenChat(processedCount, nextChat.identity);

    // Totals are logged per chat inside deleteOpenChatMessages. These counters track hides/processed.
    if (result.hidden) totalHiddenAcrossChats++;

    lastProcessedIdentity = nextChat.identity;

    if (result.stopped) break;

    console.log(`Woodchipper pass ${processedCount} finished.`);
    console.log("Open another chat when ready, and the script will continue automatically.");
    await sleep(1200);
  }

  console.log("Woodchipper stopped.");
  console.log(`Chats processed: ${processedCount}`);
  console.log(`Chats hidden: ${totalHiddenAcrossChats}`);
  console.log("To run again, paste the generated script again.");
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
            .replace("__MAX_TOTAL_DELETE_ATTEMPTS__", str(int(max_total_attempts)))
            .replace("__MAX_NO_PROGRESS_ATTEMPTS__", str(int(max_no_progress_attempts)))
            .replace("__MAX_EMPTY_SCROLL_ROUNDS__", str(int(max_empty_scroll_rounds)))
            .replace("__MAX_CHATS_TO_PROCESS__", str(int(max_chats_to_process)))
            .replace("__WAIT_FOR_NEXT_CHAT_SECONDS__", str(int(wait_for_next_chat_seconds)))
            .replace("__HIDE_AFTER_DELETE__", "true" if hide_after_delete else "false")
            .strip()
        )

        st.success("Script generated for the currently open Reddit chat.")

        st.markdown(
            """
            **How to run it:**

            1. On Reddit, open the single chat you want to clean.
            2. Open DevTools.
            3. Go to the **Console** tab.
            4. Paste the script below.
            5. Press Enter.

            Stop while it is running with:

            ```js
            window.__redditSingleChatCleanupStop = true
            ```
            """
        )

        st.code(script, language="javascript")

        st.download_button(
            label="Download generated script as .js",
            data=script,
            file_name="reddit_chat_woodchipper_auto_delete_hide.js",
            mime="text/javascript",
            use_container_width=True
        )
else:
    st.info("Enter your username and click the button to generate the woodchipper script.")
