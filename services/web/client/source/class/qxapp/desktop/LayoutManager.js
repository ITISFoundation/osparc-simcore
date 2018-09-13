
qx.Class.define("qxapp.desktop.LayoutManager", {
  extend: qx.ui.container.Composite,

  construct: function() {
    this.base();

    this.set({
      layout: new qx.ui.layout.VBox()
    });

    this.__nodeCheck();

    this.__navBar = this.__createNavigationBar();
    this.__navBar.setHeight(100);
    this.add(this.__navBar);

    this.__prjStack = this.__getPrjStack();

    this.add(this.__prjStack, {
      flex: 1
    });

    this.__navBar.addListener("HomePressed", function() {
      this.__prjStack.setSelection([this.__prjBrowser]);
      this.__navBar.setCurrentStatus("Browser");
    }, this);

    this.__prjBrowser.addListener("StartProject", function(e) {
      let project = e.getData();
      if (this.__prjEditor) {
        this.__prjStack.remove(this.__prjEditor);
      }
      this.__prjEditor = new qxapp.desktop.PrjEditor(project.getProjectId());
      this.__prjStack.add(this.__prjEditor);
      this.__prjStack.setSelection([this.__prjEditor]);
      this.__navBar.setCurrentStatus(project.getName());
      // this.__PrjEditor.showSettings(false);
    }, this);
  },

  events: {},

  members: {
    __navBar: null,
    __prjStack: null,
    __prjBrowser: null,
    __prjEditor: null,

    __createNavigationBar: function() {
      let navBar = new qxapp.desktop.NavigationBar();
      navBar.setCurrentStatus("Browser");
      return navBar;
    },

    __getPrjStack: function() {
      let prjStack = new qx.ui.container.Stack();

      this.__prjBrowser = new qxapp.desktop.PrjBrowser();
      prjStack.add(this.__prjBrowser);

      return prjStack;
    },

    __nodeCheck: function() {
      /** a little ajv test */
      let nodeCheck = new qx.io.request.Xhr("/resource/qxapp/node-meta-v0.0.1.json");
      nodeCheck.addListener("success", e => {
        let data = e.getTarget().getResponse();
        try {
          let ajv = new qxapp.wrappers.Ajv(data);
          let store = qxapp.data.Store.getInstance();
          [
            "builtInServicesRegistered",
            "servicesRegistered",
            "interactiveServicesRegistered"
          ].forEach(event => {
            store.addListener(event, ev => {
              const services = ev.getData();
              for (let i = 0; i < services.length; i++) {
                const service = services[i];
                let check = ajv.validate(service);
                console.log("services validation result " + service.key + ":", check);
              }
            }, this);
          });
          store.getBuiltInServicesAsync();
          store.getComputationalServices();
          store.getInteractiveServices();
        } catch (err) {
          console.error(err);
        }
      });
      nodeCheck.send();
    }
  }
});
