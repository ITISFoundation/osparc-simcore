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

qx.Class.define("osparc.pricing.ServicesList", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(5));

    this.getChildControl("services-list");
    this.getChildControl("add-service");
  },

  properties: {
    pricingPlanId: {
      check: "Number",
      init: null,
      nullable: false,
      apply: "__fetchServices"
    }
  },

  members: {
    __model: null,
    __servicesModel: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "services-list": {
          control = new osparc.service.ServiceList("adminPanel");
          const scrolledServices = new qx.ui.container.Scroll();
          scrolledServices.add(control);
          this._addAt(scrolledServices, 0, {
            flex: 1
          });
          break;
        }
        case "add-service":
          control = new qx.ui.form.Button().set({
            appearance: "form-button",
            label: this.tr("Add Service"),
            alignX: "center",
            icon: "@FontAwesome5Solid/plus/14",
            allowGrowX: false
          });
          control.addListener("execute", () => this.__openAddServiceToPlan());
          this._addAt(control, 1);
          break;
      }
      return control || this.base(arguments, id);
    },

    __fetchServices: function() {
      const params = {
        url: {
          pricingPlanId: this.getPricingPlanId()
        }
      };
      osparc.data.Resources.fetch("billableServices", "get", params)
        .then(data => this.__populateList(data));
    },

    __populateList: function(services) {
      const sList = [];
      services.forEach(service => {
        const serviceKey = service["serviceKey"];
        const serviceVersion = service["serviceVersion"];
        const serviceMetaData = osparc.service.Utils.getMetaData(serviceKey, serviceVersion);
        if (serviceMetaData) {
          sList.push(qx.data.marshal.Json.createModel(serviceMetaData));
        }
      });

      const servicesList = this.getChildControl("services-list");
      servicesList.setModel(new qx.data.Array(sList));
    },

    __openAddServiceToPlan: function() {
      const srvCat = new osparc.workbench.ServiceCatalog();
      srvCat.addListener("addService", e => {
        const data = e.getData();
        const service = data.service;
        console.log(service);
        const params = {
          url: {
            pricingPlanId: this.getPricingPlanId()
          },
          data: {
            serviceKey: service.getKey(),
            serviceVersion: service.getVersion()
          }
        };
        osparc.data.Resources.fetch("billableServices", "post", params)
          .then(() => this.__fetchServices());
      });
      srvCat.center();
      srvCat.open();
    }
  }
});
