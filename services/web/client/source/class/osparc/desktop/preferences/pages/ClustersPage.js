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
    __clustersList: null,
    __selectOrgMemberLayout: null,
    __organizationsAndMembers: null,
    __membersArrayModel: null,

    __getCreateClusterSection: function() {
      const createClusterBtn = new qx.ui.form.Button(this.tr("Create New Cluster")).set({
        allowGrowX: false
      });
      createClusterBtn.addListener("execute", function() {
        const newCluster = true;
        const clusterEditor = new osparc.component.editor.ClusterEditor(newCluster);
        const title = this.tr("Cluster Details Editor");
        const win = osparc.ui.window.Window.popUpInWindow(clusterEditor, title, 400, 250);
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
      const clustersList = this.__clustersList = new qx.ui.form.List().set({
        decorator: "no-border",
        spacing: 3,
        height: 150,
        width: 150,
        backgroundColor: "material-button-background"
      });
      clustersList.addListener("changeSelection", e => {
        this.__clusterSelected(e.getData());
      }, this);

      const clustersModel = this.__clustersModel = new qx.data.Array();
      const clustersCtrl = new qx.data.controller.List(clustersModel, clustersList, "name");
      clustersCtrl.setDelegate({
        createItem: () => new osparc.ui.list.ClusterListItem(),
        bindItem: (ctrl, item, id) => {
          ctrl.bindProperty("id", "model", null, item, id);
          ctrl.bindProperty("id", "key", null, item, id);
          ctrl.bindProperty("thumbnail", "thumbnail", null, item, id);
          ctrl.bindProperty("name", "title", null, item, id);
          ctrl.bindProperty("endpoint", "endpoint", null, item, id);
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

      return clustersList;
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

      const organizationsAndMembers = this.__organizationsAndMembers = new osparc.component.filter.OrganizationsAndMembers("orgAndMembClusters");
      hBox.add(organizationsAndMembers, {
        flex: 1
      });

      const addCollaboratorBtn = new qx.ui.form.Button(this.tr("Add")).set({
        allowGrowY: false,
        enabled: false
      });
      addCollaboratorBtn.addListener("execute", () => {
        this.__addMembers(this.__organizationsAndMembers.getSelectedGIDs());
      }, this);
      qx.event.message.Bus.getInstance().subscribe("OrgAndMembClustersFilter", () => {
        const anySelected = Boolean(this.__organizationsAndMembers.getSelectedGIDs().length);
        addCollaboratorBtn.setEnabled(anySelected);
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

      const membersArrayModel = this.__membersArrayModel = new qx.data.Array();
      const membersCtrl = new qx.data.controller.List(membersArrayModel, memebersUIList, "name");
      membersCtrl.setDelegate({
        createItem: () => new osparc.ui.list.MemberListItem(),
        bindItem: (ctrl, item, id) => {
          ctrl.bindProperty("id", "model", null, item, id);
          ctrl.bindProperty("id", "key", null, item, id);
          ctrl.bindProperty("thumbnail", "thumbnail", null, item, id);
          ctrl.bindProperty("name", "title", null, item, id);
          ctrl.bindProperty("endpoint", "endpoint", null, item, id);
          ctrl.bindProperty("simpleAuthenticationUsername", "simpleAuthenticationUsername", null, item, id);
          ctrl.bindProperty("simpleAuthenticationPassword", "simpleAuthenticationPassword", null, item, id);
          ctrl.bindProperty("accessRights", "accessRights", null, item, id);
          ctrl.bindProperty("login", "subtitleMD", null, item, id);
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

    __reloadClusters: function(reloadMembers = false) {
      let reloadClusterKey = null;
      if (reloadMembers) {
        reloadClusterKey = this.__currentCluster.getKey();
      }

      const clustersModel = this.__clustersModel;
      clustersModel.removeAll();

      osparc.data.Resources.get("clusters")
        .then(clusters => {
          clusters.forEach(cluster => clustersModel.append(qx.data.marshal.Json.createModel(cluster)));
          if (reloadClusterKey) {
            const selectables = this.__clustersList.getSelectables();
            selectables.forEach(selectable => {
              if (selectable.getKey() === reloadClusterKey) {
                this.__currentCluster = selectable;
                this.__reloadClusterMembers();
              }
            });
          }
        });
    },

    __reloadClusterMembers: function() {
      const membersArrayModel = this.__membersArrayModel;
      membersArrayModel.removeAll();

      const clusterModel = this.__currentCluster;
      if (clusterModel === null) {
        return;
      }

      const clusterMembers = clusterModel.getMembersList();

      const canWrite = clusterModel.getAccessRights().getWrite();
      if (canWrite) {
        this.__selectOrgMemberLayout.show();
        const memberKeys = [];
        clusterMembers.forEach(clusterMember => memberKeys.push(clusterMember["gid"]));
        this.__organizationsAndMembers.reloadVisibleCollaborators(memberKeys);
      }

      osparc.store.Store.getInstance().getPotentialCollaborators()
        .then(potentialCollaborators => {
          clusterMembers.forEach(clusterMember => {
            const gid = clusterMember.gid;
            if (gid in potentialCollaborators) {
              const collaborator = potentialCollaborators[gid];
              const collabObj = {};
              if (collaborator["collabType"] === 1) {
                collabObj["thumbnail"] = collaborator["thumbnail"] || "@FontAwesome5Solid/users/24";
                collabObj["name"] = osparc.utils.Utils.firstsUp(collaborator["label"]);
                collabObj["login"] = collaborator["description"];
              } else if (collaborator["collabType"] === 2) {
                collabObj["thumbnail"] = osparc.utils.Avatar.getUrl(collaborator["login"], 32);
                collabObj["name"] = osparc.utils.Utils.firstsUp(collaborator["first_name"], collaborator["last_name"]);
                collabObj["login"] = collaborator["login"];
              }
              if (Object.keys(collabObj).length) {
                collabObj["id"] = collaborator["gid"];
                collabObj["accessRights"] = JSON.parse(qx.util.Serializer.toJson(clusterMember));
                collabObj["showOptions"] = canWrite;
                membersArrayModel.append(qx.data.marshal.Json.createModel(collabObj));
              }
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
      const clusterEditor = new osparc.component.editor.ClusterEditor(newCluster);
      cluster.bind("id", clusterEditor, "cid");
      cluster.bind("name", clusterEditor, "label");
      cluster.bind("endpoint", clusterEditor, "endpoint");
      clusterEditor.setSimpleAuthenticationUsername(cluster.getAuthentication().getUsername());
      clusterEditor.setSimpleAuthenticationPassword(cluster.getAuthentication().getPassword());
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
      const endpoint = clusterEditor.getEndpoint();
      const authenticationType = "simple";
      const simpleAuthenticationUsername = clusterEditor.getSimpleAuthenticationUsername();
      const simpleAuthenticationPassword = clusterEditor.getSimpleAuthenticationPassword();
      const description = clusterEditor.getDescription();
      const params = {
        url: {
          "cid": clusterKey
        },
        data: {
          "name": name,
          "endpoint": endpoint,
          "authentication": {
            "type": authenticationType,
            "username": simpleAuthenticationUsername,
            "password": simpleAuthenticationPassword
          },
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
      const endpoint = clusterEditor.getEndpoint();
      const authenticationType = "simple";
      const simpleAuthenticationUsername = clusterEditor.getSimpleAuthenticationUsername();
      const simpleAuthenticationPassword = clusterEditor.getSimpleAuthenticationPassword();
      const description = clusterEditor.getDescription();
      const params = {
        url: {
          "cid": clusterId
        },
        data: {
          "name": name,
          "endpoint": endpoint,
          "authentication": {
            "type": authenticationType,
            "username": simpleAuthenticationUsername,
            "password": simpleAuthenticationPassword
          },
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

    __addMembers: function(gids) {
      if (this.__currentCluster === null) {
        return;
      }

      const accessRights = JSON.parse(qx.util.Serializer.toJson(this.__currentCluster.getMembers()));
      gids.forEach(gid => {
        if (gid in accessRights) {
          return;
        }

        accessRights[gid] = {
          "read": true,
          "write": false,
          "delete": false
        };
      });

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
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Member(s) added"));
          osparc.store.Store.getInstance().reset("clusters");
          this.__reloadClusters(true);
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

      accessRights[clusterMember["key"]] = {
        "read": true,
        "write": true,
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
          osparc.component.message.FlashMessenger.getInstance().logAs(clusterMember["name"] + this.tr(" successfully promoted"));
          osparc.store.Store.getInstance().reset("clusters");
          this.__reloadClusters(true);
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

      delete accessRights[clusterMember["key"]];
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
          this.__reloadClusters(true);
        })
        .catch(err => {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Something went wrong removing ") + clusterMember["name"], "ERROR");
          console.error(err);
        });
    }
  }
});
