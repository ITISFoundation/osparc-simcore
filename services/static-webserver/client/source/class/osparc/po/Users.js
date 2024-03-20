/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Pedro Crespo-Valero (pcrespov)
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.po.Users", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    this.__buildLayout();
  },

  statics: {
    createGroupBox: function(title) {
      const box = new qx.ui.groupbox.GroupBox(title).set({
        appearance: "settings-groupbox",
        layout: new qx.ui.layout.VBox(5),
        alignX: "center"
      });
      box.getChildControl("legend").set({
        font: "text-14"
      });
      box.getChildControl("frame").set({
        backgroundColor: "transparent"
      });
      return box;
    },

    createHelpLabel: function(text) {
      const label = new qx.ui.basic.Label(text).set({
        font: "text-13",
        rich: true,
        alignX: "left"
      });
      return label;
    }
  },

  members: {
    __generatedUsersLayout: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "create-users":
          control = this.__createUsers();
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      this._createChildControlImpl("create-users");
    },

    __createUsers: function() {
      const usersGroupBox = this.self().createGroupBox(this.tr("Create users"));

      const disclaimer = this.self().createHelpLabel(this.tr("There is no users required in this product/deployment.")).set({
        textColor: "info"
      });
      disclaimer.exclude();
      const config = osparc.store.Store.getInstance().get("config");
      if ("users_required" in config && config["users_required"] === false) {
        disclaimer.show();
      }
      usersGroupBox.add(disclaimer);

      const newTokenForm = this.__createUsersForm();
      const form = new qx.ui.form.renderer.Single(newTokenForm);
      usersGroupBox.add(form);

      return usersGroupBox;
    },

    __createUsersForm: function() {
      const form = new qx.ui.form.Form();

      const userEmail = new qx.ui.form.TextField().set({
        required: true,
        placeholder: this.tr("new.user@email.address")
      });
      form.add(userEmail, this.tr("User Email"));

      const generateUsersBtn = new osparc.ui.form.FetchButton(this.tr("Search"));
      generateUsersBtn.set({
        appearance: "form-button"
      });
      generateUsersBtn.addListener("execute", () => {
        if (!osparc.data.Permissions.getInstance().canDo("user.users.generate", true)) {
          return;
        }
        if (form.validate()) {
          if (this.__generatedUsersLayout) {
            this._remove(this.__generatedUsersLayout);
          }
          const params = {
            data: {
              "email": userEmail.getValue()
            }
          };

          generateUsersBtn.setFetching(true);
          osparc.data.Resources.fetch("users", "post", params)
            .then(data => {
              const generatedUsersLayout = this.__generatedUsersLayout = this.__createGeneratedUsersLayout(data);
              this._add(generatedUsersLayout);
            })
            .catch(err => {
              console.error(err);
              osparc.FlashMessenger.logAs(err.message, "ERROR");
            })
            .finally(() => generateUsersBtn.setFetching(false));
        }
      }, this);
      form.addButton(generateUsersBtn);

      return form;
    },

    __createGeneratedUsersLayout: function(respData) {
      const vBox = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));

      const hBox = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
        alignY: "middle"
      }));
      vBox.add(hBox);

      const usersField = new qx.ui.form.TextField(respData["users_link"]).set({
        readOnly: true
      });
      hBox.add(usersField, {
        flex: 1
      });


      const respLabel = new qx.ui.basic.Label(this.tr("Data encrypted in the users"));
      vBox.add(respLabel);

      const printData = osparc.utils.Utils.deepCloneObject(respData);
      delete printData["users_link"];
      const usersRespViewer = new osparc.ui.basic.JsonTreeWidget(respData, "users-data");
      const container = new qx.ui.container.Scroll();
      container.add(usersRespViewer);
      vBox.add(container);

      return vBox;
    }
  }
});
