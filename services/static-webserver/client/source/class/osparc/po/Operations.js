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

qx.Class.define("osparc.po.Operations", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    const grid = new qx.ui.layout.Grid(20, 20);
    grid.setColumnFlex(0, 1);
    grid.setColumnFlex(1, 1);
    this._setLayout(grid);

    this.__buildLayout();
  },

  statics: {
    createGroupBox: function(title) {
      const box = new qx.ui.groupbox.GroupBox(title).set({
        appearance: "settings-groupbox",
        layout: new qx.ui.layout.VBox(10),
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
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "create-invitation":
          control = this.__createInvitations();
          break;
      }
      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      this._createChildControlImpl("create-invitation");
    },

    __createInvitationForm: function() {
      const form = new qx.ui.form.Form();

      const userEmail = new qx.ui.form.TextField().set({
        placeholder: this.tr("Input your token key")
      });
      form.add(userEmail, this.tr("User Email"));

      const trialDays = new qx.ui.form.Spinner().set({
        minimum: 0,
        maximum: 1000,
        value: 0
      });
      form.add(trialDays, this.tr("Trial Days"));

      const generateInvitationBtn = new osparc.ui.form.FetchButton(this.tr("Generate"));
      generateInvitationBtn.addListener("execute", () => {
        if (!osparc.data.Permissions.getInstance().canDo("user.invitation.generate", true)) {
          return;
        }
        const params = {
          data: {
            "guest": userEmail.getValue(),
            "trialAccountDays": trialDays.getValue()
          }
        };
        generateInvitationBtn.setFetching(true);
        osparc.data.Resources.fetch("invitations", "get", params)
          .then(data => console.log(data))
          .catch(err => {
            console.error(err);
            osparc.FlashMessenger.logAs(err.message, "ERROR");
          })
          .finally(() => generateInvitationBtn.setFetching(false));
      }, this);
      form.addButton(generateInvitationBtn);

      return form;
    },

    __createInvitations: function() {
      const invitationGroupBox = this.createGroupBox(this.tr("Create invitation"));

      const label = this.createHelpLabel(this.tr("This is a list of the 'statics' resources"));
      invitationGroupBox.add(label);

      const newTokenForm = this.__createInvitationForm();
      const form = new qx.ui.form.renderer.Single(newTokenForm);
      invitationGroupBox.add(form);

      return invitationGroupBox;
    }
  }
});
