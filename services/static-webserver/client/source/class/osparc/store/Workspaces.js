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

    fetchWorkspaces: function() {
      if (osparc.auth.Data.getInstance().isGuest()) {
        return new Promise(resolve => {
          resolve([]);
        });
      }

      return osparc.data.Resources.getInstance().getAllPages("workspaces")
        .then(workspacesData => {
          workspacesData.forEach(workspaceData => {
            const workspace = new osparc.data.model.Workspace(workspaceData);
            this.__addToCache(workspace);
          });
          return this.workspacesCached;
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
      const params = {
        data: newWorkspaceData
      };
      return osparc.data.Resources.getInstance().fetch("workspaces", "post", params)
        .then(workspaceData => {
          const newWorkspace = new osparc.data.model.Workspace(workspaceData);
          this.__addToCache(newWorkspace);
          return newWorkspace;
        });
    },

    deleteWorkspace: function(workspaceId) {
      return new Promise((resolve, reject) => {
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
            resolve(workspace);
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
