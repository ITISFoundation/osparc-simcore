/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.product.quickStart.s4l.Slides", {
  extend: osparc.product.quickStart.SlidesBase,

  construct: function() {
    this.base(arguments, "s4l-slides", this.tr("Quick Start"));
  },

  members: {
    _getSlides: function() {
      return [
        new osparc.product.quickStart.s4l.Welcome()
      ];
    },
    // overriden
    _getFooterItems: function() {
      const footerItems = [];

      const docLink = new qx.ui.basic.Label().set({
        visibility: "excluded",
        textAlign: "center",
        rich : true
      });
      osparc.store.Support.getManuals()
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
        textAlign: "center",
        rich : true
      });
      osparc.store.Support.getLicenseURL()
        .then(licenseUrl => {
          const color = qx.theme.manager.Color.getInstance().resolve("text");
          const textLink = `<a href=${licenseUrl} style='color: ${color}' target='_blank'>Licensing</a>`;
          licenseLink.setValue(textLink);
          licenseLink.show();
        });
      footerItems.push(licenseLink);

      const dontShowCB = osparc.product.quickStart.Utils.createDontShowAgain("s4lliteDontShowQuickStart");
      footerItems.push(dontShowCB);

      return footerItems;
    }
  }
});
