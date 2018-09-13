/* global window */
qx.Class.define("qxapp.desktop.PrjEditor", {
  extend: qx.ui.splitpane.Pane,

  construct: function(projectId) {
    this.base(arguments, "horizontal");

    let splitter = this.__splitter = this.getChildControl("splitter");

    const settingsWidth = this.__settingsWidth = 500;
    let settingsView = this.__settingsView = new qxapp.components.workbench.SettingsView().set({
      width: Math.round(0.75 * settingsWidth)
    });

    let settingsBox = this.__settingsBox = new qx.ui.container.Composite(new qx.ui.layout.Canvas()).set({
      minWidth: 0,
      visibility: "excluded",
      maxWidth: settingsWidth,
      width: Math.round(0.75 * settingsWidth)
    });

    settingsBox.add(settingsView, {
      top: 0,
      right: 0
    });

    this.add(settingsBox, 0);

    settingsBox.addListener("changeWidth", e => {
      let width = e.getData();
      if (width != 0) {
        settingsView.setWidth(width);
      }
    });

    let workbenchData = this.__getProjectDocument(projectId);
    let workbench = this.__workbench = new qxapp.components.workbench.Workbench(workbenchData);
    this.add(workbench, 1);

    workbench.addListenerOnce("appear", () => {
      workbench.getContentElement().getDomElement()
        .addEventListener("transitionend", () => {
          [
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



    this.showSettings(false);

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
        let urlUpdate = data.url + "/retrieve";
        let req = new qx.io.request.Xhr();
        req.set({
          url: urlUpdate,
          method: "POST"
        });
        req.send();
      }
    }, this);

    // this.__settingsView.addListener("NodeProgress", function(e) {
    //  const nodeId = e.getData()[0];
    //  const progress = e.getData()[1];
    //  this.__workbench.updateProgress(nodeId, progress);
    // }, this);

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
  },

  members: {
    __pane: null,
    __settingsView: null,
    __settingsBox: null,
    __workbench: null,
    __settingsWidth: null,
    __transDeco: null,
    __splitter: null,
    __projectId: null,

    showSettings: function(showSettings) {
      if (showSettings) {
        this.__settingsBox.show();
      }
      qx.ui.core.queue.Manager.flush();
      this.__settingsBox.set({
        decorator: this.__transDeco,
        width: showSettings ? Math.round(this.__settingsWidth * 0.75) : 0
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

    __getProjectDocument: function(projectId) {
      let workbenchData = {};
      if (projectId === null || projectId === undefined) {
        projectId = qxapp.utils.Utils.uuidv4();
      } else {
        workbenchData = qxapp.data.Store.getInstance().getProjectList()[projectId].workbench;
      }
      this.__projectId = projectId;

      return workbenchData;
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
