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

qx.Class.define("osparc.component.export.Permissions", {
  extend: qx.ui.core.Widget,
  type: "abstract",

  /**
    * @param serializedData {Object} Object containing the Serialized Data
    */
  construct: function(serializedData) {
    this.base(arguments);

    this.__serializedData = serializedData;

    this._setLayout(new qx.ui.layout.VBox(10));

    this.__buildLayout();

    this.__getMyFriends();
  },

  statics: {
    canDelete: function(accessRights) {
      let canDelete = accessRights.getDelete ? accessRights.getDelete() : false;
      canDelete = canDelete || (accessRights.getWrite_access ? accessRights.getWrite_access() : false);
      return canDelete;
    },

    canWrite: function(accessRights) {
      let canWrite = accessRights.getWrite ? accessRights.getWrite() : false;
      canWrite = canWrite || (accessRights.getWrite_access ? accessRights.getWrite_access() : false);
      return canWrite;
    },

    canView: function(accessRights) {
      let canView = accessRights.getRead ? accessRights.getRead() : false;
      canView = canView || (accessRights.getExecute_access ? accessRights.getExecute_access() : false);
      return canView;
    }
  },

  members: {
    __serializedData: null,
    __organizationsAndMembers: null,
    __collaboratorsModel: null,
    __myFrieds: null,

    __buildLayout: function() {
      const addCollaborator = this.__createAddCollaboratorSection();
      this._add(addCollaborator);

      const collaboratorsList = this.__createCollaboratorsListSection();
      this._add(collaboratorsList, {
        flex: 1
      });
    },

    __createAddCollaboratorSection: function() {
      const vBox = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
      vBox.setVisibility(this._isUserOwner() ? "visible" : "excluded");

      const label = new qx.ui.basic.Label(this.tr("Select from the following list"));
      vBox.add(label);

      const hBox = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
        alignY: "middle"
      }));
      vBox.add(hBox, {
        flex: 1
      });

      const organizationsAndMembers = this.__organizationsAndMembers = new osparc.component.filter.OrganizationsAndMembers("orgAndMembPerms");
      hBox.add(organizationsAndMembers, {
        flex: 1
      });

      const addCollaboratorBtn = new qx.ui.form.Button(this.tr("Add")).set({
        allowGrowY: false
      });
      addCollaboratorBtn.addListener("execute", () => {
        this._addCollaborator();
      }, this);
      hBox.add(addCollaboratorBtn);

      return vBox;
    },

    __createCollaboratorsListSection: function() {
      const vBox = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));

      const label = new qx.ui.basic.Label(this.tr("Shared with"));
      vBox.add(label);

      const collaboratorsUIList = new qx.ui.form.List().set({
        decorator: "no-border",
        spacing: 3,
        width: 150,
        padding: 0,
        backgroundColor: "material-button-background"
      });

      const collaboratorsModel = this.__collaboratorsModel = new qx.data.Array();
      const collaboratorsCtrl = new qx.data.controller.List(collaboratorsModel, collaboratorsUIList, "name");
      collaboratorsCtrl.setDelegate({
        createItem: () => new osparc.dashboard.CollaboratorListItem(),
        bindItem: (ctrl, item, id) => {
          ctrl.bindProperty("gid", "model", null, item, id);
          ctrl.bindProperty("gid", "key", null, item, id);
          ctrl.bindProperty("thumbnail", "thumbnail", null, item, id);
          ctrl.bindProperty("name", "title", null, item, id); // user
          ctrl.bindProperty("label", "title", null, item, id); // organization
          ctrl.bindProperty("login", "subtitle", null, item, id); // user
          ctrl.bindProperty("description", "subtitle", null, item, id); // organization
          ctrl.bindProperty("isOrg", "isOrganization", null, item, id);
          ctrl.bindProperty("accessRights", "accessRights", null, item, id);
          ctrl.bindProperty("showOptions", "showOptions", null, item, id);
        },
        configureItem: item => {
          item.getChildControl("thumbnail").getContentElement()
            .setStyles({
              "border-radius": "16px"
            });
          item.addListener("promoteCollaborator", e => {
            const orgMember = e.getData();
            this._promoteCollaborator(orgMember);
          });
          item.addListener("removeCollaborator", e => {
            const orgMember = e.getData();
            this._deleteCollaborator(orgMember);
          });
        }
      });
      vBox.add(collaboratorsUIList, {
        flex: 1
      });

      return vBox;
    },

    __getMyFriends: function() {
      this.__myFrieds = {};

      const store = osparc.store.Store.getInstance();
      const promises = [];
      promises.push(store.getGroupsOrganizations());
      promises.push(store.getVisibleMembers());
      Promise.all(promises)
        .then(values => {
          const orgs = values[0];
          const orgMembers = values[1];
          orgs.forEach(org => {
            org["isOrg"] = true;
            this.__myFrieds[org["gid"]] = org;
          });
          for (const gid of Object.keys(orgMembers)) {
            const orgMember = orgMembers[gid];
            orgMember["isOrg"] = false;
            this.__myFrieds[gid] = orgMember;
          }
          this.__reloadOrganizationsAndMembers();
          this.__reloadCollaboratorsList();
        });
    },

    __reloadOrganizationsAndMembers: function() {
      this.__organizationsAndMembers.reset();

      const aceessRights = this.__getAccessRights();
      const myFriends = Object.values(this.__myFrieds);

      // sort them first
      myFriends.sort((a, b) => (a["label"] > b["label"]) ? 1 : -1);
      myFriends.sort((a, b) => (a["isOrg"] && !b["isOrg"]) ? -1 : 1);

      myFriends.forEach(myFriend => {
        const gid = myFriend["gid"];
        if (parseInt(gid) !== osparc.auth.Data.getInstance().getGroupId() && !(parseInt(gid) in aceessRights)) {
          const btn = this.__organizationsAndMembers.addOption(myFriend);
          btn.setIcon(myFriend["isOrg"] ? "@FontAwesome5Solid/users/14" : "@FontAwesome5Solid/user/14");
        }
      });
    },

    __reloadCollaboratorsList: function() {
      this.__collaboratorsModel.removeAll();

      const aceessRights = this.__getAccessRights();
      Object.keys(aceessRights).forEach(gid => {
        if (Object.prototype.hasOwnProperty.call(this.__myFrieds, gid)) {
          const collaborator = this.__myFrieds[gid];
          if ("first_name" in collaborator) {
            collaborator["thumbnail"] = osparc.utils.Avatar.getUrl(collaborator["login"], 32);
            collaborator["name"] = osparc.utils.Utils.firstsUp(collaborator["first_name"], collaborator["last_name"]);
          }
          collaborator["accessRights"] = aceessRights[gid];
          if (this._isUserOwner()) {
            collaborator["showOptions"] = true;
          }
          const collaboratorModel = qx.data.marshal.Json.createModel(collaborator);
          if (parseInt(gid) === osparc.auth.Data.getInstance().getGroupId()) {
            this.__collaboratorsModel.insertAt(0, collaboratorModel);
          } else {
            this.__collaboratorsModel.append(collaboratorModel);
          }
        }
      });
    },

    __getAccessRights: function() {
      return this.__serializedData["accessRights"] || this.__serializedData["access_rights"];
    },

    _isUserOwner: function() {
      throw new Error("Abstract method called!");
    },

    _addCollaborator: function() {
      throw new Error("Abstract method called!");
    },

    _promoteCollaborator: function(collaborator) {
      throw new Error("Abstract method called!");
    },

    _deleteCollaborator: function(collaborator) {
      throw new Error("Abstract method called!");
    }
  }
});
