/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/* eslint no-warning-comments: "off" */

qx.Class.define("qxapp.desktop.ServiceBrowser", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    let prjBrowserLayout = new qx.ui.layout.VBox(10);
    this._setLayout(prjBrowserLayout);

    let iframe = qxapp.utils.Utils.createLoadingIFrame(this.tr("Services"));
    this._add(iframe, {
      flex: 1
    });

    const interval = 1000;
    let userTimer = new qx.event.Timer(interval);
    userTimer.addListener("interval", () => {
      if (this.__servicesReady) {
        userTimer.stop();
        this._removeAll();
        iframe.dispose();
        this.__createServicesLayout();
      }
    }, this);
    userTimer.start();

    this.__initResources();
  },

  members: {
    __servicesReady: null,

    __initResources: function() {
      this.__getServicesPreload();
    },

    __getServicesPreload: function() {
      let store = qxapp.data.Store.getInstance();
      store.addListener("servicesRegistered", e => {
        // Do not validate if are not taking actions
        // this.__nodeCheck(e.getData());
        this.__servicesReady = e.getData();
      }, this);
      store.getServices(true);
    },

    __createServicesLayout: function() {
      const navBarLabelFont = qx.bom.Font.fromConfig(qxapp.theme.Font.fonts["nav-bar-label"]);
      let servicesLabel = new qx.ui.basic.Label(this.tr("Services")).set({
        font: navBarLabelFont,
        minWidth: 150
      });
      this._add(servicesLabel);

      let servicesLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
      /*
      // create and add the lists
      var serviceNamesList = new qx.ui.form.List();
      servicesLayout.add(serviceNamesList);
      var serviceVersionsList = new qx.ui.form.List();
      servicesLayout.add(serviceVersionsList);
      let serviceInfoLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
      servicesLayout.add(serviceInfoLayout);


      // create the controllers, one for each list
      // and set the name in the data for the label
      var controller1 = new qx.data.controller.List(null, serviceNamesList);
      controller1.setLabelPath("name");
      var controller2 = new qx.data.controller.List(null, serviceVersionsList);
      controller2.setLabelPath("name");

      // create the data store
      var url = qx.util.ResourceManager.getInstance().toUri("demobrowser/demo/data/finder.json");
      var store = new qx.data.store.Json(url);

      // connect the store and the first controller
      store.bind("model.files", controller1, "model");
      // connect the rest of the controllers
      controller1.bind("selection[0].files", controller2, "model");
      */
      this._add(servicesLayout);
    },

    __nodeCheck: function(services) {
      /** a little ajv test */
      let nodeCheck = new qx.io.request.Xhr("/resource/qxapp/node-meta-v0.0.1.json");
      nodeCheck.addListener("success", e => {
        let data = e.getTarget().getResponse();
        try {
          let ajv = new qxapp.wrappers.Ajv(data);
          for (const srvId in services) {
            const service = services[srvId];
            let check = ajv.validate(service);
            console.log("services validation result " + service.key + ":", check);
          }
        } catch (err) {
          console.error(err);
        }
      }, this);
      nodeCheck.send();
    }
  }
});
