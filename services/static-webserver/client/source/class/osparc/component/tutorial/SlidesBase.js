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

qx.Class.define("osparc.component.tutorial.SlidesBase", {
  extend: osparc.ui.window.SingletonWindow,
  type: "abstract",

  construct: function(id, caption, icon) {
    this.base(arguments, id, caption, icon);

    this.set({
      layout: new qx.ui.layout.VBox(20),
      contentPadding: 15,
      modal: true,
      width: 800,
      height: 800,
      showMaximize: false,
      showMinimize: false,
      resizable: false
    });

    const closeBtn = this.getChildControl("close-button");
    osparc.utils.Utils.setIdToWidget(closeBtn, "quickStartWindowCloseBtn");

    const arrowsLayout = this.__createArrows();
    this.add(arrowsLayout);

    const stack = this.__stack = this._createStack();
    this.add(stack, {
      flex: 1
    });

    const footer = this._createFooter();
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
        label: this.tr("Previous"),
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

      const slideCounter = this.__slideCounter = new qx.ui.basic.Label();
      arrowsLayout.add(slideCounter);

      arrowsLayout.add(new qx.ui.core.Spacer(), {
        flex: 1
      });

      const nextBtn = this.__nextBtn = new qx.ui.form.Button().set({
        label: this.tr("Next"),
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
      this.__slideCounter.setValue(`${idx+1}/${selectables.length}`);
    },

    _createStack: function() {
      throw new Error("Abstract method called!");
    },

    _createFooter: function() {
      throw new Error("Abstract method called!");
    }
  }
});
