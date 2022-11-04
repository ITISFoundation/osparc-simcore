
qx.Class.define("osparc.navigation.Manuals", {
  type: "static",

  statics: {
    getLicenseLink: function() {
      let licenseLink = null;
      const productName = osparc.utils.Utils.getProductName();
      switch (productName) {
        case "osparc":
        case "s4l":
        case "s4llight":
          licenseLink = "http://docs.osparc.io/#/docs/support/license";
          break;
        case "tis":
          licenseLink = "https://itisfoundation.github.io/ti-planning-tool-manual/#/docs/support/license";
          break;
      }
      return licenseLink;
    },

    getManuals: function(statics) {
      const productName = osparc.utils.Utils.getProductName();
      const manualUrlKey = productName + "ManualUrl";
      const manualExtraUrlKey = productName + "ManualExtraUrl";
      const manuals = [];
      switch (productName) {
        case "osparc":
        case "s4l":
        case "s4llight":
          manuals.push({
            label: qx.locale.Manager.tr("User Manual"),
            icon: "@FontAwesome5Solid/book/22",
            url: statics[manualUrlKey]
          });
          if (osparc.utils.Utils.isInZ43() && statics && manualExtraUrlKey in statics) {
            manuals.push({
              label: qx.locale.Manager.tr("Z43 Manual"),
              icon: "@FontAwesome5Solid/book-medical/22",
              url: statics[manualExtraUrlKey]
            });
          }
          break;
        case "tis":
          manuals.push({
            label: qx.locale.Manager.tr("TI Planning Tool Manual"),
            icon: "@FontAwesome5Solid/book/22",
            url: statics[manualUrlKey]
          });
          break;
      }

      return manuals;
    },

    addFeedbackButtonsToMenu: function(menu, statics) {
      const newGHIssueBtn = new qx.ui.menu.Button(qx.locale.Manager.tr("Issue in GitHub"));
      newGHIssueBtn.addListener("execute", () => osparc.navigation.UserMenuButton.openGithubIssueInfoDialog(), this);
      menu.add(newGHIssueBtn);

      if (osparc.utils.Utils.isInZ43()) {
        const newFogbugzIssueBtn = new qx.ui.menu.Button(qx.locale.Manager.tr("Issue in Fogbugz"));
        newFogbugzIssueBtn.addListener("execute", () => osparc.navigation.UserMenuButton.openFogbugzIssueInfoDialog(), this);
        menu.add(newFogbugzIssueBtn);
      }

      const feedbackAnonBtn = new qx.ui.menu.Button(qx.locale.Manager.tr("Anonymous feedback"));
      feedbackAnonBtn.addListener("execute", () => {
        if (statics.osparcFeedbackFormUrl) {
          window.open(statics.osparcFeedbackFormUrl);
        }
      });
      menu.add(feedbackAnonBtn);
    }
  }
});
