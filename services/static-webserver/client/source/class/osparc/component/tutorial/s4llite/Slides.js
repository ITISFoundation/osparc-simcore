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
    _getSlides: function() {
      return [
        new osparc.component.tutorial.s4llite.Welcome(),
        new osparc.component.tutorial.s4llite.Projects(),
        new osparc.component.tutorial.s4llite.Tutorials(),
        new osparc.component.tutorial.s4llite.S4LLite()
      ];
    },
    // overriden
    _getFooterItems: function() {
      const footerItems = [];

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
      footerItems.push(docLink);

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
      footerItems.push(licenseLink);

      const dontShowCB = new qx.ui.form.CheckBox(this.tr("Don't show again")).set({
        value: osparc.utils.Utils.localCache.getLocalStorageItem("s4lliteDontShowQuickStart") === "true"
      });
      dontShowCB.addListener("changeValue", e => {
        const dontShow = e.getData();
        osparc.utils.Utils.localCache.setLocalStorageItem("s4lliteDontShowQuickStart", Boolean(dontShow));
      });
      footerItems.push(dontShowCB);

      return footerItems;
    }
  }
});
