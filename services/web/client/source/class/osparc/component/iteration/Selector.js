/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 *
 */

qx.Class.define("osparc.component.iteration.Selector", {
  extend: qx.ui.table.Table,

  /**
   * Constructor sets the model and general look.
   */
  construct: function(primaryStudy) {
    this.__model = new qx.ui.table.model.Simple();
    this.__model.setColumns([
      this.tr("SutdyId"),
      this.tr("Iteration"),
      this.tr("Variables"),
      this.tr("Show")
    ]);

    this.base(arguments, this.__model, {
      tableColumnModel: obj => new qx.ui.table.columnmodel.Resize(obj),
      initiallyHiddenColumns: [0]
    });

    const columnModel = this.getTableColumnModel();
    columnModel.getBehavior().setMinWidth(1, 80);
    columnModel.getBehavior().setMinWidth(2, 80);
    columnModel.getBehavior().setMinWidth(3, 50);

    this.getSelectionModel().setSelectionMode(qx.ui.table.selection.Model.SINGLE_SELECTION);

    this.__attachEventHandlers();
  },

  statics: {
    popUpInWindow: function(selectorWidget) {
      const window = new osparc.ui.window.Window(qx.locale.Manager.tr("Iteration Selector")).set({
        autoDestroy: true,
        layout: new qx.ui.layout.Grow(),
        showMinimize: false,
        showMaximize: false,
        resizable: true,
        width: 400,
        height: 400,
        clickAwayClose: true
      });
      window.add(selectorWidget);
      window.center();
      return window;
    }
  },

  events: {
    "openIteration": "qx.event.type.Data"
  },

  members: {
    __model: null,

    __attachEventHandlers: function() {
    }
  }
});
