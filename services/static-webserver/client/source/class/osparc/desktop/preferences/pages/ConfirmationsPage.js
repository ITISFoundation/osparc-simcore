/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Confirmations in preferences dialog
 */

qx.Class.define("osparc.desktop.preferences.pages.ConfirmationsPage", {
  extend: osparc.desktop.preferences.pages.BasePage,

  construct: function() {
    const iconSrc = "@FontAwesome5Solid/question-circle/24";
    const title = this.tr("Confirmation Settings");
    this.base(arguments, title, iconSrc);

    const confirmationSettings = this.__createConfirmationsSettings();
    this.add(confirmationSettings);

    if (osparc.product.Utils.showPreferencesExperimental()) {
      const experimentalSettings = this.__createExperimentalSettings();
      this.add(experimentalSettings);
    }
  },

  members: {
    __createConfirmationsSettings: function() {
      // layout
      const label = this._createHelpLabel(this.tr("Show Confirmation/Warning Message Window for the following actions:"));
      this.add(label);

      this.add(new qx.ui.core.Spacer(null, 10));

      const preferencesSettings = osparc.desktop.preferences.Preferences.getInstance();

      const box = new qx.ui.container.Composite(new qx.ui.layout.VBox(10)).set({
        paddingLeft: 10
      });

      const patchPreference = (preferenceId, preferenceField, newValue) => {
        preferenceField.setEnabled(false);
        const params = {
          url: {
            preferenceId
          },
          data: {
            "value": newValue
          }
        };
        osparc.data.Resources.fetch("preferences", "patch", params)
          .then(() => {
            preferencesSettings.set(newValue);
          })
          .catch(err => {
            console.error(err);
            osparc.component.message.FlashMessenger.logAs(err.message, "ERROR");
          })
          .finally(() => preferenceField.setEnabled(true));
      };
      const cbConfirmBackToDashboard = new qx.ui.form.CheckBox(this.tr("Go back to the Dashboard"));
      preferencesSettings.bind("confirmBackToDashboard", cbConfirmBackToDashboard, "value");
      // cbConfirmBackToDashboard.bind("value", preferencesSettings, "confirmBackToDashboard");
      preferencesSettings.addListener("changeValue", e => patchPreference("confirmBackToDashboard", preferencesSettings, e.getData()));
      box.add(cbConfirmBackToDashboard);

      const studyLabel = osparc.product.Utils.getStudyAlias();
      const cbConfirmDeleteStudy = new qx.ui.form.CheckBox(this.tr("Delete a ") + studyLabel);
      preferencesSettings.bind("confirmDeleteStudy", cbConfirmDeleteStudy, "value");
      cbConfirmDeleteStudy.bind("value", preferencesSettings, "confirmDeleteStudy");
      cbConfirmDeleteStudy.addListener("changeValue", e => {
        if (!e.getData()) {
          const msg = this.tr("Warning: deleting a ") + studyLabel + this.tr(" cannot be undone");
          const win = new osparc.ui.window.Confirmation(msg).set({
            confirmText: this.tr("Understood"),
            confirmAction: "delete"
          });
          win.center();
          win.open();
          win.addListener("close", () => {
            if (!win.getConfirmed()) {
              cbConfirmDeleteStudy.setValue(true);
            }
          }, this);
        }
      }, this);
      box.add(cbConfirmDeleteStudy);

      if (!(osparc.product.Utils.isProduct("tis") || osparc.product.Utils.isProduct("s4llite"))) {
        const cbConfirmDeleteNode = new qx.ui.form.CheckBox(this.tr("Delete a Node"));
        preferencesSettings.bind("confirmDeleteNode", cbConfirmDeleteNode, "value");
        cbConfirmDeleteNode.bind("value", preferencesSettings, "confirmDeleteNode");
        cbConfirmDeleteNode.addListener("changeValue", e => {
          if (!e.getData()) {
            const msg = this.tr("Warning: deleting a node cannot be undone");
            const win = new osparc.ui.window.Confirmation(msg).set({
              confirmText: this.tr("Understood"),
              confirmAction: "delete"
            });
            win.center();
            win.open();
            win.addListener("close", () => {
              if (!win.getConfirmed()) {
                cbConfirmDeleteNode.setValue(true);
              }
            }, this);
          }
        }, this);
        box.add(cbConfirmDeleteNode);

        const cbConfirmStopNode = new qx.ui.form.CheckBox(this.tr("Stop Node"));
        preferencesSettings.bind("confirmStopNode", cbConfirmStopNode, "value");
        cbConfirmStopNode.bind("value", preferencesSettings, "confirmStopNode");
        box.add(cbConfirmStopNode);

        const cbSnapNodeToGrid = new qx.ui.form.CheckBox(this.tr("Snap Node to grid"));
        preferencesSettings.bind("snapNodeToGrid", cbSnapNodeToGrid, "value");
        cbSnapNodeToGrid.bind("value", preferencesSettings, "snapNodeToGrid");
        box.add(cbSnapNodeToGrid);
      }

      return box;
    },

    __createExperimentalSettings: function() {
      // layout
      const box = this._createSectionBox("Experimental preferences");

      const label = this._createHelpLabel(this.tr(
        "This is a list of experimental preferences"
      ));
      box.add(label);

      const preferencesSettings = osparc.desktop.preferences.Preferences.getInstance();

      const cbAutoPorts = new qx.ui.form.CheckBox(this.tr("Connect ports automatically"));
      preferencesSettings.bind("autoConnectPorts", cbAutoPorts, "value");
      cbAutoPorts.bind("value", preferencesSettings, "autoConnectPorts");
      box.add(cbAutoPorts);

      return box;
    }
  }
});
