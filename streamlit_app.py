import json
import streamlit as st

st.set_page_config(
    page_title="Reddit Chat Delete Script Generator",
    page_icon="🧹",
    layout="centered"
)

st.title("Reddit Chat Delete Script Generator")
st.caption("Generate a selected-chat delete script, then paste it into Reddit's DevTools Console.")

st.warning(
    "Hosted Streamlit apps cannot directly control reddit.com in your browser. "
    "This app generates JavaScript that you paste into the Console on a Reddit chat page."
)

username = st.text_input(
    "Reddit username",
    placeholder="without u/"
)

speed = st.slider(
    "Max deletes per minute",
    min_value=20,
    max_value=150,
    value=80,
    step=10
)

retry_rounds = st.slider(
    "Max retry rounds per chat",
    min_value=3,
    max_value=30,
    value=12,
    step=1,
    help="The script will keep retrying visible failed messages until they disappear or this limit is reached."
)

no_progress_rounds = st.slider(
    "Stop after this many no-progress rounds",
    min_value=2,
    max_value=10,
    value=4,
    step=1,
    help="Stops a chat if Reddit refuses to delete messages repeatedly."
)

generate = st.button(
    "Generate selected-chat retry delete script",
    type="primary",
    use_container_width=True
)

JS_TEMPLATE = r"""
// Reddit Selected-Chat Own-Message Bulk Delete with Retry + Sidebar Recovery
// Shows a checkbox picker first.
// Deletes only YOUR sent messages in the selected chats.
// Retries failed visible messages until they disappear or the safety limit is reached.
// Does NOT delete comments.
// Does NOT delete posts.
// Works on Reddit chat pages even if the URL is not exactly /chat.
// Run on any Reddit chat page where the left chat sidebar is visible.
//
// Tip: If Reddit hides the sidebar after opening a chat, this version tries Back/history.back()
// before moving to the next selected chat.

(async () => {
  const USERNAME = __USERNAME_JSON__;
  const MAX_DELETES_PER_MINUTE = __MAX_DELETES__;

  const MAX_RETRY_ROUNDS_PER_CHAT = __MAX_RETRY_ROUNDS__;
  const MAX_NO_PROGRESS_ROUNDS = __MAX_NO_PROGRESS_ROUNDS__;

  const DELETE_DELAY_MS = Math.ceil(60000 / MAX_DELETES_PER_MINUTE);
  const SHORT_DELAY_MS = 100;
  const MENU_DELAY_MS = 150;
  const CONFIRM_DELAY_MS = 150;
  const SCROLL_DELAY_MS = 600;
  const CHAT_SWITCH_DELAY_MS = 1800;
  const SIDEBAR_RECOVERY_DELAY_MS = 1400;
  const GONE_CHECK_TIMEOUT_MS = 2500;
  const GONE_CHECK_INTERVAL_MS = 150;

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
    const link = localQuery(el, "a");

    const href =
      el.href ||
      el.getAttribute("href") ||
      link?.href ||
      link?.getAttribute("href") ||
      "";

    const text = cleanText(getReadableText(el)).slice(0, 180);

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

  const waitUntilMessageGone = async (eventEl) => {
    const started = Date.now();

    while (Date.now() - started < GONE_CHECK_TIMEOUT_MS) {
      await sleep(GONE_CHECK_INTERVAL_MS);

      if (!document.contains(eventEl)) {
        return true;
      }

      if (!isVisible(eventEl)) {
        return true;
      }

      if (!isOwnMessage(eventEl)) {
        return true;
      }
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

    const gone = await waitUntilMessageGone(eventEl);

    return gone;
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
    let retryRounds = 0;
    let noProgressRounds = 0;
    let lastRemainingCount = Infinity;

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
          console.log("Delete attempt failed. It will retry if the message remains visible.");
        }
      }

      await scrollCurrentChatUp();

      const remaining = getOwnMessageEvents().length;

      console.log(
        `Round ${retryRounds} done. Deleted this round: ${roundDeleted}. Failed this round: ${roundFailed}. Remaining visible own messages: ${remaining}.`
      );

      if (remaining === 0) {
        console.log("All visible own messages are gone in this chat.");
        break;
      }

      if (remaining >= lastRemainingCount && roundDeleted === 0) {
        noProgressRounds++;
      } else {
        noProgressRounds = 0;
      }

      lastRemainingCount = remaining;

      if (noProgressRounds >= MAX_NO_PROGRESS_ROUNDS) {
        console.warn(
          "Stopping this chat because repeated retry rounds made no progress. Reddit may be refusing deletion, the UI changed, or these messages may not be deletable."
        );
        break;
      }

      await sleep(1000);
    }

    return { deleted, failed };
  };

  const getChatCandidates = () => {
    const selectors = [
      'a[href*="chat"]',
      'a[href*="channel"]',
      'a[href*="room"]',
      '[role="link"]',
      '[role="listitem"]',
      '[role="option"]',
      'rs-list-item',
      'rs-room-list-item',
      'rs-conversation-list-item',
      'button',
      'a'
    ].join(",");

    const raw = deepQueryAll(selectors)
      .filter(isVisible)
      .filter((el) => {
        const r = el.getBoundingClientRect();
        const text = cleanText(getReadableText(el));

        if (!text || text.length < 2) return false;

        const inLeftSidebar =
          r.left >= 0 &&
          r.left < window.innerWidth * 0.5 &&
          r.width >= 90 &&
          r.width <= window.innerWidth * 0.6 &&
          r.height >= 24 &&
          r.height <= 170;

        const notTopNav = r.top > 55;

        const notObviousBadItem =
          !/create|settings|logout|advertise|premium|popular|home|all|notifications|explore|search|close|back|help|privacy|terms|reddit recap|communities|custom feeds/i.test(
            text
          );

        return inLeftSidebar && notTopNav && notObviousBadItem;
      });

    const unique = [];
    const seen = new Set();

    for (const el of raw) {
      const r = el.getBoundingClientRect();

      const link = localQuery(el, "a");

      const href =
        el.href ||
        el.getAttribute("href") ||
        link?.href ||
        link?.getAttribute("href") ||
        "";

      const text = cleanText(getReadableText(el)).slice(0, 180);
      const key = href || text;

      if (!key || seen.has(key)) continue;

      seen.add(key);

      unique.push({
        key,
        text: text || key,
        href,
        top: Math.round(r.top),
        left: Math.round(r.left),
        width: Math.round(r.width),
        height: Math.round(r.height),
        element: el
      });
    }

    console.log(
      "Detected chat candidates:",
      unique.map((chat, i) => ({
        number: i + 1,
        text: chat.text,
        href: chat.href,
        top: chat.top,
        left: chat.left,
        width: chat.width,
        height: chat.height
      }))
    );

    return unique;
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

    if (possibleBackButtons.length === 0) {
      return false;
    }

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

    if (chats.length > 0) {
      return true;
    }

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

    console.warn(
      "Still cannot see the chat list. Widen the Reddit window or undock DevTools, then run again."
    );

    return false;
  };

  const findChatElementByKey = async (key, fallbackText = "") => {
    await returnToChatListIfNeeded();

    const candidates = getChatCandidates();

    let match = candidates.find((chat) => chat.key === key);

    if (!match && fallbackText) {
      const cleanedFallback = cleanText(fallbackText).toLowerCase();

      match = candidates.find((chat) => {
        const cleanedCandidate = cleanText(chat.text).toLowerCase();

        return (
          cleanedCandidate === cleanedFallback ||
          cleanedCandidate.includes(cleanedFallback) ||
          cleanedFallback.includes(cleanedCandidate)
        );
      });
    }

    if (match && match.element && isVisible(match.element)) {
      return match.element;
    }

    return null;
  };

  const clickChatByKey = async (key, fallbackText) => {
    const chatEl = await findChatElementByKey(key, fallbackText);

    if (!chatEl) {
      console.warn(`Could not find chat again: ${fallbackText || key}`);
      return false;
    }

    chatEl.scrollIntoView({ block: "center" });
    await sleep(300);

    console.log(`Opening selected chat: ${fallbackText || key}`);

    // Use a real click instead of location.href. This helps keep Reddit's sidebar layout alive.
    chatEl.click();

    await sleep(CHAT_SWITCH_DELAY_MS);

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
      panel.style.width = "min(760px, 92vw)";
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
          If a chat is missing, cancel this popup, scroll the left Reddit chat sidebar to load more chats,
          then run the script again. If the script only processes one chat, undock DevTools or widen the Reddit window.
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
  console.log("Current URL:", location.href);
  console.log("Tip: the URL does not need to be exactly /chat.");
  console.log("Tip: scroll the left chat sidebar before running if you want more chats to appear.");
  console.log("Tip: if only one chat processes, undock DevTools or widen the Reddit window.");
  console.log(`Retry settings: ${MAX_RETRY_ROUNDS_PER_CHAT} retry rounds per chat, stop after ${MAX_NO_PROGRESS_ROUNDS} no-progress rounds.`);

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
      `Finished chat: ${chat.text}. Deleted: ${result.deleted}. Failed/skipped attempts: ${result.failed}.`
    );

    // After each chat, try to restore the chat list before the next loop.
    await returnToChatListIfNeeded();
  }

  console.log("Selected-chat cleanup finished.");
  console.log(`Chats processed: ${processedChats}`);
  console.log(`Total deleted: ${totalDeleted}`);
  console.log(`Total skipped/failed attempts: ${totalFailed}`);

  if (totalFailed > 0) {
    console.log("If many messages failed, run again with a slower speed like 60 or increase retry rounds.");
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
            .strip()
        )

        st.success("Script generated.")

        st.markdown(
            """
            **How to use it:**

            1. Open Reddit Chat.
            2. It is okay if Reddit redirects you to a specific chat/channel URL.
            3. Make sure the left chat sidebar is visible.
            4. For best results, undock DevTools or make the Reddit window wide.
            5. Scroll the left chat sidebar until the chats you want are loaded.
            6. Open DevTools.
            7. Go to the **Console** tab.
            8. Paste the generated script.
            9. Select the chats in the popup.
            10. Click **Delete selected chats**.

            This version tries to recover the sidebar after each chat before moving to the next one.
            """
        )

        st.code(script, language="javascript")

        st.download_button(
            label="Download script as .js",
            data=script,
            file_name="reddit_selected_chat_retry_delete_sidebar_recovery.js",
            mime="text/javascript",
            use_container_width=True
        )
else:
    st.info("Enter your Reddit username and click the button to generate the script.")
