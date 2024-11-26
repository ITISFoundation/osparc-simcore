/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.desktop.organizations.MembersList", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    this._add(this.__createIntroText());
    this._add(this.__getMemberInvitation());
    this._add(this.__getRolesToolbar());
    this._add(this.__getMembersFilter());
    this._add(this.__getMembersList(), {
      flex: 1
    });
  },

  statics: {
    getNoReadAccess: function() {
      return {
        "read": false,
        "write": false,
        "delete": false
      };
    },

    getReadAccess: function() {
      return {
        "read": true,
        "write": false,
        "delete": false
      };
    },

    getWriteAccess: function() {
      return {
        "read": true,
        "write": true,
        "delete": false
      };
    },

    getDeleteAccess: function() {
      return {
        "read": true,
        "write": true,
        "delete": true
      };
    },

    sortOrgMembers: function(a, b) {
      const sorted = osparc.share.Collaborators.sortByAccessRights(a["accessRights"], b["accessRights"]);
      if (sorted !== 0) {
        return sorted;
      }
      if (("login" in a) && ("login" in b)) {
        return a["login"].localeCompare(b["login"]);
      }
      return 0;
    }
  },

  members: {
    __currentOrg: null,
    __introLabel: null,
    __memberInvitation: null,
    __membersModel: null,

    setCurrentOrg: function(orgModel) {
      if (orgModel === null) {
        return;
      }
      this.__currentOrg = orgModel;
      this.__reloadOrgMembers();
    },

    __createIntroText: function() {
      const intro = this.__introLabel = new qx.ui.basic.Label().set({
        alignX: "left",
        rich: true,
        font: "text-13"
      });
      return intro;
    },

    __getMemberInvitation: function() {
      const hBox = this.__memberInvitation = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
        alignY: "middle"
      }));

      const userEmail = new qx.ui.form.TextField().set({
        required: true,
        placeholder: this.tr(" New Member's email")
      });
      hBox.add(userEmail, {
        flex: 1
      });

      const validator = new qx.ui.form.validation.Manager();
      validator.add(userEmail, qx.util.Validate.email());

      const addBtn = new qx.ui.form.Button(this.tr("Add"));
      addBtn.addListener("execute", function() {
        if (validator.validate()) {
          this.__addMember(userEmail.getValue());
        }
      }, this);
      hBox.add(addBtn);

      return hBox;
    },

    __getRolesToolbar: function() {
      return osparc.data.Roles.createRolesOrgInfo();
    },

    __getMembersFilter: function() {
      const filter = new osparc.filter.TextFilter("text", "organizationMembersList").set({
        allowStretchX: true,
        margin: [0, 10, 5, 10]
      });
      return filter;
    },

    __getMembersList: function() {
      const membersUIList = new qx.ui.form.List().set({
        decorator: "no-border",
        spacing: 3,
        width: 150
      });

      const membersModel = this.__membersModel = new qx.data.Array();
      const membersCtrl = new qx.data.controller.List(membersModel, membersUIList, "name");
      membersCtrl.setDelegate({
        createItem: () => new osparc.ui.list.MemberListItem(),
        bindItem: (ctrl, item, id) => {
          ctrl.bindProperty("userId", "model", null, item, id);
          ctrl.bindProperty("userId", "key", null, item, id);
          ctrl.bindProperty("thumbnail", "thumbnail", null, item, id);
          ctrl.bindProperty("name", "title", null, item, id);
          ctrl.bindProperty("accessRights", "accessRights", null, item, id);
          ctrl.bindProperty("login", "subtitleMD", null, item, id);
          ctrl.bindProperty("options", "options", null, item, id);
          ctrl.bindProperty("showOptions", "showOptions", null, item, id);
        },
        configureItem: item => {
          item.subscribeToFilterGroup("organizationMembersList");
          item.getChildControl("thumbnail").getContentElement()
            .setStyles({
              "border-radius": "16px"
            });
          item.addListener("promoteToMember", e => {
            const listedMember = e.getData();
            this.__promoteToUser(listedMember);
          });
          item.addListener("promoteToManager", e => {
            const listedMember = e.getData();
            this.__promoteToManager(listedMember);
          });
          item.addListener("promoteToAdministrator", e => {
            const listedMember = e.getData();
            this.__promoteToAdministrator(listedMember);
          });
          item.addListener("demoteToUser", e => {
            const listedMember = e.getData();
            this.__demoteToRestrictedUser(listedMember);
          });
          item.addListener("demoteToMember", e => {
            const listedMember = e.getData();
            this.__demoteToMember(listedMember);
          });
          item.addListener("demoteToManager", e => {
            const listedMember = e.getData();
            this.__demoteToManager(listedMember);
          });
          item.addListener("removeMember", e => {
            const listedMember = e.getData();
            this.__deleteMember(listedMember);
          });
          item.addListener("leaveResource", e => {
            const listedMember = e.getData();
            this.__deleteMyself(listedMember);
          });
        }
      });

      return membersUIList;
    },

    __reloadOrgMembers: function() {
      const membersModel = this.__membersModel;
      membersModel.removeAll();

      const organization = this.__currentOrg;
      if (organization === null) {
        return;
      }

      const canIWrite = organization.getAccessRights()["write"];
      const canIDelete = organization.getAccessRights()["delete"];

      const introText = canIWrite ?
        this.tr("You can add new members and promote or demote existing ones.") :
        this.tr("You can't add new members to this Organization. Please contact an Administrator or Manager.");
      this.__introLabel.setValue(introText);

      this.__memberInvitation.set({
        enabled: canIWrite
      });

      const membersList = [];
      const groupMembers = organization.getGroupMembers();
      Object.values(groupMembers).forEach(groupMember => {
        const member = {};
        member["userId"] = groupMember.getUserId();
        member["groupId"] = groupMember.getGroupId();
        member["thumbnail"] = groupMember.getThumbnail();
        member["name"] = groupMember.getLabel();
        member["login"] = groupMember.getLogin();
        member["accessRights"] = groupMember.getAccessRights();
        let options = [];
        if (canIDelete) {
          // admin...
          if (groupMember.getAccessRights()["delete"]) {
            // ...on admin
            options = [];
          } else if (groupMember.getAccessRights()["write"]) {
            // ...on manager
            options = [
              "promoteToAdministrator",
              "demoteToMember",
              "removeMember"
            ];
          } else if (groupMember.getAccessRights()["read"]) {
            // ...on member
            options = [
              "promoteToManager",
              "demoteToUser",
              "removeMember"
            ];
          } else if (!groupMember.getAccessRights()["read"]) {
            // ...on user
            options = [
              "promoteToMember",
              "removeMember"
            ];
          }
        } else if (canIWrite) {
          // manager...
          if (groupMember.getAccessRights()["delete"]) {
            // ...on admin
            options = [];
          } else if (groupMember.getAccessRights()["write"]) {
            // ...on manager
            options = [];
          } else if (groupMember.getAccessRights()["read"]) {
            // ...on member
            options = [
              "promoteToManager",
              "demoteToUser",
              "removeMember"
            ];
          } else if (!groupMember.getAccessRights()["read"]) {
            // ...on user
            options = [
              "promoteToMember",
              "removeMember"
            ];
          }
        }
        // Let me go?
        const openStudy = osparc.store.Store.getInstance().getCurrentStudy();
        const myGroupId = osparc.store.Groups.getInstance().getMyGroupId();
        if (
          openStudy === null &&
          canIWrite &&
          groupMembers.length > 1 && groupMember.getGroupId() === myGroupId
        ) {
          options.push("leave");
        }
        member["options"] = options;
        member["showOptions"] = Boolean(options.length);
        membersList.push(member);
      });
      membersList.sort(this.self().sortOrgMembers);
      membersList.forEach(member => membersModel.append(qx.data.marshal.Json.createModel(member)));
    },

    __addMember: async function(orgMemberEmail) {
      if (this.__currentOrg === null) {
        return;
      }

      const orgId = this.__currentOrg.getGroupId();
      const groupsStore = osparc.store.Groups.getInstance();
      groupsStore.postMember(orgId, orgMemberEmail)
        .then(newMember => {
          const text = orgMemberEmail + this.tr(" successfully added");
          osparc.FlashMessenger.getInstance().logAs(text);
          this.__reloadOrgMembers();

          // push 'NEW_ORGANIZATION' notification
          osparc.notification.Notifications.postNewOrganization(newMember.getUserId(), orgId);
        })
        .catch(err => {
          const errorMessage = err["message"] || this.tr("Something went wrong adding the user");
          osparc.FlashMessenger.getInstance().logAs(errorMessage, "ERROR");
          console.error(err);
        });
    },

    __promoteToUser: function(listedMember) {
      if (this.__currentOrg === null) {
        return;
      }

      const newAccessRights = this.self().getReadAccess();
      const groupsStore = osparc.store.Groups.getInstance();
      groupsStore.patchMember(this.__currentOrg.getGroupId(), listedMember["id"], newAccessRights)
        .then(() => {
          osparc.FlashMessenger.getInstance().logAs(this.tr(`Successfully promoted to ${osparc.data.Roles.ORG[1].label}`));
          this.__reloadOrgMembers();
        })
        .catch(err => {
          osparc.FlashMessenger.getInstance().logAs(this.tr("Something went wrong promoting to ") + osparc.data.Roles.ORG[1].label, "ERROR");
          console.error(err);
        });
    },

    __demoteToRestrictedUser: function(listedMember, msg) {
      if (this.__currentOrg === null) {
        return;
      }

      const orgId = this.__currentOrg.getGroupId();
      const userId = "id" in listedMember ? listedMember["id"] : listedMember["key"]
      const newAccessRights = this.self().getNoReadAccess();
      const groupsStore = osparc.store.Groups.getInstance();
      groupsStore.patchAccessRights(orgId, userId, newAccessRights)
        .then(() => {
          if (msg === undefined) {
            msg = this.tr(`Successfully demoted to ${osparc.data.Roles.ORG[0].label}`);
          }
          osparc.FlashMessenger.getInstance().logAs(msg);
          this.__reloadOrgMembers();
        })
        .catch(err => {
          osparc.FlashMessenger.getInstance().logAs(this.tr("Something went wrong demoting to ") + osparc.data.Roles.ORG[0].label, "ERROR");
          console.error(err);
        });
    },

    __promoteToManager: function(listedMember) {
      if (this.__currentOrg === null) {
        return;
      }

      const orgId = this.__currentOrg.getGroupId();
      const userId = listedMember["id"];
      const newAccessRights = this.self().getWriteAccess();
      const groupsStore = osparc.store.Groups.getInstance();
      groupsStore.patchAccessRights(orgId, userId, newAccessRights)
        .then(() => {
          osparc.FlashMessenger.getInstance().logAs(this.tr(`Successfully promoted to ${osparc.data.Roles.ORG[2].label}`));
          this.__reloadOrgMembers();
        })
        .catch(err => {
          osparc.FlashMessenger.getInstance().logAs(this.tr("Something went wrong promoting to ") + osparc.data.Roles.ORG[2].label, "ERROR");
          console.error(err);
        });
    },

    __promoteToAdministrator: function(listedMember) {
      if (this.__currentOrg === null) {
        return;
      }

      const orgId = this.__currentOrg.getGroupId();
      const userId = listedMember["id"];
      const newAccessRights = this.self().getDeleteAccess();
      const groupsStore = osparc.store.Groups.getInstance();
      groupsStore.patchAccessRights(orgId, userId, newAccessRights)
        .then(() => {
          osparc.FlashMessenger.getInstance().logAs(this.tr(`Successfully promoted to ${osparc.data.Roles.ORG[3].label}`));
          this.__reloadOrgMembers();
        })
        .catch(err => {
          osparc.FlashMessenger.getInstance().logAs(this.tr("Something went wrong promoting to ") + osparc.data.Roles.ORG[3].label, "ERROR");
          console.error(err);
        });
    },

    __demoteToMember: function(listedMember) {
      if (this.__currentOrg === null) {
        return;
      }

      const orgId = this.__currentOrg.getGroupId();
      const userId = listedMember["id"];
      const newAccessRights = this.self().getReadAccess();
      const groupsStore = osparc.store.Groups.getInstance();
      groupsStore.patchAccessRights(orgId, userId, newAccessRights)
        .then(() => {
          osparc.FlashMessenger.getInstance().logAs(this.tr(`Successfully demoted to ${osparc.data.Roles.ORG[1].label}`));
          this.__reloadOrgMembers();
        })
        .catch(err => {
          osparc.FlashMessenger.getInstance().logAs(this.tr("Something went wrong demoting to ") + osparc.data.Roles.ORG[1].label, "ERROR");
          console.error(err);
        });
    },

    __demoteToManager: function(listedMember) {
      if (this.__currentOrg === null) {
        return;
      }

      const orgId = this.__currentOrg.getGroupId();
      const userId = listedMember["id"];
      const newAccessRights = this.self().getWriteAccess();
      const groupsStore = osparc.store.Groups.getInstance();
      groupsStore.patchAccessRights(orgId, userId, newAccessRights)
        .then(() => {
          osparc.FlashMessenger.getInstance().logAs(this.tr(`Successfully demoted to ${osparc.data.Roles.ORG[3].label}`));
          this.__reloadOrgMembers();
        })
        .catch(err => {
          osparc.FlashMessenger.getInstance().logAs(this.tr("Something went wrong demoting to ") + osparc.data.Roles.ORG[3].label, "ERROR");
          console.error(err);
        });
    },

    __doDeleteMember: function(listedMember) {
      const groupsStore = osparc.store.Groups.getInstance();
      return groupsStore.removeMember(this.__currentOrg.getGroupId(), listedMember["id"])
        .then(() => {
          osparc.FlashMessenger.getInstance().logAs(listedMember["name"] + this.tr(" successfully removed"));
          this.__reloadOrgMembers();
        })
        .catch(err => {
          osparc.FlashMessenger.getInstance().logAs(this.tr("Something went wrong removing ") + listedMember["name"], "ERROR");
          console.error(err);
        });
    },

    __deleteMember: function(listedMember) {
      if (this.__currentOrg === null) {
        return;
      }

      this.__doDeleteMember(listedMember)
        .then(() => this.__reloadOrgMembers());
    },

    __deleteMyself: function(orgMember) {
      if (this.__currentOrg === null) {
        return;
      }

      const members = this.__currentOrg.getGroupMembers()
      const isThereAnyAdmin = members.some(member => member.getAccessRights()["delete"]);
      const isThereAnyManager = members.some(member => member.getAccessRights()["write"]);
      let rUSure = this.tr("Are you sure you want to leave?");
      if (isThereAnyAdmin) {
        rUSure += `<br>There is no ${osparc.data.Roles.ORG[2].label} in this Organization.`;
      } else if (isThereAnyManager) {
        rUSure += `<br>There is no ${osparc.data.Roles.ORG[3].label} in this Organization.`;
      }
      rUSure += "<br><br>" + this.tr("If you Leave, the page will be reloaded.");
      const confirmationWin = new osparc.ui.window.Confirmation(rUSure).set({
        caption: this.tr("Leave Organization"),
        confirmText: this.tr("Leave"),
        confirmAction: "delete"
      });
      confirmationWin.center();
      confirmationWin.open();
      confirmationWin.addListener("close", () => {
        if (confirmationWin.getConfirmed()) {
          this.__doDeleteMember(orgMember)
            .then(() => window.location.reload());
        }
      }, this);
    }
  }
});
