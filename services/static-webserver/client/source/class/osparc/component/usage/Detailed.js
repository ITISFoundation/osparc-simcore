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

qx.Class.define("osparc.component.usage.Detailed", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(20));

    Promise.all([
      osparc.data.Resources.dummy.getUsageOverview(),
      osparc.data.Resources.dummy.getUsageDetailed()
    ])
      .then(datas => this.__buildLayout(datas[0], datas[1]))
      .catch(err => console.error(err));
  },

  statics: {
    COLS: [{
      title: qx.locale.Manager.tr("Study Name"),
      type: () => new qx.ui.table.cellrenderer.String()
    }, {
      title: qx.locale.Manager.tr("Type"),
      type: () => new qx.ui.table.cellrenderer.String()
    }, {
      title: qx.locale.Manager.tr("Start time"),
      type: () => new qx.ui.table.cellrenderer.Date()
    }, {
      title: qx.locale.Manager.tr("Duration"),
      type: () => new qx.ui.table.cellrenderer.Number()
    }, {
      title: qx.locale.Manager.tr("Cores"),
      type: () => new qx.ui.table.cellrenderer.Number()
    }, {
      title: qx.locale.Manager.tr("Status"),
      type: () => new qx.ui.table.cellrenderer.String()
    }],

    detailedToData: function(detailed) {
      const data = [];
      detailed.forEach(job => {
        const jobData = [];
        jobData.push(job.studyName);
        jobData.push(job.jobType);
        const startDate = osparc.utils.Utils.formatDateAndTime(new Date(job.start));
        jobData.push(startDate);
        const duration = (job.duration/(60*60*1000)).toFixed(2);
        jobData.push(duration);
        jobData.push(job.numberOfCores);
        jobData.push(job.status);
        data.push(jobData);
      });
      return data;
    },

    popUpInWindow: function() {
      const usageDetailedView = new osparc.component.usage.Detailed();
      osparc.ui.window.Window.popUpInWindow(usageDetailedView, qx.locale.Manager.tr("Detailed Usage Overview"), 700, 500);
    }
  },

  members: {
    __buildLayout: function(overview, detailed) {
      this.__addComputing(overview.computing);
      this.__addDetailedTable(detailed);
    },

    __addComputing: function(computing) {
      const compLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));

      const title = new qx.ui.basic.Label().set({
        value: this.tr("Computational hours used"),
        font: "text-14"
      });
      compLayout.add(title);

      const compTotal = Math.round(computing.total/(60*60*1000));
      const compUsed = Math.round(computing.used/(60*60*1000));
      const remaining = new qx.ui.basic.Label().set({
        value: `${compUsed} of ${compTotal} CPU hours`,
        font: "text-14"
      });
      compLayout.add(remaining);

      const progress = new qx.ui.indicator.ProgressBar().set({
        height: 12,
        maximum: computing.total,
        value: computing.used
      });
      progress.getChildControl("progress").set({
        backgroundColor: "strong-main"
      });
      compLayout.add(progress);

      this._add(compLayout);
    },

    __addDetailedTable: function(detailed) {
      const model = new qx.ui.table.model.Simple();
      model.setColumns(this.self().COLS.map(col => col.title));

      const table = this.__loggerTable = new qx.ui.table.Table(model, {
        tableColumnModel: obj => new qx.ui.table.columnmodel.Resize(obj)
      }).set({
        selectable: true,
        statusBarVisible: false,
        showCellFocusIndicator: false,
        rowHeight: 25,
        forceLineHeight: false
      });
      const columnModel = table.getTableColumnModel();
      columnModel.getBehavior().setMinWidth(0, 60);
      columnModel.getBehavior().setMinWidth(1, 60);
      columnModel.getBehavior().setMinWidth(2, 60);
      columnModel.getBehavior().setMinWidth(5, 60);
      this.self().COLS.forEach((col, idx) => columnModel.setDataCellRenderer(idx, col.type.call(this)));

      model.setData(this.self().detailedToData(detailed));

      this._add(table);
    }
  }
});
