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

  statics: {
    footerLinks: function() {
      const footerLinks = [];

      const videoText = "<a href=https://youtu.be/-ZE6yOJ3ipw style='color: white' target='_blank'>TIP video</a>";
      const videoLabel = new qx.ui.basic.Label(videoText).set({
        textAlign: "center",
        rich : true
      });
      footerLinks.push(videoLabel);

      const manualsLabel = new qx.ui.basic.Label().set({
        visibility: "excluded",
        textAlign: "center",
        rich : true
      });
      const manuals = osparc.store.Support.getManuals();
      if (manuals.length > 0) {
        manualsLabel.setValue(`<a href=${manuals[0].url} style='color: white' target='_blank'>Documentation</a>`);
        manualsLabel.show();
      }
      footerLinks.push(manualsLabel);

      const licenseText = "<a href=https://itis.swiss/meta-navigation/privacy-policy/ style='color: white' target='_blank'>Privacy Policy</a>";
      const licenseLabel = new qx.ui.basic.Label(licenseText).set({
        textAlign: "center",
        rich : true
      });
      footerLinks.push(licenseLabel);

      return footerLinks;
    }
  },

  members: {
    // overriden
    _getSlides: function() {
      return [
        new osparc.product.quickStart.ti.Welcome(),
        new osparc.product.quickStart.ti.Dashboard(),
        new osparc.product.quickStart.ti.ElectrodeSelector(),
        new osparc.product.quickStart.ti.PostPro(),
        new osparc.product.quickStart.ti.S4LPostPro(),
        new osparc.product.quickStart.ti.MoreInformation()
      ];
    },

    // overriden
    _getFooterItems: function() {
      const footerItems = this.self().footerLinks();

      const dontShowCB = osparc.product.quickStart.Utils.createDontShowAgain("tiDontShowQuickStart");
      footerItems.push(dontShowCB);

      return footerItems;
    }
  }
});
