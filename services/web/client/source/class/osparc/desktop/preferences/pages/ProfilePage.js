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

qx.Class.define("osparc.desktop.preferences.pages.ProfilePage", {
  extend: osparc.desktop.preferences.pages.BasePage,

  construct: function() {
    const iconSrc = "@FontAwesome5Solid/user/24";
    const title = this.tr("Profile");
    this.base(arguments, title, iconSrc);

    this.__userProfileData = null;
    this.__userProfileModel = null;

    this.__getProfile();

    this.add(this.__createProfileUser());
  },

  members: {
    __userProfileData: null,
    __userProfileModel: null,

    __createProfileUser: function() {
      // layout
      const box = this._createSectionBox(this.tr("User"));

      const email = new qx.ui.form.TextField().set({
        placeholder: this.tr("Email")
      });

      const firstName = new qx.ui.form.TextField().set({
        placeholder: this.tr("First Name")
      });

      const lastName = new qx.ui.form.TextField().set({
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

      const form = new qx.ui.form.Form();
      form.add(email, "", null, "email");
      form.add(firstName, "", null, "firstName");
      form.add(lastName, "", null, "lastName");
      form.add(role, "", null, "role");

      box.add(new qx.ui.form.renderer.Single(form));

      const expirationLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5)).set({
        paddingLeft: 16,
        visibility: "excluded"
      });
      expirationLayout.add(new qx.ui.basic.Label(this.tr("Expiration date:")));
      const expirationDate = new qx.ui.basic.Label();
      expirationLayout.add(expirationDate);
      const infoLabel = this.tr("Please, contact us by email:<br>");
      const infoExtension = new osparc.ui.hint.InfoHint(infoLabel);
      osparc.store.StaticInfo.getInstance().getSupportEmail()
        .then(supportEmail => infoExtension.setHintText(infoLabel + supportEmail));
      expirationLayout.add(infoExtension);
      box.add(expirationLayout);

      const img = new qx.ui.basic.Image().set({
        decorator: new qx.ui.decoration.Decorator().set({
          radius: 50
        }),
        alignX: "center"
      });
      box.add(img);

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
        converter: data => {
          if (data) {
            expirationLayout.show();
            return osparc.utils.Utils.formatDateAndTime(new Date(data));
          }
          return "";
        }
      });
      controller.addTarget(img, "source", "email", false, {
        converter: function(data) {
          return osparc.utils.Avatar.getUrl(email.getValue(), 150);
        }
      });

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
            osparc.component.message.FlashMessenger.getInstance().logAs(msg, "INFO");
          }, this);

          req.addListenerOnce("fail", e => {
            this.__resetDataToModel();
            const error = e.getTarget().getResponse().error;
            const msg = error ? error["errors"][0].message : this.tr("Failed to update profile");
            osparc.component.message.FlashMessenger.getInstance().logAs(msg, "ERROR");
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
    }
  }
});
