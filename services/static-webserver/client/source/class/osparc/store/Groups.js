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
      init: {},
      event: "organizationsChanged",
    },

    groupMe: {
      check: "osparc.data.model.Group",
      init: {}
    },
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
            label: myAuthData.getUsername(),
            description: `${myAuthData.getFirstName()} ${myAuthData.getLastName()} - ${myAuthData.getEmail()}`,
            thumbnail: osparc.utils.Avatar.emailToThumbnail(myAuthData.getEmail(), myAuthData.getUsername()),
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
              this.__addMemberToCache(orgMember, groupId);
            });
          }
        });
    },

    fetchGroupsAndMembers: function() {
      return new Promise(resolve => {
        this.__fetchGroups()
          .then(orgs => {
            // reset Users
            const usersStore = osparc.store.Users.getInstance();
            usersStore.resetUsers();
            const promises = Object.keys(orgs).map(orgId => this.__fetchGroupMembers(orgId));
            Promise.all(promises)
              .then(() => resolve())
              .catch(err => console.error(err));
          });
      })
    },

    getAllGroups: function() {
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

      return allGroupsAndUsers;
    },

    getMyGroupId: function() {
      return osparc.auth.Data.getInstance().getGroupId();
    },

    getOrganizationIds: function() {
      return Object.keys(this.getOrganizations());
    },

    getAllMyGroupIds: function() {
      return [
        this.getMyGroupId(),
        ...this.getOrganizationIds().map(gId => parseInt(gId)),
        this.getEveryoneProductGroup().getGroupId(),
        this.getEveryoneGroup().getGroupId(),
      ]
    },

    getGroup: function(groupId) {
      const groups = [];

      const groupMe = this.getGroupMe();
      groupMe["collabType"] = 2;
      groups.push(groupMe);

      const usersStore = osparc.store.Users.getInstance();
      const users = usersStore.getUsers();
      users.forEach(user => {
        user["collabType"] = 2;
        groups.push(user);
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

      if (includeProductEveryone && productEveryone) {
        productEveryone["collabType"] = 0;
        potentialCollaborators[productEveryone.getGroupId()] = productEveryone;
      }

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

      if (includeMe) {
        const myGroup = this.getGroupMe();
        myGroup["collabType"] = 2;
        potentialCollaborators[myGroup.getGroupId()] = myGroup;
      }

      const usersStore = osparc.store.Users.getInstance();
      const users = usersStore.getUsers();
      users.forEach(user => {
        user["collabType"] = 2;
        potentialCollaborators[user.getGroupId()] = user;
      });

      return potentialCollaborators;
    },

    getOrganization: function(groupId) {
      groupId = parseInt(groupId);
      if (groupId && groupId in this.getOrganizations()) {
        return this.getOrganizations()[groupId];
      }
      return null;
    },

    getUserByUserId: function(userId) {
      if (userId) {
        const usersStore = osparc.store.Users.getInstance();
        const users = usersStore.getUsers();
        return users.find(user => user.getUserId() === userId);
      }
      return null;
    },

    getUserByGroupId: function(groupId) {
      if (groupId) {
        const usersStore = osparc.store.Users.getInstance();
        const users = usersStore.getUsers();
        return users.find(user => user.getGroupId() === groupId);
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

    getGroupMemberByUsername: function(orgId, username) {
      const org = this.getGroup(orgId);
      if (org) {
        return org.getGroupMemberByUsername(username);
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
    addMember: function(orgId, username, email = null) {
      const gid = parseInt(orgId);
      const params = {
        url: {
          "gid": gid
        },
        data: {},
      };
      if (email) {
        params.data["email"] = email;
      } else {
        params.data["userName"] = username;
      }
      return osparc.data.Resources.fetch("organizationMembers", "post", params)
        .then(() => {
          // the backend doesn't return the user back,
          // so fetch them all again and return the user
          return this.__fetchGroupMembers(gid);
        })
        .then(() => {
          const groupMember = email ? this.getGroupMemberByLogin(gid, email) : this.getGroupMemberByUsername(gid, username);
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

    __addMemberToCache: function(orgMember, orgId = null) {
      const userMember = new osparc.data.model.UserMember(orgMember);
      if (orgId) {
        const organization = this.getOrganization(orgId);
        if (organization) {
          organization.addGroupMember(userMember);
        }
      }
      osparc.store.Users.getInstance().addUser(orgMember);
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
