/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 *
 */

qx.Class.define("osparc.file.FolderViewer", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    this.getChildControl("folder-name");
    this.getChildControl("view-options");
  },

  properties: {
    folder: {
      check: "qx.core.Object",
      nullable: true,
      event: "changeFolder",
      apply: "__applyFolder"
    },

    mode: {
      check: ["list", "icons"],
      init: "list",
      nullable: false,
      event: "changeMode",
      apply: "__reloadFolderContent"
    }
  },

  events: {
    "requestDatasetFiles": "qx.event.type.Data"
  },

  statics: {
    getItemButton: function() {
      return new qx.ui.form.ToggleButton().set({
        iconPosition: "top",
        width: 80,
        padding: 5
      });
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
        case "header":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox());
          this._add(control);
          break;
        case "folder-name": {
          const header = this.getChildControl("header");
          control = new qx.ui.basic.Label(this.tr("Select Folder")).set({
            font: "title-16",
            allowGrowX: true,
            alignY: "middle"
          });
          header.addAt(control, 0, {
            flex: 1
          });
          break;
        }
        case "view-options": {
          const header = this.getChildControl("header");
          control = new qx.ui.form.MenuButton(this.tr("View"));
          const menu = new qx.ui.menu.Menu();
          const listBtn = new qx.ui.menu.Button(this.tr("List"));
          listBtn.addListener("execute", () => {
            this.setMode("list");
          });
          menu.add(listBtn);
          const iconsBtn = new qx.ui.menu.Button(this.tr("Icons"));
          iconsBtn.addListener("execute", () => {
            this.setMode("icons");
          });
          menu.add(iconsBtn);
          control.setMenu(menu);
          header.addAt(control, 1);
          break;
        }
        case "table": {
          const tableModel = new qx.ui.table.model.Simple();
          tableModel.setColumns([
            this.tr("-"),
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
          control.setColumnWidth(this.self().T_POS.NAME, 300);
          this.bind("mode", control, "visibility", {
            converter: mode => mode === "list" ? "visible" : "excluded"
          });
          this._add(control, {
            flex: 1
          });
          break;
        }
        case "icons-layout": {
          control = new qx.ui.container.Composite(new qx.ui.layout.Flow());
          this.bind("mode", control, "visibility", {
            converter: mode => mode === "icons" ? "visible" : "excluded"
          });
          this._add(control, {
            flex: 1
          });
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    __getEmptyEntry: function() {
      const items = [];
      if (this.getMode() === "list") {
        items.push([
          "",
          this.tr("Empty folder"),
          "",
          "",
          ""
        ]);
      } else if (this.getMode() === "icons") {
        items.push(this.self().getItemButton().set({
          label: this.tr("Empty folder")
        }));
      }
      return items;
    },

    __convertEntries: function(content) {
      const items = [];
      if (this.getMode() === "list") {
        content.forEach(entry => {
          const row = [];
          row.push(this.__getIcon(entry));
          row.push(entry.getLabel());
          row.push(entry.getLastModified ? entry.getLastModified() : "");
          row.push(entry.getSize ? entry.getSize() : "");
          row.push(entry.getItemId());
          items.push(row);
        });
      } else if (this.getMode() === "icons") {
        content.forEach(entry => {
          const btn = this.self().getItemButton().set({
            label: entry.getLabel(),
            icon: this.__getIcon(entry),
            toolTipText: entry.getLabel()
          });
          btn.itemId = entry.getItemId();
          items.push(btn);
        });
      }
      return items;
    },

    __getIcon: function(entry) {
      return this.__isFolder(entry) ? "@MaterialIcons/folder" : "@MaterialIcons/insert_drive_file";
    },

    __isFolder: function(entry) {
      if (entry.getIsDataset) {
        return entry.getIsDataset();
      }
      if (entry.getChildren) {
        return entry.getChildren().length;
      }
      return false;
    },

    __getEntries: function() {
      if (this.getFolder()) {
        const children = this.getFolder().getChildren().toArray();
        return this.__convertEntries(children);
      }
      return [];
    },

    __applyFolder: function() {
      this.bind("folder", this.getChildControl("folder-name"), "value", {
        converter: folder => folder ? folder.getLabel() : "Select folder"
      });

      if (this.getFolder().getLoaded && !this.getFolder().getLoaded()) {
        this.fireDataEvent("requestDatasetFiles", {
          locationId: this.getFolder().getLocation(),
          datasetId: this.getFolder().getPath()
        });
      }

      this.getFolder().getChildren().addListener("change", () => {
        this.__reloadFolderContent();
      }, this);
      this.__reloadFolderContent();
    },

    __reloadFolderContent: function() {
      let entries = this.__getEntries();
      if (entries.length === 0) {
        entries = this.__getEmptyEntry();
      }
      if (this.getMode() === "list") {
        const table = this.getChildControl("table");
        table.setData(entries);
      } else if (this.getMode() === "icons") {
        const iconsLayout = this.getChildControl("icons-layout");
        iconsLayout.removeAll();
        const iconsGroup = new qx.ui.form.RadioGroup();
        entries.forEach(entry => {
          iconsGroup.add(entry);
          iconsLayout.add(entry);
        });
      }
    }
  }
});
