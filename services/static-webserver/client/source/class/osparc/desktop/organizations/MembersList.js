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
      const msg = this.tr("If you are a manager or administrator, you can add new members and promote or demote existing ones.");
      const intro = new qx.ui.basic.Label().set({
        value: msg,
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
      hBox.exclude();

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
      const memebersUIList = new qx.ui.form.List().set({
        decorator: "no-border",
        spacing: 3,
        width: 150,
        backgroundColor: "background-main-2"
      });

      const membersModel = this.__membersModel = new qx.data.Array();
      const membersCtrl = new qx.data.controller.List(membersModel, memebersUIList, "name");
      membersCtrl.setDelegate({
        createItem: () => new osparc.ui.list.MemberListItem(),
        bindItem: (ctrl, item, id) => {
          ctrl.bindProperty("id", "model", null, item, id);
          ctrl.bindProperty("id", "key", null, item, id);
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
            const clusterMember = e.getData();
            this.__promoteToMember(clusterMember);
          });
          item.addListener("promoteToManager", e => {
            const orgMember = e.getData();
            this.__promoteToManager(orgMember);
          });
          item.addListener("promoteToAdministrator", e => {
            const orgMember = e.getData();
            this.__promoteToAdministrator(orgMember);
          });
          item.addListener("demoteToUser", e => {
            const clusterMember = e.getData();
            this.__demoteToUser(clusterMember);
          });
          item.addListener("demoteToMember", e => {
            const orgMember = e.getData();
            this.__demoteToMember(orgMember);
          });
          item.addListener("demoteToManager", e => {
            const orgMember = e.getData();
            this.__demoteToManager(orgMember);
          });
          item.addListener("removeMember", e => {
            const orgMember = e.getData();
            this.__deleteMember(orgMember);
          });
        }
      });

      return memebersUIList;
    },

    __reloadOrgMembers: function() {
      const membersModel = this.__membersModel;
      membersModel.removeAll();

      const orgModel = this.__currentOrg;
      if (orgModel === null) {
        return;
      }

      const canIWrite = orgModel.getAccessRights().getWrite();
      const canIDelete = orgModel.getAccessRights().getDelete();
      this.__memberInvitation.set({
        visibility: canIWrite ? "visible" : "excluded"
      });

      const params = {
        url: {
          "gid": orgModel.getGid()
        }
      };
      osparc.data.Resources.get("organizationMembers", params)
        .then(members => {
          const membersList = [];
          members.forEach(member => {
            member["thumbnail"] = osparc.utils.Avatar.getUrl(member["login"], 32);
            member["name"] = osparc.utils.Utils.firstsUp(member["first_name"], member["last_name"]);
            let options = [];
            if (canIDelete) {
              // admin...
              if (member["accessRights"]["delete"]) {
                // ...on admin
                options = [];
              } else if (member["accessRights"]["write"]) {
                // ...on manager
                options = [
                  "promoteToAdministrator",
                  "demoteToMember",
                  "removeMember"
                ];
              } else if (member["accessRights"]["read"]) {
                // ...on member
                options = [
                  "promoteToManager",
                  "demoteToUser",
                  "removeMember"
                ];
              } else if (!member["accessRights"]["read"]) {
                // ...on user
                options = [
                  "promoteToMember",
                  "removeMember"
                ];
              }
            } else if (canIWrite) {
              // manager...
              if (member["accessRights"]["delete"]) {
                // ...on admin
                options = [];
              } else if (member["accessRights"]["write"]) {
                // ...on manager
                options = [];
              } else if (member["accessRights"]["read"]) {
                // ...on member
                options = [
                  "promoteToManager",
                  "demoteToUser",
                  "removeMember"
                ];
              } else if (!member["accessRights"]["read"]) {
                // ...on user
                options = [
                  "promoteToMember",
                  "removeMember"
                ];
              }
            }
            member["options"] = options;
            member["showOptions"] = Boolean(options.length);
            membersList.push(member);
          });
          membersList.sort(this.self().sortOrgMembers);
          membersList.forEach(member => membersModel.append(qx.data.marshal.Json.createModel(member)));
        });
    },

    __addMember: async function(orgMemberEmail) {
      if (this.__currentOrg === null) {
        return;
      }

      const productEveryone = await osparc.store.Store.getInstance().getProductEveryone();

      const orgId = this.__currentOrg.getGid();
      const params = {
        url: {
          "gid": orgId
        },
        data: {
          "email": orgMemberEmail
        }
      };
      osparc.data.Resources.fetch("organizationMembers", "post", params)
        .then(() => {
          const text = orgMemberEmail + this.tr(" successfully added.");
          if (productEveryone && productEveryone["gid"] === parseInt(orgId)) {
            // demote the new member to user
            const params2 = {
              url: {
                "gid": orgId
              }
            };
            osparc.data.Resources.get("organizationMembers", params2)
              .then(respOrgMembers => {
                const newMember = respOrgMembers.find(m => m["login"] === orgMemberEmail);
                if (newMember) {
                  this.__demoteToUser(newMember, text);
                }
              });
          } else {
            osparc.FlashMessenger.getInstance().logAs(text);
            osparc.store.Store.getInstance().reset("organizationMembers");
            this.__reloadOrgMembers();

            // push 'NEW_ORGANIZATION' notification
            const params2 = {
              url: {
                "gid": orgId
              }
            };
            osparc.data.Resources.get("organizationMembers", params2)
              .then(respOrgMembers => {
                const newMember = respOrgMembers.find(m => m["login"] === orgMemberEmail);
                if (newMember) {
                  osparc.notification.Notifications.postNewOrganization(newMember["id"], orgId);
                }
              });
          }
        })
        .catch(err => {
          osparc.FlashMessenger.getInstance().logAs(this.tr("Something went wrong adding the user"), "ERROR");
          console.error(err);
        });
    },

    __promoteToMember: function(orgMember) {
      if (this.__currentOrg === null) {
        return;
      }

      const params = {
        url: {
          "gid": this.__currentOrg.getGid(),
          "uid": orgMember["id"]
        },
        data: {
          "accessRights": this.self().getReadAccess()
        }
      };
      osparc.data.Resources.fetch("organizationMembers", "patch", params)
        .then(() => {
          osparc.FlashMessenger.getInstance().logAs(orgMember["name"] + this.tr(" successfully promoted to Member"));
          osparc.store.Store.getInstance().reset("organizationMembers");
          this.__reloadOrgMembers();
        })
        .catch(err => {
          osparc.FlashMessenger.getInstance().logAs(this.tr("Something went wrong promoting ") + orgMember["name"], "ERROR");
          console.error(err);
        });
    },

    __demoteToUser: function(orgMember, msg) {
      if (this.__currentOrg === null) {
        return;
      }

      const params = {
        url: {
          "gid": this.__currentOrg.getGid(),
          "uid": "id" in orgMember ? orgMember["id"] : orgMember["key"]
        },
        data: {
          "accessRights": this.self().getNoReadAccess()
        }
      };
      osparc.data.Resources.fetch("organizationMembers", "patch", params)
        .then(() => {
          if (msg === undefined) {
            msg = orgMember["name"] + this.tr(" successfully demoted to User");
          }
          osparc.FlashMessenger.getInstance().logAs(msg);
          osparc.store.Store.getInstance().reset("organizationMembers");
          this.__reloadOrgMembers();
        })
        .catch(err => {
          osparc.FlashMessenger.getInstance().logAs(this.tr("Something went wrong demoting ") + orgMember["name"], "ERROR");
          console.error(err);
        });
    },

    __promoteToManager: function(orgMember) {
      if (this.__currentOrg === null) {
        return;
      }

      const params = {
        url: {
          "gid": this.__currentOrg.getGid(),
          "uid": orgMember["id"]
        },
        data: {
          "accessRights": this.self().getWriteAccess()
        }
      };
      osparc.data.Resources.fetch("organizationMembers", "patch", params)
        .then(() => {
          osparc.FlashMessenger.getInstance().logAs(orgMember["name"] + this.tr(" successfully promoted to Manager"));
          osparc.store.Store.getInstance().reset("organizationMembers");
          this.__reloadOrgMembers();
        })
        .catch(err => {
          osparc.FlashMessenger.getInstance().logAs(this.tr("Something went wrong promoting ") + orgMember["name"], "ERROR");
          console.error(err);
        });
    },

    __promoteToAdministrator: function(orgMember) {
      if (this.__currentOrg === null) {
        return;
      }

      const params = {
        url: {
          "gid": this.__currentOrg.getGid(),
          "uid": orgMember["id"]
        },
        data: {
          "accessRights": this.self().getDeleteAccess()
        }
      };
      osparc.data.Resources.fetch("organizationMembers", "patch", params)
        .then(() => {
          osparc.FlashMessenger.getInstance().logAs(orgMember["name"] + this.tr(" successfully promoted to Administrator"));
          osparc.store.Store.getInstance().reset("organizationMembers");
          this.__reloadOrgMembers();
        })
        .catch(err => {
          osparc.FlashMessenger.getInstance().logAs(this.tr("Something went wrong promoting ") + orgMember["name"], "ERROR");
          console.error(err);
        });
    },

    __demoteToMember: function(orgMember) {
      if (this.__currentOrg === null) {
        return;
      }

      const params = {
        url: {
          "gid": this.__currentOrg.getGid(),
          "uid": orgMember["id"]
        },
        data: {
          "accessRights": this.self().getReadAccess()
        }
      };
      osparc.data.Resources.fetch("organizationMembers", "patch", params)
        .then(() => {
          osparc.FlashMessenger.getInstance().logAs(orgMember["name"] + this.tr(" successfully demoted to Member"));
          osparc.store.Store.getInstance().reset("organizationMembers");
          this.__reloadOrgMembers();
        })
        .catch(err => {
          osparc.FlashMessenger.getInstance().logAs(this.tr("Something went wrong demoting ") + orgMember["name"], "ERROR");
          console.error(err);
        });
    },

    __demoteToManager: function(orgMember) {
      if (this.__currentOrg === null) {
        return;
      }

      const params = {
        url: {
          "gid": this.__currentOrg.getGid(),
          "uid": orgMember["id"]
        },
        data: {
          "accessRights": this.self().getWriteAccess()
        }
      };
      osparc.data.Resources.fetch("organizationMembers", "patch", params)
        .then(() => {
          osparc.FlashMessenger.getInstance().logAs(orgMember["name"] + this.tr(" successfully demoted to Manager"));
          osparc.store.Store.getInstance().reset("organizationMembers");
          this.__reloadOrgMembers();
        })
        .catch(err => {
          osparc.FlashMessenger.getInstance().logAs(this.tr("Something went wrong demoting ") + orgMember["name"], "ERROR");
          console.error(err);
        });
    },

    __deleteMember: function(orgMember) {
      if (this.__currentOrg === null) {
        return;
      }

      const params = {
        url: {
          "gid": this.__currentOrg.getGid(),
          "uid": orgMember["id"]
        }
      };
      osparc.data.Resources.fetch("organizationMembers", "delete", params)
        .then(() => {
          osparc.FlashMessenger.getInstance().logAs(orgMember["name"] + this.tr(" successfully removed"));
          osparc.store.Store.getInstance().reset("organizationMembers");
          this.__reloadOrgMembers();
        })
        .catch(err => {
          osparc.FlashMessenger.getInstance().logAs(this.tr("Something went wrong removing ") + orgMember["name"], "ERROR");
          console.error(err);
        });
    }
  }
});
