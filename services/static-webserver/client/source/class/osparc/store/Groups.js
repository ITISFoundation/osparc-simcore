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

qx.Class.define("osparc.store.Groups", {
  extend: qx.core.Object,
  type: "singleton",

  construct: function() {
    this.base(arguments);

    this.groupsCached = [];
  },

  properties: {
    organizations: {
      check: "Object",
      init: {}
    },

    organizationMembers: {
      check: "Object",
      init: {}
    },

    reachableMembers: {
      check: "Object",
      init: {}
    },

    everyoneProductGroup: {
      check: "Object",
      init: {}
    },

    everyoneGroup: {
      check: "Object",
      init: {}
    },
  },

  events: {
    "groupAdded": "qx.event.type.Data",
    "groupRemoved": "qx.event.type.Data",
    "groupMoved": "qx.event.type.Data",
  },

  statics: {
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
    groupsCached: null,

    fetchGroups: function() {
      if (osparc.auth.Data.getInstance().isGuest()) {
        return new Promise(resolve => {
          resolve([]);
        });
      }

      return osparc.data.Resources.getInstance().getAllPages("groups")
        .then(groupsData => {
          const groups = [];
          groupsData.forEach(groupData => {
            const group = this.__addToCache(groupData);
            groups.push(group);
          });
          return groups;
        });
    },

    __getGroups: function(group) {
      return new Promise(resolve => {
        osparc.data.Resources.get("organizations")
          .then(groups => {
            resolve(groups[group]);
          })
          .catch(err => console.error(err));
      });
    },

    getGroupsMe: function() {
      return this.__getGroups("me");
    },

    getGroupsOrganizations: function() {
      return this.__getGroups("organizations");
    },

    getProductEveryone: function() {
      return this.__getGroups("product");
    },

    getGroupEveryone: function() {
      return this.__getGroups("all");
    },

    __getAllGroups: function() {
      return new Promise(resolve => {
        const promises = [];
        promises.push(this.getGroupsMe());
        promises.push(this.getReachableMembers());
        promises.push(this.getGroupsOrganizations());
        promises.push(this.getProductEveryone());
        promises.push(this.getGroupEveryone());
        Promise.all(promises)
          .then(values => {
            const groups = [];
            const groupMe = values[0];
            groupMe["collabType"] = 2;
            groups.push(groupMe);
            const orgMembers = values[1];
            for (const gid of Object.keys(orgMembers)) {
              orgMembers[gid]["collabType"] = 2;
              groups.push(orgMembers[gid]);
            }
            values[2].forEach(org => {
              org["collabType"] = 1;
              groups.push(org);
            });
            const groupProductEveryone = values[3];
            if (groupProductEveryone) {
              groupProductEveryone["collabType"] = 0;
              groups.push(groupProductEveryone);
            }
            const groupEveryone = values[4];
            if (groupEveryone) {
              groupEveryone["collabType"] = 0;
              groups.push(groupEveryone);
            }
            resolve(groups);
          });
      });
    },

    getOrganizationOrUser: function(orgId) {
      return new Promise(resolve => {
        this.__getAllGroups()
          .then(orgs => {
            const idx = orgs.findIndex(org => org.gid === parseInt(orgId));
            if (idx > -1) {
              resolve(orgs[idx]);
            }
            resolve(null);
          });
      });
    },

    getAllGroupsAndMembers: function() {
      return new Promise(resolve => {
        osparc.data.Resources.get("organizations")
          .then(resp => {
            this.setEveryoneGroup(resp["all"]);
            this.setEveryoneProductGroup(resp["product"]);
            const orgMembersPromises = [];
            const orgs = resp["organizations"];
            orgs.forEach(org => {
              const params = {
                url: {
                  "gid": org["gid"]
                }
              };
              orgMembersPromises.push(osparc.data.Resources.get("organizationMembers", params));
            });
            Promise.all(orgMembersPromises)
              .then(orgMemberss => {
                const reachableMembers = this.getReachableMembers();
                orgMemberss.forEach(orgMembers => {
                  orgMembers.forEach(orgMember => {
                    orgMember["label"] = osparc.utils.Utils.firstsUp(
                      `${"first_name" in orgMember && orgMember["first_name"] != null ? orgMember["first_name"] : orgMember["login"]}`,
                      `${orgMember["last_name"] ? orgMember["last_name"] : ""}`
                    );
                    reachableMembers[orgMember["gid"]] = orgMember;
                  });
                });
                resolve();
              });
          });
      });
    },

    getPotentialCollaborators: function(includeMe = false, includeProductEveryone = false) {
      return new Promise((resolve, reject) => {
        const promises = [];
        promises.push(this.getGroupsOrganizations());
        promises.push(this.getReachableMembers());
        promises.push(this.getEveryoneProductGroup());
        Promise.all(promises)
          .then(values => {
            const orgs = values[0]; // array
            const members = values[1]; // object
            const productEveryone = values[2]; // entry
            const potentialCollaborators = {};
            orgs.forEach(org => {
              if (org["accessRights"]["read"]) {
                // maybe because of migration script, some users have access to the product everyone group
                // rely on the includeProductEveryone argument to exclude it if necessary
                if (org["gid"] === productEveryone["gid"] && !includeProductEveryone) {
                  return;
                }
                org["collabType"] = 1;
                potentialCollaborators[org["gid"]] = org;
              }
            });
            for (const gid of Object.keys(members)) {
              members[gid]["collabType"] = 2;
              potentialCollaborators[gid] = members[gid];
            }
            if (includeMe) {
              const myData = osparc.auth.Data.getInstance();
              const myGid = myData.getGroupId();
              potentialCollaborators[myGid] = {
                "login": myData.getEmail(),
                "first_name": myData.getFirstName(),
                "last_name": myData.getLastName(),
                "collabType": 2
              };
            }
            if (includeProductEveryone && productEveryone) {
              productEveryone["collabType"] = 0;
              potentialCollaborators[productEveryone["gid"]] = productEveryone;
            }
            resolve(potentialCollaborators);
          })
          .catch(err => {
            console.error(err);
            reject(err);
          });
      });
    },

    getGroup: function(gid) {
      return new Promise(resolve => {
        if (gid) {
          this.getPotentialCollaborators()
            .then(potentialCollaborators => {
              let group = null;
              if (gid in potentialCollaborators) {
                group = potentialCollaborators[gid];
              }
              resolve(group);
            })
            .catch(() => resolve(null));
        } else {
          resolve(null);
        }
      });
    },

    getUser: function(uid) {
      if (uid) {
        const visibleMembers = this.getReachableMembers();
        return Object.values(visibleMembers).find(member => member.id === uid);
      }
      return null;
    },

    postGroup: function(name, parentGroupId = null, workspaceId = null) {
      const newGroupData = {
        name,
        parentGroupId,
        workspaceId,
      };
      const params = {
        data: newGroupData
      };
      return osparc.data.Resources.getInstance().fetch("groups", "post", params)
        .then(groupData => {
          const group = this.__addToCache(groupData);
          this.fireDataEvent("groupAdded", group);
          return group;
        });
    },

    deleteGroup: function(groupId, workspaceId) {
      const params = {
        "url": {
          groupId
        }
      };
      return osparc.data.Resources.getInstance().fetch("groups", "delete", params)
        .then(() => {
          const group = this.getGroup(groupId);
          if (group) {
            this.__deleteFromCache(groupId, workspaceId);
            this.fireDataEvent("groupRemoved", group);
          }
        })
        .catch(console.error);
    },

    putGroup: function(groupId, updateData) {
      const group = this.getGroup(groupId);
      const oldParentGroupId = group.getParentGroupId();
      const params = {
        "url": {
          groupId
        },
        data: updateData
      };
      return osparc.data.Resources.getInstance().fetch("groups", "update", params)
        .then(groupData => {
          this.__addToCache(groupData);
          if (updateData.parentGroupId !== oldParentGroupId) {
            this.fireDataEvent("groupMoved", {
              group,
              oldParentGroupId,
            });
          }
        })
        .catch(console.error);
    },

    /*
    getGroup: function(groupId = null) {
      return this.groupsCached.find(f => f.getGroupId() === groupId);
    },
    */

    __addToCache: function(groupData) {
      let group = this.groupsCached.find(f => f.getGroupId() === groupData["groupId"] && f.getWorkspaceId() === groupData["workspaceId"]);
      if (group) {
        const props = Object.keys(qx.util.PropertyUtil.getProperties(osparc.data.model.Group));
        // put
        Object.keys(groupData).forEach(key => {
          if (key === "createdAt") {
            group.set("createdAt", new Date(groupData["createdAt"]));
          } else if (key === "modifiedAt") {
            group.set("lastModified", new Date(groupData["modifiedAt"]));
          } else if (key === "trashedAt") {
            group.set("trashedAt", new Date(groupData["trashedAt"]));
          } else if (props.includes(key)) {
            group.set(key, groupData[key]);
          }
        });
      } else {
        // get and post
        group = new osparc.data.model.Group(groupData);
        this.groupsCached.unshift(group);
      }
      return group;
    },

    __deleteFromCache: function(groupId, workspaceId) {
      const idx = this.groupsCached.findIndex(f => f.getGroupId() === groupId && f.getWorkspaceId() === workspaceId);
      if (idx > -1) {
        this.groupsCached.splice(idx, 1);
        return true;
      }
      return false;
    }
  }
});
