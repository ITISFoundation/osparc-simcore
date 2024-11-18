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

qx.Class.define("osparc.tester.WebSocketMessages", {
  extend: osparc.po.BaseView,
  construct: function() {
    this.base(arguments);
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "toolbar":
          control = new qx.ui.toolbar.ToolBar();
          this._add(control);
          break;
        case "filter-text": {
          const toolbar = this.getChildControl("toolbar");
          control = new qx.ui.form.TextField().set({
            appearance: "toolbar-textfield",
            liveUpdate: true,
            placeholder: this.tr("Filter")
          });
          osparc.utils.Utils.setIdToWidget(control, "logsFilterField");
          toolbar.add(control, {
            flex: 1
          });
          break;
        }
        case "messages-table": {
          const tableModel = new qx.ui.table.model.Simple();
          tableModel.setColumns([
            this.tr("Date"),
            this.tr("Channel"),
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
            1,
            new qx.ui.table.cellrenderer.String().set({
              defaultCellStyle: "user-select: text"
            })
          );
          control.getTableColumnModel().setDataCellRenderer(
            0,
            new qx.ui.table.cellrenderer.String().set({
              defaultCellStyle: "user-select: text"
            })
          );
          control.getTableColumnModel().setDataCellRenderer(
            2,
            new osparc.ui.table.cellrenderer.Html().set({
              defaultCellStyle: "user-select: text; text-wrap: wrap"
            })
          );
          control.setColumnWidth(0, 80);
          control.setColumnWidth(1, 150);

          control.setDataRowRenderer(new osparc.ui.table.rowrenderer.ExpandSelection(control));
          this._add(control, {
            flex: 1
          });
          break;
        }
        case "json-viewer":
          control = new osparc.ui.basic.JsonTreeWidget();
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    _buildLayout: function() {
      this.getChildControl("filter-text");
      const table = this.getChildControl("messages-table");
      const jsonViewer = this.getChildControl("json-viewer");

      table.addListener("cellTap", e => {
        const selectedRow = e.getRow();
        const rowData = table.getTableModel().getRowData(selectedRow);
        jsonViewer.setJson(JSON.parse(rowData[2]));
      }, this);

      this.__populateTable();
    },

    __populateTable: function() {
      const socket = osparc.wrapper.WebSocket.getInstance();
      const messagesObj = socket.getCachedMessages();
      const messagesArray = [];
      for (const channel in messagesObj) {
        messagesObj[channel].forEach(msg => {
          messagesArray.push({
            date: msg.date,
            channel,
            message: msg.message,
          });
        });
      }
      messagesArray.sort((a, b) => {
        return new Date(b.date) - new Date(a.date); // newest first
      });
      const datas = [];
      messagesArray.forEach(entry => {
        const data = [
          new Date(entry.date).toLocaleTimeString(),
          entry.channel,
          JSON.stringify(entry.message),
        ];
        datas.push(data);
      });
      this.getChildControl("messages-table").getTableModel().setData(datas);
    }
  }
});
