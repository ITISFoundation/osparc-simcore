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
 * A speech-bubble style flash message that appears below a target widget,
 * with an arrow pointing up and a product-colored border.
 */
qx.Class.define("osparc.desktop.credits.CreditsFlashMessage", {
  extend: qx.ui.container.Composite,

  /**
   * @param {String} message Text to display in the bubble
   */
  construct: function(message) {
    this.base(arguments, new qx.ui.layout.VBox(0));

    this.set({
      zIndex: osparc.utils.Utils.FLOATING_Z_INDEX,
      allowGrowX: false,
    });

    this.__buildLayout(message);
  },

  statics: {
    AUTO_DISMISS_MS: 5000,
    __activeMessages: [],

    getActiveMessages: function() {
      return this.__activeMessages;
    },

    __repositionAll: function(anchor) {
      if (!anchor || !anchor.getBounds()) {
        return;
      }
      const bounds = osparc.utils.Utils.getBounds(anchor);
      const baseTop = bounds.top + bounds.height + 4;
      // Right edge of anchor is our alignment reference
      const anchorCenter = bounds.left + Math.round(bounds.width / 2);
      let offsetY = 0;
      for (const msg of this.__activeMessages) {
        const msgBounds = msg.getBounds();
        const msgWidth = msgBounds ? msgBounds.width : 250;
        // Position so the arrow (which is marginRight:8 + 8px half-width = ~16px from right edge) points at anchor center
        const left = anchorCenter - msgWidth + 24;
        msg.setLayoutProperties({
          left: Math.max(0, left),
          top: baseTop + offsetY,
        });
        if (msgBounds) {
          offsetY += msgBounds.height + 4;
        }
      }
    },
  },

  members: {
    __buildLayout: function(message) {
      const color = qx.theme.manager.Color.getInstance().resolve("strong-main");
      const bgColor = qx.theme.manager.Color.getInstance().resolve("background-main");

      // Arrow pointing up (outline: outer border triangle + inner bg triangle)
      const arrowWrapper = new qx.ui.core.Widget().set({
        height: 9,
        width: 16,
        allowGrowX: false,
        allowGrowY: false,
        alignX: "right",
        marginRight: 8,
      });
      arrowWrapper.addListenerOnce("appear", () => {
        const dom = arrowWrapper.getContentElement().getDomElement();
        if (dom) {
          dom.style.position = "relative";
          dom.style.overflow = "visible";
          dom.innerHTML = `<div style="position:absolute;top:0;left:0;width:0;height:0;border-left:8px solid transparent;border-right:8px solid transparent;border-bottom:9px solid ${color}"></div><div style="position:absolute;top:2px;left:1px;width:0;height:0;border-left:7px solid transparent;border-right:7px solid transparent;border-bottom:8px solid ${bgColor}"></div>`;
        }
      });
      this.add(arrowWrapper);

      // Message bubble
      const bubble = new qx.ui.basic.Label(message).set({
        font: "text-14",
        padding: 8,
        backgroundColor: "background-main",
        alignX: "right",
        allowGrowX: false,
        rich: false,
      });
      bubble.getContentElement().setStyles({
        "border": "1px solid " + color,
        "border-radius": "4px",
        "white-space": "nowrap",
      });
      this.add(bubble);
    },

    /**
     * Show the flash message anchored below the given widget.
     * Stacks below any already-visible messages.
     * Auto-dismisses after the configured duration.
     *
     * @param {qx.ui.core.Widget} anchor Widget to position below
     */
    showBelow: function(anchor) {
      const root = qx.core.Init.getApplication().getRoot();
      root.add(this);

      const activeMessages = this.self().getActiveMessages();
      activeMessages.push(this);
      this.__anchor = anchor;

      const position = () => {
        this.self().__repositionAll(anchor);
      };

      if (anchor.getBounds()) {
        // Delay slightly to allow this widget to render and get bounds
        qx.event.Timer.once(() => position(), this, 50);
      } else {
        anchor.addListenerOnce("appear", () => position());
      }

      // Auto-dismiss
      qx.event.Timer.once(() => {
        const idx = activeMessages.indexOf(this);
        if (idx > -1) {
          activeMessages.splice(idx, 1);
        }
        if (root.indexOf(this) > -1) {
          root.remove(this);
          this.dispose();
        }
        // Reposition remaining messages
        this.self().__repositionAll(anchor);
      }, this, this.self().AUTO_DISMISS_MS);
    },
  }
});
