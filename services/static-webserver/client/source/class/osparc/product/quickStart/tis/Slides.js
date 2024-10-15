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

qx.Class.define("osparc.product.quickStart.tis.Slides", {
  extend: osparc.product.quickStart.SlidesBase,

  construct: function() {
    this.base(arguments, "ti-slides", this.tr("Quick Start"));
  },

  statics: {
    footerLinks: function() {
      const footerLinks = [];

      const videoText = osparc.utils.Utils.createHTMLLink("TIP videos", "https://www.youtube.com/playlist?list=PLcJQYcVCSqDu5gXnJj-_vS_spGhZOe-jF");
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
        const manualText = osparc.utils.Utils.createHTMLLink("Documentation", manuals[0].url);
        manualsLabel.setValue(manualText);
        manualsLabel.show();
      }
      footerLinks.push(manualsLabel);

      const licenseText = osparc.utils.Utils.createHTMLLink("Privacy Policy", "https://itis.swiss/meta-navigation/privacy-policy/");
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
        new osparc.product.quickStart.tis.Welcome(),
        new osparc.product.quickStart.tis.Dashboard(),
        new osparc.product.quickStart.tis.ElectrodeSelector(),
        new osparc.product.quickStart.tis.PostPro(),
        new osparc.product.quickStart.tis.S4LPostPro(),
        new osparc.product.quickStart.tis.MoreInformation()
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
