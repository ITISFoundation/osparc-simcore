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

    const walletIndicatorSettings = this.__createCreditsIndicatorSettings();
    this.add(walletIndicatorSettings);
  },

  statics: {
    patchPreference: function(preferenceId, preferenceField, newValue) {
      const preferencesSettings = osparc.Preferences.getInstance();

      const oldValue = preferencesSettings.get(preferenceId);
      if (newValue === oldValue) {
        return;
      }

      preferenceField.setEnabled(false);
      osparc.Preferences.patchPreference(preferenceId, newValue)
        .then(() => preferencesSettings.set(preferenceId, newValue))
        .catch(err => {
          console.error(err);
          osparc.FlashMessenger.logAs(err.message, "ERROR");
          preferenceField.setValue(oldValue);
        })
        .finally(() => preferenceField.setEnabled(true));
    }
  },

  members: {
    __createConfirmationsSettings: function() {
      // layout
      const label = this._createHelpLabel(this.tr("Ask for confirmation for the following actions:"));
      this.add(label);

      this.add(new qx.ui.core.Spacer(null, 10));

      const preferencesSettings = osparc.Preferences.getInstance();

      const box = new qx.ui.container.Composite(new qx.ui.layout.VBox(10)).set({
        paddingLeft: 10
      });

      const cbConfirmBackToDashboard = new qx.ui.form.CheckBox(this.tr("Go back to the Dashboard"));
      preferencesSettings.bind("confirmBackToDashboard", cbConfirmBackToDashboard, "value");
      cbConfirmBackToDashboard.addListener("changeValue", e => this.self().patchPreference("confirmBackToDashboard", cbConfirmBackToDashboard, e.getData()));
      box.add(cbConfirmBackToDashboard);

      const studyAlias = osparc.product.Utils.getStudyAlias({firstUpperCase: true});
      const cbConfirmDeleteStudy = new qx.ui.form.CheckBox(this.tr("Delete a ") + studyAlias);
      preferencesSettings.bind("confirmDeleteStudy", cbConfirmDeleteStudy, "value");
      cbConfirmDeleteStudy.addListener("changeValue", e => {
        if (e.getData()) {
          this.self().patchPreference("confirmDeleteStudy", cbConfirmDeleteStudy, true);
        } else {
          const msg = this.tr("Warning: deleting a ") + studyAlias + this.tr(" cannot be undone");
          const win = new osparc.ui.window.Confirmation(msg).set({
            confirmText: this.tr("Understood"),
            confirmAction: "delete"
          });
          win.center();
          win.open();
          win.addListener("close", () => {
            if (win.getConfirmed()) {
              this.self().patchPreference("confirmDeleteStudy", cbConfirmDeleteStudy, false);
            } else {
              cbConfirmDeleteStudy.setValue(true);
            }
          }, this);
        }
      }, this);
      box.add(cbConfirmDeleteStudy);

      if (!(osparc.product.Utils.isProduct("tis") || osparc.product.Utils.isProduct("s4llite"))) {
        const cbConfirmDeleteNode = new qx.ui.form.CheckBox(this.tr("Delete a Node"));
        preferencesSettings.bind("confirmDeleteNode", cbConfirmDeleteNode, "value");
        cbConfirmDeleteNode.addListener("changeValue", e => {
          if (e.getData()) {
            this.self().patchPreference("confirmDeleteNode", cbConfirmDeleteNode, true);
          } else {
            const msg = this.tr("Warning: deleting a node cannot be undone");
            const win = new osparc.ui.window.Confirmation(msg).set({
              confirmText: this.tr("Understood"),
              confirmAction: "delete"
            });
            win.center();
            win.open();
            win.addListener("close", () => {
              if (win.getConfirmed()) {
                this.self().patchPreference("confirmDeleteNode", cbConfirmDeleteNode, false);
              } else {
                cbConfirmDeleteNode.setValue(true);
              }
            }, this);
          }
        }, this);
        box.add(cbConfirmDeleteNode);

        const cbConfirmStopNode = new qx.ui.form.CheckBox(this.tr("Stop Node"));
        preferencesSettings.bind("confirmStopNode", cbConfirmStopNode, "value");
        cbConfirmStopNode.addListener("changeValue", e => this.self().patchPreference("confirmStopNode", cbConfirmStopNode, e.getData()));
        box.add(cbConfirmStopNode);

        const cbSnapNodeToGrid = new qx.ui.form.CheckBox(this.tr("Snap Node to grid"));
        preferencesSettings.bind("snapNodeToGrid", cbSnapNodeToGrid, "value");
        cbSnapNodeToGrid.addListener("changeValue", e => this.self().patchPreference("snapNodeToGrid", cbSnapNodeToGrid, e.getData()));
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

      const preferencesSettings = osparc.Preferences.getInstance();

      const cbAutoPorts = new qx.ui.form.CheckBox(this.tr("Connect ports automatically"));
      preferencesSettings.bind("autoConnectPorts", cbAutoPorts, "value");
      cbAutoPorts.addListener("changeValue", e => this.self().patchPreference("autoConnectPorts", cbAutoPorts, e.getData()));
      box.add(cbAutoPorts);

      return box;
    },

    __createCreditsIndicatorSettings: function() {
      // layout
      const box = this._createSectionBox(this.tr("Credits Indicator"));

      const label = this._createHelpLabel(this.tr(
        "Choose how you want the Credits Indicator to look like and when it is shown"
      ));
      box.add(label);

      const preferencesSettings = osparc.Preferences.getInstance();

      const walletIndicatorModeSB = new qx.ui.form.SelectBox().set({
        allowGrowX: false
      });
      [{
        id: "both",
        label: "Both"
      }, {
        id: "text",
        label: "Text"
      }, {
        id: "bar",
        label: "Bar"
      }].forEach(options => {
        const lItem = new qx.ui.form.ListItem(options.label, null, options.id);
        walletIndicatorModeSB.add(lItem);
      });
      const value = preferencesSettings.getWalletIndicatorMode();
      walletIndicatorModeSB.getSelectables(selectable => {
        if (selectable.getModel() === value) {
          walletIndicatorModeSB.setSelected([selectable]);
        }
      });
      walletIndicatorModeSB.addListener("changeValue", e => {
        const selectable = e.getData();
        osparc.Preferences.patchPreference("walletIndicatorMode", selectable.getModel());
      });
      box.add(walletIndicatorModeSB);

      return box;
    }
  }
});
