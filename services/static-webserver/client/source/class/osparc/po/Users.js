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
  extend: osparc.po.BaseView,

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "search-users":
          control = this.__searchUsers();
          this._add(control);
          break;
        case "finding-status":
          control = new qx.ui.basic.Label();
          this._add(control);
          break;
        case "found-users-container":
          control = new qx.ui.container.Scroll();
          this._add(control, {
            flex: 1
          });
          break;
      }
      return control || this.base(arguments, id);
    },

    _buildLayout: function() {
      this.getChildControl("search-users");
      this.getChildControl("finding-status");
      this.getChildControl("found-users-container");
    },

    __searchUsers: function() {
      const usersGroupBox = osparc.po.BaseView.createGroupBox(this.tr("Search"));

      const searchUsersForm = this.__searchUsersForm();
      const form = new qx.ui.form.renderer.Single(searchUsersForm);
      usersGroupBox.add(form);

      return usersGroupBox;
    },

    __searchUsersForm: function() {
      const form = new qx.ui.form.Form();

      const userEmail = new qx.ui.form.TextField().set({
        required: true,
        placeholder: this.tr("user@email.address or user@*")
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
          searchBtn.setFetching(true);
          const findingStatus = this.getChildControl("finding-status");
          findingStatus.setValue(this.tr("Searching users..."));
          const params = {
            url: {
              email: userEmail.getValue()
            }
          };
          osparc.data.Resources.fetch("poUsers", "search", params)
            .then(data => {
              findingStatus.setValue(data.length + this.tr(" user(s) found"));
              this.__populateFoundUsersLayout(data);
            })
            .catch(err => {
              findingStatus.setValue(this.tr("Error searching users"));
              console.error(err);
              osparc.FlashMessenger.logAs(err.message, "ERROR");
            })
            .finally(() => searchBtn.setFetching(false));
        }
      }, this);
      form.addButton(searchBtn);

      return form;
    },

    __populateFoundUsersLayout: function(respData) {
      const foundUsersContainer = this.getChildControl("found-users-container");
      osparc.utils.Utils.removeAllChildren(foundUsersContainer);
      const usersRespViewer = new osparc.ui.basic.JsonTreeWidget(respData, "users-data");
      foundUsersContainer.add(usersRespViewer);
    }
  }
});
