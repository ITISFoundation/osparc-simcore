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

qx.Class.define("osparc.component.permissions.Permissions", {
  extend: qx.ui.core.Widget,
  type: "abstract",

  /**
    * @param serializedData {Object} Object containing the Serialized Data
    */
  construct: function(serializedData, initCollabs = []) {
    this.base(arguments);

    this._serializedData = serializedData;

    this._setLayout(new qx.ui.layout.VBox(5));

    this.__buildLayout();

    this.__collaborators = {};
    initCollabs.forEach(initCollab => {
      this.__collaborators[initCollab["gid"]] = initCollab;
    });
    this.getCollaborators();
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
    _serializedData: null,
    __organizationsAndMembers: null,
    __collaboratorsModel: null,
    __collaborators: null,
    __addCollaboratorBtn: null,

    __buildLayout: function() {
      const addCollaborator = this.__createAddCollaboratorSection();
      this._add(addCollaborator);

      const collaboratorsList = this.__createCollaboratorsListSection();
      this._add(collaboratorsList, {
        flex: 1
      });

      // for now, only for studies
      if ("uuid" in this._serializedData) {
        const studyLinkSection = this.__createStudyLinkSection();
        this._add(studyLinkSection);
      }
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

      const addCollaboratorBtn = this.__addCollaboratorBtn = new qx.ui.form.Button(this.tr("Add")).set({
        allowGrowY: false,
        enabled: false
      });
      addCollaboratorBtn.addListener("execute", () => {
        this._addCollaborator();
      }, this);
      qx.event.message.Bus.getInstance().subscribe("OrgAndMembPermsFilter", () => {
        const anySelected = Boolean(this.__organizationsAndMembers.getSelectedGIDs().length);
        this.__addCollaboratorBtn.setEnabled(anySelected);
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
          ctrl.bindProperty("collabType", "collabType", null, item, id);
          ctrl.bindProperty("thumbnail", "thumbnail", null, item, id);
          ctrl.bindProperty("name", "title", null, item, id); // user
          ctrl.bindProperty("label", "title", null, item, id); // organization
          ctrl.bindProperty("login", "subtitle", null, item, id); // user
          ctrl.bindProperty("description", "subtitle", null, item, id); // organization
          ctrl.bindProperty("accessRights", "accessRights", null, item, id);
          ctrl.bindProperty("showOptions", "showOptions", null, item, id);
        },
        configureItem: item => {
          item.getChildControl("thumbnail").getContentElement()
            .setStyles({
              "border-radius": "16px"
            });
          item.addListener("makeOwner", e => {
            const orgMember = e.getData();
            this._makeOwner(orgMember);
          });
          item.addListener("makeCollaborator", e => {
            const orgMember = e.getData();
            this._makeCollaborator(orgMember);
          });
          item.addListener("makeViewer", e => {
            const orgMember = e.getData();
            this._makeViewer(orgMember);
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

    __createStudyLinkSection: function() {
      const vBox = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));

      const label = new qx.ui.basic.Label().set({
        value: this.tr("Those that have access to the study can use the following permanent link:"),
        rich: true
      });
      vBox.add(label);

      const hBox = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
        alignY: "middle"
      }));
      vBox.add(hBox, {
        flex: 1
      });

      const link = window.location.href + "#/study/" + this._serializedData["uuid"];
      const linkField = new qx.ui.form.TextField(link);
      hBox.add(linkField, {
        flex: 1
      });

      const copyLinkBtn = new qx.ui.form.Button(this.tr("Copy link"));
      copyLinkBtn.addListener("execute", () => {
        if (osparc.utils.Utils.copyTextToClipboard(link)) {
          copyLinkBtn.setIcon("@FontAwesome5Solid/check/12");
        }
      }, this);
      hBox.add(copyLinkBtn);

      return vBox;
    },

    getCollaborators: function() {
      const store = osparc.store.Store.getInstance();
      const promises = [];
      promises.push(store.getGroupsOrganizations());
      promises.push(store.getVisibleMembers());
      Promise.all(promises)
        .then(values => {
          const orgs = values[0]; // array
          const orgMembers = values[1]; // object
          orgs.forEach(org => {
            org["collabType"] = 1;
            this.__collaborators[org["gid"]] = org;
          });
          for (const gid of Object.keys(orgMembers)) {
            const orgMember = orgMembers[gid];
            orgMember["collabType"] = 2;
            this.__collaborators[gid] = orgMember;
          }
          this.__reloadOrganizationsAndMembers();
          this.__reloadCollaboratorsList();
        });
    },

    __reloadOrganizationsAndMembers: function() {
      this.__organizationsAndMembers.reset();

      const aceessRights = this.__getAccessRights();
      const myFriends = Object.values(this.__collaborators);

      // sort them first
      myFriends.sort((a, b) => {
        if (a["collabType"] > b["collabType"]) {
          return 1;
        }
        if (a["collabType"] < b["collabType"]) {
          return -1;
        }
        if (a["label"] > b["label"]) {
          return 1;
        }
        return -1;
      });

      myFriends.forEach(myFriend => {
        const gid = myFriend["gid"];
        if (parseInt(gid) !== osparc.auth.Data.getInstance().getGroupId() && !(parseInt(gid) in aceessRights)) {
          const btn = this.__organizationsAndMembers.addOption(myFriend);
          let iconPath = null;
          switch (myFriend["collabType"]) {
            case 0:
              iconPath = "@FontAwesome5Solid/globe/14";
              break;
            case 1:
              iconPath = "@FontAwesome5Solid/users/14";
              break;
            case 2:
              iconPath = "@FontAwesome5Solid/user/14";
              break;
          }
          btn.setIcon(iconPath);
        }
      });
    },

    __reloadCollaboratorsList: function() {
      this.__collaboratorsModel.removeAll();

      const aceessRights = this.__getAccessRights();
      Object.keys(aceessRights).forEach(gid => {
        if (Object.prototype.hasOwnProperty.call(this.__collaborators, gid)) {
          const collaborator = this.__collaborators[gid];
          if ("first_name" in collaborator) {
            collaborator["thumbnail"] = osparc.utils.Avatar.getUrl(collaborator["login"], 32);
            collaborator["name"] = osparc.utils.Utils.firstsUp(collaborator["first_name"], collaborator["last_name"]);
          }
          collaborator["accessRights"] = aceessRights[gid];
          collaborator["showOptions"] = this._isUserOwner();
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
      return this._serializedData["accessRights"] || this._serializedData["access_rights"];
    },

    _isUserOwner: function() {
      throw new Error("Abstract method called!");
    },

    _addCollaborator: function() {
      throw new Error("Abstract method called!");
    },

    _deleteCollaborator: function(collaborator) {
      throw new Error("Abstract method called!");
    },

    _makeOwner: function(collaborator) {
      throw new Error("Abstract method called!");
    },

    _makeCollaborator: function(collaborator) {
      throw new Error("Abstract method called!");
    },

    _makeViewer: function(collaborator) {
      throw new Error("Abstract method called!");
    }
  }
});
