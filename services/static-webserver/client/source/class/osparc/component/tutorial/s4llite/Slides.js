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
  extend: osparc.component.tutorial.SlidesBase,

  construct: function() {
    this.base(arguments, "s4llite-slides", this.tr("Quick Start"));
  },

  members: {
    _createStack: function() {
      const stack = new qx.ui.container.Stack();
      [
        new osparc.component.tutorial.s4llite.Welcome(),
        new osparc.component.tutorial.s4llite.Projects(),
        new osparc.component.tutorial.s4llite.Tutorials(),
        new osparc.component.tutorial.s4llite.S4LLite()
      ].forEach(slide => {
        const slideContainer = new qx.ui.container.Scroll();
        slideContainer.add(slide);
        stack.add(slideContainer);
      });
      return stack;
    },

    _createFooter: function() {
      const footer = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
        alignX: "center"
      }));

      const docLink = new qx.ui.basic.Label().set({
        visibility: "excluded",
        allowGrowX: true,
        textAlign: "center",
        rich : true
      });
      osparc.navigation.Manuals.getManuals()
        .then(manuals => {
          if (manuals.length > 0) {
            const color = qx.theme.manager.Color.getInstance().resolve("text");
            docLink.setValue(`<a href=${manuals[0].url} style='color: ${color}' target='_blank'>Documentation</a>`);
          }
          docLink.show();
        });
      footer.add(docLink, {
        flex: 1
      });

      const licenseLink = new qx.ui.basic.Label().set({
        visibility: "excluded",
        allowGrowX: true,
        textAlign: "center",
        rich : true
      });
      osparc.navigation.Manuals.getLicenseURL()
        .then(licenseUrl => {
          const color = qx.theme.manager.Color.getInstance().resolve("text");
          const textLink = `<a href=${licenseUrl} style='color: ${color}' target='_blank'>Licensing</a>`;
          licenseLink.setValue(textLink);
          licenseLink.show();
        });
      footer.add(licenseLink, {
        flex: 1
      });

      const dontShowCB = new qx.ui.form.CheckBox(this.tr("Don't show again")).set({
        value: osparc.utils.Utils.localCache.getLocalStorageItem("s4lliteDontShowQuickStart") === "true"
      });
      dontShowCB.addListener("changeValue", e => {
        const dontShow = e.getData();
        osparc.utils.Utils.localCache.setLocalStorageItem("s4lliteDontShowQuickStart", Boolean(dontShow));
      });
      footer.add(dontShowCB, {
        flex: 1
      });

      return footer;
    }
  }
});
