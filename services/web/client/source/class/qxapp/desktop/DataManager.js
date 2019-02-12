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

/* global document */
/* eslint no-warning-comments: "off" */

qx.Class.define("qxapp.desktop.DataManager", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    let prjBrowserLayout = new qx.ui.layout.VBox(10);
    this._setLayout(prjBrowserLayout);

    this.__createDataManagerLayout();
    this.__initResources();
  },

  members: {
    __tree: null,
    __selectedFileLayout: null,
    __pieChart: null,

    __initResources: function() {
      this.__tree.populateTree();
    },

    __createDataManagerLayout: function() {
      let dataManagerMainLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(20));

      let label = new qx.ui.basic.Label(this.tr("Data Manager")).set({
        font: qx.bom.Font.fromConfig(qxapp.theme.Font.fonts["nav-bar-label"]),
        minWidth: 150
      });
      dataManagerMainLayout.add(label);

      let toDatCore = new qxapp.component.widget.LinkButton(this.tr("To DAT-Core"), "https://app.blackfynn.io");
      dataManagerMainLayout.add(toDatCore);

      let dataManagerLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(20));
      dataManagerMainLayout.add(dataManagerLayout, {
        flex: 1
      });

      let treeLayout = this.__createTreeLayout();
      dataManagerLayout.add(treeLayout, {
        flex: 1
      });

      let chartLayout = this.__createChartLayout();
      dataManagerLayout.add(chartLayout);

      this._add(dataManagerMainLayout);
    },

    __createTreeLayout: function() {
      let treeLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));

      let filesTree = this.__tree = new qxapp.component.widget.FilesTree().set({
        dragMechnism: true,
        dropMechnism: true,
        minHeight: 600
      });
      filesTree.addListener("selectionChanged", () => {
        this.__selectionChanged();
      }, this);
      filesTree.addListener("fileCopied", e => {
        this.__initResources();
      }, this);
      filesTree.addListener("modelChanged", () => {
        this.__reloadChartData();
      }, this);
      treeLayout.add(filesTree, {
        flex: 1
      });

      let addBtn = new qxapp.component.widget.FilesAdd(this.tr("Add file(s)"));
      addBtn.addListener("fileAdded", e => {
        this.__initResources();
      }, this);
      treeLayout.add(addBtn);

      let selectedFileLayout = this.__selectedFileLayout = new qxapp.component.widget.FileLabelWithActions();
      selectedFileLayout.addListener("fileDeleted", () => {
        this.__initResources();
      }, this);
      treeLayout.add(selectedFileLayout);

      return treeLayout;
    },

    __createChartLayout: function() {
      let chartLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));

      let label = new qx.ui.basic.Label(this.tr("Data Resources")).set({
        font: qx.bom.Font.fromConfig(qxapp.theme.Font.fonts["nav-bar-label"]),
        minWidth: 500
      });
      chartLayout.add(label);

      const plotlyDivId = "DataResources";
      let plotly = new qxapp.component.widget.PlotlyWidget(plotlyDivId);
      plotly.addListener("plotlyWidgetReady", e => {
        if (e.getData()) {
          this.__pieChart = plotly;
          let myPlot = document.getElementById(plotlyDivId);
          myPlot.on("plotly_click", data => {
            this.__reloadChartData(data["points"][0]["id"][0]);
          }, this);
          this.__reloadChartData();
        }
      }, this);
      chartLayout.add(plotly, {
        flex: 1
      });

      return chartLayout;
    },

    __selectionChanged: function() {
      this.__tree.resetSelection();
      let selectionData = this.__tree.getSelectedFile();
      if (selectionData) {
        this.__selectedFileLayout.itemSelected(selectionData["selectedItem"], selectionData["isFile"]);
      }
    },

    __reloadChartData: function(pathId) {
      if (this.__pieChart) {
        const dataInfo = this.__getDataInfo(pathId);
        const ids = dataInfo["ids"];
        const labels = dataInfo["labels"];
        const values = dataInfo["values"];
        const tooltips = dataInfo["tooltips"];
        const title = dataInfo["title"];
        this.__pieChart.setData(ids, labels, values, tooltips, title);
      }
    },

    __getDataInfo: function(pathId) {
      const context = pathId || "/";
      const children = this.__tree.getModel().getChildren();

      let data = {
        "ids": [],
        "labels": [],
        "values": [],
        "tooltips": [],
        "title": context
      };
      if (pathId === undefined) {
        data["ids"].push("FreeSpaceId");
        data["labels"].push("Free space");
        const value = (Math.floor(Math.random()*1000000)+1);
        data["values"].push(value);
        data["tooltips"].push(qxapp.utils.Utils.bytesToSize(value));
      }
      for (let i=0; i<children.length; i++) {
        const child = children.toArray()[i];
        data["ids"].push(child.getLabel());
        data["labels"].push(child.getLabel());
        const value2 = (Math.floor(Math.random()*1000000)+1);
        data["values"].push(value2);
        data["tooltips"].push(qxapp.utils.Utils.bytesToSize(value2));
      }
      return data;
    }
  }
});
