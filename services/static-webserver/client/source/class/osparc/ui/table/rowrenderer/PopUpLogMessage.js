/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2026 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Row renderer for the Logger table that shows a floating overlay with
 * the full log message, timestamp, origin, and log level when a row is clicked.
 *
 * Uses a fixed-position overlay appended to document.body, which avoids
 * qooxdoo table pane clipping constraints (overflow:hidden at multiple levels).
 */
qx.Class.define("osparc.ui.table.rowrenderer.PopUpLogMessage", {
  extend: qx.ui.table.rowrenderer.Default,

  construct: function(table, messageColPos) {
    this.base(arguments);

    this.__table = table;
    this.__messageColPos = messageColPos;
    this.__overlay = null;
    this.__dismissHandler = null;
    this.__scrollDismissHandler = null;
    this.__activeRowIndex = null;
  },

  statics: {
    LOG_LEVEL_INFO: {
      "-1": { label: "DEBUG", themeColor: "logger-debug-message" },
      "0": { label: "INFO", themeColor: "logger-info-message" },
      "1": { label: "WARNING", themeColor: "logger-warning-message" },
      "2": { label: "ERROR", themeColor: "logger-error-message" },
    },
  },

  members: {
    __table: null,
    __messageColPos: null,
    __overlay: null,
    __dismissHandler: null,
    __scrollDismissHandler: null,
    __activeRowIndex: null,

    __closeOverlay: function() {
      if (this.__overlay && this.__overlay.parentNode) {
        this.__overlay.parentNode.removeChild(this.__overlay);
      }
      this.__overlay = null;
      this.__activeRowIndex = null;
      if (this.__dismissHandler) {
        document.removeEventListener("mousedown", this.__dismissHandler, true);
        this.__dismissHandler = null;
      }
      if (this.__scrollDismissHandler) {
        document.removeEventListener("scroll", this.__scrollDismissHandler, true);
        this.__scrollDismissHandler = null;
      }
    },

    __getLogLevelBadge: function(rowData) {
      if (!rowData || rowData.logLevel == null) {
        return null;
      }
      const entry = this.self().LOG_LEVEL_INFO[String(rowData.logLevel)];
      if (!entry) {
        return null;
      }
      const colorManager = qx.theme.manager.Color.getInstance();
      const resolvedColor = colorManager.resolve(entry.themeColor);
      return { label: entry.label, color: resolvedColor };
    },

    __showOverlay: function(rowElem, rowInfo) {
      const messageDiv = rowElem.children.item(this.__messageColPos);
      if (!messageDiv) {
        return;
      }

      this.__closeOverlay();

      const rowData = rowInfo.rowData;
      const cellStyle = window.getComputedStyle(messageDiv);
      const rowStyle = window.getComputedStyle(rowElem);
      const rect = rowElem.getBoundingClientRect();
      const bgColor = rowElem.style.backgroundColor || rowStyle.backgroundColor || "#222";

      // Build overlay
      const overlay = document.createElement("div");
      const baseStyles = [
        "position: fixed",
        "left: " + rect.left + "px",
        "width: " + rect.width + "px",
        "max-height: 50vh",
        "overflow-y: auto",
        "padding: 8px 12px",
        "border-radius: 4px",
        "border: 1px solid rgba(255,255,255,0.15)",
        "box-shadow: 0 6px 20px rgba(0,0,0,0.4)",
        "z-index: 100000",
        "font-family: " + cellStyle.fontFamily,
        "font-size: " + cellStyle.fontSize,
        "color: " + cellStyle.color,
        "background-color: " + bgColor,
      ];

      // If the row is in the bottom half of the viewport, render the overlay above
      const viewportHeight = window.innerHeight;
      if (rect.bottom > viewportHeight * 0.65) {
        baseStyles.push("bottom: " + (viewportHeight - rect.bottom) + "px");
      } else {
        baseStyles.push("top: " + rect.top + "px");
      }

      overlay.style.cssText = baseStyles.join("; ");

      // Header row: [badge] [timestamp] [origin] ... [x]
      const header = document.createElement("div");
      header.style.cssText = [
        "display: flex",
        "align-items: center",
        "gap: 8px",
        "margin-bottom: 6px",
        "padding-bottom: 6px",
        "border-bottom: 1px solid rgba(255,255,255,0.12)",
        "font-size: 11px",
        "opacity: 0.85",
      ].join("; ");

      // Log level badge
      const badgeInfo = this.__getLogLevelBadge(rowData);
      if (badgeInfo) {
        const badge = document.createElement("span");
        badge.textContent = badgeInfo.label;
        badge.style.cssText = [
          "background-color: " + badgeInfo.color,
          "color: #000",
          "padding: 1px 6px",
          "border-radius: 3px",
          "font-weight: 600",
          "font-size: 10px",
          "letter-spacing: 0.5px",
        ].join("; ");
        header.appendChild(badge);
      }

      // Timestamp
      if (rowData && rowData.timeStamp) {
        const time = document.createElement("span");
        time.textContent = rowData.timeStamp;
        time.style.cssText = "opacity: 0.7; font-variant-numeric: tabular-nums";
        header.appendChild(time);
      }

      // Origin
      if (rowData && rowData.label) {
        const origin = document.createElement("span");
        origin.textContent = rowData.label;
        origin.style.cssText = "opacity: 0.7; margin-left: auto";
        header.appendChild(origin);
      }

      // Close button
      const closeBtn = document.createElement("span");
      closeBtn.textContent = "\u00d7";
      closeBtn.style.cssText = [
        "margin-left: auto",
        "cursor: pointer",
        "font-size: 16px",
        "line-height: 1",
        "opacity: 0.6",
        "padding: 0 2px",
      ].join("; ");
      const self = this;
      closeBtn.onclick = function(e) {
        e.stopPropagation();
        self.__closeOverlay();
      };
      header.appendChild(closeBtn);

      overlay.appendChild(header);

      // Message body
      const body = document.createElement("div");
      body.innerHTML = messageDiv.innerHTML;
      body.style.cssText = [
        "white-space: pre-wrap",
        "word-break: break-word",
        "user-select: text",
        "line-height: 1.5",
      ].join("; ");
      overlay.appendChild(body);

      document.body.appendChild(overlay);
      this.__overlay = overlay;
      this.__activeRowIndex = rowInfo.row;

      // Close when clicking outside
      this.__dismissHandler = function(e) {
        if (!overlay.contains(e.target)) {
          self.__closeOverlay();
        }
      };
      setTimeout(function() {
        document.addEventListener("mousedown", self.__dismissHandler, true);
      }, 0);

      // Close on scroll since the fixed position becomes stale
      this.__scrollDismissHandler = function() {
        self.__closeOverlay();
      };
      document.addEventListener("scroll", this.__scrollDismissHandler, true);
    },

    // overridden
    updateDataRowElement: function(rowInfo, rowElem) {
      this.base(arguments, rowInfo, rowElem);

      const self = this;
      const rowIndex = rowInfo.row;
      rowElem.style.cursor = "pointer";
      rowElem.onclick = function() {
        if (self.__activeRowIndex === rowIndex) {
          self.__closeOverlay();
        } else {
          self.__showOverlay(rowElem, rowInfo);
        }
      };
    }
  }
});
