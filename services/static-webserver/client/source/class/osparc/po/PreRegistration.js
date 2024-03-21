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

qx.Class.define("osparc.po.PreRegistration", {
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
    __preRegistrationLayout: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "search-preregistration":
          control = this.__searchPreRegistration();
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      this._createChildControlImpl("search-preregistration");
    },

    __searchPreRegistration: function() {
      const _group_box = this.self().createGroupBox(this.tr("Pre-Registration"));
      const _form = this.__preRegistrationForm();
      const _formRenderer = new qx.ui.form.renderer.Single(_form);
      _group_box.add(_formRenderer);

      return _group_box;
    },

    __preRegistrationForm: function() {
      const form = new qx.ui.form.Form();
      const requestAccountData = new qx.ui.form.TextArea().set({
        required: true,
        minHeight: 200,
        placeholder: this.tr("Copy&Paste the Request Account Form in JSON format here ...")
      });
      form.add(requestAccountData, this.tr("Request Form"));

      const submitBtn = new osparc.ui.form.FetchButton(this.tr("Submit"));
      submitBtn.set({
        appearance: "form-button"
      });

      submitBtn.addListener("execute", () => {
        if (!osparc.data.Permissions.getInstance().canDo("user.users.pre-register", true)) {
          return;
        }
        if (form.validate()) {
          if (this.__preRegistrationLayout) {
            this._remove(this.__preRegistrationLayout);
          }

          const params = {
            data: JSON.parse(requestAccountData.getValue())
          };
          submitBtn.setFetching(true);
          osparc.data.Resources.fetch("users", "preRegister", params)
            .then(data => {
              const _layout = this.__preRegistrationLayout = this.__createPreRegistrationLayout(data);
              this._add(_layout);
            })
            .catch(err => {
              console.error(err);
              osparc.FlashMessenger.logAs(err.message, "ERROR");
            })
            .finally(() => submitBtn.setFetching(false));
        }
      }, this);
      form.addButton(submitBtn);

      return form;
    },

    __createPreRegistrationLayout: function(respData) {
      const vBox = new qx.ui.container.Composite(new qx.ui.layout.VBox(2));

      const hBox = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
        alignY: "middle"
      }));
      vBox.add(hBox);

      const respLabel = new qx.ui.basic.Label(this.tr("Pre-Registered as:"));
      vBox.add(respLabel);

      const preregistrationRespViewer = new osparc.ui.basic.JsonTreeWidget(respData, "preregistration-data");
      const container = new qx.ui.container.Scroll();
      container.add(preregistrationRespViewer);
      vBox.add(container);

      return vBox;
    }
  }
});
