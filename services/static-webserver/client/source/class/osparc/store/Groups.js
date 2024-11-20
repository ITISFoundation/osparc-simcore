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
    this.usersCached = [];
  },

  properties: {
    everyoneGroup: {
      check: "osparc.data.model.Group",
      init: {}
    },

    everyoneProductGroup: {
      check: "osparc.data.model.Group",
      init: {}
    },

    organizations: {
      check: "Object",
      init: {}
    },

    groupMe: {
      check: "osparc.data.model.Group",
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
  },

  events: {
    "groupAdded": "qx.event.type.Data",
    "groupRemoved": "qx.event.type.Data",
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
    usersCached: null,

    fetchGroups: function() {
      if (osparc.auth.Data.getInstance().isGuest()) {
        return new Promise(resolve => {
          resolve([]);
        });
      }
      const useCache = false;
      return osparc.data.Resources.get("organizations", {}, useCache)
        .then(resp => {
          const everyoneGroup = this.__addToGroupsCache(resp["all"], "everyone");
          const productEveryoneGroup = this.__addToGroupsCache(resp["product"], "productEveryone");
          const groupMe = this.__addToGroupsCache(resp["me"], "me");
          const orgs = {};
          resp["organizations"].forEach(organization => {
            const org = this.__addToGroupsCache(organization, "organization");
            orgs[org.getGroupId()] = org;
          });
          this.setEveryoneGroup(everyoneGroup);
          this.setEveryoneProductGroup(productEveryoneGroup);
          this.setGroupMe(groupMe);
          this.setOrganizations(orgs);
          return orgs;
        });
    },

    __fetchGroupMembers: function(groupId) {
      const params = {
        url: {
          gid: groupId
        }
      };
      return osparc.data.Resources.get("organizationMembers", params)
        .then(orgMembers => {
          this.getOrganizationMembers()[groupId] = {};
          orgMembers.forEach(orgMember => {
            orgMember["label"] = osparc.utils.Utils.firstsUp(
              `${"first_name" in orgMember && orgMember["first_name"] != null ? orgMember["first_name"] : orgMember["login"]}`,
              `${orgMember["last_name"] ? orgMember["last_name"] : ""}`
            );
            this.getOrganizationMembers()[groupId][orgMember["gid"]] = orgMember;
          });
        });
    },

    fetchAll: function() {
      this.fetchGroups()
        .then(orgs => {
          this.resetOrganizationMembers();
          this.resetReachableMembers();
          const memberPromises = Object.keys(orgs).map(orgId => this.__fetchGroupMembers(orgId));
          Promise.all(memberPromises)
            .then(() => {
              Object.values(this.getOrganizationMembers()).forEach(orgMembers => {
                Object.values(orgMembers).forEach(reachableMember => {
                  this.getReachableMembers()[reachableMember["gid"]] = reachableMember;
                });
              });
            });

          /*
          const orgMembersPromises = [];
          Object.keys(orgs).forEach(gid => {
            const params = {
              url: {
                gid
              }
            };
            orgMembersPromises.push(osparc.data.Resources.get("organizationMembers", params));
          });
          Promise.all(orgMembersPromises)
            .then(orgMemberss => {
              const reachableMembers = {};
              orgMemberss.forEach(orgMembers => {
                orgMembers.forEach(orgMember => {
                  orgMember["label"] = osparc.utils.Utils.firstsUp(
                    `${"first_name" in orgMember && orgMember["first_name"] != null ? orgMember["first_name"] : orgMember["login"]}`,
                    `${orgMember["last_name"] ? orgMember["last_name"] : ""}`
                  );
                  reachableMembers[orgMember["gid"]] = orgMember;
                });
              });
              this.setReachableMembers(reachableMembers);
            });
          */
        });
    },

    getMyGroupId: function() {
      return this.getGroupMe().getGroupId();
    },

    getOrganizationIds: function() {
      return Object.keys(this.getOrganizations());
    },

    __getAllGroups: function() {
      const groups = [];

      const groupMe = this.getGroupMe();
      groupMe["collabType"] = 2;
      groups.push(groupMe);

      Object.values(this.getReachableMembers()).forEach(member => {
        member["collabType"] = 2;
        groups.push(member);
      });

      Object.values(this.getOrganizations()).forEach(org => {
        org["collabType"] = 1;
        groups.push(org);
      });

      const groupProductEveryone = this.getEveryoneProductGroup();
      groupProductEveryone["collabType"] = 0;
      groups.push(groupProductEveryone);

      const groupEveryone = this.getEveryoneGroup();
      groupEveryone["collabType"] = 0;
      groups.push(groupEveryone);

      return groups;
    },

    getOrganizationOrUser: function(orgId) {
      const orgs = this.__getAllGroups();
      const idx = orgs.findIndex(org => "gid" in org ? org["gid"] === parseInt(orgId) : org.getGroupId() === parseInt(orgId));
      if (idx > -1) {
        return orgs[idx];
      }
      return null;
    },

    getPotentialCollaborators: function(includeMe = false, includeProductEveryone = false) {
      return new Promise((resolve, reject) => {
        const potentialCollaborators = {};
        const orgs = this.getOrganizations();
        const productEveryone = this.getEveryoneProductGroup();
        Object.values(orgs).forEach(org => {
          if (org.getAccessRights()["read"]) {
            // maybe because of migration script, some users have access to the product everyone group
            // rely on the includeProductEveryone argument to exclude it if necessary
            if (org.getGroupId() === productEveryone.getGroupId() && !includeProductEveryone) {
              return;
            }
            org["collabType"] = 1;
            potentialCollaborators[org.getGroupId()] = org;
          }
        });
        const members = this.getReachableMembers();
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
          potentialCollaborators[productEveryone.getGroupId()] = productEveryone;
        }
        resolve(potentialCollaborators);
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
          const group = this.__addToGroupsCache(groupData);
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
            this.__deleteFromGroupsCache(groupId, workspaceId);
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
          this.__addToGroupsCache(groupData);
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

    __addToGroupsCache: function(groupData, groupType) {
      let group = this.groupsCached.find(f => f.getGroupId() === groupData["gid"]);
      if (group) {
        const props = Object.keys(qx.util.PropertyUtil.getProperties(osparc.data.model.Group));
        // put
        Object.keys(groupData).forEach(key => {
          if (props.includes(key)) {
            group.set(key, groupData[key]);
          }
        });
      } else {
        // get and post
        group = new osparc.data.model.Group(groupData).set({
          groupType
        });
        this.groupsCached.unshift(group);
      }
      return group;
    },

    __deleteFromGroupsCache: function(groupId, workspaceId) {
      const idx = this.groupsCached.findIndex(f => f.getGroupId() === groupId);
      if (idx > -1) {
        this.groupsCached.splice(idx, 1);
        return true;
      }
      return false;
    }
  }
});
