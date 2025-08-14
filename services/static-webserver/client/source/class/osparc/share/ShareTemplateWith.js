/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * View that shows template publishing sharing options:
 * - Private
 * - My organizations
 * - Product everyone
 */

qx.Class.define("osparc.share.ShareTemplateWith", {
  extend: qx.ui.core.Widget,

  /**
   * @param studyData {Object} Object containing part or the entire serialized Study Data
   */
  construct: function(studyData) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    this.__potentialTemplateData = osparc.data.model.Study.deepCloneStudyObject(studyData);

    this.__selectedCollabs = new qx.ui.container.Composite(new qx.ui.layout.HBox());
    this.__updateAccessRights();

    this.__buildLayout();
  },

  members: {
    __potentialTemplateData: null,
    __selectedCollabs: null,

    __buildLayout: function() {
      // mark it us template, so that testers can share it with product everyone
      this.__potentialTemplateData["resourceType"] = "template";
      const addCollaborators = new osparc.share.AddCollaborators(this.__potentialTemplateData, true);
      addCollaborators.getChildControl("intro-text").set({
        value: this.tr("Make the template accessible to:"),
        font: "text-14",
      });
      addCollaborators.getChildControl("share-with").set({
        icon: "@FontAwesome5Solid/share-alt/12",
        label: this.tr("Share"),
      });
      this._add(addCollaborators);

      this._add(this.__selectedCollabs);

      addCollaborators.addListener("addCollaborators", e => {
        const {
          selectedGids,
        } = e.getData();
        if (selectedGids.length) {
          const potentialCollaborators = osparc.store.Groups.getInstance().getPotentialCollaborators(false, true)
          const currentGids = this.getSelectedGroups();
          selectedGids.forEach(gid => {
            if (gid in potentialCollaborators && !currentGids.includes(gid)) {
              const collabButton = new qx.ui.toolbar.Button(potentialCollaborators[gid].getLabel(), "@MaterialIcons/close/12");
              collabButton.gid = gid;
              this.__selectedCollabs.add(collabButton);
              collabButton.addListener("execute", () => {
                this.__selectedCollabs.remove(collabButton);
                this.__updateAccessRights();
              });
            }
          });
          this.__updateAccessRights();
        }
      }, this);
    },

    __updateAccessRights: function() {
      const readAccessRole = osparc.data.Roles.STUDY["read"];
      const deleteAccessRole = osparc.data.Roles.STUDY["delete"];
      // these "accessRights" are only used for repopulating potential collaborators in the AddCollaborators -> NewCollaboratorsManager
      const myGroupId = osparc.auth.Data.getInstance().getGroupId();
      this.__potentialTemplateData["accessRights"] = {};
      this.__potentialTemplateData["accessRights"][myGroupId] = deleteAccessRole.accessRights;
      this.getSelectedGroups().forEach(gid => this.__potentialTemplateData["accessRights"][gid] = readAccessRole.accessRights);
    },

    getSelectedGroups: function() {
      const groupIDs = [];
      this.__selectedCollabs.getChildren().forEach(selectedCollab => groupIDs.push(selectedCollab.gid));
      return groupIDs;
    }
  }
});
