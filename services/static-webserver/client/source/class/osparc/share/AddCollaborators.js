/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 *   Widget that offers the "Share with..." button to add collaborators to a resource.
 *   It also provides the "Check Organization..." direct access.
 *   As output, once the user select n gid in the NewCollaboratorsManager pop up window,
 * an event is fired with the list of collaborators.
 */

qx.Class.define("osparc.share.AddCollaborators", {
  extend: qx.ui.core.Widget,

  /**
    * @param serializedDataCopy {Object} Object containing the Serialized Data
    */
  construct: function(serializedDataCopy) {
    this.base(arguments);

    this.__serializedDataCopy = serializedDataCopy;

    this._setLayout(new qx.ui.layout.VBox(5));

    this.__buildLayout();
  },

  events: {
    "addCollaborators": "qx.event.type.Data"
  },

  members: {
    __serializedDataCopy: null,

    __buildLayout: function() {
      const label = new qx.ui.basic.Label(this.tr("Select from the list below and click Share"));
      this._add(label);

      const addCollaboratorBtn = new qx.ui.form.Button(this.tr("Share with...")).set({
        appearance: "form-button",
        alignX: "left",
        allowGrowX: false
      });
      addCollaboratorBtn.addListener("execute", () => {
        const collaboratorsManager = new osparc.share.NewCollaboratorsManager(this.__serializedDataCopy);
        collaboratorsManager.addListener("addCollaborators", e => {
          collaboratorsManager.close();
          this.fireDataEvent("addCollaborators", e.getData());
        }, this);
      }, this);
      this._add(addCollaboratorBtn);

      const organizations = new qx.ui.form.Button(this.tr("Check Organizations...")).set({
        appearance: "form-button-outlined",
        allowGrowY: false,
        allowGrowX: false,
        icon: osparc.dashboard.CardBase.SHARED_ORGS
      });
      organizations.addListener("execute", () => osparc.desktop.organizations.OrganizationsWindow.openWindow(), this);
      this._add(organizations);
    }
  }
});
