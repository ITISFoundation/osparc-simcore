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
 *
 */

qx.Class.define("osparc.component.export.Permissions", {
  extend: qx.ui.core.Widget,

  construct: function(study) {
    this.base(arguments);

    this.__study = osparc.utils.Utils.deepCloneObject(study);

    this._setLayout(new qx.ui.layout.VBox(15));

    this.__buildLayout();

    this.__getMyFriends();
  },

  statics: {
    getCollaboratorAccessRight: function() {
      return {
        "read": true,
        "write": true,
        "execute": false
      };
    },

    getOwnerAccessRight: function() {
      return {
        "read": true,
        "write": true,
        "execute": true
      };
    }
  },

  members: {
    __study: null,
    __organizationsAndMembers: null,
    __collaboratorsModel: null,
    __myFrieds: null,

    createWindow: function() {
      return osparc.component.export.ShareResourceBase.createWindow(this.tr("Share with people and organizations"), this);
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
            this.__myFrieds[org["gid"]] = org;
          });
          for (const gid of Object.keys(orgMembers)) {
            this.__myFrieds[gid] = orgMembers[gid];
          }
          this.__populateOrganizationsAndMembers();
          this.__reloadCollaboratorsList();
        });
    },

    __populateOrganizationsAndMembers: function() {
      const myFriends = this.__myFrieds;
      for (const gid of Object.keys(myFriends)) {
        const myFriend = myFriends[gid];
        if (gid !== osparc.auth.Data.getInstance().getGroupId()) {
          this.__organizationsAndMembers.addOption(myFriend);
        }
      }
    },

    __reloadCollaboratorsList: function() {
      this.__collaboratorsModel.removeAll();

      const aceessRights = this.__study["accessRights"];
      Object.keys(aceessRights).forEach(gid => {
        if (Object.prototype.hasOwnProperty.call(this.__myFrieds, gid)) {
          const collaborator = this.__myFrieds[gid];
          if ("first_name" in collaborator) {
            collaborator["thumbnail"] = osparc.utils.Avatar.getUrl(collaborator["login"], 32);
            collaborator["name"] = osparc.utils.Utils.capitalize(collaborator["first_name"]) + " " + osparc.utils.Utils.capitalize(collaborator["last_name"]);
          }
          collaborator["access_rights"] = aceessRights[gid];
          if (this.__isUserOwner()) {
            collaborator["showOptions"] = true;
          }
          const collaboratorModel = qx.data.marshal.Json.createModel(collaborator);
          if (gid === osparc.auth.Data.getInstance().getGroupId()) {
            this.__collaboratorsModel.insertAt(0, collaboratorModel);
          } else {
            this.__collaboratorsModel.append(collaboratorModel);
          }
        }
      });
    },

    __isUserOwner: function() {
      const myGid = osparc.auth.Data.getInstance().getGroupId();
      const aceessRights = this.__study["accessRights"];
      if (myGid in aceessRights) {
        return aceessRights[myGid]["execute"];
      }
      return false;
    },

    __addCollaborator: function() {
      const gids = this.__organizationsAndMembers.getSelectedGIDs();
      if (gids.length === 0) {
        return;
      }

      gids.forEach(gid => {
        this.__study["accessRights"][gid] = this.self().getCollaboratorAccessRight();
      });
      const params = {
        url: {
          "projectId": this.__study["uuid"]
        },
        data: this.__study
      };
      osparc.data.Resources.fetch("studies", "put", params)
        .then(() => {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Collaborator(s) successfully made Owner"));
          this.__reloadCollaboratorsList();
        })
        .catch(err => {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Something went adding collaborators"), "ERROR");
          console.error(err);
        });
    },

    __promoteCollaborator: function(collaborator) {
      this.__study["accessRights"][collaborator["gid"]] = this.self().getOwnerAccessRight();
      const params = {
        url: {
          "projectId": this.__study["uuid"]
        },
        data: this.__study
      };
      osparc.data.Resources.fetch("studies", "put", params)
        .then(() => {
          osparc.component.message.FlashMessenger.getInstance().logAs(collaborator["name"] + this.tr(" successfully made Owner"));
          this.__reloadCollaboratorsList();
        })
        .catch(err => {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Something went wrong making ") + collaborator["name"] + this.tr(" Owner"), "ERROR");
          console.error(err);
        });
    },

    __deleteCollaborator: function(collaborator) {
      const success = delete this.__study["accessRights"][collaborator["gid"]];
      if (!success) {
        osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Something went wrong making ") + collaborator["name"] + this.tr(" Owner"), "ERROR");
      }

      const params = {
        url: {
          "projectId": this.__study["uuid"]
        },
        data: this.__study
      };
      osparc.data.Resources.fetch("studies", "put", params)
        .then(() => {
          osparc.component.message.FlashMessenger.getInstance().logAs(collaborator["name"] + this.tr(" successfully removed"));
          this.__reloadCollaboratorsList();
        })
        .catch(err => {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Something went wrong making ") + collaborator["name"] + this.tr(" Owner"), "ERROR");
          console.error(err);
        });
    }
  }
});
