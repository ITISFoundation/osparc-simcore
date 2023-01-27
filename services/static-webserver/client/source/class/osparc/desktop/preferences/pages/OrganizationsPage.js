/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Pedro Crespo (pcrespov)

************************************************************************ */

/**
 *  Organization and members in preferences dialog
 *
 */

qx.Class.define("osparc.desktop.preferences.pages.OrganizationsPage", {
  extend: osparc.desktop.preferences.pages.BasePage,

  construct: function() {
    const iconSrc = "@FontAwesome5Solid/sitemap/24";
    const title = this.tr("Organizations");
    this.base(arguments, title, iconSrc);

    const msg = this.tr("\
    An organization is any group of users that are able to share resources with each other.<br>\
    Here you may review the organizations you are a part of, create new ones, \
    or manage the membership and access rights of organizations where you are a manager/administrator.");
    const intro = this._createHelpLabel(msg);
    this._add(intro);

    this.add(this.__getOrganizationsSection());
    this.add(this.__getMembersSection(), {
      flex: 1
    });

    this.__reloadOrganizations();
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
      if (("label" in a) && ("label" in b)) {
        // orgs
        return a["label"].localeCompare(b["label"]);
      }
      if (("login" in a) && ("login" in b)) {
        // members
        return a["login"].localeCompare(b["login"]);
      }
      return 0;
    }
  },

  members: {
    __currentOrg: null,
    __orgsModel: null,
    __memberInvitation: null,
    __membersModel: null,

    __getCreateOrganizationSection: function() {
      const createOrgBtn = new qx.ui.form.Button().set({
        appearance: "strong-button",
        label: this.tr("New Organization"),
        alignX: "center",
        icon: "@FontAwesome5Solid/plus/14",
        allowGrowX: false
      });
      createOrgBtn.addListener("execute", function() {
        const newOrg = true;
        const orgEditor = new osparc.component.editor.OrganizationEditor(newOrg);
        const title = this.tr("Organization Details Editor");
        const win = osparc.ui.window.Window.popUpInWindow(orgEditor, title, 400, 250);
        orgEditor.addListener("createOrg", () => {
          this.__createOrganization(win, orgEditor.getChildControl("create"), orgEditor);
        });
        orgEditor.addListener("cancel", () => win.close());
      }, this);
      return createOrgBtn;
    },

    __getOrganizationsSection: function() {
      const box = this._createSectionBox(this.tr("Organizations"));
      if (osparc.data.Permissions.getInstance().canDo("user.organizations.create")) {
        box.add(this.__getCreateOrganizationSection());
      }
      box.add(this.__getOrganizationsList());
      box.setContentPadding(0);
      return box;
    },

    __getOrganizationsList: function() {
      const orgsUIList = new qx.ui.form.List().set({
        decorator: "no-border",
        spacing: 3,
        height: 150,
        width: 150,
        backgroundColor: "background-main-2"
      });
      orgsUIList.addListener("changeSelection", e => {
        this.__organizationSelected(e.getData());
      }, this);

      const orgsModel = this.__orgsModel = new qx.data.Array();
      const orgsCtrl = new qx.data.controller.List(orgsModel, orgsUIList, "label");
      orgsCtrl.setDelegate({
        createItem: () => new osparc.ui.list.OrganizationListItem(),
        bindItem: (ctrl, item, id) => {
          ctrl.bindProperty("gid", "model", null, item, id);
          ctrl.bindProperty("gid", "key", null, item, id);
          ctrl.bindProperty("thumbnail", "thumbnail", null, item, id);
          ctrl.bindProperty("label", "title", null, item, id);
          ctrl.bindProperty("description", "subtitle", null, item, id);
          ctrl.bindProperty("nMembers", "contact", null, item, id);
          ctrl.bindProperty("accessRights", "accessRights", null, item, id);
        },
        configureItem: item => {
          const thumbanil = item.getChildControl("thumbnail");
          thumbanil.getContentElement()
            .setStyles({
              "border-radius": "16px"
            });

          item.addListener("openEditOrganization", e => {
            const orgKey = e.getData();
            this.__openEditOrganization(orgKey);
          });

          item.addListener("deleteOrganization", e => {
            const orgKey = e.getData();
            this.__deleteOrganization(orgKey);
          });
        }
      });

      return orgsUIList;
    },

    __getMembersSection: function() {
      const box = this._createSectionBox(this.tr("Members"));
      box.add(this.__getMemberInvitation());
      box.add(this.__getMembersList(), {
        flex: 1
      });
      box.setContentPadding(0);
      return box;
    },

    __getMemberInvitation: function() {
      const hBox = this.__memberInvitation = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
        alignY: "middle"
      }));
      hBox.exclude();

      const userEmail = new qx.ui.form.TextField().set({
        required: true,
        placeholder: this.tr("New Member's email")
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
          ctrl.bindProperty("showOptions", "showOptions", null, item, id);
        },
        configureItem: item => {
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
            this.__promoteToAdministator(orgMember);
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

    __organizationSelected: function(data) {
      this.__memberInvitation.exclude();
      if (data && data.length>0) {
        this.__currentOrg = data[0];
      } else {
        this.__currentOrg = null;
      }
      this.__reloadOrgMembers();
    },

    __reloadOrganizations: function() {
      const orgsModel = this.__orgsModel;
      orgsModel.removeAll();

      osparc.data.Resources.get("organizations")
        .then(async respOrgs => {
          const orgs = respOrgs["organizations"];
          const promises = await orgs.map(async org => {
            const params = {
              url: {
                gid: org["gid"]
              }
            };
            const respOrgMembers = await osparc.data.Resources.get("organizationMembers", params);
            org["nMembers"] = Object.keys(respOrgMembers).length + this.tr(" members");
            return org;
          });
          const orgsList = await Promise.all(promises);
          orgsList.sort(this.self().sortByAccessRights);
          orgsList.forEach(org => orgsModel.append(qx.data.marshal.Json.createModel(org)));
        });
    },

    __reloadOrgMembers: function() {
      const membersModel = this.__membersModel;
      membersModel.removeAll();

      const orgModel = this.__currentOrg;
      if (orgModel === null) {
        return;
      }

      const canWrite = orgModel.getAccessRights().getWrite();
      if (canWrite) {
        this.__memberInvitation.show();
      }

      const params = {
        url: {
          "gid": orgModel.getKey()
        }
      };
      osparc.data.Resources.get("organizationMembers", params)
        .then(members => {
          const membersList = [];
          members.forEach(member => {
            member["thumbnail"] = osparc.utils.Avatar.getUrl(member["login"], 32);
            member["name"] = osparc.utils.Utils.firstsUp(member["first_name"], member["last_name"]);
            member["showOptions"] = canWrite;
            membersList.push(member);
          });
          membersList.sort(this.self().sortByAccessRights);
          membersList.forEach(member => membersModel.append(qx.data.marshal.Json.createModel(member)));
        });
    },

    __openEditOrganization: function(orgKey) {
      let org = null;
      this.__orgsModel.forEach(orgModel => {
        if (orgModel.getGid() === parseInt(orgKey)) {
          org = orgModel;
        }
      });
      if (org === null) {
        return;
      }

      const newOrg = false;
      const orgEditor = new osparc.component.editor.OrganizationEditor(newOrg);
      org.bind("gid", orgEditor, "gid");
      org.bind("label", orgEditor, "label");
      org.bind("description", orgEditor, "description");
      org.bind("thumbnail", orgEditor, "thumbnail", {
        converter: val => val ? val : ""
      });
      const title = this.tr("Organization Details Editor");
      const win = osparc.ui.window.Window.popUpInWindow(orgEditor, title, 400, 250);
      orgEditor.addListener("updateOrg", () => {
        this.__updateOrganization(win, orgEditor.getChildControl("save"), orgEditor);
      });
      orgEditor.addListener("cancel", () => win.close());
    },

    __deleteOrganization: function(orgKey) {
      let org = null;
      this.__orgsModel.forEach(orgModel => {
        if (orgModel.getGid() === parseInt(orgKey)) {
          org = orgModel;
        }
      });
      if (org === null) {
        return;
      }

      const name = org.getLabel();
      const msg = this.tr("Are you sure you want to delete ") + name + "?";
      const win = new osparc.ui.window.Confirmation(msg).set({
        confirmText: this.tr("Delete"),
        confirmAction: "delete"
      });
      win.center();
      win.open();
      win.addListener("close", () => {
        if (win.getConfirmed()) {
          const params = {
            url: {
              "gid": orgKey
            }
          };
          osparc.data.Resources.fetch("organizations", "delete", params)
            .then(() => {
              osparc.store.Store.getInstance().reset("organizations");
              // reload "profile", "organizations" are part of the information in this endpoint
              osparc.data.Resources.getOne("profile", {}, null, false)
                .then(() => {
                  this.__reloadOrganizations();
                });
            })
            .catch(err => {
              osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Something went wrong deleting ") + name, "ERROR");
              console.error(err);
            })
            .finally(() => {
              win.close();
            });
        }
      }, this);
    },

    __createOrganization: function(win, button, orgEditor) {
      const orgKey = orgEditor.getGid();
      const name = orgEditor.getLabel();
      const description = orgEditor.getDescription();
      const thumbnail = orgEditor.getThumbnail();
      const params = {
        url: {
          "gid": orgKey
        },
        data: {
          "label": name,
          "description": description,
          "thumbnail": thumbnail || null
        }
      };
      osparc.data.Resources.fetch("organizations", "post", params)
        .then(() => {
          osparc.component.message.FlashMessenger.getInstance().logAs(name + this.tr(" successfully created"));
          button.setFetching(false);
          osparc.store.Store.getInstance().reset("organizations");
          // reload "profile", "organizations" are part of the information in this endpoint
          osparc.data.Resources.getOne("profile", {}, null, false)
            .then(() => {
              this.__reloadOrganizations();
            });
        })
        .catch(err => {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Something went wrong creating ") + name, "ERROR");
          button.setFetching(false);
          console.error(err);
        })
        .finally(() => {
          win.close();
        });
    },

    __updateOrganization: function(win, button, orgEditor) {
      const orgKey = orgEditor.getGid();
      const name = orgEditor.getLabel();
      const description = orgEditor.getDescription();
      const thumbnail = orgEditor.getThumbnail();
      const params = {
        url: {
          "gid": orgKey
        },
        data: {
          "label": name,
          "description": description,
          "thumbnail": thumbnail || null
        }
      };
      osparc.data.Resources.fetch("organizations", "patch", params)
        .then(() => {
          osparc.component.message.FlashMessenger.getInstance().logAs(name + this.tr(" successfully edited"));
          button.setFetching(false);
          win.close();
          osparc.store.Store.getInstance().reset("organizations");
          this.__reloadOrganizations();
        })
        .catch(err => {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Something went wrong editing ") + name, "ERROR");
          button.setFetching(false);
          console.error(err);
        });
    },

    __addMember: function(orgMemberEmail) {
      if (this.__currentOrg === null) {
        return;
      }

      const orgId = this.__currentOrg.getKey();
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
          const store = osparc.store.Store.getInstance();
          store.getProductEveryone()
            .then(productEveryone => {
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
                      const msg = orgMemberEmail + this.tr(" added");
                      this.__demoteToUser(newMember, msg);
                    }
                  });
              } else {
                osparc.component.message.FlashMessenger.getInstance().logAs(orgMemberEmail + this.tr(" added"));
                osparc.store.Store.getInstance().reset("organizationMembers");
                this.__reloadOrgMembers();
              }
            });
        })
        .catch(err => {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Something went wrong adding the user"), "ERROR");
          console.error(err);
        });
    },

    __promoteToMember: function(orgMember) {
      if (this.__currentOrg === null) {
        return;
      }

      const params = {
        url: {
          "gid": this.__currentOrg.getKey(),
          "uid": orgMember["id"]
        },
        data: {
          "accessRights": this.self().getReadAccess()
        }
      };
      osparc.data.Resources.fetch("organizationMembers", "patch", params)
        .then(() => {
          osparc.component.message.FlashMessenger.getInstance().logAs(orgMember["name"] + this.tr(" successfully promoted to Member"));
          osparc.store.Store.getInstance().reset("organizationMembers");
          this.__reloadOrgMembers();
        })
        .catch(err => {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Something went wrong promoting ") + orgMember["name"], "ERROR");
          console.error(err);
        });
    },

    __demoteToUser: function(orgMember, msg) {
      if (this.__currentOrg === null) {
        return;
      }

      const params = {
        url: {
          "gid": this.__currentOrg.getKey(),
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
          osparc.component.message.FlashMessenger.getInstance().logAs(msg);
          osparc.store.Store.getInstance().reset("organizationMembers");
          this.__reloadOrgMembers();
        })
        .catch(err => {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Something went wrong demoting ") + orgMember["name"], "ERROR");
          console.error(err);
        });
    },

    __promoteToManager: function(orgMember) {
      if (this.__currentOrg === null) {
        return;
      }

      const params = {
        url: {
          "gid": this.__currentOrg.getKey(),
          "uid": orgMember["id"]
        },
        data: {
          "accessRights": this.self().getWriteAccess()
        }
      };
      osparc.data.Resources.fetch("organizationMembers", "patch", params)
        .then(() => {
          osparc.component.message.FlashMessenger.getInstance().logAs(orgMember["name"] + this.tr(" successfully promoted to Manager"));
          osparc.store.Store.getInstance().reset("organizationMembers");
          this.__reloadOrgMembers();
        })
        .catch(err => {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Something went wrong promoting ") + orgMember["name"], "ERROR");
          console.error(err);
        });
    },

    __promoteToAdministator: function(orgMember) {
      if (this.__currentOrg === null) {
        return;
      }

      const params = {
        url: {
          "gid": this.__currentOrg.getKey(),
          "uid": orgMember["id"]
        },
        data: {
          "accessRights": this.self().getDeleteAccess()
        }
      };
      osparc.data.Resources.fetch("organizationMembers", "patch", params)
        .then(() => {
          osparc.component.message.FlashMessenger.getInstance().logAs(orgMember["name"] + this.tr(" successfully promoted to Administrator"));
          osparc.store.Store.getInstance().reset("organizationMembers");
          this.__reloadOrgMembers();
        })
        .catch(err => {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Something went wrong promoting ") + orgMember["name"], "ERROR");
          console.error(err);
        });
    },

    __demoteToMember: function(orgMember) {
      if (this.__currentOrg === null) {
        return;
      }

      const params = {
        url: {
          "gid": this.__currentOrg.getKey(),
          "uid": orgMember["id"]
        },
        data: {
          "accessRights": this.self().getReadAccess()
        }
      };
      osparc.data.Resources.fetch("organizationMembers", "patch", params)
        .then(() => {
          osparc.component.message.FlashMessenger.getInstance().logAs(orgMember["name"] + this.tr(" successfully demoted to Member"));
          osparc.store.Store.getInstance().reset("organizationMembers");
          this.__reloadOrgMembers();
        })
        .catch(err => {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Something went wrong demoting ") + orgMember["name"], "ERROR");
          console.error(err);
        });
    },

    __demoteToManager: function(orgMember) {
      if (this.__currentOrg === null) {
        return;
      }

      const params = {
        url: {
          "gid": this.__currentOrg.getKey(),
          "uid": orgMember["id"]
        },
        data: {
          "accessRights": this.self().getWriteAccess()
        }
      };
      osparc.data.Resources.fetch("organizationMembers", "patch", params)
        .then(() => {
          osparc.component.message.FlashMessenger.getInstance().logAs(orgMember["name"] + this.tr(" successfully demoted to Manager"));
          osparc.store.Store.getInstance().reset("organizationMembers");
          this.__reloadOrgMembers();
        })
        .catch(err => {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Something went wrong demoting ") + orgMember["name"], "ERROR");
          console.error(err);
        });
    },

    __deleteMember: function(orgMember) {
      if (this.__currentOrg === null) {
        return;
      }

      const params = {
        url: {
          "gid": this.__currentOrg.getKey(),
          "uid": orgMember["id"]
        }
      };
      osparc.data.Resources.fetch("organizationMembers", "delete", params)
        .then(() => {
          osparc.component.message.FlashMessenger.getInstance().logAs(orgMember["name"] + this.tr(" successfully removed"));
          osparc.store.Store.getInstance().reset("organizationMembers");
          this.__reloadOrgMembers();
        })
        .catch(err => {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Something went wrong removing ") + orgMember["name"], "ERROR");
          console.error(err);
        });
    }
  }
});
