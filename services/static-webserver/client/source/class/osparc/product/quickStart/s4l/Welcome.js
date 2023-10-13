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

qx.Class.define("osparc.product.quickStart.s4l.Welcome", {
  extend: osparc.ui.window.SingletonWindow,

  construct: function() {
    this.base(arguments, "s4l-welcome", this.tr("Welcome to Sim4Life"));

    this.set({
      layout: new qx.ui.layout.VBox(20),
      contentPadding: 15,
      modal: true,
      width: 500,
      height: 500,
      showMaximize: false,
      showMinimize: false
    });

    this.__buildLayout();
  },

  members: {
    __buildLayout: function() {
      const content = this.__createContent();
      this.add(content, {
        flex: 1
      });

      const footer = this.__createFooter();
      this.add(footer);
    },

    __createContent: function() {
      const content = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));

      const introTitle = this.tr("Experience Most Advanced Simulations – All In The Cloud");
      const intro1 = osparc.product.quickStart.Utils.createLabel(introTitle);
      intro1.set({
        font: "text-16"
      });
      content.add(intro1);

      const welcomeText = this.tr("Welcome onboard ") + osparc.utils.Utils.capitalize(osparc.auth.Data.getInstance().getUserName()) + ",";
      const welcome = osparc.product.quickStart.Utils.createLabel(welcomeText);
      content.add(welcome);

      const introText = this.tr("\
        Sim4Life is a revolutionary simulation platform, combining computable human phantoms with the most powerful physics solvers and the most advanced tissue models, for directly analyzing biological real-world phenomena and complex technical devices in a validated biological and anatomical environment.\
        <br>\
        <br>\
        In order to facilitate the introduction to the platform, we have some Guided Tours that can be found under the User Menu.\
        <br>\
        <br>\
        For more specific technical information, please refer to the Manuals on the Navigation Bar.\
      ");
      const intro2 = osparc.product.quickStart.Utils.createLabel(introText);
      content.add(intro2);

      content.add(new qx.ui.core.Spacer(null, 20));

      const logo = new osparc.ui.basic.Logo().set({
        width: 260,
        height: 110
      });
      content.add(logo);

      content.add(new qx.ui.core.Spacer(null, 20));

      return content;
    },

    __createFooter: function() {
      const footer = new qx.ui.container.Composite(new qx.ui.layout.HBox(10)).set({
        alignX: "center"
      });

      const footerItems = this.__getFooterItems();
      footerItems.forEach((footerItem, idx) => {
        footer.add(footerItem);
        if (idx !== footerItems.length-1) {
          footer.add(new qx.ui.core.Widget().set({
            maxHeight: 15
          }), {
            flex: 1
          });
        }
      });

      return footer;
    },

    __getFooterItems: function() {
      const footerItems = [];

      const docLink = new qx.ui.basic.Label().set({
        visibility: "excluded",
        textAlign: "center",
        rich : true
      });
      const manuals = osparc.store.Support.getManuals();
      if (manuals.length > 0) {
        const color = qx.theme.manager.Color.getInstance().resolve("text");
        docLink.setValue(`<a href=${manuals[0].url} style='color: ${color}' target='_blank'>Documentation</a>`);
        docLink.show();
      }
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

      const dontShowCB = osparc.product.quickStart.Utils.createDontShowAgain("s4lDontShowQuickStart");
      footerItems.push(dontShowCB);

      return footerItems;
    }
  }
});
