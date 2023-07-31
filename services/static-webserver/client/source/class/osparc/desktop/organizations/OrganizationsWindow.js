/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.desktop.organizations.OrganizationsWindow", {
  extend: osparc.ui.window.SingletonWindow,

  construct: function() {
    this.base(arguments, "organizations", this.tr("Organizations"));

    this.set({
      layout: new qx.ui.layout.VBox(),
      modal: true,
      width: 550,
      height: 660,
      showMaximize: false,
      showMinimize: false,
      appearance: "service-window"
    });

    this.__buildLayout();
  },

  statics: {
    openWindow: function() {
      const orgsWindow = new osparc.desktop.organizations.OrganizationsWindow();
      orgsWindow.center();
      orgsWindow.open();
      return orgsWindow;
    },

    evaluateOrganizationsButton: function(btn) {
      if (!osparc.data.Permissions.getInstance().canDo("user.organizations.create")) {
        btn.exclude();
        return;
      }
      osparc.data.Resources.get("organizations")
        .then(resp => {
          const orgs = resp["organizations"];
          if (orgs.length) {
            btn.show();
          }
        });
    }
  },

  members: {
    __stack: null,
    __orgsList: null,
    __orgDetails: null,

    __buildLayout: function() {
      const stack = this.__stack = new qx.ui.container.Stack();
      this.add(stack, {
        flex: 1
      });

      const orgsPage = this.__orgsList = new osparc.desktop.organizations.OrganizationsList();
      const orgDetails = this.__orgDetails = new osparc.desktop.organizations.OrganizationDetails();
      stack.add(orgsPage);
      stack.add(orgDetails);

      orgsPage.addListener("organizationSelected", e => {
        const orgId = e.getData();
        this.openOrganizationDetails(orgId);
      });

      orgDetails.addListener("backToOrganizations", () => {
        this.getChildControl("title").setValue(this.tr("Organizations"));
        this.__stack.setSelection([orgsPage]);
        orgsPage.reloadOrganizations();
      });
    },

    openOrganizationDetails: function(organizationId) {
      const openOrgDetails = orgId => {
        const orgModel = this.__orgsList.getOrgModel(orgId);
        this.__orgDetails.setCurrentOrg(orgModel);
        this.getChildControl("title").setValue(this.tr("Organization details"));
        this.__stack.setSelection([this.__orgDetails]);
      };
      if (this.__orgsList.isOrganizationsLoaded()) {
        openOrgDetails(organizationId);
      } else {
        this.__orgsList.addListenerOnce("changeOrganizationsLoaded", () => openOrgDetails(organizationId));
      }
    }
  }
});
