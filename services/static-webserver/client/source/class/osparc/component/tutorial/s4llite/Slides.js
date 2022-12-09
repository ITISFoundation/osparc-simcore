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

qx.Class.define("osparc.component.tutorial.s4llite.Slides", {
  extend: osparc.ui.window.SingletonWindow,

  construct: function() {
    this.base(arguments, "ti-slides", this.tr("Quick Start"));

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

    const stack = this.__createStack();
    this.add(stack, {
      flex: 1
    });

    const footer = this.__createFooter();
    this.add(footer);

    this.__setSlideIdx(0);
  },

  statics: {
    createLabel: function(text) {
      const label = new qx.ui.basic.Label().set({
        rich: true,
        wrap: true,
        font: "text-14"
      });
      if (text) {
        label.setValue(text);
      }
      return label;
    }
  },

  members: {
    __currentIdx: null,
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

    __createStack: function() {
      const stack = this.__stack = new qx.ui.container.Stack();
      [
        new osparc.component.tutorial.ti.Welcome(),
        new osparc.component.tutorial.ti.Dashboard(),
        new osparc.component.tutorial.ti.ElectrodeSelector(),
        new osparc.component.tutorial.ti.PostPro(),
        new osparc.component.tutorial.ti.S4LPostPro()
      ].forEach(slide => {
        const slideContainer = new qx.ui.container.Scroll();
        slideContainer.add(slide);
        stack.add(slideContainer);
      });
      return stack;
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

    __createFooter: function() {
      const footer = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));

      const text1 = "<a href=https://youtu.be/-ZE6yOJ3ipw style='color: white' target='_blank'>TIP video</a>";
      const link1 = new qx.ui.basic.Label(text1).set({
        allowGrowX: true,
        textAlign: "center",
        rich : true
      });
      footer.add(link1, {
        flex: 1
      });

      const link2 = new qx.ui.basic.Label().set({
        visibility: "excluded",
        allowGrowX: true,
        textAlign: "center",
        rich : true
      });
      osparc.navigation.Manuals.getManuals()
        .then(manuals => {
          if (manuals.length > 0) {
            link2.setValue(`<a href=${manuals[0].url} style='color: white' target='_blank'>Documentation</a>`);
          }
          link2.show();
        });
      footer.add(link2, {
        flex: 1
      });

      const text3 = "<a href=https://itis.swiss/meta-navigation/privacy-policy/ style='color: white' target='_blank'>Privacy Policy</a>";
      const link3 = new qx.ui.basic.Label(text3).set({
        allowGrowX: true,
        textAlign: "center",
        rich : true
      });
      footer.add(link3, {
        flex: 1
      });

      const dontShowCB = new qx.ui.form.CheckBox(this.tr("Don't show again")).set({
        value: osparc.utils.Utils.localCache.getLocalStorageItem("tiDontShowQuickStart") === "true"
      });
      dontShowCB.addListener("changeValue", e => {
        const dontShow = e.getData();
        osparc.utils.Utils.localCache.setLocalStorageItem("tiDontShowQuickStart", Boolean(dontShow));
      });
      footer.add(dontShowCB, {
        flex: 1
      });

      return footer;
    }
  }
});
