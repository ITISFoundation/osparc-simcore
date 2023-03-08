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

qx.Class.define("osparc.desktop.preferences.pages.OrganizationServicesList", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    this._add(this.__createIntroText());
    this._add(this.__getServicesFilter());
    this._add(this.__getServicesList(), {
      flex: 1
    });
  },

  members: {
    __currentOrg: null,
    __servicesModel: null,

    setCurrentOrg: function(orgModel) {
      if (orgModel === null) {
        return;
      }
      this.__currentOrg = orgModel;
      this.__reloadOrgServices();
    },

    __createIntroText: function() {
      const msg = this.tr("This is the list of services shared with this Organization");
      const intro = new qx.ui.basic.Label().set({
        value: msg,
        alignX: "left",
        rich: true,
        font: "text-13"
      });
      return intro;
    },

    __getServicesFilter: function() {
      const filter = new osparc.component.filter.TextFilter("name", "organizationServicesList").set({
        allowStretchX: true,
        margin: [0, 10, 5, 10]
      });
      return filter;
    },

    __getServicesList: function() {
      const servicesUIList = new qx.ui.form.List().set({
        decorator: "no-border",
        spacing: 3,
        width: 150,
        backgroundColor: "background-main-2"
      });

      const servicesModel = this.__servicesModel = new qx.data.Array();
      const servicesCtrl = new qx.data.controller.List(servicesModel, servicesUIList, "name");
      servicesCtrl.setDelegate({
        createItem: () => new osparc.dashboard.ListButtonItem(),
        bindItem: (ctrl, item, id) => {
          ctrl.bindProperty("resourceData", "resourceData", null, item, id);
        },
        configureItem: item => {
          item.subscribeToFilterGroup("organizationServicesList");
        }
      });

      return servicesUIList;
    },

    __reloadOrgServices: function() {
      const membersModel = this.__servicesModel;
      membersModel.removeAll();

      const orgModel = this.__currentOrg;
      if (orgModel === null) {
        return;
      }
      return;
    }
  }
});
