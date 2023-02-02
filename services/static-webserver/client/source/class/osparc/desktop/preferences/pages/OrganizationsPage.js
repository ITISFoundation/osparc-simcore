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
  },

  statics: {
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
      return 0;
    }
  },

  members: {
    __createPages: function() {
      const pages = new qx.ui.container.Stack();
      const orgsPage = new osparc.desktop.preferences.pages.OrganizationsList();
      const membersPage = new osparc.desktop.preferences.pages.OrganizationMembersList();
      pages.add(orgsPage);
      pages.add(membersPage);
      this.add(pages, {
        flex: 1
      });

      orgsPage.addListener("organizationSelected", e => {
        const currentOrg = e.getData();
        if (currentOrg) {
          membersPage.setCurrentOrg(currentOrg);
          pages.setSelection([membersPage]);
        }
      });

      membersPage.addListener("backToOrganizations", () => {
        pages.setSelection([orgsPage]);
        orgsPage.reloadOrganizations();
      });

      orgsPage.reloadOrganizations();
    }
  }
});
