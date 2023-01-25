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

    const experimentalSettings = this.__createConfirmationsSettings();
    this.add(experimentalSettings);
  },

  members: {
    __createConfirmationsSettings: function() {
      // layout
      const label = this._createHelpLabel(this.tr("Provide warnings for the following actions:"));
      this.add(label);

      this.add(new qx.ui.core.Spacer(null, 10));

      const preferencesSettings = osparc.desktop.preferences.Preferences.getInstance();

      const box = new qx.ui.container.Composite(new qx.ui.layout.VBox(10)).set({
        paddingLeft: 10
      });

      const cbConfirmBackToDashboard = new qx.ui.form.CheckBox(this.tr("Go back to the Dashboard"));
      preferencesSettings.bind("confirmBackToDashboard", cbConfirmBackToDashboard, "value");
      cbConfirmBackToDashboard.bind("value", preferencesSettings, "confirmBackToDashboard");
      box.add(cbConfirmBackToDashboard);

      const studyLabel = osparc.utils.Utils.getStudyLabel();
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

      const cbConfirmWindowSize = new qx.ui.form.CheckBox(this.tr("Window size check"));
      preferencesSettings.bind("confirmWindowSize", cbConfirmWindowSize, "value");
      cbConfirmWindowSize.bind("value", preferencesSettings, "confirmWindowSize");
      box.add(cbConfirmWindowSize);

      return box;
    }
  }
});
