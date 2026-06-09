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
  },

  members: {
    __buildLayout: function(message) {
      const color = qx.theme.manager.Color.getInstance().resolve("strong-main");

      // Arrow pointing up
      const arrow = new qx.ui.core.Widget().set({
        width: 0,
        height: 0,
        allowGrowX: false,
        alignX: "right",
        marginRight: 12,
      });
      arrow.getContentElement().setStyles({
        "width": "0",
        "height": "0",
        "border-left": "8px solid transparent",
        "border-right": "8px solid transparent",
        "border-bottom": "8px solid",
        "border-bottom-color": color,
      });
      this.add(arrow);

      // Message bubble
      const bubble = new qx.ui.basic.Label(message).set({
        font: "text-14",
        padding: 8,
        backgroundColor: "background-main",
      });
      bubble.getContentElement().setStyles({
        "border": "2px solid " + color,
        "border-radius": "6px",
      });
      this.add(bubble);
    },

    /**
     * Show the flash message anchored below the given widget.
     * Auto-dismisses after the configured duration.
     *
     * @param {qx.ui.core.Widget} anchor Widget to position below
     */
    showBelow: function(anchor) {
      const root = qx.core.Init.getApplication().getRoot();
      root.add(this);

      const position = () => {
        const bounds = osparc.utils.Utils.getBounds(anchor);
        this.setLayoutProperties({
          left: bounds.left + bounds.width - 200,
          top: bounds.top + bounds.height + 4,
        });
      };

      if (anchor.getBounds()) {
        position();
      } else {
        anchor.addListenerOnce("appear", () => position());
      }

      // Auto-dismiss
      qx.event.Timer.once(() => {
        if (root.indexOf(this) > -1) {
          root.remove(this);
          this.dispose();
        }
      }, this, this.self().AUTO_DISMISS_MS);
    },
  }
});
