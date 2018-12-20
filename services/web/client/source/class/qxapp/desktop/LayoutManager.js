/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/* eslint no-warning-comments: "off" */

qx.Class.define("qxapp.desktop.LayoutManager", {
  extend: qx.ui.container.Composite,

  construct: function() {
    this.base();

    this.set({
      layout: new qx.ui.layout.VBox()
    });

    this.__navBar = this.__createNavigationBar();
    this.__navBar.setHeight(100);
    this.__navBar.addListener("nodeDoubleClicked", e => {
      if (this.__prjEditor) {
        let nodeId = e.getData();
        this.__prjEditor.nodeSelected(nodeId);
      }
    }, this);
    this.add(this.__navBar);

    let prjStack = this.__prjStack = new qx.ui.container.Stack();
    this.add(prjStack, {
      flex: 1
    });

    let iframe = this.__createLoadingIFrame(this.tr("User Information"));
    this.__prjStack.add(iframe);
    this.__prjStack.setSelection([iframe]);

    const interval = 1000;
    let userTimer = new qx.event.Timer(interval);
    userTimer.addListener("interval", () => {
      if (this.__userReady) {
        userTimer.stop();
        this.__prjStack.remove(iframe);
        iframe.dispose();
        this.__createMainLayout();
      }
    }, this);
    userTimer.start();

    this.__initResources();
  },

  events: {},

  members: {
    __navBar: null,
    __prjStack: null,
    __prjBrowser: null,
    __prjEditor: null,
    __userReady: null,
    __servicesReady: null,

    __createLoadingIFrame: function(text) {
      const loadingUri = qxapp.utils.Utils.getLoaderUri(text);
      let iframe = new qx.ui.embed.Iframe(loadingUri);
      iframe.setBackgroundColor("transparent");
      return iframe;
    },

    __createMainLayout: function() {
      this.__prjBrowser = new qxapp.desktop.PrjBrowser();
      this.__prjStack.add(this.__prjBrowser);

      this.__navBar.addListener("dashboardPressed", function() {
        this.__prjStack.setSelection([this.__prjBrowser]);
        this.__prjBrowser.reloadUserProjects();
        this.__navBar.setMainViewCaption(this.tr("Dashboard"));
      }, this);

      this.__prjBrowser.addListener("startProject", e => {
        const projectData = e.getData();
        if (this.__servicesReady === null) {
          let iframe = this.__createLoadingIFrame(this.tr("Services"));
          this.__prjStack.add(iframe);
          this.__prjStack.setSelection([iframe]);

          const interval = 1000;
          let servicesTimer = new qx.event.Timer(interval);
          servicesTimer.addListener("interval", () => {
            if (this.__servicesReady) {
              servicesTimer.stop();
              this.__prjStack.remove(iframe);
              iframe.dispose();
              this.__loadProjectModel(projectData);
            }
          }, this);
          servicesTimer.start();
        } else {
          this.__loadProjectModel(projectData);
        }
      }, this);
    },

    __loadProjectModel: function(projectData) {
      let projectModel = new qxapp.data.model.ProjectModel(projectData);

      if (this.__prjEditor) {
        this.__prjStack.remove(this.__prjEditor);
      }
      this.__prjEditor = new qxapp.desktop.PrjEditor(projectModel);
      this.__prjStack.add(this.__prjEditor);
      this.__prjStack.setSelection([this.__prjEditor]);
      this.__navBar.setProjectModel(projectModel);
      this.__navBar.setMainViewCaption(projectModel.getWorkbenchModel().getPathIds("root"));

      this.__prjEditor.addListener("changeMainViewCaption", function(ev) {
        const elements = ev.getData();
        this.__navBar.setMainViewCaption(elements);
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
      let permissions = qxapp.data.Permissions.getInstance();
      permissions.addListener("userProfileRecieved", e => {
        this.__userReady = e.getData();
      }, this);
      permissions.loadUserRoleFromBackend();
    },

    __getServicesPreload: function() {
      let store = qxapp.data.Store.getInstance();
      store.addListener("servicesRegistered", e => {
        // Do not validate if are not taking actions
        // this.__nodeCheck(e.getData());
        this.__servicesReady = e.getData();
      }, this);
      store.getServices(true);
    }
  }
});
