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

qx.Class.define("osparc.file.FolderContent", {
  extend: qx.ui.container.Stack,

  construct: function() {
    this.base(arguments);

    this.getChildControl("icons-layout");
    this.getChildControl("table");
  },

  properties: {
    folder: {
      check: "qx.core.Object",
      init: null,
      nullable: true,
      event: "changeFolder",
      apply: "__applyFolder"
    },

    mode: {
      check: ["list", "icons"],
      init: "icons",
      nullable: false,
      event: "changeMode",
      apply: "__reloadFolderContent"
    },

    multiSelect: {
      check: "Boolean",
      init: false,
      nullable: false,
      event: "changeMultiSelect",
      apply: "__reloadFolderContent"
    },
  },

  events: {
    "selectionChanged": "qx.event.type.Data", // tap
    "itemSelected": "qx.event.type.Data", // dbltap
    "requestDatasetFiles": "qx.event.type.Data",
  },

  statics: {
    getItemButton: function() {
      const item = new qx.ui.form.ToggleButton().set({
        iconPosition: "top",
        width: 100,
        height: 80,
        padding: 3
      });
      item.getChildControl("label").set({
        rich: true,
        textAlign: "center",
        maxWidth: 100,
        maxHeight: 31
      });
      osparc.utils.Utils.setIdToWidget(item, "FolderViewerItem");
      return item;
    },

    T_POS: {
      TYPE: 0,
      NAME: 1,
      DATE: 2,
      SIZE: 3,
      ID: 4
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "table": {
          const tableModel = new qx.ui.table.model.Simple();
          tableModel.setColumns([
            "",
            this.tr("Name"),
            this.tr("Date Modified"),
            this.tr("Size"),
            this.tr("Id")
          ]);
          control = new osparc.ui.table.Table(tableModel, {
            // tableColumnModel: obj => new qx.ui.table.columnmodel.Resize(obj),
            initiallyHiddenColumns: [this.self().T_POS.ID]
          });
          control.getTableColumnModel().setDataCellRenderer(this.self().T_POS.TYPE, new qx.ui.table.cellrenderer.Image());
          control.setColumnWidth(this.self().T_POS.TYPE, 30);
          control.setColumnWidth(this.self().T_POS.NAME, 360);
          control.setColumnWidth(this.self().T_POS.DATE, 170);
          control.setColumnWidth(this.self().T_POS.SIZE, 70);
          this.bind("mode", control, "visibility", {
            converter: mode => mode === "list" ? "visible" : "excluded"
          });
          const scroll = new qx.ui.container.Scroll();
          scroll.add(control);
          this.add(scroll);
          break;
        }
        case "icons-layout": {
          control = new qx.ui.container.Composite(new qx.ui.layout.Flow(5, 5));
          osparc.utils.Utils.setIdToWidget(control, "FolderViewerIconsContent");
          this.bind("mode", control, "visibility", {
            converter: mode => mode === "icons" ? "visible" : "excluded"
          });
          const scroll = new qx.ui.container.Scroll();
          scroll.add(control);
          this.add(scroll);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    __convertEntries: function(content) {
      const items = [];
      if (this.getMode() === "list") {
        content.forEach(entry => {
          const row = [];
          row.push(entry.getIcon ? entry.getIcon() : this.__getIcon(entry));
          row.push(entry.getLabel());
          row.push(entry.getLastModified ? osparc.utils.Utils.formatDateAndTime(new Date(entry.getLastModified())) : "");
          row.push(entry.getSize ? osparc.utils.Utils.bytesToSize(entry.getSize()) : "");
          if (entry.getItemId) {
            row.push(entry.getItemId());
          }
          row.entry = entry;
          items.push(row);
        });
      } else if (this.getMode() === "icons") {
        content.forEach(entry => {
          let tt = entry.getLabel();
          if (entry.getSize) {
            tt += "<br>" + osparc.utils.Utils.bytesToSize(entry.getSize());
          }
          if (entry.getLastModified) {
            tt += "<br>" + osparc.utils.Utils.formatDateAndTime(new Date(entry.getLastModified()));
          }
          const item = this.self().getItemButton().set({
            label: entry.getLabel(),
            icon: entry.getIcon ? entry.getIcon() : this.__getIcon(entry),
            toolTipText: tt
          });
          const icon = item.getChildControl("icon", true);
          if (icon.getSource() === "@FontAwesome5Solid/circle-notch/12") {
            icon.setPadding(0);
            icon.setMarginRight(4);
            icon.getContentElement().addClass("rotate");
          }

          if (entry.getItemId) {
            item.itemId = entry.getItemId();
            this.__attachListenersToItems(item, entry);
          }
          items.push(item);
        });
      }
      return items;
    },

    __getIcon: function(entry) {
      return osparc.file.FilesTree.isDir(entry) ? "@MaterialIcons/folder" : "@MaterialIcons/insert_drive_file";
    },

    __getEntries: function() {
      if (this.getFolder()) {
        const children = this.getFolder().getChildren().toArray();
        return this.__convertEntries(children);
      }
      return [];
    },

    __applyFolder: function(folder) {
      if (folder) {
        if (folder.getLoaded && !folder.getLoaded()) {
          this.fireDataEvent("requestDatasetFiles", {
            locationId: folder.getLocation(),
            datasetId: folder.getPath()
          });
        }

        folder.getChildren().addListener("change", () => {
          this.__reloadFolderContent();
        }, this);
      }

      this.__reloadFolderContent();
    },

    __reloadFolderContent: function() {
      const entries = this.__getEntries();
      if (this.getMode() === "list") {
        const table = this.getChildControl("table");
        table.setData(entries);
        this.__attachListenersTotable(table);
      } else if (this.getMode() === "icons") {
        const iconsLayout = this.getChildControl("icons-layout");
        iconsLayout.removeAll();
        const iconsGroup = new qx.ui.form.RadioGroup().set({
          allowEmptySelection: true
        });
        entries.forEach(entry => {
          iconsGroup.add(entry);
          iconsLayout.add(entry);
        });
      }
      this.setSelection([this.getSelectables()[this.getMode() === "icons" ? 0 : 1]]);
    },

    __itemTapped: function(item) {
      this.fireDataEvent("selectionChanged", item);
    },

    __itemDblTapped: function(item) {
      this.fireDataEvent("itemSelected", item);
      if (osparc.file.FilesTree.isDir(item)) {
        this.setFolder(item);
      }
    },

    __attachListenersToItems: function(btn, entry) {
      btn.addListener("tap", () => {
        this.__itemTapped(entry);
      }, this);
      btn.addListener("dbltap", () => {
        this.__itemDblTapped(entry);
      }, this);
    },

    __attachListenersTotable: function(table) {
      table.addListener("cellTap", e => {
        const selectedRow = e.getRow();
        const rowData = table.getTableModel().getRowData(selectedRow);
        if ("entry" in rowData) {
          this.__itemTapped(rowData.entry);
        }
      }, this);
      table.addListener("cellDbltap", e => {
        const selectedRow = e.getRow();
        const rowData = table.getTableModel().getRowData(selectedRow);
        if ("entry" in rowData) {
          this.__itemDblTapped(rowData.entry);
        }
      }, this);
    }
  }
});
