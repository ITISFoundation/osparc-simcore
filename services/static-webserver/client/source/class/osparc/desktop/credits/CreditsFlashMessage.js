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
      let offsetY = 0;
      for (const msg of this.__activeMessages) {
        msg.setLayoutProperties({
          left: bounds.left + bounds.width - 200,
          top: baseTop + offsetY,
        });
        const msgBounds = msg.getBounds();
        if (msgBounds) {
          offsetY += msgBounds.height + 4;
        }
      }
    },
  },

  members: {
    __buildLayout: function(message) {
      const color = qx.theme.manager.Color.getInstance().resolve("strong-main");

      // Arrow pointing up
      const arrow = new qx.ui.core.Widget().set({
        height: 8,
        allowGrowX: false,
        allowGrowY: false,
        alignX: "right",
        marginRight: 12,
      });
      arrow.addListenerOnce("appear", () => {
        const el = arrow.getContentElement().getDomElement();
        if (el) {
          el.style.width = "0";
          el.style.height = "0";
          el.style.borderLeft = "8px solid transparent";
          el.style.borderRight = "8px solid transparent";
          el.style.borderBottom = "8px solid " + color;
        }
      });
      this.add(arrow);

      // Message bubble
      const bubble = new qx.ui.basic.Label(message).set({
        font: "text-14",
        padding: 8,
        backgroundColor: "background-main",
      });
      bubble.getContentElement().setStyles({
        "border": "1px solid " + color,
        "border-radius": "6px",
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
