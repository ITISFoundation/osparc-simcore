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

qx.Class.define("osparc.share.Collaborators", {
  extend: qx.ui.core.Widget,
  type: "abstract",

  /**
    * @param serializedDataCopy {Object} Object containing the Serialized Data
    */
  construct: function(serializedDataCopy) {
    this.base(arguments);

    this._serializedDataCopy = serializedDataCopy;

    this._setLayout(new qx.ui.layout.VBox(15));

    this.set({
      padding: 5
    });

    this.__buildLayout();

    this._reloadCollaboratorsList();
  },

  events: {
    "updateAccessRights": "qx.event.type.Data"
  },

  statics: {
    sortByAccessRights: function(aAccessRights, bAccessRights) {
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
        sorted = this.self().sortByAccessRights(aAccessRights, bAccessRights);
      } else if ("execute" in aAccessRights) {
        // services
        if (aAccessRights["write"] !== bAccessRights["write"]) {
          sorted = bAccessRights["write"] - aAccessRights["write"];
        } else if (aAccessRights["execute"] !== bAccessRights["execute"]) {
          sorted = bAccessRights["execute"] - aAccessRights["execute"];
        }
      }
      return sorted;
    },

    createStudyLinkSection: function(serializedData) {
      const vBox = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));

      const label = new qx.ui.basic.Label().set({
        value: qx.locale.Manager.tr("Any logged-in user with access to the ") + osparc.product.Utils.getStudyAlias() + qx.locale.Manager.tr(" can open it"),
        rich: true
      });
      vBox.add(label);

      const hBox = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
        alignY: "middle"
      }));
      vBox.add(hBox, {
        flex: 1
      });

      const link = window.location.href + "#/study/" + serializedData["uuid"];
      const linkField = new qx.ui.form.TextField(link);
      hBox.add(linkField, {
        flex: 1
      });

      const copyLinkBtn = new qx.ui.form.Button(qx.locale.Manager.tr("Copy link"));
      copyLinkBtn.addListener("execute", () => {
        if (osparc.utils.Utils.copyTextToClipboard(link)) {
          copyLinkBtn.setIcon("@FontAwesome5Solid/check/12");
        }
      });
      hBox.add(copyLinkBtn);

      return vBox;
    },

    createTemplateLinkSection: function(serializedData) {
      const vBox = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));

      if ("permalink" in serializedData) {
        const permalink = serializedData["permalink"];

        const label = new qx.ui.basic.Label().set({
          rich: true
        });
        if (permalink["is_public"]) {
          label.setValue(qx.locale.Manager.tr("Anyone on the internet with the link can open this ") + osparc.product.Utils.getTemplateAlias());
        } else {
          label.setValue(qx.locale.Manager.tr("Any logged-in user with the link can copy and open this ") + osparc.product.Utils.getTemplateAlias());
        }
        vBox.add(label);

        const hBox = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
          alignY: "middle"
        }));
        vBox.add(hBox, {
          flex: 1
        });

        const link = permalink["url"];
        const linkField = new qx.ui.form.TextField(link);
        hBox.add(linkField, {
          flex: 1
        });

        const copyLinkBtn = new qx.ui.form.Button(qx.locale.Manager.tr("Copy link"));
        copyLinkBtn.addListener("execute", () => {
          if (osparc.utils.Utils.copyTextToClipboard(link)) {
            copyLinkBtn.setIcon("@FontAwesome5Solid/check/12");
          }
        });
        hBox.add(copyLinkBtn);
      }

      return vBox;
    }
  },

  members: {
    _serializedDataCopy: null,
    _resourceType: null,
    __addCollaborators: null,
    __collaboratorsModel: null,

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
        case "study-link":
          control = this.self().createStudyLinkSection(this._serializedDataCopy);
          this._add(control);
          // excluded by default
          control.exclude();
          break;
        case "template-link":
          control = this.self().createTemplateLinkSection(this._serializedDataCopy);
          this._add(control);
          // excluded by default
          control.exclude();
          break;
      }
      return control || this.base(arguments, id);
    },

    __canIShare: function() {
      if (this._resourceType === "study" && this._serializedDataCopy["workspaceId"]) {
        // Access Rights are set at workspace level
        return false;
      }

      let canIShare = false;
      switch (this._resourceType) {
        case "study":
        case "template":
        case "tutorial":
        case "hypertool":
          canIShare = osparc.data.model.Study.canIWrite(this._serializedDataCopy["accessRights"]);
          break;
        case "service":
          canIShare = osparc.service.Utils.canIWrite(this._serializedDataCopy["accessRights"]);
          break;
        case "workspace":
          canIShare = osparc.share.CollaboratorsWorkspace.canIDelete(this._serializedDataCopy["myAccessRights"]);
          break;
        case "tag":
          canIShare = osparc.share.CollaboratorsTag.canIWrite(this._serializedDataCopy["myAccessRights"]);
          break;
      }
      return canIShare;
    },

    __canIChangePermissions: function() {
      if (this._resourceType === "study" && this._serializedDataCopy["workspaceId"]) {
        // Access Rights are set at workspace level
        return false;
      }
      let fullOptions = false;
      switch (this._resourceType) {
        case "study":
        case "template":
        case "tutorial":
        case "hypertool":
          fullOptions = osparc.data.model.Study.canIDelete(this._serializedDataCopy["accessRights"]);
          break;
        case "service":
          fullOptions = osparc.service.Utils.canIWrite(this._serializedDataCopy["accessRights"]);
          break;
        case "workspace":
          fullOptions = osparc.share.CollaboratorsWorkspace.canIDelete(this._serializedDataCopy["myAccessRights"]);
          break;
        case "tag":
          fullOptions = osparc.share.CollaboratorsTag.canIDelete(this._serializedDataCopy["myAccessRights"]);
          break;
      }
      return fullOptions;
    },

    __createRolesLayout: function() {
      let rolesLayout = null;
      switch (this._resourceType) {
        case "study":
        case "template":
        case "tutorial":
        case "hypertool":
          rolesLayout = osparc.data.Roles.createRolesStudyInfo();
          break;
        case "service":
          rolesLayout = osparc.data.Roles.createRolesServicesInfo();
          break;
        case "workspace":
          rolesLayout = osparc.data.Roles.createRolesWorkspaceInfo();
          break;
        case "tag":
          rolesLayout = osparc.data.Roles.createRolesStudyInfo();
          break;
      }
      return rolesLayout;
    },

    __buildLayout: function() {
      if (this.__canIShare()) {
        this.__addCollaborators = this._createChildControlImpl("add-collaborator");
      }
      this._createChildControlImpl("collaborators-list");
      this._createChildControlImpl("study-link");
      this._createChildControlImpl("template-link");
    },

    __createAddCollaboratorSection: function() {
      const serializedDataCopy = osparc.utils.Utils.deepCloneObject(this._serializedDataCopy);
      // pass resourceType, so that, if it's a template testers can share it with product everyone
      serializedDataCopy["resourceType"] = this._resourceType;
      const addCollaborators = new osparc.share.AddCollaborators(serializedDataCopy);
      addCollaborators.addListener("addCollaborators", e => {
        const {
          selectedGids,
          newAccessRights,
        } = e.getData();
        this._addEditors(selectedGids, newAccessRights);
      }, this);
      return addCollaborators;
    },

    __createCollaboratorsListSection: function() {
      const vBox = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));

      const header = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));

      const label = new qx.ui.basic.Label(this.tr("Shared with:"));
      label.set({
        allowGrowX: true,
        alignY: "middle",
      });
      header.add(label, {
        flex: 1
      });

      const rolesLayout = this.__createRolesLayout();
      const leaveButton = this.__getLeaveStudyButton();
      if (leaveButton) {
        rolesLayout.addAt(leaveButton, 0);
      }
      header.add(rolesLayout);
      vBox.add(header);

      const collaboratorsUIList = new qx.ui.form.List().set({
        decorator: "no-border",
        spacing: 3,
        width: 150,
        padding: 0,
        backgroundColor: "transparent",
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
          ctrl.bindProperty("label", "title", null, item, id);
          ctrl.bindProperty("description", "subtitleMD", null, item, id);
          ctrl.bindProperty("resourceType", "resourceType", null, item, id); // Resource type
          ctrl.bindProperty("accessRights", "accessRights", null, item, id);
          ctrl.bindProperty("showOptions", "showOptions", null, item, id);
        },
        configureItem: item => {
          item.getChildControl("thumbnail").getContentElement()
            .setStyles({
              "border-radius": "16px"
            });
          item.addListener("promoteToEditor", e => {
            const orgMember = e.getData();
            this._promoteToEditor(orgMember, item);
          });
          item.addListener("promoteToOwner", e => {
            const orgMember = e.getData();
            this._promoteToOwner(orgMember, item);
          });
          item.addListener("demoteToUser", e => {
            const orgMember = e.getData();
            this._demoteToUser(orgMember, item);
          });
          item.addListener("demoteToEditor", e => {
            const orgMember = e.getData();
            this._demoteToEditor(orgMember, item);
          });
          item.addListener("removeMember", e => {
            const orgMember = e.getData();
            if (
              ["study", "template", "tutorial", "hypertool"].includes(this._resourceType) &&
              !osparc.share.CollaboratorsStudy.canCollaboratorBeRemoved(this._serializedDataCopy, orgMember["gid"])
            ) {
              let msg = this.tr("Collaborator can't be removed:");
              msg += this._serializedDataCopy["name"] + this.tr(" needs at least one owner.");
              if (
                Object.keys(this._serializedDataCopy["accessRights"]).length === 1 &&
                Object.values(this._serializedDataCopy["accessRights"])[0]["delete"]
              ) {
                msg += "<br>" + this.tr("You might want to delete it instead.");
              }
              osparc.FlashMessenger.logError(msg);
              return;
            }
            this._deleteMember(orgMember, item);
          });
        }
      });
      vBox.add(collaboratorsUIList, {
        flex: 1
      });

      return vBox;
    },

    __getLeaveStudyButton: function() {
      const myGid = osparc.auth.Data.getInstance().getGroupId();
      if (
        ["study", "template", "tutorial", "hypertool"].includes(this._resourceType) &&
        osparc.share.CollaboratorsStudy.canCollaboratorBeRemoved(this._serializedDataCopy, myGid)
      ) {
        const leaveText = this.tr("Leave") + " " + osparc.product.Utils.getStudyAlias({
          firstUpperCase: true
        });
        const leaveButton = new qx.ui.form.Button(leaveText).set({
          allowGrowX: false,
          visibility: Object.keys(this._serializedDataCopy["accessRights"]).includes(myGid.toString()) ? "visible" : "excluded"
        });
        leaveButton.addListener("execute", () => {
          const collaborator = {
            gid: myGid,
            name: osparc.store.Groups.getInstance().getGroupMe().getLabel(),
          }
          this._deleteMember(collaborator)
            .then(() => {
              qx.event.message.Bus.dispatchByName("reloadStudies");
            });
        }, this);
        return leaveButton;
      }
      return null;
    },

    _reloadCollaboratorsList: async function() {
      // reload "Share with..." list
      if (this.__addCollaborators) {
        const serializedDataCopy = osparc.utils.Utils.deepCloneObject(this._serializedDataCopy);
        // pass resourceType, so that, if it's a template testers can share it with product everyone
        serializedDataCopy["resourceType"] = this._resourceType;
        this.__addCollaborators.setSerializedData(serializedDataCopy);
      }

      // reload list
      this.__collaboratorsModel.removeAll();

      const groupsStore = osparc.store.Groups.getInstance();
      const everyoneGIds = [
        groupsStore.getEveryoneProductGroup().getGroupId(),
        groupsStore.getEveryoneGroup().getGroupId()
      ];
      const accessRights = this._serializedDataCopy["accessRights"];
      const collaboratorsList = [];
      const showOptions = this.__canIChangePermissions();
      const allGroups = groupsStore.getAllGroups();
      const usersStore = osparc.store.Users.getInstance();
      for (let i=0; i<Object.keys(accessRights).length; i++) {
        const gid = parseInt(Object.keys(accessRights)[i]);
        let collab = null;
        if (gid in allGroups) {
          collab = allGroups[gid];
        } else {
          collab = await usersStore.getUser(gid);
        }
        if (collab) {
          // Do not override collaborator object
          const collaborator = {
            "gid": collab.getGroupId(),
            "thumbnail": collab.getThumbnail(),
            "label": collab.getLabel(),
            "description": collab.getDescription(),
          };
          if (!("getUserId" in collab)) {
            // organization
            if (everyoneGIds.includes(parseInt(gid))) {
              collaborator["thumbnail"] = "@FontAwesome5Solid/globe/32";
            } else if (!collaborator["thumbnail"]) {
              collaborator["thumbnail"] = "@FontAwesome5Solid/users/26";
            }
          }
          collaborator["accessRights"] = accessRights[gid];
          collaborator["showOptions"] = showOptions;
          collaborator["resourceType"] = this._resourceType;
          collaboratorsList.push(collaborator);
        }
      }
      collaboratorsList.sort(this.self().sortStudyOrServiceCollabs);
      collaboratorsList.forEach(c => this.__collaboratorsModel.append(qx.data.marshal.Json.createModel(c)));
    },

    _addEditors: function(gids) {
      throw new Error("Abstract method called!");
    },

    _deleteMember: function(collaborator, item) {
      throw new Error("Abstract method called!");
    },

    _promoteToOwner: function(collaborator, item) {
      throw new Error("Abstract method called!");
    },

    _promoteToEditor: function(collaborator, item) {
      throw new Error("Abstract method called!");
    },

    _demoteToUser: function(collaborator, item) {
      throw new Error("Abstract method called!");
    },

    _demoteToEditor: function(collaborator, item) {
      throw new Error("Abstract method called!");
    }
  }
});
