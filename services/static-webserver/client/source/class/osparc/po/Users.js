/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

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

  },

  members: {
    __foundUsersLayout: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "search-users":
          control = this.__searchUsers();
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      this._createChildControlImpl("search-users");
    },

    __searchUsers: function() {
      const usersGroupBox = this.self().createGroupBox(this.tr("Search"));
      const searchUsersForm = this.__searchUsersForm();
      const form = new qx.ui.form.renderer.Single(searchUsersForm);
      usersGroupBox.add(form);

      return usersGroupBox;
    },

    __searchUsersForm: function() {
      const form = new qx.ui.form.Form();

      const userEmail = new qx.ui.form.TextField().set({
        required: true,
        placeholder: this.tr("new.user@email.address")
      });
      form.add(userEmail, this.tr("Email"));

      const searchBtn = new osparc.ui.form.FetchButton(this.tr("Search"));
      searchBtn.set({
        appearance: "form-button"
      });
      searchBtn.addListener("execute", () => {
        if (!osparc.data.Permissions.getInstance().canDo("user.users.search", true)) {
          return;
        }
        if (form.validate()) {
          if (this.__foundUsersLayout) {
            this._remove(this.__foundUsersLayout);
          }
          const params = {
            url:{
              email: userEmail.getValue()
            }
          };

          searchBtn.setFetching(true);
          osparc.data.Resources.fetch("users", "search", params)
            .then(data => {
              const foundUsersLayout = this.__foundUsersLayout = this.__createFoundUsersLayout(data);
              this._add(foundUsersLayout);
            })
            .catch(err => {
              console.error(err);
              osparc.FlashMessenger.logAs(err.message, "ERROR");
            })
            .finally(() => searchBtn.setFetching(false));
        }
      }, this);
      form.addButton(searchBtn);

      return form;
    },

    __createFoundUsersLayout: function(respData) {
      const vBox = new qx.ui.container.Composite(new qx.ui.layout.VBox(2));

      const hBox = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
        alignY: "middle"
      }));
      vBox.add(hBox);

      const respLabel = new qx.ui.basic.Label(this.tr("Found users:"));
      vBox.add(respLabel);

      const usersRespViewer = new osparc.ui.basic.JsonTreeWidget(respData, "users-data");
      const container = new qx.ui.container.Scroll();
      container.add(usersRespViewer);
      vBox.add(container);

      return vBox;
    }
  }
});
