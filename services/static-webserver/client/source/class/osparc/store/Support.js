
qx.Class.define("osparc.store.Support", {
  type: "static",

  statics: {
    getLicenseURL: function() {
      return new Promise(resolve => {
        osparc.store.VendorInfo.getInstance().getVendor()
          .then(vendor => {
            if (vendor) {
              if ("license_url" in vendor) {
                resolve(vendor["license_url"]);
              } else if ("url" in vendor) {
                resolve(vendor["url"]);
              } else {
                resolve("");
              }
            }
          });
      });
    },

    getManuals: function() {
      return new Promise(resolve => {
        osparc.store.VendorInfo.getInstance().getManuals()
          .then(manuals => resolve(manuals));
      });
    },

    addQuickStartToMenu: function(menu) {
      const quickStart = osparc.product.quickStart.Utils.getQuickStart();
      if (quickStart) {
        const qsButton = new qx.ui.menu.Button(qx.locale.Manager.tr("Quick Start"));
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
      const guidedToursButton = new qx.ui.menu.Button(qx.locale.Manager.tr("Guided Tours"));
      guidedToursButton.exclude();
      menu.add(guidedToursButton);
      const fetchTours = osparc.product.tours.Utils.getTours();
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
      return new Promise(resolve => {
        osparc.store.Support.getManuals()
          .then(manuals => {
            if (menuButton) {
              menuButton.setVisibility(manuals.length ? "visible" : "excluded");
            }
            manuals.forEach(manual => {
              const manualBtn = new qx.ui.menu.Button(manual.label);
              manualBtn.getChildControl("label").set({
                rich: true
              });
              manualBtn.addListener("execute", () => window.open(manual.url), this);
              menu.add(manualBtn);
            });
          })
          .finally(() => resolve(true));
      });
    },

    addSupportButtonsToMenu: function(menu, menuButton) {
      return new Promise(resolve => {
        Promise.all([
          osparc.store.VendorInfo.getInstance().getIssues(),
          osparc.store.VendorInfo.getInstance().getSupports()
        ])
          .then(values => {
            const issues = values[0];
            const supports = values[1];
            if (menuButton) {
              menuButton.setVisibility(issues.length || supports.length ? "visible" : "excluded");
            }
            issues.forEach(issueInfo => {
              const label = issueInfo["label"];
              const issueButton = new qx.ui.menu.Button(label);
              issueButton.getChildControl("label").set({
                rich: true
              });
              issueButton.addListener("execute", () => {
                const issueConfirmationWindow = new osparc.ui.window.Dialog(label + " " + qx.locale.Manager.tr("Information"), null,
                  qx.locale.Manager.tr("To create an issue, you must have an account and be already logged-in.")
                );
                const contBtn = new qx.ui.form.Button(qx.locale.Manager.tr("Continue"), "@FontAwesome5Solid/external-link-alt/12");
                contBtn.addListener("execute", () => {
                  window.open(issueInfo["new_url"]);
                  issueConfirmationWindow.close();
                }, this);
                const loginBtn = new qx.ui.form.Button(qx.locale.Manager.tr("Log in in ") + label, "@FontAwesome5Solid/external-link-alt/12");
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

            supports.forEach(suportInfo => {
              const supportBtn = new qx.ui.menu.Button(suportInfo["label"]);
              supportBtn.getChildControl("label").set({
                rich: true
              });
              let icon = null;
              let cb = null;
              switch (suportInfo["kind"]) {
                case "web":
                  icon = "@FontAwesome5Solid/link/12";
                  cb = () => window.open(suportInfo["url"]);
                  break;
                case "forum":
                  icon = "@FontAwesome5Solid/comments/12";
                  cb = () => window.open(suportInfo["url"]);
                  break;
                case "email":
                  icon = "@FontAwesome5Solid/envelope/12";
                  cb = () => this.__openSendEmailFeedbackDialog(suportInfo["email"]);
                  break;
              }
              supportBtn.setIcon(icon);
              supportBtn.addListener("execute", () => cb(), this);
              menu.add(supportBtn);
            });
          })
          .finally(() => resolve(true));
      });
    },

    mailToText: function(email, subject) {
      const color = qx.theme.manager.Color.getInstance().resolve("text");
      const textLink = `<center>&nbsp&nbsp<a href="mailto:${email}?subject=${subject}" style='color: ${color}' target='_blank'>${email}</a>&nbsp&nbsp<center>`;
      return textLink;
    },

    getMailToLabel: function(email, subject) {
      const mailto = new qx.ui.basic.Label(this.mailToText(email, subject)).set({
        alignX: "center",
        font: "text-14",
        selectable: true,
        rich: true
      });
      return mailto;
    },

    __openSendEmailFeedbackDialog: function(email) {
      const productName = osparc.product.Utils.getProductName();
      const giveEmailFeedbackWindow = new osparc.ui.window.Dialog("Feedback", null, qx.locale.Manager.tr("Please send us an email to:"));
      const mailto = this.getMailToLabel(email, productName + " feedback");
      giveEmailFeedbackWindow.addWidget(mailto);
      giveEmailFeedbackWindow.open();
    },

    openInvitationRequiredDialog: function() {
      const createAccountWindow = new osparc.ui.window.Dialog("Create Account").set({
        maxWidth: 380
      });
      Promise.all([
        osparc.store.VendorInfo.getInstance().getVendor(),
        osparc.store.StaticInfo.getInstance().getDisplayName()
      ])
        .then(values => {
          const vendor = values[0];
          const displayName = values[1];
          if ("invitation_url" in vendor) {
            let message = qx.locale.Manager.tr("Registration is currently only available with an invitation.");
            message += "<br>";
            message += qx.locale.Manager.tr("Please request access to ") + displayName + ":";
            message += "<br>";
            createAccountWindow.setMessage(message);
            const linkLabel = new osparc.ui.basic.LinkLabel(vendor["invitation_url"], vendor["invitation_url"]);
            createAccountWindow.addWidget(linkLabel);
          } else {
            osparc.utils.Utils.createAccountMessage()
              .then(message => {
                createAccountWindow.setMessage(message);
              });
          }
        });
      createAccountWindow.center();
      createAccountWindow.open();
    }
  }
});
