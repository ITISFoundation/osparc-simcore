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

qx.Class.define("osparc.component.tutorial.ti.Slides", {
  extend: osparc.component.tutorial.SlidesBase,

  construct: function() {
    this.base(arguments, "ti-slides", this.tr("Quick Start"));
  },

  members: {
    // overriden
    _createStack: function() {
      const stack = new qx.ui.container.Stack();
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

    // overriden
    _createFooter: function() {
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
        value: osparc.utils.Utils.localCache.getLocalStorageItem("tiDontShowQuickStart") === "true",
        allowGrowX: true,
        alignX: "center"
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
