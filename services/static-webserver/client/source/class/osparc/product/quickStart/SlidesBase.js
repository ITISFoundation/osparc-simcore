/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2022 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.product.quickStart.SlidesBase", {
  extend: osparc.ui.window.SingletonWindow,
  type: "abstract",

  construct: function(id, caption, icon) {
    this.base(arguments, id, caption, icon);

    this.set({
      layout: new qx.ui.layout.VBox(20),
      contentPadding: 15,
      modal: true,
      width: 700,
      height: 700,
      showMaximize: false,
      showMinimize: false
    });

    const closeBtn = this.getChildControl("close-button");
    osparc.utils.Utils.setIdToWidget(closeBtn, "quickStartWindowCloseBtn");

    const arrowsLayout = this.__createArrows();
    this.add(arrowsLayout);

    const stack = this.__stack = this.__createStack();
    this.add(stack, {
      flex: 1
    });

    const footer = this.__createFooter();
    this.add(footer);

    this.__setSlideIdx(0);
  },

  members: {
    __currentIdx: null,
    __slideCounter: null,
    __prevBtn: null,
    __nextBtn: null,
    __stack: null,

    __createArrows: function() {
      const arrowsLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox());

      const prevBtn = this.__prevBtn = new qx.ui.form.Button().set({
        icon: "@FontAwesome5Solid/arrow-left/20",
        allowGrowX: true,
        backgroundColor: "transparent",
        iconPosition: "left",
        alignX: "left"
      });
      prevBtn.addListener("execute", () => this.__setSlideIdx(this.__currentIdx-1), this);
      arrowsLayout.add(prevBtn);

      arrowsLayout.add(new qx.ui.core.Spacer(), {
        flex: 1
      });

      const slideCounter = this.__slideCounter = new qx.ui.container.Composite(new qx.ui.layout.HBox(2)).set({
        alignY: "middle",
        maxWidth: 160,
        maxHeight: 10
      });
      arrowsLayout.add(slideCounter);

      arrowsLayout.add(new qx.ui.core.Spacer(), {
        flex: 1
      });

      const nextBtn = this.__nextBtn = new qx.ui.form.Button().set({
        icon: "@FontAwesome5Solid/arrow-right/20",
        allowGrowX: true,
        backgroundColor: "transparent",
        iconPosition: "right",
        alignX: "right"
      });
      nextBtn.addListener("execute", () => this.__setSlideIdx(this.__currentIdx+1), this);
      arrowsLayout.add(nextBtn);

      return arrowsLayout;
    },

    __setSlideIdx: function(idx) {
      const selectables = this.__stack.getSelectables();
      if (idx > -1 && idx < selectables.length) {
        this.__currentIdx = idx;
        this.__stack.setSelection([selectables[idx]]);
        this.__prevBtn.setEnabled(idx !== 0);
        this.__nextBtn.setEnabled(idx !== selectables.length-1);
      }
      this.__slideCounter.removeAll();
      for (let i=0; i<selectables.length; i++) {
        const widget = new qx.ui.core.Widget().set({
          backgroundColor: idx === i ? "strong-main" : "text"
        });
        this.__slideCounter.add(widget, {
          flex: 1
        });
      }
    },

    __createStack: function() {
      const stack = new qx.ui.container.Stack();
      this._getSlides().forEach(slide => {
        const slideContainer = new qx.ui.container.Scroll();
        slideContainer.add(slide);
        stack.add(slideContainer);
      });
      return stack;
    },

    __createFooter: function() {
      const footer = new qx.ui.container.Composite(new qx.ui.layout.HBox(10)).set({
        alignX: "center"
      });

      const footerItems = this._getFooterItems();
      footerItems.forEach((footerItem, idx) => {
        footer.add(footerItem);
        if (idx !== footerItems.length-1) {
          footer.add(new qx.ui.core.Widget().set({
            maxHeight: 15
          }), {
            flex: 1
          });
        }
      });

      return footer;
    },

    _getSlides: function() {
      throw new Error("Abstract method called!");
    },

    _getFooterItems: function() {
      throw new Error("Abstract method called!");
    }
  }
});
