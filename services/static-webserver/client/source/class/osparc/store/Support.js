
qx.Class.define("osparc.store.Support", {
  type: "static",

  statics: {
    getLicenseURL: function() {
      const vendor = osparc.store.VendorInfo.getVendor();
      if (vendor) {
        if ("license_url" in vendor) {
          return vendor["license_url"];
        } else if ("url" in vendor) {
          return vendor["url"];
        }
      }
      return "";
    },

    getManuals: function() {
      return osparc.store.VendorInfo.getManuals();
    },

    __getQuickStartInfo: function() {
      const quickStart = osparc.product.quickStart.Utils.getQuickStart();
      if (quickStart) {
        return {
          label: qx.locale.Manager.tr("Introduction"),
          icon: "@FontAwesome5Solid/graduation-cap/14",
          callback: () => {
            const tutorialWindow = quickStart.tutorial();
            tutorialWindow.center();
            tutorialWindow.open();
          }
        }
      }
      return null;
    },

    addQuickStartToMenu: function(menu) {
      const quickStartInfo = this.__getQuickStartInfo();
      if (quickStartInfo) {
        const qsButton = new qx.ui.menu.Button(quickStartInfo.label, quickStartInfo.icon);
        qsButton.getChildControl("label").set({
          rich: true
        });
        qsButton.addListener("execute", () => quickStartInfo.callback());
        menu.add(qsButton);
      }
    },

    getQuickStartButton: function() {
      const quickStartInfo = this.__getQuickStartInfo();
      if (quickStartInfo) {
        const qsButton = new qx.ui.form.Button(quickStartInfo.label, quickStartInfo.icon);
        qsButton.getChildControl("label").set({
          rich: true
        });
        qsButton.addListener("execute", () => quickStartInfo.callback());
        return qsButton;
      }
      return null;
    },

    __getGuidedToursInfo: function() {
      return {
        label: qx.locale.Manager.tr("Guided Tours"),
        icon: "@FontAwesome5Solid/graduation-cap/14",
      }
    },

    populateGuidedToursButton: function(button) {
      const fetchTours = osparc.product.tours.Tours.getTours();
      if (fetchTours) {
        fetchTours
          .then(tours => {
            if (tours) {
              button.show();
              button.addListener("execute", () => {
                const toursManager = new osparc.tours.Manager();
                toursManager.setTours(tours);
                toursManager.start();
              });
            }
          });
      }
    },

    addGuidedToursToMenu: function(menu) {
      const guidedToursInfo = this.__getGuidedToursInfo();
      const guidedToursButton = new qx.ui.menu.Button(guidedToursInfo.label, guidedToursInfo.icon);
      guidedToursButton.exclude();
      menu.add(guidedToursButton);
      this.populateGuidedToursButton(guidedToursButton);
    },

    getGuidedToursButton: function() {
      const guidedToursInfo = this.__getGuidedToursInfo();
      const guidedToursButton = new qx.ui.form.Button(guidedToursInfo.label, guidedToursInfo.icon);
      guidedToursButton.exclude();
      this.populateGuidedToursButton(guidedToursButton);
      return guidedToursButton;
    },

    addManualsToMenu: function(menu) {
      const manuals = osparc.store.Support.getManuals();
      const addManuals = mn => {
        manuals.forEach(manual => {
          const manualBtn = new qx.ui.menu.Button(manual.label, "@FontAwesome5Solid/book/14");
          manualBtn.getChildControl("label").set({
            rich: true
          });
          manualBtn.addListener("execute", () => window.open(manual.url), this);
          mn.add(manualBtn);
        });
      };
      if (manuals.length > 1) {
        // if there are more than 1 manuals, add them in their own menu
        const ownMenu = new qx.ui.menu.Menu().set({
          appearance: "menu-wider",
        });
        const manualsBtn = new qx.ui.menu.Button(qx.locale.Manager.tr("Manuals"), "@FontAwesome5Solid/book/14");
        manualsBtn.setMenu(ownMenu);
        menu.add(manualsBtn);
        addManuals(ownMenu);
      } else {
        addManuals(menu);
      }
    },

    getManualButtons: function() {
      const manuals = osparc.store.Support.getManuals();
      const manualButtons = [];
      manuals.forEach(manual => {
        const manualBtn = new qx.ui.form.Button(manual.label, "@FontAwesome5Solid/book/14");
        manualBtn.getChildControl("label").set({
          rich: true
        });
        manualBtn.addListener("execute", () => window.open(manual.url), this);
        manualButtons.push(manualBtn);
      });
      return manualButtons;
    },

    __getIssueInfos: function() {
      const issuesInfos = [];
      const issues = osparc.store.VendorInfo.getIssues();
      issues.forEach(issueInfo => {
        issuesInfos.push({
          label: issueInfo["label"],
          icon: "@FontAwesome5Solid/comments/14",
          callback: () => {
            const issueConfirmationWindow = new osparc.ui.window.Dialog(issueInfo["label"] + " " + qx.locale.Manager.tr("Information"), null,
              qx.locale.Manager.tr("To create an issue, you must have an account and be already logged-in.")
            );
            const continueBtn = new qx.ui.form.Button(qx.locale.Manager.tr("Continue"), "@FontAwesome5Solid/external-link-alt/14");
            continueBtn.addListener("execute", () => {
              window.open(issueInfo["new_url"]);
              issueConfirmationWindow.close();
            }, this);
            const loginBtn = new qx.ui.form.Button(qx.locale.Manager.tr("Log in in ") + issueInfo["label"], "@FontAwesome5Solid/external-link-alt/14");
            loginBtn.addListener("execute", () => window.open(issueInfo["login_url"]), this);
            issueConfirmationWindow.addButton(continueBtn);
            issueConfirmationWindow.addButton(loginBtn);
            issueConfirmationWindow.addCancelButton();
            issueConfirmationWindow.open();
          },
        });
      });
      return issuesInfos;
    },

    __getSupportInfos: function() {
      const supportInfos = [];
      const supports = osparc.store.VendorInfo.getSupports();
      supports.forEach(supportInfo => {
        const label = supportInfo["label"];
        let icon = null;
        let callback = null;
        switch (supportInfo["kind"]) {
          case "web":
            icon = "@FontAwesome5Solid/link/14";
            callback = () => window.open(supportInfo["url"]);
            break;
          case "forum":
            icon = "@FontAwesome5Solid/comments/14";
            callback = () => window.open(supportInfo["url"]);
            break;
          case "email":
            if (osparc.store.Groups.getInstance().isSupportEnabled()) {
              // if support is enabled, ignore the email option
              return;
            }
            icon = "@FontAwesome5Solid/envelope/14";
            callback = () => this.__openSendEmailFeedbackDialog(supportInfo["email"]);
            break;
        }
        supportInfos.push({
          label,
          icon,
          callback,
        });
      });
      return supportInfos;
    },

    addSupportButtonsToMenu: function(menu) {
      const issuesInfos = this.__getIssueInfos();
      issuesInfos.forEach(issueInfo => {
        const issueButton = new qx.ui.menu.Button(issueInfo.label, issueInfo.icon);
        issueButton.getChildControl("label").set({
          rich: true
        });
        issueButton.addListener("execute", issueInfo.callback, this);
        menu.add(issueButton);
      });

      const supportInfos = this.__getSupportInfos();
      if (issuesInfos.length && supportInfos.length) {
        menu.addSeparator();
      }

      supportInfos.forEach(supportInfo => {
        const supportBtn = new qx.ui.menu.Button(supportInfo.label, supportInfo.icon);
        supportBtn.getChildControl("label").set({
          rich: true
        });
        supportBtn.addListener("execute", supportInfo.callback, this);
        menu.add(supportBtn);
      });
    },

    getSupportButtons: function() {
      const buttons = [];
      const issuesInfos = this.__getIssueInfos();
      issuesInfos.forEach(issueInfo => {
        const issueButton = new qx.ui.form.Button(issueInfo.label, issueInfo.icon);
        issueButton.getChildControl("label").set({
          rich: true
        });
        issueButton.addListener("execute", issueInfo.callback, this);
        buttons.push(issueButton);
      });

      const supportInfos = this.__getSupportInfos();
      supportInfos.forEach(supportInfo => {
        const supportBtn = new qx.ui.form.Button(supportInfo.label, supportInfo.icon);
        supportBtn.getChildControl("label").set({
          rich: true
        });
        supportBtn.addListener("execute", supportInfo.callback, this);
        buttons.push(supportBtn);
      });
      return buttons;
    },

    __getReleaseInfo: function() {
      const releaseTag = osparc.utils.Utils.getReleaseTag();
      const releaseLink = osparc.utils.Utils.getReleaseLink();
      return {
        label: qx.locale.Manager.tr("What's New in") + " " + releaseTag,
        icon: "@FontAwesome5Solid/bullhorn/14",
        callback: () => { window.open(releaseLink); },
      };
    },

    addReleaseNotesToMenu: function(menu) {
      const releaseInfo = this.__getReleaseInfo();
      const releaseBtn = new qx.ui.menu.Button(releaseInfo.label, releaseInfo.icon);
      releaseBtn.addListener("execute", releaseInfo.callback, this);
      menu.add(releaseBtn);
    },

    getReleaseNotesButton: function() {
      const releaseInfo = this.__getReleaseInfo();
      const releaseBtn = new qx.ui.form.Button(releaseInfo.label, releaseInfo.icon);
      releaseBtn.addListener("execute", releaseInfo.callback, this);
      return releaseBtn;
    },

    mailToLink: function(email, subject, centered = true) {
      const color = qx.theme.manager.Color.getInstance().resolve("text");
      let textLink = `<a href="mailto:${email}?subject=${subject}" style='color: ${color}' target='_blank'>${email}</a>`;
      if (centered) {
        textLink = `<center>${textLink}</center>`
      }
      return textLink;
    },

    requestAccountLink: function(centered = true) {
      const color = qx.theme.manager.Color.getInstance().resolve("text");
      const link = window.location.origin + "/#/request-account";
      let textLink = `<a href="${link}" style='color: ${color}' target='_blank'>Request Account</a>`;
      if (centered) {
        textLink = `<center>${textLink}</center>`
      }
      return textLink;
    },

    getMailToLabel: function(email, subject) {
      const mailto = new qx.ui.basic.Label().set({
        font: "text-14",
        allowGrowX: true, // let it grow to make it easier to select
        selectable: true,
        rich: true,
      });
      if (email) {
        mailto.setValue(this.mailToLink(email, subject, false));
      }
      return mailto;
    },

    __openSendEmailFeedbackDialog: function(email) {
      const productName = osparc.product.Utils.getProductName();
      const giveEmailFeedbackWindow = new osparc.ui.window.Dialog("Feedback", null, qx.locale.Manager.tr("Please send us an email to:"));
      const mailto = this.getMailToLabel(email, productName + " feedback");
      mailto.setTextAlign("center");
      giveEmailFeedbackWindow.addWidget(mailto);
      giveEmailFeedbackWindow.open();
    },

    openInvitationRequiredDialog: function() {
      const createAccountWindow = new osparc.ui.window.Dialog("Create Account").set({
        maxWidth: 380
      });
      osparc.utils.Utils.setIdToWidget(createAccountWindow, "createAccountWindow");
      const vendor = osparc.store.VendorInfo.getVendor();
      if ("invitation_url" in vendor) {
        const displayName = osparc.store.StaticInfo.getDisplayName();
        let message = qx.locale.Manager.tr("Registration is currently only available with an invitation.");
        message += "<br>";
        message += qx.locale.Manager.tr("Please request access to ") + displayName + ":";
        message += "<br>";
        createAccountWindow.setMessage(message);
        const linkLabel = new osparc.ui.basic.LinkLabel(vendor["invitation_url"], vendor["invitation_url"]);
        createAccountWindow.addWidget(linkLabel);
      } else {
        const message = osparc.utils.Utils.createAccountMessage();
        createAccountWindow.setMessage(message);
      }
      createAccountWindow.center();
      createAccountWindow.open();
    },
  }
});
