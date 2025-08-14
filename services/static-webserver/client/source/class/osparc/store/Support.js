
qx.Class.define("osparc.store.Support", {
  type: "static",

  statics: {
    getLicenseURL: function() {
      const vendor = osparc.store.VendorInfo.getInstance().getVendor();
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
      return osparc.store.VendorInfo.getInstance().getManuals();
    },

    addSupportConversationsToMenu: function(menu) {
      if (osparc.product.Utils.isSupportEnabled()) {
        const supportCenterButton = new qx.ui.menu.Button().set({
          label: qx.locale.Manager.tr("Ask a Question"),
          icon: "@FontAwesome5Regular/question-circle/16",
        });
        if (osparc.store.Products.getInstance().amIASupportUser()) {
          supportCenterButton.set({
            label: qx.locale.Manager.tr("Support Center"),
          });
        }
        menu.add(supportCenterButton);
      }
    },

    addQuickStartToMenu: function(menu) {
      const quickStart = osparc.product.quickStart.Utils.getQuickStart();
      if (quickStart) {
        const qsButton = new qx.ui.menu.Button(qx.locale.Manager.tr("Quick Start"), "@FontAwesome5Solid/graduation-cap/14");
        qsButton.getChildControl("label").set({
          rich: true
        });
        qsButton.addListener("execute", () => {
          const tutorialWindow = quickStart.tutorial();
          tutorialWindow.center();
          tutorialWindow.open();
        });
        menu.add(qsButton);
      }
    },

    addGuidedToursToMenu: function(menu) {
      const guidedToursButton = new qx.ui.menu.Button(qx.locale.Manager.tr("Guided Tours"), "@FontAwesome5Solid/graduation-cap/14");
      guidedToursButton.exclude();
      menu.add(guidedToursButton);
      const fetchTours = osparc.product.tours.Tours.getTours();
      if (fetchTours) {
        fetchTours
          .then(tours => {
            if (tours) {
              guidedToursButton.show();
              guidedToursButton.addListener("execute", () => {
                const toursManager = new osparc.tours.Manager();
                toursManager.setTours(tours);
                toursManager.start();
              });
            }
          });
      }
    },

    addManualButtonsToMenu: function(menu, menuButton) {
      const manuals = osparc.store.Support.getManuals();
      if (menuButton) {
        menuButton.setVisibility(manuals && manuals.length ? "visible" : "excluded");
      }
      manuals.forEach(manual => {
        const manualBtn = new qx.ui.menu.Button(manual.label, "@FontAwesome5Solid/book/14");
        manualBtn.getChildControl("label").set({
          rich: true
        });
        manualBtn.addListener("execute", () => window.open(manual.url), this);
        menu.add(manualBtn);
      });
    },

    addSupportButtonsToMenu: function(menu, menuButton) {
      const issues = osparc.store.VendorInfo.getInstance().getIssues();
      const supports = osparc.store.VendorInfo.getInstance().getSupports();
      if (menuButton) {
        menuButton.setVisibility(issues.length || supports.length ? "visible" : "excluded");
      }
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
      const releaseBtn = new qx.ui.menu.Button(qx.locale.Manager.tr("Release Notes") + " " + releaseTag, "@FontAwesome5Solid/book/14");
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
      const vendor = osparc.store.VendorInfo.getInstance().getVendor();
      if ("invitation_url" in vendor) {
        const displayName = osparc.store.StaticInfo.getInstance().getDisplayName();
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
