/* Framework-free, same-origin consumer. Never render returned values as HTML. */
"use strict";

const form = document.getElementById("ask-form");
const status = document.getElementById("status");
const results = document.getElementById("results");
const button = form.querySelector("button");

function renderTable(result) {
  const table = document.createElement("table");
  const caption = table.createCaption();
  caption.textContent = "Orders in your current authorized scope";
  const header = table.createTHead().insertRow();
  for (const column of result.columns) {
    const th = document.createElement("th");
    th.scope = "col";
    th.textContent = column.label || column.key;
    header.appendChild(th);
  }
  const body = table.createTBody();
  for (const row of result.data) {
    const tr = body.insertRow();
    for (const column of result.columns) {
      // Explicit columns only; do not enumerate other keys on the row.
      const cell = tr.insertCell();
      cell.textContent = row[column.key] == null ? "—" : String(row[column.key]);
    }
  }
  return table;
}

function recoveryMessage(response, payload) {
  if (response.status === 401 || response.status === 403) {
    return "Access failed. Sign in again or ask the host administrator to review access.";
  }
  if (response.status === 429) {
    return "Too many requests. Wait before retrying; follow the host retry policy.";
  }
  if (payload?.error?.code === "asklens.member.unavailable") {
    return "A requested query member is unavailable. Refresh the visible catalog or ask the host administrator.";
  }
  return "The request could not be completed. Use an exact configured question or retry later.";
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  results.replaceChildren(); // Never leave stale authorized rows on an error.
  results.setAttribute("aria-busy", "true");
  button.disabled = true;
  status.textContent = "Loading…";
  try {
    const response = await fetch(form.action, {
      method: "POST",
      mode: "same-origin",
      credentials: "same-origin",
      redirect: "error",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": form.elements.csrfmiddlewaretoken.value,
      },
      body: JSON.stringify({
        question: form.elements.question.value,
        include_presentation: false,
      }),
    });
    // Login redirects, HTML CSRF failures, and raw errors are not UI messages.
    const payload = response.headers.get("content-type")?.includes("application/json")
      ? await response.json() : null;
    if (!response.ok || payload?.error) {
      status.textContent = recoveryMessage(response, payload);
    } else if (payload?.response_type !== "query") {
      status.textContent = "Use one of the exact configured data questions.";
    } else {
      const result = payload.result;
      if (!Array.isArray(result?.columns) || !Array.isArray(result?.data)) {
        throw new Error("Unexpected result shape");
      }
      results.appendChild(renderTable(result));
      status.textContent = result.data.length === 0
        ? "No matching rows in your current authorized scope."
        : `${result.row_count} rows returned.`;
      if (result.result_metadata?.truncated) {
        status.textContent += " Showing a limited result; refine your question. No next-page cursor is available.";
      }
    }
  } catch {
    results.replaceChildren();
    status.textContent = "The request could not be completed. Check your connection and sign in, then retry.";
  } finally {
    results.setAttribute("aria-busy", "false");
    button.disabled = false;
  }
});
