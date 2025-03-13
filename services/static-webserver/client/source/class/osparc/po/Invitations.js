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
  extend: osparc.po.BaseView,

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "create-invitation":
          control = this.__createInvitations();
          this._add(control);
          break;
        case "invitation-container": {
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
          this._add(control, {
            flex: 1
          });
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    _buildLayout: function() {
      this.getChildControl("create-invitation");
      this.getChildControl("invitation-container");
    },

    __createInvitations: function() {
      const invitationGroupBox = osparc.po.BaseView.createGroupBox(this.tr("Create invitation"));

      const disclaimer = osparc.po.BaseView.createHelpLabel(this.tr("There is no invitation required in this product/deployment."));
      disclaimer.exclude();
      const config = osparc.store.Store.getInstance().get("config");
      if ("invitation_required" in config && config["invitation_required"] === false) {
        disclaimer.show();
      }
      invitationGroupBox.add(disclaimer);

      const newTokenForm = this.__createInvitationForm();
      const form = new qx.ui.form.renderer.Single(newTokenForm);
      invitationGroupBox.add(form);

      return invitationGroupBox;
    },

    __createInvitationForm: function() {
      const form = new qx.ui.form.Form();

      const userEmail = new qx.ui.form.TextField().set({
        required: true,
        placeholder: this.tr("new.user@email.address")
      });
      form.add(userEmail, this.tr("User Email"));

      const extraCreditsInUsd = new qx.ui.form.Spinner().set({
        minimum: 0,
        maximum: 1000,
        value: 100
      });
      form.add(extraCreditsInUsd, this.tr("Welcome Credits (USD)"));

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
      generateInvitationBtn.set({
        appearance: "form-button"
      });
      generateInvitationBtn.addListener("execute", () => {
        if (!osparc.data.Permissions.getInstance().canDo("user.invitation.generate", true)) {
          return;
        }
        if (form.validate()) {
          generateInvitationBtn.setFetching(true);
          const params = {
            data: {
              "guest": userEmail.getValue()
            }
          };
          if (extraCreditsInUsd.getValue() > 0) {
            params.data["extraCreditsInUsd"] = extraCreditsInUsd.getValue();
          }
          if (withExpiration.getValue()) {
            params.data["trialAccountDays"] = trialDays.getValue();
          }
          osparc.data.Resources.fetch("invitations", "post", params)
            .then(data => {
              this.__populateInvitationLayout(data);
            })
            .catch(err => {
              console.error(err);
              osparc.FlashMessenger.logError(err);
            })
            .finally(() => generateInvitationBtn.setFetching(false));
        }
      }, this);
      form.addButton(generateInvitationBtn);

      return form;
    },

    __populateInvitationLayout: function(respData) {
      const vBox = this.getChildControl("invitation-container");
      vBox.removeAll();

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
      copyInvitationBtn.set({appearance: "form-button-outlined"});
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
      vBox.add(container, {
        flex: 1
      });
    }
  }
});
