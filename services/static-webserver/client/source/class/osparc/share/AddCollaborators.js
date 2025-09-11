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
 *   Widget that offers the "Share" button to add collaborators to a resource.
 *   It also provides the "Check Organization..." direct access.
 *   As output, once the user select n gid in the NewCollaboratorsManager pop up window,
 * an event is fired with the list of collaborators.
 */

qx.Class.define("osparc.share.AddCollaborators", {
  extend: qx.ui.core.Widget,

  /**
    * @param serializedDataCopy {Object} Object containing the Serialized Data
    * @param publishingTemplate {Boolean} Wether the widget needs to be initialized for publishing template
    */
  construct: function(serializedDataCopy, publishingTemplate = false) {
    this.base(arguments);

    this.__serializedDataCopy = serializedDataCopy;
    this.__publishingTemplate = publishingTemplate;

    this._setLayout(new qx.ui.layout.VBox(5));

    this.__buildLayout();
  },

  events: {
    "addCollaborators": "qx.event.type.Data"
  },

  members: {
    __serializedDataCopy: null,
    __publishingTemplate: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "intro-text":
          control = new qx.ui.basic.Label();
          this._addAt(control, 0);
          break;
        case "buttons-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox());
          this._add(control);
          break;
        case "share-with":
          control = new qx.ui.form.Button().set({
            icon: "@FontAwesome5Solid/share-alt/12",
            label: this.tr("Share"),
            appearance: "form-button",
            alignX: "left",
            allowGrowX: false
          });
          this.getChildControl("buttons-layout").add(control);
          this.getChildControl("buttons-layout").add(new qx.ui.core.Spacer(), {
            flex: 1
          });
          break;
        case "my-organizations":
          control = new qx.ui.form.Button(this.tr("My Organizations...")).set({
            appearance: "form-button-outlined",
            allowGrowY: false,
            allowGrowX: false,
            alignX: "right",
            icon: osparc.dashboard.CardBase.SHARED_ORGS
          });
          this.getChildControl("buttons-layout").add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    setSerializedData: function(serializedDataCopy) {
      this.__serializedDataCopy = serializedDataCopy;
    },

    __buildLayout: function() {
      const addCollaboratorBtn = this.getChildControl("share-with");
      addCollaboratorBtn.addListener("execute", () => {
        const collaboratorsManager = new osparc.share.NewCollaboratorsManager(this.__serializedDataCopy);
        if (this.__publishingTemplate) {
          collaboratorsManager.getActionButton().setLabel(this.tr("Publish for"));
        }
        collaboratorsManager.addListener("addCollaborators", e => {
          collaboratorsManager.close();
          this.fireDataEvent("addCollaborators", e.getData());
        }, this);
        if (this.__serializedDataCopy["resourceType"] === "study") {
          collaboratorsManager.addListener("shareWithEmails", e => {
            const {
              selectedEmails,
              newAccessRights,
              message,
            } = e.getData();
            collaboratorsManager.close();
            osparc.store.Study.getInstance().sendShareEmails(this.__serializedDataCopy, selectedEmails, newAccessRights, message)
              .then(() => osparc.FlashMessenger.logAs(this.tr("Emails sent"), "INFO"))
              .catch(err => osparc.FlashMessenger.logError(err));
          }, this);
        }
      }, this);

      const organizations = this.getChildControl("my-organizations");
      organizations.addListener("execute", () => osparc.desktop.organizations.OrganizationsWindow.openWindow(), this);
    }
  }
});
