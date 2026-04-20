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
 * Row renderer for the Logger table that shows a popup with
 * the full log message, timestamp, origin, and log level when a row is clicked.
 *
 * The popup is added to the application root to avoid
 * qooxdoo table pane clipping constraints (overflow:hidden at multiple levels).
 */
qx.Class.define("osparc.ui.table.rowrenderer.PopUpLogMessage", {
  extend: qx.ui.table.rowrenderer.Default,

  construct: function(table, messageColPos) {
    this.base(arguments);

    this.__table = table;
    this.__messageColPos = messageColPos;
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
    __popup: null,
    __activeRowIndex: null,

    __closePopup: function() {
      if (this.__popup) {
        const root = qx.core.Init.getApplication().getRoot();
        if (root.indexOf(this.__popup) >= 0) {
          root.remove(this.__popup);
        }
        this.__popup.dispose();
        this.__popup = null;
      }
      this.__activeRowIndex = null;
    },

    __createBadge: function(rowData) {
      if (!rowData || rowData.logLevel == null) {
        return null;
      }
      const entry = this.self().LOG_LEVEL_INFO[String(rowData.logLevel)];
      if (!entry) {
        return null;
      }
      const badge = new qx.ui.basic.Label(entry.label).set({
        font: "text-10",
        padding: [1, 6],
        textColor: "text",
        backgroundColor: entry.themeColor,
      });
      return badge;
    },

    __showPopup: function(rowElem, rowIndex, rowData) {
      const messageDiv = rowElem.children.item(this.__messageColPos);
      if (!messageDiv) {
        return;
      }

      this.__closePopup();

      const rect = rowElem.getBoundingClientRect();

      // Container
      const popup = new qx.ui.container.Composite(new qx.ui.layout.VBox(4)).set({
        backgroundColor: "background-main-2",
        padding: 8,
        maxHeight: Math.round(window.innerHeight * 0.5),
        width: Math.round(rect.width),
        zIndex: osparc.utils.Utils.FLOATING_Z_INDEX,
        decorator: "material-textfield",
      });

      // Header
      const header = new qx.ui.container.Composite(new qx.ui.layout.HBox(8).set({
        alignY: "middle",
      }));

      // Log level badge
      const badge = this.__createBadge(rowData);
      if (badge) {
        header.add(badge);
      }

      // Timestamp
      if (rowData && rowData.timeStamp) {
        header.add(new qx.ui.basic.Label(String(rowData.timeStamp)).set({
          font: "text-11",
          textColor: "text-opa70",
        }));
      }

      // Origin
      if (rowData && rowData.label) {
        header.add(new qx.ui.basic.Label(rowData.label).set({
          font: "text-11",
          textColor: "text-opa70",
        }));
      }

      // Spacer
      header.add(new qx.ui.core.Spacer(), {
        flex: 1
      });

      // Copy button
      const copyBtn = osparc.utils.Utils.getCopyButton();
      copyBtn.addListener("execute", () => {
        const text = osparc.widget.logger.LoggerView.printRow(rowData);
        osparc.utils.Utils.copyTextToClipboard(text);
      });
      header.add(copyBtn);

      // Close button
      const closeBtn = new qx.ui.form.Button(null, "@MaterialIcons/close/12").set({
        allowGrowY: false,
        padding: 3,
        maxWidth: 20,
      });
      closeBtn.addListener("execute", () => this.__closePopup());
      header.add(closeBtn);

      popup.add(header);

      // Separator
      popup.add(new qx.ui.menu.Separator());

      // Message body (scrollable)
      const scroll = new qx.ui.container.Scroll();
      const messageLabel = new qx.ui.basic.Label(messageDiv.innerHTML).set({
        rich: true,
        selectable: true,
        wrap: true,
      });
      scroll.add(messageLabel);
      popup.add(scroll, { flex: 1 });

      // Position: anchor to row, flip above if near bottom
      const root = qx.core.Init.getApplication().getRoot();
      const viewportHeight = window.innerHeight;
      let top;
      if (rect.bottom > viewportHeight * 0.65) {
        // Place above: we'll adjust after rendering
        top = Math.max(0, Math.round(rect.top) - 200);
      } else {
        top = Math.round(rect.top);
      }
      root.add(popup, {
        left: Math.round(rect.left),
        top: top,
      });

      // Adjust position after popup is rendered and has actual height
      if (rect.bottom > viewportHeight * 0.65) {
        popup.addListenerOnce("appear", () => {
          const bounds = popup.getBounds();
          if (bounds) {
            const adjustedTop = Math.max(0, Math.round(rect.bottom) - bounds.height);
            popup.setLayoutProperties({
              left: Math.round(rect.left),
              top: adjustedTop,
            });
          }
        });
      }

      this.__popup = popup;
      this.__activeRowIndex = rowIndex;

      // Close on scroll since the fixed position becomes stale
      const scrollHandler = () => {
        this.__closePopup();
        document.removeEventListener("scroll", scrollHandler, true);
      };
      document.addEventListener("scroll", scrollHandler, true);

      // Close on click outside
      const clickHandler = e => {
        if (popup.isDisposed()) {
          document.removeEventListener("mousedown", clickHandler, true);
          return;
        }
        const popupElem = popup.getContentElement().getDomElement();
        if (popupElem && !popupElem.contains(e.target)) {
          document.removeEventListener("mousedown", clickHandler, true);
          this.__closePopup();
        }
      };
      popup.addListenerOnce("appear", () => {
        setTimeout(() => document.addEventListener("mousedown", clickHandler, true), 0);
      });
      popup.addListenerOnce("disappear", () => {
        document.removeEventListener("mousedown", clickHandler, true);
      });
    },

    // overridden
    updateDataRowElement: function(rowInfo, rowElem) {
      this.base(arguments, rowInfo, rowElem);

      const self = this;
      const rowIndex = rowInfo.row;
      // Capture rowData now — rowInfo is a shared mutable object reused across rows
      const rowData = rowInfo.rowData;
      rowElem.style.cursor = "pointer";
      rowElem.onclick = function() {
        if (self.__activeRowIndex === rowIndex) {
          self.__closePopup();
        } else {
          self.__showPopup(rowElem, rowIndex, rowData);
        }
      };
    }
  }
});
