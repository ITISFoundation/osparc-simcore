
qx.Class.define("osparc.navigation.Manuals", {
  type: "static",

  statics: {
    getLicenseLink: function() {
      let licenseLink = null;
      const productName = osparc.utils.Utils.getProductName();
      switch (productName) {
        case "osparc":
        case "s4l":
        case "s4llite":
          licenseLink = "http://docs.osparc.io/#/docs/support/license";
          break;
        case "tis":
          licenseLink = "https://itisfoundation.github.io/ti-planning-tool-manual/#/docs/support/license";
          break;
      }
      return licenseLink;
    },

    getManuals: function() {
      return new Promise(resolve => {
        osparc.store.VendorInfo.getInstance().getManuals()
          .then(manuals => resolve(manuals));
      });
    },

    __openGithubIssueInfoDialog: function() {
      const issueConfirmationWindow = new osparc.ui.window.Dialog("Information", null,
        qx.locale.Manager.tr("To create an issue in GitHub, you must have an account in GitHub and be already logged-in.")
      );
      const contBtn = new qx.ui.form.Button(qx.locale.Manager.tr("Continue"), "@FontAwesome5Solid/external-link-alt/12");
      contBtn.addListener("execute", () => {
        window.open(osparc.utils.issue.Github.getNewIssueUrl());
        issueConfirmationWindow.close();
      }, this);
      const loginBtn = new qx.ui.form.Button(qx.locale.Manager.tr("Log in in GitHub"), "@FontAwesome5Solid/external-link-alt/12");
      loginBtn.addListener("execute", () => window.open("https://github.com/login"), this);
      issueConfirmationWindow.addButton(contBtn);
      issueConfirmationWindow.addButton(loginBtn);
      issueConfirmationWindow.addCancelButton();
      issueConfirmationWindow.open();
    },

    __openFogbugzIssueInfoDialog: function() {
      const issueConfirmationWindow = new osparc.ui.window.Dialog("Information", null,
        qx.locale.Manager.tr("To create an issue in Fogbugz, you must have an account in Fogbugz and be already logged-in.")
      );
      const contBtn = new qx.ui.form.Button(qx.locale.Manager.tr("Continue"), "@FontAwesome5Solid/external-link-alt/12");
      contBtn.addListener("execute", () => {
        osparc.data.Resources.get("statics")
          .then(statics => {
            const fbNewIssueUrl = osparc.utils.issue.Fogbugz.getNewIssueUrl(statics);
            if (fbNewIssueUrl) {
              window.open(fbNewIssueUrl);
              issueConfirmationWindow.close();
            }
          });
      }, this);
      const loginBtn = new qx.ui.form.Button(qx.locale.Manager.tr("Log in in Fogbugz"), "@FontAwesome5Solid/external-link-alt/12");
      loginBtn.addListener("execute", () => {
        osparc.data.Resources.get("statics")
          .then(statics => {
            if (statics && statics.osparcIssuesLoginUrl) {
              window.open(statics.osparcIssuesLoginUrl);
            }
          });
      }, this);
      issueConfirmationWindow.addButton(contBtn);
      issueConfirmationWindow.addButton(loginBtn);
      issueConfirmationWindow.addCancelButton();
      issueConfirmationWindow.open();
    },

    __openSendEmailFeedbackDialog: function(statics) {
      let email = null;
      if (osparc.utils.Utils.isProduct("s4l") && statics.s4lSupportEmail) {
        email = statics.s4lSupportEmail;
      } else if (osparc.utils.Utils.isProduct("s4llite") || statics.s4lliteSupportEmail) {
        email = statics.s4lliteSupportEmail;
      }
      if (email === null) {
        return;
      }

      const productName = osparc.utils.Utils.getProductName();
      const giveEmailFeedbackWindow = new osparc.ui.window.Dialog("Feedback", null,
        qx.locale.Manager.tr("Send us an email to:")
      );
      const color = qx.theme.manager.Color.getInstance().resolve("text");
      const textLink = `&nbsp<a href=mailto:${email}?subject=${productName} feedback" style='color: ${color}' target='_blank'>${email}</a>&nbsp`;
      const mailto = new qx.ui.basic.Label(textLink).set({
        selectable: true,
        rich : true
      });
      giveEmailFeedbackWindow.addWidget(mailto);
      giveEmailFeedbackWindow.addCancelButton().set({
        label: qx.locale.Manager.tr("Close")
      });
      giveEmailFeedbackWindow.open();
    },

    addFeedbackButtonsToMenu: function(menu, statics) {
      const newGHIssueBtn = new qx.ui.menu.Button(qx.locale.Manager.tr("Issue in GitHub"));
      newGHIssueBtn.addListener("execute", () => this.__openGithubIssueInfoDialog(), this);
      menu.add(newGHIssueBtn);

      if (osparc.utils.Utils.isInZ43()) {
        const newFogbugzIssueBtn = new qx.ui.menu.Button(qx.locale.Manager.tr("Issue in Fogbugz"));
        newFogbugzIssueBtn.addListener("execute", () => this.__openFogbugzIssueInfoDialog(), this);
        menu.add(newFogbugzIssueBtn);
      }

      if (osparc.utils.Utils.isProduct("s4l") || osparc.utils.Utils.isProduct("s4llite")) {
        const forumBtn = new qx.ui.menu.Button(qx.locale.Manager.tr("S4L Forum"));
        forumBtn.addListener("execute", () => window.open("https://forum.zmt.swiss/"), this);
        menu.add(forumBtn);

        if (statics.s4lSupportEmail || statics.s4lliteSupportEmail) {
          const giveFeedbackBtn = new qx.ui.menu.Button(qx.locale.Manager.tr("Give us Feedback"));
          giveFeedbackBtn.addListener("execute", () => this.__openSendEmailFeedbackDialog(statics), this);
          menu.add(giveFeedbackBtn);
        }
      }

      const feedbackAnonBtn = new qx.ui.menu.Button(qx.locale.Manager.tr("Anonymous feedback")).set({
        visibility: statics.osparcFeedbackFormUrl ? "visible" : "excluded"
      });
      feedbackAnonBtn.addListener("execute", () => {
        if (statics.osparcFeedbackFormUrl) {
          window.open(statics.osparcFeedbackFormUrl);
        }
      });
      menu.add(feedbackAnonBtn);
    }
  }
});
