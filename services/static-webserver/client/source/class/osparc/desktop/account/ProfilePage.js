/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Pedro Crespo (pcrespov)

************************************************************************ */

/**
 *  User profile in preferences dialog
 *
 *  - user name, surname, email, avatar
 *
 */

qx.Class.define("osparc.desktop.account.ProfilePage", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(15));

    this.__userProfileData = null;
    this.__userProfileModel = null;

    this.__fetchProfile();

    this._add(this.__createProfileUser());
    if (osparc.store.StaticInfo.getInstance().is2FARequired()) {
      this._add(this.__create2FASection());
    }
    this._add(this.__createPasswordSection());
    this._add(this.__createDeleteAccount());
  },

  members: {
    __userProfileData: null,
    __userProfileModel: null,

    __createProfileUser: function() {
      // layout
      const box = osparc.ui.window.TabbedView.createSectionBox(this.tr("User"));
      box.set({
        alignX: "left",
        maxWidth: 500
      });

      const firstName = new qx.ui.form.TextField().set({
        placeholder: this.tr("First Name")
      });

      const lastName = new qx.ui.form.TextField().set({
        placeholder: this.tr("Last Name")
      });

      const email = new qx.ui.form.TextField().set({
        placeholder: this.tr("Email"),
        readOnly: true
      });

      const form = new qx.ui.form.Form();
      form.add(firstName, "First Name", null, "firstName");
      form.add(lastName, "Last Name", null, "lastName");
      form.add(email, "Email", null, "email");
      box.add(new qx.ui.form.renderer.Single(form));

      const expirationLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5)).set({
        paddingLeft: 16,
        visibility: "excluded"
      });
      const expirationDateLabel = new qx.ui.basic.Label(this.tr("Expiration date:")).set({
        textColor: "danger-red"
      });
      expirationLayout.add(expirationDateLabel);
      const expirationDate = new qx.ui.basic.Label();
      expirationLayout.add(expirationDate);
      const infoLabel = this.tr("Please contact us by email:<br>");
      const infoExtension = new osparc.ui.hint.InfoHint(infoLabel);
      const supportEmail = osparc.store.VendorInfo.getInstance().getSupportEmail();
      infoExtension.setHintText(infoLabel + supportEmail);
      expirationLayout.add(infoExtension);
      box.add(expirationLayout);

      // binding to a model
      const raw = {
        "firstName": null,
        "lastName": null,
        "email": null,
        "role": null,
        "expirationDate": null
      };

      if (qx.core.Environment.get("qx.debug")) {
        raw.firstName = "Bizzy";
        raw.lastName = "Zastrow";
        raw.email = "bizzy@itis.swiss";
        raw.role = "User";
        raw.expirationDate = null;
      }
      const model = this.__userProfileModel = qx.data.marshal.Json.createModel(raw);
      const controller = new qx.data.controller.Object(model);

      controller.addTarget(email, "value", "email", true);
      controller.addTarget(firstName, "value", "firstName", true, null, {
        converter: function(data) {
          return data.replace(/^\w/, c => c.toUpperCase());
        }
      });
      controller.addTarget(lastName, "value", "lastName", true);
      controller.addTarget(expirationDate, "value", "expirationDate", false, {
        converter: expirationDay => {
          if (expirationDay) {
            expirationLayout.show();
            return osparc.utils.Utils.formatDate(new Date(expirationDay));
          }
          return "";
        }
      });

      // validation
      const emailValidator = new qx.ui.form.validation.Manager();
      emailValidator.add(email, qx.util.Validate.email());

      const namesValidator = new qx.ui.form.validation.Manager();
      namesValidator.add(firstName, qx.util.Validate.regExp(/[^\.\d]+/), this.tr("Avoid dots or numbers in text"));
      namesValidator.add(lastName, qx.util.Validate.regExp(/^$|[^\.\d]+/), this.tr("Avoid dots or numbers in text")); // allow also empty last name

      const updateBtn = new qx.ui.form.Button("Update Profile").set({
        appearance: "form-button",
        alignX: "right",
        allowGrowX: false
      });
      box.add(updateBtn);

      updateBtn.addListener("execute", () => {
        if (!osparc.data.Permissions.getInstance().canDo("user.user.update", true)) {
          this.__resetDataToModel();
          return;
        }

        const requests = {
          email: null,
          names: null
        };
        if (this.__userProfileData["login"] !== model.getEmail()) {
          if (emailValidator.validate()) {
            const emailReq = new osparc.io.request.ApiRequest("/auth/change-email", "POST");
            emailReq.setRequestData({
              "email": model.getEmail()
            });
            requests.email = emailReq;
          }
        }

        if (this.__userProfileData["first_name"] !== model.getFirstName() || this.__userProfileData["last_name"] !== model.getLastName()) {
          if (namesValidator.validate()) {
            const profileReq = new osparc.io.request.ApiRequest("/me", "PUT");
            profileReq.setRequestData({
              "first_name": model.getFirstName(),
              "last_name": model.getLastName()
            });
            requests.names = profileReq;
          }
        }

        Object.keys(requests).forEach(key => {
          const req = requests[key];
          if (req === null) {
            return;
          }

          req.addListenerOnce("success", e => {
            const reqData = e.getTarget().getRequestData();
            this.__setDataToModel(Object.assign(this.__userProfileData, reqData));
            osparc.auth.Manager.getInstance().updateProfile(this.__userProfileData);
            const res = e.getTarget().getResponse();
            const msg = (res && res.data) ? res.data : this.tr("Profile updated");
            osparc.FlashMessenger.getInstance().logAs(msg, "INFO");
          }, this);

          req.addListenerOnce("fail", e => {
            this.__resetDataToModel();
            const error = e.getTarget().getResponse().error;
            const msg = error ? error["errors"][0].message : this.tr("Failed to update profile");
            osparc.FlashMessenger.getInstance().logAs(msg, "ERROR");
          }, this);

          req.send();
        });
      }, this);

      return box;
    },

    __create2FASection: function() {
      const box = osparc.ui.window.TabbedView.createSectionBox(this.tr("2 Factor Authentication"));

      const label = osparc.ui.window.TabbedView.createHelpLabel(this.tr("Set your preferred method to use for two-factor authentication when signing in:"));
      box.add(label);

      const form = new qx.ui.form.Form();

      const preferencesSettings = osparc.Preferences.getInstance();

      const twoFAPreferenceSB = new qx.ui.form.SelectBox().set({
        allowGrowX: false
      });
      [{
        id: "SMS",
        label: "SMS"
      }, {
        id: "EMAIL",
        label: "e-mail"
      }, {
        id: "DISABLED",
        label: "Disabled"
      }].forEach(options => {
        const lItem = new qx.ui.form.ListItem(options.label, null, options.id);
        twoFAPreferenceSB.add(lItem);
      });
      const value = preferencesSettings.getTwoFAPreference();
      twoFAPreferenceSB.getSelectables().forEach(selectable => {
        if (selectable.getModel() === value) {
          twoFAPreferenceSB.setSelection([selectable]);
        }
      });
      twoFAPreferenceSB.addListener("changeValue", e => {
        const currentSelection = e.getData();
        const lastSelection = e.getOldData();
        const selectedId = currentSelection.getModel();
        if (selectedId === "DISABLED") {
          const discourageTitle = this.tr("You are about to disable the 2FA");
          const discourageText = this.tr("\
            The 2 Factor Authentication is one more measure to prevent hackers from accessing your account with an additional layer of security. \
            When you sign in, 2FA helps make sure that your resources and personal information stays private, safe and secure.\
          ");
          const win = new osparc.ui.window.Confirmation(discourageTitle).set({
            caption: discourageTitle,
            message: discourageText,
            confirmText: this.tr("Yes, disable"),
            confirmAction: "delete"
          });
          win.center();
          win.open();
          win.addListener("close", () => {
            if (win.getConfirmed()) {
              osparc.Preferences.patchPreferenceField("twoFAPreference", twoFAPreferenceSB, selectedId);
            } else {
              twoFAPreferenceSB.setSelection([lastSelection]);
            }
          }, this);
        } else {
          osparc.Preferences.patchPreferenceField("twoFAPreference", twoFAPreferenceSB, selectedId);
        }
      });
      form.add(twoFAPreferenceSB, this.tr("2FA Method"));

      box.add(new qx.ui.form.renderer.Single(form));

      return box;
    },

    __fetchProfile: function() {
      osparc.data.Resources.getOne("profile", {}, null, false)
        .then(profile => {
          this.__setDataToModel(profile);
        })
        .catch(err => {
          console.error(err);
        });
    },

    __setDataToModel: function(data) {
      if (data) {
        this.__userProfileData = data;
        this.__userProfileModel.set({
          "firstName": data["first_name"] || "",
          "lastName": data["last_name"] || "",
          "email": data["login"],
          "role": data["role"] || "",
          "expirationDate": data["expirationDate"] || null
        });
      }
    },

    __resetDataToModel: function() {
      this.__setDataToModel(this.__userProfileData);
    },

    __createPasswordSection: function() {
      // layout
      const box = osparc.ui.window.TabbedView.createSectionBox(this.tr("Password"));
      box.set({
        alignX: "left",
        maxWidth: 500
      });

      const currentPassword = new osparc.ui.form.PasswordField().set({
        required: true,
        placeholder: this.tr("Your current password")
      });

      const newPassword = new osparc.ui.form.PasswordField().set({
        required: true,
        placeholder: this.tr("Your new password")
      });

      const confirm = new osparc.ui.form.PasswordField().set({
        required: true,
        placeholder: this.tr("Retype your new password")
      });

      const form = new qx.ui.form.Form();
      form.add(currentPassword, "Current Password", null, "curPassword");
      form.add(newPassword, "New Password", null, "newPassword");
      form.add(confirm, "Confirm New Password", null, "newPassword2");
      box.add(new qx.ui.form.renderer.Single(form));

      const manager = new qx.ui.form.validation.Manager();
      manager.add(newPassword, osparc.auth.core.Utils.passwordLengthValidator);
      manager.add(confirm, osparc.auth.core.Utils.passwordLengthValidator);
      manager.setValidator(function(_itemForms) {
        return osparc.auth.core.Utils.checkSamePasswords(newPassword, confirm);
      });

      const resetBtn = new qx.ui.form.Button("Reset Password").set({
        appearance: "form-button",
        alignX: "right",
        allowGrowX: false
      });
      box.add(resetBtn);

      resetBtn.addListener("execute", () => {
        if (manager.validate()) {
          const params = {
            data: {
              current: currentPassword.getValue(),
              new: newPassword.getValue(),
              confirm: confirm.getValue()
            }
          };
          osparc.data.Resources.fetch("password", "post", params)
            .then(data => {
              osparc.FlashMessenger.getInstance().log(data);
              [currentPassword, newPassword, confirm].forEach(item => {
                item.resetValue();
              });
            })
            .catch(err => {
              console.error(err);
              osparc.FlashMessenger.getInstance().logAs(this.tr("Failed to reset password"), "ERROR");
              [currentPassword, newPassword, confirm].forEach(item => {
                item.resetValue();
              });
            });
        }
      });

      return box;
    },

    __createDeleteAccount: function() {
      // layout
      const box = osparc.ui.window.TabbedView.createSectionBox(this.tr("Danger Zone")).set({
        alignX: "left",
        maxWidth: 500
      });

      const deleteBtn = new qx.ui.form.Button(this.tr("Delete Account")).set({
        appearance: "danger-button",
        alignX: "right",
        allowGrowX: false
      });
      deleteBtn.addListener("execute", () => {
        const deleteAccount = new osparc.desktop.account.DeleteAccount();
        const win = osparc.ui.window.Window.popUpInWindow(deleteAccount, qx.locale.Manager.tr("Delete Account"), 430, null);
        deleteAccount.addListener("cancel", () => win.close());
        deleteAccount.addListener("deleted", () => win.close());
      });
      box.add(deleteBtn);

      return box;
    }
  }
});
