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
 * Singleton that manages a stack of card-style flash messages.
 * Each message appears below a target widget as an elevated card with a coin icon,
 * a brand-colored left accent and a soft shadow. Cards slide and fade in/out, and only
 * the topmost card shows an arrow pointing up to the anchor.
 */
qx.Class.define("osparc.desktop.credits.CreditsFlashMessage", {
  extend: qx.core.Object,
  type: "singleton",

  construct: function() {
    this.base(arguments);

    this.__activeMessages = [];
    this.__pendingMessages = [];
  },

  statics: {
    AUTO_DISMISS_MS: 5000,
    MAX_VISIBLE_MESSAGES: 4,
    ANIMATION_MS: 220,
  },

  members: {
    __activeMessages: null,
    __pendingMessages: null,
    __container: null,

    /**
     * Show a flash message anchored below the given widget.
     *
     * @param {String} message Text to display in the card
     * @param {qx.ui.core.Widget} anchor Widget to position the card below
     */
    addMessage: function(message, anchor) {
      const container = this.__getContainer();
      const color = qx.theme.manager.Color.getInstance().resolve("strong-main");

      // Keep at most MAX_VISIBLE_MESSAGES entries: queue the rest and show them
      // as slots free up (see __dismissMessage).
      if (this.__activeMessages.length >= this.self().MAX_VISIBLE_MESSAGES) {
        this.__pendingMessages.push({ message, anchor });
        return;
      }

      // Arrow (only visible on the topmost card)
      const arrowWrapper = this.__createArrow();
      container.add(arrowWrapper);

      // Card: message
      const card = new qx.ui.container.Composite(new qx.ui.layout.HBox(8).set({
        alignY: "middle",
      })).set({
        paddingTop: 10,
        paddingBottom: 10,
        paddingLeft: 14,
        paddingRight: 16,
        backgroundColor: "background-main",
        alignX: "right",
        allowGrowX: false,
      });
      card.getContentElement().setStyles({
        "border-left": "4px solid " + color,
        "border-radius": "4px",
        "box-shadow": "0 6px 18px rgba(0, 0, 0, 0.28)",
      });

      const label = new qx.ui.basic.Label(message).set({
        font: "text-14",
        rich: true,
        wrap: false,
        alignY: "middle",
      });
      label.getContentElement().setStyles({
        "white-space": "nowrap",
      });
      // Measure the text so the label stays on a single line
      const font = qx.theme.manager.Font.getInstance().resolve("text-14");
      const textSize = qx.bom.Label.getTextSize(message, font.getStyles());
      label.setWidth(textSize.width);
      card.add(label);

      container.add(card);

      const entry = { arrowWrapper, card };
      this.__activeMessages.push(entry);

      this.__updateArrowVisibility();
      this.__positionContainer(anchor);
      this.__animateIn(arrowWrapper);
      this.__animateIn(card);

      // Auto-dismiss
      qx.event.Timer.once(() => this.__dismissMessage(entry, anchor), this, this.self().AUTO_DISMISS_MS);

      container.show();
    },

    __createArrow: function() {
      const bgColor = qx.theme.manager.Color.getInstance().resolve("background-main");
      const arrowWrapper = new qx.ui.core.Widget().set({
        height: 7,
        width: 16,
        allowGrowX: false,
        allowGrowY: false,
        alignX: "right",
        marginRight: 6,
      });
      arrowWrapper.setUserData("isArrow", true);
      arrowWrapper.addListenerOnce("appear", () => {
        const dom = arrowWrapper.getContentElement().getDomElement();
        if (dom) {
          dom.style.position = "relative";
          dom.style.overflow = "visible";
          // A clean solid triangle (CSS borders) pointing up, in the card's background
          // color, sitting flush against the top card.
          dom.innerHTML = `<div style="position:absolute;bottom:-1px;right:0;width:0;height:0;border-left:8px solid transparent;border-right:8px solid transparent;border-bottom:8px solid ${bgColor}"></div>`;
        }
      });
      return arrowWrapper;
    },

    __animateIn: function(widget) {
      const apply = () => {
        const dom = widget.getContentElement().getDomElement();
        if (!dom) {
          return;
        }
        dom.style.opacity = "0";
        dom.style.transform = "translateY(-8px)";
        // force reflow so the transition runs from the initial state
        void dom.offsetHeight;
        dom.style.transition = `opacity ${this.self().ANIMATION_MS}ms ease, transform ${this.self().ANIMATION_MS}ms ease`;
        dom.style.opacity = "1";
        dom.style.transform = "translateY(0)";
      };
      if (widget.getContentElement().getDomElement()) {
        apply();
      } else {
        widget.addListenerOnce("appear", apply);
      }
    },

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

    __dismissMessage: function(entry, anchor) {
      const container = this.__getContainer();
      const idx = this.__activeMessages.indexOf(entry);
      if (idx === -1) {
        // already dismissed
        return;
      }
      this.__activeMessages.splice(idx, 1);

      const cleanup = () => {
        container.remove(entry.arrowWrapper);
        container.remove(entry.card);
        entry.arrowWrapper.dispose();
        entry.card.dispose();

        this.__updateArrowVisibility();
        this.__positionContainer(anchor);

        // Hide container if empty
        if (this.__activeMessages.length === 0) {
          container.exclude();
        }

        // A slot freed up: show the next queued message, if any.
        if (this.__pendingMessages.length) {
          const next = this.__pendingMessages.shift();
          this.addMessage(next.message, next.anchor);
        }
      };

      // Fade + slide out, then remove
      const cardDom = entry.card.getContentElement().getDomElement();
      const arrowDom = entry.arrowWrapper.getContentElement().getDomElement();
      [cardDom, arrowDom].forEach(dom => {
        if (dom) {
          dom.style.transition = `opacity ${this.self().ANIMATION_MS}ms ease, transform ${this.self().ANIMATION_MS}ms ease`;
          dom.style.opacity = "0";
          dom.style.transform = "translateY(-8px)";
        }
      });
      if (cardDom) {
        qx.event.Timer.once(cleanup, this, this.self().ANIMATION_MS);
      } else {
        cleanup();
      }
    },
  }
});
