/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Pedro Crespo (pcrespov)
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 *  User profile in preferences dialog
 *
 *  - first name, last name, userName, email
 *
 */

qx.Class.define("osparc.desktop.account.ProfilePage", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(15));

    this._add(this.__createProfileUser());
    this._add(this.__createPrivacySection());
    if (osparc.store.StaticInfo.is2FARequired()) {
      this._add(this.__create2FASection());
    }
    this._add(this.__createPasswordSection());
    this._add(this.__createContactSection());
    this._add(this.__createTransferProjectsSection());
    this._add(this.__createDeleteAccount());

    this.__userProfileData = {};
    this.__userPrivacyData = {};

    this.__fetchMyProfile();
  },

  statics: {
    PROFILE: {
      POS: {
        USERNAME: 0,
        FIRST_NAME: 1,
        LAST_NAME: 2,
        EMAIL: 3,
        PHONE: 4,
      },
    },

    createSectionBox: function(title) {
      const box = new osparc.widget.SectionBox(title).set({
        alignX: "left",
        maxWidth: 500
      });
      return box;
    },
  },

  members: {
    __userProfileData: null,
    __userProfileModel: null,
    __userProfileForm: null,
    __userProfileRenderer: null,
    __updateProfileBtn: null,
    __userPrivacyData: null,
    __userPrivacyModel: null,
    __privacyRenderer: null,
    __updatePrivacyBtn: null,
    __sms2FAItem: null,
    __personalInfoModel: null,
    __personalInfoRenderer: null,

    __fetchMyProfile: function() {
      this.__userProfileRenderer.setEnabled(false);
      this.__privacyRenderer.setEnabled(false);
      this.__personalInfoRenderer.setEnabled(false);

      osparc.data.Resources.getOne("profile", {}, null, false)
        .then(profile => {
          this.__setDataToProfile(profile);
          this.__setDataToPrivacy(profile["privacy"]);
          this.__userProfileRenderer.setEnabled(true);
          this.__privacyRenderer.setEnabled(true);
          this.__personalInfoRenderer.setEnabled(true);
        })
        .catch(err => console.error(err));
    },

    __setDataToProfile: function(data) {
      if (data) {
        this.__userProfileData = data;
        this.__userProfileModel.set({
          "userName": data["userName"] || "",
          "firstName": data["first_name"] || "",
          "lastName": data["last_name"] || "",
          "email": data["login"],
          "phone": data["phone"] || "-",
          "expirationDate": data["expirationDate"] || null,
        });
        if (data["contact"]) {
          const contact = data["contact"];
          this.__personalInfoModel.set({
            "institution": contact["institution"] || "",
            "address": contact["address"] || "",
            "city": contact["city"] || "",
            "state": contact["state"] || "",
            "country": contact["country"] || "",
            "postalCode": contact["postalCode"] || "",
          });
        }
      }
      this.__updateProfileBtn.setEnabled(false);

      if (this.__sms2FAItem) {
        this.__sms2FAItem.setEnabled(Boolean(data["phone"]));
      }
    },

    __setDataToPrivacy: function(privacyData) {
      if (privacyData) {
        this.__userPrivacyData = privacyData;
        this.__userPrivacyModel.set({
          "hideUserName": "hideUserName" in privacyData ? privacyData["hideUserName"] : false,
          "hideFullname": "hideFullname" in privacyData ? privacyData["hideFullname"] : true,
          "hideEmail": "hideEmail" in privacyData ? privacyData["hideEmail"] : true,
        });

        const visibleIcon = "@FontAwesome5Solid/eye/12";
        const hiddenIcon = "@FontAwesome5Solid/eye-slash/12";
        const createImage = source => {
          return new qx.ui.basic.Image(source).set({
            alignX: "center",
            alignY: "middle",
          });
        }
        const pos = this.self().PROFILE.POS;
        const widgets = {
          [pos.USERNAME]: createImage(this.__userPrivacyModel.getHideUserName() ? hiddenIcon : visibleIcon),
          [pos.FIRST_NAME]: createImage(this.__userPrivacyModel.getHideFullname() ? hiddenIcon : visibleIcon),
          [pos.LAST_NAME]: createImage(this.__userPrivacyModel.getHideFullname() ? hiddenIcon : visibleIcon),
          [pos.EMAIL]: createImage(this.__userPrivacyModel.getHideEmail() ? hiddenIcon : visibleIcon),
        };
        if (osparc.store.StaticInfo.isUpdatePhoneNumberEnabled()) {
          const updatePhoneNumberButton = new qx.ui.form.Button(null, "@FontAwesome5Solid/pencil-alt/12").set({
            padding: [1, 5],
          });
          updatePhoneNumberButton.addListener("execute", () => this.__openPhoneNumberUpdater(), this);
          widgets[pos.PHONE] = updatePhoneNumberButton;
        }
        this.__userProfileRenderer.setWidgets(widgets);
      }
      this.__updatePrivacyBtn.setEnabled(false);
    },

    __resetUserData: function() {
      this.__setDataToProfile(this.__userProfileData);
    },

    __resetPrivacyData: function() {
      this.__setDataToPrivacy(this.__userPrivacyData);
    },

    __createProfileUser: function() {
      // layout
      const box = this.self().createSectionBox(this.tr("User"));

      const userName = new qx.ui.form.TextField().set({
        placeholder: this.tr("userName")
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

      const phoneNumber = new qx.ui.form.TextField().set({
        placeholder: this.tr("Phone Number"),
        readOnly: true
      });

      const profileForm = this.__userProfileForm = new qx.ui.form.Form();
      profileForm.add(userName, "UserName", null, "userName");
      profileForm.add(firstName, "First Name", null, "firstName");
      profileForm.add(lastName, "Last Name", null, "lastName");
      profileForm.add(email, "Email", null, "email");
      if (osparc.store.StaticInfo.is2FARequired()) {
        profileForm.add(phoneNumber, "Phone Number", null, "phone");
      }
      this.__userProfileRenderer = new osparc.ui.form.renderer.SingleWithWidget(profileForm);
      box.add(this.__userProfileRenderer);

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
      const infoLabel = this.tr("Please contact us via email:<br>");
      const infoExtension = new osparc.ui.hint.InfoHint(infoLabel);
      const supportEmail = osparc.store.VendorInfo.getSupportEmail();
      infoExtension.setHintText(infoLabel + supportEmail);
      expirationLayout.add(infoExtension);
      box.add(expirationLayout);

      // binding to a model
      const raw = {
        "userName": "",
        "firstName": "",
        "lastName": "",
        "email": "",
        "phone": "",
        "expirationDate": null,
      };

      const model = this.__userProfileModel = qx.data.marshal.Json.createModel(raw);
      const controller = new qx.data.controller.Object(model);

      controller.addTarget(userName, "value", "userName", true);
      controller.addTarget(email, "value", "email", true);
      controller.addTarget(firstName, "value", "firstName", true, null, {
        converter: function(data) {
          return data.replace(/^\w/, c => c.toUpperCase());
        }
      });
      controller.addTarget(lastName, "value", "lastName", true);
      controller.addTarget(phoneNumber, "value", "phone", true);
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

      const updateProfileBtn = this.__updateProfileBtn = new qx.ui.form.Button().set({
        label: this.tr("Update Profile"),
        appearance: "form-button",
        alignX: "right",
        allowGrowX: false,
        enabled: false,
      });
      box.add(updateProfileBtn);

      updateProfileBtn.addListener("execute", () => {
        if (!osparc.data.Permissions.getInstance().canDo("user.user.update", true)) {
          this.__resetUserData();
          return;
        }

        const patchData = {};
        if (this.__userProfileData["userName"] !== model.getUserName()) {
          patchData["userName"] = model.getUserName();
        }
        if (this.__userProfileData["first_name"] !== model.getFirstName()) {
          patchData["first_name"] = model.getFirstName();
        }
        if (this.__userProfileData["last_name"] !== model.getLastName()) {
          patchData["last_name"] = model.getLastName();
        }

        if (Object.keys(patchData).length) {
          if (namesValidator.validate()) {
            const params = {
              data: patchData
            };
            osparc.data.Resources.fetch("profile", "patch", params)
              .then(() => {
                this.__setDataToProfile(Object.assign(this.__userProfileData, params.data));
                osparc.auth.Manager.getInstance().updateProfile(this.__userProfileData);
                const msg = this.tr("Profile updated");
                osparc.FlashMessenger.logAs(msg, "INFO");
              })
              .catch(err => {
                this.__resetUserData();
                osparc.FlashMessenger.logError(err, this.tr("Unsuccessful profile update"));
              });
          }
        }
      });

      const profileFields = [
        userName,
        firstName,
        lastName,
      ]
      const valueChanged = () => {
        const anyChanged =
          userName.getValue() !== this.__userProfileData["userName"] ||
          firstName.getValue() !== this.__userProfileData["first_name"] ||
          lastName.getValue() !== this.__userProfileData["last_name"];
        updateProfileBtn.setEnabled(anyChanged);
      };
      profileFields.forEach(privacyField => privacyField.addListener("changeValue", () => valueChanged()));

      return box;
    },

    __createPrivacySection: function() {
      // binding to a model
      const defaultModel = {
        "hideUserName": false,
        "hideFullname": true,
        "hideEmail": true,
      };

      const privacyModel = this.__userPrivacyModel = qx.data.marshal.Json.createModel(defaultModel, true);

      const box = this.self().createSectionBox(this.tr("Privacy"));
      box.addHelper(this.tr("Choose what others see."));

      const hideUserName = new qx.ui.form.CheckBox().set({
        value: defaultModel.hideUserName
      });
      const hideFullname = new qx.ui.form.CheckBox().set({
        value: defaultModel.hideFullname
      });
      const hideEmail = new qx.ui.form.CheckBox().set({
        value: defaultModel.hideEmail
      });

      const privacyForm = new qx.ui.form.Form();
      privacyForm.add(hideUserName, "Hide UserName", null, "hideUserName");
      privacyForm.add(hideFullname, "Hide Full Name", null, "hideFullname");
      privacyForm.add(hideEmail, "Hide Email", null, "hideEmail");
      this.__privacyRenderer = new qx.ui.form.renderer.Single(privacyForm);
      box.add(this.__privacyRenderer);

      const privacyModelCtrl = new qx.data.controller.Object(privacyModel);
      privacyModelCtrl.addTarget(hideUserName, "value", "hideUserName", true);
      privacyModelCtrl.addTarget(hideFullname, "value", "hideFullname", true);
      privacyModelCtrl.addTarget(hideEmail, "value", "hideEmail", true);

      const updatePrivacyBtn = this.__updatePrivacyBtn = new qx.ui.form.Button().set({
        label: this.tr("Update Privacy"),
        appearance: "form-button",
        alignX: "right",
        allowGrowX: false,
        enabled: false,
      });
      box.add(updatePrivacyBtn);
      updatePrivacyBtn.addListener("execute", () => {
        if (!osparc.data.Permissions.getInstance().canDo("user.user.update", true)) {
          this.__resetPrivacyData();
          return;
        }
        const patchData = {
          "privacy": {}
        };
        if (this.__userPrivacyData["hideUserName"] !== privacyModel.getHideUserName()) {
          patchData["privacy"]["hideUserName"] = privacyModel.getHideUserName();
        }
        if (this.__userPrivacyData["hideFullname"] !== privacyModel.getHideFullname()) {
          patchData["privacy"]["hideFullname"] = privacyModel.getHideFullname();
        }
        if (this.__userPrivacyData["hideEmail"] !== privacyModel.getHideEmail()) {
          patchData["privacy"]["hideEmail"] = privacyModel.getHideEmail();
        }

        if (
          "hideFullname" in patchData["privacy"] &&
          patchData["privacy"]["hideFullname"] === false &&
          this.__userProfileData["first_name"] === null
        ) {
          this.__userProfileForm.getItem("firstName").set({
            invalidMessage: qx.locale.Manager.tr("Name is required"),
            valid: false
          });
          osparc.FlashMessenger.logAs(this.tr("Set the Name first"), "WARNING");
          return;
        }

        if (Object.keys(patchData["privacy"]).length) {
          const params = {
            data: patchData
          };
          osparc.data.Resources.fetch("profile", "patch", params)
            .then(() => {
              this.__setDataToPrivacy(Object.assign(this.__userPrivacyData, params.data["privacy"]));
              const msg = this.tr("Privacy updated");
              osparc.FlashMessenger.logAs(msg, "INFO");
            })
            .catch(err => {
              this.__resetPrivacyData();
              osparc.FlashMessenger.logError(err, this.tr("Unsuccessful privacy update"));
            });
        }
      });

      const optOutMessage = new qx.ui.basic.Atom().set({
        label: this.tr("If all searchable fields are hidden, you will not be discoverable."),
        icon: "@FontAwesome5Solid/exclamation-triangle/14",
        gap: 8,
        allowGrowX: false,
      });
      optOutMessage.getChildControl("icon").setTextColor("warning-yellow")
      box.add(optOutMessage);

      const privacyFields = [
        hideUserName,
        hideFullname,
        hideEmail,
      ]
      const valueChanged = () => {
        const anyChanged =
          hideUserName.getValue() !== this.__userPrivacyData["hideUserName"] ||
          hideFullname.getValue() !== this.__userPrivacyData["hideFullname"] ||
          hideEmail.getValue() !== this.__userPrivacyData["hideEmail"];
        updatePrivacyBtn.setEnabled(anyChanged);

        if (privacyFields.every(privacyField => privacyField.getValue())) {
          optOutMessage.show();
        } else {
          optOutMessage.exclude();
        }
      };
      privacyFields.forEach(privacyField => privacyField.addListener("changeValue", () => valueChanged()));

      return box;
    },

    __create2FASection: function() {
      const box = this.self().createSectionBox(this.tr("Two-Factor Authentication"));
      box.addHelper(this.tr("Set your preferred method to use for two-factor authentication when signing in:"));

      const form = new qx.ui.form.Form();

      const preferencesSettings = osparc.Preferences.getInstance();

      const twoFAPreferenceSB = new qx.ui.form.SelectBox().set({
        allowGrowX: false
      });
      twoFAPreferenceSB.getChildControl("arrow").syncAppearance(); // force sync to show the arrow
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
        if (options.id === "SMS") {
          this.__sms2FAItem = lItem;
        }
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
            The Two-Factor Authentication is one more measure to prevent hackers from accessing your account with an additional layer of security. \
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

    __createPasswordSection: function() {
      // layout
      const box = this.self().createSectionBox(this.tr("Password"));

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
              const msg = this.tr("Unsuccessful password reset");
              osparc.FlashMessenger.logError(err, msg);
              [currentPassword, newPassword, confirm].forEach(item => {
                item.resetValue();
              });
            });
        }
      });

      return box;
    },

    __createContactSection: function() {
      // layout
      const box = this.self().createSectionBox(this.tr("Contact"));

      const institution = new qx.ui.form.TextField().set({
        placeholder: osparc.product.Utils.getInstitutionAlias().label,
        readOnly: true,
      });

      const address = new qx.ui.form.TextField().set({
        placeholder: this.tr("Address"),
        readOnly: true,
      });
      const city = new qx.ui.form.TextField().set({
        placeholder: this.tr("City"),
        readOnly: true,
      });

      const state = new qx.ui.form.TextField().set({
        placeholder: this.tr("State"),
        readOnly: true,
      });

      const country = new qx.ui.form.TextField().set({
        placeholder: this.tr("Country"),
        readOnly: true,
      });

      const postalCode = new qx.ui.form.TextField().set({
        placeholder: this.tr("Postal Code"),
        readOnly: true,
      });

      const personalInfoForm = new qx.ui.form.Form();
      personalInfoForm.add(institution, osparc.product.Utils.getInstitutionAlias().label, null, "institution");
      personalInfoForm.add(address, this.tr("Address"), null, "address");
      personalInfoForm.add(city, this.tr("City"), null, "city");
      personalInfoForm.add(state, this.tr("State"), null, "state");
      personalInfoForm.add(country, this.tr("Country"), null, "country");
      personalInfoForm.add(postalCode, this.tr("Postal Code"), null, "postalCode");
      this.__personalInfoRenderer = new qx.ui.form.renderer.Single(personalInfoForm);
      box.add(this.__personalInfoRenderer);

      // binding to a model
      const raw = {
        "institution": null,
        "address": null,
        "city": null,
        "state": null,
        "country": null,
        "postalCode": null,
      };

      const model = this.__personalInfoModel = qx.data.marshal.Json.createModel(raw);
      const controller = new qx.data.controller.Object(model);

      controller.addTarget(institution, "value", "institution", true);
      controller.addTarget(address, "value", "address", true);
      controller.addTarget(city, "value", "city", true);
      controller.addTarget(state, "value", "state", true);
      controller.addTarget(country, "value", "country", true);
      controller.addTarget(postalCode, "value", "postalCode", true);

      return box;
    },

    __createTransferProjectsSection: function() {
      const box = this.self().createSectionBox(this.tr("Transfer Projects"));
      box.addHelper(this.tr("Transfer of your projects to another user."));

      const transferBtn = new qx.ui.form.Button(this.tr("Transfer Projects")).set({
        appearance: "strong-button",
        alignX: "right",
        allowGrowX: false
      });
      transferBtn.addListener("execute", () => {
        const transferProjects = new osparc.desktop.account.TransferProjects();
        const win = osparc.ui.window.Window.popUpInWindow(transferProjects, qx.locale.Manager.tr("Transfer Projects"), 500, null);
        transferProjects.addListener("cancel", () => win.close());
        transferProjects.addListener("transferred", () => win.close());
      });
      box.add(transferBtn);

      return box;
    },

    __createDeleteAccount: function() {
      // layout
      const box = this.self().createSectionBox(this.tr("Delete Account"));
      box.addHelper(this.tr("Request the deletion of your account."));

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
    },

    __openPhoneNumberUpdater: function() {
      const verifyPhoneNumberView = new osparc.auth.ui.VerifyPhoneNumberView().set({
        userEmail: osparc.auth.Data.getInstance().getEmail(),
        updatingNumber: true,
      });
      verifyPhoneNumberView.getChildControl("title").exclude();
      verifyPhoneNumberView.getChildControl("send-via-email-button").exclude();
      const win = osparc.ui.window.Window.popUpInWindow(verifyPhoneNumberView, this.tr("Update Phone Number"), 330, 135).set({
        clickAwayClose: false,
        resizable: false,
        showClose: true
      });
      verifyPhoneNumberView.addListener("done", () => {
        win.close();
        this.__fetchMyProfile();
      }, this);
    },
  }
});
