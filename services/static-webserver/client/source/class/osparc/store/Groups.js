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

    this.__groupsCached = [];
  },

  properties: {
    everyoneGroup: {
      check: "osparc.data.model.Group",
      init: null // this will stay null for guest users
    },

    everyoneProductGroup: {
      check: "osparc.data.model.Group",
      init: null // this will stay null for guest users
    },

    supportGroup: {
      check: "osparc.data.model.Group",
      init: null, // this will stay null for guest users
      nullable: true,
      event: "changeSupportGroup",
    },

    chatbot: {
      check: "osparc.data.model.Group",
      init: null,
      nullable: true,
      event: "changeChatbot",
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
    COLLAB_TYPE: {
      EVERYONE: "everyone",
      SUPPORT: "support",
      ORGANIZATION: "organization",
      USER: "user",
    },

    COLLAB_TYPE_ORDER: [
      "everyone", // osparc.store.Groups.COLLAB_TYPE.EVERYONE
      "support",  // osparc.store.Groups.COLLAB_TYPE.SUPPORT,
      "organization", // osparc.store.Groups.COLLAB_TYPE.ORGANIZATION
      "user", // osparc.store.Groups.COLLAB_TYPE.USER
    ],
  },

  members: {
    __groupsCached: null,
    __groupsPromiseCached: null,

    fetchGroups: function() {
      if (osparc.auth.Data.getInstance().isGuest()) {
        return new Promise(resolve => {
          resolve([]);
        });
      }

      if (this.__groupsPromiseCached) {
        return this.__groupsPromiseCached;
      }

      if (this.__groupsCached && this.__groupsCached.length) {
        return new Promise(resolve => {
          resolve(this.getOrganizations());
        });
      }

      const useCache = false;
      return this.__groupsPromiseCached = osparc.data.Resources.get("organizations", {}, useCache)
        .then(resp => {
          const everyoneGroup = this.__addToGroupsCache(resp["all"], "everyone");
          const productEveryoneGroup = this.__addToGroupsCache(resp["product"], "productEveryone");
          let supportGroup = null;
          if ("support" in resp && resp["support"]) {
            supportGroup = this.__addToGroupsCache(resp["support"], "support");
          }
          let chatbot = null;
          if ("chatbot" in resp && resp["chatbot"]) {
            chatbot = this.__addToGroupsCache(resp["chatbot"], "chatbot");
          }
          const groupMe = this.__addToGroupsCache(resp["me"], "me");
          const orgs = {};
          resp["organizations"].forEach(organization => {
            if (supportGroup && supportGroup.getGroupId() === organization["gid"]) {
              // support group was already added to the cache, but it was missing the accessRights
              // the accessRights come from the organization, update them
              supportGroup.setAccessRights(organization["accessRights"]);
            }
            const org = this.__addToGroupsCache(organization, "organization");
            orgs[org.getGroupId()] = org;
          });
          this.setEveryoneGroup(everyoneGroup);
          this.setEveryoneProductGroup(productEveryoneGroup);
          this.setSupportGroup(supportGroup);
          this.setChatbot(chatbot);
          this.setOrganizations(orgs);
          this.setGroupMe(groupMe);
          const myAuthData = osparc.auth.Data.getInstance();
          const description = osparc.data.model.User.userDataToDescription(myAuthData.getFirstName(), myAuthData.getLastName(), myAuthData.getEmail());
          groupMe.set({
            label: myAuthData.getUserName(),
            description,
            thumbnail: myAuthData.getAvatar(32),
          })
          return orgs;
        })
        .finally(() => {
          this.__groupsPromiseCached = null;
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
        })
        .catch(err => osparc.FlashMessenger.logError(err));
    },

    fetchGroupsAndMembers: function() {
      return new Promise(resolve => {
        this.fetchGroups()
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
      if (groupEveryone) {
        allGroupsAndUsers[groupEveryone.getGroupId()] = groupEveryone;
      }

      const groupProductEveryone = this.getEveryoneProductGroup();
      if (groupProductEveryone) {
        allGroupsAndUsers[groupProductEveryone.getGroupId()] = groupProductEveryone;
      }

      const supportGroup = this.getSupportGroup();
      if (supportGroup) {
        allGroupsAndUsers[supportGroup.getGroupId()] = supportGroup;
      }

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
      const allMyGroupIds = [
        this.getMyGroupId(),
        ...this.getOrganizationIds().map(gId => parseInt(gId))
      ];
      if (this.getEveryoneGroup()) {
        allMyGroupIds.push(this.getEveryoneGroup().getGroupId());
      }
      return allMyGroupIds;
    },

    getEveryoneGroupIds: function() {
      const everyoneGroupIds = this.getEveryoneGroups().map(g => g.getGroupId());
      return everyoneGroupIds;
    },

    getEveryoneGroups: function() {
      const everyoneGroups = [];
      if (this.getEveryoneProductGroup()) {
        everyoneGroups.push(this.getEveryoneProductGroup());
      }
      if (this.getEveryoneGroup()) {
        everyoneGroups.push(this.getEveryoneGroup());
      }
      return everyoneGroups;
    },

    isSupportEnabled: function() {
      return Boolean(this.getSupportGroup());
    },

    amIASupportUser: function() {
      const supportGroup = this.getSupportGroup();
      if (supportGroup) {
        const myOrgIds = this.getOrganizationIds().map(gId => parseInt(gId));
        return myOrgIds.includes(supportGroup.getGroupId());
      }
      return false;
    },

    getGroup: function(groupId) {
      const groups = [];

      const groupMe = this.getGroupMe();
      groupMe["collabType"] = osparc.store.Groups.COLLAB_TYPE.USER;
      groups.push(groupMe);

      const usersStore = osparc.store.Users.getInstance();
      const users = usersStore.getUsers();
      users.forEach(user => {
        user["collabType"] = osparc.store.Groups.COLLAB_TYPE.USER;
        groups.push(user);
      });

      Object.values(this.getOrganizations()).forEach(org => {
        org["collabType"] = osparc.store.Groups.COLLAB_TYPE.ORGANIZATION;
        groups.push(org);
      });

      const supportGroup = this.getSupportGroup();
      if (supportGroup && groups.findIndex(g => g.getGroupId() === supportGroup.getGroupId()) === -1) {
        supportGroup["collabType"] = osparc.store.Groups.COLLAB_TYPE.SUPPORT;
        groups.push(supportGroup);
      }

      const groupProductEveryone = this.getEveryoneProductGroup();
      if (groupProductEveryone) {
        groupProductEveryone["collabType"] = osparc.store.Groups.COLLAB_TYPE.EVERYONE;
        groups.push(groupProductEveryone);
      }

      const groupEveryone = this.getEveryoneGroup();
      if (groupEveryone) {
        groupEveryone["collabType"] = osparc.store.Groups.COLLAB_TYPE.EVERYONE;
        groups.push(groupEveryone);
      }
      const idx = groups.findIndex(group => group.getGroupId() === parseInt(groupId));
      if (idx > -1) {
        return groups[idx];
      }
      return null;
    },

    getPotentialCollaborators: function(includeMe = false, includeProductEveryone = false) {
      const potentialCollaborators = {};
      const orgs = this.getOrganizations();
      const supportGroup = this.getSupportGroup();
      const productEveryone = this.getEveryoneProductGroup();

      if (includeProductEveryone && productEveryone) {
        productEveryone["collabType"] = osparc.store.Groups.COLLAB_TYPE.EVERYONE;
        potentialCollaborators[productEveryone.getGroupId()] = productEveryone;
      }

      Object.values(orgs).forEach(org => {
        if (org.getAccessRights()["read"]) {
          // maybe because of migration script, some users have access to the product everyone group
          // rely on the includeProductEveryone argument to exclude it if necessary
          if (org.getGroupId() === productEveryone.getGroupId() && !includeProductEveryone) {
            return;
          }
          org["collabType"] = osparc.store.Groups.COLLAB_TYPE.ORGANIZATION;
          potentialCollaborators[org.getGroupId()] = org;
        }
      });

      if (supportGroup && !(supportGroup.getGroupId() in potentialCollaborators)) {
        supportGroup["collabType"] = osparc.store.Groups.COLLAB_TYPE.SUPPORT;
        potentialCollaborators[supportGroup.getGroupId()] = supportGroup;
      }

      if (includeMe) {
        const myGroup = this.getGroupMe();
        myGroup["collabType"] = osparc.store.Groups.COLLAB_TYPE.USER;
        potentialCollaborators[myGroup.getGroupId()] = myGroup;
      }

      const usersStore = osparc.store.Users.getInstance();
      const users = usersStore.getUsers();
      users.forEach(user => {
        user["collabType"] = osparc.store.Groups.COLLAB_TYPE.USER;
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

    getGroupMemberByUserName: function(orgId, userName) {
      const org = this.getGroup(orgId);
      if (org) {
        return org.getGroupMemberByUserName(userName);
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

    isChatbotEnabled: function() {
      return Boolean(this.getChatbot());
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
    addMember: function(orgId, userName, email = null) {
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
        params.data["userName"] = userName;
      }
      return osparc.data.Resources.fetch("organizationMembers", "post", params)
        .then(() => {
          // the backend doesn't return the user back,
          // so fetch them all again and return the user
          return this.__fetchGroupMembers(gid);
        })
        .then(() => {
          const groupMember = email ? this.getGroupMemberByLogin(gid, email) : this.getGroupMemberByUserName(gid, userName);
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
      let group = this.__groupsCached.find(f => f.getGroupId() === groupData["gid"]);
      if (!group) {
        group = new osparc.data.model.Group(groupData).set({
          groupType
        });
        this.__groupsCached.unshift(group);
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
