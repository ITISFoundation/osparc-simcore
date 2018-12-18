
qx.Class.define("qxapp.desktop.LayoutManager", {
  extend: qx.ui.container.Composite,

  construct: function() {
    this.base();

    this.__createLoadingLayout();
    this.__initResources();
  },

  events: {},

  members: {
    __navBar: null,
    __prjStack: null,
    __prjBrowser: null,
    __prjEditor: null,
    __servicesReady: null,
    __userReady: null,

    __createLoadingLayout: function() {
      const interval = 250;
      let loadingTimer = new qx.event.Timer(interval);
      loadingTimer.addListener("interval", () => {
        if (this.__userReady) {
          loadingTimer.stop();
          this.__createMainLayout();
        }
      }, this);
      loadingTimer.start();

      this.set({
        layout: new qx.ui.layout.Canvas()
      });

      const loadingUri = qxapp.utils.Utils.getLoaderUri(this.tr("User Information"));
      let iframe = new qx.ui.embed.Iframe(loadingUri);
      this.add(iframe, {
        left: 0,
        top: 0,
        right: 0,
        bottom: 0
      });
    },

    __createMainLayout: function() {
      this.removeAll();

      this.set({
        layout: new qx.ui.layout.VBox()
      });

      this.__navBar = this.__createNavigationBar();
      this.__navBar.setHeight(100);
      this.__navBar.addListener("NodeDoubleClicked", e => {
        if (this.__prjEditor) {
          let nodeId = e.getData();
          this.__prjEditor.nodeSelected(nodeId);
        }
      }, this);
      this.add(this.__navBar);

      let prjStack = this.__prjStack = new qx.ui.container.Stack();

      this.__prjBrowser = new qxapp.desktop.PrjBrowser();
      prjStack.add(this.__prjBrowser);

      this.add(this.__prjStack, {
        flex: 1
      });

      this.__navBar.addListener("DashboardPressed", function() {
        this.__prjStack.setSelection([this.__prjBrowser]);
        this.__prjBrowser.reloadUserProjects();
        this.__navBar.setMainViewCaption("Dashboard");
      }, this);

      this.__prjBrowser.addListener("StartProject", e => {
        const data = e.getData();
        const projectModel = data.projectModel;
        if (this.__prjEditor) {
          this.__prjStack.remove(this.__prjEditor);
        }
        this.__prjEditor = new qxapp.desktop.PrjEditor(projectModel);
        this.__prjStack.add(this.__prjEditor);
        this.__prjStack.setSelection([this.__prjEditor]);
        this.__navBar.setProjectModel(projectModel);
        this.__navBar.setMainViewCaption(projectModel.getWorkbenchModel().getPathIds("root"));

        this.__prjEditor.addListener("ChangeMainViewCaption", function(ev) {
          const elements = ev.getData();
          this.__navBar.setMainViewCaption(elements);
        }, this);
      }, this);
    },

    __createNavigationBar: function() {
      let navBar = new qxapp.desktop.NavigationBar();
      navBar.setMainViewCaption("Dashboard");
      return navBar;
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
    },

    __initResources: function() {
      this.__getUserProfile();
      this.__getServicesPreload();
    },

    __getUserProfile: function() {
      let store = qxapp.data.Store.getInstance();
      store.addListener("UserProfileRecieved", e => {
        this.__userReady = e.getData();
      }, this);
      store.loadUserRole();
    },

    __getServicesPreload: function() {
      let store = qxapp.data.Store.getInstance();
      store.addListener("servicesRegistered", e => {
        this.__nodeCheck(e.getData());
        this.__servicesReady = e.getData();
      }, this);
      store.getServices(true);
    }
  }
});
