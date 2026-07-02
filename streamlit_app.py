// Reddit Selected-Chat Own-Message Bulk Delete
// Shows a checkbox picker first.
// Deletes only YOUR sent messages in the selected chats.
// Does NOT delete comments.
// Does NOT delete posts.
// Run on https://www.reddit.com/chat with the left chat sidebar visible.

(async () => {
  const USERNAME = prompt("Enter your exact Reddit username, without u/:");
  if (!USERNAME) return console.log("Cancelled: username required.");

  const MAX_DELETES_PER_MINUTE = Number(
    prompt("Max deletes per minute? Try 60-100.", "80")
  ) || 80;

  const DELETE_DELAY_MS = Math.ceil(60000 / MAX_DELETES_PER_MINUTE);
  const SHORT_DELAY_MS = 100;
  const MENU_DELAY_MS = 150;
  const CONFIRM_DELAY_MS = 150;
  const SCROLL_DELAY_MS = 600;
  const CHAT_SWITCH_DELAY_MS = 1800;

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  const escapeRegExp = (value) =>
    value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

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
    if (!el) return false;

    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);

    return (
      r.width > 0 &&
      r.height > 0 &&
      s.display !== "none" &&
      s.visibility !== "hidden"
    );
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
    return (
      el.innerText ||
      el.textContent ||
      el.getAttribute("aria-label") ||
      el.getAttribute("title") ||
      el.href ||
      ""
    ).trim();
  };

  const cleanText = (text) => {
    return String(text || "")
      .replace(/\s+/g, " ")
      .trim();
  };

  const getChatKey = (el) => {
    const href = el.href || el.getAttribute("href") || "";
    const text = cleanText(getReadableText(el)).slice(0, 160);
    return href || text;
  };

  const isOwnMessage = (eventEl) => {
    const msg = localQuery(eventEl, ".room-message[aria-label], [aria-label]");
    const aria = msg?.getAttribute("aria-label") || "";

    return new RegExp(
      "^" + escapeRegExp(USERNAME) + "\\s+said\\b",
      "i"
    ).test(aria.trim());
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

  const confirmDeleteDialog = async () => {
    await sleep(CONFIRM_DELAY_MS);

    const buttons = deepQueryAll('button, [role="button"], rs-button').filter(
      isVisible
    );

    const confirm = buttons.find((b) => {
      const text = getReadableText(b).toLowerCase();

      return (
        text.includes("yes, delete") ||
        text === "delete" ||
        text.includes("confirm")
      );
    });

    if (confirm) {
      confirm.click();
      return true;
    }

    return false;
  };

  const deleteOne = async (eventEl) => {
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
        return false;
      }

      more.click();
      await sleep(MENU_DELAY_MS);

      const deleteItem = findDeleteMenuItem();

      if (!deleteItem) {
        return false;
      }

      deleteItem.click();
    }

    await confirmDeleteDialog();
    await sleep(DELETE_DELAY_MS);

    return true;
  };

  const getOwnMessageEvents = () =>
    deepQueryAll("rs-timeline-event")
      .filter(isVisible)
      .filter(isOwnMessage);

  const findChatMessageScroller = () => {
    const scrollables = deepQueryAll("*").filter((el) => {
      try {
        const r = el.getBoundingClientRect();
        const s = getComputedStyle(el);

        return (
          isVisible(el) &&
          r.left > window.innerWidth * 0.25 &&
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
    let lastCount = -1;
    let stuckRounds = 0;

    while (true) {
      const ownMessages = getOwnMessageEvents();

      if (ownMessages.length === 0) {
        stuckRounds++;
      } else {
        stuckRounds = 0;
      }

      for (const msg of ownMessages) {
        const ok = await deleteOne(msg);

        if (ok) {
          deleted++;
          console.log(`Deleted ${deleted} message(s) in this chat...`);
        } else {
          failed++;
          console.log(`Skipped/failed ${failed} message(s) in this chat...`);
        }
      }

      await scrollCurrentChatUp();

      const currentCount = getOwnMessageEvents().length;

      if (currentCount === lastCount) {
        stuckRounds++;
      }

      lastCount = currentCount;

      if (stuckRounds >= 3) {
        break;
      }
    }

    return { deleted, failed };
  };

  const getChatCandidates = () => {
    const candidates = deepQueryAll(
      [
        'a[href*="/chat/"]',
        '[role="link"][href*="/chat/"]',
        '[role="listitem"]',
        'rs-list-item',
        'button'
      ].join(",")
    )
      .filter(isVisible)
      .filter((el) => {
        const r = el.getBoundingClientRect();
        const text = cleanText(getReadableText(el));

        if (!text || text.length < 2) return false;

        const inLeftSidebar =
          r.left < window.innerWidth * 0.45 &&
          r.width > 120 &&
          r.height >= 28 &&
          r.height <= 130;

        const notTopNav = r.top > 70;

        const notObviousBadItem =
          !/create|settings|logout|advertise|premium|popular|home|all|messages|notifications/i.test(
            text
          );

        return inLeftSidebar && notTopNav && notObviousBadItem;
      });

    const unique = [];
    const seen = new Set();

    for (const el of candidates) {
      const key = getChatKey(el);
      const text = cleanText(getReadableText(el)).slice(0, 160);

      if (!key || seen.has(key)) continue;

      seen.add(key);
      unique.push({
        key,
        text: text || key,
        href: el.href || el.getAttribute("href") || "",
        element: el
      });
    }

    return unique;
  };

  const findChatElementByKey = (key) => {
    const candidates = getChatCandidates();

    const match = candidates.find((chat) => chat.key === key);

    if (match && match.element && isVisible(match.element)) {
      return match.element;
    }

    return null;
  };

  const clickChatByKey = async (key, fallbackText) => {
    let chatEl = findChatElementByKey(key);

    if (!chatEl) {
      console.warn(`Could not find chat again: ${fallbackText || key}`);
      return false;
    }

    chatEl.scrollIntoView({ block: "center" });
    await sleep(300);

    console.log(`Opening selected chat: ${fallbackText || key}`);

    chatEl.click();
    await sleep(CHAT_SWITCH_DELAY_MS);

    return true;
  };

  const showChatPicker = async () => {
    const chats = getChatCandidates();

    if (chats.length === 0) {
      alert(
        "No chats found. Make sure you are on reddit.com/chat and the left chat sidebar is visible."
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
      panel.style.width = "min(720px, 92vw)";
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

        <div style="display:flex;gap:8px;margin-bottom:12px;">
          <button id="rcc-select-all" style="padding:8px 10px;cursor:pointer;">Select all</button>
          <button id="rcc-select-none" style="padding:8px 10px;cursor:pointer;">Select none</button>
        </div>

        <div id="rcc-list" style="border:1px solid #ddd;border-radius:8px;overflow:hidden;"></div>

        <div style="display:flex;justify-content:flex-end;gap:10px;margin-top:14px;">
          <button id="rcc-cancel" style="padding:10px 14px;cursor:pointer;">Cancel</button>
          <button id="rcc-run" style="padding:10px 14px;cursor:pointer;background:#ff4500;color:#fff;border:0;border-radius:6px;">
            Delete selected chats
          </button>
        </div>
      `;

      const list = panel.querySelector("#rcc-list");

      chats.forEach((chat, index) => {
        const row = document.createElement("label");
        row.style.display = "flex";
        row.style.alignItems = "center";
        row.style.gap = "10px";
        row.style.padding = "10px";
        row.style.borderBottom = "1px solid #eee";
        row.style.cursor = "pointer";
        row.style.fontSize = "14px";

        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.checked = false;
        checkbox.dataset.index = String(index);

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
          href: chats[i].href
        }));

        closeWith(selected);
      };
    });
  };

  console.log("Scanning visible chats...");
  console.log("Tip: scroll the left chat sidebar before running if you want more chats to appear.");

  const selectedChats = await showChatPicker();

  if (!selectedChats.length) {
    console.log("No chats selected. Cancelled.");
    return;
  }

  console.log(`Selected ${selectedChats.length} chat(s).`);
  console.log(`Speed: up to ${MAX_DELETES_PER_MINUTE} deletes per minute.`);

  let totalDeleted = 0;
  let totalFailed = 0;
  let processedChats = 0;

  for (const chat of selectedChats) {
    const opened = await clickChatByKey(chat.key, chat.text);

    if (!opened) {
      totalFailed++;
      continue;
    }

    processedChats++;

    console.log(`Cleaning selected chat ${processedChats}/${selectedChats.length}: ${chat.text}`);

    const result = await deleteCurrentChatMessages();

    totalDeleted += result.deleted;
    totalFailed += result.failed;

    console.log(
      `Finished chat: ${chat.text}. Deleted: ${result.deleted}. Failed/skipped: ${result.failed}.`
    );
  }

  console.log("Selected-chat cleanup finished.");
  console.log(`Chats processed: ${processedChats}`);
  console.log(`Total deleted: ${totalDeleted}`);
  console.log(`Total skipped/failed: ${totalFailed}`);

  if (totalFailed > 0) {
    console.log("If many messages failed, run again with a slower speed like 60.");
  }
})();
