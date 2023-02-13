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

    this._setLayout(new qx.ui.layout.VBox(10));

    this.__buildLayout();

    this.__collaborators = {};
    initCollabs.forEach(initCollab => {
      this.__collaborators[initCollab["gid"]] = initCollab;
    });
    this.__getCollaborators();
  },

  statics: {
    sortByAccessRights: function(a, b) {
      const aAccessRights = a["accessRights"];
      const bAccessRights = b["accessRights"];
      if (aAccessRights["delete"] !== bAccessRights["delete"]) {
        return bAccessRights["delete"] - aAccessRights["delete"];
      }
      if (aAccessRights["write"] !== bAccessRights["write"]) {
        return bAccessRights["write"] - aAccessRights["write"];
      }
      if (aAccessRights["read"] !== bAccessRights["read"]) {
        return bAccessRights["read"] - aAccessRights["read"];
      }
      return 0;
    },

    sortStudyOrServiceCollabs: function(a, b) {
      const aAccessRights = a["accessRights"];
      const bAccessRights = b["accessRights"];
      let sorted = null;
      if ("delete" in aAccessRights) {
        // studies
        sorted = this.self().sortByAccessRights(a, b);
      } else if ("write_access" in aAccessRights) {
        // services
        if (aAccessRights["write_access"] !== bAccessRights["write_access"]) {
          sorted = bAccessRights["write_access"] - aAccessRights["write_access"];
        } else if (aAccessRights["read_access"] !== bAccessRights["read_access"]) {
          sorted = bAccessRights["read_access"] - aAccessRights["read_access"];
        }
      }
      return sorted;
    }
  },

  members: {
    _serializedData: null,
    __organizationsAndMembers: null,
    __collaboratorsModel: null,
    __collaborators: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "add-collaborator":
          control = this.__createAddCollaboratorSection();
          this._add(control);
          break;
        case "collaborators-list":
          control = this.__createCollaboratorsListSection();
          this._add(control, {
            flex: 1
          });
          break;
        case "open-organizations-btn":
          control = new qx.ui.form.Button(this.tr("Organizations...")).set({
            allowGrowY: false,
            allowGrowX: false,
            icon: osparc.dashboard.CardBase.SHARED_ORGS
          });
          osparc.desktop.preferences.PreferencesWindow.evaluateOrganizationsButton(control);
          control.addListener("execute", () => {
            const preferencesWindow = osparc.desktop.preferences.PreferencesWindow.openWindow();
            preferencesWindow.openOrganizations();
          }, this);
          this._add(control, {
            flex: 1
          });
          break;
        case "study-link":
          control = this.__createStudyLinkSection();
          this._add(control);
          // excluded by default
          control.exclude();
      }
      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      this._createChildControlImpl("add-collaborator");
      this._createChildControlImpl("open-organizations-btn");
      this._createChildControlImpl("collaborators-list");
      this._createChildControlImpl("study-link");
    },

    __createAddCollaboratorSection: function() {
      const vBox = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
      vBox.setVisibility(this._canIWrite() ? "visible" : "excluded");

      const label = new qx.ui.basic.Label(this.tr("Select from the dropdown list below and click Add to share"));
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
        appearance: "strong-button",
        allowGrowY: false,
        enabled: false
      });
      addCollaboratorBtn.addListener("execute", () => this._addCollaborator(), this);
      qx.event.message.Bus.getInstance().subscribe("OrgAndMembPermsFilter", () => {
        const anySelected = Boolean(this.__organizationsAndMembers.getSelectedGIDs().length);
        addCollaboratorBtn.setEnabled(anySelected);
      }, this);

      hBox.add(addCollaboratorBtn);

      return vBox;
    },

    __createCollaboratorsListSection: function() {
      const vBox = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));

      const label = new qx.ui.basic.Label(this.tr("Shared with"));
      vBox.add(label);

      const rolesLayout = osparc.data.Roles.createRolesResourceInfo();
      vBox.add(rolesLayout);

      const collaboratorsUIList = new qx.ui.form.List().set({
        decorator: "no-border",
        spacing: 3,
        width: 150,
        padding: 0,
        backgroundColor: "background-main-2"
      });

      const collaboratorsModel = this.__collaboratorsModel = new qx.data.Array();
      const collaboratorsCtrl = new qx.data.controller.List(collaboratorsModel, collaboratorsUIList, "name");
      collaboratorsCtrl.setDelegate({
        createItem: () => new osparc.ui.list.CollaboratorListItem(),
        bindItem: (ctrl, item, id) => {
          ctrl.bindProperty("gid", "model", null, item, id);
          ctrl.bindProperty("gid", "key", null, item, id);
          ctrl.bindProperty("collabType", "collabType", null, item, id);
          ctrl.bindProperty("thumbnail", "thumbnail", null, item, id);
          ctrl.bindProperty("name", "title", null, item, id); // user
          ctrl.bindProperty("label", "title", null, item, id); // organization
          ctrl.bindProperty("login", "subtitleMD", null, item, id); // user
          ctrl.bindProperty("description", "subtitle", null, item, id); // organization
          ctrl.bindProperty("accessRights", "accessRights", null, item, id);
          ctrl.bindProperty("showOptions", "showOptions", null, item, id);
        },
        configureItem: item => {
          item.getChildControl("thumbnail").getContentElement()
            .setStyles({
              "border-radius": "16px"
            });
          item.addListener("promoteToCollaborator", e => {
            const orgMember = e.getData();
            this._promoteToCollaborator(orgMember);
          });
          item.addListener("promoteToOwner", e => {
            const orgMember = e.getData();
            this._promoteToOwner(orgMember);
          });
          item.addListener("demoteToViewer", e => {
            const orgMember = e.getData();
            this._demoteToViewer(orgMember);
          });
          item.addListener("demoteToCollaborator", e => {
            const orgMember = e.getData();
            this._demoteToCollaborator(orgMember);
          });
          item.addListener("removeMember", e => {
            const orgMember = e.getData();
            this._deleteMember(orgMember);
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
        value: this.tr("Permanent Link for users that have access to the ") + osparc.product.Utils.getStudyAlias(),
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

    __getCollaborators: function() {
      osparc.store.Store.getInstance().getPotentialCollaborators()
        .then(potentialCollaborators => {
          this.__collaborators = Object.assign(this.__collaborators, potentialCollaborators);
          this.__reloadOrganizationsAndMembers();
          this.__reloadCollaboratorsList();
        });
    },

    __reloadOrganizationsAndMembers: function() {
      this.__organizationsAndMembers.reset();

      const aceessRights = this._serializedData["accessRights"];
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

      const aceessRights = this._serializedData["accessRights"];
      const collaboratorsList = [];
      Object.keys(aceessRights).forEach(gid => {
        if (Object.prototype.hasOwnProperty.call(this.__collaborators, gid)) {
          const collab = this.__collaborators[gid];
          // Do not override collaborator object
          const collaborator = osparc.utils.Utils.deepCloneObject(collab);
          if ("first_name" in collaborator) {
            collaborator["thumbnail"] = osparc.utils.Avatar.getUrl(collaborator["login"], 32);
            collaborator["name"] = osparc.utils.Utils.firstsUp(collaborator["first_name"], collaborator["last_name"]);
          }
          collaborator["accessRights"] = aceessRights[gid];
          collaborator["showOptions"] = this._canIWrite();
          collaboratorsList.push(collaborator);
        }
      });
      collaboratorsList.sort(this.self().sortStudyOrServiceCollabs);
      collaboratorsList.forEach(c => this.__collaboratorsModel.append(qx.data.marshal.Json.createModel(c)));
    },

    _canIWrite: function() {
      throw new Error("Abstract method called!");
    },

    _addCollaborator: function() {
      throw new Error("Abstract method called!");
    },

    _deleteMember: function(collaborator) {
      throw new Error("Abstract method called!");
    },

    _promoteToOwner: function(collaborator) {
      throw new Error("Abstract method called!");
    },

    _promoteToCollaborator: function(collaborator) {
      throw new Error("Abstract method called!");
    },

    _demoteToViewer: function(collaborator) {
      throw new Error("Abstract method called!");
    },

    _demoteToCollaborator: function(collaborator) {
      throw new Error("Abstract method called!");
    }
  }
});
