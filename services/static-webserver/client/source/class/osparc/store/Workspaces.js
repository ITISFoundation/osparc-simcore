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

    createNewWorkspaceData: function(name, description = "", thumbnail = "") {
      return {
        name,
        description,
        thumbnail,
      };
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
      const promises = [];
      Object.keys(newCollaborators).forEach(groupId => {
        const params = {
          url: {
            workspaceId,
            groupId,
          },
          data: newCollaborators[groupId]
        };
        promises.push(osparc.data.Resources.fetch("workspaces", "postAccessRights", params));
      });
      return Promise.all(promises)
        .then(() => {
          const workspace = this.getWorkspace(workspaceId);
          const newAccessRights = workspace.getAccessRights();
          Object.keys(newCollaborators).forEach(gid => {
            newAccessRights[gid] = newCollaborators[gid];
          });
          workspace.set({
            accessRights: newAccessRights,
            modifiedAt: new Date()
          });
        })
        .catch(console.error);
    },

    removeCollaborator: function(workspaceId, groupId) {
      const params = {
        url: {
          workspaceId,
          groupId,
        }
      };
      return osparc.data.Resources.fetch("workspaces", "deleteAccessRights", params)
        .then(() => {
          const workspace = this.getWorkspace(workspaceId);
          const newAccessRights = workspace.getAccessRights();
          delete newAccessRights[groupId];
          workspace.set({
            accessRights: newAccessRights,
            modifiedAt: new Date()
          });
        })
        .catch(console.error);
    },

    updateCollaborator: function(workspaceId, groupId, newPermissions) {
      const params = {
        url: {
          workspaceId,
          groupId,
        },
        data: newPermissions
      };
      return osparc.data.Resources.fetch("workspaces", "putAccessRights", params)
        .then(() => {
          const workspace = this.getWorkspace(workspaceId);
          const newAccessRights = workspace.getAccessRights();
          newAccessRights[groupId] = newPermissions;
          workspace.set({
            accessRights: workspace.newAccessRights,
            modifiedAt: new Date()
          });
        })
        .catch(console.error);
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
