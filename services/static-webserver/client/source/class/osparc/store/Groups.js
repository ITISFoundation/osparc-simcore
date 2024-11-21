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

    reachableUsers: {
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

    __fetchGroups: function() {
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
          const group = this.getOrganization(groupId);
          if (group) {
            // reset group's group members
            group.setGroupMembers({});
            orgMembers.forEach(orgMember => {
              const user = new osparc.data.model.User(orgMember);
              this.__addToUsersCache(user, groupId);
            });
          }
        });
    },

    fetchGroupsAndMembers: function() {
      return new Promise(resolve => {
        this.__fetchGroups()
          .then(orgs => {
            // reset Reachable Users
            this.resetReachableUsers();
            const promises = Object.keys(orgs).map(orgId => this.__fetchGroupMembers(orgId));
            Promise.all(promises)
              .then(() => resolve())
              .catch(err => console.error(err));
          });
      })
    },

    getMyGroupId: function() {
      return this.getGroupMe().getGroupId();
    },

    getOrganizationIds: function() {
      return Object.keys(this.getOrganizations());
    },

    getGroup: function(groupId) {
      const groups = [];

      const groupMe = this.getGroupMe();
      groupMe["collabType"] = 2;
      groups.push(groupMe);

      Object.values(this.getReachableUsers()).forEach(member => {
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
      const idx = groups.findIndex(group => group.getGroupId() === parseInt(groupId));
      if (idx > -1) {
        return groups[idx];
      }
      return null;
    },

    getPotentialCollaborators: function(includeMe = false, includeProductEveryone = false) {
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
      const members = this.getReachableUsers();
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
      return potentialCollaborators;
    },

    getOrganization: function(groupId) {
      if (groupId && groupId in this.getOrganizations()) {
        return this.getOrganizations()[groupId];
      }
      return null;
    },

    getUserByUserId: function(userId) {
      if (userId) {
        const visibleMembers = this.getReachableUsers();
        return Object.values(visibleMembers).find(member => member.getUserId() === userId);
      }
      return null;
    },

    getUserByGroupId: function(groupId) {
      if (groupId) {
        const visibleMembers = this.getReachableUsers();
        return Object.values(visibleMembers).find(member => member.getGroupId() === groupId);
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
          const group = this.getOrganization(groupId);
          if (group) {
            this.__deleteFromGroupsCache(groupId, workspaceId);
            this.fireDataEvent("groupRemoved", group);
          }
        })
        .catch(console.error);
    },

    putGroup: function(groupId, updateData) {
      const group = this.getOrganization(groupId);
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

    postMember: function(orgId, newMemberEmail) {
      const params = {
        url: {
          "gid": orgId
        },
        data: {
          "email": newMemberEmail
        }
      };
      osparc.data.Resources.fetch("organizationMembers", "post", params)
        .then(newMember => {
          const user = new osparc.data.model.User(newMember);
          this.__addToUsersCache(user, orgId);
          return user;
        })
        .catch(err => {
          const errorMessage = err["message"] || this.tr("Something went wrong adding the user");
          osparc.FlashMessenger.getInstance().logAs(errorMessage, "ERROR");
          console.error(err);
        });
    },

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
    },

    __addToUsersCache: function(user, orgId = null) {
      if (orgId) {
        const organization = this.getOrganization(orgId);
        if (organization) {
          organization.getGroupMembers()[user.getGroupId()] = user;
        }
      }
      this.getReachableUsers()[user.getGroupId()] = user;
    }
  }
});
