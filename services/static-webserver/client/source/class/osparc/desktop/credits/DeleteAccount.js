/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.desktop.credits.DeleteAccount", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments, this.tr("Delete Account"));

    this._setLayout(new qx.ui.layout.VBox(15));

    this.__buildLayout();
  },

  events: {
    "deleted": "qx.event.type.Event",
    "cancel": "qx.event.type.Event"
  },

  members: {
    __form: null,

    _createChildControlImpl: function(id) {
      let control = null;
      switch (id) {
        case "intro-text": {
          const text = this.tr("\
            This account will be deleted in 14 days.<br>\
            During this period, if you want to recover it or delete your\
            data right away, please send us an email to support@osparc.com.\
          ");
          control = new qx.ui.basic.Label().set({
            value: text,
            font: "text-14",
            rich: true,
            wrap: true
          });
          this._add(control);
          break;
        }
        case "delete-form":
          control = this.__createDeleteForm();
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      this.getChildControl("intro-text");
      this.getChildControl("delete-form");
    },

    __createDeleteForm: function() {
      const form = this.__form = new qx.ui.form.Form();

      const email = new qx.ui.form.TextField().set({
        placeholder: this.tr("Your email"),
        required: true
      });
      form.add(email, "Email address", qx.util.Validate.email(), "email");
      this.addListener("appear", () => email.focus());

      const password = new osparc.ui.form.PasswordField().set({
        placeholder: this.tr("Your password"),
        required: true
      });
      form.add(password, "Password", null, "password");

      const cancelBtn = new qx.ui.form.Button(this.tr("Cancel"));
      cancelBtn.addListener("execute", () => this.fireEvent("cancel"), this);
      form.addButton(cancelBtn);

      const deleteBtn = new osparc.ui.form.FetchButton(this.tr("Delete Account")).set({
        appearance: "danger-button"
      });
      deleteBtn.addListener("execute", () => {
        if (form.validate()) {
          this.__requestDeletion(form, deleteBtn);
        }
      }, this);
      form.addButton(deleteBtn);

      const formRenderer = new qx.ui.form.renderer.Single(form);
      return formRenderer;
    },

    __requestDeletion: function(form, deleteBtn) {
      deleteBtn.setFetching(true);
      const params = {
        data: {
          email: form.getItem("email").getValue(),
          password: form.getItem("password").getValue()
        }
      };
      osparc.data.Resources.fetch("auth", "unregister", params)
        .then(() => {
          const msg = this.tr("You account will be deleted in 14 days");
          osparc.FlashMessenger.getInstance().logAs(msg, "INFO");
          this.fireEvent("deleted");
        })
        .catch(err => {
          console.error(err);
          osparc.FlashMessenger.logAs(err.message, "ERROR");
        })
        .finally(() => deleteBtn.setFetching(false));
    }
  }
});
