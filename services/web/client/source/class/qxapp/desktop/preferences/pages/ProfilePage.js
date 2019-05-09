/* ************************************************************************

   qxapp - the simcore frontend

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

qx.Class.define("qxapp.desktop.preferences.pages.ProfilePage", {
  extend:qxapp.desktop.preferences.pages.BasePage,

  construct: function() {
    const iconSrc = "@FontAwesome5Solid/sliders-h/24";
    const title = this.tr("Profile");
    this.base(arguments, title, iconSrc);

    this.__userProfileData = null;
    this.__userProfileModel = null;

    this.add(this.__createProfileUser());
  },

  members: {
    __userProfileData: null,
    __userProfileModel: null,

    __createProfileUser: function() {
      // layout
      const box = this._createSectionBox("User");

      const email = new qx.ui.form.TextField().set({
        placeholder: this.tr("Email")
      });

      const firstName = new qx.ui.form.TextField().set({
        placeholder: this.tr("First Name")
      });

      const lastName = new qx.ui.form.TextField().set({
        placeholder: this.tr("Last Name")
      });

      const role = new qx.ui.form.TextField().set({
        readOnly: true
      });

      const form = new qx.ui.form.Form();
      form.add(email, "", null, "email");
      form.add(firstName, "", null, "firstName");
      form.add(lastName, "", null, "lastName");
      form.add(role, "", null, "role");

      box.add(new qx.ui.form.renderer.Single(form));

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
        "role": null
      };

      if (qx.core.Environment.get("qx.debug")) {
        raw = {
          "firstName": "Bizzy",
          "lastName": "Zastrow",
          "email": "bizzy@itis.ethz.ch",
          "role": "Tester"
        };
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
      controller.addTarget(img, "source", "email", false, {
        converter: function(data) {
          return qxapp.utils.Avatar.getUrl(email.getValue(), 150);
        }
      });

      // validation
      const manager = new qx.ui.form.validation.Manager();
      manager.add(email, qx.util.Validate.email());
      [firstName, lastName].forEach(field => {
        manager.add(field, qx.util.Validate.regExp(/[^\.\d]+/), this.tr("Avoid dots or numbers in text"));
      });

      const updateBtn = new qx.ui.form.Button("Update Profile").set({
        allowGrowX: false
      });
      box.add(updateBtn);

      // update trigger
      updateBtn.addListener("execute", () => {
        if (!qxapp.data.Permissions.getInstance().canDo("preferences.user.update", true)) {
          this.__resetDataToModel();
          return;
        }

        if (manager.validate()) {
          const emailReq = new qxapp.io.request.ApiRequest("/auth/change-email", "POST");
          emailReq.setRequestData({
            "email": model.getEmail()
          });

          const profileReq = new qxapp.io.request.ApiRequest("/me", "PUT");
          profileReq.setRequestData({
            "first_name": model.getFirstName(),
            "last_name": model.getLastName()
          });

          [emailReq, profileReq].forEach(req => {
            // requests
            req.addListenerOnce("success", e => {
              const res = e.getTarget().getResponse();
              if (res && res.data) {
                qxapp.component.widget.FlashMessenger.getInstance().log(res.data);
              }
            }, this);

            req.addListenerOnce("fail", e => {
              // FIXME: should revert to old?? or GET? Store might resolve this??
              this.__resetDataToModel();
              const error = e.getTarget().getResponse().error;
              const msg = error ? error["errors"][0].message : this.tr("Failed to update profile");
              qxapp.component.widget.FlashMessenger.getInstance().logAs(msg, "ERROR");
            }, this);

            req.send();
          });
        }
      }, this);

      this.__getValuesFromServer();

      return box;
    },

    __getValuesFromServer: function() {
      // get values from server
      const request = new qxapp.io.request.ApiRequest("/me", "GET");
      request.addListenerOnce("success", e => {
        const data = e.getTarget().getResponse()["data"];
        this.__setDataToModel(data);
      }, this);

      request.addListenerOnce("fail", e => {
        const error = e.getTarget().getResponse().error;
        const msg = error ? error["errors"][0].message : this.tr("Failed to get profile");
        qxapp.component.widget.FlashMessenger.getInstance().logAs(msg, "ERROR", "user");
      });

      request.send();
    },

    __setDataToModel: function(data) {
      if (data) {
        this.__userProfileData = data;
        this.__userProfileModel.set({
          "firstName": data["first_name"] || "",
          "lastName": data["last_name"] || "",
          "email": data["login"],
          "role": data["role"] || ""
        });
      }
    },

    __resetDataToModel: function() {
      this.__setDataToModel(this.__userProfileData);
    }
  }
});
