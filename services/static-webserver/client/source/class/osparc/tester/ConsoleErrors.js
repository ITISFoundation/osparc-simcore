/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.tester.ConsoleErrors", {
  extend: osparc.po.BaseView,
  construct: function() {
    this.base(arguments);
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "filter-message": {
          control = new qx.ui.form.TextField().set({
            liveUpdate : true,
            placeholder: this.tr("Search in Message"),
          });
          this._add(control);
          break;
        }
        case "messages-table": {
          const tableModel = new qx.ui.table.model.Filtered();
          tableModel.setColumns([
            this.tr("Date"),
            this.tr("Message"),
          ]);
          const custom = {
            tableColumnModel: function(obj) {
              return new qx.ui.table.columnmodel.Resize(obj);
            }
          };
          control = new qx.ui.table.Table(tableModel, custom).set({
            selectable: true,
            statusBarVisible: false,
            showCellFocusIndicator: false,
            forceLineHeight: false
          });
          control.getTableColumnModel().setDataCellRenderer(
            0,
            new qx.ui.table.cellrenderer.String().set({
              defaultCellStyle: "user-select: text"
            })
          );
          control.getTableColumnModel().setDataCellRenderer(
            1,
            new osparc.ui.table.cellrenderer.Html().set({
              defaultCellStyle: "user-select: text; text-wrap: wrap"
            })
          );
          control.setColumnWidth(0, 80);

          // control.setDataRowRenderer(new osparc.ui.table.rowrenderer.ExpandSelection(control));
          this._add(control, {
            flex: 1
          });
          break;
        }
        case "error-viewer":
          control = new qx.ui.form.TextArea().set({
            autoSize: true,
          });
          this._add(control, {
            flex: 1
          });
          break;
      }
      return control || this.base(arguments, id);
    },

    _buildLayout: function() {
      const filterMessage = this.getChildControl("filter-message");
      const table = this.getChildControl("messages-table");
      const errorViewer = this.getChildControl("error-viewer");

      const model = table.getTableModel();
      filterMessage.addListener("changeValue", e => {
        const value = e.getData();
        model.resetHiddenRows();
        model.addNotRegex(value, "Message", true);
        model.applyFilters();
      });
      table.addListener("cellTap", e => {
        const selectedRow = e.getRow();
        const rowData = table.getTableModel().getRowData(selectedRow);
        errorViewer.setValue(JSON.stringify(rowData[1]));
      }, this);

      this.__populateTable();
    },

    __populateTable: function() {
      const consoleErrorTracker = osparc.ConsoleErrorTracker.getInstance();
      const errors = consoleErrorTracker.getErrors();
      const errorsArray = [];
      errors.forEach(msg => {
        errorsArray.push({
          date: msg.date,
          message: msg.error,
        });
      });
      errorsArray.sort((a, b) => {
        return new Date(b.date) - new Date(a.date); // newest first
      });
      const datas = [];
      errorsArray.forEach(entry => {
        const data = [
          new Date(entry.date).toLocaleTimeString(),
          entry.message,
        ];
        datas.push(data);
      });
      this.getChildControl("messages-table").getTableModel().setData(datas);
    }
  }
});
