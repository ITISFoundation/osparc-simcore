/* global window */
qx.Class.define("qxapp.desktop.PrjEditor", {
  extend: qx.ui.splitpane.Pane,

  construct: function(projectId) {
    this.base(arguments, "horizontal");

    let splitter = this.__splitter = this.getChildControl("splitter");

    const settingsWidth = this.__settingsWidth = 600;

    let workbenchData = {};
    if (projectId !== null) {
      workbenchData = qxapp.dev.fake.Data.getProjectList()[projectId].workbench;
    }
    let workbench = this.__workbench = new qxapp.components.workbench.Workbench(workbenchData);
    let settingsBox = this.__settingsBox = new qx.ui.container.Composite(new qx.ui.layout.Canvas()).set({
      minWidth: 0,
      visibility: "excluded",
      maxWidth: settingsWidth
    });

    let settingsBoxContent = new qx.ui.container.Composite(new qx.ui.layout.VBox(10, null, "separator-vertical"));
    settingsBox.add(settingsBoxContent, {
      top: 0,
      left: 0,
      right: 0,
      bottom: 0
    });

    let miniWorkbenchView = this.__miniWorkbenchView = new qxapp.components.workbench.WorkbenchMini(workbenchData);
    settingsBoxContent.add(miniWorkbenchView, {
      flex: 1
    });

    let extraView = this.__extraView = new qx.ui.container.Composite(new qx.ui.layout.Canvas()).set({
      backgroundColor: "blue"
    });
    settingsBoxContent.add(extraView, {
      flex: 1
    });

    let settingsView = this.__settingsView = new qxapp.components.workbench.SettingsView();
    settingsBoxContent.add(settingsView, {
      flex: 1
    });

    settingsBox.addListener("changeWidth", e => {
      let width = e.getData();
      if (width != 0) {
        miniWorkbenchView.setWidth(width);
        extraView.setWidth(width);
        settingsView.setWidth(width);
      }
    });

    this.add(workbench, 0);
    this.add(settingsBox, 1);

    workbench.addListenerOnce("appear", () => {
      workbench.getContentElement().getDomElement()
        .addEventListener("transitionend", () => {
          [
            miniWorkbenchView,
            extraView,
            settingsView,
            splitter,
            settingsBox,
            workbench
          ].forEach(w => {
            w.resetDecorator();
          });
          if (settingsBox.getWidth() === 0) {
            settingsBox.exclude();
          }
        });
    });


    this.showSettings(true);

    this.__settingsView.addListener("SettingsEdited", function() {
      this.showSettings(false);
    }, this);

    this.__settingsView.addListener("ShowViewer", function(e) {
      let data = e.getData();
      let viewerWin = this.__createBrowserWindow(data.url, data.name);

      //  const metadata = e.getData().metadata;
      //  const nodeId = e.getData().nodeId;
      //  let url = "http://" + window.location.hostname + ":" + metadata.viewer.port;
      //  let viewerWin = this.__createBrowserWindow(url, metadata.name);

      this.__workbench.addWindowToDesktop(viewerWin);

      // Workaround for updating inputs
      if (data.name === "3d-viewer") {
        let urlUpdate = "http://" + window.location.hostname + ":" + data.viewer.port + "/retrieve";
        let req = new qx.io.request.Xhr();
        req.set({
          url: urlUpdate,
          method: "POST"
        });
        req.send();
      }

      const slotName = "openDynamic";
      let socket = qxapp.wrappers.WebSocket.getInstance();
      let args = {
        serviceName: data.name,
        nodeId: data.nodeId
      };
      socket.emit(slotName, args);
    }, this);

    this.__workbench.addListener("NodeDoubleClicked", function(e) {
      let node = e.getData();
      this.__settingsView.setNode(node);
      this.showSettings(true);
    }, this);

    this.__transDeco = new qx.ui.decoration.Decorator().set({
      transitionProperty: ["left", "right", "width"],
      transitionDuration: "0.3s",
      transitionTimingFunction: "ease"
    });

    this.__settingsBox.set({
      decorator: this.__transDeco
    });
    this.__miniWorkbenchView.set({
      decorator: this.__transDeco
    });
    this.__extraView.set({
      decorator: this.__transDeco
    });
    this.__settingsView.set({
      decorator: this.__transDeco
    });
    this.__workbench.set({
      decorator: this.__transDeco
    });
    this.__splitter.set({
      decorator: this.__transDeco
    });
  },

  members: {
    __pane: null,
    __miniWorkbenchView: null,
    __extraView: null,
    __settingsView: null,
    __settingsBox: null,
    __workbench: null,
    __settingsWidth: null,
    __transDeco: null,
    __splitter: null,

    showSettings: function(showSettings) {
      console.log("showSettings", showSettings);
      if (showSettings) {
        this.__settingsBox.show();
      }
      qx.ui.core.queue.Manager.flush();
      this.__settingsBox.set({
        width: showSettings ? Math.round(this.__settingsWidth * 0.75) : 0
      });
    },

    __createBrowserWindow: function(url, name) {
      console.log("Accessing:", url);
      let win = new qx.ui.window.Window(name);
      win.setShowMinimize(false);
      win.setLayout(new qx.ui.layout.VBox(5));
      let iframe = new qx.ui.embed.Iframe().set({
        width: 1050,
        height: 700,
        minWidth: 600,
        minHeight: 500,
        source: url,
        decorator : null
      });
      win.add(iframe, {
        flex: 1
      });
      win.moveTo(150, 150);

      win.addListener("dblclick", function(e) {
        e.stopPropagation();
      });

      return win;
    }
  }
});
