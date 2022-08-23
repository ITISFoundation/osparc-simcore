
qx.Class.define("osparc.navigation.Manuals", {
  type: "static",

  statics: {
    getManuals: function(statics) {
      let manuals = [];
      if (statics && statics.osparcManualUrl) {
        manuals.push({
          label: qx.locale.Manager.tr("User Manual"),
          icon: "@FontAwesome5Solid/book/22",
          url: statics.osparcManualUrl
        });
      }

      if (osparc.utils.Utils.isInZ43() && statics && statics.osparcManualExtraUrl) {
        manuals.push({
          label: qx.locale.Manager.tr("Z43 Manual"),
          icon: "@FontAwesome5Solid/book-medical/22",
          url: statics.osparcManualExtraUrl
        });
      }

      if (osparc.utils.Utils.isProduct("tis") && statics && statics.tisManualUrl) {
        // "TI Planning Tool Manual" only
        manuals = [{
          label: qx.locale.Manager.tr("TI Planning Tool Manual"),
          icon: "@FontAwesome5Solid/book/22",
          url: statics.tisManualUrl
        }];
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
