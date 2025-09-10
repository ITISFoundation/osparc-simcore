
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

    addSupportConversationsToMenu: function(menu) {
      const supportCenterButton = new qx.ui.menu.Button().set({
        label: qx.locale.Manager.tr("Support Center"),
        icon: "@FontAwesome5Solid/question-circle/16",
      });
      supportCenterButton.addListener("execute", () => osparc.support.SupportCenter.openWindow());
      menu.add(supportCenterButton);

      const askAQuestionButton = new qx.ui.menu.Button().set({
        label: qx.locale.Manager.tr("Ask a Question"),
        icon: "@FontAwesome5Solid/comments/16",
        visibility: "excluded",
      });
      askAQuestionButton.addListener("execute", () => osparc.support.SupportCenter.openWindow("conversations"));
      menu.add(askAQuestionButton);

      const updateAskAQuestionButton = () => {
        const isSupportEnabled = osparc.store.Groups.getInstance().isSupportEnabled();
        askAQuestionButton.set({
          visibility: isSupportEnabled ? "visible" : "excluded",
        });
      }

      updateAskAQuestionButton();
      osparc.store.Groups.getInstance().addListener("changeSupportGroup", () => updateAskAQuestionButton());
    },

    __getQuickStartInfo: function() {
      const quickStart = osparc.product.quickStart.Utils.getQuickStart();
      if (quickStart) {
        return {
          label: qx.locale.Manager.tr("Quick Start"),
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

    addSupportButtonsToMenu: function(menu) {
      const issues = osparc.store.VendorInfo.getIssues();
      const supports = osparc.store.VendorInfo.getSupports();
      issues.forEach(issueInfo => {
        const label = issueInfo["label"];
        const issueButton = new qx.ui.menu.Button(label, "@FontAwesome5Solid/comments/14");
        issueButton.getChildControl("label").set({
          rich: true
        });
        issueButton.addListener("execute", () => {
          const issueConfirmationWindow = new osparc.ui.window.Dialog(label + " " + qx.locale.Manager.tr("Information"), null,
            qx.locale.Manager.tr("To create an issue, you must have an account and be already logged-in.")
          );
          const contBtn = new qx.ui.form.Button(qx.locale.Manager.tr("Continue"), "@FontAwesome5Solid/external-link-alt/14");
          contBtn.addListener("execute", () => {
            window.open(issueInfo["new_url"]);
            issueConfirmationWindow.close();
          }, this);
          const loginBtn = new qx.ui.form.Button(qx.locale.Manager.tr("Log in in ") + label, "@FontAwesome5Solid/external-link-alt/14");
          loginBtn.addListener("execute", () => window.open(issueInfo["login_url"]), this);
          issueConfirmationWindow.addButton(contBtn);
          issueConfirmationWindow.addButton(loginBtn);
          issueConfirmationWindow.addCancelButton();
          issueConfirmationWindow.open();
        }, this);
        menu.add(issueButton);
      });

      if (issues.length && supports.length) {
        menu.addSeparator();
      }

      supports.forEach(supportInfo => {
        const supportBtn = new qx.ui.menu.Button(supportInfo["label"]);
        supportBtn.getChildControl("label").set({
          rich: true
        });
        let icon = null;
        let cb = null;
        switch (supportInfo["kind"]) {
          case "web":
            icon = "@FontAwesome5Solid/link/14";
            cb = () => window.open(supportInfo["url"]);
            break;
          case "forum":
            icon = "@FontAwesome5Solid/comments/14";
            cb = () => window.open(supportInfo["url"]);
            break;
          case "email":
            icon = "@FontAwesome5Solid/envelope/14";
            cb = () => this.__openSendEmailFeedbackDialog(supportInfo["email"]);
            break;
        }
        supportBtn.setIcon(icon);
        supportBtn.addListener("execute", () => cb(), this);
        menu.add(supportBtn);
      });
    },

    addReleaseNotesToMenu: function(menu) {
      const releaseTag = osparc.utils.Utils.getReleaseTag();
      const releaseLink = osparc.utils.Utils.getReleaseLink();
      const releaseBtn = new qx.ui.menu.Button(qx.locale.Manager.tr("What's new in") + " " + releaseTag, "@FontAwesome5Solid/bullhorn/14");
      releaseBtn.addListener("execute", () => window.open(releaseLink), this);
      menu.add(releaseBtn);
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
