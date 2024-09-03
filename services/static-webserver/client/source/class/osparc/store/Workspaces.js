/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.store.Workspaces", {
  type: "static",

  statics: {
    workspacesCached: [],

    iconPath: function(iconsSize = 18) {
      const source = "@MaterialIcons/folder_shared/";
      if (iconsSize === -1) {
        return source;
      }
      return source+iconsSize;
    },

    FAKE_WORKSPACES: [{
      workspaceId: 1,
      name: "Workspace 1",
      description: "Workspace 1 desc",
      thumbnail: "https://images.ctfassets.net/hrltx12pl8hq/01rJn4TormMsGQs1ZRIpzX/16a1cae2440420d0fd0a7a9a006f2dcb/Artboard_Copy_231.jpg?fit=fill&w=600&h=600",
      myAccessRights: {
        read: true,
        write: true,
        delete: true,
      },
      accessRights: {
        3: {
          read: true,
          write: true,
          delete: true,
        },
        5: {
          read: true,
          write: true,
          delete: false,
        },
        9: {
          read: true,
          write: false,
          delete: false,
        },
      },
      createdAt: "2024-03-04 15:59:51.579217",
      lastModified: "2024-03-05 15:18:21.515403",
    }, {
      workspaceId: 2,
      name: "Workspace 2",
      description: "Workspace 2 desc",
      thumbnail: "",
      myAccessRights: {
        read: true,
        write: true,
        delete: false,
      },
      accessRights: {
        3: {
          read: true,
          write: true,
          delete: false,
        },
        5: {
          read: true,
          write: true,
          delete: true,
        },
        9: {
          read: true,
          write: false,
          delete: false,
        },
      },
      createdAt: "2024-03-05 15:18:21.515403",
      lastModified: "2024-04-24 12:03:05.15249",
    }, {
      workspaceId: 3,
      name: "Workspace 3",
      description: "Workspace 3 desc",
      thumbnail: "https://media.springernature.com/lw703/springer-static/image/art%3A10.1038%2F528452a/MediaObjects/41586_2015_Article_BF528452a_Figg_HTML.jpg",
      myAccessRights: {
        read: true,
        write: false,
        delete: false,
      },
      accessRights: {
        3: {
          read: true,
          write: false,
          delete: false,
        },
        5: {
          read: true,
          write: true,
          delete: false,
        },
        9: {
          read: true,
          write: true,
          delete: true,
        },
      },
      createdAt: "2024-04-24 12:03:05.15249",
      lastModified: "2024-06-21 13:00:40.33769",
    }],

    fetchWorkspaces: function() {
      if (osparc.auth.Data.getInstance().isGuest()) {
        return new Promise(resolve => {
          resolve([]);
        });
      }

      /*
      return osparc.data.Resources.getInstance().getAllPages("workspaces", params)
        .then(workspacesData => {
          const workspaces = [];
          workspacesData.forEach(workspaceData => {
            const workspace = new osparc.data.model.Workspace(workspaceData);
            this.__addToCache(workspace);
            workspaces.push(workspace);
          });
          return workspaces;
        });
      */

      return new Promise(resolve => {
        if (this.workspacesCached.length === 0) {
          this.self().FAKE_WORKSPACES.forEach(workspaceData => {
            const workspace = new osparc.data.model.Workspace(workspaceData);
            this.__addToCache(workspace);
          });
        }
        resolve(this.workspacesCached);
      });
    },

    createNewWorkspaceData: function(name, description = "", thumbnail = "") {
      return {
        name,
        description,
        thumbnail,
      };
    },

    postWorkspace: function(newWorkspaceData) {
      /*
      const params = {
        data: newWorkspaceData
      };
      return osparc.data.Resources.getInstance().fetch("workspaces", "post", params)
        .then(workspaceData => {
          const newWorkspace = new osparc.data.model.Workspace(workspaceData);
          this.__addToCache(newWorkspace);
          return newWorkspace;
        });
      */
      const workspaceData = newWorkspaceData;
      workspaceData["workspaceId"] = Math.floor(Math.random() * 100) + 100;
      workspaceData["myAccessRights"] = osparc.share.CollaboratorsWorkspace.getOwnerAccessRight();
      const myGroupId = osparc.auth.Data.getInstance().getGroupId();
      workspaceData["accessRights"] = {};
      workspaceData["accessRights"][myGroupId] = osparc.share.CollaboratorsWorkspace.getOwnerAccessRight();
      workspaceData["createdAt"] = new Date().toISOString();
      workspaceData["lastModified"] = new Date().toISOString();
      return new Promise(resolve => {
        const workspace = new osparc.data.model.Workspace(workspaceData);
        this.__addToCache(workspace);
        resolve(workspace);
      });
    },

    deleteWorkspace: function(workspaceId) {
      return new Promise((resolve, reject) => {
        if (this.__deleteFromCache(workspaceId)) {
          resolve();
        } else {
          reject();
        }
        /*
        const params = {
          "url": {
            workspaceId
          }
        };
        osparc.data.Resources.getInstance().fetch("workspaces", "delete", params)
          .then(() => {
            if (this.__deleteFromCache(workspaceId)) {
              resolve();
            } else {
              reject();
            }
          })
          .catch(err => reject(err));
        */
      });
    },

    putWorkspace: function(workspaceId, updateData) {
      return new Promise((resolve, reject) => {
        const params = {
          "url": {
            workspaceId
          },
          data: updateData
        };
        osparc.data.Resources.getInstance().fetch("workspaces", "update", params)
          .then(() => {
            const workspace = this.getWorkspace(workspaceId);
            Object.keys(updateData).forEach(propKey => {
              const upKey = qx.lang.String.firstUp(propKey);
              const setter = "set" + upKey;
              if (workspace && setter in workspace) {
                workspace[setter](updateData[propKey]);
              }
            });
            workspace.setLastModified(new Date());
            this.__deleteFromCache(workspaceId);
            this.__addToCache(workspace);
            resolve();
          })
          .catch(err => reject(err));
      });
    },

    addCollaborators: function(workspaceId, newCollaborators) {
      return new Promise((resolve, reject) => {
        const workspace = this.getWorkspace(workspaceId);
        if (workspace) {
          const accessRights = workspace.getAccessRights();
          const newAccessRights = Object.assign(accessRights, newCollaborators);
          workspace.set({
            accessRights: newAccessRights,
            lastModified: new Date()
          })
          resolve();
        } else {
          reject();
        }
      });
    },

    removeCollaborator: function(workspaceId, gid) {
      return new Promise((resolve, reject) => {
        const workspace = this.getWorkspace(workspaceId);
        if (workspace) {
          const accessRights = workspace.getAccessRights();
          delete accessRights[gid];
          workspace.set({
            accessRights: accessRights,
            lastModified: new Date()
          })
          resolve();
        } else {
          reject();
        }
      });
    },

    updateCollaborator: function(workspaceId, gid, newPermissions) {
      return new Promise((resolve, reject) => {
        const workspace = this.getWorkspace(workspaceId);
        if (workspace) {
          const accessRights = workspace.getAccessRights();
          if (gid in accessRights) {
            accessRights[gid] = newPermissions;
            workspace.set({
              accessRights: accessRights,
              lastModified: new Date()
            })
            resolve();
            return;
          }
        }
        reject();
      });
    },

    getWorkspaces: function(parentId = null) {
      return this.workspacesCached.filter(f => f.getParentId() === parentId);
    },

    getWorkspace: function(workspaceId = null) {
      return this.workspacesCached.find(f => f.getWorkspaceId() === workspaceId);
    },

    __addToCache: function(workspace) {
      const found = this.workspacesCached.find(f => f.getWorkspaceId() === workspace.getWorkspaceId());
      if (!found) {
        this.workspacesCached.unshift(workspace);
      }
    },

    __deleteFromCache: function(workspaceId) {
      const idx = this.workspacesCached.findIndex(f => f.getWorkspaceId() === workspaceId);
      if (idx > -1) {
        this.workspacesCached.splice(idx, 1);
        return true;
      }
      return false;
    }
  }
});
