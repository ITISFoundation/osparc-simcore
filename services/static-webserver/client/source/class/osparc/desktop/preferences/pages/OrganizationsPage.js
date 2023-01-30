/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Pedro Crespo (pcrespov)

************************************************************************ */

/**
 *  Organization and members in preferences dialog
 *
 */

qx.Class.define("osparc.desktop.preferences.pages.OrganizationsPage", {
  extend: osparc.desktop.preferences.pages.BasePage,

  construct: function() {
    const iconSrc = "@FontAwesome5Solid/sitemap/24";
    const title = this.tr("Organizations");
    this.base(arguments, title, iconSrc);

    this.__createPages();

    this.__orgsPage.reloadOrganizations();
  },

  statics: {
    getNoReadAccess: function() {
      return {
        "read": false,
        "write": false,
        "delete": false
      };
    },

    getReadAccess: function() {
      return {
        "read": true,
        "write": false,
        "delete": false
      };
    },

    getWriteAccess: function() {
      return {
        "read": true,
        "write": true,
        "delete": false
      };
    },

    getDeleteAccess: function() {
      return {
        "read": true,
        "write": true,
        "delete": true
      };
    },

    sortByAccessRights: function(a, b) {
      const aAccessRights = a["accessRights"];
      const bAccessRights = b["accessRights"];
      if (aAccessRights["delete"] !== bAccessRights["delete"]) {
        return bAccessRights["delete"] - aAccessRights["delete"];
      }
      if (aAccessRights["write"] !== bAccessRights["write"]) {
        return bAccessRights["write"] - aAccessRights["write"];
      }
      if (aAccessRights["read"] !== bAccessRights["read"]) {
        return bAccessRights["read"] - aAccessRights["read"];
      }
      if (("label" in a) && ("label" in b)) {
        // orgs
        return a["label"].localeCompare(b["label"]);
      }
      if (("login" in a) && ("login" in b)) {
        // members
        return a["login"].localeCompare(b["login"]);
      }
      return 0;
    }
  },

  members: {
    __orgsPage: null,
    __membersPage: null,

    __createPages: function() {
      const pages = new qx.ui.container.Stack();
      const orgsPage = this.__orgsPage = new osparc.desktop.preferences.pages.OrganizationsList();
      const membersPage = this.__memebersPage = new osparc.desktop.preferences.pages.OrganizationMembers();
      pages.add(orgsPage);
      pages.add(membersPage);
      this.add(pages, {
        flex: 1
      });

      orgsPage.addListener("organizationSelected", e => {
        const currentOrg = e.getData();
        membersPage.setCurrentOrg(currentOrg);
        pages.setSelection([membersPage]);
      });
    }
  }
});
