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

qx.Class.define("osparc.component.share.Collaborators", {
  extend: qx.ui.core.Widget,
  type: "abstract",

  /**
    * @param serializedData {Object} Object containing the Serialized Data
    */
  construct: function(serializedData, initCollabs = []) {
    this.base(arguments);

    this._serializedData = serializedData;

    this._setLayout(new qx.ui.layout.VBox(10));

    this.set({
      padding: 5
    });

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
          osparc.desktop.organizations.OrganizationsWindow.evaluateOrganizationsButton(control);
          control.addListener("execute", () => osparc.desktop.organizations.OrganizationsWindow.openWindow(), this);
          this._add(control, {
            flex: 1
          });
          break;
        case "study-link":
          control = this.self().createStudyLinkSection(this._serializedData);
          this._add(control);
          // excluded by default
          control.exclude();
          break;
        case "template-link":
          control = this.self().createTemplateLinkSection(this._serializedData);
          this._add(control);
          // excluded by default
          control.exclude();
          break;
      }
      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      this._createChildControlImpl("add-collaborator");
      this._createChildControlImpl("open-organizations-btn");
      this._createChildControlImpl("collaborators-list");
      this._createChildControlImpl("study-link");
      this._createChildControlImpl("template-link");
    },

    __createAddCollaboratorSection: function() {
      const vBox = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
      if ("uuid" in this._serializedData) {
        // study
        vBox.setVisibility(this._canIDelete() ? "visible" : "excluded");
      } else {
        // service
        vBox.setVisibility(this._canIWrite() ? "visible" : "excluded");
      }

      const label = new qx.ui.basic.Label(this.tr("Select from the list below and click Share"));
      vBox.add(label);

      const addCollaboratorBtn = new qx.ui.form.Button(this.tr("Add Collaborators...")).set({
        appearance: "strong-button",
        allowGrowX: false
      });
      addCollaboratorBtn.addListener("execute", () => {
        const collaboratorsManager = new osparc.component.share.NewCollaboratorsManager(this._serializedData);
        collaboratorsManager.addListener("addCollaborators", e => {
          const cb = () => collaboratorsManager.close();
          this._addCollaborators(e.getData(), cb);
        }, this);
      }, this);
      vBox.add(addCollaboratorBtn);

      return vBox;
    },

    __createCollaboratorsListSection: function() {
      const vBox = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));

      const label = new qx.ui.basic.Label(this.tr("Shared with"));
      vBox.add(label);

      const rolesLayout = osparc.data.Roles.createRolesResourceInfo();
      const leaveButton = this.__getLeaveStudyButton();
      if (leaveButton) {
        rolesLayout.addAt(leaveButton, 0);
      }
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
            this._promoteToCollaborator(orgMember, item);
          });
          item.addListener("promoteToOwner", e => {
            const orgMember = e.getData();
            this._promoteToOwner(orgMember, item);
          });
          item.addListener("demoteToViewer", e => {
            const orgMember = e.getData();
            this._demoteToViewer(orgMember, item);
          });
          item.addListener("demoteToCollaborator", e => {
            const orgMember = e.getData();
            this._demoteToCollaborator(orgMember, item);
          });
          item.addListener("removeMember", e => {
            const orgMember = e.getData();
            this._deleteMember(orgMember, item);
          });
        }
      });
      vBox.add(collaboratorsUIList, {
        flex: 1
      });

      return vBox;
    },

    __getCollaborators: function() {
      osparc.store.Store.getInstance().getPotentialCollaborators()
        .then(potentialCollaborators => {
          this.__collaborators = Object.assign(this.__collaborators, potentialCollaborators);
          this._reloadCollaboratorsList();
        });
    },

    __getLeaveStudyButton: function() {
      if (osparc.utils.Resources.isStudy(this._serializedData)) {
        const myGid = osparc.auth.Data.getInstance().getGroupId();
        const leaveButton = new qx.ui.form.Button(this.tr("Leave Study")).set({
          allowGrowX: false,
          visibility: Object.keys(this._serializedData["accessRights"]).includes(myGid.toString()) ? "visible" : "excluded"
        });
        leaveButton.addListener("execute", () => {
          if (osparc.component.share.CollaboratorsStudy.checkRemoveCollaborator(this._serializedData, myGid)) {
            // OM: XXXXXXXXXXXXXXXXXXXXX
            // this._deleteMember({gid: myGid});
            console.log("delete member", myGid);
          }
        }, this);
        return leaveButton;
      }
      return null;
    },

    _reloadCollaboratorsList: function() {
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

    _canIDelete: function() {
      throw new Error("Abstract method called!");
    },

    _canIWrite: function() {
      throw new Error("Abstract method called!");
    },

    _addCollaborators: function(gids) {
      throw new Error("Abstract method called!");
    },

    _deleteMember: function(collaborator, item) {
      throw new Error("Abstract method called!");
    },

    _promoteToOwner: function(collaborator, item) {
      throw new Error("Abstract method called!");
    },

    _promoteToCollaborator: function(collaborator, item) {
      throw new Error("Abstract method called!");
    },

    _demoteToViewer: function(collaborator, item) {
      throw new Error("Abstract method called!");
    },

    _demoteToCollaborator: function(collaborator, item) {
      throw new Error("Abstract method called!");
    }
  }
});
