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
  extend: qx.core.Object,
  type: "singleton",

  construct: function() {
    this.base(arguments);

    this.workspacesCached = [];
  },

  events: {
    "workspaceAdded": "qx.event.type.Data",
    "workspaceRemoved": "qx.event.type.Data",
  },

  statics: {
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

    curateOrderBy: function(orderBy) {
      const curatedOrderBy = osparc.utils.Utils.deepCloneObject(orderBy);
      if (curatedOrderBy.field !== "name") {
        // only "modified_at" and "name" supported
        curatedOrderBy.field = "modified_at";
      }
      return curatedOrderBy;
    },
  },

  members: {
    workspacesCached: null,

    fetchWorkspaces: function() {
      if (osparc.auth.Data.getInstance().isGuest()) {
        return new Promise(resolve => {
          resolve([]);
        });
      }

      return osparc.data.Resources.getInstance().getAllPages("workspaces")
        .then(workspacesData => {
          workspacesData.forEach(workspaceData => {
            this.__addToCache(workspaceData);
          });
          return this.workspacesCached;
        });
    },

    fetchAllTrashedWorkspaces: function(orderBy = {
      field: "modified_at",
      direction: "desc"
    }) {
      if (osparc.auth.Data.getInstance().isGuest()) {
        return new Promise(resolve => {
          resolve([]);
        });
      }

      const curatedOrderBy = this.self().curateOrderBy(orderBy);
      const params = {
        url: {
          orderBy: JSON.stringify(curatedOrderBy),
        }
      };
      return osparc.data.Resources.getInstance().getAllPages("workspaces", params, "getPageTrashed")
        .then(trashedWorkspacesData => {
          const workspaces = [];
          trashedWorkspacesData.forEach(workspaceData => {
            const workspace = this.__addToCache(workspaceData);
            workspaces.push(workspace);
          });
          return workspaces;
        });
    },

    searchWorkspaces: function(text) {
      if (osparc.auth.Data.getInstance().isGuest()) {
        return new Promise(resolve => {
          resolve([]);
        });
      }

      const params = {
        url: {
          text,
        }
      };
      return osparc.data.Resources.getInstance().getAllPages("workspaces", params, "getPageSearch")
        .then(workspacesData => {
          const workspaces = [];
          workspacesData.forEach(workspaceData => {
            const workspace = this.__addToCache(workspaceData);
            workspaces.push(workspace);
          });
          return workspaces;
        });
    },

    postWorkspace: function(newWorkspaceData) {
      const params = {
        data: newWorkspaceData
      };
      return osparc.data.Resources.getInstance().fetch("workspaces", "post", params)
        .then(workspaceData => {
          const newWorkspace = this.__addToCache(workspaceData);
          this.fireDataEvent("workspaceAdded", newWorkspace);
          return newWorkspace;
        });
    },

    trashWorkspace: function(workspaceId) {
      const params = {
        "url": {
          workspaceId
        }
      };
      return osparc.data.Resources.getInstance().fetch("workspaces", "trash", params)
        .then(() => {
          const workspace = this.getWorkspace(workspaceId);
          if (workspace) {
            this.__deleteFromCache(workspaceId);
            this.fireDataEvent("workspaceRemoved", workspace);
          }
        })
        .catch(console.error);
    },

    untrashWorkspace: function(workspace) {
      const params = {
        "url": {
          workspaceId: workspace.getWorkspaceId(),
        }
      };
      return osparc.data.Resources.getInstance().fetch("workspaces", "untrash", params)
        .then(() => {
          this.workspacesCached.unshift(workspace);
          this.fireDataEvent("workspaceAdded", workspace);
        })
        .catch(console.error);
    },

    deleteWorkspace: function(workspaceId) {
      const params = {
        "url": {
          workspaceId
        }
      };
      return osparc.data.Resources.getInstance().fetch("workspaces", "delete", params)
        .then(() => {
          const workspace = this.getWorkspace(workspaceId);
          if (workspace) {
            this.__deleteFromCache(workspaceId);
            this.fireDataEvent("workspaceRemoved", workspace);
          }
        })
        .catch(console.error);
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
            workspace.set({
              modifiedAt: new Date()
            });
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

    getWorkspace: function(workspaceId = null) {
      return this.workspacesCached.find(w => w.getWorkspaceId() === workspaceId);
    },

    getWorkspaces: function() {
      return this.workspacesCached;
    },

    __addToCache: function(workspaceData) {
      let workspace = this.workspacesCached.find(w => w.getWorkspaceId() === workspaceData["workspaceId"]);
      if (workspace) {
        const props = Object.keys(qx.util.PropertyUtil.getProperties(osparc.data.model.Workspace));
        // put
        Object.keys(workspaceData).forEach(key => {
          if (key === "createdAt") {
            workspace.set("createdAt", new Date(workspaceData["createdAt"]));
          } else if (key === "modifiedAt") {
            workspace.set("modifiedAt", new Date(workspaceData["modifiedAt"]));
          } else if (key === "trashedAt") {
            workspace.set("trashedAt", new Date(workspaceData["trashedAt"]));
          } else if (props.includes(key)) {
            workspace.set(key, workspaceData[key]);
          }
        });
      } else {
        workspace = new osparc.data.model.Workspace(workspaceData);
        this.workspacesCached.unshift(workspace);
      }
      return workspace;
    },

    __deleteFromCache: function(workspaceId) {
      const idx = this.workspacesCached.findIndex(w => w.getWorkspaceId() === workspaceId);
      if (idx > -1) {
        this.workspacesCached.splice(idx, 1);
        return true;
      }
      return false;
    }
  }
});
