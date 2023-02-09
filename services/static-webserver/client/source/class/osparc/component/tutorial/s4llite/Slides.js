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
        new osparc.component.tutorial.s4llite.Dashboard(),
        new osparc.component.tutorial.s4llite.S4LLiteSpecs(),
        new osparc.component.tutorial.s4llite.S4LLiteUI()
      ];
    },
    // overriden
    _getFooterItems: function() {
      const footerItems = [];

      const videoText = "<a href=https://www.youtube.com/@zurichmedtechag2809 style='color: white' target='_blank'>S4L lite video</a>";
      const videoLabel = new qx.ui.basic.Label(videoText).set({
        textAlign: "center",
        rich : true
      });
      footerItems.push(videoLabel);

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

      const dontShowCB = osparc.component.tutorial.Utils.createDontShowAgain("s4lliteDontShowQuickStart");
      footerItems.push(dontShowCB);

      return footerItems;
    }
  }
});
