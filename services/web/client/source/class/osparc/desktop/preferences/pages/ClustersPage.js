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
    const iconSrc = "@FontAwesome5Solid/server/24";
    // const iconSrc = "@FontAwesome5Brands/hubspot/24";
    const title = this.tr("Clusters");
    this.base(arguments, title, iconSrc);

    if (osparc.data.Permissions.getInstance().canDo("user.clusters.create")) {
      this.add(this.__getCreateClusterSection());
    }
    this.add(this.__getClustersSection());
    this.add(this.__getOrgsAndMembersSection(), {
      flex: 1
    });

    this.__reloadClusters();
  },

  members: {
    __currentCluster: null,
    __clustersModel: null,
    __selectOrgMemberLayout: null,
    __orgsAndMembersFilter: null,
    __membersModel: null,

    __getCreateClusterSection: function() {
      const createClusterBtn = new qx.ui.form.Button(this.tr("Create New Cluster")).set({
        allowGrowX: false
      });
      createClusterBtn.addListener("execute", function() {
        const newCluster = true;
        const clusterEditor = new osparc.dashboard.ClusterEditor(newCluster);
        const title = this.tr("Cluster Details Editor");
        const win = osparc.ui.window.Window.popUpInWindow(clusterEditor, title, 400, 200);
        clusterEditor.addListener("createCluster", () => {
          this.__createCluster(win, clusterEditor.getChildControl("create"), clusterEditor);
        });
        clusterEditor.addListener("cancel", () => win.close());
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
          ctrl.bindProperty("id", "model", null, item, id);
          ctrl.bindProperty("id", "key", null, item, id);
          ctrl.bindProperty("name", "title", null, item, id);
          ctrl.bindProperty("description", "subtitle", null, item, id);
          ctrl.bindProperty("access_rights", "members", null, item, id);
        },
        configureItem: item => {
          item.addListener("openEditCluster", e => {
            const clusterId = e.getData();
            this.__openEditCluster(clusterId);
          });

          item.addListener("deleteCluster", e => {
            const clusterId = e.getData();
            this.__deleteCluster(clusterId);
          });
        }
      });

      return clustersUIList;
    },

    __getOrgsAndMembersSection: function() {
      const box = this._createSectionBox(this.tr("Organization and Members"));
      box.add(this.__getOrgMembersFilter());
      box.add(this.__getMembersList(), {
        flex: 1
      });
      box.setContentPadding(0);
      return box;
    },

    __getOrgMembersFilter: function() {
      const vBox = this.__selectOrgMemberLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox());
      vBox.exclude();

      const label = new qx.ui.basic.Label(this.tr("Select from the following list")).set({
        paddingLeft: 5
      });
      vBox.add(label);

      const hBox = new qx.ui.container.Composite(new qx.ui.layout.HBox(5).set({
        alignY: "middle"
      }));
      vBox.add(hBox);

      const orgsAndMembersFilter = this.__orgsAndMembersFilter = new osparc.component.filter.OrganizationsAndMembers("orgAndMembClusters");
      hBox.add(orgsAndMembersFilter, {
        flex: 1
      });

      const addCollaboratorBtn = new qx.ui.form.Button(this.tr("Add")).set({
        allowGrowY: false,
        enabled: false
      });
      addCollaboratorBtn.addListener("execute", () => {
        this.__addMembers();
      }, this);
      qx.event.message.Bus.getInstance().subscribe("orgAndMembClusters", () => {
        const anySelected = Boolean(this.__organizationsAndMembers.getSelectedGIDs().length);
        this.__addCollaboratorBtn.setEnabled(anySelected);
      }, this);

      hBox.add(addCollaboratorBtn);

      return vBox;
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
        createItem: () => new osparc.dashboard.MemberListItem(),
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
          item.addListener("promoteToManager", e => {
            const clusterMember = e.getData();
            this.__promoteToManager(clusterMember);
          });
          item.addListener("removeMember", e => {
            const clusterMember = e.getData();
            this.__deleteMember(clusterMember);
          });
        }
      });

      return memebersUIList;
    },

    __clusterSelected: function(data) {
      this.__selectOrgMemberLayout.exclude();
      if (data && data.length>0) {
        this.__currentCluster = data[0];
      } else {
        this.__currentCluster = null;
      }
      this.__reloadClusterMembers();
    },

    __reloadClusters: function() {
      const clustersModel = this.__clustersModel;
      clustersModel.removeAll();

      osparc.data.Resources.get("clusters")
        .then(clusters => {
          clusters.forEach(cluster => clustersModel.append(qx.data.marshal.Json.createModel(cluster)));
        });
    },

    __reloadClusterMembers: function() {
      const membersModel = this.__membersModel;
      membersModel.removeAll();

      const clusterModel = this.__currentCluster;
      if (clusterModel === null) {
        return;
      }

      const clusterMembers = clusterModel.getMembersList();

      const canWrite = clusterModel.getAccessRights().getWrite();
      if (canWrite) {
        this.__selectOrgMemberLayout.show();
        const memberKeys = Object.keys(clusterModel.getMembersObj());
        this.__orgsAndMembersFilter.reloadVisibleCollaborators(memberKeys);
      }

      const store = osparc.store.Store.getInstance();
      const promises = [];
      promises.push(store.getVisibleMembers());
      Promise.all(promises)
        .then(values => {
          const members = values[0]; // object

          clusterMembers.forEach(clusterMember => {
            if (clusterMember.gid in members) {
              const memberObj = {};
              const member = members[clusterMember.gid];
              memberObj["thumbnail"] = osparc.utils.Avatar.getUrl(member["login"], 32);
              memberObj["name"] = osparc.utils.Utils.firstsUp(member["first_name"], member["last_name"]);
              memberObj["showOptions"] = canWrite;
              memberObj["accessRights"] = {
                "read": clusterMember.getRead(),
                "write": clusterMember.getWrite(),
                "delete": clusterMember.getDelete()
              };
              memberObj["login"] = member["login"];
              memberObj["id"] = member["gid"];
              membersModel.append(qx.data.marshal.Json.createModel(memberObj));
            }
          });
        });
    },

    __openEditCluster: function(clusterId) {
      let cluster = null;
      this.__clustersModel.forEach(clusterModel => {
        if (clusterModel.getId() === parseInt(clusterId)) {
          cluster = clusterModel;
        }
      });
      if (cluster === null) {
        return;
      }

      const newCluster = false;
      const clusterEditor = new osparc.dashboard.ClusterEditor(newCluster);
      cluster.bind("id", clusterEditor, "cid");
      cluster.bind("name", clusterEditor, "label");
      cluster.bind("description", clusterEditor, "description");
      const title = this.tr("Cluster Details Editor");
      const win = osparc.ui.window.Window.popUpInWindow(clusterEditor, title, 400, 200);
      clusterEditor.addListener("updateCluster", () => {
        this.__updateCluster(win, clusterEditor.getChildControl("save"), clusterEditor);
      });
      clusterEditor.addListener("cancel", () => win.close());
    },

    __deleteCluster: function(clusterId) {
      let cluster = null;
      this.__clustersModel.forEach(clusterModel => {
        if (clusterModel.getId() === parseInt(clusterId)) {
          cluster = clusterModel;
        }
      });
      if (cluster === null) {
        return;
      }

      const name = cluster.getName();
      const msg = this.tr("Are you sure you want to delete ") + name + "?";
      const win = new osparc.ui.window.Confirmation(msg);
      win.center();
      win.open();
      win.addListener("close", () => {
        if (win.getConfirmed()) {
          const params = {
            url: {
              "cid": clusterId
            }
          };
          osparc.data.Resources.fetch("clusters", "delete", params)
            .then(() => {
              osparc.store.Store.getInstance().reset("clusters");
              this.__reloadClusters();
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

    __createCluster: function(win, button, clusterEditor) {
      const clusterKey = clusterEditor.getCid();
      const name = clusterEditor.getLabel();
      const description = clusterEditor.getDescription();
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
          this.__reloadClusters();
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

    __updateCluster: function(win, button, clusterEditor) {
      const clusterId = clusterEditor.getCid();
      const name = clusterEditor.getLabel();
      const description = clusterEditor.getDescription();
      const params = {
        url: {
          "cid": clusterId
        },
        data: {
          "name": name,
          "description": description,
          "type": "AWS"
        }
      };
      osparc.data.Resources.fetch("clusters", "patch", params)
        .then(() => {
          osparc.component.message.FlashMessenger.getInstance().logAs(name + this.tr(" successfully edited"));
          button.setFetching(false);
          win.close();
          osparc.store.Store.getInstance().reset("clusters");
          this.__reloadClusters();
        })
        .catch(err => {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Something went wrong editing ") + name, "ERROR");
          button.setFetching(false);
          console.error(err);
        });
    },

    __addMembers: function(clusterMemberEmail) {
    },

    __addMember: function(clusterMemberEmail) {
      if (this.__currentCluster === null) {
        return;
      }

      const params = {
        url: {
          "cid": this.__currentCluster.getKey()
        },
        data: {
          "email": clusterMemberEmail
        }
      };
      osparc.data.Resources.fetch("clusterMembers", "post", params)
        .then(() => {
          osparc.component.message.FlashMessenger.getInstance().logAs(clusterMemberEmail + this.tr(" added"));
          osparc.store.Store.getInstance().reset("clusterMembers");
          this.__reloadClusterMembers();
        })
        .catch(err => {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Something went wrong with the invitation"), "ERROR");
          console.error(err);
        });
    },

    __promoteToManager: function(clusterMember) {
      if (this.__currentCluster === null) {
        return;
      }

      const accessRights = JSON.parse(qx.util.Serializer.toJson(this.__currentCluster.getMembers()));
      if (!(clusterMember["key"] in accessRights)) {
        return;
      }
      delete accessRights[clusterMember["key"]];
      const params = {
        url: {
          "cid": this.__currentCluster.getKey()
        },
        data: {
          "accessRights": accessRights
        }
      };
      osparc.data.Resources.fetch("clusterMembers", "patch", params)
        .then(() => {
          osparc.component.message.FlashMessenger.getInstance().logAs(clusterMember["name"] + this.tr(" successfully promoted"));
          osparc.store.Store.getInstance().reset("clusterMembers");
          this.__reloadClusterMembers();
        })
        .catch(err => {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Something went wrong promoting ") + clusterMember["name"], "ERROR");
          console.error(err);
        });
    },

    __deleteMember: function(clusterMember) {
      if (this.__currentCluster === null) {
        return;
      }

      const accessRights = JSON.parse(qx.util.Serializer.toJson(this.__currentCluster.getMembers()));
      if (!(clusterMember["key"] in accessRights)) {
        return;
      }

      accessRights[clusterMember["key"]] = {
        "read": false,
        "write": false,
        "delete": false
      };
      const params = {
        url: {
          "cid": this.__currentCluster.getKey()
        },
        data: {
          "accessRights": accessRights
        }
      };
      osparc.data.Resources.fetch("clusters", "patch", params)
        .then(() => {
          osparc.component.message.FlashMessenger.getInstance().logAs(clusterMember["name"] + this.tr(" successfully removed"));
          osparc.store.Store.getInstance().reset("clusters");
          this.__reloadClusterMembers();
        })
        .catch(err => {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Something went wrong removing ") + clusterMember["name"], "ERROR");
          console.error(err);
        });
    }
  }
});
