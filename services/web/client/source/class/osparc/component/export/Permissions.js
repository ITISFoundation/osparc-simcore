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
 * Widget for modifying Study permissions. This is the way for sharing studies
 * - Creates a copy of study data
 * - It allows changing study's access right, so that the study owners can:
 *   - Share it with Organizations and/or Organization Members (Collaborators)
 *   - Make other Collaborators Owner
 *   - Remove collaborators
 */

qx.Class.define("osparc.component.export.Permissions", {
  extend: qx.ui.core.Widget,

  /**
    * @param studyData {Object} Object containing the serialized Study Data
    */
  construct: function(studyData) {
    this.base(arguments);

    this.__studyData = osparc.utils.Utils.deepCloneObject(studyData);

    this._setLayout(new qx.ui.layout.VBox(15));

    this.__buildLayout();

    this.__getMyFriends();
  },

  events: {
    "updateStudy": "qx.event.type.Data"
  },

  statics: {
    getCollaboratorAccessRight: function() {
      return {
        "read": true,
        "write": true,
        "delete": false
      };
    },

    getOwnerAccessRight: function() {
      return {
        "read": true,
        "write": true,
        "delete": true
      };
    },

    removeCollaborator: function(studyData, gid) {
      return delete studyData["accessRights"][gid];
    },

    createWindow: function(winText, shareResourceWidget) {
      const window = new qx.ui.window.Window(winText).set({
        appearance: "service-window",
        layout: new qx.ui.layout.Grow(),
        autoDestroy: true,
        contentPadding: 10,
        width: 400,
        height: 300,
        showMaximize: false,
        showMinimize: false,
        modal: true
      });
      window.add(shareResourceWidget);
      window.center();
      return window;
    }
  },

  members: {
    __studyData: null,
    __organizationsAndMembers: null,
    __collaboratorsModel: null,
    __myFrieds: null,

    createWindow: function() {
      return this.self().createWindow(this.tr("Share with people and organizations"), this);
    },

    __buildLayout: function() {
      const addCollaborator = this.__createAddCollaborator();
      this._add(addCollaborator);

      const collaboratorsList = this.__createCollaboratorsList();
      this._add(collaboratorsList, {
        flex: 1
      });
    },

    __createAddCollaborator: function() {
      const vBox = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
      vBox.setVisibility(this.__isUserOwner() ? "visible" : "excluded");

      const label = new qx.ui.basic.Label().set({
        value: this.tr("Add Collaborators and Organizations")
      });
      vBox.add(label);

      const hBox = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
        alignY: "middle"
      }));
      vBox.add(hBox, {
        flex: 1
      });

      const organizationsAndMembers = this.__organizationsAndMembers = new osparc.component.filter.OrganizationsAndMembers("asfd");
      hBox.add(organizationsAndMembers, {
        flex: 1
      });

      const addCollaboratorBtn = new qx.ui.form.Button(this.tr("Add")).set({
        allowGrowY: false
      });
      addCollaboratorBtn.addListener("execute", () => {
        this.__addCollaborator();
      }, this);
      hBox.add(addCollaboratorBtn);

      return vBox;
    },

    __createCollaboratorsList: function() {
      const collaboratorsUIList = new qx.ui.form.List().set({
        decorator: "no-border",
        spacing: 3,
        width: 150
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
          ctrl.bindProperty("access_rights", "accessRights", null, item, id);
          ctrl.bindProperty("showOptions", "showOptions", null, item, id);
        },
        configureItem: item => {
          item.getChildControl("thumbnail").getContentElement()
            .setStyles({
              "border-radius": "16px"
            });
          item.addListener("promoteCollaborator", e => {
            const orgMember = e.getData();
            this.__promoteCollaborator(orgMember);
          });
          item.addListener("removeCollaborator", e => {
            const orgMember = e.getData();
            this.__deleteCollaborator(orgMember);
          });
        }
      });

      return collaboratorsUIList;
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

      const aceessRights = this.__studyData["accessRights"];
      const myFriends = this.__myFrieds;
      for (const gid of Object.keys(myFriends)) {
        const myFriend = myFriends[gid];
        if (parseInt(gid) !== osparc.auth.Data.getInstance().getGroupId() && !(parseInt(gid) in aceessRights)) {
          const btn = this.__organizationsAndMembers.addOption(myFriend);
          btn.setIcon(myFriend["isOrg"] ? "@FontAwesome5Solid/users/14" : "@FontAwesome5Solid/user/14");
        }
      }
    },

    __reloadCollaboratorsList: function() {
      this.__collaboratorsModel.removeAll();

      const aceessRights = this.__studyData["accessRights"];
      Object.keys(aceessRights).forEach(gid => {
        if (Object.prototype.hasOwnProperty.call(this.__myFrieds, gid)) {
          const collaborator = this.__myFrieds[gid];
          if ("first_name" in collaborator) {
            collaborator["thumbnail"] = osparc.utils.Avatar.getUrl(collaborator["login"], 32);
            collaborator["name"] = osparc.utils.Utils.firstsUp(collaborator["first_name"], collaborator["last_name"]);
          }
          collaborator["access_rights"] = aceessRights[gid];
          if (this.__isUserOwner()) {
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

    __isUserOwner: function() {
      const myGid = osparc.auth.Data.getInstance().getGroupId();
      const aceessRights = this.__studyData["accessRights"];
      if (myGid in aceessRights) {
        return aceessRights[myGid]["delete"];
      }
      return false;
    },

    __addCollaborator: function() {
      const gids = this.__organizationsAndMembers.getSelectedGIDs();
      if (gids.length === 0) {
        return;
      }

      gids.forEach(gid => {
        this.__studyData["accessRights"][gid] = this.self().getCollaboratorAccessRight();
      });
      const params = {
        url: {
          "projectId": this.__studyData["uuid"]
        },
        data: this.__studyData
      };
      osparc.data.Resources.fetch("studies", "put", params)
        .then(() => {
          this.fireDataEvent("updateStudy", this.__studyData["uuid"]);
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Collaborator(s) successfully added"));
          this.__reloadOrganizationsAndMembers();
          this.__reloadCollaboratorsList();
        })
        .catch(err => {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Something went adding collaborator(s)"), "ERROR");
          console.error(err);
        });
    },

    __promoteCollaborator: function(collaborator) {
      this.__studyData["accessRights"][collaborator["gid"]] = this.self().getOwnerAccessRight();
      const params = {
        url: {
          "projectId": this.__studyData["uuid"]
        },
        data: this.__studyData
      };
      osparc.data.Resources.fetch("studies", "put", params)
        .then(() => {
          this.fireDataEvent("updateStudy", this.__studyData["uuid"]);
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Collaborator successfully made Owner"));
          this.__reloadOrganizationsAndMembers();
          this.__reloadCollaboratorsList();
        })
        .catch(err => {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Something went wrong making Collaborator Owner"), "ERROR");
          console.error(err);
        });
    },

    __deleteCollaborator: function(collaborator) {
      const success = this.self().removeCollaborator(this.__studyData, collaborator["gid"]);
      if (!success) {
        osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Something went wrong removing Collaborator"), "ERROR");
      }

      const params = {
        url: {
          "projectId": this.__studyData["uuid"]
        },
        data: this.__studyData
      };
      osparc.data.Resources.fetch("studies", "put", params)
        .then(() => {
          this.fireDataEvent("updateStudy", this.__studyData["uuid"]);
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Collaborator successfully removed"));
          this.__reloadOrganizationsAndMembers();
          this.__reloadCollaboratorsList();
        })
        .catch(err => {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Something went wrong removing Collaborator"), "ERROR");
          console.error(err);
        });
    }
  }
});
