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
        this.__container = new qx.ui.container.Composite(new qx.ui.layout.VBox(0)).set({
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

      // Anchor by the RIGHT edge so the stack never shifts horizontally when
      // message widths change (the credits button is fixed at the top-right).
      // The arrow sits ~12px from the container's right edge; align it under the anchor center.
      const root = qx.core.Init.getApplication().getRoot();
      const rootBounds = root.getBounds();
      const rootWidth = rootBounds ? rootBounds.width : (bounds.left + bounds.width);
      const anchorCenter = bounds.left + Math.round(bounds.width / 2);
      const right = rootWidth - anchorCenter - 12;

      container.setLayoutProperties({
        right: Math.max(0, right),
        top: baseTop,
      });
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

    __updateBubbleMargins: function() {
      // Overlap borders between adjacent bubbles, but keep the last bubble's bottom border intact
      const messages = this.__activeMessages;
      for (let i = 0; i < messages.length; i++) {
        const isLast = (i === messages.length - 1);
        messages[i].bubble.setMarginBottom(isLast ? 0 : -1);
      }
    },

    addMessage: function(message, anchor) {
      const container = this.__getContainer();
      const color = qx.theme.manager.Color.getInstance().resolve("strong-main");
      const bgColor = qx.theme.manager.Color.getInstance().resolve("background-main");

      // Arrow (only visible on the first message)
      const arrowWrapper = new qx.ui.core.Widget().set({
        height: 8,
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
          // A 45deg-rotated square whose top+left borders form the arrow outline.
          // Its background covers the bubble's top border underneath, so no line shows.
          dom.innerHTML = `<div style="position:absolute;top:3px;right:4px;width:11px;height:11px;background:${bgColor};border-top:1px solid ${color};border-left:1px solid ${color};transform:rotate(45deg)"></div>`;
        }
      });
      container.add(arrowWrapper);

      // Message bubble
      const bubble = new qx.ui.basic.Label(message).set({
        font: "text-14",
        paddingTop: 10,
        paddingBottom: 10,
        paddingLeft: 12,
        paddingRight: 12,
        backgroundColor: "background-main",
        rich: true,
        wrap: false,
        alignX: "right",
        allowGrowX: false,
      });
      bubble.getContentElement().setStyles({
        "border": "1px solid " + color,
        "border-radius": "4px",
        "white-space": "nowrap",
      });
      // Measure the text so the bubble sizes to a single line
      const font = qx.theme.manager.Font.getInstance().resolve("text-14");
      const textSize = qx.bom.Label.getTextSize(message, font.getStyles());
      bubble.setWidth(textSize.width + 24 + 2); // padding (12*2) + border (1*2)
      container.add(bubble);

      const entry = { arrowWrapper, bubble };
      this.__activeMessages.push(entry);

      this.__updateArrowVisibility();
      this.__updateBubbleMargins();
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
        this.__updateBubbleMargins();
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
