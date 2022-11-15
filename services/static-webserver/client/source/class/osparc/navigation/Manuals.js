
qx.Class.define("osparc.navigation.Manuals", {
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

    addManualButtonsToMenu: function(menu, menuButton) {
      osparc.navigation.Manuals.getManuals()
        .then(manuals => {
          if (menuButton) {
            menuButton.setVisibility(manuals.length ? "visible" : "excluded");
          }
          manuals.forEach(manual => {
            const manualBtn = new qx.ui.menu.Button(manual.label);
            manualBtn.addListener("execute", () => window.open(manual.url), this);
            menu.add(manualBtn);
          });
        });
    },

    addSupportButtonsToMenu: function(menu, menuButton) {
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
        });
    },

    __openSendEmailFeedbackDialog: function(email) {
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
    }
  }
});
