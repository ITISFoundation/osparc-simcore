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
        minHeight: 600
      });
      filesTree.addListener("selectionChanged", () => {
        this.__selectionChanged();
      }, this);
      treeLayout.add(filesTree, {
        flex: 1
      });

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
          let myPlot = document.getElementById(plotlyDivId);
          myPlot.on("plotly_click", data => {
            console.log(data);
          }, this);
          const ids = ["FreeSpaceId", "SimcoreS3Id", "DatcoreId"];
          const labels = ["Free space", "simcore.s3", "datcore"];
          const values = [40, 16, 44];
          const tooltips = ["40KB", "16KB", "44KB"];
          plotly.setData(ids, labels, values, tooltips);
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

    __getDataInfo: function(path) {
      const dataInfo = {
        freeSpaceId: {
          label: "Free Space",
          value: "40"
        },
        simcoreId: {
          label: "simcore.s3",
          value: "5"
        },
        datcoreId: {
          label: "datcore",
          value: "50"
        }
      };
      let data = {};
      if (path === undefined) {
        data["ids"] = Object.keys(dataInfo);
      }
      return data;
    }
  }
});
