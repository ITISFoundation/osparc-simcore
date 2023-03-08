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
    const iconSrc = "@FontAwesome5Solid/users/24";
    const title = this.tr("Organizations");
    this.base(arguments, title, iconSrc);

    this.__createPages();
  },

  members: {
    __stack: null,
    __orgsList: null,
    __orgDetails: null,

    __createPages: function() {
      const stack = this.__stack = new qx.ui.container.Stack();
      const orgsPage = this.__orgsList = new osparc.desktop.preferences.pages.OrganizationsList();
      const orgDetails = this.__orgDetails = new osparc.desktop.preferences.pages.OrganizationDetails();
      stack.add(orgsPage);
      stack.add(orgDetails);
      this.add(stack, {
        flex: 1
      });

      orgsPage.addListener("organizationSelected", e => {
        const orgId = e.getData();
        const orgModel = this.__orgsList.getOrgModel(orgId);
        this.__orgDetails.setCurrentOrg(orgModel);

        this.getChildControl("title").setValue(this.tr("Organization details"));
        this.__stack.setSelection([this.__orgDetails]);
      });

      orgDetails.addListener("backToOrganizations", () => {
        this.getChildControl("title").setValue(this.tr("Organizations"));
        this.__stack.setSelection([orgsPage]);
        orgsPage.reloadOrganizations();
      });
    }
  }
});
