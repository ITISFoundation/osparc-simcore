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
 * Only the topmost message in the stack shows the arrow.
 */
qx.Class.define("osparc.desktop.credits.CreditsFlashMessage", {
  extend: qx.ui.core.Widget,

  /**
   * @param {String} message Text to display in the bubble
   */
  construct: function(message) {
    this.base(arguments);

    this.__message = message;
  },

  statics: {
    AUTO_DISMISS_MS: 5000,
    __activeMessages: [],
    __container: null,
    __arrowEl: null,

    __getContainer: function() {
      if (!this.__container) {
        this.__container = new qx.ui.container.Composite(new qx.ui.layout.VBox(4)).set({
          zIndex: osparc.utils.Utils.FLOATING_Z_INDEX,
        });
        const root = qx.core.Init.getApplication().getRoot();
        root.add(this.__container);
      }
      return this.__container;
    },

    __positionContainer: function(anchor) {
      if (!anchor || !anchor.getBounds()) {
        return;
      }
      const container = this.__getContainer();
      const bounds = osparc.utils.Utils.getBounds(anchor);
      const baseTop = bounds.top + bounds.height + 4;
      const anchorCenter = bounds.left + Math.round(bounds.width / 2);

      // Position after a brief delay to get container width
      qx.event.Timer.once(() => {
        const containerBounds = container.getBounds();
        const containerWidth = containerBounds ? containerBounds.width : 250;
        // Align so the arrow (16px from right edge) points at anchor center
        const left = anchorCenter - containerWidth + 16;
        container.setLayoutProperties({
          left: Math.max(0, left),
          top: baseTop,
        });
      }, this, 30);
    },

    __updateArrowVisibility: function() {
      const container = this.__getContainer();
      const children = container.getChildren();
      for (let i = 0; i < children.length; i++) {
        const child = children[i];
        if (child.getUserData && child.getUserData("isArrow")) {
          child.setVisibility(i === 0 ? "visible" : "excluded");
        }
      }
    },

    addMessage: function(message, anchor) {
      const container = this.__getContainer();
      const color = qx.theme.manager.Color.getInstance().resolve("strong-main");
      const bgColor = qx.theme.manager.Color.getInstance().resolve("background-main");

      // Arrow (only visible on the first message group)
      const arrowWrapper = new qx.ui.core.Widget().set({
        height: 9,
        width: 16,
        allowGrowX: false,
        allowGrowY: false,
        alignX: "right",
        marginRight: 4,
      });
      arrowWrapper.setUserData("isArrow", true);
      arrowWrapper.addListenerOnce("appear", () => {
        const dom = arrowWrapper.getContentElement().getDomElement();
        if (dom) {
          dom.style.position = "relative";
          dom.style.overflow = "visible";
          dom.innerHTML = `<div style="position:absolute;top:0;left:0;width:0;height:0;border-left:8px solid transparent;border-right:8px solid transparent;border-bottom:9px solid ${color}"></div><div style="position:absolute;top:2px;left:1px;width:0;height:0;border-left:7px solid transparent;border-right:7px solid transparent;border-bottom:8px solid ${bgColor}"></div>`;
        }
      });
      container.add(arrowWrapper);

      // Message bubble
      const bubble = new qx.ui.basic.Label(message).set({
        font: "text-14",
        padding: 8,
        backgroundColor: "background-main",
        alignX: "right",
      });
      bubble.getContentElement().setStyles({
        "border": "1px solid " + color,
        "border-radius": "4px",
        "white-space": "nowrap",
      });
      container.add(bubble);

      const entry = { arrowWrapper, bubble };
      this.__activeMessages.push(entry);

      this.__updateArrowVisibility();
      this.__positionContainer(anchor);

      // Auto-dismiss
      qx.event.Timer.once(() => {
        const idx = this.__activeMessages.indexOf(entry);
        if (idx > -1) {
          this.__activeMessages.splice(idx, 1);
        }
        container.remove(arrowWrapper);
        container.remove(bubble);
        arrowWrapper.dispose();
        bubble.dispose();

        this.__updateArrowVisibility();
        this.__positionContainer(anchor);

        // Hide container if empty
        if (this.__activeMessages.length === 0) {
          container.exclude();
        }
      }, this, this.AUTO_DISMISS_MS);

      container.show();
    },
  },

  members: {
    __message: null,

    /**
     * Show the flash message anchored below the given widget.
     *
     * @param {qx.ui.core.Widget} anchor Widget to position below
     */
    showBelow: function(anchor) {
      this.self().addMessage(this.__message, anchor);
    },
  }
});
