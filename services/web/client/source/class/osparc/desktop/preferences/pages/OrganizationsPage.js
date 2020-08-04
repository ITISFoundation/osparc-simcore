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

    if (osparc.data.Permissions.getInstance().canDo("user.organizations.create")) {
      this.add(this.__getCreateOrganizationSection());
    }
    this.add(this.__getOrganizationsSection());
    this.add(this.__getMembersSection(), {
      flex: 1
    });

    this.__reloadOrganizations();
  },

  members: {
    __currentOrg: null,
    __orgsModel: null,
    __memberInvitation: null,
    __membersModel: null,

    __getCreateOrganizationSection: function() {
      const createOrgBtn = new qx.ui.form.Button(this.tr("Create New Organization")).set({
        allowGrowX: false
      });
      createOrgBtn.addListener("execute", function() {
        const newOrg = true;
        const orgEditor = new osparc.dashboard.OrganizationEditor(newOrg);
        const win = osparc.dashboard.OrganizationEditor.popUpInWindow(this.tr("Organization Details Editor"), orgEditor);
        orgEditor.addListener("createOrg", () => {
          this.__createOrganization(win, orgEditor.getChildControl("create"), orgEditor);
        });
      }, this);
      return createOrgBtn;
    },

    __getOrganizationsSection: function() {
      const box = this._createSectionBox(this.tr("Organizations"));
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
        backgroundColor: "material-button-background"
      });
      orgsUIList.addListener("changeSelection", e => {
        this.__organizationSelected(e.getData());
      }, this);

      const orgsModel = this.__orgsModel = new qx.data.Array();
      const orgsCtrl = new qx.data.controller.List(orgsModel, orgsUIList, "label");
      orgsCtrl.setDelegate({
        createItem: () => new osparc.dashboard.OrganizationListItem(),
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
            this.__openEditOrganization(e.getData());
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

      const inviteBtn = new qx.ui.form.Button(this.tr("Invite"));
      inviteBtn.addListener("execute", function() {
        if (validator.validate()) {
          this.__addMember(userEmail.getValue());
        }
      }, this);
      hBox.add(inviteBtn);

      return hBox;
    },

    __getMembersList: function() {
      const memebersUIList = new qx.ui.form.List().set({
        decorator: "no-border",
        spacing: 3,
        width: 150,
        backgroundColor: "material-button-background"
      });

      const membersModel = this.__membersModel = new qx.data.Array();
      const membersCtrl = new qx.data.controller.List(membersModel, memebersUIList, "name");
      membersCtrl.setDelegate({
        createItem: () => new osparc.dashboard.OrgMemberListItem(),
        bindItem: (ctrl, item, id) => {
          ctrl.bindProperty("id", "model", null, item, id);
          ctrl.bindProperty("id", "key", null, item, id);
          ctrl.bindProperty("thumbnail", "thumbnail", null, item, id);
          ctrl.bindProperty("name", "title", null, item, id);
          ctrl.bindProperty("accessRights", "accessRights", null, item, id);
          ctrl.bindProperty("login", "subtitle", null, item, id);
          ctrl.bindProperty("showOptions", "showOptions", null, item, id);
        },
        configureItem: item => {
          item.getChildControl("thumbnail").getContentElement()
            .setStyles({
              "border-radius": "16px"
            });
          item.addListener("promoteOrgMember", e => {
            const orgMember = e.getData();
            this.__promoteMember(orgMember);
          });
          item.addListener("removeOrgMember", e => {
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
        .then(respOrgs => {
          const orgs = respOrgs["organizations"];
          orgs.forEach(org => {
            const params = {
              url: {
                gid: org["gid"]
              }
            };
            osparc.data.Resources.get("organizationMembers", params)
              .then(respOrgMembers => {
                org["nMembers"] = Object.keys(respOrgMembers).length + this.tr(" members");
                orgsModel.append(qx.data.marshal.Json.createModel(org));
              });
          });
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
          members.forEach(member => {
            member["thumbnail"] = osparc.utils.Avatar.getUrl(member["login"], 32);
            member["name"] = osparc.utils.Utils.firstsUp(member["first_name"], member["last_name"]);
            member["showOptions"] = canWrite;
            membersModel.append(qx.data.marshal.Json.createModel(member));
          });
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
      const orgEditor = new osparc.dashboard.OrganizationEditor(newOrg);
      org.bind("gid", orgEditor, "gid");
      org.bind("label", orgEditor, "label");
      org.bind("description", orgEditor, "description");
      org.bind("thumbnail", orgEditor, "thumbnail", {
        converter: val => val ? val : ""
      });
      const win = osparc.dashboard.OrganizationEditor.popUpInWindow(this.tr("Organization Details Editor"), orgEditor);
      orgEditor.addListener("updateOrg", () => {
        this.__updateOrganization(win, orgEditor.getChildControl("save"), orgEditor);
      });
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
          win.close();
          osparc.store.Store.getInstance().reset("organizations");
          this.__reloadOrganizations();
        })
        .catch(err => {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Something went wrong creating ") + name, "ERROR");
          button.setFetching(false);
          console.error(err);
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

      const params = {
        url: {
          "gid": this.__currentOrg.getKey()
        },
        data: {
          "email": orgMemberEmail
        }
      };
      osparc.data.Resources.fetch("organizationMembers", "post", params)
        .then(() => {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Invitation sent to ") + orgMemberEmail);
          osparc.store.Store.getInstance().reset("organizationMembers");
          this.__reloadOrgMembers();
        })
        .catch(err => {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Something went wrong with the invitation"), "ERROR");
          console.error(err);
        });
    },

    __promoteMember: function(orgMember) {
      if (this.__currentOrg === null) {
        return;
      }

      const params = {
        url: {
          "gid": this.__currentOrg.getKey(),
          "uid": orgMember["key"]
        },
        data: {
          "accessRights": {
            "read": true,
            "write": true,
            "delete": false
          }
        }
      };
      osparc.data.Resources.fetch("organizationMembers", "patch", params)
        .then(() => {
          osparc.component.message.FlashMessenger.getInstance().logAs(orgMember["name"] + this.tr(" successfully promoted"));
          osparc.store.Store.getInstance().reset("organizationMembers");
          this.__reloadOrgMembers();
        })
        .catch(err => {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Something went wrong promoting ") + orgMember["name"], "ERROR");
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
          "uid": orgMember["key"]
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
