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

qx.Class.define("osparc.desktop.organizations.ServicesList", {
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
      const filter = new osparc.filter.TextFilter("text", "organizationServicesList").set({
        allowStretchX: true,
        margin: [0, 10, 5, 10]
      });
      return filter;
    },

    __getServicesList: function() {
      const servicesUIList = new qx.ui.form.List().set({
        decorator: "no-border",
        spacing: 3
      });

      const servicesModel = this.__servicesModel = new qx.data.Array();
      const servicesCtrl = new qx.data.controller.List(servicesModel, servicesUIList, "name");
      servicesCtrl.setDelegate({
        createItem: () => new osparc.desktop.organizations.SharedResourceListItem("service"),
        bindItem: (ctrl, item, id) => {
          ctrl.bindProperty("key", "model", null, item, id);
          ctrl.bindProperty("key", "key", null, item, id);
          ctrl.bindProperty("version", "version", null, item, id);
          ctrl.bindProperty("orgId", "orgId", null, item, id);
          ctrl.bindProperty("thumbnail", "thumbnail", null, item, id);
          ctrl.bindProperty("name", "title", null, item, id);
          ctrl.bindProperty("description", "subtitleMD", null, item, id);
          ctrl.bindProperty("accessRights", "accessRights", {
            converter: data => data.get(item.getOrgId())
          }, item, id);
        },
        configureItem: item => {
          item.subscribeToFilterGroup("organizationTemplatesList");
          item.addListener("openMoreInfo", e => {
            const serviceKey = e.getData()["key"];
            const serviceVersion = e.getData()["version"];
            osparc.store.Services.getService(serviceKey, serviceVersion)
              .then(serviceData => {
                if (serviceData) {
                  serviceData["resourceType"] = "service";
                  const resourceDetails = new osparc.dashboard.ResourceDetails(serviceData).set({
                    showOpenButton: false
                  });
                  osparc.dashboard.ResourceDetails.popUpInWindow(resourceDetails);
                }
              });
          });
        }
      });

      return servicesUIList;
    },

    __reloadOrgServices: function() {
      const servicesModel = this.__servicesModel;
      servicesModel.removeAll();

      const orgModel = this.__currentOrg;
      if (orgModel === null) {
        return;
      }

      const groupId = orgModel.getGroupId();
      osparc.store.Services.getServicesLatest()
        .then(servicesLatest => {
          const orgServices = [];
          Object.keys(servicesLatest).forEach(key => {
            const serviceLatest = servicesLatest[key];
            if (groupId in serviceLatest["accessRights"]) {
              orgServices.push(serviceLatest);
            }
          });
          orgServices.forEach(orgService => {
            const orgServiceCopy = osparc.utils.Utils.deepCloneObject(orgService);
            orgServiceCopy["orgId"] = groupId;
            if (orgServiceCopy["thumbnail"] === null) {
              orgServiceCopy["thumbnail"] = osparc.dashboard.CardBase.PRODUCT_ICON;
            }
            servicesModel.append(qx.data.marshal.Json.createModel(orgServiceCopy));
          });
        });
    }
  }
});
