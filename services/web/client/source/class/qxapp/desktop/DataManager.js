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

/**
 * Widget that provides access to the data belonging to the active user.
 * - On the left side: myData FilesTree with the FileLabelWithActions
 * - On the right side: a pie chart reflecting the data resources consumed (hidden until there is real info)
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let dataManager = new qxapp.desktop.DataManager();
 *   this.getRoot().add(dataManager);
 * </pre>
 */

/* global document */

qx.Class.define("qxapp.desktop.DataManager", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    const prjBrowserLayout = new qx.ui.layout.VBox(10);
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
      const dataManagerMainLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(20));

      const label = new qx.ui.basic.Label(this.tr("Data Manager")).set({
        font: qx.bom.Font.fromConfig(qxapp.theme.Font.fonts["nav-bar-label"]),
        minWidth: 150
      });
      dataManagerMainLayout.add(label);

      const dataManagerControl = new qx.ui.container.Composite(new qx.ui.layout.HBox(20));

      // button for refetching data
      const reloadBtn = new qx.ui.form.Button().set({
        icon: "@FontAwesome5Solid/sync-alt/16"
      });
      reloadBtn.addListener("execute", function() {
        this.__initResources();
      }, this);
      dataManagerControl.add(reloadBtn);

      const toDatCore = new qxapp.ui.form.LinkButton(this.tr("To DAT-Core"), "https://app.blackfynn.io");
      dataManagerControl.add(toDatCore);

      dataManagerMainLayout.add(dataManagerControl);

      const dataManagerLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(20));
      dataManagerMainLayout.add(dataManagerLayout, {
        flex: 1
      });

      const treeLayout = this.__createTreeLayout();
      dataManagerLayout.add(treeLayout, {
        flex: 1
      });

      const showPieChart = false;
      if (showPieChart) {
        const chartLayout = this.__createChartLayout();
        dataManagerLayout.add(chartLayout);
      }

      this._add(dataManagerMainLayout);
    },

    __createTreeLayout: function() {
      const treeLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));

      const filesTree = this.__tree = new qxapp.file.FilesTree().set({
        dragMechnism: true,
        dropMechnism: true,
        minHeight: 600
      });
      filesTree.addListener("selectionChanged", () => {
        this.__selectionChanged();
      }, this);
      filesTree.addListener("fileCopied", e => {
        if (e) {
          this.__initResources();
        }
      }, this);
      filesTree.addListener("modelChanged", () => {
        this.__reloadChartData();
      }, this);
      treeLayout.add(filesTree, {
        flex: 1
      });

      const addBtn = new qxapp.file.FilesAdd();
      addBtn.addListener("fileAdded", e => {
        this.__initResources();
      }, this);
      treeLayout.add(addBtn);

      const selectedFileLayout = this.__selectedFileLayout = new qxapp.file.FileLabelWithActions();
      selectedFileLayout.addListener("fileDeleted", () => {
        this.__initResources();
      }, this);
      treeLayout.add(selectedFileLayout);

      return treeLayout;
    },

    __createChartLayout: function() {
      let chartLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));

      const label = new qx.ui.basic.Label(this.tr("Data Resources")).set({
        font: qx.bom.Font.fromConfig(qxapp.theme.Font.fonts["nav-bar-label"]),
        minWidth: 500
      });
      chartLayout.add(label);

      const plotlyDivId = "DataResources";
      const plotly = new qxapp.component.widget.PlotlyWidget(plotlyDivId);
      plotly.addListener("plotlyWidgetReady", e => {
        if (e.getData()) {
          this.__pieChart = plotly;
          const myPlot = document.getElementById(plotlyDivId);
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
      const selectionData = this.__tree.getSelectedFile();
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
