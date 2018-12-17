/**
 *  User profile in preferences dialog
 *
 *  - user name, surname, email, avatar
 *
 */
/* eslint no-warning-comments: "off" */
qx.Class.define("qxapp.desktop.preferences.pages.ProfilePage", {
  extend:qxapp.desktop.preferences.pages.BasePage,

  construct: function() {
    const iconSrc = "@FontAwesome5Solid/sliders-h/24";
    const title = this.tr("Profile");
    this.base(arguments, title, iconSrc);

    this.add(this.__createProfileUser());
  },

  members: {

    __createProfileUser: function() {
      // layout
      let box = this._createSectionBox("User");

      let email = new qx.ui.form.TextField().set({
        placeholder: this.tr("Email")
      });

      let firstName = new qx.ui.form.TextField().set({
        placeholder: this.tr("First Name")
      });

      let lastName = new qx.ui.form.TextField().set({
        placeholder: this.tr("Last Name")
      });

      let role = new qx.ui.form.TextField().set({
        readOnly: true
      });

      let form = new qx.ui.form.Form();
      form.add(email, "", null, "email");
      form.add(firstName, "", null, "firstName");
      form.add(lastName, "", null, "lastName");
      form.add(role, "", null, "role");

      box.add(new qx.ui.form.renderer.Single(form));

      let img = new qx.ui.basic.Image().set({
        alignX: "center"
      });
      box.add(img);

      let updateBtn = new qx.ui.form.Button("Update Profile").set({
        allowGrowX: false
      });
      box.add(updateBtn);

      // binding to a model
      let raw = {
        "first_name": null,
        "last_name": null,
        "email": null,
        "role": null
      };

      if (qx.core.Environment.get("qx.debug")) {
        raw = {
          "first_name": "Bizzy",
          "last_name": "Zastrow",
          "email": "bizzy@itis.ethz.ch",
          "role": "Tester"
        };
      }
      let model = qx.data.marshal.Json.createModel(raw);
      let controller = new qx.data.controller.Object(model);

      controller.addTarget(email, "value", "email", true);
      controller.addTarget(firstName, "value", "first_name", true, null, {
        converter: function(data) {
          return data.replace(/^\w/, c => c.toUpperCase());
        }
      });
      controller.addTarget(lastName, "value", "last_name", true);
      controller.addTarget(role, "value", "role", false);
      controller.addTarget(img, "source", "email", false, {
        converter: function(data) {
          return qxapp.utils.Avatar.getUrl(email.getValue(), 150);
        }
      });

      // validation
      let manager = new qx.ui.form.validation.Manager();
      manager.add(email, qx.util.Validate.email());
      manager.add(firstName, qx.util.Validate.string());
      manager.add(lastName, qx.util.Validate.string());

      // update trigger
      updateBtn.addListenerOnce("execute", function() {
        if (manager.validate()) {
          let request = new qxapp.io.request.ApiRequest("/auth/change-email", "POST");
          request.setRequestData({
            "email": model.email
          });

          request.addListenerOnce("success", function(e) {
            const res = e.getTarget().getResponse();
            qxapp.component.widget.FlashMessenger.getInstance().log(res.data);
          }, this);

          request.addListenerOnce("fail", function(e) {
            const res = e.getTarget().getResponse();
            const msg = res.error|| "Failed to update email";
            email.set({
              invalidMessage: msg,
              valid: false
            });
          }, this);

          request.send();
        }
      }, this);

      // get values from server
      let request = new qxapp.io.request.ApiRequest("/me", "GET");
      request.addListenerOnce("success", function(e) {
        const data = e.getTarget().getResponse()["data"];
        model.set({
          "first_name": data["first_name"],
          "last_name": data["last_name"],
          "email": data["login"],
          "role": data["role"]
        });
      });

      request.addListenerOnce("fail", function(e) {
        const res = e.getTarget().getResponse();
        const msg = res.error || "Failed to update profile";
        qxapp.component.widget.FlashMessenger.getInstance().logAs(msg, "Error", "user");
      });

      request.send();
      return box;
    }
  }
});
