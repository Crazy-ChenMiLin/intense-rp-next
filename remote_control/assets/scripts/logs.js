(function () {
  const remote = window.IRPRemote;
  const state = remote.state;
  const elements = remote.elements;
  const assets = remote.config.assets || {};
  const icons = assets.icons || {};

  let pendingLogEntries = [];
  let logFlushScheduled = false;

  function clearConsolePlaceholder() {
    const placeholder = document.getElementById("console-placeholder");
    if (placeholder) {
      placeholder.remove();
    }
  }

  function setConsolePlaceholder(text) {
    let placeholder = document.getElementById("console-placeholder");
    if (!placeholder && elements.consoleOutput && !elements.consoleOutput.children.length) {
      placeholder = document.createElement("div");
      placeholder.id = "console-placeholder";
      placeholder.className = "console-output__placeholder";
      elements.consoleOutput.appendChild(placeholder);
    }
    if (placeholder) {
      placeholder.textContent = text || "";
    }
  }

  function logEntryId(entry) {
    const id = Number(entry && entry.id);
    return Number.isFinite(id) && id > 0 ? id : 0;
  }

  function flushPendingLogs() {
    logFlushScheduled = false;
    if (!pendingLogEntries.length) {
      return;
    }

    clearConsolePlaceholder();
    const fragment = document.createDocumentFragment();
    pendingLogEntries.forEach((entry) => {
      const line = document.createElement("div");
      line.className = "log-line log-line--" + remote.escapeHtml(entry.level || "INFO");
      line.textContent = entry.message || "";
      fragment.appendChild(line);
    });
    pendingLogEntries = [];
    elements.consoleOutput.appendChild(fragment);
    elements.consoleOutput.scrollTop = elements.consoleOutput.scrollHeight;
  }

  function appendLog(entry) {
    const id = logEntryId(entry);
    if (id && id <= state.logLastId) {
      return;
    }
    if (id) {
      state.logLastId = id;
    }

    pendingLogEntries.push(entry);
    if (logFlushScheduled) {
      return;
    }
    logFlushScheduled = true;
    window.requestAnimationFrame(flushPendingLogs);
  }

  function resetConsoleOutput(placeholderText) {
    pendingLogEntries = [];
    logFlushScheduled = false;
    if (elements.consoleOutput) {
      elements.consoleOutput.innerHTML = "";
    }
    setConsolePlaceholder(placeholderText || "正在加载日志");
  }

  function setLogsConnected(connected, message) {
    state.logConnected = Boolean(connected);
    if (state.logConnected) {
      elements.logsFooterButton.innerHTML = '<span class="web-button__label">返回</span>';
      remote.setStatus(elements.logsStatus, "", false);
    } else {
      elements.logsFooterButton.innerHTML =
        '<span class="web-button__icon" aria-hidden="true"><img src="' +
        remote.escapeHtml(icons.chevron_right) +
        '" alt=""></span><span class="web-button__label">重新连接</span>';
      remote.setStatus(elements.logsStatus, message || "日志连接已断开。", true);
    }
  }

  function stop() {
    if (state.logController) {
      state.logController.abort();
      state.logController = null;
    }
    state.logConnected = false;
  }

  async function loadLogHistory(controller) {
    const response = await remote.requestJson(remote.apiUrl("/api/logs/history"), {
      method: "GET",
      headers: remote.authHeaders(false),
      cache: "no-store",
      signal: controller.signal,
    });

    const entries = response && Array.isArray(response.entries) ? response.entries : [];
    const latestId = Number(response && response.latest_id);
    if (Number.isFinite(latestId) && latestId < state.logLastId) {
      state.logLastId = 0;
      resetConsoleOutput("正在加载日志");
    }

    entries.forEach((entry) => {
      appendLog(entry);
    });
    flushPendingLogs();

    if (Number.isFinite(latestId) && latestId > state.logLastId) {
      state.logLastId = latestId;
    }
  }

  async function start() {
    stop();
    setLogsConnected(true, "");
    setConsolePlaceholder("正在加载日志");

    const controller = new AbortController();
    state.logController = controller;

    try {
      await loadLogHistory(controller);
      if (controller.signal.aborted) {
        return;
      }

      setConsolePlaceholder("已连接，等待日志...");
      const streamUrl = remote.apiUrl(
        "/api/logs/stream?after=" + encodeURIComponent(String(state.logLastId || 0))
      );
      const response = await fetch(streamUrl, {
        method: "GET",
        headers: remote.authHeaders(false),
        cache: "no-store",
        signal: controller.signal,
      });

      if (!response.ok || !response.body) {
        throw new Error("无法连接到日志流。");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const result = await reader.read();
        if (result.done) {
          throw new Error("The logs stream closed.");
        }

        buffer += decoder.decode(result.value, { stream: true });
        const blocks = buffer.split("\n\n");
        buffer = blocks.pop() || "";

        blocks.forEach((block) => {
          if (!block || block.startsWith(":")) {
            return;
          }
          const lines = block.split("\n");
          let eventName = "message";
          let dataText = "";
          lines.forEach((line) => {
            if (line.startsWith("event:")) {
              eventName = line.slice(6).trim();
            } else if (line.startsWith("data:")) {
              dataText += line.slice(5).trim();
            }
          });
          if (eventName === "connected") {
            setLogsConnected(true, "");
            setConsolePlaceholder("已连接，等待日志...");
            return;
          }
          if (eventName !== "log" || !dataText) {
            return;
          }
          try {
            const entry = JSON.parse(dataText);
            appendLog(entry);
          } catch (_error) {
            // Ignore malformed log events.
          }
        });
      }
    } catch (error) {
      if (controller.signal.aborted) {
        return;
      }
      setLogsConnected(
        false,
        error && error.message ? error.message : "日志连接已断开。"
      );
    } finally {
      if (state.logController === controller) {
        state.logController = null;
      }
    }
  }

  remote.logs = {
    start: start,
    stop: stop,
  };
})();
