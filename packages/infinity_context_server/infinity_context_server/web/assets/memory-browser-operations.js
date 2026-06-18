(() => {
  "use strict";

  const browser = window.infinityContextBrowser;
  if (!browser) {
    return;
  }

  const {
    state,
    els,
    apiJson,
    refreshAll,
    listItem,
    emptyItem,
    sectionLabel,
    actionButton,
    formatDate,
    shortId,
    setError,
  } = browser;

  window.infinityContextOperations = {
    renderOperations,
  };

  function renderOperations() {
    els.operationsList.replaceChildren();
    const console = state.operationsConsole;
    if (!console) {
      els.operationsList.append(emptyItem("Operations unavailable."));
      return;
    }
    if (console.diagnostics?.scope_not_found) {
      els.operationsList.append(emptyItem("Create or select a MemoryScope to see operations."));
      return;
    }

    els.operationsList.append(
      operationSummaryItem(
        "Extraction jobs",
        console.extraction_status_counts || {},
        console.diagnostics?.extraction_active_count,
        console.diagnostics?.extraction_retryable_count,
      ),
      operationSummaryItem(
        "Link review queue",
        console.link_suggestion_status_counts || {},
        console.diagnostics?.link_suggestion_pending_count,
        console.diagnostics?.link_suggestion_reviewed_count,
      ),
    );

    const jobs = console.extraction_jobs || [];
    if (!jobs.length) {
      els.operationsList.append(emptyItem("No extraction jobs."));
      return;
    }

    els.operationsList.append(sectionLabel("Recent extractions"));
    for (const job of jobs.slice(0, 50)) {
      els.operationsList.append(extractionJobItem(job));
    }
  }

  function operationSummaryItem(title, counts, primaryCount, secondaryCount) {
    const countText = Object.entries(counts)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([status, count]) => `${status}:${count}`)
      .join("  ");
    return listItem({
      title,
      text: countText || "No activity.",
      meta: [primaryCount ?? 0, secondaryCount ?? 0].join(" / "),
    });
  }

  function extractionJobItem(job) {
    const progress = job.progress || {};
    const execution = job.execution || {};
    const parts = [
      `${job.parser_profile || "profile"} / ${job.parser_name || "pending"}`,
      progress.message,
      job.safe_error_message,
      execution.retry_after_at ? `Retry after ${formatDate(execution.retry_after_at)}` : "",
    ].filter(Boolean);
    const item = listItem({
      title: `${job.status} / ${progress.percent ?? 0}%`,
      text: parts.join("\n"),
      meta: `${shortId(job.asset_id)} ${formatDate(job.updated_at)}`,
    });
    const retryable = ["failed", "unsupported", "canceled", "stale"].includes(job.status);
    const cancelable = ["pending", "running"].includes(job.status);
    if (retryable || cancelable) {
      item.append(extractionJobActions(job, { retryable, cancelable }));
    }
    return item;
  }

  function extractionJobActions(job, { retryable, cancelable }) {
    const actions = document.createElement("div");
    actions.className = retryable && cancelable ? "action-row two-actions" : "action-row one-action";
    if (retryable) {
      actions.append(actionButton("Retry", () => retryAssetExtraction(job.id), "primary-button"));
    }
    if (cancelable) {
      actions.append(actionButton("Cancel", () => cancelAssetExtraction(job.id)));
    }
    return actions;
  }

  async function retryAssetExtraction(jobId) {
    if (!window.confirm("Retry this extraction job?")) {
      return;
    }
    setError("");
    try {
      await apiJson(`/v1/asset-extractions/${encodeURIComponent(jobId)}/retry`, {
        method: "POST",
      });
      await refreshAll({ silent: true });
      setError("Extraction retry queued.");
    } catch (error) {
      setError(error.message);
    }
  }

  async function cancelAssetExtraction(jobId) {
    if (!window.confirm("Cancel this extraction job?")) {
      return;
    }
    setError("");
    try {
      await apiJson(`/v1/asset-extractions/${encodeURIComponent(jobId)}/cancel`, {
        method: "POST",
      });
      await refreshAll({ silent: true });
      setError("Extraction cancellation requested.");
    } catch (error) {
      setError(error.message);
    }
  }
})();
