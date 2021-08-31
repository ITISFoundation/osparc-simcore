/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaz)

************************************************************************ */

/**
 *  Clusters and members in preferences dialog
 *
 */

qx.Class.define("osparc.desktop.preferences.pages.ClustersPage", {
  extend: osparc.desktop.preferences.pages.BasePage,

  construct: function() {
    // const iconSrc = "@FontAwesome5Solid/hubspot/24";
    const iconSrc = "@FontAwesome5Solid/cat/24";
    const title = this.tr("Clusters");
    this.base(arguments, title, iconSrc);

    if (osparc.data.Permissions.getInstance().canDo("user.clusters.create")) {
      this.add(this.__getCreateClusterSection());
    }
    this.add(this.__getClustersSection());
    this.add(this.__getMembersSection(), {
      flex: 1
    });

    this.__reloadClusters();
  },

  members: {
    __currentCluster: null,
    __clustersModel: null,
    __memberInvitation: null,
    __membersModel: null,

    __getCreateClusterSection: function() {
      const createClusterBtn = new qx.ui.form.Button(this.tr("Create New Cluster")).set({
        allowGrowX: false
      });
      createClusterBtn.addListener("execute", function() {
        const newOrg = true;
        const orgEditor = new osparc.dashboard.ClusterEditor(newOrg);
        const title = this.tr("Cluster Details Editor");
        const win = osparc.ui.window.Window.popUpInWindow(orgEditor, title, 400, 250);
        orgEditor.addListener("createCluster", () => {
          this.__createCluster(win, orgEditor.getChildControl("create"), orgEditor);
        });
        orgEditor.addListener("cancel", () => win.close());
      }, this);
      return createClusterBtn;
    },

    __getClustersSection: function() {
      const box = this._createSectionBox(this.tr("Clusters"));
      box.add(this.__getClustersList());
      box.setContentPadding(0);
      return box;
    },

    __getClustersList: function() {
      const clustersUIList = new qx.ui.form.List().set({
        decorator: "no-border",
        spacing: 3,
        height: 150,
        width: 150,
        backgroundColor: "material-button-background"
      });
      clustersUIList.addListener("changeSelection", e => {
        this.__clusterSelected(e.getData());
      }, this);

      const clustersModel = this.__clustersModel = new qx.data.Array();
      const clustersCtrl = new qx.data.controller.List(clustersModel, clustersUIList, "name");
      clustersCtrl.setDelegate({
        createItem: () => new osparc.dashboard.ClusterListItem(),
        bindItem: (ctrl, item, id) => {
          ctrl.bindProperty("gid", "model", null, item, id);
          ctrl.bindProperty("gid", "key", null, item, id);
          ctrl.bindProperty("name", "title", null, item, id);
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

          item.addListener("openEditCluster", e => {
            // const orgKey = e.getData();
            // this.__openEditCluster(orgKey);
          });

          item.addListener("deleteCluster", e => {
            const orgKey = e.getData();
            this.__deleteCluster(orgKey);
          });
        }
      });

      return clustersUIList;
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

    __clusterSelected: function(data) {
      this.__memberInvitation.exclude();
      if (data && data.length>0) {
        this.__currentCluster = data[0];
      } else {
        this.__currentCluster = null;
      }
      this.__reloadOrgMembers();
    },

    __reloadClusters: function() {
      const orgsModel = this.__clustersModel;
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

      const orgModel = this.__currentCluster;
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

    __openEditCluster: function(orgKey) {
      let org = null;
      this.__clustersModel.forEach(orgModel => {
        if (orgModel.getGid() === parseInt(orgKey)) {
          org = orgModel;
        }
      });
      if (org === null) {
        return;
      }

      const newOrg = false;
      const orgEditor = new osparc.dashboard.ClusterEditor(newOrg);
      org.bind("gid", orgEditor, "gid");
      org.bind("name", orgEditor, "label");
      org.bind("description", orgEditor, "description");
      const title = this.tr("Cluster Details Editor");
      const win = osparc.ui.window.Window.popUpInWindow(orgEditor, title, 400, 250);
      orgEditor.addListener("updateOrg", () => {
        this.__updateCluster(win, orgEditor.getChildControl("save"), orgEditor);
      });
      orgEditor.addListener("cancel", () => win.close());
    },

    __deleteCluster: function(orgKey) {
      let org = null;
      this.__clustersModel.forEach(orgModel => {
        if (orgModel.getGid() === parseInt(orgKey)) {
          org = orgModel;
        }
      });
      if (org === null) {
        return;
      }

      const name = org.getLabel();
      const msg = this.tr("Are you sure you want to delete ") + name + "?";
      const win = new osparc.ui.window.Confirmation(msg);
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
                  this.__reloadClusters();
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

    __createCluster: function(win, button, orgEditor) {
      const clusterKey = orgEditor.getCid();
      const name = orgEditor.getLabel();
      const description = orgEditor.getDescription();
      const params = {
        url: {
          "cid": clusterKey
        },
        data: {
          "name": name,
          "description": description,
          "type": "AWS"
        }
      };
      osparc.data.Resources.fetch("clusters", "post", params)
        .then(() => {
          osparc.component.message.FlashMessenger.getInstance().logAs(name + this.tr(" successfully created"));
          button.setFetching(false);
          osparc.store.Store.getInstance().reset("clusters");
          // reload "profile", "organizations" are part of the information in this endpoint
          osparc.data.Resources.getOne("profile", {}, null, false)
            .then(() => {
              this.__reloadClusters();
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

    __updateCluster: function(win, button, orgEditor) {
      const orgKey = orgEditor.getGid();
      const name = orgEditor.getLabel();
      const description = orgEditor.getDescription();
      const thumbnail = orgEditor.getThumbnail();
      const params = {
        url: {
          "gid": orgKey
        },
        data: {
          "name": name,
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
          this.__reloadClusters();
        })
        .catch(err => {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Something went wrong editing ") + name, "ERROR");
          button.setFetching(false);
          console.error(err);
        });
    },

    __addMember: function(orgMemberEmail) {
      if (this.__currentCluster === null) {
        return;
      }

      const params = {
        url: {
          "gid": this.__currentCluster.getKey()
        },
        data: {
          "email": orgMemberEmail
        }
      };
      osparc.data.Resources.fetch("organizationMembers", "post", params)
        .then(() => {
          osparc.component.message.FlashMessenger.getInstance().logAs(orgMemberEmail + this.tr(" added"));
          osparc.store.Store.getInstance().reset("organizationMembers");
          this.__reloadOrgMembers();
        })
        .catch(err => {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Something went wrong with the invitation"), "ERROR");
          console.error(err);
        });
    },

    __promoteMember: function(orgMember) {
      if (this.__currentCluster === null) {
        return;
      }

      const params = {
        url: {
          "gid": this.__currentCluster.getKey(),
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
      if (this.__currentCluster === null) {
        return;
      }

      const params = {
        url: {
          "gid": this.__currentCluster.getKey(),
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
