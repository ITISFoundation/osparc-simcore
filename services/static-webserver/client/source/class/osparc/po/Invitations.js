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

qx.Class.define("osparc.po.Invitations", {
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
    __generatedInvitationLayout: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "create-invitation":
          control = this.__createInvitations();
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      this._createChildControlImpl("create-invitation");
    },

    __createInvitations: function() {
      const invitationGroupBox = this.self().createGroupBox(this.tr("Create invitation"));

      const disclaimer = this.self().createHelpLabel(this.tr("There is no invitation required in this product/deployment.")).set({
        textColor: "warning-yellow"
      });
      disclaimer.exclude();
      osparc.data.Resources.getOne("config")
        .then(config => {
          if ("invitation_required" in config && config["invitation_required"] === false) {
            disclaimer.show();
          }
        });
      invitationGroupBox.add(disclaimer);

      const newTokenForm = this.__createInvitationForm();
      const form = new qx.ui.form.renderer.Single(newTokenForm);
      invitationGroupBox.add(form);

      return invitationGroupBox;
    },

    __createInvitationForm: function() {
      const form = new qx.ui.form.Form();

      const userEmail = new qx.ui.form.TextField().set({
        placeholder: this.tr("new.user@email.address")
      });
      form.add(userEmail, this.tr("User Email"));

      const withExpiration = new qx.ui.form.CheckBox().set({
        value: false
      });
      form.add(withExpiration, this.tr("With expiration"));

      const trialDays = new qx.ui.form.Spinner().set({
        minimum: 1,
        maximum: 1000,
        value: 1
      });
      withExpiration.bind("value", trialDays, "visibility", {
        converter: val => val ? "visible" : "excluded"
      });
      form.add(trialDays, this.tr("Trial Days"));

      const generateInvitationBtn = new osparc.ui.form.FetchButton(this.tr("Generate"));
      generateInvitationBtn.addListener("execute", () => {
        if (!osparc.data.Permissions.getInstance().canDo("user.invitation.generate", true)) {
          return;
        }
        if (this.__generatedInvitationLayout) {
          this._remove(this.__generatedInvitationLayout);
        }
        const params = {
          data: {
            "guest": userEmail.getValue()
          }
        };
        if (withExpiration.getValue()) {
          params.data["trialAccountDays"] = trialDays.getValue();
        }
        generateInvitationBtn.setFetching(true);
        osparc.data.Resources.fetch("invitations", "post", params)
          .then(data => {
            const generatedInvitationLayout = this.__generatedInvitationLayout = this.__createGeneratedInvitationLayout(data);
            this._add(generatedInvitationLayout);
          })
          .catch(err => {
            console.error(err);
            osparc.FlashMessenger.logAs(err.message, "ERROR");
          })
          .finally(() => generateInvitationBtn.setFetching(false));
      }, this);
      form.addButton(generateInvitationBtn);

      return form;
    },

    __createGeneratedInvitationLayout: function(respData) {
      const vBox = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));

      const label = new qx.ui.basic.Label().set({
        value: this.tr("Remember that this is a one time use link")
      });
      vBox.add(label);

      const hBox = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
        alignY: "middle"
      }));
      vBox.add(hBox);

      const invitationField = new qx.ui.form.TextField(respData["invitation_link"]).set({
        readOnly: true
      });
      hBox.add(invitationField, {
        flex: 1
      });

      const copyInvitationBtn = new qx.ui.form.Button(this.tr("Copy invitation link"));
      copyInvitationBtn.addListener("execute", () => {
        if (osparc.utils.Utils.copyTextToClipboard(respData["invitation_link"])) {
          copyInvitationBtn.setIcon("@FontAwesome5Solid/check/12");
        }
      });
      hBox.add(copyInvitationBtn);

      const respLabel = new qx.ui.basic.Label(this.tr("Data encrypted in the invitation"));
      vBox.add(respLabel);

      const printData = osparc.utils.Utils.deepCloneObject(respData);
      delete printData["invitation_link"];
      const invitationRespViewer = new osparc.ui.basic.JsonTreeWidget(respData, "invitation-data");
      const container = new qx.ui.container.Scroll();
      container.add(invitationRespViewer);
      vBox.add(container);

      return vBox;
    }
  }
});
