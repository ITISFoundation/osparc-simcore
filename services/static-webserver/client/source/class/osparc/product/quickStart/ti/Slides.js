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

qx.Class.define("osparc.product.quickStart.ti.Slides", {
  extend: osparc.product.quickStart.SlidesBase,

  construct: function() {
    this.base(arguments, "ti-slides", this.tr("Quick Start"));
  },

  members: {
    // overriden
    _getSlides: function() {
      return [
        new osparc.product.quickStart.ti.Welcome(),
        new osparc.product.quickStart.ti.Dashboard(),
        new osparc.product.quickStart.ti.ElectrodeSelector(),
        new osparc.product.quickStart.ti.PostPro(),
        new osparc.product.quickStart.ti.S4LPostPro()
      ];
    },

    // overriden
    _getFooterItems: function() {
      const footerItems = [];

      const videoText = "<a href=https://youtu.be/-ZE6yOJ3ipw style='color: white' target='_blank'>TIP video</a>";
      const videoLabel = new qx.ui.basic.Label(videoText).set({
        textAlign: "center",
        rich : true
      });
      footerItems.push(videoLabel);

      const manualsLabel = new qx.ui.basic.Label().set({
        visibility: "excluded",
        textAlign: "center",
        rich : true
      });
      const manuals = osparc.store.Support.getManuals();
      if (manuals && manuals.length > 0) {
        manualsLabel.setValue(`<a href=${manuals[0].url} style='color: white' target='_blank'>Documentation</a>`);
        manualsLabel.show();
      }
      footerItems.push(manualsLabel);

      const licenseText = "<a href=https://itis.swiss/meta-navigation/privacy-policy/ style='color: white' target='_blank'>Privacy Policy</a>";
      const licenseLabel = new qx.ui.basic.Label(licenseText).set({
        allowGrowX: true,
        textAlign: "center",
        rich : true
      });
      footerItems.push(licenseLabel);

      const dontShowCB = osparc.product.quickStart.Utils.createDontShowAgain("tiDontShowQuickStart");
      footerItems.push(dontShowCB);

      return footerItems;
    }
  }
});
