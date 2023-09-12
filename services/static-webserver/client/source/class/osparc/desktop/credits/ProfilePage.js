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

qx.Class.define("osparc.desktop.credits.ProfilePage", {
  extend: osparc.desktop.preferences.pages.BasePage,

  construct: function() {
    const iconSrc = "@FontAwesome5Solid/user/24";
    const title = this.tr("Profile");
    this.base(arguments, title, iconSrc);

    this.__userProfileData = null;
    this.__userProfileModel = null;

    this.__getProfile();

    this.add(this.__createProfileUser());
    this.add(this.__createPasswordSection());
  },

  members: {
    __userProfileData: null,
    __userProfileModel: null,

    __createProfileUser: function() {
      // layout
      const box = this._createSectionBox(this.tr("User"));
      box.set({
        alignX: "left",
        maxWidth: 500
      });

      const email = new qx.ui.form.TextField().set({
        tabIndex: 1,
        placeholder: this.tr("Email")
      });

      const firstName = new qx.ui.form.TextField().set({
        tabIndex: 2,
        placeholder: this.tr("First Name")
      });

      const lastName = new qx.ui.form.TextField().set({
        tabIndex: 3,
        placeholder: this.tr("Last Name")
      });

      let role = null;
      const permissions = osparc.data.Permissions.getInstance();
      if (permissions.canDo("user.role.update")) {
        role = new qx.ui.form.SelectBox();
        const roles = permissions.getChildrenRoles(permissions.getRole());
        for (let i=0; i<roles.length; i++) {
          const roleItem = new qx.ui.form.ListItem(roles[i]);
          role.add(roleItem);
          role.setSelection([roleItem]);
        }
        role.addListener("changeSelection", function(e) {
          let newRole = e.getData()[0].getLabel();
          newRole = newRole.toLowerCase();
          permissions.setRole(newRole);
        }, this);
      } else {
        role = new qx.ui.form.TextField().set({
          readOnly: true
        });
      }
      role.set({
        tabIndex: 4
      });

      const form = new qx.ui.form.Form();
      form.add(email, "Email", null, "email");
      form.add(firstName, "First Name", null, "firstName");
      form.add(lastName, "Last Name", null, "lastName");
      form.add(role, "Role", null, "role");
      box.add(new qx.ui.form.renderer.Single(form));

      const expirationLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5)).set({
        paddingLeft: 16,
        visibility: "excluded"
      });
      expirationLayout.add(new qx.ui.basic.Label(this.tr("Expiration date:")));
      const expirationDate = new qx.ui.basic.Label();
      expirationLayout.add(expirationDate);
      const infoLabel = this.tr("Please contact us by email:<br>");
      const infoExtension = new osparc.ui.hint.InfoHint(infoLabel);
      osparc.store.VendorInfo.getInstance().getSupportEmail()
        .then(supportEmail => infoExtension.setHintText(infoLabel + supportEmail));
      expirationLayout.add(infoExtension);
      box.add(expirationLayout);

      /*
      const img = new qx.ui.basic.Image().set({
        maxWidth: 100,
        maxHeight: 100,
        scale: true,
        decorator: new qx.ui.decoration.Decorator().set({
          radius: 30
        }),
        alignX: "center"
      });
      box.add(img);
      */

      // binding to a model
      let raw = {
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
      controller.addTarget(role, "value", "role", false);
      controller.addTarget(expirationDate, "value", "expirationDate", false, {
        converter: expirationDay => {
          if (expirationDay) {
            expirationLayout.show();
            return osparc.utils.Utils.formatDate(new Date(expirationDay));
          }
          return "";
        }
      });
      /*
      controller.addTarget(img, "source", "email", false, {
        converter: function(data) {
          return osparc.utils.Avatar.getUrl(email.getValue(), 150);
        }
      });
      */

      // validation
      const emailValidator = new qx.ui.form.validation.Manager();
      emailValidator.add(email, qx.util.Validate.email());

      const namesValidator = new qx.ui.form.validation.Manager();
      namesValidator.add(firstName, qx.util.Validate.regExp(/[^\.\d]+/), this.tr("Avoid dots or numbers in text"));
      namesValidator.add(lastName, qx.util.Validate.regExp(/^$|[^\.\d]+/), this.tr("Avoid dots or numbers in text")); // allow also emtpy last name

      const updateBtn = new qx.ui.form.Button("Update Profile").set({
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

    __getProfile: function() {
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
      const box = this._createSectionBox(this.tr("Password"));
      box.set({
        alignX: "left",
        maxWidth: 500
      });

      const currentPassword = new osparc.ui.form.PasswordField().set({
        tabIndex: 1,
        required: true,
        placeholder: this.tr("Your current password")
      });

      const newPassword = new osparc.ui.form.PasswordField().set({
        tabIndex: 2,
        required: true,
        placeholder: this.tr("Your new password")
      });

      const confirm = new osparc.ui.form.PasswordField().set({
        tabIndex: 3,
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
    }
  }
});
