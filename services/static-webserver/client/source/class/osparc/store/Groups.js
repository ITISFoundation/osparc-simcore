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
          this.setOrganizations(orgs);
          this.setGroupMe(groupMe);
          const myAuthData = osparc.auth.Data.getInstance();
          groupMe.set({
            label: osparc.data.model.User.namesToLabel(myAuthData.getFirstName(), myAuthData.getLastName()),
            description: myAuthData.getEmail(),
            thumbnail: osparc.data.model.User.emailToThumbnail(myAuthData.getEmail()),
          })
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

    getAllGroupsAndUsers: function() {
      const allGroupsAndUsers = {};

      const groupEveryone = this.getEveryoneGroup();
      allGroupsAndUsers[groupEveryone.getGroupId()] = groupEveryone;

      const groupProductEveryone = this.getEveryoneProductGroup();
      allGroupsAndUsers[groupProductEveryone.getGroupId()] = groupProductEveryone;

      const groupMe = this.getGroupMe();
      allGroupsAndUsers[groupMe.getGroupId()] = groupMe;

      Object.values(this.getOrganizations()).forEach(organization => {
        allGroupsAndUsers[organization.getGroupId()] = organization;
      });

      Object.values(this.getReachableUsers()).forEach(reachableUser => {
        allGroupsAndUsers[reachableUser.getGroupId()] = reachableUser;
      });

      return allGroupsAndUsers;
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
        const myGroup = this.getGroupMe();
        myGroup["collabType"] = 2;
        potentialCollaborators[myGroup.getGroupId()] = myGroup;
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

    getGroupMemberByUserId: function(orgId, userId) {
      const org = this.getGroup(orgId);
      if (org) {
        return org.getGroupMemberByUserId(userId);
      }
      return null;
    },

    getGroupMemberByLogin: function(orgId, userEmail) {
      const org = this.getGroup(orgId);
      if (org) {
        return org.getGroupMemberByLogin(userEmail);
      }
      return null;
    },

    // CRUD GROUP
    postOrganization: function(name, description, thumbnail) {
      const newGroupData = {
        "label": name,
        "description": description,
        "thumbnail": thumbnail || null
      };
      const params = {
        data: newGroupData
      };
      let group = null;
      return osparc.data.Resources.fetch("organizations", "post", params)
        .then(groupData => {
          group = this.__addToGroupsCache(groupData, "organization");
          this.getOrganizations()[group.getGroupId()] = group;
          return this.__fetchGroupMembers(group.getGroupId());
        })
        .then(() => {
          return group;
        });
    },

    deleteOrganization: function(groupId) {
      const params = {
        url: {
          "gid": groupId
        }
      };
      return osparc.data.Resources.fetch("organizations", "delete", params)
        .then(() => {
          this.__deleteFromGroupsCache(groupId);
          delete this.getOrganizations()[groupId];
        });
    },

    patchOrganization: function(groupId, name, description, thumbnail) {
      const params = {
        url: {
          "gid": groupId
        },
        data: {
          "label": name,
          "description": description,
          "thumbnail": thumbnail || null
        }
      };
      return osparc.data.Resources.fetch("organizations", "patch", params)
        .then(() => {
          const organization = this.getOrganization(groupId);
          if (organization) {
            organization.set({
              label: name,
              description: description,
              thumbnail: thumbnail || null
            });
          }
        });
    },
    // CRUD GROUP

    // CRUD GROUP MEMBERS
    postMember: function(orgId, newMemberEmail) {
      const gid = parseInt(orgId);
      const params = {
        url: {
          "gid": gid
        },
        data: {
          "email": newMemberEmail
        }
      };
      return osparc.data.Resources.fetch("organizationMembers", "post", params)
        .then(() => {
          // the backend doesn't return the user back,
          // so fetch them all again and return the user
          return this.__fetchGroupMembers(gid);
        })
        .then(() => {
          const groupMember = this.getGroupMemberByLogin(gid, newMemberEmail);
          if (groupMember) {
            return groupMember;
          }
          return null;
        });
    },

    patchAccessRights: function(orgId, userId, newAccessRights) {
      const gid = parseInt(orgId);
      const uid = parseInt(userId);
      const params = {
        url: {
          gid,
          uid,
        },
        data: {
          "accessRights": newAccessRights
        }
      };
      return osparc.data.Resources.fetch("organizationMembers", "patch", params)
        .then(() => {
          const groupMember = this.getGroupMemberByUserId(gid, uid);
          if (groupMember) {
            groupMember.setAccessRights(newAccessRights);
            return groupMember;
          }
          return null;
        });
    },

    removeMember: function(orgId, userId) {
      const params = {
        url: {
          "gid": parseInt(orgId),
          "uid": parseInt(userId),
        }
      };
      return osparc.data.Resources.fetch("organizationMembers", "delete", params)
        .then(() => {
          this.__removeUserFromCache(parseInt(userId), parseInt(orgId));
        });
    },
    // CRUD GROUP MEMBERS

    __addToGroupsCache: function(groupData, groupType) {
      let group = this.groupsCached.find(f => f.getGroupId() === groupData["gid"]);
      if (!group) {
        group = new osparc.data.model.Group(groupData).set({
          groupType
        });
        this.groupsCached.unshift(group);
      }
      return group;
    },

    __deleteFromGroupsCache: function(groupId) {
      delete this.getOrganizations()[groupId];
    },

    __addToUsersCache: function(user, orgId = null) {
      if (orgId) {
        const organization = this.getOrganization(orgId);
        if (organization) {
          organization.addGroupMember(user);
        }
      }
      this.getReachableUsers()[user.getGroupId()] = user;
    },

    __removeUserFromCache: function(userId, orgId) {
      if (orgId) {
        const organization = this.getOrganization(orgId);
        if (organization) {
          organization.removeGroupMember(userId)
        }
      }
    },
  }
});
